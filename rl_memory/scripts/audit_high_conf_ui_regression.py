#!/usr/bin/env python3
"""Audit targeted regressions for high-confidence UI infra failures.

The script is intentionally conservative: it only flags the deterministic
page/executor/selector symptoms that were used to build the 636-goal target
set. Generic invalid model actions/selectors are left as agent failures.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ERROR_CONTEXT_KEYS = (
    "step_error_message",
    "error",
    "exception",
    "executor_error",
    "raw_output_tail",
    "stdout_tail",
    "stderr_tail",
    "last_error",
)

HELP_ISSUE_OPTIONS = (
    "broken_seal",
    "partial_delivery",
    "quality_issue",
    "wrong_item",
)

FILE_TEXT_SELECTORS = (
    "#proof-file-name",
    "#paper-file",
    "#assignment-file-name",
    "#doc-name",
)

ERROR_WORD_RE = re.compile(
    r"timeout|error|exception|not found|waiting for locator|strict mode|"
    r"did not find|set_input_files|locator resolved",
    re.IGNORECASE,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_goal_list(path: Path | None) -> list[str]:
    if not path:
        return []
    goals: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            goals.append(value)
    return goals


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _load_expected_details(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if not path or not path.exists():
        return {}
    data = _read_json(path)
    by_goal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _iter_dicts(data):
        goal_id = item.get("goal_id") or item.get("goal")
        if isinstance(goal_id, str) and goal_id.startswith("WFG-"):
            by_goal[goal_id].append(item)
    return dict(by_goal)


def _load_summary_records(run_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    summary_paths = sorted(
        run_dir.glob("**/*summary*.json"),
        key=lambda p: (p.stat().st_mtime, str(p)),
    )
    for path in summary_paths:
        try:
            data = _read_json(path)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for record in data.get("records") or []:
            if not isinstance(record, dict):
                continue
            goal_id = record.get("goal_id")
            if isinstance(goal_id, str):
                enriched = dict(record)
                enriched["_summary_path"] = str(path)
                records[goal_id] = enriched
    return records


def _trace_goal_id(path: Path, data: dict[str, Any]) -> str:
    for key in ("goal_id", "task_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith("WFG-"):
            return value
    return path.parent.name


def _load_traces(run_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    traces: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(run_dir.glob("**/workflow_execution_trace.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        traces[_trace_goal_id(path, data)] = (path, data)
    return traces


def _stringify_error_context(module: dict[str, Any]) -> str:
    atomic = module.get("atomic_result") or {}
    values: list[str] = []
    if isinstance(atomic, dict):
        for key in ERROR_CONTEXT_KEYS:
            value = atomic.get(key)
            if value:
                values.append(str(value))
        # Some runner versions keep nested execution diagnostics.
        for key in ("result", "metadata", "diagnostics"):
            value = atomic.get(key)
            if isinstance(value, dict):
                for sub_key in ERROR_CONTEXT_KEYS:
                    sub_value = value.get(sub_key)
                    if sub_value:
                        values.append(str(sub_value))
    for key in ERROR_CONTEXT_KEYS:
        value = module.get(key)
        if value:
            values.append(str(value))
    return "\n".join(values)


def _classify_high_conf_ui_issue(text: str) -> list[str]:
    lower = text.lower()
    issues: list[str] = []

    if "page.set_input_files" in lower and (
        'type="text"' in lower
        or "placeholder=" in lower
        or any(selector in text for selector in FILE_TEXT_SELECTORS)
    ):
        issues.append("upload_text_input_executor_mismatch")

    if "strict mode violation" in lower:
        issues.append("selector_strict_mode_violation")

    if "#modal_confirm" in text and ERROR_WORD_RE.search(text):
        issues.append("modal_confirm_selector_alias")

    if "did not find some options" in lower and any(option in text for option in HELP_ISSUE_OPTIONS):
        issues.append("missing_help_issue_option")

    if (
        any(selector in text for selector in FILE_TEXT_SELECTORS)
        and "set_input_files" in lower
        and ERROR_WORD_RE.search(text)
    ):
        issues.append("file_text_selector_upload_failure")

    # Preserve order but remove duplicates when one symptom satisfies two rules.
    return list(dict.fromkeys(issues))


def _module_success(module: dict[str, Any]) -> bool:
    atomic = module.get("atomic_result") or {}
    if isinstance(atomic, dict) and atomic.get("success") is True:
        return True
    return module.get("status") == "success"


def _module_failure_category(module: dict[str, Any]) -> str:
    atomic = module.get("atomic_result") or {}
    if isinstance(atomic, dict):
        category = atomic.get("failure_category")
        if category:
            return str(category)
    return str(module.get("failure_category") or "")


def _brief_error(module: dict[str, Any], limit: int = 300) -> str:
    text = _stringify_error_context(module).replace("\n", " ").strip()
    return text[:limit]


def _expected_modules(details: list[dict[str, Any]]) -> str:
    modules: list[str] = []
    for item in details:
        for key in ("module_id", "module", "task_id"):
            value = item.get(key)
            if isinstance(value, str) and value.startswith("MODULE_"):
                modules.append(value)
    return ";".join(sorted(set(modules)))


def _expected_issue_types(details: list[dict[str, Any]]) -> str:
    issues: list[str] = []
    for item in details:
        text = json.dumps(item, ensure_ascii=False)
        issues.extend(_classify_high_conf_ui_issue(text))
        category = item.get("category") or item.get("failure_category") or item.get("issue_type")
        if category:
            issues.append(str(category))
    return ";".join(sorted(set(issues)))


def audit_run(
    run_dir: Path,
    goal_list: Path | None,
    details_path: Path | None,
    out_dir: Path,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    expected_details = _load_expected_details(details_path)
    expected_goals = _load_goal_list(goal_list)
    if not expected_goals:
        expected_goals = sorted(expected_details)

    summary_records = _load_summary_records(run_dir)
    traces = _load_traces(run_dir)

    if not expected_goals:
        expected_goals = sorted(set(summary_records) | set(traces))

    rows: list[dict[str, Any]] = []
    remaining_high_conf_attempts: list[dict[str, Any]] = []
    failure_categories = Counter()
    remaining_issue_types = Counter()
    expected_module_counts = Counter()
    observed_module_failures = Counter()

    for goal_id in expected_goals:
        details = expected_details.get(goal_id, [])
        expected_modules = _expected_modules(details)
        for module_id in expected_modules.split(";"):
            if module_id:
                expected_module_counts[module_id] += 1

        record = summary_records.get(goal_id, {})
        trace_tuple = traces.get(goal_id)
        trace_path = trace_tuple[0] if trace_tuple else None
        trace = trace_tuple[1] if trace_tuple else {}
        modules = trace.get("executed_modules") or trace.get("modules") or []
        if not isinstance(modules, list):
            modules = []

        failing_modules: list[str] = []
        goal_issue_types: list[str] = []
        goal_error_snippets: list[str] = []
        module_categories: list[str] = []
        primary_failure_module = ""
        primary_failure_category = ""
        primary_failure_error_snippet = ""

        for idx, module in enumerate(modules):
            if not isinstance(module, dict):
                continue
            module_id = str(module.get("module_id") or module.get("task_id") or f"module_{idx}")
            if _module_success(module):
                continue
            failing_modules.append(module_id)
            category = _module_failure_category(module)
            if category:
                module_categories.append(category)
                failure_categories[category] += 1
                observed_module_failures[(module_id, category)] += 1
            if not primary_failure_module:
                primary_failure_module = module_id
                primary_failure_category = category
                primary_failure_error_snippet = _brief_error(module)
            error_text = _stringify_error_context(module)
            issues = _classify_high_conf_ui_issue(error_text)
            if issues:
                snippet = _brief_error(module)
                for issue in issues:
                    remaining_issue_types[issue] += 1
                goal_issue_types.extend(issues)
                goal_error_snippets.append(snippet)
                remaining_high_conf_attempts.append(
                    {
                        "goal_id": goal_id,
                        "module_id": module_id,
                        "failure_category": category,
                        "issue_types": issues,
                        "error_snippet": snippet,
                        "trace_path": str(trace_path) if trace_path else "",
                    }
                )

        success = record.get("success")
        if success is None:
            success = trace.get("success")
        if success is None:
            success = trace.get("final_success")

        rows.append(
            {
                "goal_id": goal_id,
                "trace_found": bool(trace_tuple),
                "success": success if success is not None else "",
                "success_type": record.get("success_type", ""),
                "theme": record.get("theme") or trace.get("theme") or "",
                "blueprint_id": record.get("blueprint_id") or trace.get("blueprint_id") or "",
                "target_state_coverage": record.get("target_state_coverage", ""),
                "composite_score": record.get("composite_score", ""),
                "invalid_transition_count": record.get("invalid_transition_count", ""),
                "attempted_module_invocations": record.get("attempted_module_invocations", len(modules)),
                "actual_step_count": record.get("actual_step_count", ""),
                "expected_modules_from_old_run": expected_modules,
                "expected_issue_types_from_old_run": _expected_issue_types(details),
                "primary_failure_module": primary_failure_module,
                "primary_failure_category": primary_failure_category,
                "primary_failure_error_snippet": primary_failure_error_snippet,
                "failing_modules": ";".join(sorted(set(failing_modules))),
                "failure_categories": ";".join(sorted(set(module_categories))),
                "remaining_high_conf_ui_issue": bool(goal_issue_types),
                "remaining_high_conf_ui_issue_types": ";".join(sorted(set(goal_issue_types))),
                "remaining_high_conf_error_snippet": " | ".join(goal_error_snippets)[:500],
                "trace_path": str(trace_path) if trace_path else "",
                "summary_path": record.get("_summary_path", ""),
            }
        )

    missing_goals = [row["goal_id"] for row in rows if not row["trace_found"]]
    remaining_issue_goals = [
        row["goal_id"] for row in rows if row["remaining_high_conf_ui_issue"]
    ]
    completed_rows = [row for row in rows if row["trace_found"]]
    success_rows = [row for row in rows if row["success"] is True]

    summary = {
        "run_dir": str(run_dir),
        "goal_list": str(goal_list) if goal_list else "",
        "details_path": str(details_path) if details_path else "",
        "expected_goal_count": len(expected_goals),
        "trace_found_count": len(completed_rows),
        "missing_trace_count": len(missing_goals),
        "success_count": len(success_rows),
        "success_rate_on_expected_goals": (len(success_rows) / len(expected_goals)) if expected_goals else 0.0,
        "success_rate_on_traced_goals": (len(success_rows) / len(completed_rows)) if completed_rows else 0.0,
        "remaining_high_conf_ui_goal_count": len(set(remaining_issue_goals)),
        "remaining_high_conf_ui_attempt_count": len(remaining_high_conf_attempts),
        "remaining_high_conf_ui_issue_type_counts": dict(remaining_issue_types.most_common()),
        "failure_category_counts": dict(failure_categories.most_common()),
        "expected_module_counts": dict(expected_module_counts.most_common()),
        "observed_module_failure_counts": {
            f"{module_id}::{category}": count
            for (module_id, category), count in observed_module_failures.most_common()
        },
        "missing_goals": missing_goals,
        "remaining_high_conf_ui_attempts": remaining_high_conf_attempts,
    }

    csv_path = out_dir / "high_conf_ui_regression_goal_audit.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    _dump_json(out_dir / "high_conf_ui_regression_audit.json", {"summary": summary, "rows": rows})
    _write_markdown(out_dir / "high_conf_ui_regression_summary.md", summary)
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# High-confidence UI Infra Regression Audit",
        "",
        "## Scope",
        "",
        "- This audit covers only the deterministic high-confidence UI infra / selector / page implementation symptoms used to build the target goal set.",
        "- Generic model errors, invalid free-form selectors, repeated actions, and premature DONE are not counted as benchmark infra issues here.",
        "",
        "## Totals",
        "",
        f"- Expected goals: {summary['expected_goal_count']}",
        f"- Traces found: {summary['trace_found_count']}",
        f"- Missing traces: {summary['missing_trace_count']}",
        f"- Goal success count: {summary['success_count']}",
        f"- Success rate on expected goals: {summary['success_rate_on_expected_goals']:.4f}",
        f"- Remaining high-confidence UI issue goals: {summary['remaining_high_conf_ui_goal_count']}",
        f"- Remaining high-confidence UI issue attempts: {summary['remaining_high_conf_ui_attempt_count']}",
        "",
        "## Remaining High-confidence Issue Types",
        "",
    ]

    issue_counts = summary.get("remaining_high_conf_ui_issue_type_counts") or {}
    if issue_counts:
        for issue, count in issue_counts.items():
            lines.append(f"- `{issue}`: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Failure Categories", ""])
    failure_counts = summary.get("failure_category_counts") or {}
    if failure_counts:
        for category, count in failure_counts.items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Expected Modules From Old Run", ""])
    module_counts = summary.get("expected_module_counts") or {}
    if module_counts:
        for module, count in module_counts.items():
            lines.append(f"- `{module}`: {count}")
    else:
        lines.append("- None")

    if summary.get("missing_goals"):
        lines.extend(["", "## Missing Goals", ""])
        for goal_id in summary["missing_goals"][:100]:
            lines.append(f"- `{goal_id}`")
        if len(summary["missing_goals"]) > 100:
            lines.append(f"- ... {len(summary['missing_goals']) - 100} more")

    if summary.get("remaining_high_conf_ui_attempts"):
        lines.extend(["", "## Remaining High-confidence UI Attempts", ""])
        for item in summary["remaining_high_conf_ui_attempts"][:100]:
            issues = ";".join(item["issue_types"])
            lines.append(
                f"- `{item['goal_id']}` / `{item['module_id']}` / `{issues}`: "
                f"{item['error_snippet']}"
            )
        if len(summary["remaining_high_conf_ui_attempts"]) > 100:
            lines.append(
                f"- ... {len(summary['remaining_high_conf_ui_attempts']) - 100} more"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--goal-list", type=Path)
    parser.add_argument("--details-json", type=Path)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()

    out_dir = args.out_dir or args.run_dir / "high_conf_ui_regression_audit"
    result = audit_run(args.run_dir, args.goal_list, args.details_json, out_dir)
    summary = result["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
