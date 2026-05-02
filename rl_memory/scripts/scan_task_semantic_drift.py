#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


ID_RE = re.compile(r"\b(?:[A-Z]{1,5}-[A-Z0-9]{2,}|PNR[0-9A-Z]+|RX-\d+|DR-\d+|APT-\d+|CONF-\d+)\b")
PHRASE_RE = re.compile(r"'([^']{3,})'|\"([^\"]{3,})\"")

GENERIC_CRITERIA_PATTERNS = (
    "about:blank",
    "chrome-error://",
)

OBSERVATIONAL_GOAL_PATTERNS = (
    r"\bopen\b",
    r"\bcheck\b",
    r"\breview\b",
    r"\bview\b",
    r"\binspect\b",
    r"\blook up\b",
    r"\bsee\b",
    r"\bfind out\b",
)

CONCEPT_PATTERNS = {
    "rent_lease": [r"\brent\b", r"\blease\b", r"\bapartment\b", r"\bproperty\b", r"\bhousing\b"],
    "maintenance_complaint": [r"\bmaintenance\b", r"\brepair\b", r"\bleak\w*\b", r"\bpipe\b", r"\bcomplaint\b", r"\bnoise\b", r"\bneighbor\b"],
    "airport_parking": [r"\bairport\b", r"\bparking\b"],
    "transfer_commute": [r"\btransfer\b", r"\bcommute\b", r"\btransport\b", r"\bself[_ -]?drive\b", r"\btaxi\b"],
    "flight_trip": [r"\bflight\b", r"\bhotel\b", r"\bvisa\b", r"\btrip\b", r"\btravel\b", r"\bpnr\b", r"\bcheck[- ]?in\b", r"\brebook\w*\b"],
    "bank_account": [r"\bbank\b", r"\baccount\b", r"\bbalance\b", r"\bchecking\b", r"\bsavings\b", r"\bloan\b"],
    "tax_bill_expense": [r"\btax\w*\b", r"\bbill\w*\b", r"\bexpense\b", r"\bautopay\b", r"\binvestment\b", r"\bfinance\b"],
    "email_calendar_job": [r"\bemail\b", r"\bcalendar\b", r"\bjob\b", r"\blinkedin\b"],
    "conference_paper_receipt": [r"\bconference\b", r"\bpaper\b", r"\breceipt\b"],
    "shopping_order": [r"\border\b", r"\bcoupon\b", r"\breturn\b", r"\bwarranty\b", r"\breview\b", r"\bauction\b", r"\bdelivery\b", r"\bprice\b", r"\bsale\b"],
    "food_subscription": [r"\bfood\b", r"\bpizza\b", r"\bsubscription\b", r"\brestaurant\b", r"\bmeal\b"],
    "prescription_refill": [r"\bprescription\w*\b", r"\brefill\w*\b", r"\bmedication\b", r"\brx-\d+\b"],
    "healthcare": [r"\bdoctor\b", r"\binsurance\b", r"\bvaccine\b", r"\bhealth\b", r"\bclaim\b"],
    "gov_civic": [r"\baddress\b", r"\bvehicle\b", r"\bpermit\b", r"\bparking permit\b", r"\bgovernment\b"],
    "voter": [r"\bvoter\b", r"\bvote\b", r"\bballot\b"],
    "library_book": [r"\blibrary\b", r"\bebook\b", r"\breservation\b"],
    "school_learning": [r"\bcourse\b", r"\bassignment\b", r"\bcertification\b", r"\bstudent\b"],
    "security_privacy": [r"\bpassword\b", r"\bprivacy\b", r"\bsecurity\b", r"\b2fa\b", r"\brecovery\b", r"\baudit\b", r"\bdata deletion\b"],
    "social": [r"\bparty\b", r"\broommate\b", r"\bdonation\b", r"\bgift\b", r"\brsvp\b", r"\bcharity\b", r"\bsplit\b"],
    "utilities_energy": [r"\butilit(?:y|ies)\b", r"\belectricity\b", r"\bwater\b", r"\bbroadband\b", r"\benergy\b", r"\bthermostat\b", r"\bbulb\b", r"\bmeter\b", r"\bcamera\b", r"\bsmart\b"],
}


def extract_ids(text: str) -> list[str]:
    return sorted(set(ID_RE.findall(text or "")))


def extract_phrases(text: str) -> list[str]:
    phrases = []
    for left, right in PHRASE_RE.findall(text or ""):
        phrase = left or right
        phrase = phrase.strip()
        if len(phrase) >= 4:
            if len(phrase.split()) > 6:
                continue
            if re.search(r"[.!?]", phrase):
                continue
            if not re.search(r"[A-Z0-9\u4e00-\u9fff]", phrase):
                continue
            phrases.append(phrase)
    return sorted(set(phrases))


def extract_domain_from_urls(text: str) -> list[str]:
    return sorted(set(re.findall(r"/([a-z0-9-]+\.local)/", text or "")))


def extract_concepts(text: str) -> set[str]:
    lower = (text or "").lower()
    lower = re.sub(r"[a-z0-9-]+\.local", " ", lower)
    lower = re.sub(r"(url|mem|json|exists|text)\s*\(", " ", lower)
    lower = re.sub(r"[_./]", " ", lower)
    found = set()
    for concept, patterns in CONCEPT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower):
                found.add(concept)
                break
    return found


def goal_is_observational(goal: str) -> bool:
    lower = (goal or "").lower()
    return any(re.search(pattern, lower) for pattern in OBSERVATIONAL_GOAL_PATTERNS)


