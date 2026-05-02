#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
TASKS_ROOT = ROOT / "tasks"
MODULE_LIBRARY = TASKS_ROOT / "workflow_module_library.json"
BINDINGS_PATH = TASKS_ROOT / "workflow_module_bindings.json"
DEFAULT_OUTPUT_JSON = ROOT / ".task_sync_meta" / "workflow_binding_audit.json"
DEFAULT_OUTPUT_MD = ROOT / ".task_sync_meta" / "workflow_binding_audit.md"


PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit workflow module bindings against active source tasks.")
    parser.add_argument("--modules", default=str(MODULE_LIBRARY))
    parser.add_argument("--bindings", default=str(BINDINGS_PATH))
    parser.add_argument("--tasks-root", default=str(TASKS_ROOT))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def clean_goal(text: str) -> str:
    text = text.strip()
    prefixes = [
        "Your task is to ",
        "Complete the following task: ",
        "Ensure you ",
        "Complete the following task: ",
    ]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text[:1].upper() + text[1:] if text else text


def parameter_replacements(inputs: dict[str, Any]) -> list[tuple[str, str]]:
    replacements = []
    for key, value in inputs.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            raw = str(int(value)) if float(value).is_integer() else str(value)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                continue
        else:
            continue
        replacements.append((raw, f"{{{key}}}"))
    return sorted(replacements, key=lambda item: len(item[0]), reverse=True)


def parameterize_text(text: str, inputs: dict[str, Any]) -> str:
    result = text
    for raw, placeholder in parameter_replacements(inputs):
        result = re.sub(re.escape(raw), placeholder, result)
    return result


