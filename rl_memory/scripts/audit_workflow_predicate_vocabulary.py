#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path("/Users/masteryth/Documents/webagent")
MODULE_LIBRARY = ROOT / "tasks" / "workflow_module_library.json"
VOCAB_PATH = ROOT / "tasks" / "workflow_predicate_vocabulary.json"
DEFAULT_OUTPUT_JSON = ROOT / ".task_sync_meta" / "workflow_predicate_audit.json"
DEFAULT_OUTPUT_MD = ROOT / ".task_sync_meta" / "workflow_predicate_audit.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit workflow predicate vocabulary quality and synchronization.")
    parser.add_argument("--modules", default=str(MODULE_LIBRARY))
    parser.add_argument("--vocab", default=str(VOCAB_PATH))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def suffix_match(predicate: str, suffix: str) -> bool:
    return predicate.endswith(suffix)


def token_match(predicate: str, token: str) -> bool:
    return token in predicate


def main() -> None:
    args = parse_args()
    modules = load_json(Path(args.modules))["modules"]
    vocab = load_json(Path(args.vocab))
    naming = vocab["naming_conventions"]
    predicates_in_modules = sorted(
        {
            pred
            for module in modules
            for key in ("all_of", "any_of", "none_of")
            for pred in module["requires"].get(key, [])
        }
        | {
            pred
            for module in modules
            for pred in module["effects"].get("adds", []) + module["effects"].get("removes", [])
        }
    )
    predicates_in_vocab = sorted(vocab["predicates"])

    issues: list[dict[str, str]] = []
    module_only = sorted(set(predicates_in_modules) - set(predicates_in_vocab))
    vocab_only = sorted(set(predicates_in_vocab) - set(predicates_in_modules))
    for pred in module_only:
        issues.append({"predicate": pred, "issue": "missing_from_vocab"})
    for pred in vocab_only:
        issues.append({"predicate": pred, "issue": "orphaned_in_vocab"})

    allowlisted = naming.get("allowlisted_discouraged_patterns", {})
    for pred in predicates_in_modules:
        if any(pred.startswith(prefix) for prefix in naming.get("forbidden_prefixes_in_core_modules", [])):
            issues.append({"predicate": pred, "issue": "forbidden_prefix"})
        for pattern in naming.get("forbidden_local_patterns_in_core_modules", []):
            if pattern == "*_context_available" and pred.endswith("_context_available"):
                issues.append({"predicate": pred, "issue": "forbidden_local_pattern"})
            if pattern == "*_completed" and pred.endswith("_completed"):
                issues.append({"predicate": pred, "issue": "forbidden_local_pattern"})

        for suffix in naming.get("discouraged_suffixes", {}):
            if suffix_match(pred, suffix) and pred not in allowlisted.get(suffix, []):
                issues.append({"predicate": pred, "issue": f"discouraged_suffix:{suffix}"})
        for token in naming.get("discouraged_tokens", {}):
            if token_match(pred, token) and pred not in allowlisted.get(token, []):
                issues.append({"predicate": pred, "issue": f"discouraged_token:{token}"})

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    hard_fail_reasons = sorted({item["issue"] for item in issues if not item["issue"].startswith("orphaned_in_vocab")})

    report = {
        "version": 1,
        "module_library": str(Path(args.modules)),
        "vocab_path": str(Path(args.vocab)),
        "predicate_count_in_modules": len(predicates_in_modules),
        "predicate_count_in_vocab": len(predicates_in_vocab),
        "issues": issues,
        "hard_fail_reasons": hard_fail_reasons,
    }
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Workflow Predicate Audit",
        "",
        f"- module_library: `{Path(args.modules)}`",
        f"- vocab_path: `{Path(args.vocab)}`",
        f"- predicate_count_in_modules: {len(predicates_in_modules)}",
        f"- predicate_count_in_vocab: {len(predicates_in_vocab)}",
        f"- strict_status: {'pass' if not hard_fail_reasons else 'fail'}",
        "",
        "## Issues",
    ]
    if not issues:
        lines.append("- none")
    else:
        for item in issues:
            lines.append(f"- `{item['predicate']}`: {item['issue']}")
    output_md.write_text("\n".join(lines) + "\n")

    if args.strict and hard_fail_reasons:
        print("workflow predicate audit failed: " + ", ".join(hard_fail_reasons), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
