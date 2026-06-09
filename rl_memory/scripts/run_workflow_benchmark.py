#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import socket
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_ROOT = ROOT / "tasks"
DEFAULT_BATCH_ROOT = TASKS_ROOT / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_MODULES = TASKS_ROOT / "workflow_module_library.json"
DEFAULT_BINDINGS = TASKS_ROOT / "workflow_module_bindings.json"

_SUPPLY_DISRUPTION_GOALS: dict[str, str] = {
    "cancel_order": (
        "Resolve the disruption by cancelling the Spare Water Filter order and requesting a refund. "
        "When prompted, enter the resolution reason: Water filter shipment disrupted; refund requested."
    ),
    "request_refund": (
        "Resolve the disruption by cancelling the Desk Air Purifier shipment and requesting a refund. "
        "When prompted, enter the resolution reason: Air purifier shipment disrupted; refund requested."
    ),
    "switch_item": (
        "Resolve the disruption by rerouting Baby Formula shipping through the alternate hub. "
        "When prompted, enter the resolution reason: Baby Formula needed; reroute through alternate hub."
    ),
}

_SMART_METER_SOURCE_LABELS: dict[str, str] = {
    "outdoor_photo": "Outdoor meter photo",
    "tenant_portal": "Tenant portal statement",
    "manual_display": "Manual display check",
}

_JOB_SEARCH_SOURCE_EMAIL_IDS: dict[tuple[str, str], str] = {
    ("research engineer next steps", "research-hiring@example.com"): "job-thread-research-001",
    ("platform engineer application", "talent@example.com"): "job-thread-platform-002",
    ("ml systems interview follow-up", "mlsystems@example.com"): "job-thread-mlsystems-003",
    ("applied scientist recruiter note", "science-recruiting@example.com"): "job-thread-science-004",
    ("job application follow-up", "recruiter@example.com"): "job-thread-general-005",
}

_LINKEDIN_SOURCE_EMAIL_IDS: dict[tuple[str, str], str] = {
    ("linkedin profile update", "notifications@linkedin.com"): "linkedin-profile-update-001",
}

_RECEIPT_SOURCE_BY_FILE: dict[str, dict[str, str]] = {
    "taxi_invoice_march.pdf": {
        "id": "receipt-taxi-march",
        "vendor": "City Taxi",
        "document_date": "2025-03-31",
        "amount": "42.80",
        "archive_code": "ARC-TAXI-0331",
        "retention_label": "expense_receipt",
    },
    "event_receipt_round1.pdf": {"id": "receipt-event-round1", "vendor": "City Taxi", "document_date": "2025-03-29", "amount": "31.40", "archive_code": "ARC-EVT-R1", "retention_label": "event_receipt"},
    "event_receipt_round2.pdf": {"id": "receipt-event-round2", "vendor": "Metro Catering", "document_date": "2025-03-30", "amount": "86.00", "archive_code": "ARC-EVT-R2", "retention_label": "event_receipt"},
    "event_receipt_round3.pdf": {"id": "receipt-event-round3", "vendor": "City Taxi", "document_date": "2025-03-31", "amount": "38.50", "archive_code": "ARC-EVT-R3", "retention_label": "event_receipt"},
    "event_receipt_round4.pdf": {"id": "receipt-event-round4", "vendor": "Conference Shuttle", "document_date": "2025-04-01", "amount": "54.25", "archive_code": "ARC-EVT-R4", "retention_label": "event_receipt"},
    "event_receipt_round5.pdf": {"id": "receipt-event-round5", "vendor": "Venue Services", "document_date": "2025-04-02", "amount": "112.00", "archive_code": "ARC-EVT-R5", "retention_label": "event_receipt"},
}

_PAPER_DRAFT_IDS: dict[str, str] = {
    "branch-aware benchmarking": "paper-draft-branch-aware",
    "workflow robustness study": "paper-draft-workflow-robustness",
    "cross-site planning benchmarks": "paper-draft-cross-site",
    "agent failure taxonomy": "paper-draft-failure-taxonomy",
}

_EVENT_TRANSFER_RECIPIENT_NAMES: dict[str, str] = {
    "S112233": "Samira Ortiz",
}

_BANK_APPLICANT_IDS: dict[str, str] = {
    "alex chen": "applicant-alex",
    "mira patel": "applicant-mira",
    "noah rivera": "applicant-noah",
    "lina chen": "applicant-lina",
    "owen brooks": "applicant-owen",
    "ivy zhang": "applicant-ivy",
}