def has_only_generic_criteria(criteria: list[str]) -> bool:
    if not criteria:
        return True
    concrete = False
    for item in criteria:
        lowered = item.lower()
        if any(pat in lowered for pat in GENERIC_CRITERIA_PATTERNS):
            continue
        if any(token in lowered for token in ("mem(", "json(", "text(", "exists(", "url().includes('/")):
            concrete = True
            break
    return not concrete


def summarize_oracle(steps: list[dict]) -> str:
    parts = []
    for step in steps:
        act = step.get("act", "")
        selector = step.get("selector", "")
        value = step.get("value", "")
        url = step.get("url", "")
        note = step.get("note", "")
        parts.append(f"{act} {selector} {value} {url} {note}".strip())
    return " | ".join(parts)


def analyze_task(task_dir: Path) -> dict:
    spec = json.loads((task_dir / "task_spec.json").read_text(encoding="utf-8"))
    oracle = json.loads((task_dir / "oracle_trace.json").read_text(encoding="utf-8"))

    goal = spec.get("goal", "")
    criteria = spec.get("success_criteria", [])
    criteria_text = "\n".join(criteria)
    oracle_steps = oracle.get("steps", [])
    oracle_text = summarize_oracle(oracle_steps)

    goal_ids = extract_ids(goal)
    criteria_ids = extract_ids(criteria_text)
    oracle_ids = extract_ids(oracle_text)

    goal_phrases = extract_phrases(goal)
    criteria_phrases = extract_phrases(criteria_text)
    oracle_phrases = extract_phrases(oracle_text)

    goal_concepts = extract_concepts(goal)
    criteria_concepts = extract_concepts(criteria_text)
    oracle_concepts = extract_concepts(oracle_text)

    flags: list[str] = []
    severity = 0

    mutating_steps = [s for s in oracle_steps if s.get("act") in {"click", "type", "select", "done"}]
    if not mutating_steps and not goal_is_observational(goal):
        flags.append("oracle_has_no_mutating_steps")
        severity += 3

    if has_only_generic_criteria(criteria):
        flags.append("criteria_are_generic_only")
        severity += 3

    missing_oracle_ids = [x for x in goal_ids if x not in oracle_ids]
    if missing_oracle_ids:
        flags.append(f"goal_ids_missing_in_oracle:{','.join(missing_oracle_ids)}")
        severity += 2

    missing_criteria_ids = [x for x in goal_ids if x not in criteria_ids]
    if missing_criteria_ids:
        flags.append(f"goal_ids_missing_in_criteria:{','.join(missing_criteria_ids)}")
        severity += 2

    missing_goal_phrases = []
    for phrase in goal_phrases:
        lowered = phrase.lower()
        if lowered not in criteria_text.lower() and lowered not in oracle_text.lower():
            missing_goal_phrases.append(phrase)
    if missing_goal_phrases:
        flags.append(f"goal_phrases_missing:{','.join(missing_goal_phrases)}")
        severity += 2

    if goal_concepts and oracle_concepts and goal_concepts.isdisjoint(oracle_concepts):
        flags.append(f"goal_vs_oracle_concepts_disjoint:{','.join(sorted(goal_concepts))}->{','.join(sorted(oracle_concepts))}")
        severity += 3

    if goal_concepts and criteria_concepts and goal_concepts.isdisjoint(criteria_concepts):
        flags.append(f"goal_vs_criteria_concepts_disjoint:{','.join(sorted(goal_concepts))}->{','.join(sorted(criteria_concepts))}")
        severity += 3

    oracle_domains = extract_domain_from_urls(oracle_text)
    criteria_domains = extract_domain_from_urls(criteria_text)
    if criteria_domains and oracle_domains and set(criteria_domains).isdisjoint(set(oracle_domains)):
        flags.append(f"criteria_vs_oracle_domain_mismatch:{','.join(criteria_domains)}->{','.join(oracle_domains)}")
        severity += 3

    return {
        "task": task_dir.name,
        "severity": severity,
        "flags": flags,
        "goal": goal,
        "goal_concepts": sorted(goal_concepts),
        "criteria_concepts": sorted(criteria_concepts),
        "oracle_concepts": sorted(oracle_concepts),
        "goal_ids": goal_ids,
        "criteria_ids": criteria_ids,
        "oracle_ids": oracle_ids,
        "oracle_domains": oracle_domains,
        "criteria_domains": criteria_domains,
        "oracle_step_count": len(oracle_steps),
        "oracle_mutating_step_count": len(mutating_steps),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-root", default="tasks")
    parser.add_argument("--min-severity", type=int, default=3)
    parser.add_argument("--out-json", default="")
    args = parser.parse_args()

    tasks_root = Path(args.tasks_root)
    reports = []
    for task_dir in sorted(p for p in tasks_root.iterdir() if p.is_dir()):
        spec_path = task_dir / "task_spec.json"
        oracle_path = task_dir / "oracle_trace.json"
        if not spec_path.exists() or not oracle_path.exists():
            continue
        try:
            report = analyze_task(task_dir)
        except Exception as exc:
            reports.append({
                "task": task_dir.name,
                "severity": 99,
                "flags": [f"parse_error:{exc}"],
            })
            continue
        if report["severity"] >= args.min_severity:
            reports.append(report)

    reports.sort(key=lambda x: (-x["severity"], x["task"]))
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"flagged_tasks\t{len(reports)}")
    for item in reports[:50]:
        print(f"{item['task']}\tseverity={item['severity']}\tflags={' | '.join(item['flags'])}")


if __name__ == "__main__":
    main()
