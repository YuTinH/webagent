#!/usr/bin/env python3
import argparse
import copy
import importlib.util
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_ROOT = ROOT / "tasks"
DEFAULT_MODULES = TASKS_ROOT / "workflow_module_library.json"
DEFAULT_BINDINGS = TASKS_ROOT / "workflow_module_bindings.json"

sys.path.insert(0, str(ROOT))

from agent.executor import TaskExecutor  # noqa: E402


def _load_local_helper(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load local helper module from {SCRIPT_DIR / filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


try:
    from rl_memory.scripts.evaluate_workflow_episode import evaluate_episode  # noqa: E402
except ModuleNotFoundError:
    evaluate_episode = _load_local_helper(
        "_workflow_eval_local",
        "evaluate_workflow_episode.py",
    ).evaluate_episode


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a workflow episode by resolving workflow modules into instantiated atomic tasks."
    )
    parser.add_argument("--goal", required=True, help="Path to workflow goal instance JSON.")
    parser.add_argument("--oracle", required=True, help="Path to workflow oracle JSON.")
    parser.add_argument("--path-id", help="Reference success path to execute. Defaults to the first path.")
    parser.add_argument(
        "--module-trace-json",
        help="Optional JSON file with executed_modules-style entries. Overrides --path-id when provided.",
    )
    parser.add_argument("--modules", default=str(DEFAULT_MODULES), help="Path to workflow module library JSON.")
    parser.add_argument("--bindings", default=str(DEFAULT_BINDINGS), help="Path to workflow module binding JSON.")
    parser.add_argument(
        "--output-root",
        help="Directory for instantiated task files, execution trace, and evaluation outputs. Defaults to .task_sync_meta/workflow_runs/<goal_id>.",
    )
    parser.add_argument("--db-path", default=str(ROOT / "data.db"), help="SQLite database path for atomic task execution.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode when --execute is set.")
    parser.add_argument("--slow", type=int, default=0, metavar="MS", help="Slow down atomic execution by N milliseconds.")
    parser.add_argument("--execute", action="store_true", help="Actually execute the instantiated atomic tasks.")
    return parser.parse_args()


def choose_reference_path(oracle: dict[str, Any], path_id: str | None) -> dict[str, Any]:
    paths = oracle.get("success_paths", [])
    if not paths:
        raise ValueError("oracle has no success_paths")
    if path_id is None:
        return paths[0]
    for path in paths:
        if path.get("path_id") == path_id:
            return path
    raise ValueError(f"unknown path_id: {path_id}")


def build_execution_plan(
    goal: dict[str, Any],
    oracle: dict[str, Any],
    bindings_doc: dict[str, Any],
    path_id: str | None,
    module_trace_json: Path | None,
) -> tuple[list[dict[str, Any]], str]:
    bindings_by_id = {binding["binding_id"]: binding for binding in bindings_doc["bindings"]}
    bindings_by_module: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings_doc["bindings"]:
        bindings_by_module.setdefault(binding["module_id"], []).append(binding)

    if module_trace_json is not None:
        entries = load_json(module_trace_json)
        if not isinstance(entries, list):
            raise ValueError("--module-trace-json must point to a JSON array")
        plan = []
        for index, entry in enumerate(entries, start=1):
            module_id = entry["module_id"]
            binding = None
            if entry.get("binding_id"):
                binding = bindings_by_id[entry["binding_id"]]
            else:
                candidates = bindings_by_module.get(module_id, [])
                if not candidates:
                    raise ValueError(f"no binding found for module {module_id}")
                binding = candidates[0]
            entry_matches_binding = (
                (not entry.get("binding_id") or entry.get("binding_id") == binding["binding_id"])
                and (
                    not entry.get("binding_task_id")
                    or entry.get("binding_task_id") == binding["backing_task_id"]
                )
            )
            parameter_values = dict(binding.get("default_parameter_values", {}))
            if entry_matches_binding and binding.get("allow_parameter_overrides", True):
                parameter_values.update(entry.get("parameter_values", {}))
            plan.append(
                {
                    "index": index,
                    "module_id": module_id,
                    "binding_id": binding["binding_id"],
                    "binding_task_id": binding["backing_task_id"],
                    "task_dir": binding["task_dir"],
                    "invocation_id": entry.get("invocation_id", f"{goal['goal_id']}-C{index}"),
                    "parameter_values": parameter_values,
                    "description": _canonicalize_plan_description(
                        module_id,
                        (
                            entry.get("description")
                            if entry_matches_binding and entry.get("description")
                            else binding.get("seed_example", {}).get("description") or module_id
                        ),
                        parameter_values,
                    ),
                    "expected_observables": (
                        entry.get("expected_observables")
                        if entry_matches_binding and entry.get("expected_observables")
                        else binding.get("seed_example", {}).get("observables", [])
                    ),
                }
            )
        return plan, "custom_trace"

    path = choose_reference_path(oracle, path_id)
    invocations = {item["invocation_id"]: item for item in oracle.get("reference_invocations", [])}
    required_modules = path.get("required_modules", [])
    invocation_ids = path.get("reference_invocation_ids", [])
    if len(required_modules) != len(invocation_ids):
        raise ValueError(f"path {path['path_id']} has mismatched module/invocation counts")

    plan = []
    for index, (module_id, invocation_id) in enumerate(zip(required_modules, invocation_ids), start=1):
        invocation = invocations[invocation_id]
        binding = bindings_by_id.get(invocation.get("binding_id"))
        if binding is None:
            candidates = bindings_by_module.get(module_id, [])
            if not candidates:
                raise ValueError(f"no binding found for module {module_id}")
            binding = candidates[0]
        invocation_matches_binding = (
            (not invocation.get("binding_id") or invocation.get("binding_id") == binding["binding_id"])
            and (
                not invocation.get("binding_task_id")
                or invocation.get("binding_task_id") == binding["backing_task_id"]
            )
        )
        parameter_values = dict(binding.get("default_parameter_values", {}))
        if invocation_matches_binding and binding.get("allow_parameter_overrides", True):
            parameter_values.update(invocation.get("parameter_values", {}))
        plan.append(
            {
                "index": index,
                "module_id": module_id,
                "binding_id": binding["binding_id"],
                "binding_task_id": binding["backing_task_id"],
                "task_dir": binding["task_dir"],
                "invocation_id": invocation_id,
                "parameter_values": parameter_values,
                "description": _canonicalize_plan_description(
                    module_id,
                    (
                        invocation.get("description")
                        if invocation_matches_binding and invocation.get("description")
                        else binding.get("seed_example", {}).get("description") or module_id
                    ),
                    parameter_values,
                ),
                "expected_observables": (
                    invocation.get("expected_observables")
                    if invocation_matches_binding and invocation.get("expected_observables")
                    else binding.get("seed_example", {}).get("observables", [])
                ),
            }
        )
    return plan, path["path_id"]


def stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _format_scalar_for_description(value: Any) -> str:
    if isinstance(value, (int, float)):
        value_f = float(value)
        if value_f.is_integer():
            return str(int(value_f))
        return str(value)
    raw = str(value or "").strip()
    try:
        value_f = float(raw)
        if value_f.is_integer():
            return str(int(value_f))
    except Exception:
        pass
    return raw


def _format_decimal(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except Exception:
        return str(value)


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_housekeeping_service_type(value: Any) -> str:
    raw = str(value or "").strip()
    aliases = {
        "standard_cleaning": "regular_cleaning",
        "standard cleaning": "regular_cleaning",
        "regular cleaning": "regular_cleaning",
    }
    return aliases.get(raw.lower(), raw)


_VISA_REQUIREMENT_PRESETS: dict[str, dict[str, str]] = {
    "France": {
        "visa_type": "申根签证 (Type C)",
        "stay_duration": "最长90天 (180天内)",
    },
    "Japan": {
        "visa_type": "短期滞在 (旅游)",
        "stay_duration": "15天 / 30天 / 90天",
    },
    "Singapore": {
        "visa_type": "电子入境许可 / 以使馆要求为准",
        "stay_duration": "通常可停留30天",
    },
    "Thailand": {
        "visa_type": "旅游签证 / 免签政策以当期要求为准",
        "stay_duration": "通常可停留30天 / 60天",
    },
    "Vietnam": {
        "visa_type": "电子签证 (eVisa)",
        "stay_duration": "通常可停留90天",
    },
    "UAE": {
        "visa_type": "电子签或落地签（视护照而定）",
        "stay_duration": "通常可停留30天",
    },
    "United Arab Emirates": {
        "visa_type": "电子签或落地签（视护照而定）",
        "stay_duration": "通常可停留30天",
    },
}

_EVENT_TICKET_PRESETS: dict[str, dict[str, Any]] = {
    "EVT-101": {
        "event_id": "EVT-101",
        "event_name": "Campus Music Fest",
        "price": 50,
    },
    "EVT-102": {
        "event_id": "EVT-102",
        "event_name": "Open Lecture Night",
        "price": 0,
    },
    "EVT-103": {
        "event_id": "EVT-103",
        "event_name": "Outdoor Film Meetup",
        "price": 30,
    },
}

_EVENT_TICKET_NAME_ALIASES: dict[str, str] = {
    "campus music fest": "EVT-101",
    "校园音乐节": "EVT-101",
    "open lecture night": "EVT-102",
    "公开讲座之夜": "EVT-102",
    "outdoor film meetup": "EVT-103",
    "户外放映会": "EVT-103",
}


def _normalize_event_ticket_target(
    effective_parameter_values: dict[str, Any],
    spec_inst: dict[str, Any],
) -> dict[str, Any]:
    inputs = spec_inst.get("inputs", {})
    raw_event_id = str(effective_parameter_values.get("event_id", inputs.get("event_id", "")) or "").strip()
    raw_event_name = str(
        effective_parameter_values.get("event_name", effective_parameter_values.get("eventName", inputs.get("event_name", "")))
        or ""
    ).strip()
    raw_price = effective_parameter_values.get("price", inputs.get("price", ""))
    recipient_id = str(
        effective_parameter_values.get(
            "recipient_id",
            effective_parameter_values.get("recipientId", inputs.get("recipient_id", "")),
        )
        or ""
    ).strip()

    if raw_event_id in _EVENT_TICKET_PRESETS:
        target = dict(_EVENT_TICKET_PRESETS[raw_event_id])
    else:
        alias_key = raw_event_name.strip().lower()
        if alias_key in _EVENT_TICKET_NAME_ALIASES:
            target = dict(_EVENT_TICKET_PRESETS[_EVENT_TICKET_NAME_ALIASES[alias_key]])
        else:
            target = {}
            try:
                numeric_price = float(raw_price)
            except Exception:
                numeric_price = None
            if numeric_price is not None:
                matches = [item for item in _EVENT_TICKET_PRESETS.values() if float(item["price"]) == numeric_price]
                if len(matches) == 1:
                    target = dict(matches[0])
    if not target:
        target = {
            "event_id": raw_event_id,
            "event_name": raw_event_name,
            "price": raw_price,
        }
    target["recipient_id"] = recipient_id
    return target


def _rewrite_scoring_checkpoints(spec_inst: dict[str, Any], assertions: list[str]) -> None:
    original = list(spec_inst.get("scoring_checkpoints", []) or [])
    rewritten = []
    for idx, assertion in enumerate(assertions):
        if idx < len(original):
            checkpoint = copy.deepcopy(original[idx])
        else:
            checkpoint = {
                "id": f"crit_{idx + 1}_final",
                "name": f"Criterion {idx + 1} final",
                "weight": 1.0,
                "required": True,
                "depends_on": [],
            }
        checkpoint["assertion"] = assertion
        checkpoint.setdefault("id", f"crit_{idx + 1}_final")
        checkpoint.setdefault("name", f"Criterion {idx + 1} final")
        checkpoint.setdefault("weight", 1.0)
        checkpoint.setdefault("required", True)
        checkpoint.setdefault("depends_on", [])
        rewritten.append(checkpoint)
    spec_inst["scoring_checkpoints"] = rewritten


def _apply_module_specific_instantiation(
    spec_inst: dict[str, Any],
    binding: dict[str, Any],
    effective_parameter_values: dict[str, Any],
) -> bool:
    module_id = str(binding.get("module_id") or "")

    if module_id == "MODULE_VISA_REQUIREMENTS":
        destination = str(effective_parameter_values.get("destination_country") or spec_inst["inputs"].get("destination_country") or "").strip()
        passport = str(effective_parameter_values.get("passport_country") or spec_inst["inputs"].get("passport_country") or "").strip()
        preset = _VISA_REQUIREMENT_PRESETS.get(
            destination,
            {
                "visa_type": "需要查询使馆官网",
                "stay_duration": "未知",
            },
        )
        spec_inst["goal"] = f"Check the visa requirements for {destination} with a {passport} passport."
        assertions = [
            f"mem('visa.search.last.destination') == '{destination}'",
            f"mem('visa.search.last.visa_type') == '{preset['visa_type']}'",
            f"mem('visa.search.last.stay_duration') == '{preset['stay_duration']}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_TRANSPORT_TOPUP":
        amount = float(effective_parameter_values.get("topup_amount", spec_inst["inputs"].get("topup_amount", 0)) or 0)
        threshold = _format_scalar_for_description(
            effective_parameter_values.get("auto_recharge_threshold", spec_inst["inputs"].get("auto_recharge_threshold", ""))
        )
        auto_amount = _format_scalar_for_description(
            effective_parameter_values.get("auto_recharge_amount", spec_inst["inputs"].get("auto_recharge_amount", ""))
        )
        balance = 25.5 + amount
        spec_inst["goal"] = (
            f"Top up the transport card by {_format_scalar_for_description(amount)}, "
            f"with auto-recharge threshold {threshold} and recharge amount {auto_amount}."
        )
        assertions = [
            f"mem('transport.card.balance') == '{_format_decimal(balance)}'",
            f"mem('transport.card.last_topup_amount') == '{_format_decimal(amount)}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_HOUSEKEEPING_BOOKING":
        service_type = _normalize_housekeeping_service_type(
            effective_parameter_values.get("service_type", spec_inst["inputs"].get("service_type", ""))
        )
        service_date = str(effective_parameter_values.get("service_date", spec_inst["inputs"].get("service_date", "")) or "").strip()
        service_time = str(effective_parameter_values.get("service_time", spec_inst["inputs"].get("service_time", "")) or "").strip()
        spec_inst.setdefault("inputs", {})["service_type"] = service_type
        spec_inst["goal"] = f"Book a {service_type.replace('_', ' ')} housekeeping session for {service_date} at {service_time}."
        assertions = [
            "mem('local_services.housekeeping_bookings.last.status') == 'confirmed'",
            f"mem('local_services.housekeeping_bookings.last.type') == '{service_type}'",
            f"mem('local_services.housekeeping_bookings.last.date') == '{service_date}'",
            f"mem('local_services.housekeeping_bookings.last.time') == '{service_time}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_LOGISTICS_FIX":
        order_id = str(
            effective_parameter_values.get("order_id", effective_parameter_values.get("orderId", spec_inst["inputs"].get("order_id", "")))
            or ""
        ).strip()
        issue_type = str(
            effective_parameter_values.get("issue_type", effective_parameter_values.get("type", spec_inst["inputs"].get("issue_type", "")))
            or ""
        ).strip()
        description = str(
            effective_parameter_values.get("description", spec_inst["inputs"].get("description", ""))
            or ""
        ).strip()
        spec_inst["goal"] = f"Open a logistics ticket for order {order_id} with issue type {issue_type}."
        assertions = [
            "mem('support.ticket.last.status') == 'open'",
            f"mem('support.ticket.last.order_id') == '{order_id}'",
            f"mem('support.ticket.last.type') == '{issue_type}'",
            f"mem('support.ticket.last.description') == '{description}'",
            "url().includes('/shop.local/help.html?status=ticket_created')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_SUBSCRIPTION_REFUND":
        subscription_id = str(
            effective_parameter_values.get("subscription_id", spec_inst["inputs"].get("subscription_id", ""))
            or ""
        ).strip()
        reason = str(effective_parameter_values.get("reason", spec_inst["inputs"].get("reason", "")) or "").strip()
        estimated_refund = 0.0
        if subscription_id == "SUB-8821":
            estimated_refund = round(200 * (8 / 12), 2)
        elif subscription_id == "SUB-9932":
            estimated_refund = round(30 * (10 / 30), 2)
        spec_inst["goal"] = f"Request a prorated refund for subscription {subscription_id} because {reason}"
        assertions = [
            f"mem('support.refund_requests.last.subscription_id') == '{subscription_id}'",
            "mem('support.refund_requests.last.status') == 'processing'",
            f"mem('support.refund_requests.last.estimated_refund') == '{estimated_refund}'",
            f"mem('support.refund_requests.last.reason') == '{reason}'",
            "exists(\"#refund-requests-list .card\")",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_EVENT_TICKETS":
        target = _normalize_event_ticket_target(effective_parameter_values, spec_inst)
        event_name = str(target.get("event_name", "") or "").strip()
        recipient_id = str(target.get("recipient_id", "") or "").strip()
        expected_status = "transferred" if recipient_id else "active"
        if recipient_id:
            spec_inst["goal"] = f"Buy a ticket for {event_name} and transfer it to {recipient_id}."
        else:
            spec_inst["goal"] = f"Buy a ticket for {event_name}."
        assertions = [
            f"mem('tickets.user_tickets.last.status') == '{expected_status}'",
            f"mem('tickets.user_tickets.last.event_name') == '{event_name}'",
            "exists(\"#tickets-list .card .badge.pri\")" if expected_status == "transferred" else "exists(\"#tickets-list .card\")",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_ROOMMATE_EXPENSE_SPLIT":
        month = str(effective_parameter_values.get("month", spec_inst["inputs"].get("month", "")) or "").strip()
        rules = str(effective_parameter_values.get("rules", spec_inst["inputs"].get("rules", "")) or "").strip()
        spec_inst["goal"] = f"Settle the shared expenses for {month} using the {rules} split rule."
        assertions = [
            f"mem('settlements.{month}.state') == 'settled'",
            f"json('env','settlements.{month}.rules') == '{rules}'",
            "url().includes('/social.local/split.html')",
            f"url().includes('month={month}')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_CHARITY_DONATION":
        charity_name = str(
            effective_parameter_values.get("charity_name", spec_inst["inputs"].get("charity_name", "")) or ""
        ).strip()
        amount = _format_decimal(effective_parameter_values.get("amount", spec_inst["inputs"].get("amount", "0")) or 0)
        tax_deductible = _is_truthy(
            effective_parameter_values.get("tax_deductible", spec_inst["inputs"].get("tax_deductible", False))
        )
        receipt_label = "request a tax-deductible receipt" if tax_deductible else "do not request a tax-deductible receipt"
        spec_inst["goal"] = f"Record a donation of {amount} to {charity_name} and {receipt_label}."
        assertions = [
            f"mem('charity.donations.last.charity_name') == '{charity_name}'",
            f"mem('charity.donations.last.amount') == '{amount}'",
            f"mem('charity.donations.last.tax_deductible') == '{'1' if tax_deductible else '0'}'",
            "url().includes('/social.local/charity.html')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_BILLING_REVIEW":
        utility_types = effective_parameter_values.get("utility_types", spec_inst["inputs"].get("utility_types", [])) or []
        if isinstance(utility_types, str):
            utility_types = [utility_types]
        utilities = [str(item).strip() for item in utility_types if str(item).strip()]
        utility_label = ", ".join(utilities) if utilities else "current utility"
        spec_inst["goal"] = f"Open the gov.local Bills page and review the current {utility_label} bills."
        assertions = [
            "url().includes('/gov.local/billing/index.html')",
            "exists('.bill-item')",
            "exists('.bills-summary')",
            "mem('bills.pending_count') >= 1",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_COURSE_ENROLLMENT":
        course_id = str(effective_parameter_values.get("courseId", spec_inst["inputs"].get("courseId", "")) or "").strip()
        spec_inst["goal"] = f"Enroll in the course {course_id} from the Nebula catalog."
        assertions = [
            f"mem('courses.{course_id}.state') == 'enrolled'",
            "url().includes('/school.local/my-learning.html')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_BUY_EBOOK":
        book_id = str(effective_parameter_values.get("bookId", spec_inst["inputs"].get("bookId", "")) or "").strip()
        spec_inst["goal"] = f"Buy the ebook {book_id} and add it to My Learning."
        assertions = [
            f"mem('library.books.{book_id}.owned') == 'true'",
            f"mem('library.books.last.id') == '{book_id}'",
            "url().includes('/school.local/my-learning.html')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_INVESTMENT_ACCOUNT":
        name = str(effective_parameter_values.get("name", spec_inst["inputs"].get("name", "")) or "").strip()
        acc_type = str(effective_parameter_values.get("type", spec_inst["inputs"].get("type", "")) or "").strip()
        initial_deposit = _format_decimal(
            effective_parameter_values.get("initial_deposit", spec_inst["inputs"].get("initial_deposit", "0")) or 0
        )
        spec_inst["goal"] = f"Open the {name} investment account with type {acc_type} and an initial deposit of {initial_deposit}."
        assertions = [
            "mem('finance.investment_accounts.last.status') == 'active'",
            f"mem('finance.investment_accounts.last.name') == '{name}'",
            f"mem('finance.investment_accounts.last.type') == '{acc_type}'",
            f"mem('finance.investment_accounts.last.balance') == '{initial_deposit}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_TRANSFER_FUNDS":
        category = str(effective_parameter_values.get("category", spec_inst["inputs"].get("category", "")) or "").strip()
        limit = _format_scalar_for_description(effective_parameter_values.get("limit", spec_inst["inputs"].get("limit", "")))
        spec_inst["goal"] = f"Update the {category} budget limit to {limit}."
        assertions = [
            "url().includes('/bank.local/budget.html?updated=true')",
            f"mem('finance.budgets.{category}.limit') == {limit}",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_VACCINE_MGMT":
        vaccine_type = str(
            effective_parameter_values.get("vaccine_type", effective_parameter_values.get("type", spec_inst["inputs"].get("vaccine_type", "")))
            or ""
        ).strip()
        appointment_date = str(
            effective_parameter_values.get("appointment_date", effective_parameter_values.get("date", spec_inst["inputs"].get("appointment_date", "")))
            or ""
        ).strip()
        appointment_time = str(
            effective_parameter_values.get("appointment_time", effective_parameter_values.get("time", spec_inst["inputs"].get("appointment_time", "")))
            or ""
        ).strip()
        spec_inst["goal"] = f"Book a {vaccine_type} vaccine appointment for {appointment_date} at {appointment_time}."
        assertions = [
            "mem('health.vaccines.last.status') == 'booked'",
            f"mem('health.vaccines.last.type') == '{vaccine_type}'",
            f"mem('health.vaccines.last.date') == '{appointment_date}'",
            f"mem('health.vaccines.last.time') == '{appointment_time}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_PARKING_PERMIT_APPLICATION":
        plate_number = str(
            effective_parameter_values.get("plate_number", effective_parameter_values.get("plateNumber", spec_inst["inputs"].get("plate_number", "")))
            or ""
        ).strip()
        permit_type = str(
            effective_parameter_values.get("permit_type", effective_parameter_values.get("permitType", spec_inst["inputs"].get("permit_type", "")))
            or ""
        ).strip()
        duration_months = _format_scalar_for_description(
            effective_parameter_values.get("duration_months", effective_parameter_values.get("durationMonths", spec_inst["inputs"].get("duration_months", "")))
        )
        spec_inst["goal"] = f"Apply for a {permit_type} parking permit for plate {plate_number} for {duration_months} months."
        assertions = [
            "mem('permits.parking.state') == 'submitted'",
            f"mem('gov.parking_permits.last.plate_number') == '{plate_number}'",
            f"mem('gov.parking_permits.last.permit_type') == '{permit_type}'",
            f"mem('gov.parking_permits.last.duration_months') == '{duration_months}'",
            "url().includes('/gov.local/parking-permits.html')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_FIND_HOME":
        property_id = str(
            effective_parameter_values.get("propertyId", spec_inst["inputs"].get("propertyId", "")) or ""
        ).strip()
        lease_term = str(
            effective_parameter_values.get("leaseTerm", spec_inst["inputs"].get("leaseTerm", "")) or ""
        ).strip()
        assertions = [
            f"mem('housing.lease.last.id') == '{property_id}'",
            f"mem('housing.lease.last.term') == '{lease_term}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_BUDGET_LIMIT_UPDATE":
        category = str(effective_parameter_values.get("category", spec_inst["inputs"].get("category", "")) or "").strip()
        limit = _format_scalar_for_description(effective_parameter_values.get("limit", spec_inst["inputs"].get("limit", "")))
        spec_inst["goal"] = f"Set a tight budget for {category}."
        assertions = [f"mem('finance.budgets.{category}.limit') == {limit}"]
        spec_inst["success_criteria"] = assertions
        checkpoints = list(spec_inst.get("scoring_checkpoints", []) or [])
        for checkpoint in checkpoints:
            if checkpoint.get("id") == "cp_budget_limit_set":
                checkpoint["assertion"] = assertions[0]
        spec_inst["scoring_checkpoints"] = checkpoints
        return True

    if module_id == "MODULE_BOOK_FLIGHT":
        departure = str(effective_parameter_values.get("departure", spec_inst["inputs"].get("departure", "")) or "").strip()
        destination = str(effective_parameter_values.get("destination", spec_inst["inputs"].get("destination", "")) or "").strip()
        depart_date = str(effective_parameter_values.get("depart_date", spec_inst["inputs"].get("depart_date", "")) or "").strip()
        passengers = _format_scalar_for_description(
            effective_parameter_values.get("passengers", spec_inst["inputs"].get("passengers", "1"))
        )
        passenger_label = "passenger" if passengers == "1" else "passengers"
        spec_inst["goal"] = f"Book a flight from {departure} to {destination} on {depart_date} for {passengers} {passenger_label}."
        assertions = [
            "url().includes('/trip.local/manage.html')",
            f"mem('travel.flight.last.destination') == '{destination}'",
            "mem('travel.flight.last.pnr') includes 'PNR-'",
            "NOT[url().includes('about:blank')]",
            "NOT[url().includes('chrome-error://')]",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_BOOK_HOTEL":
        city = str(effective_parameter_values.get("city", spec_inst["inputs"].get("city", "")) or "").strip()
        check_in_date = str(
            effective_parameter_values.get("check_in_date", spec_inst["inputs"].get("check_in_date", "")) or ""
        ).strip()
        check_out_date = str(
            effective_parameter_values.get("check_out_date", spec_inst["inputs"].get("check_out_date", "")) or ""
        ).strip()
        guests = _format_scalar_for_description(
            effective_parameter_values.get("guests", spec_inst["inputs"].get("guests", "1"))
        )
        guest_label = "guest" if guests == "1" else "guests"
        nights = 1
        try:
            nights = max(
                1,
                (
                    datetime.fromisoformat(check_out_date).date()
                    - datetime.fromisoformat(check_in_date).date()
                ).days,
            )
        except Exception:
            pass
        spec_inst["goal"] = f"Book a hotel in {city} from {check_in_date} to {check_out_date} for {guests} {guest_label}."
        assertions = [
            "url().includes('/trip.local/manage.html')",
            "json('env','trips.hotel.id') != ''",
            f"json('env','trips.hotel.city') == '{city}'",
            f"json('env','trips.hotel.checkin') == '{check_in_date}'",
            f"json('env','trips.hotel.nights') == {nights}",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_EXPENSE_REPORT":
        report_id = str(effective_parameter_values.get("reportId", spec_inst["inputs"].get("reportId", "")) or "").strip()
        total = _format_decimal(effective_parameter_values.get("total", spec_inst["inputs"].get("total", "0")) or 0)
        description = str(
            effective_parameter_values.get("description", spec_inst["inputs"].get("description", "")) or ""
        ).strip()
        pnr = str(effective_parameter_values.get("pnr", spec_inst["inputs"].get("pnr", "")) or "").strip()
        spec_inst["goal"] = f"Submit travel expense report {report_id} for {total} linked to {pnr}."
        assertions = [
            f"mem('expenses.last.id') == '{report_id}'",
            f"mem('expenses.last.total') == '{total}'",
            f"mem('expenses.last.pnr') == '{pnr}'",
            f"mem('expenses.last.description') == '{description}'",
            "url().includes('/bank.local/expense-report.html')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_PAPER_SUBMISSION":
        title = str(effective_parameter_values.get("title", spec_inst["inputs"].get("title", "")) or "").strip()
        journal = str(effective_parameter_values.get("journal", spec_inst["inputs"].get("journal", "")) or "").strip()
        file_name = str(effective_parameter_values.get("file", spec_inst["inputs"].get("file", "")) or "").strip()
        spec_inst["goal"] = f"Submit the paper {title} to {journal} using file {file_name}."
        assertions = [
            "mem('work.paper_submissions.last.id') includes 'SUB-'",
            f"mem('work.paper_submissions.last.title') == '{title}'",
            f"mem('work.paper_submissions.last.journal') == '{journal}'",
            f"mem('work.paper_submissions.last.file') == '{file_name}'",
            "mem('work.paper_submissions.last.status') == 'submitted'",
            f"exists(\"#submissions-list .card:has-text('{title}')\")",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_FOOD_DELIVERY":
        restaurant = str(
            effective_parameter_values.get("restaurant", spec_inst["inputs"].get("restaurant", "")) or ""
        ).strip()
        item = str(effective_parameter_values.get("item", spec_inst["inputs"].get("item", "")) or "").strip()
        promo_code = str(
            effective_parameter_values.get("promo_code", spec_inst["inputs"].get("promo_code", "")) or ""
        ).strip()
        total = float(effective_parameter_values.get("total", spec_inst["inputs"].get("total", 0)) or 0)
        spec_inst["goal"] = (
            f"Order {item} from {restaurant} with promo code {promo_code} for a total of {_format_scalar_for_description(total)}."
        )
        assertions = [
            "url().includes('/food.local/orders.html')",
            f"json('env','food.orders.last.restaurant') == '{restaurant}'",
            f"json('env','food.orders.last.items') includes '{item}'",
            f"json('env','food.orders.last.total') == {total}",
            f"json('env','food.orders.last.promo_code') == '{promo_code}'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_MEDICAL_CLAIM":
        claim_id = str(effective_parameter_values.get("claim_id", spec_inst["inputs"].get("claim_id", "")) or "").strip()
        appointment_id = str(
            effective_parameter_values.get("appointment_id", spec_inst["inputs"].get("appointment_id", "")) or ""
        ).strip()
        policy_id = str(effective_parameter_values.get("policy_id", spec_inst["inputs"].get("policy_id", "")) or "").strip()
        amount = _format_decimal(
            effective_parameter_values.get("amount", spec_inst["inputs"].get("amount", "0")) or 0
        )
        spec_inst["goal"] = (
            f"Complete the following task: submit insurance claim {claim_id} for appointment "
            f"{appointment_id} under policy {policy_id} for {amount}."
        )
        assertions = [
            f"mem('insurance.claim.last.id') == '{claim_id}'",
            "mem('insurance.claim.last.status') == 'processing'",
            f"mem('insurance.claim.last.appointment_id') == '{appointment_id}'",
            f"mem('insurance.claim.last.amount') == '{amount}'",
            f"mem('insurance.claim.last.policy_id') == '{policy_id}'",
            "exists('#claim-state')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_INSURANCE_POLICY":
        plan_name = str(effective_parameter_values.get("plan_name", spec_inst["inputs"].get("plan_name", "")) or "").strip()
        provider = str(effective_parameter_values.get("provider", spec_inst["inputs"].get("provider", "")) or "").strip()
        spec_inst.setdefault("inputs", {})["plan_name"] = plan_name
        spec_inst.setdefault("inputs", {})["provider"] = provider
        spec_inst["goal"] = f"Your task is to purchase the {plan_name} from {provider}."
        assertions = [
            "mem('health.insurance.active') == 1",
            f"mem('health.insurance.plan_name') == '{plan_name}'",
            f"mem('health.insurance.provider') == '{provider}'",
            "mem('health.insurance.policy_number') includes 'POL-'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_ORDER_ARRIVAL":
        product_name = str(effective_parameter_values.get("product_name", spec_inst["inputs"].get("product_name", "")) or "").strip()
        spec_inst["goal"] = f"Open My Orders and advance delivery until the order containing {product_name} is delivered."
        assertions = [
            "mem('shop.orders.last.state') == 'delivered'",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_SECOND_HAND_SALE":
        item_name = str(
            effective_parameter_values.get("item_name", effective_parameter_values.get("name", spec_inst["inputs"].get("item_name", "")))
            or ""
        ).strip()
        category = str(effective_parameter_values.get("category", spec_inst["inputs"].get("category", "")) or "").strip()
        price = float(effective_parameter_values.get("price", spec_inst["inputs"].get("price", 0)) or 0)
        spec_inst["goal"] = f"Post a marketplace listing for {item_name} in the {category} category at {_format_scalar_for_description(price)}."
        if category == "service":
            assertions = [
                f"mem('market.listed_items.last.name') == '{item_name}'",
                f"mem('market.listed_items.last.category') == '{category}'",
                (
                    "ANY[ALL[json('env','world_state.skills.certified') == true, "
                    f"mem('market.listed_items.last.price') == {_format_decimal(price * 2)}], "
                    "ALL[NOT[json('env','world_state.skills.certified') == true], "
                    f"mem('market.listed_items.last.price') == {_format_decimal(price)}]]"
                ),
                "url().includes('/market.local/index.html?listed=true')",
            ]
        else:
            assertions = [
                f"mem('market.listed_items.last.name') == '{item_name}'",
                f"mem('market.listed_items.last.category') == '{category}'",
                f"mem('market.listed_items.last.price') == '{_format_decimal(price)}'",
                "url().includes('/market.local/index.html?listed=true')",
            ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_THERMOSTAT_SCHEDULE":
        device_id = str(effective_parameter_values.get("deviceId", spec_inst["inputs"].get("deviceId", "")) or "").strip()
        location = str(effective_parameter_values.get("location", spec_inst["inputs"].get("location", "")) or "").strip()
        color = str(effective_parameter_values.get("color", spec_inst["inputs"].get("color", "")) or "").strip()
        spec_inst["goal"] = f"Configure thermostat device {device_id} in {location} with the {color} profile."
        assertions = [
            f"mem('devices.{device_id}.status') == 'active'",
            f"mem('devices.{device_id}.location') == '{location}'",
            f"exists(\"div:has-text('{location}')\")",
            "url().includes('/energy.local/index.html')",
            "NOT[url().includes('about:blank')]",
            "NOT[url().includes('chrome-error://')]",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    if module_id == "MODULE_LONG_HAUL_TRIP":
        destination = str(effective_parameter_values.get("destination", spec_inst["inputs"].get("destination", "")) or "").strip()
        passport_number = str(
            effective_parameter_values.get("passport_number", spec_inst["inputs"].get("passport_number", "")) or ""
        ).strip()
        spec_inst["goal"] = (
            f"Apply for a {destination} visa with passport {passport_number}, wait for approval, "
            f"then book the outbound {destination} flight."
        )
        assertions = [
            "mem('gov.visa_applications.last.status') == 'approved'",
            f"mem('gov.visa_applications.last.destination') == '{destination}'",
            "mem('travel.flight.last.pnr') includes 'PNR-'",
            f"mem('travel.flight.last.destination') == '{destination}'",
            "url().includes('/trip.local/manage.html')",
        ]
        spec_inst["success_criteria"] = assertions
        _rewrite_scoring_checkpoints(spec_inst, assertions)
        return True

    return False


def _canonicalize_plan_description(module_id: str, description: str, parameter_values: dict[str, Any]) -> str:
    description = str(description or "").strip()
    params = dict(parameter_values or {})
    if not params:
        return description

    if module_id == "MODULE_PRICE_PROTECTION" and params.get("order_id"):
        return f"Submit a price protection claim for order {params['order_id']}."

    if module_id == "MODULE_BOOK_FLIGHT":
        departure = _format_scalar_for_description(params.get("departure", ""))
        destination = _format_scalar_for_description(params.get("destination", ""))
        depart_date = _format_scalar_for_description(params.get("depart_date", ""))
        passengers = _format_scalar_for_description(params.get("passengers", "1"))
        passenger_label = "passenger" if passengers == "1" else "passengers"
        return f"Book a flight from {departure} to {destination} on {depart_date} for {passengers} {passenger_label}."

    if module_id == "MODULE_COUPON_MANAGEMENT" and params.get("code"):
        coupon_type = str(params.get("type", "discount") or "discount").strip().lower()
        if coupon_type == "discount":
            coupon_label = "fixed discount"
        elif coupon_type == "percentage":
            coupon_label = "percentage"
        else:
            coupon_label = coupon_type
        value = _format_scalar_for_description(params.get("value", ""))
        min_spend = _format_scalar_for_description(params.get("min_spend", ""))
        return (
            f"Add a {coupon_label} coupon {params['code']} worth {value} off "
            f"with a minimum spend of {min_spend}."
        )

    if module_id == "MODULE_HOUSEKEEPING_BOOKING":
        service_type = _normalize_housekeeping_service_type(
            params.get("service_type", "housekeeping") or "housekeeping"
        ).replace("_", " ")
        return (
            f"Book a {service_type} session for "
            f"{_format_scalar_for_description(params.get('service_date', ''))} at "
            f"{_format_scalar_for_description(params.get('service_time', ''))}."
        )

    if module_id == "MODULE_DOCTOR_APPT":
        appointment_id = _format_scalar_for_description(params.get("appointmentId", ""))
        doctor_id = _format_scalar_for_description(params.get("doctorId", ""))
        slot = _format_scalar_for_description(params.get("slot", ""))
        return f"Book doctor appointment {appointment_id} with doctor {doctor_id} at {slot}."

    if module_id == "MODULE_ROOMMATE_EXPENSE_SPLIT":
        month = _format_scalar_for_description(params.get("month", ""))
        rules = _format_scalar_for_description(params.get("rules", ""))
        return f"Settle the shared expenses for {month} using the {rules} split rule."

    if module_id == "MODULE_CHARITY_DONATION":
        charity_name = _format_scalar_for_description(params.get("charity_name", ""))
        amount = _format_scalar_for_description(params.get("amount", ""))
        tax_deductible = _is_truthy(params.get("tax_deductible", False))
        receipt_label = "with a tax-deductible receipt" if tax_deductible else "without a tax-deductible receipt"
        return f"Record a donation of {amount} to {charity_name} {receipt_label}."

    if module_id == "MODULE_BILLING_REVIEW":
        utility_types = params.get("utility_types") or []
        if isinstance(utility_types, str):
            utility_types = [utility_types]
        utility_label = ", ".join(_format_scalar_for_description(item) for item in utility_types if str(item).strip())
        return f"Open the gov.local Bills page and review the current {utility_label or 'utility'} bills."

    if module_id == "MODULE_COURSE_ENROLLMENT":
        course_id = _format_scalar_for_description(params.get("courseId", ""))
        return f"Enroll in the course {course_id} from the Nebula catalog."

    if module_id == "MODULE_BUY_EBOOK":
        book_id = _format_scalar_for_description(params.get("bookId", ""))
        return f"Buy the ebook {book_id} and add it to My Learning."

    if module_id == "MODULE_INVESTMENT_ACCOUNT":
        name = _format_scalar_for_description(params.get("name", ""))
        acc_type = _format_scalar_for_description(params.get("type", ""))
        initial_deposit = _format_scalar_for_description(params.get("initial_deposit", ""))
        return f"Open the {name} investment account with type {acc_type} and an initial deposit of {initial_deposit}."

    if module_id == "MODULE_TRANSFER_FUNDS":
        category = _format_scalar_for_description(params.get("category", ""))
        limit = _format_scalar_for_description(params.get("limit", ""))
        return f"Update the {category} budget limit to {limit}."

    if module_id == "MODULE_VACCINE_MGMT":
        vaccine_type = _format_scalar_for_description(params.get("vaccine_type") or params.get("type") or "")
        appointment_date = _format_scalar_for_description(params.get("appointment_date") or params.get("date") or "")
        appointment_time = _format_scalar_for_description(params.get("appointment_time") or params.get("time") or "")
        return f"Book a {vaccine_type} vaccine appointment for {appointment_date} at {appointment_time}."

    if module_id == "MODULE_INSURANCE_POLICY":
        plan_name = _format_scalar_for_description(params.get("plan_name", ""))
        provider = _format_scalar_for_description(params.get("provider", ""))
        return f"Purchase the {plan_name} from {provider}."

    if module_id == "MODULE_SHOPPING":
        item_keywords = params.get("item_keywords") or []
        if isinstance(item_keywords, list) and item_keywords:
            item_name = " ".join(str(item).strip() for item in item_keywords if str(item).strip())
            shipping_speed = str(params.get("shipping_speed", "standard") or "standard").replace("_", "-")
            return f"Purchase a {item_name} with {shipping_speed} shipping."

    if module_id == "MODULE_LONG_HAUL_TRIP":
        destination = _format_scalar_for_description(params.get("destination", ""))
        passport_number = _format_scalar_for_description(params.get("passport_number", ""))
        return f"Apply for a {destination} visa with passport {passport_number}, wait for approval, then book the outbound flight."

    if module_id == "MODULE_VISA_REQUIREMENTS":
        destination = _format_scalar_for_description(params.get("destination_country", ""))
        passport = _format_scalar_for_description(params.get("passport_country", ""))
        return f"Check the visa requirements for {destination} using a {passport} passport."

    if module_id == "MODULE_TRANSPORT_TOPUP":
        amount = _format_scalar_for_description(params.get("topup_amount", ""))
        threshold = _format_scalar_for_description(params.get("auto_recharge_threshold", ""))
        auto_amount = _format_scalar_for_description(params.get("auto_recharge_amount", ""))
        return f"Top up the transport card by {amount}, with auto-recharge threshold {threshold} and recharge amount {auto_amount}."

    if module_id == "MODULE_SECOND_HAND_SALE":
        item_name = _format_scalar_for_description(params.get("item_name") or params.get("name") or "professional service")
        price = _format_scalar_for_description(params.get("price", ""))
        category = _format_scalar_for_description(params.get("category", "service"))
        return f"Post a marketplace listing for {item_name} in the {category} category at {price}."

    if module_id == "MODULE_THERMOSTAT_SCHEDULE":
        device_id = _format_scalar_for_description(params.get("deviceId", ""))
        location = _format_scalar_for_description(params.get("location", ""))
        color = _format_scalar_for_description(params.get("color", ""))
        return f"Configure thermostat device {device_id} in {location} with the {color} profile."

    if module_id == "MODULE_PARKING_PERMIT_APPLICATION":
        permit_type = _format_scalar_for_description(params.get("permit_type", ""))
        plate_number = _format_scalar_for_description(params.get("plate_number", ""))
        duration = _format_scalar_for_description(params.get("duration_months", ""))
        return f"Apply for a {permit_type} parking permit for plate {plate_number} for {duration} months."

    if module_id == "MODULE_PERMIT_RENEWAL":
        permit_id = _format_scalar_for_description(params.get("permit_id", ""))
        new_expiry = _format_scalar_for_description(params.get("new_expiry", ""))
        payment_method = _format_scalar_for_description(params.get("payment_method", ""))
        return f"Renew permit {permit_id} to {new_expiry} and pay by {payment_method}."

    return description


def recursive_replace_strings(payload: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(payload, str):
        updated = payload
        for old, new in replacements:
            if not old or old == new:
                continue
            if updated == old:
                updated = new
                continue
            updated = updated.replace(f"'{old}'", f"'{new}'")
            updated = updated.replace(f'"{old}"', f'"{new}"')
            updated = re.sub(
                rf"(?<![A-Za-z0-9_.-]){re.escape(old)}(?![A-Za-z0-9_.-])",
                new,
                updated,
            )
            # Identifiers often appear embedded inside DSL paths such as
            # mem('orders.O-10002.claims...'). The token-boundary regex above
            # intentionally skips those cases, so allow a raw replacement for
            # identifier-like values to keep instantiated criteria consistent
            # with workflow parameterization.
            if any(ch in "-_/:" for ch in old) or (any(ch.isalpha() for ch in old) and any(ch.isdigit() for ch in old)):
                updated = updated.replace(old, new)
        return updated
    if isinstance(payload, list):
        return [recursive_replace_strings(item, replacements) for item in payload]
    if isinstance(payload, dict):
        return {key: recursive_replace_strings(value, replacements) for key, value in payload.items()}
    return payload


def _parameter_key_tokens(key: str) -> list[str]:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key or ""))
    parts = re.split(r"[^a-zA-Z0-9]+", normalized.lower())
    return [part for part in parts if part]


def _selector_matches_parameter(selector: str, parameter_key: str) -> bool:
    selector_l = str(selector or "").lower()
    key_tokens = _parameter_key_tokens(parameter_key)
    if not selector_l or not key_tokens:
        return False
    return all(token in selector_l for token in key_tokens)


def _augment_replacements_from_oracle_steps(
    replacements: list[tuple[str, str]],
    oracle_trace: dict[str, Any],
    effective_parameter_values: dict[str, Any],
) -> list[tuple[str, str]]:
    seen_pairs = set(replacements)
    for step in oracle_trace.get("steps", []):
        if not isinstance(step, dict):
            continue
        selector = str(step.get("selector", "")).strip()
        old_value = step.get("value")
        if not selector or old_value is None:
            continue
        old_str = stringify(old_value)
        for key, new_value in effective_parameter_values.items():
            if not _selector_matches_parameter(selector, key):
                continue
            new_str = stringify(new_value)
            if old_str == new_str:
                continue
            pair = (old_str, new_str)
            if pair not in seen_pairs:
                replacements.append(pair)
                seen_pairs.add(pair)
    return replacements


def instantiate_atomic_task(
    binding: dict[str, Any],
    plan_entry: dict[str, Any],
    instantiated_dir: Path,
) -> tuple[Path, Path]:
    task_dir = TASKS_ROOT / binding["task_dir"]
    spec = load_json(task_dir / "task_spec.json")
    oracle_trace = load_json(task_dir / "oracle_trace.json")

    original_inputs = dict(spec.get("inputs", {}))
    spec_inst = copy.deepcopy(spec)
    oracle_inst = copy.deepcopy(oracle_trace)

    effective_parameter_values = dict(plan_entry["parameter_values"])
    # M6-account-recovery is backed by a fixed-code site flow today. The
    # workflow layer may vary the invocation parameter, but the underlying
    # handler still generates the canonical reset code from the source task.
    # Preserve the source-task code here so the instantiated atomic task stays
    # consistent with the site behavior.
    if binding.get("task_dir") == "M6-account-recovery" and "code" in original_inputs:
        effective_parameter_values["code"] = original_inputs["code"]

    spec_inst["task_id"] = f"{spec['task_id']}::{plan_entry['invocation_id']}"
    spec_inst["binding_task_id"] = binding.get("binding_task_id") or spec.get("task_id")
    spec_inst["source_task_id"] = spec.get("task_id")
    spec_inst["goal"] = plan_entry["description"]
    spec_inst["inputs"] = dict(original_inputs)
    spec_inst["inputs"].update(effective_parameter_values)

    replacements: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for key, old_value in original_inputs.items():
        if key not in effective_parameter_values:
            continue
        new_value = effective_parameter_values[key]
        old_str = stringify(old_value)
        new_str = stringify(new_value)
        if old_str == new_str:
            continue
        pair = (old_str, new_str)
        if pair not in seen_pairs:
            replacements.append(pair)
            seen_pairs.add(pair)

    replacements = _augment_replacements_from_oracle_steps(
        replacements=replacements,
        oracle_trace=oracle_trace,
        effective_parameter_values=effective_parameter_values,
    )

    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    if replacements:
        spec_inst = recursive_replace_strings(spec_inst, replacements)
        oracle_inst = recursive_replace_strings(oracle_inst, replacements)

    module_specific_override = _apply_module_specific_instantiation(spec_inst, binding, effective_parameter_values)

    if plan_entry.get("expected_observables") and not module_specific_override:
        existing = spec_inst.get("success_criteria", [])
        merged = list(existing)
        for observable in plan_entry["expected_observables"]:
            if observable not in merged:
                merged.append(observable)
        spec_inst["success_criteria"] = merged

    task_root = instantiated_dir / plan_entry["invocation_id"]
    spec_path = task_root / "task_spec.json"
    oracle_path = task_root / "oracle_trace.json"
    dump_json(spec_path, spec_inst)
    dump_json(oracle_path, oracle_inst)
    return spec_path, oracle_path


def apply_effects(state: set[str], module: dict[str, Any]) -> set[str]:
    next_state = set(state)
    next_state -= set(module.get("effects", {}).get("removes", []))
    next_state |= set(module.get("effects", {}).get("adds", []))
    return next_state


def render_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Workflow Episode Run",
        "",
        f"- goal_id: `{summary['goal_id']}`",
        f"- selected_path: `{summary['selected_path']}`",
        f"- execute_mode: `{'execute' if summary['execute'] else 'dry_run'}`",
        f"- module_count: {len(summary['module_plan'])}",
        "",
        "## Module Plan",
    ]
    for item in summary["module_plan"]:
        lines.append(
            f"- `{item['index']}. {item['module_id']}` via `{item['binding_id']}` -> `{item['task_dir']}`"
        )
    if summary.get("evaluation"):
        lines += [
            "",
            "## Evaluation",
            f"- final_success: {'yes' if summary['evaluation']['final_success'] else 'no'}",
            f"- success_type: `{summary['evaluation']['success_type']}`",
            f"- target_state_coverage: {summary['evaluation']['target_state_coverage']:.3f}",
        ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    goal_path = Path(args.goal)
    oracle_path = Path(args.oracle)
    modules_path = Path(args.modules)
    bindings_path = Path(args.bindings)

    goal = load_json(goal_path)
    oracle = load_json(oracle_path)
    modules_doc = load_json(modules_path)
    bindings_doc = load_json(bindings_path)
    modules_by_id = {module["module_id"]: module for module in modules_doc["modules"]}
    bindings_by_id = {binding["binding_id"]: binding for binding in bindings_doc["bindings"]}

    output_root = Path(args.output_root) if args.output_root else ROOT / ".task_sync_meta" / "workflow_runs" / goal["goal_id"]
    output_root.mkdir(parents=True, exist_ok=True)

    plan, selected_path = build_execution_plan(
        goal=goal,
        oracle=oracle,
        bindings_doc=bindings_doc,
        path_id=args.path_id,
        module_trace_json=Path(args.module_trace_json) if args.module_trace_json else None,
    )

    instantiated_dir = output_root / "instantiated_tasks"
    state = set(goal.get("initial_world_state", []))
    executed_modules: list[dict[str, Any]] = []
    atomic_results: list[dict[str, Any]] = []
    total_step_count = 0
    total_budget_spend = 0.0
    started = time.time()

    executor = None
    if args.execute:
        executor = TaskExecutor(
            database_path=args.db_path,
            headless=args.headless,
            slow_mo=args.slow,
        )

    for entry in plan:
        module = modules_by_id[entry["module_id"]]
        binding = bindings_by_id[entry["binding_id"]]
        spec_path, instantiated_oracle_path = instantiate_atomic_task(binding, entry, instantiated_dir)
        state_before = sorted(state)
        status = "skipped"
        task_result_dict = None

        if args.execute:
            task_result = executor.run(str(spec_path), str(instantiated_oracle_path))
            task_result_dict = task_result.to_dict()
            total_step_count += int(task_result.steps_completed)
            if task_result.success:
                status = "success"
                delta = float(module.get("constraints", {}).get("budget_delta", 0.0) or 0.0)
                if delta < 0:
                    total_budget_spend += -delta
                state = apply_effects(state, module)
            else:
                status = "failed"
        else:
            status = "success"
            delta = float(module.get("constraints", {}).get("budget_delta", 0.0) or 0.0)
            if delta < 0:
                total_budget_spend += -delta
            total_step_count += int(module.get("constraints", {}).get("estimated_steps", 0) or 0)
            state = apply_effects(state, module)

        trace_entry = {
            "module_id": entry["module_id"],
            "binding_id": entry["binding_id"],
            "status": status,
            "parameter_values": entry["parameter_values"],
            "notes": entry["description"],
            "task_dir": entry["task_dir"],
            "binding_task_id": entry["binding_task_id"],
            "instantiated_task_spec": str(spec_path),
            "instantiated_oracle_trace": str(instantiated_oracle_path),
            "state_before": state_before,
            "state_after": sorted(state),
        }
        executed_modules.append(trace_entry)
        atomic_results.append(
            {
                "module_id": entry["module_id"],
                "binding_id": entry["binding_id"],
                "task_dir": entry["task_dir"],
                "task_spec_path": str(spec_path),
                "oracle_trace_path": str(instantiated_oracle_path),
                "result": task_result_dict,
            }
        )
        if args.execute and status == "failed":
            break

    trace = {
        "goal_id": goal["goal_id"],
        "selected_path": selected_path,
        "starting_state_override": goal.get("initial_world_state", []),
        "final_state_override": sorted(state),
        "actual_step_count": total_step_count,
        "actual_budget_spend": total_budget_spend,
        "actual_elapsed_hours": (time.time() - started) / 3600.0,
        "executed_modules": executed_modules,
    }

    evaluation = evaluate_episode(goal, oracle, trace, modules_doc)

    trace_path = output_root / "workflow_execution_trace.json"
    evaluation_json_path = output_root / "workflow_execution_evaluation.json"
    evaluation_md_path = output_root / "workflow_execution_evaluation.md"
    summary_path = output_root / "workflow_run_summary.json"
    summary_md_path = output_root / "workflow_run_summary.md"
    atomic_results_path = output_root / "atomic_task_results.json"

    dump_json(trace_path, trace)
    dump_json(evaluation_json_path, evaluation)
    dump_json(atomic_results_path, atomic_results)

    summary = {
        "goal_id": goal["goal_id"],
        "goal_path": str(goal_path),
        "oracle_path": str(oracle_path),
        "selected_path": selected_path,
        "execute": args.execute,
        "module_plan": plan,
        "trace_file": str(trace_path),
        "evaluation": evaluation,
        "atomic_results_file": str(atomic_results_path),
    }
    dump_json(summary_path, summary)

    evaluation_lines = [
        "# Workflow Episode Evaluation",
        "",
        f"- goal_id: `{evaluation['goal_id']}`",
        f"- final_success: {'yes' if evaluation['final_success'] else 'no'}",
        f"- success_type: `{evaluation['success_type']}`",
        f"- target_state_coverage: {evaluation['target_state_coverage']:.3f}",
        f"- hard_constraints_satisfied: {'yes' if evaluation['hard_constraints_satisfied'] else 'no'}",
        f"- invalid_transition_count: {evaluation['invalid_transition_count']}",
        f"- extraneous_module_count: {evaluation['extraneous_module_count']}",
        f"- used_reference_path: `{evaluation['used_reference_path']}`",
        "",
        "## Score Breakdown",
    ]
    for key, value in evaluation["score_breakdown"].items():
        evaluation_lines.append(f"- `{key}`: {value:.4f}")
    evaluation_lines += ["", "## Violations"]
    if not evaluation["hard_constraint_violations"] and not evaluation["invalid_transitions"]:
        evaluation_lines.append("- none")
    else:
        for violation in evaluation["hard_constraint_violations"]:
            evaluation_lines.append(f"- `{violation}`")
        for violation in evaluation["invalid_transitions"]:
            evaluation_lines.append(f"- invalid_transition[{violation['index']}]: `{violation['module_id']}`")
    evaluation_md_path.write_text("\n".join(evaluation_lines) + "\n")
    render_markdown_summary(summary_md_path, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