def normalize_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def infer_parameter_defaults(inputs: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    defaults = dict(inputs)
    normalized_keys = {key: normalize_identifier(key) for key in inputs}
    for step in steps:
        selector = step.get("selector", "")
        value = step.get("value")
        if not selector or value in (None, ""):
            continue
        normalized_selector = normalize_identifier(selector)
        for key, normalized_key in normalized_keys.items():
            if normalized_key and normalized_key in normalized_selector:
                defaults[key] = value
    return defaults


def extract_mem_paths(criteria: list[str]) -> list[str]:
    joined = "\n".join(criteria)
    return sorted(set(re.findall(r"mem\('([^']+)'\)", joined)))


def extract_env_paths(criteria: list[str]) -> list[str]:
    joined = "\n".join(criteria)
    return sorted(set(re.findall(r"json\('env','([^']+)'\)", joined)))


def extract_observables(criteria: list[str]) -> list[str]:
    observables = []
    for item in criteria:
        if any(token in item for token in ("exists(", "text(", "url().includes(", "json('env'")):
            observables.append(item)
    return observables


def build_binding_id(task_dir: str) -> str:
    return f"BIND_{task_dir.upper().replace('-', '_')}"


def instantiate_template(text: str, values: dict[str, Any]) -> str:
    out = text
    for key, value in values.items():
        out = out.replace(f"{{{key}}}", str(value))
    return out


def placeholders_in(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    for text in texts:
        seen.update(PLACEHOLDER_RE.findall(text))
    return sorted(seen)


def issue(binding_id: str, level: str, code: str, detail: str) -> dict[str, str]:
    return {
        "binding_id": binding_id,
        "level": level,
        "issue": code,
        "detail": detail,
    }


def main() -> None:
    args = parse_args()
    tasks_root = Path(args.tasks_root)
    modules = load_json(Path(args.modules))["modules"]
    bindings = load_json(Path(args.bindings))["bindings"]
    module_ids = {module["module_id"] for module in modules}

    issues: list[dict[str, str]] = []
    seen_binding_ids: set[str] = set()
    seen_task_dirs: set[str] = set()

    for binding in bindings:
        binding_id = binding["binding_id"]
        module_id = binding["module_id"]
        task_dir = binding["task_dir"]
        task_spec_path = tasks_root / task_dir / "task_spec.json"
        oracle_path = tasks_root / task_dir / "oracle_trace.json"

        if binding_id in seen_binding_ids:
            issues.append(issue(binding_id, "error", "duplicate_binding_id", f"Duplicate binding_id {binding_id}."))
        seen_binding_ids.add(binding_id)

        if task_dir in seen_task_dirs:
            issues.append(issue(binding_id, "error", "duplicate_task_dir_binding", f"Multiple bindings point to task_dir {task_dir}."))
        seen_task_dirs.add(task_dir)

        if module_id not in module_ids:
            issues.append(issue(binding_id, "error", "unknown_module_id", f"module_id {module_id} does not exist in module library."))

        if binding_id != build_binding_id(task_dir):
            issues.append(issue(binding_id, "error", "binding_id_mismatch", f"Expected {build_binding_id(task_dir)} from task_dir {task_dir}."))

        if not task_spec_path.exists():
            issues.append(issue(binding_id, "error", "missing_task_spec", f"Missing {task_spec_path}."))
            continue
        if not oracle_path.exists():
            issues.append(issue(binding_id, "error", "missing_oracle_trace", f"Missing {oracle_path}."))
            continue

        spec = load_json(task_spec_path)
        oracle = load_json(oracle_path)
        success_criteria = spec.get("success_criteria", [])
        steps = oracle.get("steps", [])
        inputs = spec.get("inputs", {})

        if spec.get("lifecycle_status") != "active":
            issues.append(issue(binding_id, "error", "inactive_source_task", f"Source task {task_dir} has lifecycle_status={spec.get('lifecycle_status')}."))

        if binding["backing_task_id"] != spec.get("task_id"):
            issues.append(issue(binding_id, "error", "backing_task_id_mismatch", f"Binding uses {binding['backing_task_id']} but task_spec has {spec.get('task_id')}."))

        expected_module_id = f"MODULE_{str(spec.get('module_group', '')).upper()}"
        if module_id != expected_module_id:
            issues.append(issue(binding_id, "error", "module_group_binding_mismatch", f"Binding module_id {module_id} does not match task module_group {spec.get('module_group')}."))

        expected_defaults = infer_parameter_defaults(inputs, steps)
        if binding.get("default_parameter_values", {}) != expected_defaults:
            issues.append(issue(binding_id, "error", "default_parameter_values_mismatch", "Binding default_parameter_values do not match inferred task defaults."))

        expected_desc_template = parameterize_text(clean_goal(spec.get("goal", "")), expected_defaults)
        if binding.get("description_template") != expected_desc_template:
            issues.append(issue(binding_id, "error", "description_template_mismatch", "description_template does not match parameterized task goal."))

        expected_observables = extract_observables(success_criteria)
        expected_observable_templates = [parameterize_text(item, expected_defaults) for item in expected_observables]
        if binding.get("observable_templates", []) != expected_observable_templates:
            issues.append(issue(binding_id, "error", "observable_templates_mismatch", "observable_templates do not match success_criteria-derived observables."))

        expected_seed = {
            "description": clean_goal(spec.get("goal", "")),
            "observables": expected_observables,
        }
        if binding.get("seed_example") != expected_seed:
            issues.append(issue(binding_id, "error", "seed_example_mismatch", "seed_example does not match the current task goal/observables."))

        expected_mem = extract_mem_paths(success_criteria)
        if binding.get("writes_memory", []) != expected_mem:
            issues.append(issue(binding_id, "error", "writes_memory_mismatch", "writes_memory does not match success_criteria mem(...) paths."))

        expected_env = extract_env_paths(success_criteria)
        if binding.get("writes_env", []) != expected_env:
            issues.append(issue(binding_id, "error", "writes_env_mismatch", "writes_env does not match success_criteria json('env', ...) paths."))

        declared_placeholders = placeholders_in([binding.get("description_template", "")] + binding.get("observable_templates", []))
        missing_defaults = sorted(set(declared_placeholders) - set(binding.get("default_parameter_values", {}).keys()))
        if missing_defaults:
            issues.append(issue(binding_id, "error", "template_placeholder_missing_default", f"Placeholders without defaults: {', '.join(missing_defaults)}."))

        if instantiate_template(binding.get("description_template", ""), binding.get("default_parameter_values", {})) != binding.get("seed_example", {}).get("description"):
            issues.append(issue(binding_id, "error", "description_instantiation_mismatch", "description_template does not instantiate back to seed_example.description."))

        instantiated_observables = [instantiate_template(item, binding.get("default_parameter_values", {})) for item in binding.get("observable_templates", [])]
        if instantiated_observables != binding.get("seed_example", {}).get("observables", []):
            issues.append(issue(binding_id, "error", "observable_instantiation_mismatch", "observable_templates do not instantiate back to seed_example.observables."))

        for key, value in binding.get("default_parameter_values", {}).items():
            if isinstance(value, str) and value:
                placeholder = f"{{{key}}}"
                if value in binding.get("description_template", "") and placeholder not in binding.get("description_template", ""):
                    issues.append(issue(binding_id, "warning", "unparameterized_seed_value_in_description", f"Value {value!r} still appears literally in description_template."))
                for obs in binding.get("observable_templates", []):
                    if value in obs and placeholder not in obs:
                        issues.append(issue(binding_id, "warning", "unparameterized_seed_value_in_observable", f"Value {value!r} still appears literally in an observable template."))

    hard_fail_reasons = sorted({item["issue"] for item in issues if item["level"] == "error"})
    report = {
        "version": 1,
        "module_library": str(Path(args.modules)),
        "bindings_path": str(Path(args.bindings)),
        "tasks_root": str(tasks_root),
        "binding_count": len(bindings),
        "module_count": len(modules),
        "issues": issues,
        "hard_fail_reasons": hard_fail_reasons,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Workflow Binding Audit",
        "",
        f"- module_library: `{Path(args.modules)}`",
        f"- bindings_path: `{Path(args.bindings)}`",
        f"- tasks_root: `{tasks_root}`",
        f"- binding_count: {len(bindings)}",
        f"- module_count: {len(modules)}",
        f"- strict_status: {'pass' if not hard_fail_reasons else 'fail'}",
        "",
        "## Issues",
    ]
    if not issues:
        lines.append("- none")
    else:
        for item in issues:
            lines.append(f"- `{item['binding_id']}` [{item['level']}] {item['issue']}: {item['detail']}")
    output_md.write_text("\n".join(lines) + "\n")

    if args.strict and hard_fail_reasons:
        print("workflow binding audit failed: " + ", ".join(hard_fail_reasons), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