_CONFERENCE_CONFIRMATIONS_BY_REG: dict[str, dict[str, str]] = {
    "CONF-9046": {
        "event": "Vision Research Expo",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
    "CONF-1184": {
        "event": "Vision Research Expo",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
    "CONF-8933": {
        "event": "Data Infra Week",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
    "CONF-3471": {
        "event": "Cloud Security Conf",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
    "CONF-2299": {
        "event": "Product Analytics Forum",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
    "CONF-7815": {
        "event": "Distributed Systems Meetup",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
    "CONF-4520": {
        "event": "Data Infra Week",
        "report_id": "EXP-2201",
        "total_amount": "980",
        "linked_pnr": "PNR-2201",
        "description": "Conference registration and travel",
        "expense_type": "conference_registration",
        "receipt_bundle": "RB-2201-CONF-REG",
    },
}


def _smart_meter_source_label(source: Any) -> str:
    source_key = str(source or "outdoor_photo").strip().lower()
    return _SMART_METER_SOURCE_LABELS.get(source_key, source_key or "Outdoor meter photo")


def _job_search_source_email_id(subject: Any, sender: Any) -> str:
    subject_key = str(subject or "Job Application Follow-up").strip().lower()
    sender_key = str(sender or "recruiter@example.com").strip().lower()
    return _JOB_SEARCH_SOURCE_EMAIL_IDS.get((subject_key, sender_key), "job-thread-general-005")


def _linkedin_source_email_id(subject: Any, sender: Any) -> str:
    subject_key = str(subject or "LinkedIn Profile Update").strip().lower()
    sender_key = str(sender or "notifications@linkedin.com").strip().lower()
    return _LINKEDIN_SOURCE_EMAIL_IDS.get((subject_key, sender_key), "linkedin-profile-update-001")


def _calendar_source_for_event(title: Any, date: Any, time_value: Any, event_type: Any = None, description: Any = None) -> dict[str, str]:
    title_text = str(title or "Dentist Follow-up").strip()
    date_text = str(date or "2026-01-16").strip()
    time_text = str(time_value or "15:30").strip()
    type_text = str(event_type or "personal").strip()
    description_text = str(description or "Routine dental follow-up").strip()
    if title_text == "牙医预约":
        title_slug = "dentist-zh"
    elif title_text.lower() == "dentist follow-up":
        title_slug = "dentist-followup"
    else:
        title_slug = re.sub(r"[^a-z0-9]+", "-", title_text.lower()).strip("-") or "event"
    date_slug = re.sub(r"[^0-9]+", "", date_text) or "20260116"
    time_slug = re.sub(r"[^0-9]+", "", time_text) or "1530"
    source_code = f"CAL-{date_slug[4:8] or '0116'}-{time_slug or '1530'}"
    return {
        "id": f"calendar-{title_slug}-{date_slug}-{time_slug}",
        "title": title_text,
        "date": date_text,
        "time": time_text,
        "type": type_text,
        "description": description_text,
        "source_code": source_code,
    }


def _receipt_source_for_file(file_name: Any) -> dict[str, str]:
    key = str(file_name or "taxi_invoice_march.pdf").strip()
    return dict(_RECEIPT_SOURCE_BY_FILE.get(key, _RECEIPT_SOURCE_BY_FILE["taxi_invoice_march.pdf"]))


def _paper_draft_id(title: Any) -> str:
    return _PAPER_DRAFT_IDS.get(str(title or "Branch-Aware Benchmarking").strip().lower(), "paper-draft-branch-aware")


def _bank_applicant_id(fullname: Any) -> str:
    return _BANK_APPLICANT_IDS.get(str(fullname or "Alex Chen").strip().lower(), "applicant-alex")


def _bank_applicant_verification_code(applicant_id: Any, phone: Any) -> str:
    applicant = re.sub(r"^applicant-", "", str(applicant_id or "applicant-alex").strip(), flags=re.IGNORECASE)
    applicant = re.sub(r"[^A-Za-z0-9]+", "", applicant).upper() or "ALEX"
    phone_tail = re.sub(r"\D+", "", str(phone or "555-0102"))[-4:] or "0102"
    return f"BANK-{applicant}-{phone_tail}"


def _parking_intake_code(plate_number: Any) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "", str(plate_number or "C55021")).upper()
    if normalized == "C55021":
        return "PARK-INT-55021"
    return f"PARK-INT-{normalized or 'ACTIVE'}"


def _renewal_notice_code(new_expiry: Any) -> str:
    expiry_text = str(new_expiry or "").strip()
    if expiry_text.startswith("2027"):
        return "RENEW-RP-2027"
    return "RENEW-RP-77"


def _conference_source_for_registration(registration_id: Any, event: Any = None) -> dict[str, str]:
    key = str(registration_id or "CONF-9046").strip()
    source = dict(_CONFERENCE_CONFIRMATIONS_BY_REG.get(key, _CONFERENCE_CONFIRMATIONS_BY_REG["CONF-9046"]))
    desired_event = str(event or "").strip().lower()
    if desired_event and str(source.get("event") or "").strip().lower() != desired_event:
        for candidate_key, candidate_source in _CONFERENCE_CONFIRMATIONS_BY_REG.items():
            if str(candidate_source.get("event") or "").strip().lower() == desired_event:
                key = candidate_key
                source = dict(candidate_source)
                break
    source["registration_id"] = key if key in _CONFERENCE_CONFIRMATIONS_BY_REG else "CONF-9046"
    return source

sys.path.insert(0, str(ROOT))

from agent.llm_client import build_client  # noqa: E402
from llm_runner import execute_agent_task  # noqa: E402
from task_handlers.property_addresses import property_address_for_id, seed_housing_properties  # noqa: E402
from task_handlers.utils import deep_merge  # noqa: E402

LEASE_ADDRESS_CONSUMERS = {
    "MODULE_LEASE_CONTRACT_REGISTRATION": "address",
    "MODULE_BANK_OPENING": "address",
    "MODULE_MOBILE_PLAN_SIGNUP": "address",
    "MODULE_UTILITY_SETUP": "address",
    "MODULE_ADDRESS_CHANGE": "new_address",
    "MODULE_VEHICLE_ADDRESS_UPDATE": "new_address",
}

COURSE_ID_CONSUMERS = {
    "MODULE_SUBMIT_ASSIGNMENT": "course_id",
}

APPOINTMENT_ID_CONSUMERS = {
    "MODULE_MEDICAL_CLAIM": "appointment_id",
}

SUPPORT_TICKET_ORDER_CONSUMERS = {
    "MODULE_CONTACT_SUPPORT": "order_id",
    "MODULE_CUSTOMER_SERVICE": "order_id",
    "MODULE_LOGISTICS_FIX": "order_id",
    "MODULE_RETURN": "order_id",
    "MODULE_WARRANTY_CLAIM": "order_id",
}

BILL_SOURCE_CONSUMERS = {
    "MODULE_AUTOPAY": {
        "bill_source_payee": "payee",
        "bill_source_account_id": "account_number",
    },
    "MODULE_COMPLEX_AUTOPAY": {
        "bill_source_payee": "payee",
        "bill_source_account_id": "account_number",
    },
}

DATA_REQUEST_CONSUMERS = {
    "MODULE_DOWNLOAD_DATA": {
        "data_request_type": "request_type",
        "data_request_platform": "platform",
        "data_request_scope": "data_scope",
        "data_request_reason": "reason",
        "data_request_contact_email": "contact_email",
    },
}

FLIGHT_PNR_CONSUMERS = {
    "MODULE_EXPENSE_REPORT": "pnr",
    "MODULE_AIRPORT_TRANSFER": "flight_pnr",
    "MODULE_CHECK_IN": "flight_pnr",
    "MODULE_COMMUTE_ROUTE": "flight_pnr",
}

# --- P1: COMPOSITE - Bank identity code chain ---
# BANK_OPENING produces verification_code (= bank identity code) and fullname.
# These propagate to BILL_AGGREGATION, AUTOPAY, COMPLEX_AUTOPAY.
BANK_IDENTITY_CODE_CONSUMERS = {
    "MODULE_BILL_AGGREGATION": "bank_identity_code",
    "MODULE_AUTOPAY": "bank_identity_code",
    "MODULE_COMPLEX_AUTOPAY": "bank_identity_code",
}

BANK_HOLDER_NAME_CONSUMERS = {
    "MODULE_BILL_AGGREGATION": "account_holder",
    "MODULE_AUTOPAY": "account_holder",
    "MODULE_COMPLEX_AUTOPAY": "account_holder",
}

# --- P2: HEALTH - Insurance policy chain ---
# INSURANCE_POLICY produces plan_id; runtime has health.insurance.policy_number.
# These propagate to PRESCRIPTION_REFILL and MEDICAL_CLAIM.
INSURANCE_PLAN_ID_CONSUMERS = {
    "MODULE_PRESCRIPTION_REFILL": "plan_id",
    "MODULE_MEDICAL_CLAIM": "plan_id",
}

INSURANCE_POLICY_NUMBER_CONSUMERS = {
    "MODULE_MEDICAL_CLAIM": "policy_id",
}

# --- P3: TRAVEL - Flight destination chain ---
# BOOK_FLIGHT/LONG_HAUL_TRIP produces destination.
# Propagates to AIRPORT_TRANSFER, CHECK_IN, COMMUTE_ROUTE.
FLIGHT_DESTINATION_CONSUMERS = {
    "MODULE_AIRPORT_TRANSFER": "flight_destination",
    "MODULE_CHECK_IN": "flight_destination",
    "MODULE_COMMUTE_ROUTE": "flight_destination",
}

# --- P4: DAILY - Order tracking chain ---
# TRACK_ORDERS produces order_id. Propagates to downstream daily modules.
TRACKED_ORDER_ID_CONSUMERS = {
    "MODULE_ORDER_ARRIVAL": "order_id",
    "MODULE_CUSTOMER_SERVICE": "order_id",
    "MODULE_LEAVE_REVIEW": "order_id",
}

# LEAVE_REVIEW produces merchant. Propagates to REVIEWS_BLACKLIST.
REVIEW_MERCHANT_CONSUMERS = {
    "MODULE_REVIEWS_BLACKLIST": "merchant",
}

PASSWORD_RESET_CONSUMERS = {
    "MODULE_PASSWORD_RESET_COMPLETION": {
        "reset_username": "username",
        "reset_code": "code",
        "reset_new_password": "new_password",
    },
}

GOAL_CONDITIONAL_REQUIRES = [
    ("MODULE_DOCTOR_APPT", "MODULE_PRESCRIPTION_REFILL", "medical_appointment_booked"),
    ("MODULE_DOCTOR_APPT", "MODULE_MEDICAL_CLAIM", "medical_appointment_booked"),
    ("MODULE_PRESCRIPTION_REFILL", "MODULE_MEDICAL_CLAIM", "prescription_refilled"),
    ("MODULE_DATA_DELETION", "MODULE_DOWNLOAD_DATA", "deletion_request_submitted"),
    ("MODULE_LOGISTICS_FIX", "MODULE_WARRANTY_CLAIM", "logistics_ticket_opened"),
    ("MODULE_LEAVE_REVIEW", "MODULE_REVIEWS_BLACKLIST", "positive_review_submitted"),
]

DEPRECATED_WORKFLOW_MODULE_IDS: set[str] = set()


def _load_local_helper(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load local helper module from {SCRIPT_DIR / filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


try:
    from rl_memory.scripts.evaluate_workflow_episode import canonical_module_id, evaluate_episode  # noqa: E402
except ModuleNotFoundError:
    _workflow_eval = _load_local_helper(
        "_workflow_eval_local",
        "evaluate_workflow_episode.py",
    )
    canonical_module_id = _workflow_eval.canonical_module_id
    evaluate_episode = _workflow_eval.evaluate_episode

try:
    from rl_memory.scripts.run_workflow_episode import (  # noqa: E402
        apply_effects,
        dump_json,
        instantiate_atomic_task,
        load_json,
    )
except ModuleNotFoundError:
    _workflow_episode = _load_local_helper("_workflow_episode_local", "run_workflow_episode.py")
    apply_effects = _workflow_episode.apply_effects
    dump_json = _workflow_episode.dump_json
    instantiate_atomic_task = _workflow_episode.instantiate_atomic_task
    load_json = _workflow_episode.load_json


MODULE_CHOOSER_SYSTEM_PROMPT = """You are a workflow planner for a web agent benchmark.
Choose exactly one next workflow module from the provided candidate list.
Rules:
1. Prefer modules that legally advance the remaining target state.
2. Do not choose a module whose preconditions are not currently satisfied unless no executable candidate exists.
3. Avoid repeating already failed modules.
4. Use the visible goal, current state, preconditions, and effects to choose; do not treat list order as an answer key.
5. Output exactly one token: a MODULE_ID from the candidate list, or DONE.
Do not explain your reasoning."""

RUNTIME_ISOLATION_NOTES = {
    "per_goal": (
        "Each goal runs in its own runtime root and server. "
        "Use this mode for official benchmark numbers."
    ),
    "shared": (
        "Shared runtime/server reuse is debug-only and can contaminate results across goals. "
        "Do not use shared-mode results as official benchmark numbers."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run workflow benchmark episodes with module-level planning and atomic execution.")
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--split", choices=["train", "dev", "test"], default="dev")
    parser.add_argument("--goal-id", action="append", default=[], help="Specific goal id to run. Can be passed multiple times.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of goals to run after filtering.")
    parser.add_argument(
        "--prompt-difficulty",
        action="append",
        choices=["easy", "medium", "hard"],
        default=[],
        help="Filter goals by prompt difficulty tier. Can be passed multiple times.",
    )
    parser.add_argument(
        "--prompt-mode",
        choices=["active", "easy", "hard"],
        default="active",
        help="Use the active prompt stored in each goal, or force a retained prompt variant when available.",
    )
    parser.add_argument("--modules", default=str(DEFAULT_MODULES))
    parser.add_argument("--bindings", default=str(DEFAULT_BINDINGS))
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--runtime-root", default=".", help="Runtime root whose data.db/env/state.json will be restored between episodes.")
    parser.add_argument("--module-policy", choices=["llm", "heuristic", "reference"], default="llm")
    parser.add_argument("--atomic-policy", choices=["agent", "dry_run", "oracle"], default="agent")
    parser.add_argument("--candidate-limit", type=int, default=12)
    parser.add_argument(
        "--decoy-quota",
        type=int,
        default=0,
        help="Optional minimum number of executable hard-negative/decoy candidates to surface when available.",
    )
    parser.add_argument(
        "--decoy-insert-rank",
        type=int,
        default=3,
        help="1-based candidate-list position used when injecting hard-negative candidates.",
    )
    parser.add_argument("--target-backward-depth", type=int, default=2)
    parser.add_argument("--module-max-tokens", type=int, default=32)
    parser.add_argument("--module-temperature", type=float, default=0.0)
    parser.add_argument("--atomic-max-steps", type=int, default=25)
    parser.add_argument("--atomic-repeat-fail-threshold", type=int, default=3)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--runtime-isolation",
        choices=["per_goal", "shared"],
        default="per_goal",
        help="Runtime isolation mode. Use `per_goal` for official results; `shared` is debug-only.",
    )
    return parser.parse_args()


def _alloc_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _prepare_goal_runtime(runtime_root: Path, snapshot_root: Path) -> None:
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "tasks").mkdir(parents=True, exist_ok=True)
    (runtime_root / "output").mkdir(parents=True, exist_ok=True)

    def _ignore_transient_files(_src: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if (
                name == ".DS_Store"
                or name.startswith(".~")
                or name.startswith(".nfs")
                or name.endswith("~")
                or name.endswith(".swp")
                or name.endswith(".swo")
                or name.endswith(".tmp")
            ):
                ignored.add(name)
        return ignored

    shutil.copytree(ROOT / "env", runtime_root / "env", dirs_exist_ok=True, ignore=_ignore_transient_files)
    sites_dst = runtime_root / "sites"
    try:
        sites_dst.symlink_to(ROOT / "sites", target_is_directory=True)
    except OSError:
        shutil.copytree(ROOT / "sites", sites_dst, dirs_exist_ok=True, ignore=_ignore_transient_files)

    restore_runtime(runtime_root, snapshot_root)


def _start_goal_server(runtime_root: Path, server_log_path: Path) -> tuple[subprocess.Popen[str], str]:
    server_log_path.parent.mkdir(parents=True, exist_ok=True)
    attempts = int(os.environ.get("WEBAGENT_SERVER_START_ATTEMPTS", "8"))
    last_error = "server did not respond"

    for attempt in range(1, attempts + 1):
        port = _alloc_port()
        base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["WEBAGENT_RUNTIME_ROOT"] = str(runtime_root)
        env["WEBAGENT_SERVER_PORT"] = str(port)
        env["WEBAGENT_SERVER_BASE_URL"] = base_url
        env.setdefault("BENCHMARK_CLEAN_MODE", "true")

        with open(server_log_path, "a", encoding="utf-8") as log_fh:
            log_fh.write(f"[server-start] attempt={attempt} port={port}\n")
            log_fh.flush()
            log_offset = log_fh.tell()
            proc = subprocess.Popen(
                [sys.executable, str(ROOT / "server.py"), str(port)],
                cwd=str(ROOT),
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
            )

        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                try:
                    with open(server_log_path, "r", encoding="utf-8", errors="replace") as check_fh:
                        check_fh.seek(log_offset)
                        recent_log = check_fh.read()
                except OSError:
                    recent_log = ""
                if "Address already in use" in recent_log and attempt < attempts:
                    last_error = f"port {port} already in use"
                    time.sleep(0.2)
                    break
                raise RuntimeError(
                    f"Goal server exited early for {runtime_root}. "
                    f"See log: {server_log_path}"
                )
            try:
                with urlopen(f"{base_url}/api/env", timeout=1) as resp:
                    if 200 <= getattr(resp, "status", 200) < 500:
                        return proc, base_url
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.2)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            if attempt < attempts:
                time.sleep(0.2)
                continue

    raise RuntimeError(
        f"Failed to start goal server after {attempts} attempts: {last_error}. "
        f"See log: {server_log_path}"
    )


@contextmanager
def _temporary_process_env(updates: dict[str, str]):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _pushd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def preconditions_satisfied(requires: dict[str, Any], state: set[str]) -> bool:
    all_of = set(requires.get("all_of", []))
    any_of = set(requires.get("any_of", []))
    none_of = set(requires.get("none_of", []))
    if not all_of.issubset(state):
        return False
    if any_of and not (any_of & state):
        return False
    if none_of & state:
        return False
    return True


def missing_preconditions(requires: dict[str, Any], state: set[str]) -> set[str]:
    missing = set(requires.get("all_of", [])) - state
    any_of = set(requires.get("any_of", []))
    if any_of and not (any_of & state):
        missing |= any_of
    return missing


def exception_payload(exc: Exception) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def summarize_atomic_result(task_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": bool(task_result.get("success")),
        "end_reason": task_result.get("end_reason", ""),
        "failure_category": task_result.get("failure_category", ""),
        "steps_executed": int(task_result.get("steps_executed", 0) or 0),
        "criteria_total": int(task_result.get("criteria_total", 0) or 0),
        "criteria_passed": int(task_result.get("criteria_passed", 0) or 0),
        "checkpoint_total": int(task_result.get("checkpoint_total", 0) or 0),
        "checkpoint_passed": int(task_result.get("checkpoint_passed", 0) or 0),
        "checkpoint_required_total": int(task_result.get("checkpoint_required_total", 0) or 0),
        "checkpoint_required_passed": int(task_result.get("checkpoint_required_passed", 0) or 0),
        "checkpoint_weight_earned": float(task_result.get("checkpoint_weight_earned", 0.0) or 0.0),
        "checkpoint_score_percent": task_result.get("checkpoint_score_percent"),
        "verify_error": task_result.get("verify_error", ""),
        "step_error_message": task_result.get("step_error_message", ""),
        "skill_bank_credit_source": task_result.get("skill_bank_credit_source", ""),
        "skill_bank_updates": task_result.get("skill_bank_updates", 0),
        "action_outcomes": task_result.get("action_outcomes", []),
        "transient_retry_count": int(task_result.get("transient_retry_count", 0) or 0),
        "transient_retry_reason": task_result.get("transient_retry_reason", ""),
        "raw_output_tail": str(task_result.get("raw_output", "") or "")[-4000:],
    }


def _is_transient_browser_close_failure(task_result: dict[str, Any]) -> bool:
    if bool(task_result.get("success")):
        return False
    error_text = " ".join(
        str(task_result.get(key, "") or "")
        for key in ("step_error_message", "verify_error", "end_reason", "raw_output")
    )
    if "Target page, context or browser has been closed" in error_text:
        return True
    return "ERROR(TimeoutOrLimit)" in error_text


def _oracle_execution_result_payload(result: Any) -> dict[str, Any]:
    result_dict = result.to_dict()
    verification = result_dict.get("verification") or {}
    error = result_dict.get("error") or {}
    success = bool(result_dict.get("success"))
    checkpoint_total = int(verification.get("checkpoint_total", 0) or 0)
    checkpoint_passed = int(verification.get("checkpoint_passed", 0) or 0)
    criteria_total = int(verification.get("criteria_total", checkpoint_total) or 0)
    criteria_passed = int(verification.get("criteria_passed", checkpoint_passed) or 0)
    if success:
        end_reason = "criteria_passed"
        failure_category = "none"
    elif error:
        end_reason = "step_error_abort"
        failure_category = str(error.get("error_type") or "oracle_step_error")
    else:
        end_reason = "criteria_or_checkpoint_failed"
        failure_category = "criteria_or_checkpoint_failed"
    verify_error = ""
    if not success:
        failed = verification.get("required_failed_ids") or verification.get("criteria_failed") or []
        if failed:
            verify_error = ",".join(str(item) for item in failed)
    return {
        "success": success,
        "end_reason": end_reason,
        "failure_category": failure_category,
        "steps_executed": int(result_dict.get("steps_completed", 0) or 0),
        "criteria_total": criteria_total,
        "criteria_passed": criteria_passed,
        "checkpoint_total": checkpoint_total,
        "checkpoint_passed": checkpoint_passed,
        "checkpoint_required_total": checkpoint_total,
        "checkpoint_required_passed": checkpoint_passed,
        "checkpoint_weight_earned": float(verification.get("step_progress", 0.0) or 0.0),
        "checkpoint_score_percent": verification.get("step_score_percent"),
        "verify_error": verify_error,
        "step_error_message": str(error.get("error_message", "") or ""),
        "skill_bank_credit_source": "oracle",
        "skill_bank_updates": 0,
        "action_outcomes": [],
        "raw_output": json.dumps(result_dict, ensure_ascii=False),
        "agent_backend": "oracle",
        "agent_model": "oracle_trace",
    }


def build_candidate_trace_payload(
    module: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    needed_predicates: set[str],
    theme: str,
    forbidden_modules: set[str] | None = None,
    forbidden_predicates: set[str] | None = None,
    *,
    score: float,
    executable: bool,
    reachable: bool,
) -> dict[str, Any]:
    adds = set(module.get("effects", {}).get("adds", []))
    direct_hits = adds & remaining_targets
    support_hits = adds & (needed_predicates - remaining_targets)
    forbidden_modules = forbidden_modules or set()
    forbidden_predicates = forbidden_predicates or set()
    forbidden_predicate_hits = adds & forbidden_predicates
    return {
        "module_id": module["module_id"],
        "name": module.get("name", module["module_id"]),
        "family": module.get("family", ""),
        "theme_match": module.get("family") == theme,
        "forbidden_module": module["module_id"] in forbidden_modules,
        "forbidden_predicate_hits": sorted(forbidden_predicate_hits),
        "requires": {
            "all_of": list(module.get("requires", {}).get("all_of", []) or []),
            "any_of": list(module.get("requires", {}).get("any_of", []) or []),
            "none_of": list(module.get("requires", {}).get("none_of", []) or []),
        },
        "adds": sorted(adds),
        "direct_target_hits": sorted(direct_hits),
        "support_target_hits": sorted(support_hits),
        "missing_preconditions": sorted(missing_preconditions(module.get("requires", {}), state)),
        "executable": executable,
        "reachable_within_remaining_budget": reachable,
        "score": score,
        "estimated_steps": int(module.get("constraints", {}).get("estimated_steps", 0) or 0),
        "budget_delta": float(module.get("constraints", {}).get("budget_delta", 0.0) or 0.0),
    }


def remap_runtime_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    target_base = os.environ.get("WEBAGENT_SERVER_BASE_URL", "").strip()
    if not target_base:
        return raw
    try:
        parsed = urlsplit(raw)
        source = urlsplit("http://localhost:8014")
        target = urlsplit(target_base)
    except Exception:
        return raw
    if parsed.scheme not in {"http", "https"}:
        return raw
    if parsed.netloc == source.netloc and target.netloc:
        return urlunsplit((target.scheme or parsed.scheme, target.netloc, parsed.path, parsed.query, parsed.fragment))
    return raw


def infer_start_url(oracle_trace_path: Path) -> str:
    if not oracle_trace_path.exists():
        return remap_runtime_url("http://localhost:8014/shop.local/index.html")
    oracle = load_json(oracle_trace_path)
    for step in oracle.get("steps", []):
        if step.get("act") == "open" and step.get("url"):
            return remap_runtime_url(str(step["url"]))
    return remap_runtime_url("http://localhost:8014/shop.local/index.html")


def infer_prompt_difficulty(goal: dict[str, Any]) -> dict[str, Any]:
    explicit = goal.get("prompt_difficulty")
    if isinstance(explicit, dict) and explicit.get("tier"):
        tier = str(explicit.get("tier") or "").strip().lower()
        if tier in {"easy", "medium", "hard"}:
            return dict(explicit)

    hard_sample = goal.get("hardening", {}).get("prompt_hard_sample", {})
    if isinstance(hard_sample, dict) and hard_sample.get("strategy") == "semantic_route_blurring":
        return {
            "tier": "hard",
            "scheme": "prompt_clarity_v1",
            "reason_codes": ["semantic_route_blurring", "requires_route_inference"],
        }

    return {
        "tier": "easy",
        "scheme": "prompt_clarity_v1",
        "reason_codes": ["clear_goal_prompt"],
    }


def apply_prompt_mode(goal: dict[str, Any], prompt_mode: str) -> dict[str, Any]:
    if prompt_mode == "active":
        return goal

    variants = goal.get("prompt_variants")
    if not isinstance(variants, dict):
        return goal
    variant = variants.get(prompt_mode)
    if not isinstance(variant, dict) or not variant.get("instruction"):
        return goal

    patched = copy.deepcopy(goal)
    patched["instruction"] = str(variant["instruction"])
    if isinstance(variant.get("visible_constraints"), dict):
        patched["visible_constraints"] = copy.deepcopy(variant["visible_constraints"])
    if isinstance(variant.get("prompt_difficulty"), dict):
        patched["prompt_difficulty"] = copy.deepcopy(variant["prompt_difficulty"])
    else:
        patched["prompt_difficulty"] = {
            "tier": prompt_mode,
            "scheme": "prompt_clarity_v1",
            "active_variant": prompt_mode,
        }
    return patched


def collect_goals(
    batch_root: Path,
    split: str,
    goal_ids: list[str],
    limit: int,
    prompt_difficulties: list[str],
) -> list[dict[str, Any]]:
    split_root = batch_root / split
    manifest = load_json(split_root / "manifest.json")
    refs = manifest.get("goals", [])
    if goal_ids:
        goal_id_set = set(goal_ids)
        refs = [item for item in refs if item["goal_id"] in goal_id_set]
    if prompt_difficulties:
        allowed_tiers = {item.strip().lower() for item in prompt_difficulties}
        filtered_refs = []
        for item in refs:
            goal = load_json(split_root / item["goal_file"])
            if infer_prompt_difficulty(goal).get("tier") in allowed_tiers:
                filtered_refs.append(item)
        refs = filtered_refs
    if limit > 0:
        refs = refs[:limit]
    return refs


def build_indices(modules_doc: dict[str, Any], bindings_doc: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    modules_by_id = {
        item["module_id"]: item
        for item in modules_doc["modules"]
        if item.get("module_id") not in DEPRECATED_WORKFLOW_MODULE_IDS
    }
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings_doc["bindings"]:
        if binding.get("module_id") in DEPRECATED_WORKFLOW_MODULE_IDS:
            continue
        bindings_by_module[binding["module_id"]].append(binding)
    return modules_by_id, dict(bindings_by_module)


def allowed_modules_from_oracle(oracle: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for path in oracle.get("success_paths", []):
        allowed.update(
            canonical_module_id(item)
            for item in (path.get("required_modules", []) or [])
            if isinstance(item, str)
        )
        allowed.update(
            canonical_module_id(item)
            for item in (path.get("optional_modules", []) or [])
            if isinstance(item, str)
        )
    for invocation in oracle.get("reference_invocations", []):
        module_id = invocation.get("module_id")
        if module_id:
            allowed.add(canonical_module_id(module_id))
    return allowed


def apply_goal_conditional_requires(
    modules_doc: dict[str, Any],
    oracle_allowed_module_ids: set[str],
) -> dict[str, Any]:
    if not oracle_allowed_module_ids:
        return modules_doc

    additions_by_module: dict[str, set[str]] = defaultdict(set)
    for source_module, target_module, required_predicate in GOAL_CONDITIONAL_REQUIRES:
        if source_module in oracle_allowed_module_ids and target_module in oracle_allowed_module_ids:
            additions_by_module[target_module].add(required_predicate)
    if not additions_by_module:
        return modules_doc

    patched = copy.deepcopy(modules_doc)
    for module in patched.get("modules", []):
        module_id = module.get("module_id")
        additions = additions_by_module.get(module_id)
        if not additions:
            continue
        requires = module.setdefault("requires", {})
        all_of = list(requires.get("all_of", []) or [])
        for predicate in sorted(additions):
            if predicate not in all_of:
                all_of.append(predicate)
        requires["all_of"] = all_of
    return patched


def compute_needed_predicates(
    modules_doc: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    depth: int,
    allowed_module_ids: set[str] | None = None,
) -> set[str]:
    modules = modules_doc["modules"]
    needed = set(remaining_targets)
    frontier = set(remaining_targets)
    for _ in range(max(0, depth)):
        new_preds: set[str] = set()
        for module in modules:
            if module.get("module_id") in DEPRECATED_WORKFLOW_MODULE_IDS:
                continue
            if allowed_module_ids and module["module_id"] not in allowed_module_ids:
                continue
            adds = set(module.get("effects", {}).get("adds", []))
            if not adds & frontier:
                continue
            requires = module.get("requires", {})
            new_preds |= (set(requires.get("all_of", [])) - state)
            any_of = set(requires.get("any_of", []))
            if any_of and not (any_of & state):
                new_preds |= any_of
        new_preds -= needed
        if not new_preds:
            break
        needed |= new_preds
        frontier = new_preds
    return needed


def score_module_candidate(
    module: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    needed_predicates: set[str],
    theme: str,
    forbidden_modules: set[str] | None = None,
    forbidden_predicates: set[str] | None = None,
) -> tuple[float, bool]:
    adds = set(module.get("effects", {}).get("adds", []))
    requires = module.get("requires", {})
    executable = preconditions_satisfied(requires, state)
    direct_hits = adds & remaining_targets
    support_hits = adds & (needed_predicates - remaining_targets)
    forbidden_modules = forbidden_modules or set()
    forbidden_predicates = forbidden_predicates or set()
    score = 0.0
    score += 12.0 * len(direct_hits)
    score += 3.0 * len(support_hits)
    if module["module_id"] in forbidden_modules:
        score -= 40.0
    score -= 15.0 * len(adds & forbidden_predicates)
    if module.get("family") == theme:
        score += 0.75
    if executable:
        score += 2.0
    else:
        score -= 50.0 + len(missing_preconditions(requires, state))
    return score, executable


def can_reach_targets_within(
    modules_doc: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    depth: int,
    blocked_modules: set[str],
    allowed_module_ids: set[str] | None = None,
) -> bool:
    if not remaining_targets or remaining_targets <= state:
        return True
    if depth <= 0:
        return False

    visited: set[tuple[frozenset[str], int]] = set()
    frontier: list[tuple[set[str], int]] = [(set(state), depth)]

    while frontier:
        current_state, steps_left = frontier.pop(0)
        if remaining_targets <= current_state:
            return True
        if steps_left <= 0:
            continue

        current_remaining = remaining_targets - current_state
        needed_predicates = compute_needed_predicates(
            modules_doc,
            current_state,
            current_remaining,
            min(2, steps_left),
            allowed_module_ids=allowed_module_ids,
        )

        ranked_next: list[tuple[int, int, str, set[str]]] = []
        for module in modules_doc["modules"]:
            module_id = module["module_id"]
            if module_id in DEPRECATED_WORKFLOW_MODULE_IDS:
                continue
            if allowed_module_ids and module_id not in allowed_module_ids:
                continue
            if module_id in blocked_modules:
                continue
            if not preconditions_satisfied(module.get("requires", {}), current_state):
                continue

            adds = set(module.get("effects", {}).get("adds", []))
            relevant_hits = adds & current_remaining
            support_hits = adds & (needed_predicates - current_remaining)
            if not relevant_hits and not support_hits:
                continue

            next_state = apply_effects(current_state, module)
            if next_state == current_state:
                continue

            ranked_next.append(
                (len(relevant_hits), len(support_hits), module_id, next_state)
            )

        ranked_next.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

        for _, _, _, next_state in ranked_next[:16]:
            key = (frozenset(next_state), steps_left - 1)
            if key in visited:
                continue
            visited.add(key)
            frontier.append((next_state, steps_left - 1))

    return False


def shortlist_candidates(
    modules_doc: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    theme: str,
    candidate_limit: int,
    backward_depth: int,
    failed_modules: set[str],
    successful_modules: list[str],
    remaining_invocations: int,
    allowed_module_ids: set[str] | None = None,
    forbidden_modules: set[str] | None = None,
    forbidden_predicates: set[str] | None = None,
    decoy_quota: int = 0,
    decoy_insert_rank: int = 3,
) -> list[dict[str, Any]]:
    needed_predicates = compute_needed_predicates(
        modules_doc,
        state,
        remaining_targets,
        backward_depth,
        allowed_module_ids=allowed_module_ids,
    )
    ranked_relevant: list[dict[str, Any]] = []
    ranked_fallback: list[dict[str, Any]] = []
    for module in modules_doc["modules"]:
        module_id = module["module_id"]
        if module_id in DEPRECATED_WORKFLOW_MODULE_IDS:
            continue
        if allowed_module_ids and module_id not in allowed_module_ids:
            continue
        if module_id in failed_modules:
            continue
        if module_id in successful_modules:
            continue
        score, executable = score_module_candidate(
            module,
            state,
            remaining_targets,
            needed_predicates,
            theme,
            forbidden_modules=forbidden_modules,
            forbidden_predicates=forbidden_predicates,
        )
        adds = set(module.get("effects", {}).get("adds", []))
        is_relevant = bool(adds & remaining_targets) or bool(adds & (needed_predicates - remaining_targets))
        if not executable and not is_relevant:
            continue
        reachable = True
        if executable:
            next_state = apply_effects(state, module)
            next_remaining = remaining_targets - next_state
            reachable = can_reach_targets_within(
                modules_doc=modules_doc,
                state=next_state,
                remaining_targets=next_remaining,
                depth=max(0, remaining_invocations - 1),
                blocked_modules=set(failed_modules) | set(successful_modules) | {module_id},
                allowed_module_ids=allowed_module_ids,
            )
            if next_remaining and not reachable:
                score -= 100.0
        trace_payload = build_candidate_trace_payload(
            module,
            state,
            remaining_targets,
            needed_predicates,
            theme,
            forbidden_modules=forbidden_modules,
            forbidden_predicates=forbidden_predicates,
            score=score,
            executable=executable,
            reachable=reachable,
        )
        materialized = dict(module)
        materialized["_candidate_trace"] = trace_payload
        bucket = ranked_relevant if is_relevant else ranked_fallback
        bucket.append(
            {
                "score": score,
                "module_id": module_id,
                "executable": executable,
                "reachable": reachable,
                "module": materialized,
            }
        )

    ranked_relevant.sort(
        key=lambda item: (item["reachable"], item["score"], item["executable"], item["module_id"]),
        reverse=True,
    )
    ranked_fallback.sort(
        key=lambda item: (item["reachable"], item["score"], item["executable"], item["module_id"]),
        reverse=True,
    )

    relevant_executable = [item for item in ranked_relevant if item["executable"]]
    fallback_executable = [item for item in ranked_fallback if item["executable"]]
    reachable_relevant_executable = [item for item in relevant_executable if item["reachable"]]
    reachable_fallback_executable = [item for item in fallback_executable if item["reachable"]]

    # Keep non-executable options out of the list, then optionally mix in
    # executable hard negatives so shortcut choices are tested without leaking
    # which candidates are decoys.
    if reachable_relevant_executable:
        ranked = reachable_relevant_executable[:candidate_limit]
        if len(ranked) < candidate_limit:
            ranked.extend(reachable_fallback_executable[: candidate_limit - len(ranked)])
    elif relevant_executable:
        ranked = relevant_executable[:candidate_limit]
        if len(ranked) < candidate_limit:
            ranked.extend(fallback_executable[: candidate_limit - len(ranked)])
    else:
        ranked = ranked_relevant[:candidate_limit]
        if len(ranked) < candidate_limit:
            ranked.extend(ranked_fallback[: candidate_limit - len(ranked)])

    shortlisted = _inject_hard_negative_candidates(
        ranked=ranked,
        ranked_relevant=ranked_relevant,
        ranked_fallback=ranked_fallback,
        candidate_limit=candidate_limit,
        decoy_quota=decoy_quota,
        decoy_insert_rank=decoy_insert_rank,
    )
    for rank, item in enumerate(shortlisted, start=1):
        item["module"]["_candidate_trace"]["rank"] = rank
    return [item["module"] for item in shortlisted]


def _is_hard_negative_candidate(item: dict[str, Any]) -> bool:
    trace = item.get("module", {}).get("_candidate_trace", {}) or {}
    return bool(trace.get("forbidden_module") or trace.get("forbidden_predicate_hits"))


def _inject_hard_negative_candidates(
    ranked: list[dict[str, Any]],
    ranked_relevant: list[dict[str, Any]],
    ranked_fallback: list[dict[str, Any]],
    candidate_limit: int,
    decoy_quota: int,
    decoy_insert_rank: int,
) -> list[dict[str, Any]]:
    shortlisted = list(ranked[:candidate_limit])
    if candidate_limit <= 0 or decoy_quota <= 0:
        return shortlisted

    current_ids = {item["module_id"] for item in shortlisted}
    current_decoys = sum(1 for item in shortlisted if _is_hard_negative_candidate(item))
    needed_decoys = max(0, decoy_quota - current_decoys)
    if needed_decoys <= 0:
        return shortlisted

    decoy_pool: list[dict[str, Any]] = []
    for item in ranked_relevant + ranked_fallback:
        if item["module_id"] in current_ids:
            continue
        if not item.get("executable"):
            continue
        if not _is_hard_negative_candidate(item):
            continue
        decoy_pool.append(item)

    insert_at = max(0, min(candidate_limit - 1, decoy_insert_rank - 1))
    for decoy in decoy_pool[:needed_decoys]:
        if len(shortlisted) >= candidate_limit:
            replace_idx = next(
                (idx for idx in range(len(shortlisted) - 1, -1, -1) if not _is_hard_negative_candidate(shortlisted[idx])),
                None,
            )
            if replace_idx is None:
                break
            removed = shortlisted.pop(replace_idx)
            current_ids.discard(removed["module_id"])
        position = min(insert_at, len(shortlisted))
        shortlisted.insert(position, decoy)
        current_ids.add(decoy["module_id"])

    return shortlisted[:candidate_limit]


def format_requires(requires: dict[str, Any]) -> str:
    chunks = []
    if requires.get("all_of"):
        chunks.append("all:" + ",".join(humanize_predicate(item) for item in requires["all_of"][:4]))
    if requires.get("any_of"):
        chunks.append("any:" + ",".join(humanize_predicate(item) for item in requires["any_of"][:4]))
    if requires.get("none_of"):
        chunks.append("none:" + ",".join(humanize_predicate(item) for item in requires["none_of"][:4]))
    return "; ".join(chunks) or "none"


def humanize_predicate(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(part for part in text.replace("-", "_").split("_") if part)


def humanize_predicates(values: Any) -> list[str]:
    return [
        item for item in (humanize_predicate(value) for value in (values or []))
        if item
    ]


_FORBIDDEN_MODULE_HINT_RE = re.compile(
    r"\s*Do not use these shortcut/decoy modules:\s*[^.]*\.\s*"
)


def sanitize_goal_instruction_for_agent(instruction: Any) -> str:
    text = str(instruction or "")
    text = _FORBIDDEN_MODULE_HINT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    chunks = [chunk.strip() for chunk in re.split(r"(?<=\.)\s+", text) if chunk.strip()]
    seen: set[str] = set()
    deduped: list[str] = []
    for chunk in chunks:
        key = chunk.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return " ".join(deduped)


def semantic_visible_constraints(visible: dict[str, Any]) -> dict[str, Any]:
    internal_keys = {
        "forbidden_modules",
        "required_modules",
        "required_module_sequence",
        "route_hint",
        "supporting_initial_state",
    }
    result = {
        key: value
        for key, value in dict(visible or {}).items()
        if key not in internal_keys
    }
    if "preferred_outcomes" in result:
        result["preferred_outcomes"] = humanize_predicates(result.get("preferred_outcomes"))
    if "must_avoid" in result:
        result["must_avoid"] = humanize_predicates(result.get("must_avoid"))
    return result


def render_module_prompt(
    goal: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    candidates: list[dict[str, Any]],
    successful_modules: list[str],
    failed_modules: set[str],
) -> str:
    lines = [
        f"THEME: {goal['theme']}",
        f"GOAL: {sanitize_goal_instruction_for_agent(goal.get('instruction', ''))}",
        f"VISIBLE_CONSTRAINTS: {json.dumps(semantic_visible_constraints(goal.get('visible_constraints', {})), ensure_ascii=False)}",
        f"CURRENT_STATE: {json.dumps(humanize_predicates(sorted(state)), ensure_ascii=False)}",
        f"TARGET_OUTCOMES: {json.dumps(humanize_predicates(goal.get('target_state', [])), ensure_ascii=False)}",
        f"REMAINING_OUTCOMES: {json.dumps(humanize_predicates(sorted(remaining_targets)), ensure_ascii=False)}",
        f"SUCCESSFUL_MODULES: {json.dumps(successful_modules, ensure_ascii=False)}",
        f"FAILED_MODULES_TO_AVOID: {json.dumps(sorted(failed_modules), ensure_ascii=False)}",
        "SELECTION_GUIDANCE: use the visible goal, visible constraints, current state, remaining outcomes, dependency information, preconditions, and effects; list order is not an answer key.",
        "",
        "CANDIDATE_MODULES:",
    ]
    for module in candidates:
        lines.append(
            f"- {module['module_id']} | {module.get('name', module['module_id'])} | "
            f"requires: {format_requires(module.get('requires', {}))} | "
            f"outcomes: {', '.join(humanize_predicates(module.get('effects', {}).get('adds', [])[:6])) or 'none'}"
        )
    lines += [
        "",
        "Return exactly one token: MODULE_ID or DONE",
        "Only return DONE when all REMAINING_OUTCOMES are already satisfied or when there is truly no candidate that can advance the goal.",
    ]
    return "\n".join(lines)


def parse_module_choice(raw: str, candidate_ids: set[str]) -> tuple[Optional[str], str]:
    text = (raw or "").strip()
    if not text:
        return None, "empty_output"
    first_line = text.splitlines()[0].strip()
    if first_line == "DONE":
        return "DONE", "first_line_done"
    if first_line in candidate_ids:
        return first_line, "first_line_exact"
    for token in first_line.replace(",", " ").split():
        token = token.strip()
        if token in candidate_ids or token == "DONE":
            return token, "first_line_token"
    for candidate in candidate_ids:
        if candidate in text:
            return candidate, "substring_candidate"
    if "DONE" in text:
        return "DONE", "substring_done"
    return None, "unparsed_output"


def is_forbidden_candidate(module: dict[str, Any]) -> bool:
    trace = module.get("_candidate_trace", {}) if isinstance(module, dict) else {}
    return bool(trace.get("forbidden_module") or trace.get("forbidden_predicate_hits"))


def first_non_forbidden_candidate(candidates: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for candidate in candidates:
        if not is_forbidden_candidate(candidate):
            return candidate
    return None


def select_next_module(
    client: Any,
    goal: dict[str, Any],
    state: set[str],
    candidates: list[dict[str, Any]],
    successful_modules: list[str],
    failed_modules: set[str],
    temperature: float,
    max_tokens: int,
) -> tuple[str, str, dict[str, Any]]:
    remaining_targets = set(goal.get("target_state", [])) - state
    if not remaining_targets:
        return "DONE", "target_already_satisfied", {
            "decision_source": "llm",
            "parsed_choice": "DONE",
            "parser_match_reason": "target_already_satisfied",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": len(candidates),
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    candidate_ids = {item["module_id"] for item in candidates}
    if not candidate_ids:
        return "DONE", "no_candidates", {
            "decision_source": "llm",
            "parsed_choice": "DONE",
            "parser_match_reason": "no_candidates",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": 0,
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    prompt = render_module_prompt(goal, state, remaining_targets, candidates, successful_modules, failed_modules)
    messages = [
        {"role": "system", "content": MODULE_CHOOSER_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    raw = client.sample_messages(messages, num_samples=1, temperature=temperature, max_tokens=max_tokens)[0]
    parsed, parse_reason = parse_module_choice(raw, candidate_ids)
    meta = {
        "decision_source": "llm",
        "parsed_choice": parsed,
        "parser_match_reason": parse_reason,
        "fallback_reason": "",
        "termination_override": False,
        "candidate_count": len(candidates),
        "planner_prompt": prompt,
        "chosen_module_id": "",
    }
    if parsed == "DONE" and remaining_targets and candidates:
        # Do not allow the planner to terminate while the goal still has unmet targets
        # and there is at least one non-forbidden executable candidate left to try.
        fallback_candidate = first_non_forbidden_candidate(candidates)
        if fallback_candidate is None:
            meta["chosen_module_id"] = "DONE"
            meta["fallback_reason"] = "honor_done_no_non_forbidden_candidates"
            return "DONE", raw, meta
        meta["fallback_reason"] = "override_done_with_remaining_targets"
        meta["termination_override"] = True
        meta["chosen_module_id"] = fallback_candidate["module_id"]
        return fallback_candidate["module_id"], raw, meta
    if parsed is not None:
        meta["chosen_module_id"] = parsed
        return parsed, raw, meta
    fallback_candidate = first_non_forbidden_candidate(candidates)
    if fallback_candidate is None:
        meta["fallback_reason"] = "unparsed_output_no_non_forbidden_candidates"
        meta["chosen_module_id"] = "DONE"
        return "DONE", raw, meta
    meta["fallback_reason"] = "unparsed_output_fallback_to_top_candidate"
    meta["chosen_module_id"] = fallback_candidate["module_id"]
    return fallback_candidate["module_id"], raw, meta


def choose_reference_next_module(
    oracle: dict[str, Any],
    successful_modules: list[str],
    successful_invocations: set[str],
) -> tuple[str, str, dict[str, Any]]:
    path = oracle.get("success_paths", [])[0]
    invocations_by_id = {
        invocation.get("invocation_id"): invocation
        for invocation in oracle.get("reference_invocations", [])
        if invocation.get("invocation_id")
    }

    reference_invocation_ids = [
        invocation_id
        for invocation_id in path.get("reference_invocation_ids", [])
        if invocation_id in invocations_by_id
    ]
    if reference_invocation_ids:
        for invocation_id in reference_invocation_ids:
            if invocation_id not in successful_invocations:
                module_id = invocations_by_id[invocation_id].get("module_id", "")
                return module_id, f"reference:{path['path_id']}:{invocation_id}", {
                    "decision_source": "reference",
                    "parsed_choice": module_id,
                    "parser_match_reason": "reference_next_invocation",
                    "fallback_reason": "",
                    "termination_override": False,
                    "candidate_count": 0,
                    "planner_prompt": "",
                    "chosen_module_id": module_id,
                    "reference_path_id": path.get("path_id", ""),
                    "reference_invocation_id": invocation_id,
                }
        return "DONE", f"reference:{path['path_id']}", {
            "decision_source": "reference",
            "parsed_choice": "DONE",
            "parser_match_reason": "reference_path_complete",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": 0,
            "planner_prompt": "",
            "chosen_module_id": "DONE",
            "reference_path_id": path.get("path_id", ""),
            "reference_invocation_id": "",
        }

    required = path.get("required_modules", [])
    for module_id in required:
        if module_id not in successful_modules:
            return module_id, f"reference:{path['path_id']}", {
                "decision_source": "reference",
                "parsed_choice": module_id,
                "parser_match_reason": "reference_next_required_module",
                "fallback_reason": "",
                "termination_override": False,
                "candidate_count": 0,
                "planner_prompt": "",
                "chosen_module_id": module_id,
                "reference_path_id": path.get("path_id", ""),
                "reference_invocation_id": "",
            }
    return "DONE", f"reference:{path['path_id']}", {
        "decision_source": "reference",
        "parsed_choice": "DONE",
        "parser_match_reason": "reference_path_complete",
        "fallback_reason": "",
        "termination_override": False,
        "candidate_count": 0,
        "planner_prompt": "",
        "chosen_module_id": "DONE",
        "reference_path_id": path.get("path_id", ""),
        "reference_invocation_id": "",
    }


def choose_heuristic_next_module(
    goal: dict[str, Any],
    state: set[str],
    candidates: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    remaining_targets = set(goal.get("target_state", [])) - state
    if not remaining_targets:
        return "DONE", "heuristic:target_already_satisfied", {
            "decision_source": "heuristic",
            "parsed_choice": "DONE",
            "parser_match_reason": "target_already_satisfied",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": len(candidates),
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    if not candidates:
        return "DONE", "heuristic:no_candidates", {
            "decision_source": "heuristic",
            "parsed_choice": "DONE",
            "parser_match_reason": "no_candidates",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": 0,
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    return candidates[0]["module_id"], "heuristic:top_ranked_candidate", {
        "decision_source": "heuristic",
        "parsed_choice": candidates[0]["module_id"],
        "parser_match_reason": "top_ranked_candidate",
        "fallback_reason": "",
        "termination_override": False,
        "candidate_count": len(candidates),
        "planner_prompt": "",
        "chosen_module_id": candidates[0]["module_id"],
    }


_HOUSEKEEPING_SERVICE_TIME_ALIASES: dict[str, str] = {
    "09:30": "09:00",
    "14:30": "15:00",
}

_DEVICE_PROFILE_ALIASES: dict[str, str] = {
    "cool white": "daylight",
    "cool_white": "daylight",
    "cool-white": "daylight",
}


def _normalize_housekeeping_service_type(value: Any) -> str:
    raw = str(value or "").strip()
    aliases = {
        "standard_cleaning": "regular_cleaning",
        "standard cleaning": "regular_cleaning",
        "regular cleaning": "regular_cleaning",
    }
    return aliases.get(raw.lower(), raw)


def _normalize_housekeeping_service_time(value: Any) -> str:
    raw = str(value or "").strip()
    return _HOUSEKEEPING_SERVICE_TIME_ALIASES.get(raw, raw)


def _normalize_device_profile(value: Any) -> str:
    raw = str(value or "").strip()
    return _DEVICE_PROFILE_ALIASES.get(raw.lower(), raw)


def _normalize_firmware_problem(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Firmware update failed"
    if "firmware update failed" in raw.lower():
        return raw
    return f"Firmware update failed: {raw}"


_UTILITY_TYPE_LABELS = {
    "all": "all bills",
    "electricity": "electricity bills",
    "water": "water bills",
    "gas": "gas bills",
}


def _normalize_utility_types(value: Any) -> list[str]:
    if value is None or value == "":
        raw_items: list[Any] = []
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                raw_items = parsed if isinstance(parsed, list) else [stripped]
            except Exception:
                raw_items = [stripped]
        else:
            raw_items = re.split(r",|/|\band\b|和|、", stripped)
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    utilities: list[str] = []
    for item in raw_items:
        key = str(item or "").strip().lower().replace(" bill", "").replace(" bills", "")
        if key in _UTILITY_TYPE_LABELS and key not in utilities:
            utilities.append(key)
    return utilities or ["electricity", "water"]


def _utility_type_label(value: str) -> str:
    return _UTILITY_TYPE_LABELS.get(value, value)


_CERTIFICATE_NAMES = {
    "Certified Python Expert",
    "Certified Data Analyst",
    "Certified Operations Specialist",
}


def _normalize_certificate_names(value: Any, fallback: list[str] | None = None) -> list[str]:
    if value is None or value == "":
        raw_items: list[Any] = []
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped in _CERTIFICATE_NAMES:
            raw_items = [stripped]
        elif stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                raw_items = parsed if isinstance(parsed, list) else [stripped]
            except Exception:
                raw_items = [stripped]
        else:
            raw_items = re.split(r",|\band then\b|\band\b|和|、", stripped)
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    certificates: list[str] = []
    for item in raw_items:
        cert = str(item or "").strip()
        if cert in _CERTIFICATE_NAMES and cert not in certificates:
            certificates.append(cert)
    return certificates or list(fallback or ["Certified Data Analyst", "Certified Operations Specialist"])


def _normalize_balance_sequence(value: Any) -> list[str]:
    allowed = {"checking", "savings", "total"}
    if value is None or value == "":
        raw_items: list[Any] = []
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                raw_items = parsed if isinstance(parsed, list) else [stripped]
            except Exception:
                raw_items = [stripped]
        else:
            raw_items = re.split(r",|/|\band then\b|\band\b|和|、", stripped)
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    sequence: list[str] = []
    for item in raw_items:
        view = str(item or "").strip().lower()
        if view in allowed and view not in sequence:
            sequence.append(view)
    return sequence or ["checking", "savings", "total"]


def _password_reset_new_password_for_username(username: Any) -> str:
    user = str(username or "").strip().lower()
    if user == "byteblaze":
        return "ByteBlaze#2026"
    return "SafePass!2026"


def _password_reset_code_for_username(username: Any) -> str:
    user = str(username or "").strip().lower()
    if user == "byteblaze":
        return "7394"
    if user == "demo_user":
        return "1234"
    return "6428"


def _normalize_binding_parameters(module_id: str, parameter_values: dict[str, Any]) -> dict[str, Any]:
    params = dict(parameter_values or {})
    if module_id == "MODULE_FIND_HOME":
        params["selected_address"] = str(
            params.get("selected_address") or property_address_for_id(params.get("propertyId"))
        ).strip()
        params.setdefault("source_id", "home-search-downtown-ready")
        params.setdefault("source_status", "ready")
        params.setdefault("source_review_code", "HOME-2600-AREA")
    if module_id == "MODULE_HOUSEKEEPING_BOOKING":
        if "service_type" in params:
            params["service_type"] = _normalize_housekeeping_service_type(params["service_type"])
        if "service_time" in params:
            params["service_time"] = _normalize_housekeeping_service_time(params["service_time"])
    if module_id in {"MODULE_CAMERA_CHECK", "MODULE_THERMOSTAT_SCHEDULE", "MODULE_SMART_BULB_SETUP"}:
        if "color" in params:
            params["color"] = _normalize_device_profile(params["color"])
    if module_id == "MODULE_FIRMWARE_UPDATE" and "problem" in params:
        params["problem"] = _normalize_firmware_problem(params["problem"])
    if module_id == "MODULE_PAPER_SUBMISSION":
        title = str(params.get("title") or "the paper").strip()
        default_abstract = f"Validates {title} with staged module selection and atomic field checks."
        current_abstract = str(params.get("abstract") or "").strip()
        if not current_abstract or ("with staged module selection and atomic field checks." in current_abstract and title not in current_abstract):
            params["abstract"] = default_abstract
        else:
            params["abstract"] = current_abstract
        params.setdefault("track", "short-paper")
        params["source_draft_id"] = _paper_draft_id(title)
    if module_id == "MODULE_BILLING_REVIEW":
        params["utility_types"] = _normalize_utility_types(params.get("utility_types"))
        params.setdefault("higher_pending_total_type", "electricity")
        params.setdefault("largest_water_bill_id", "BILL-WA-2026-01")
    if module_id == "MODULE_RECEIPT_ARCHIVING":
        file_name = str(params.get("file_path") or params.get("fileName") or "taxi_invoice_march.pdf").strip()
        source = _receipt_source_for_file(file_name)
        params["file_path"] = file_name
        params["source_doc_id"] = source["id"]
        params["vendor"] = source["vendor"]
        params["document_date"] = source["document_date"]
        params["amount"] = source["amount"]
        params["archive_code"] = source["archive_code"]
        params["retention_label"] = source["retention_label"]
    if module_id == "MODULE_CALENDAR_AGGREGATION":
        title = str(params.get("personal_title") or params.get("title") or params.get("work_title") or "Dentist Follow-up").strip()
        date = str(params.get("date") or "2026-01-16").strip()
        time_value = str(params.get("time") or "15:30").strip()
        event_type = str(params.get("event_type") or "personal").strip()
        source = _calendar_source_for_event(title, date, time_value, event_type, params.get("description"))
        params["source_calendar_id"] = source["id"]
        params["personal_title"] = source["title"]
        params["title"] = source["title"]
        params["date"] = source["date"]
        params["time"] = source["time"]
        params["event_type"] = source["type"]
        params["description"] = source["description"]
        params["source_code"] = source["source_code"]
    if module_id == "MODULE_EMAIL_CALENDAR":
        params.setdefault("event_source_code", "KC-0112-0930")
    if module_id in {"MODULE_EVENT_TICKETS", "MODULE_MOVIE_TICKETS"}:
        default_event_id = "EVT-101" if module_id == "MODULE_MOVIE_TICKETS" else "EVT-103"
        default_purchase_code = "EVT-CAMPUS-50" if module_id == "MODULE_MOVIE_TICKETS" else "EVT-FILM-30"
        params.setdefault("event_id", default_event_id)
        params.setdefault("purchase_code", default_purchase_code)
        params.setdefault("source_id", "event-ticket-request-active")
        params.setdefault("quantity", "1")
        params.setdefault("seat_section", "General Admission")
        params.setdefault("transfer_code", "TRF-SAMIRA-27")
        recipient_id = str(params.get("recipient_id") or "").strip()
        if recipient_id:
            params.setdefault("recipient_name", _EVENT_TRANSFER_RECIPIENT_NAMES.get(recipient_id, recipient_id))
    if module_id == "MODULE_SUBSCRIPTION_REFUND":
        subscription_id = str(params.get("subscription_id") or "SUB-8821").strip()
        params.setdefault("refund_intake_code", "REF-SUB-8821" if subscription_id == "SUB-8821" else "REF-SUB-9932")
        params.setdefault("expected_refund", "10.0" if subscription_id == "SUB-9932" else "133.33")
    if module_id == "MODULE_CANCEL_SUBSCRIPTION":
        params.setdefault("cancellation_code", "CANCEL-SUB-001")
        params.setdefault("effective_date", "2026-02-01")
    if module_id == "MODULE_INSURANCE_POLICY":
        params.setdefault("plan_id", "PLAN-B")
        params.setdefault("monthly_premium", "200")
        params.setdefault("waiting_period", "14 days")
    if module_id == "MODULE_PASSWORD_RESET_REQUEST":
        username = str(params.get("username") or "demo_user").strip()
        params.setdefault("channel", "sms")
        if username.lower() == "byteblaze":
            params.setdefault("request_ticket", "REC-BYTE-SMS")
        else:
            params.setdefault("request_ticket", "REC-DEMO-SMS")
        params.setdefault("code", _password_reset_code_for_username(username))
        params.setdefault("source_id", "recovery-request-active")
        params.setdefault("new_password", _password_reset_new_password_for_username(username))
    if module_id == "MODULE_PASSWORD_RESET_COMPLETION":
        username = str(params.get("username") or "demo_user").strip()
        params.setdefault("channel", "sms")
        if username.lower() == "byteblaze":
            params.setdefault("request_ticket", "REC-BYTE-SMS")
        else:
            params.setdefault("request_ticket", "REC-DEMO-SMS")
        params.setdefault("code", _password_reset_code_for_username(username))
        params.setdefault("source_id", "recovery-request-active")
        params.setdefault("new_password", _password_reset_new_password_for_username(username))
    if module_id == "MODULE_PASSWORD_RECOVERY_E2E":
        username = str(params.get("username") or "byteblaze").strip()
        params.setdefault("channel", "sms")
        if username.lower() == "byteblaze":
            params.setdefault("request_ticket", "REC-BYTE-SMS")
        else:
            params.setdefault("request_ticket", "REC-DEMO-SMS")
        params.setdefault("code", _password_reset_code_for_username(username))
        params.setdefault("source_id", "recovery-request-active")
        params.setdefault("new_password", _password_reset_new_password_for_username(username))
    if module_id == "MODULE_BANK_OPENING":
        params["applicant_id"] = _bank_applicant_id(params.get("fullname") or "Alex Chen")
        derived_verification_code = _bank_applicant_verification_code(params["applicant_id"], params.get("phone") or "555-0102")
        default_verification_code = _bank_applicant_verification_code("applicant-alex", "555-0102")
        if not params.get("verification_code") or str(params.get("verification_code")).strip() == default_verification_code:
            params["verification_code"] = derived_verification_code
    if module_id == "MODULE_LEASE_CONTRACT_REGISTRATION":
        params.setdefault("source_contract_id", "lease-contract-active")
        params.setdefault("address", "88 River Rd, Springfield")
        params.setdefault("deposit", "3500")
        params.setdefault("packet_code", "LEASE-CTR-2101")
    if module_id == "MODULE_UTILITY_SETUP":
        params.setdefault("source_id", "utility-source-active")
        params.setdefault("payee", "City Utilities")
        params.setdefault("account_number", "UTIL-7788")
        params.setdefault("monthly_cap", "260")
        params.setdefault("activation_code", "UTIL-ACT-7788")
        params.setdefault("services", ["electricity", "water", "broadband"])
        params.setdefault("plans", {"electricity": "standard", "water": "standard", "broadband": "postpaid-auto"})
    if module_id == "MODULE_AIRPORT_TRANSFER":
        params.setdefault("source_request_id", "transfer-request-active")
        params.setdefault("pickup_time", "06:40")
        params.setdefault("pickup_terminal", "T2 Departures")
        params.setdefault("party_size", "1")
    if module_id == "MODULE_MOBILE_PLAN_SIGNUP":
        params.setdefault("source_id", "mobile-signup-request")
        params.setdefault("email", _mobile_signup_email_for_name(params.get("user_name")))
        params.setdefault("signup_code", "MOB-NEW-742")
        if "plan" in params:
            params["plan"] = str(params.get("plan") or "unlimited").strip().lower()
    if module_id == "MODULE_BILL_AGGREGATION":
        params.setdefault("source_id", "bill-source-active")
        params.setdefault("verification_code", "BILL-7710")
    if module_id == "MODULE_ADDRESS_CHANGE":
        params.setdefault("proof_code", "ADDR-8891")
    if module_id == "MODULE_ADDRESS_PROOF":
        params.setdefault("verification_code", "ADDR-VERIFY-DEC")
        params.setdefault("source_id", "proof-intake-current")
    if module_id in {"MODULE_PERMIT_APP", "MODULE_PARKING_PERMIT_APPLICATION"}:
        plate = params.get("vehicle_plate", params.get("plate_number", "C-55021"))
        params.setdefault("intake_code", _parking_intake_code(plate))
    if module_id in {"MODULE_PERMIT_RENEWAL", "MODULE_RENEW_PERMIT"}:
        params.setdefault("renewal_code", _renewal_notice_code(params.get("new_expiry")))
    if module_id == "MODULE_BUDGET_LIMIT_UPDATE":
        params.setdefault("source_id", "budget-review-active")
        category_for_code = str(params.get("category") or "utilities")
        params.setdefault(
            "approval_code",
            {"food": "BUD-FOOD-019", "transport": "BUD-TRN-150", "utilities": "BUD-UTIL-042"}.get(
                category_for_code, "BUD-UTIL-042"
            ),
        )
    if module_id in {"MODULE_TAX_PREPARATION", "MODULE_FILE_TAXES"}:
        params.setdefault("source_id", "tax-source-active")
        params.setdefault("reference_code", "TAX-W2-2025" if module_id == "MODULE_FILE_TAXES" else "TAX-OFF-150")
    if module_id == "MODULE_ROOMMATE_EXPENSE_SPLIT":
        params.setdefault("source_id", "split-source-active")
        params.setdefault("settlement_code", "SETTLE-NOV-42")
    if module_id in {"MODULE_CHARITY_DONATION", "MODULE_GIFT_POOLING"}:
        params.setdefault("source_id", "donation-source-active")
        params.setdefault("campaign_code", "GIFT-TEAM-2025" if module_id == "MODULE_GIFT_POOLING" else "DON-LOCAL-2025")
    if module_id == "MODULE_RSVP_EVENT":
        params.setdefault("source_id", "group-source-active")
        params.setdefault("group_id", "GRP-002")
        params.setdefault("access_code", "RSVP-TECH-27")
    if module_id == "MODULE_CONFERENCE_REG":
        source = _conference_source_for_registration(
            params.get("registration_id") or params.get("source_registration_id"),
            params.get("event"),
        )
        params["source_registration_id"] = source["registration_id"]
        params["registration_id"] = source["registration_id"]
        params.setdefault("event", source["event"])
        params.setdefault("report_id", source["report_id"])
        params.setdefault("total_amount", source["total_amount"])
        params.setdefault("linked_pnr", source["linked_pnr"])
        params.setdefault("description", source["description"])
        params.setdefault("expense_type", source.get("expense_type", "conference_registration"))
        params.setdefault("receipt_bundle", source.get("receipt_bundle", "RB-2201-CONF-REG"))
    if module_id == "MODULE_MOBILE_PLAN_SWITCH":
        plan = str(params.get("planId") or "pro").strip().lower()
        if plan == "unlimited":
            plan = "pro"
        params["planId"] = plan
        params.setdefault("switch_code", "MOB-PRO-219")
        params.setdefault("effective_date", "2026-02-01")
        params.setdefault("usage_reading", "12.5 GB")
    if module_id == "MODULE_JOB_SEARCH":
        subject = str(params.get("subject") or "Job Application Follow-up").strip()
        sender = str(params.get("sender") or "recruiter@example.com").strip()
        params["subject"] = subject
        params["sender"] = sender
        params["source_email_id"] = _job_search_source_email_id(subject, sender)
    if module_id == "MODULE_UPDATE_LINKEDIN":
        subject = str(params.get("subject") or "LinkedIn Profile Update").strip()
        sender = str(params.get("sender") or "notifications@linkedin.com").strip()
        params["subject"] = subject
        params["sender"] = sender
        params.setdefault("summary", "Updated headline and project portfolio")
        params.setdefault("priority", "normal")
        params.setdefault("follow_up_date", "2026-01-16")
        params["source_email_id"] = _linkedin_source_email_id(subject, sender)
    if module_id in {"MODULE_DOWNLOAD_CERT", "MODULE_SKILL_CERTIFICATION"}:
        params.setdefault("cert_plan_id", "cert-plan-active")
        params.setdefault("plan_code", "CERT-OPS-SEQ-42")
        params.setdefault("eligibility_code", "ELIG-OPS-2025")
        if "certificate_names" in params:
            params["certificate_names"] = _normalize_certificate_names(params.get("certificate_names"))
        else:
            fallback = None
            if params.get("certificate_name"):
                fallback = [str(params.get("certificate_name"))]
            params["certificate_names"] = _normalize_certificate_names(None, fallback=fallback)
    if module_id == "MODULE_CHECK_BALANCE":
        params["account_sequence"] = _normalize_balance_sequence(params.get("account_sequence"))
        params["account_type"] = params["account_sequence"][-1]
    return params


def _format_binding_scalar(value: Any) -> str:
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


def _mobile_signup_email_for_name(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text or text == "test user":
        return "test@example.com"
    parts = re.findall(r"[a-z0-9]+", text)
    if not parts:
        return "test@example.com"
    return ".".join(parts[:3]) + "@example.com"


def _dependency_update_fields(updates: list[dict[str, Any]]) -> set[str]:
    return {
        str(update.get("target_field") or "").strip()
        for update in updates or []
        if str(update.get("target_field") or "").strip()
    }


def _dependency_masked_description(
    module_id: str,
    description: str,
    parameter_values: dict[str, Any],
    updates: list[dict[str, Any]],
) -> str:
    fields = _dependency_update_fields(updates)
    if not fields:
        return description

    params = dict(parameter_values or {})
    if fields & {"address", "new_address"}:
        if module_id == "MODULE_BANK_OPENING":
            fullname = _format_binding_scalar(params.get("fullname", "the applicant"))
            return (
                f"Review the active applicant profile for {fullname}, then open a new bank account using the reviewed phone and "
                "the applicant identity code plus the current residence address selected earlier in this workflow, and enable 2FA before finishing."
            )
        if module_id == "MODULE_MOBILE_PLAN_SIGNUP":
            return (
                "Review the newcomer mobile recommendation, subscribe using the recommended "
                "plan, contact, recommendation code, and the residence address selected earlier in this workflow, then finish on the active mobile account page."
            )
        if module_id == "MODULE_UTILITY_SETUP":
            return (
                "Review the utility activation notice, then set up utilities for the residence address "
                "selected earlier in this workflow using the notice details and activation code."
            )
        if module_id == "MODULE_ADDRESS_CHANGE":
            return (
                "Submit an address change to the residence address selected earlier in this workflow "
                "using the ZIP code and proof reference code shown in the checklist."
            )
        if module_id == "MODULE_VEHICLE_ADDRESS_UPDATE":
            vehicle_id = str(params.get("vehicle_id") or "V-8821").strip()
            return (
                f"Use the matching Vehicle Address Notice for vehicle {vehicle_id}, then update the record "
                "with the residence address selected earlier in this workflow and the notice insurance instruction."
            )

    if "course_id" in fields and module_id == "MODULE_SUBMIT_ASSIGNMENT":
        assignment = str(params.get("assignment_title") or "the required assignment").strip()
        file_name = str(params.get("file_name") or "the assignment attachment").strip()
        note = str(params.get("submission_note") or "the required submission note").strip()
        return (
            f"Submit {assignment} for the course enrolled earlier in this workflow using attachment {file_name}. "
            f"Add note: {note} Confirm the course integrity policy."
        )

    if "appointment_id" in fields and module_id == "MODULE_MEDICAL_CLAIM":
        return (
            "Review the active claim intake record, cross-check it with the care context, manually enter the claim fields, "
            "then submit that claim using the policy and amount shown there, but use the appointment booked earlier in this workflow as the appointment field."
        )

    if "order_id" in fields:
        if module_id == "MODULE_CONTACT_SUPPORT":
            issue_type = str(params.get("issue_type") or "the support issue").strip()
            return (
                "Review the active logistics intake, then open a matching support ticket for the order used earlier "
                f"in this workflow with issue type {issue_type} and the intake details shown there."
            )
        if module_id == "MODULE_CUSTOMER_SERVICE":
            return (
                "Review the active support briefing, ask customer service to check the current status for the order "
                "used earlier in this workflow, then send the required follow-up escalation using the briefing deadline, reason, and code."
            )
        if module_id == "MODULE_LOGISTICS_FIX":
            issue_type = str(params.get("issue_type") or "the logistics issue").strip()
            return (
                "Review the active logistics intake, then open a matching logistics ticket for the order used earlier "
                f"in this workflow with issue type {issue_type}, routing queue, description, and intake code."
            )
        if module_id == "MODULE_RETURN":
            reason = str(params.get("reason") or "the authorized return reason").strip()
            return (
                "Review the active return authorization, then submit the return request for the order used earlier "
                f"in this workflow with reason {reason}, refund method, and authorization code from the source."
            )
        if module_id == "MODULE_WARRANTY_CLAIM":
            claim_type = str(params.get("claim_type") or "repair").strip()
            serial = str(params.get("serial") or "the covered product").strip()
            issue = str(params.get("issue") or "the reported defect").strip()
            proof_file = str(params.get("proof_file") or "the supporting proof file").strip()
            return (
                f"Review the eligible warranty source, then manually enter a {claim_type} warranty claim for serial {serial} from the order used in the "
                f"earlier support or logistics step. Use issue description {issue}, attach proof file {proof_file}, "
                "confirm the product is within warranty terms, and submit the claim."
            )

    bill_fields = fields & {"payee", "account_number"}
    if bill_fields and module_id in {"MODULE_AUTOPAY", "MODULE_COMPLEX_AUTOPAY"}:
        payment_day = str(params.get("payment_day") or "").strip()
        day_clause = " Include the required payment day from the active instruction." if payment_day else ""
        return (
            "Review the active autopay instruction, then enable autopay using the billing provider and account carried "
            "from the bill source reviewed earlier in this workflow, plus the monthly limit and authorization code shown in the instruction."
            + day_clause
        )

    data_request_fields = fields & {"request_type", "platform", "data_scope", "reason", "contact_email"}
    if data_request_fields and module_id == "MODULE_DOWNLOAD_DATA":
        return (
            "Prepare and download the export package from the export request created earlier in this "
            "workflow. Review the carried request scope and contact details before downloading."
        )

    if "pnr" in fields and module_id == "MODULE_EXPENSE_REPORT":
        return (
            "Review the matching Travel Reimbursement Request on the expense page, then manually submit "
            "the report using the request's report ID, amount, PNR, description, expense type, and receipt "
            "bundle code. Confirm the source match before submitting."
        )

    reset_fields = fields & {"username", "code", "new_password"}
    if reset_fields and module_id == "MODULE_PASSWORD_RESET_COMPLETION":
        account_ref = "the account used in the earlier password reset request"
        code_ref = (
            "first open Mobile.local messages and read the numeric verification code in the latest Security "
            "message, then return to Security.local reset-password page and enter that observed number in "
            "the Verification Code field"
        )
        if reset_fields == {"username"}:
            code_ref = (
                "first open Mobile.local messages and read the requested numeric verification code, then "
                "enter that observed number in the Security.local Verification Code field"
            )
        elif reset_fields == {"code"}:
            account_ref = str(params.get("username") or "the target account").strip()
        return (
            f"Complete account recovery for {account_ref} by using {code_ref} and setting the new password "
            "to the approved value shown in the earlier recovery request."
        )

    return description


def _normalize_binding_description(module_id: str, description: str, parameter_values: dict[str, Any]) -> str:
    params = dict(parameter_values or {})
    if module_id == "MODULE_HEALTH_PLAN_ACTIVATION":
        return (
            "Review the Standard and Premium health plan options, activate the Premium Health Plan, type "
            "Premium Health Plan as the confirmation phrase, confirm that the listed benefits were reviewed, "
            "and confirm the plan."
        )
    if module_id == "MODULE_PASSWORD_MANAGER":
        return (
            "Review the credential request, load it into the add-credential form, use the request fields, "
            "confirm the request match, then review the credential before saving."
        )
    if module_id == "MODULE_MEDICAL_CLAIM":
        return (
            "Review the active claim intake record, cross-check it against the care context and policy details, manually enter the intake fields, "
            "then submit the insurance claim using the intake's claim ID, appointment ID, policy ID, and amount."
        )
    if module_id == "MODULE_DATA_DELETION":
        params = dict(parameter_values or {})
        request_type = _format_binding_scalar(params.get("request_type") or "export")
        platform = _format_binding_scalar(params.get("platform") or "Facebook")
        data_scope = _format_binding_scalar(params.get("data_scope") or "posts, photos, messages")
        reason = _format_binding_scalar(params.get("reason") or "Download archive before account cleanup")
        contact_email = _format_binding_scalar(params.get("contact_email") or "privacy.user@example.com")
        return (
            f"Submit a data {request_type} request to {platform} covering {data_scope}, "
            f"use reason {reason}, contact email {contact_email}, and confirm identity ownership."
        )
    if module_id == "MODULE_DOWNLOAD_DATA":
        params = dict(parameter_values or {})
        platform = _format_binding_scalar(params.get("platform") or "NebulaCloud")
        return (
            f"Prepare and download the export package for the matching {platform} export request. "
            "Review the request scope and contact details before downloading."
        )
    if module_id == "MODULE_WARRANTY_CLAIM":
        return (
            "Review the eligible warranty claim source, manually enter its serial, order, claim type, issue, "
            "and proof file, confirm the product is within warranty terms, and submit the claim."
        )
    if module_id == "MODULE_SUBMIT_ASSIGNMENT":
        params = dict(parameter_values or {})
        course_id = _format_binding_scalar(params.get("course_id") or "ML202")
        assignment = _format_binding_scalar(params.get("assignment_title") or "ML202 Project Draft")
        file_name = _format_binding_scalar(params.get("file_name") or "ml202_project_draft.pdf")
        note = _format_binding_scalar(params.get("submission_note") or "Assignment submitted before review time.")
        return (
            f"Submit {assignment} for course {course_id} using attachment {file_name}. "
            f"Add note: {note} Confirm the course integrity policy."
        )
    if module_id == "MODULE_SUPPLY_DISRUPTION":
        params = dict(parameter_values or {})
        action = str(params.get("action") or "cancel_order").strip().lower()
        return _SUPPLY_DISRUPTION_GOALS.get(action, _SUPPLY_DISRUPTION_GOALS["cancel_order"])
    if module_id == "MODULE_SMART_METER":
        params = dict(parameter_values or {})
        reading = _format_binding_scalar(params.get("reading") or "13020.75")
        source_label = _smart_meter_source_label(params.get("source") or "outdoor_photo")
        return (
            f"Submit a smart meter reading of {reading} kWh using the {source_label} source, "
            "copy the meter ID, billing window, and evidence code from the reviewed evidence, "
            "review the confirmation details, and confirm the reading."
        )
    if module_id == "MODULE_CUSTOMER_SERVICE":
        return (
            "Review the active support briefing, ask customer service to check the current status for the briefing order, "
            "then after the bot returns the order status send a follow-up escalation using the briefing deadline, "
            "escalation reason, and escalation code."
        )
    if module_id == "MODULE_EMAIL_CALENDAR":
        return (
            "Search the work inbox for the relevant kickoff invitation email, open it to verify "
            "the event details, then add the matching calendar event using only the details and "
            "confirmation code shown in that email."
        )
    if module_id == "MODULE_PASSWORD_RESET_REQUEST":
        return (
            "Review the active recovery request, request a password reset code for the matching account "
            "via the requested channel, note the approved new password for later, and confirm the recovery channel before continuing to the reset form."
        )
    if module_id == "MODULE_PASSWORD_RESET_COMPLETION":
        return (
            "Review the active recovery request, request a verification code through its approved channel and ticket, "
            "open Mobile.local messages and read the latest numeric Security code, then return to Security.local "
            "reset-password page and set the approved new password shown in that request."
        )
    if module_id == "MODULE_PASSWORD_RECOVERY_E2E":
        return (
            "Review the active recovery request, request a verification code through its approved channel and ticket, "
            "read the latest Security message in Mobile, then return to Security.local and set the approved new password shown in that request."
        )
    if module_id == "MODULE_FIND_HOME":
        return (
            "Review the ready Housing Search Brief for the new downtown lease, use the brief's constraints "
            "to filter and sort listings, choose the listing that satisfies the brief's selection rule, "
            "set the lease term from the brief, and apply."
        )
    if module_id == "MODULE_UTILITY_SETUP":
        return "Review the utility activation notice, then set up utilities using the residence, billing details, plan details, and activation code shown there."
    if module_id == "MODULE_AIRPORT_TRANSFER":
        return (
            "Review the transfer request and vehicle readiness shown on the page, confirm the request match, "
            "then book airport transfer using the request details and the method that matches the current vehicle condition."
        )
    if module_id == "MODULE_ADDRESS_CHANGE":
        return (
            "Review the residence source and proof-document checklist, then submit the address change "
            "using the address, ZIP code, proof document, and reference code shown there."
        )
    if module_id == "MODULE_ADDRESS_PROOF":
        return (
            "Review the matching Address Proof Intake item, upload the listed address proof using the document type "
            "and verification code shown there, confirm the intake was matched, and verify the profile shows the address as verified."
        )
    if module_id in {"MODULE_PERMIT_APP", "MODULE_PARKING_PERMIT_APPLICATION"}:
        return (
            "Use the matching Permit Request Intake item, review its permit type, duration, and intake code, "
            "then apply using those request details."
        )
    if module_id == "MODULE_PERMIT_RENEWAL":
        return (
            "Review the matching renewal notice, then manually renew the permit using "
            "the new expiry, payment method, and notice code shown there."
        )
    if module_id == "MODULE_RENEW_PERMIT":
        params = dict(parameter_values or {})
        permit_id = str(params.get("permit_id") or "RP-2024-77").strip()
        new_expiry = str(params.get("new_expiry") or "2027-01-15").strip()
        payment_method = str(params.get("payment_method") or "card").strip()
        return (
            f"Renew permit {permit_id} to {new_expiry}, pay by {payment_method}, use the renewal notice code shown "
            "on the permit page, and verify the renewed permit is recorded."
        )
    if module_id == "MODULE_BANK_OPENING":
        fullname = _format_binding_scalar(params.get("fullname", "the applicant"))
        return (
            f"Review the active applicant profile for {fullname} and the current residence source, then open a new bank account "
            "using the reviewed phone, address, and applicant identity code, and enable 2FA before finishing."
        )
    if module_id == "MODULE_VEHICLE_ADDRESS_UPDATE":
        params = dict(parameter_values or {})
        vehicle_id = str(params.get("vehicle_id") or "V-8821").strip()
        return (
            f"Use the matching Vehicle Address Notice for vehicle {vehicle_id}, then update the record "
            "with the notice address and insurance instruction."
        )
    if module_id == "MODULE_ENERGY_OPTIMIZE":
        return (
            "Review the optimization recommendations, manually select the recommended meter, choose the plan recommended "
            "for that meter, and confirm the projected cost details."
        )
    if module_id == "MODULE_CARD_REPLACEMENT":
        return (
            "Review the active card replacement authorization, replace the matching card using the replacement card "
            "and verification code shown there, and confirm linked merchant bindings are updated."
        )
    if module_id == "MODULE_LOST_CARD_FREEZE":
        return (
            "Review the active card incident, freeze the matching card using the lost-card reason and freeze code, "
            "and acknowledge linked merchant payment impact."
        )
    if module_id == "MODULE_PRESCRIPTION_REFILL":
        return (
            "Review the active refill request, then refill the matching prescription "
            "using the fulfillment method and refill code shown there, and confirm the refill details."
        )
    if module_id == "MODULE_LIVE_AUCTION":
        return (
            "Review the active auction bid plan, manually enter the plan's bid amount, maximum budget, "
            "and bid code for the matching live auction, then confirm the bid."
        )
    if module_id == "MODULE_RECEIPT_ARCHIVING":
        file_name = str(params.get("file_path") or params.get("fileName") or "the listed file").strip()
        return (
            f"Review the Archive Intake source for {file_name}, then archive that file as a receipt "
            "using the vendor, document date, amount, archive code, and retention label shown in the source."
        )
    if module_id == "MODULE_BUDGET_LIMIT_UPDATE":
        return (
            "Review the active budget memo, apply the recommended category limit, reason, and approval code, "
            "and confirm the current limit was reviewed."
        )
    if module_id == "MODULE_TRANSFER_FUNDS":
        return (
            "Review the active budget memo created by the funds transfer decision, apply the memo's "
            "recommended category limit, record the memo reason, confirm the current limit was reviewed, "
            "and save the budget update."
        )
    if module_id == "MODULE_HOUSEKEEPING_BOOKING":
        params = dict(parameter_values or {})
        service_date = str(params.get("service_date") or "").strip()
        return (
            f"Use the matching Service Request, then book the service for {service_date} "
            "by manually entering the request's listed type, time, and instructions."
        )
    if module_id == "MODULE_CAMERA_CHECK":
        params = dict(parameter_values or {})
        device_id = str(params.get("deviceId") or params.get("device_id") or "").strip()
        location = str(params.get("location") or "").strip()
        color = _normalize_device_profile(params.get("color") or "")
        return f"Review the active device setup ticket, then manually add camera device {device_id} at location {location} using profile {color} and its setup code."
    if module_id == "MODULE_SMART_BULB_SETUP":
        params = dict(parameter_values or {})
        device_id = str(params.get("deviceId") or params.get("device_id") or "").strip()
        location = str(params.get("location") or "").strip()
        color = _normalize_device_profile(params.get("color") or "")
        return f"Review the active device setup ticket, then manually configure smart bulb device {device_id} in {location} with profile {color} and its setup code."
    if module_id == "MODULE_THERMOSTAT_SCHEDULE":
        params = dict(parameter_values or {})
        device_id = str(params.get("deviceId") or params.get("device_id") or "").strip()
        location = str(params.get("location") or "").strip()
        color = _normalize_device_profile(params.get("color") or "")
        return f"Review the active device setup ticket, then manually configure thermostat device {device_id} in {location} with profile {color} and its setup code."
    if module_id == "MODULE_FIRMWARE_UPDATE":
        params = dict(parameter_values or {})
        appliance = str(params.get("appliance") or "Smart Thermostat").strip()
        serial_number = str(params.get("serial_number") or "").strip()
        problem = _normalize_firmware_problem(params.get("problem") or "")
        service_date = str(params.get("service_date") or "").strip()
        return (
            f"Review the active appliance service intake for {appliance} serial {serial_number}, then report "
            f"{problem} and request service on {service_date} using the intake details."
        )
    params = dict(parameter_values or {})
    if module_id == "MODULE_LEAVE_REVIEW":
        merchant = str(params.get("merchant") or "美味餐厅").strip()
        rating = _format_binding_scalar(params.get("rating") or "5")
        content = str(params.get("content") or "非常棒的用餐体验，会再次光顾！").strip()
        return (
            f"Leave a {rating}-star product review for {merchant} with content: {content} "
            "Do not blacklist the merchant."
        )
    if module_id == "MODULE_CONTACT_SUPPORT":
        order_id = str(params.get("order_id") or "O-98321").strip()
        issue_type = str(params.get("issue_type") or "missing").strip()
        description_text = str(params.get("description") or "An item was missing from my delivered package.").strip()
        return (
            f"Open a support ticket for order {order_id}, select issue type {issue_type}, "
            f"and use this description: {description_text}"
        )
    if module_id == "MODULE_LOGISTICS_FIX":
        order_id = str(params.get("order_id") or params.get("orderId") or "O-98321").strip()
        issue_type = str(params.get("issue_type") or params.get("type") or "damaged").strip()
        description_text = str(params.get("description") or "The package arrived with a damaged item.").strip()
        return (
            f"Open a logistics ticket for order {order_id}, select issue type {issue_type}, "
            f"and use this description: {description_text}"
        )
    if module_id == "MODULE_SUBSCRIPTION_REFUND":
        subscription_id = str(params.get("subscription_id") or "SUB-8821").strip()
        reason = str(params.get("reason") or "Service is no longer needed.").strip()
        return (
            f"Review the active refund intake, then request a prorated refund for subscription {subscription_id} "
            f"with reason: {reason}. Use the intake code and expected refund shown in that active intake."
        )
    if module_id == "MODULE_EXPENSE_REPORT":
        return (
            "Review the matching Travel Reimbursement Request on the expense page, then manually submit "
            "the report using the request's report ID, amount, PNR, description, expense type, and "
            "receipt bundle code. Confirm the source match before submitting."
        )
    if module_id == "MODULE_COUPON_MANAGEMENT":
        return (
            "Review the matching coupon request, then manually create the coupon using the request's "
            "name, code, type, value, minimum spend, and expiry date."
        )
    if module_id == "MODULE_LEASE_CONTRACT_REGISTRATION":
        return "Review the active lease contract packet, then register the contract using the fields and packet code shown there."
    if module_id == "MODULE_BILL_AGGREGATION":
        return (
            "Review the bill source catalog, then add and synchronize the approved source using its account "
            "and verification code after confirming the source match."
        )
    if module_id == "MODULE_TAX_PREPARATION":
        return "Review the tax intake queue, then upload the ready document using the fields and reference code shown there."
    if module_id == "MODULE_FILE_TAXES":
        name = str(params.get("document_name") or params.get("name") or "W2-2025").strip()
        return f"Review the tax intake queue for {name}, then upload the ready document using the fields and reference code shown there."
    if module_id == "MODULE_ROOMMATE_EXPENSE_SPLIT":
        return "Review the roommate settlement memo, then settle the shared expenses using the month, split rule, and reference code shown there."
    if module_id == "MODULE_RSVP_EVENT":
        return "Review the RSVP organizer note, then join the indicated organizer group using its access code after matching the note and agreeing to the community rules."
    if module_id == "MODULE_GIFT_POOLING":
        return "Review the gift-pool memo, then record the contribution using the amount, recipient, receipt setting, and campaign code shown there after confirming the memo match."
    if module_id == "MODULE_CHARITY_DONATION":
        return "Review the donation memo, then record the contribution using the amount, recipient, receipt setting, and campaign code shown there after confirming the memo match."
    if module_id == "MODULE_MOBILE_PLAN_SIGNUP":
        return "Review the newcomer mobile recommendation, then subscribe using the recommended plan, contact, residence, and recommendation code."
    if module_id == "MODULE_CHECK_BALANCE":
        sequence = _normalize_balance_sequence(params.get("account_sequence", params.get("account_type", "")))
        if len(sequence) == 1:
            return f"Open the bank dashboard and view the {sequence[-1]} balance."
        return (
            "Open the bank dashboard and review balances in this order: "
            f"{', '.join(sequence[:-1])}, then {sequence[-1]}. Finish on the {sequence[-1]} balance view."
        )
    if module_id == "MODULE_CALENDAR_AGGREGATION":
        return (
            "Review the matching active calendar intake note, then add the event using "
            "the date, time, type, source confirmation code, and description shown in that note."
        )
    if module_id == "MODULE_CONFERENCE_REG":
        report_id = str(params.get("report_id") or params.get("reportId") or "EXP-2201").strip()
        total_amount = _format_binding_scalar(params.get("total_amount") or params.get("total") or "980")
        linked_pnr = str(params.get("linked_pnr") or params.get("pnr") or "PNR-2201").strip()
        description_text = str(params.get("description") or "Conference registration and travel").strip()
        event = str(params.get("event") or "the conference").strip()
        registration_id = str(params.get("registration_id") or params.get("source_registration_id") or "").strip()
        source_clause = f" for registration {registration_id}" if registration_id else ""
        return (
            f"Review the conference confirmation for {event}{source_clause}, confirm the source match, then manually submit the expense report "
            "using the report id, amount, linked PNR, description, expense type, and receipt bundle shown in that confirmation."
        )
    if module_id == "MODULE_JOB_SEARCH":
        return (
            "Search the work inbox for the relevant recruiting follow-up email, open it to verify "
            "the thread details, then review the active follow-up request in Email Tracking and "
            "create a pending tracked thread using the reviewed request fields."
        )
    if module_id == "MODULE_MOBILE_PLAN_SWITCH":
        return (
            "Review the account usage and advisor note, switch the active mobile subscription to the recommended plan, "
            "enter the advisor note code, effective date, and usage reading shown there, and confirm the switch in the confirmation dialog."
        )
    if module_id == "MODULE_PAPER_SUBMISSION":
        title = str(params.get("title") or "").strip()
        return (
            f"Review the ready draft package for {title}, then submit the paper using the venue, authors, "
            "abstract, track, and file shown in that draft package."
        )
    if module_id == "MODULE_BILLING_REVIEW":
        utilities = _normalize_utility_types(params.get("utility_types"))
        utility_labels = [_utility_type_label(item) for item in utilities]
        if len(utility_labels) == 1:
            return (
                f"Open the gov.local Bills page, use the bill-type filter to review {utility_labels[0]}, "
                "and leave that filter selected."
            )
        return (
            "Open the gov.local Bills page, use the bill-type filters to review "
            f"{', '.join(utility_labels[:-1])} and {utility_labels[-1]} separately, "
            f"record which utility has the higher pending total and the largest pending water bill ID, "
            f"and finish with the {utility_labels[-1]} filter selected."
        )
    if module_id in {"MODULE_DOWNLOAD_CERT", "MODULE_SKILL_CERTIFICATION"}:
        return (
            "Review the approved certification plan, then apply for the certificates in the plan order "
            "using the approved plan code and eligibility code, and verify the final request matches the plan."
        )
    if module_id != "MODULE_UPDATE_LINKEDIN":
        return description
    return (
        "Search the work inbox for the LinkedIn profile update notification, open it to verify "
        "the thread details, then create a pending email tracking thread using the subject, sender, "
        "summary, priority, and follow-up date shown in that source email."
    )


def resolve_execution_binding(
    module_id: str,
    oracle: dict[str, Any],
    bindings_by_module: dict[str, list[dict[str, Any]]],
    used_invocations: set[str],
    forced_invocation_id: str = "",
) -> dict[str, Any]:
    invocations = oracle.get("reference_invocations", [])
    invocations_by_id = {
        invocation.get("invocation_id"): invocation
        for invocation in invocations
        if invocation.get("invocation_id")
    }
    chosen_invocation = None
    if forced_invocation_id:
        invocation = invocations_by_id.get(forced_invocation_id)
        if invocation and invocation.get("module_id") != module_id:
            raise ValueError(
                f"reference invocation {forced_invocation_id} belongs to "
                f"{invocation.get('module_id')}, not {module_id}"
            )
        chosen_invocation = invocation
        if chosen_invocation is None:
            raise ValueError(f"reference invocation not found: {forced_invocation_id}")
    else:
        required_modules = {
            item
            for item in (oracle.get("evaluation", {}) or {}).get("required_modules", []) or []
            if isinstance(item, str)
        }
        for path in oracle.get("success_paths", []) or []:
            path_modules = {
                item for item in path.get("required_modules", []) or []
                if isinstance(item, str)
            }
            if required_modules and path_modules != required_modules:
                continue
            for invocation_id in path.get("reference_invocation_ids", []) or []:
                if invocation_id in used_invocations:
                    continue
                invocation = invocations_by_id.get(invocation_id)
                if invocation and invocation.get("module_id") == module_id:
                    chosen_invocation = invocation
                    break
            if chosen_invocation:
                break
        for invocation in invocations:
            if chosen_invocation:
                break
            if invocation.get("module_id") == module_id and invocation.get("invocation_id") not in used_invocations:
                chosen_invocation = invocation
                break

    bindings = bindings_by_module.get(module_id, [])
    if not bindings:
        raise ValueError(f"no binding available for module {module_id}")

    binding = None
    if chosen_invocation and chosen_invocation.get("binding_id"):
        for item in bindings:
            if item["binding_id"] == chosen_invocation["binding_id"]:
                binding = item
                break
    if binding is None:
        binding = bindings[0]

    invocation_matches_binding = False
    if chosen_invocation:
        chosen_binding_id = str(chosen_invocation.get("binding_id") or "").strip()
        chosen_binding_task_id = str(chosen_invocation.get("binding_task_id") or "").strip()
        invocation_matches_binding = (
            (not chosen_binding_id or chosen_binding_id == binding["binding_id"])
            and (not chosen_binding_task_id or chosen_binding_task_id == binding["backing_task_id"])
        )

    parameter_values = dict(binding.get("default_parameter_values", {}))
    description = binding.get("seed_example", {}).get("description") or module_id
    expected_observables = list(binding.get("seed_example", {}).get("observables", []) or [])
    invocation_id = None
    if chosen_invocation:
        invocation_id = chosen_invocation.get("invocation_id")
        if invocation_matches_binding:
            parameter_values.update(chosen_invocation.get("parameter_values", {}))
            if chosen_invocation.get("description"):
                description = chosen_invocation["description"]
            if chosen_invocation.get("expected_observables"):
                expected_observables = list(chosen_invocation["expected_observables"])

    parameter_values = _normalize_binding_parameters(module_id, parameter_values)
    description = _normalize_binding_description(module_id, description, parameter_values)

    return {
        "module_id": module_id,
        "binding_id": binding["binding_id"],
        "binding_task_id": binding["backing_task_id"],
        "task_dir": binding["task_dir"],
        "parameter_values": parameter_values,
        "description": description,
        "expected_observables": expected_observables,
        "invocation_id": invocation_id,
    }


def _runtime_path_get(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _successful_source_modules(executed_modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        entry for entry in executed_modules
        if entry.get("status") == "success" and isinstance(entry.get("parameter_values"), dict)
    ]


def _cross_task_dependency_context(
    executed_modules: list[dict[str, Any]],
    runtime_root: Path,
) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for entry in _successful_source_modules(executed_modules):
        module_id = str(entry.get("module_id") or "")
        params = dict(entry.get("parameter_values") or {})
        if module_id == "MODULE_FIND_HOME":
            address = str(
                params.get("selected_address") or property_address_for_id(params.get("propertyId"))
            ).strip()
            if address:
                context["lease_address"] = {
                    "value": address,
                    "source_module_id": module_id,
                    "source_field": "selected_address",
                }
        if module_id == "MODULE_LEASE_CONTRACT_REGISTRATION":
            address = str(params.get("address") or "88 River Rd, Springfield").strip()
            if address:
                context["lease_address"] = {
                    "value": address,
                    "source_module_id": module_id,
                    "source_field": "address",
                }
        if module_id == "MODULE_COURSE_ENROLLMENT":
            course_id = str(params.get("courseId") or params.get("course_id") or "").strip()
            if course_id:
                context["course_id"] = {
                    "value": course_id,
                    "source_module_id": module_id,
                    "source_field": "courseId",
                }
        if module_id == "MODULE_DOCTOR_APPT":
            appointment_id = str(params.get("appointmentId") or params.get("appointment_id") or "").strip()
            if appointment_id:
                context["appointment_id"] = {
                    "value": appointment_id,
                    "source_module_id": module_id,
                    "source_field": "appointmentId",
                }
        if module_id in {"MODULE_CONTACT_SUPPORT", "MODULE_CUSTOMER_SERVICE", "MODULE_LOGISTICS_FIX"}:
            order_id = str(params.get("order_id") or params.get("orderId") or "").strip()
            if order_id:
                context["support_ticket_order_id"] = {
                    "value": order_id,
                    "source_module_id": module_id,
                    "source_field": "order_id",
                }
        if module_id == "MODULE_BILL_AGGREGATION":
            payee = str(params.get("name") or params.get("payee") or "").strip()
            account_id = str(
                params.get("account_id")
                or params.get("account_number")
                or params.get("source_account_number")
                or ""
            ).strip()
            if payee:
                context["bill_source_payee"] = {
                    "value": payee,
                    "source_module_id": module_id,
                    "source_field": "name",
                }
            if account_id:
                context["bill_source_account_id"] = {
                    "value": account_id,
                    "source_module_id": module_id,
                    "source_field": "account_id",
                }
        if module_id == "MODULE_DATA_DELETION":
            request_type = str(params.get("request_type") or "").strip()
            platform = str(params.get("platform") or "").strip()
            data_scope = str(params.get("data_scope") or "").strip()
            reason = str(params.get("reason") or "").strip()
            contact_email = str(params.get("contact_email") or "").strip()
            if request_type:
                context["data_request_type"] = {
                    "value": request_type,
                    "source_module_id": module_id,
                    "source_field": "request_type",
                }
            if platform:
                context["data_request_platform"] = {
                    "value": platform,
                    "source_module_id": module_id,
                    "source_field": "platform",
                }
            if data_scope:
                context["data_request_scope"] = {
                    "value": data_scope,
                    "source_module_id": module_id,
                    "source_field": "data_scope",
                }
            if reason:
                context["data_request_reason"] = {
                    "value": reason,
                    "source_module_id": module_id,
                    "source_field": "reason",
                }
            if contact_email:
                context["data_request_contact_email"] = {
                    "value": contact_email,
                    "source_module_id": module_id,
                    "source_field": "contact_email",
                }
        if module_id in {"MODULE_BOOK_FLIGHT", "MODULE_LONG_HAUL_TRIP"}:
            pnr = str(params.get("pnr") or "").strip()
            if pnr:
                context["flight_pnr"] = {
                    "value": pnr,
                    "source_module_id": module_id,
                    "source_field": "pnr",
                }
            # P3: TRAVEL - extract flight destination
            destination = str(params.get("destination") or "").strip()
            if destination:
                context["flight_destination"] = {
                    "value": destination,
                    "source_module_id": module_id,
                    "source_field": "destination",
                }
        # P1: COMPOSITE - extract bank identity code and holder name
        if module_id == "MODULE_BANK_OPENING":
            identity_code = str(params.get("verification_code") or "").strip()
            if identity_code:
                context["bank_identity_code"] = {
                    "value": identity_code,
                    "source_module_id": module_id,
                    "source_field": "verification_code",
                }
            holder_name = str(params.get("fullname") or "").strip()
            if holder_name:
                context["bank_holder_name"] = {
                    "value": holder_name,
                    "source_module_id": module_id,
                    "source_field": "fullname",
                }
        # P2: HEALTH - extract insurance plan_id and policy_number
        if module_id == "MODULE_INSURANCE_POLICY":
            plan_id = str(params.get("plan_id") or "").strip()
            if plan_id:
                context["insurance_plan_id"] = {
                    "value": plan_id,
                    "source_module_id": module_id,
                    "source_field": "plan_id",
                }
        # P4: DAILY - extract tracked order_id from TRACK_ORDERS
        if module_id == "MODULE_TRACK_ORDERS":
            order_id = str(params.get("order_id") or params.get("orderId") or "").strip()
            if order_id:
                context["tracked_order_id"] = {
                    "value": order_id,
                    "source_module_id": module_id,
                    "source_field": "order_id",
                }
        # P4: DAILY - extract merchant from LEAVE_REVIEW
        if module_id == "MODULE_LEAVE_REVIEW":
            merchant = str(params.get("merchant") or "").strip()
            if merchant:
                context["review_merchant"] = {
                    "value": merchant,
                    "source_module_id": module_id,
                    "source_field": "merchant",
                }
        if module_id == "MODULE_PASSWORD_RESET_REQUEST":
            username = str(params.get("username") or "").strip()
            if username:
                context["reset_username"] = {
                    "value": username,
                    "source_module_id": module_id,
                    "source_field": "username",
                }
            reset_code = str(params.get("code") or _password_reset_code_for_username(username)).strip()
            if reset_code:
                context["reset_code"] = {
                    "value": reset_code,
                    "source_module_id": module_id,
                    "source_field": "code",
                }
            reset_new_password = str(
                params.get("new_password") or _password_reset_new_password_for_username(username)
            ).strip()
            if reset_new_password:
                context["reset_new_password"] = {
                    "value": reset_new_password,
                    "source_module_id": module_id,
                    "source_field": "new_password",
                }

    env = _load_runtime_state(runtime_root)
    flight_pnr = str(_runtime_path_get(env, "trips.flight.pnr") or "").strip()
    flight_source = next(
        (
            str(entry.get("module_id") or "")
            for entry in reversed(_successful_source_modules(executed_modules))
            if entry.get("module_id") in {"MODULE_BOOK_FLIGHT", "MODULE_LONG_HAUL_TRIP"}
        ),
        "MODULE_BOOK_FLIGHT",
    )
    if flight_pnr and "flight_pnr" not in context and any(
        entry.get("module_id") in {"MODULE_BOOK_FLIGHT", "MODULE_LONG_HAUL_TRIP"}
        for entry in _successful_source_modules(executed_modules)
    ):
        context["flight_pnr"] = {
            "value": flight_pnr,
            "source_module_id": flight_source,
            "source_field": "trips.flight.pnr",
        }

    reset_code = str(_runtime_path_get(env, "security.reset_code") or "").strip()
    if reset_code and "reset_code" not in context and any(
        entry.get("module_id") == "MODULE_PASSWORD_RESET_REQUEST"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["reset_code"] = {
            "value": reset_code,
            "source_module_id": "MODULE_PASSWORD_RESET_REQUEST",
            "source_field": "security.reset_code",
        }
    reset_username = str(_runtime_path_get(env, "security.reset_user") or "").strip()
    if reset_username and "reset_username" not in context:
        context["reset_username"] = {
            "value": reset_username,
            "source_module_id": "MODULE_PASSWORD_RESET_REQUEST",
            "source_field": "security.reset_user",
        }
    reset_new_password = str(
        _runtime_path_get(env, "security.password_reset.approved_new_password") or ""
    ).strip()
    if reset_new_password and "reset_new_password" not in context:
        context["reset_new_password"] = {
            "value": reset_new_password,
            "source_module_id": "MODULE_PASSWORD_RESET_REQUEST",
            "source_field": "security.password_reset.approved_new_password",
        }

    appointment_id = str(_runtime_path_get(env, "health.appointments.last.id") or "").strip()
    if appointment_id and "appointment_id" not in context and any(
        entry.get("module_id") == "MODULE_DOCTOR_APPT"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["appointment_id"] = {
            "value": appointment_id,
            "source_module_id": "MODULE_DOCTOR_APPT",
            "source_field": "health.appointments.last.id",
        }

    support_order_id = str(_runtime_path_get(env, "support.tickets.last.order_id") or "").strip()
    if support_order_id and "support_ticket_order_id" not in context and any(
        entry.get("module_id") == "MODULE_LOGISTICS_FIX"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["support_ticket_order_id"] = {
            "value": support_order_id,
            "source_module_id": "MODULE_LOGISTICS_FIX",
            "source_field": "support.tickets.last.order_id",
        }

    bill_source_payee = str(_runtime_path_get(env, "bills.sources.last.name") or "").strip()
    if bill_source_payee and "bill_source_payee" not in context and any(
        entry.get("module_id") == "MODULE_BILL_AGGREGATION"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["bill_source_payee"] = {
            "value": bill_source_payee,
            "source_module_id": "MODULE_BILL_AGGREGATION",
            "source_field": "bills.sources.last.name",
        }
    bill_source_account_id = str(_runtime_path_get(env, "bills.sources.last.account_id") or "").strip()
    if bill_source_account_id and "bill_source_account_id" not in context and any(
        entry.get("module_id") == "MODULE_BILL_AGGREGATION"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["bill_source_account_id"] = {
            "value": bill_source_account_id,
            "source_module_id": "MODULE_BILL_AGGREGATION",
            "source_field": "bills.sources.last.account_id",
        }

    # P1: COMPOSITE - runtime fallback for bank identity code and holder name
    bank_identity = str(_runtime_path_get(env, "bank.account.identity_code") or "").strip()
    if bank_identity and "bank_identity_code" not in context and any(
        entry.get("module_id") == "MODULE_BANK_OPENING"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["bank_identity_code"] = {
            "value": bank_identity,
            "source_module_id": "MODULE_BANK_OPENING",
            "source_field": "bank.account.identity_code",
        }
    bank_holder = str(_runtime_path_get(env, "bank.account.holder_name") or "").strip()
    if bank_holder and "bank_holder_name" not in context and any(
        entry.get("module_id") == "MODULE_BANK_OPENING"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["bank_holder_name"] = {
            "value": bank_holder,
            "source_module_id": "MODULE_BANK_OPENING",
            "source_field": "bank.account.holder_name",
        }

    # P2: HEALTH - runtime fallback for insurance plan_id and policy_number
    ins_plan_id = str(_runtime_path_get(env, "health.insurance.plan_id") or "").strip()
    if ins_plan_id and "insurance_plan_id" not in context and any(
        entry.get("module_id") == "MODULE_INSURANCE_POLICY"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["insurance_plan_id"] = {
            "value": ins_plan_id,
            "source_module_id": "MODULE_INSURANCE_POLICY",
            "source_field": "health.insurance.plan_id",
        }
    ins_policy_number = str(_runtime_path_get(env, "health.insurance.policy_number") or "").strip()
    if ins_policy_number and "insurance_policy_number" not in context and any(
        entry.get("module_id") == "MODULE_INSURANCE_POLICY"
        for entry in _successful_source_modules(executed_modules)
    ):
        context["insurance_policy_number"] = {
            "value": ins_policy_number,
            "source_module_id": "MODULE_INSURANCE_POLICY",
            "source_field": "health.insurance.policy_number",
        }

    # P3: TRAVEL - runtime fallback for flight destination
    flight_dest = str(_runtime_path_get(env, "trips.flight.destination") or "").strip()
    if flight_dest and "flight_destination" not in context and any(
        entry.get("module_id") in {"MODULE_BOOK_FLIGHT", "MODULE_LONG_HAUL_TRIP"}
        for entry in _successful_source_modules(executed_modules)
    ):
        context["flight_destination"] = {
            "value": flight_dest,
            "source_module_id": flight_source,
            "source_field": "trips.flight.destination",
        }

    return context


def _dependency_update(
    *,
    context: dict[str, dict[str, Any]],
    context_key: str,
    params: dict[str, Any],
    target_field: str,
    reason: str,
) -> dict[str, Any] | None:
    source = context.get(context_key) or {}
    value = str(source.get("value") or "").strip()
    if not value:
        return None
    old_value = params.get(target_field)
    old_value_text = str(old_value or "").strip()
    value_changed = old_value_text != value
    params[target_field] = value
    return {
        "source_module_id": source.get("source_module_id", ""),
        "source_field": source.get("source_field", context_key),
        "target_field": target_field,
        "old_value": old_value,
        "new_value": value,
        "value_changed": value_changed,
        "reason": reason,
    }


def apply_cross_task_parameter_dependencies(
    module_id: str,
    binding_payload: dict[str, Any],
    executed_modules: list[dict[str, Any]],
    runtime_root: Path,
) -> dict[str, Any]:
    params = dict(binding_payload.get("parameter_values") or {})
    context = _cross_task_dependency_context(executed_modules, runtime_root)
    updates: list[dict[str, Any]] = []

    address_field = LEASE_ADDRESS_CONSUMERS.get(module_id)
    if address_field:
        update = _dependency_update(
            context=context,
            context_key="lease_address",
            params=params,
            target_field=address_field,
            reason="carry_selected_residence_address",
        )
        if update:
            updates.append(update)

    course_field = COURSE_ID_CONSUMERS.get(module_id)
    if course_field:
        update = _dependency_update(
            context=context,
            context_key="course_id",
            params=params,
            target_field=course_field,
            reason="carry_enrolled_course_id",
        )
        if update:
            updates.append(update)

    appointment_field = APPOINTMENT_ID_CONSUMERS.get(module_id)
    if appointment_field:
        update = _dependency_update(
            context=context,
            context_key="appointment_id",
            params=params,
            target_field=appointment_field,
            reason="carry_booked_appointment_id",
        )
        if update:
            updates.append(update)

    support_order_field = SUPPORT_TICKET_ORDER_CONSUMERS.get(module_id)
    if support_order_field:
        update = _dependency_update(
            context=context,
            context_key="support_ticket_order_id",
            params=params,
            target_field=support_order_field,
            reason="carry_support_ticket_order_id",
        )
        if update:
            updates.append(update)

    for context_key, target_field in BILL_SOURCE_CONSUMERS.get(module_id, {}).items():
        update = _dependency_update(
            context=context,
            context_key=context_key,
            params=params,
            target_field=target_field,
            reason="carry_reviewed_bill_source",
        )
        if update:
            updates.append(update)

    for context_key, target_field in DATA_REQUEST_CONSUMERS.get(module_id, {}).items():
        update = _dependency_update(
            context=context,
            context_key=context_key,
            params=params,
            target_field=target_field,
            reason="carry_prior_data_request_fields",
        )
        if update:
            updates.append(update)

    pnr_field = FLIGHT_PNR_CONSUMERS.get(module_id)
    if pnr_field:
        update = _dependency_update(
            context=context,
            context_key="flight_pnr",
            params=params,
            target_field=pnr_field,
            reason="carry_booked_flight_pnr",
        )
        if update:
            updates.append(update)

    for context_key, target_field in PASSWORD_RESET_CONSUMERS.get(module_id, {}).items():
        update = _dependency_update(
            context=context,
            context_key=context_key,
            params=params,
            target_field=target_field,
            reason="carry_password_reset_state",
        )
        if update:
            updates.append(update)

    # P1: COMPOSITE - inject bank identity code
    bank_id_field = BANK_IDENTITY_CODE_CONSUMERS.get(module_id)
    if bank_id_field:
        update = _dependency_update(
            context=context,
            context_key="bank_identity_code",
            params=params,
            target_field=bank_id_field,
            reason="carry_bank_identity_code",
        )
        if update:
            updates.append(update)

    # P1: COMPOSITE - inject bank holder name
    bank_holder_field = BANK_HOLDER_NAME_CONSUMERS.get(module_id)
    if bank_holder_field:
        update = _dependency_update(
            context=context,
            context_key="bank_holder_name",
            params=params,
            target_field=bank_holder_field,
            reason="carry_bank_holder_name",
        )
        if update:
            updates.append(update)

    # P2: HEALTH - inject insurance plan_id
    ins_plan_field = INSURANCE_PLAN_ID_CONSUMERS.get(module_id)
    if ins_plan_field:
        update = _dependency_update(
            context=context,
            context_key="insurance_plan_id",
            params=params,
            target_field=ins_plan_field,
            reason="carry_insurance_plan_id",
        )
        if update:
            updates.append(update)

    # P2: HEALTH - inject insurance policy_number
    ins_policy_field = INSURANCE_POLICY_NUMBER_CONSUMERS.get(module_id)
    if ins_policy_field:
        update = _dependency_update(
            context=context,
            context_key="insurance_policy_number",
            params=params,
            target_field=ins_policy_field,
            reason="carry_insurance_policy_number",
        )
        if update:
            updates.append(update)

    # P3: TRAVEL - inject flight destination
    dest_field = FLIGHT_DESTINATION_CONSUMERS.get(module_id)
    if dest_field:
        update = _dependency_update(
            context=context,
            context_key="flight_destination",
            params=params,
            target_field=dest_field,
            reason="carry_booked_flight_destination",
        )
        if update:
            updates.append(update)

    # P4: DAILY - inject tracked order_id
    tracked_order_field = TRACKED_ORDER_ID_CONSUMERS.get(module_id)
    if tracked_order_field:
        update = _dependency_update(
            context=context,
            context_key="tracked_order_id",
            params=params,
            target_field=tracked_order_field,
            reason="carry_tracked_order_id",
        )
        if update:
            updates.append(update)

    # P4: DAILY - inject review merchant
    merchant_field = REVIEW_MERCHANT_CONSUMERS.get(module_id)
    if merchant_field:
        update = _dependency_update(
            context=context,
            context_key="review_merchant",
            params=params,
            target_field=merchant_field,
            reason="carry_review_merchant",
        )
        if update:
            updates.append(update)

    if not updates:
        return binding_payload

    updated_payload = dict(binding_payload)
    updated_params = _normalize_binding_parameters(module_id, params)
    updated_payload["parameter_values"] = updated_params
    normalized_description = _normalize_binding_description(
        module_id,
        str(binding_payload.get("description") or module_id),
        updated_params,
    )
    updated_payload["description"] = _dependency_masked_description(
        module_id,
        normalized_description,
        updated_params,
        updates,
    )
    updated_payload["dependency_parameter_updates"] = updates
    return updated_payload


_RUNTIME_LIST_MERGE_SPECS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("work", "emails"), "id"),
    (("work", "paper_drafts"), "id"),
    (("work", "conference_confirmations"), "registration_id"),
    (("calendar", "sources"), "id"),
    (("cloud", "archive_sources"), "id"),
    (("mobile", "signup_sources"), "id"),
    (("mobile", "switch_recommendations"), "id"),
    (("bills", "sources"), "id"),
    (("finance", "budget_sources"), "id"),
    (("finance", "tax_sources"), "id"),
    (("social", "split_sources"), "id"),
    (("social", "donation_sources"), "id"),
    (("social", "group_sources"), "id"),
    (("user_profile", "bank_applicants"), "id"),
)


def _merge_runtime_fixture_lists(env: dict[str, Any], fixtures: dict[str, Any]) -> dict[str, Any]:
    for path, key_field in _RUNTIME_LIST_MERGE_SPECS:
        fixture_parent: Any = fixtures
        env_parent: Any = env
        for key in path[:-1]:
            fixture_parent = fixture_parent.get(key, {}) if isinstance(fixture_parent, dict) else {}
            if not isinstance(env_parent, dict):
                env_parent = {}
            env_parent = env_parent.setdefault(key, {})
        leaf = path[-1]
        fixture_items = fixture_parent.get(leaf, []) if isinstance(fixture_parent, dict) else []
        env_items = env_parent.get(leaf, []) if isinstance(env_parent, dict) else []
        if not isinstance(fixture_items, list):
            continue
        if not isinstance(env_items, list):
            env_items = []
        seen = {
            str(item.get(key_field) or "")
            for item in env_items
            if isinstance(item, dict) and str(item.get(key_field) or "")
        }
        merged = list(env_items)
        for item in fixture_items:
            if not isinstance(item, dict):
                continue
            item_key = str(item.get(key_field) or "")
            if item_key and item_key not in seen:
                merged.append(item)
                seen.add(item_key)
        env_parent[leaf] = merged
    return env


def _clean_env_from_initial_files(env_dir: Path) -> dict[str, Any]:
    env: dict[str, Any] = {}
    for path in sorted(env_dir.glob("*_initial.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            previous = env
            env = deep_merge(env, payload)
            env = _merge_runtime_fixture_lists(env, previous)
            env = _merge_runtime_fixture_lists(env, payload)
    env.setdefault("housing", {})["properties"] = seed_housing_properties()
    return env


def _initialize_clean_snapshot_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-shm", "-wal"):
        path = Path(f"{db_path}{suffix}")
        try:
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            pass

    schema_path = ROOT / "database" / "schema.sql"
    seed_path = ROOT / "database" / "seed_data.sql"
    with sqlite3.connect(db_path, timeout=30) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.executescript(schema_path.read_text(encoding="utf-8"))
        cur.executescript(seed_path.read_text(encoding="utf-8"))
        conn.commit()
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    for suffix in ("-shm", "-wal"):
        path = Path(f"{db_path}{suffix}")
        try:
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            pass


def snapshot_runtime(runtime_root: Path, snapshot_root: Path) -> None:
    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)
    snapshot_root.mkdir(parents=True, exist_ok=True)

    env_snapshot = snapshot_root / "env"
    env_snapshot.mkdir(parents=True, exist_ok=True)
    clean_env = _clean_env_from_initial_files(runtime_root / "env")
    (env_snapshot / "state.json").write_text(
        json.dumps(clean_env, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    _initialize_clean_snapshot_db(snapshot_root / "data.db")


def restore_runtime(runtime_root: Path, snapshot_root: Path) -> None:
    for rel in ("data.db", "data.db-shm", "data.db-wal", "env/state.json"):
        src = snapshot_root / rel
        dst = runtime_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
        elif dst.exists():
            dst.unlink()


def _runtime_initial_predicates(raw: Any) -> set[str]:
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    if isinstance(raw, dict):
        return {key for key, value in raw.items() if value is True}
    return set()


def _load_runtime_state(runtime_root: Path) -> dict[str, Any]:
    state_path = runtime_root / "env" / "state.json"
    if not state_path.exists():
        env: dict[str, Any] = {}
        env_dir = runtime_root / "env"
        for path in sorted(env_dir.glob("*_initial.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                env = deep_merge(env, payload)
        return env
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_runtime_state(runtime_root: Path, env: dict[str, Any]) -> None:
    state_path = runtime_root / "env" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(env, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _runtime_memory_set(conn: sqlite3.Connection, key: str, value: Any, ts: str, source: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
        [key, str(value), ts, source, 1.0],
    )


def _materialize_shop_order_predicate(runtime_root: Path, predicates: set[str]) -> None:
    needs_order = bool(predicates & {"shop_order_exists", "shop_order_pending", "shop_order_delivered"})
    if not needs_order:
        return

    delivered = "shop_order_delivered" in predicates and "shop_order_pending" not in predicates
    state = "delivered" if delivered else "confirmed"
    order_id = "O-70001"

    env = _load_runtime_state(runtime_root)
    ts = str(env.get("system_time") or datetime.now().isoformat())
    order_payload = {
        "id": order_id,
        "items": [
            {
                "id": "WM-5521",
                "sku": "WM-5521",
                "name": "Wireless Mouse",
                "category": "electronics",
                "quantity": 1,
                "qty": 1,
                "price": 29.99,
            }
        ],
        "total": 29.99,
        "state": state,
        "shipping_speed": "standard",
        "shipping_address": "123 Main St",
        "date": ts,
    }
    env.setdefault("shop", {}).setdefault("orders", {})
    env["shop"]["orders"][order_id] = order_payload
    env["shop"]["orders"]["last"] = {
        "id": order_id,
        "state": state,
        "total": 29.99,
    }
    env["pending_order"] = not delivered
    env["has_shop_delivered"] = delivered
    _save_runtime_state(runtime_root, env)

    db_path = runtime_root / "data.db"
    if not db_path.exists():
        return
    with sqlite3.connect(db_path, timeout=60) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DELETE FROM order_items WHERE order_id = ?", [order_id])
        conn.execute("DELETE FROM orders WHERE id = ?", [order_id])
        conn.execute(
            """
            INSERT INTO orders
              (id, user_id, total, state, shipping_speed, shipping_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [order_id, 1, 29.99, state, "standard", "123 Main St", ts],
        )
        conn.execute(
            "INSERT INTO order_items (order_id, sku, quantity, price) VALUES (?, ?, ?, ?)",
            [order_id, "WM-5521", 1, 29.99],
        )
        _runtime_memory_set(conn, "shop.orders.last.id", order_id, ts, "workflow_initial_state")
        _runtime_memory_set(conn, "shop.orders.last.state", state, ts, "workflow_initial_state")
        _runtime_memory_set(conn, "shop.orders.last.total", "29.99", ts, "workflow_initial_state")
        _runtime_memory_set(conn, f"shop.orders.{order_id}.state", state, ts, "workflow_initial_state")
        _runtime_memory_set(conn, "pending_order", "false" if delivered else "true", ts, "workflow_initial_state")
        _runtime_memory_set(conn, "has_shop_delivered", "true" if delivered else "false", ts, "workflow_initial_state")
        conn.commit()


def _materialize_bank_balance_predicate(runtime_root: Path, predicates: set[str]) -> None:
    balance_predicates = {
        "bank_balance_available",
        "banking_balance_available",
        "checking_balance_available",
    }
    if not predicates & balance_predicates:
        return

    balance = 500.0
    env = _load_runtime_state(runtime_root)
    ts = str(env.get("system_time") or datetime.now().isoformat())
    env.setdefault("banking", {}).setdefault("balance", {})["checking"] = balance
    _save_runtime_state(runtime_root, env)

    db_path = runtime_root / "data.db"
    if not db_path.exists():
        return
    with sqlite3.connect(db_path, timeout=60) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.execute(
            "UPDATE accounts SET balance = ? WHERE user_id = 1 AND type = 'checking'",
            [balance],
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO accounts (user_id, type, balance, currency, created_at) VALUES (?, ?, ?, ?, ?)",
                [1, "checking", balance, "USD", ts],
            )
        _runtime_memory_set(conn, "banking.balance.checking", balance, ts, "workflow_initial_state")
        conn.commit()


def materialize_initial_world_state(runtime_root: Path, initial_world_state: Any) -> None:
    predicates = _runtime_initial_predicates(initial_world_state)
    _materialize_shop_order_predicate(runtime_root, predicates)
    _materialize_bank_balance_predicate(runtime_root, predicates)


def execute_atomic_module(
    module: dict[str, Any],
    binding_payload: dict[str, Any],
    goal: dict[str, Any],
    stage_root: Path,
    client: Any,
    atomic_policy: str,
    atomic_max_steps: int,
    repeat_fail_threshold: int,
    headless: bool,
    verbose: bool,
    invocation_counter: int,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    invocation_id = binding_payload.get("invocation_id") or f"{goal['goal_id']}-R{invocation_counter}"
    plan_entry = {
        "index": invocation_counter,
        "module_id": module["module_id"],
        "binding_id": binding_payload["binding_id"],
        "binding_task_id": binding_payload["binding_task_id"],
        "task_dir": binding_payload["task_dir"],
        "invocation_id": invocation_id,
        "parameter_values": binding_payload["parameter_values"],
        "description": binding_payload["description"],
        "expected_observables": binding_payload["expected_observables"],
    }
    spec_path, oracle_path = instantiate_atomic_task(binding_payload, plan_entry, stage_root)
    if atomic_policy == "dry_run":
        return (
            {
                "success": True,
                "steps_executed": int(module.get("constraints", {}).get("estimated_steps", 0) or 0),
                "raw_output": "dry_run",
                "failure_category": "",
                "end_reason": "dry_run_success",
                "agent_backend": getattr(client, "backend_name", "unknown") if client else "none",
                "agent_model": getattr(client, "model", "") if client else "",
            },
            {
                "task_spec_path": str(spec_path),
                "oracle_trace_path": str(oracle_path),
            },
        )
    if atomic_policy == "oracle":
        from agent.executor import TaskExecutor

        port = str(os.environ.get("WEBAGENT_SERVER_PORT") or "").strip()
        if port:
            TaskExecutor.SUITE_PORT = int(port)
        executor = TaskExecutor(
            database_path=str((Path.cwd() / "data.db").resolve()),
            headless=headless,
            slow_mo=0,
        )
        result = executor.run(str(spec_path), str(oracle_path))
        return _oracle_execution_result_payload(result), {
            "task_spec_path": str(spec_path),
            "oracle_trace_path": str(oracle_path),
        }

    runtime_task_id = f"_workflow_runtime/{goal['goal_id']}/{invocation_id}"
    start_url = infer_start_url(oracle_path)
    result = execute_agent_task(
        task_id=runtime_task_id,
        start_url=start_url,
        max_steps=atomic_max_steps,
        repeat_fail_threshold=repeat_fail_threshold,
        stop_on_first_fail_step=True,
        headless=headless,
        client=client,
        write_result=False,
        verbose=verbose,
    )
    if _is_transient_browser_close_failure(result):
        retry_result = execute_agent_task(
            task_id=runtime_task_id,
            start_url=start_url,
            max_steps=atomic_max_steps,
            repeat_fail_threshold=repeat_fail_threshold,
            stop_on_first_fail_step=True,
            headless=headless,
            client=client,
            write_result=False,
            verbose=verbose,
        )
        retry_result["transient_retry_count"] = 1
        retry_result["transient_retry_reason"] = result.get("step_error_message") or result.get("end_reason") or ""
        result = retry_result
    return result, {
        "task_spec_path": str(spec_path),
        "oracle_trace_path": str(oracle_path),
    }


def run_single_goal(
    goal_ref: dict[str, Any],
    split_root: Path,
    output_root: Path,
    runtime_root: Path,
    snapshot_root: Path,
    modules_doc: dict[str, Any],
    bindings_doc: dict[str, Any],
    client: Any,
    args: argparse.Namespace,
) -> dict[str, Any]:
    goal = load_json(split_root / goal_ref["goal_file"])
    goal = apply_prompt_mode(goal, args.prompt_mode)
    oracle = load_json(split_root / goal_ref["oracle_file"])
    prompt_difficulty = infer_prompt_difficulty(goal)
    oracle_allowed_module_ids = allowed_modules_from_oracle(oracle)
    modules_doc_for_goal = apply_goal_conditional_requires(modules_doc, oracle_allowed_module_ids)
    modules_by_id, bindings_by_module = build_indices(modules_doc_for_goal, bindings_doc)
    planning_allowed_module_ids = (
        oracle_allowed_module_ids if args.module_policy == "reference" else None
    )

    restore_runtime(runtime_root, snapshot_root)
    materialize_initial_world_state(runtime_root, goal.get("initial_world_state", []))

    state = set(goal.get("initial_world_state", []))
    successful_modules: list[str] = []
    successful_invocations: set[str] = set()
    failed_modules: set[str] = set()
    used_invocations: set[str] = set()
    executed_modules: list[dict[str, Any]] = []
    selection_trace: list[dict[str, Any]] = []
    actual_step_count = 0
    actual_budget_spend = 0.0
    start_ts = time.time()

    max_module_invocations = int(goal.get("max_module_invocations", 0) or 0)
    episode_root = output_root / goal["goal_id"]
    stage_root = Path("tasks") / "_workflow_runtime" / goal["goal_id"]
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)
    visible_constraints = goal.get("visible_constraints", {}) or {}
    forbidden_modules = {
        item for item in visible_constraints.get("forbidden_modules", [])
        if isinstance(item, str)
    }
    forbidden_predicates = {
        item for item in visible_constraints.get("must_avoid", [])
        if isinstance(item, str)
    }

    for turn in range(1, max_module_invocations + 1):
        remaining_targets = set(goal.get("target_state", [])) - state
        candidates = shortlist_candidates(
            modules_doc=modules_doc_for_goal,
            state=state,
            remaining_targets=remaining_targets,
            theme=goal["theme"],
            candidate_limit=args.candidate_limit,
            decoy_quota=args.decoy_quota,
            decoy_insert_rank=args.decoy_insert_rank,
            backward_depth=args.target_backward_depth,
            failed_modules=failed_modules,
            successful_modules=successful_modules,
            remaining_invocations=max_module_invocations - turn + 1,
            allowed_module_ids=planning_allowed_module_ids,
            forbidden_modules=forbidden_modules,
            forbidden_predicates=forbidden_predicates,
        )

        selection_event = {
            "turn": turn,
            "module_policy": args.module_policy,
            "state_before": sorted(state),
            "remaining_targets": sorted(remaining_targets),
            "remaining_targets_before": sorted(remaining_targets),
            "successful_modules_before": list(successful_modules),
            "failed_modules_before": sorted(failed_modules),
            "candidate_count": len(candidates),
            "candidate_module_ids": [item["module_id"] for item in candidates],
            "candidate_details": [dict(item.get("_candidate_trace", {})) for item in candidates],
            "decoy_quota": args.decoy_quota,
            "decoy_insert_rank": args.decoy_insert_rank,
        }

        try:
            if args.module_policy == "reference":
                chosen_module_id, raw_decision, decision_meta = choose_reference_next_module(
                    oracle,
                    successful_modules,
                    successful_invocations,
                )
            elif args.module_policy == "heuristic":
                chosen_module_id, raw_decision, decision_meta = choose_heuristic_next_module(goal, state, candidates)
            else:
                chosen_module_id, raw_decision, decision_meta = select_next_module(
                    client=client,
                    goal=goal,
                    state=state,
                    candidates=candidates,
                    successful_modules=successful_modules,
                    failed_modules=failed_modules,
                    temperature=args.module_temperature,
                    max_tokens=args.module_max_tokens,
                )
        except Exception as exc:
            selection_event.update(
                {
                    "raw_decision": "",
                    "planner_raw_choice": "",
                    "chosen_module_id": "ERROR",
                    "module_id": "ERROR",
                    "decision_meta": {
                        "decision_source": args.module_policy,
                        "decision_error": exception_payload(exc),
                    },
                    "selection_error": exception_payload(exc),
                    "state_after": sorted(state),
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                }
            )
            selection_trace.append(selection_event)
            break

        selected_candidate = next(
            (dict(item.get("_candidate_trace", {})) for item in candidates if item["module_id"] == chosen_module_id),
            None,
        )
        selection_event.update(
            {
                "raw_decision": raw_decision,
                "planner_raw_choice": raw_decision,
                "chosen_module_id": chosen_module_id,
                "module_id": chosen_module_id,
                "decision_meta": decision_meta,
                "selected_candidate": selected_candidate,
                "selected_candidate_rank": selected_candidate.get("rank") if selected_candidate else None,
            }
        )

        if chosen_module_id == "DONE":
            selection_event.update(
                {
                    "terminated": True,
                    "state_after": sorted(state),
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                }
            )
            selection_trace.append(selection_event)
            break
        if chosen_module_id not in modules_by_id:
            failed_modules.add(chosen_module_id)
            selection_event.update(
                {
                    "selection_error": {
                        "type": "UnknownModule",
                        "message": f"unknown module selected: {chosen_module_id}",
                    },
                    "state_after": sorted(state),
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                }
            )
            selection_trace.append(selection_event)
            break

        module = modules_by_id[chosen_module_id]
        state_before = set(state)
        state_before_sorted = sorted(state_before)
        binding_payload = None
        staged = None
        try:
            binding_payload = resolve_execution_binding(
                chosen_module_id,
                oracle,
                bindings_by_module,
                used_invocations,
                forced_invocation_id=str(decision_meta.get("reference_invocation_id") or ""),
            )
            binding_payload = apply_cross_task_parameter_dependencies(
                chosen_module_id,
                binding_payload,
                executed_modules,
                runtime_root,
            )
            if binding_payload.get("invocation_id"):
                used_invocations.add(binding_payload["invocation_id"])

            task_result, staged = execute_atomic_module(
                module=module,
                binding_payload=binding_payload,
                goal=goal,
                stage_root=stage_root,
                client=client,
                atomic_policy=args.atomic_policy,
                atomic_max_steps=args.atomic_max_steps,
                repeat_fail_threshold=args.atomic_repeat_fail_threshold,
                headless=args.headless,
                verbose=args.verbose,
                invocation_counter=turn,
            )
        except Exception as exc:
            failed_modules.add(chosen_module_id)
            error_result = {
                "success": False,
                "end_reason": "exception",
                "failure_category": type(exc).__name__,
                "steps_executed": 0,
                "verify_error": "",
                "step_error_message": str(exc),
                "raw_output": "",
            }
            executed_modules.append(
                {
                    "module_id": chosen_module_id,
                    "binding_id": binding_payload["binding_id"] if binding_payload else "",
                    "status": "error",
                    "parameter_values": binding_payload["parameter_values"] if binding_payload else {},
                    "invocation_id": binding_payload.get("invocation_id") if binding_payload else "",
                    "notes": binding_payload["description"] if binding_payload else "",
                    "task_dir": binding_payload["task_dir"] if binding_payload else "",
                    "binding_task_id": binding_payload["binding_task_id"] if binding_payload else "",
                    "instantiated_task_spec": staged["task_spec_path"] if staged else "",
                    "instantiated_oracle_trace": staged["oracle_trace_path"] if staged else "",
                    "dependency_parameter_updates": (
                        binding_payload.get("dependency_parameter_updates", []) if binding_payload else []
                    ),
                    "state_before": state_before_sorted,
                    "state_after": state_before_sorted,
                    "module_decision_raw_output": raw_decision,
                    "atomic_result": summarize_atomic_result(error_result),
                    "execution_exception": exception_payload(exc),
                }
            )
            selection_event.update(
                {
                    "binding": (
                        {
                            "binding_id": binding_payload["binding_id"],
                            "binding_task_id": binding_payload["binding_task_id"],
                            "task_dir": binding_payload["task_dir"],
                            "invocation_id": binding_payload.get("invocation_id") or f"{goal['goal_id']}-R{turn}",
                            "dependency_parameter_updates": binding_payload.get("dependency_parameter_updates", []),
                        }
                        if binding_payload
                        else {}
                    ),
                    "execution_exception": exception_payload(exc),
                    "atomic_result": summarize_atomic_result(error_result),
                    "state_after": state_before_sorted,
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                    "state_delta_added": [],
                    "state_delta_removed": [],
                }
            )
            selection_trace.append(selection_event)
            break

        success = bool(task_result.get("success"))
        if success:
            successful_modules.append(chosen_module_id)
            if binding_payload.get("invocation_id"):
                successful_invocations.add(binding_payload["invocation_id"])
            delta = float(module.get("constraints", {}).get("budget_delta", 0.0) or 0.0)
            if delta < 0:
                actual_budget_spend += -delta
            actual_step_count += int(task_result.get("steps_executed") or module.get("constraints", {}).get("estimated_steps", 0) or 0)
            state = apply_effects(state, module)
        else:
            failed_modules.add(chosen_module_id)
            actual_step_count += int(task_result.get("steps_executed") or 0)

        atomic_result_summary = summarize_atomic_result(task_result)
        state_after_sorted = sorted(state)

        executed_modules.append(
            {
                "module_id": chosen_module_id,
                "binding_id": binding_payload["binding_id"],
                "status": "success" if success else "failed",
                "parameter_values": binding_payload["parameter_values"],
                "invocation_id": binding_payload.get("invocation_id") or "",
                "notes": binding_payload["description"],
                "task_dir": binding_payload["task_dir"],
                "binding_task_id": binding_payload["binding_task_id"],
                "instantiated_task_spec": staged["task_spec_path"] if staged else "",
                "instantiated_oracle_trace": staged["oracle_trace_path"] if staged else "",
                "dependency_parameter_updates": binding_payload.get("dependency_parameter_updates", []),
                "state_before": state_before_sorted,
                "state_after": state_after_sorted,
                "module_decision_raw_output": raw_decision,
                "atomic_result": atomic_result_summary,
            }
        )
        selection_event.update(
            {
                "binding": {
                    "binding_id": binding_payload["binding_id"],
                    "binding_task_id": binding_payload["binding_task_id"],
                    "task_dir": binding_payload["task_dir"],
                    "invocation_id": binding_payload.get("invocation_id") or f"{goal['goal_id']}-R{turn}",
                    "dependency_parameter_updates": binding_payload.get("dependency_parameter_updates", []),
                },
                "atomic_result": atomic_result_summary,
                "state_after": state_after_sorted,
                "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                "state_delta_added": sorted(state - state_before),
                "state_delta_removed": sorted(state_before - state),
            }
        )
        selection_trace.append(selection_event)

        if not success and args.module_policy == "reference":
            break
        if success and set(goal.get("target_state", [])) <= state:
            break

    trace = {
        "goal_id": goal["goal_id"],
        "selected_path": args.module_policy,
        "starting_state_override": goal.get("initial_world_state", []),
        "final_state_override": sorted(state),
        "actual_step_count": actual_step_count,
        "actual_budget_spend": actual_budget_spend,
        "actual_elapsed_hours": (time.time() - start_ts) / 3600.0,
        "executed_modules": executed_modules,
    }
    evaluation = evaluate_episode(goal, oracle, trace, modules_doc_for_goal)

    dump_json(episode_root / "workflow_execution_trace.json", trace)
    dump_json(episode_root / "workflow_execution_evaluation.json", evaluation)
    dump_json(episode_root / "workflow_module_selection_trace.json", selection_trace)

    record = {
        "goal_id": goal["goal_id"],
        "theme": goal["theme"],
        "blueprint_id": goal_ref["blueprint_id"],
        "prompt_difficulty": prompt_difficulty,
        "prompt_difficulty_tier": prompt_difficulty.get("tier", "easy"),
        "success": evaluation["final_success"],
        "semantic_success": evaluation.get("semantic_final_success", evaluation["final_success"]),
        "strict_path_success": evaluation.get("strict_path_success", evaluation["final_success"]),
        "success_type": evaluation["success_type"],
        "target_state_coverage": evaluation["target_state_coverage"],
        "composite_score": evaluation["score_breakdown"]["composite_score"],
        "attempted_module_invocations": evaluation["resource_usage"]["attempted_module_invocations"],
        "actual_step_count": evaluation["resource_usage"]["actual_step_count"],
        "used_reference_path": evaluation["used_reference_path"],
        "hard_constraint_violations": evaluation["hard_constraint_violations"],
        "route_constraint_violations": evaluation.get("route_constraint_violations", []),
        "route_required_module_misses": evaluation.get("route_required_module_misses", []),
        "invalid_transition_count": evaluation["invalid_transition_count"],
        "output_dir": str(episode_root),
    }
    dump_json(episode_root / "workflow_run_summary.json", record)
    return record


def render_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Workflow Benchmark Run",
        "",
        f"- batch_root: `{summary['batch_root']}`",
        f"- split: `{summary['split']}`",
        f"- module_policy: `{summary['module_policy']}`",
        f"- atomic_policy: `{summary['atomic_policy']}`",
        f"- prompt_mode: `{summary.get('prompt_mode', 'active')}`",
        f"- runtime_isolation: `{summary['runtime_isolation']}`",
        f"- agent_backend: `{summary['agent_backend']}`",
        f"- agent_model: `{summary['agent_model']}`",
        f"- total_goals: {summary['total_goals']}",
        f"- final_success_count: {summary['final_success_count']}",
        f"- final_success_rate: {summary['final_success_rate']:.4f}",
        f"- strict_path_success_count: {summary.get('strict_path_success_count', summary['final_success_count'])}",
        f"- strict_path_success_rate: {summary.get('strict_path_success_rate', summary['final_success_rate']):.4f}",
        f"- average_composite_score: {summary['average_composite_score']:.4f}",
        f"- runtime_note: {summary['runtime_note']}",
        "",
        "## Success Types",
    ]
    for key, value in sorted(summary["success_type_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Per Theme"]
    for theme, item in sorted(summary["per_theme"].items()):
        lines.append(
            f"- `{theme}`: {item['success_count']}/{item['goal_count']} semantic success, "
            f"strict_path={item.get('strict_path_success_count', item['success_count'])}/{item['goal_count']}, "
            f"avg_score={item['average_composite_score']:.4f}"
        )
    if summary.get("per_prompt_difficulty"):
        lines += ["", "## Per Prompt Difficulty"]
        for tier, item in sorted(summary["per_prompt_difficulty"].items()):
            lines.append(
                f"- `{tier}`: {item['success_count']}/{item['goal_count']} semantic success, "
                f"strict_path={item.get('strict_path_success_count', item['success_count'])}/{item['goal_count']}, "
                f"avg_score={item['average_composite_score']:.4f}"
            )
    if "completed_goals" in summary:
        lines += [
            "",
            "## Progress",
            f"- completed_goals: {summary['completed_goals']}",
            f"- is_complete: {summary.get('is_complete', False)}",
        ]
    path.write_text("\n".join(lines) + "\n")


def build_summary(
    *,
    batch_root: Path,
    split: str,
    args: argparse.Namespace,
    client: Any,
    records: list[dict[str, Any]],
    planned_total_goals: int,
    is_complete: bool,
) -> dict[str, Any]:
    success_type_counts = Counter(item["success_type"] for item in records)
    per_theme_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_prompt_difficulty_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        per_theme_buckets[item["theme"]].append(item)
        per_prompt_difficulty_buckets[item.get("prompt_difficulty_tier", "easy")].append(item)

    per_theme = {}
    for theme, items in per_theme_buckets.items():
        per_theme[theme] = {
            "goal_count": len(items),
            "success_count": sum(1 for item in items if item["success"]),
            "strict_path_success_count": sum(1 for item in items if item.get("strict_path_success", item["success"])),
            "average_composite_score": sum(item["composite_score"] for item in items) / len(items),
        }

    per_prompt_difficulty = {}
    for tier, items in per_prompt_difficulty_buckets.items():
        per_prompt_difficulty[tier] = {
            "goal_count": len(items),
            "success_count": sum(1 for item in items if item["success"]),
            "strict_path_success_count": sum(1 for item in items if item.get("strict_path_success", item["success"])),
            "average_composite_score": sum(item["composite_score"] for item in items) / len(items),
        }

    completed_goals = len(records)
    success_count = sum(1 for item in records if item["success"])
    strict_path_success_count = sum(1 for item in records if item.get("strict_path_success", item["success"]))
    summary = {
        "version": 1,
        "batch_root": str(batch_root),
        "split": split,
        "module_policy": args.module_policy,
        "atomic_policy": args.atomic_policy,
        "prompt_mode": args.prompt_mode,
        "runtime_isolation": args.runtime_isolation,
        "runtime_note": RUNTIME_ISOLATION_NOTES[args.runtime_isolation],
        "agent_backend": getattr(client, "backend_name", "none") if client else "none",
        "agent_model": getattr(client, "model", "") if client else "",
        "total_goals": planned_total_goals if planned_total_goals else completed_goals,
        "completed_goals": completed_goals,
        "is_complete": is_complete,
        "final_success_count": success_count,
        "final_success_rate": (success_count / completed_goals) if completed_goals else 0.0,
        "strict_path_success_count": strict_path_success_count,
        "strict_path_success_rate": (strict_path_success_count / completed_goals) if completed_goals else 0.0,
        "average_composite_score": (sum(item["composite_score"] for item in records) / completed_goals) if completed_goals else 0.0,
        "success_type_counts": dict(sorted(success_type_counts.items())),
        "per_theme": per_theme,
        "per_prompt_difficulty": per_prompt_difficulty,
        "records": records,
    }
    return summary


def main() -> None:
    args = parse_args()
    if args.runtime_isolation == "shared":
        print(
            "[workflow-benchmark] WARNING: shared runtime isolation reuses a single runtime and server "
            "across goals. This mode is for debugging only and can contaminate benchmark results. "
            "Use --runtime-isolation per_goal for official numbers.",
            file=sys.stderr,
        )

    batch_root = Path(args.batch_root).resolve()
    split_root = batch_root / args.split
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_root = Path(args.runtime_root).resolve()
    snapshot_root = output_root / "_runtime_snapshot"
    snapshot_runtime(runtime_root, snapshot_root)

    modules_doc = load_json(Path(args.modules))
    bindings_doc = load_json(Path(args.bindings))
    goal_refs = collect_goals(
        batch_root,
        args.split,
        args.goal_id,
        args.limit,
        args.prompt_difficulty,
    )

    client = None
    if args.module_policy == "llm" or args.atomic_policy == "agent":
        client = build_client()

    records = []
    goal_output_root = output_root / args.split
    planned_total_goals = len(goal_refs)

    def _write_partial_summary() -> None:
        partial_summary = build_summary(
            batch_root=batch_root,
            split=args.split,
            args=args,
            client=client,
            records=records,
            planned_total_goals=planned_total_goals,
            is_complete=False,
        )
        dump_json(output_root / f"{args.split}_summary.partial.json", partial_summary)
        render_markdown(output_root / f"{args.split}_summary.partial.md", partial_summary)

    if args.runtime_isolation == "shared":
        for goal_ref in goal_refs:
            records.append(
                run_single_goal(
                    goal_ref=goal_ref,
                    split_root=split_root,
                    output_root=goal_output_root,
                    runtime_root=runtime_root,
                    snapshot_root=snapshot_root,
                    modules_doc=modules_doc,
                    bindings_doc=bindings_doc,
                    client=client,
                    args=args,
                )
            )
            _write_partial_summary()
    else:
        isolated_root = output_root / "_goal_runtimes"
        isolated_root.mkdir(parents=True, exist_ok=True)
        for goal_ref in goal_refs:
            goal_id = goal_ref["goal_id"]
            goal_runtime_root = isolated_root / goal_id / "runtime"
            goal_server_log = isolated_root / goal_id / "server.log"
            _prepare_goal_runtime(goal_runtime_root, snapshot_root)
            proc = None
            try:
                proc, goal_base_url = _start_goal_server(goal_runtime_root, goal_server_log)
                env_updates = {
                    "WEBAGENT_RUNTIME_ROOT": str(goal_runtime_root),
                    "WEBAGENT_SERVER_BASE_URL": goal_base_url,
                    "WEBAGENT_SERVER_PORT": goal_base_url.rsplit(":", 1)[-1],
                }
                with _temporary_process_env(env_updates), _pushd(goal_runtime_root):
                    records.append(
                        run_single_goal(
                            goal_ref=goal_ref,
                            split_root=split_root,
                            output_root=goal_output_root,
                            runtime_root=goal_runtime_root,
                            snapshot_root=snapshot_root,
                            modules_doc=modules_doc,
                            bindings_doc=bindings_doc,
                            client=client,
                            args=args,
                        )
                    )
                    _write_partial_summary()
            finally:
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        proc.kill()

    summary = build_summary(
        batch_root=batch_root,
        split=args.split,
        args=args,
        client=client,
        records=records,
        planned_total_goals=planned_total_goals,
        is_complete=True,
    )

    dump_json(output_root / f"{args.split}_summary.json", summary)
    render_markdown(output_root / f"{args.split}_summary.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
