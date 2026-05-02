#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
TASKS_ROOT = ROOT / "tasks"
CATALOG_PATH = TASKS_ROOT / "task_module_catalog.json"
OUTPUT_PATH = TASKS_ROOT / "workflow_module_library.json"
BINDINGS_OUTPUT_PATH = TASKS_ROOT / "workflow_module_bindings.json"
PREDICATE_VOCAB_PATH = TASKS_ROOT / "workflow_predicate_vocabulary.json"
SUMMARY_PATH = ROOT / ".task_sync_meta" / "workflow_module_library_summary.md"

THEME_BY_PREFIX = {
    "A": "newcomer",
    "B": "daily",
    "C": "support",
    "D": "finance",
    "E": "travel",
    "F": "career",
    "G": "health",
    "H": "government",
    "I": "home",
    "J": "education",
    "K": "social",
    "L": "security",
    "M": "crisis",
    "Z": "composite",
}

RISK_BY_THEME = {
    "newcomer": "medium",
    "daily": "low",
    "support": "medium",
    "finance": "high",
    "travel": "medium",
    "career": "medium",
    "health": "medium",
    "government": "medium",
    "home": "medium",
    "education": "low",
    "social": "low",
    "security": "high",
    "crisis": "high",
    "composite": "high",
}


def _titleize(slug: str) -> str:
    parts = slug.split("_")
    out = []
    for part in parts:
        if part == "2fa":
            out.append("2FA")
        elif part == "ebook":
            out.append("eBook")
        else:
            out.append(part.capitalize())
    return " ".join(out)


def _clean_goal(text: str) -> str:
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


def _extract_mem_paths(criteria: list[str]) -> list[str]:
    joined = "\n".join(criteria)
    return sorted(set(re.findall(r"mem\('([^']+)'\)", joined)))


def _extract_env_paths(criteria: list[str]) -> list[str]:
    joined = "\n".join(criteria)
    return sorted(set(re.findall(r"json\('env','([^']+)'\)", joined)))


def _extract_observables(criteria: list[str]) -> list[str]:
    observables = []
    for item in criteria:
        if any(token in item for token in ("exists(", "text(", "url().includes(", "json('env'")):
            observables.append(item)
    return observables


def _parameter_replacements(inputs: dict[str, Any]) -> list[tuple[str, str]]:
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


def _parameterize_text(text: str, inputs: dict[str, Any]) -> str:
    result = text
    for raw, placeholder in _parameter_replacements(inputs):
        result = re.sub(re.escape(raw), placeholder, result)
    return result


def _normalize_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _infer_parameter_defaults(inputs: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    defaults = dict(inputs)
    normalized_keys = {key: _normalize_identifier(key) for key in inputs}
    for step in steps:
        selector = step.get("selector", "")
        value = step.get("value")
        if not selector or value in (None, ""):
            continue
        normalized_selector = _normalize_identifier(selector)
        for key, normalized_key in normalized_keys.items():
            if normalized_key and normalized_key in normalized_selector:
                defaults[key] = value
    return defaults


def _infer_param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) or isinstance(value, float):
        return "number"
    if isinstance(value, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return "date"
        return "string"
    return "json"


def _build_parameters(inputs: dict[str, Any], include_defaults: bool = False) -> list[dict[str, Any]]:
    params = []
    for key, value in inputs.items():
        entry = {
            "name": key,
            "type": _infer_param_type(value),
            "required": True,
            "description": f"Instantiated input slot: {key}",
        }
        if include_defaults:
            entry["default_value"] = value
        params.append(entry)
    return params


def _merge_parameter_schemas(parameter_defaults_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for defaults in parameter_defaults_list:
        for param in _build_parameters(defaults, include_defaults=False):
            merged.setdefault(param["name"], param)
    return [merged[name] for name in sorted(merged)]


def _extract_numeric_budget_hint(inputs: dict[str, Any]) -> float:
    skip_tokens = ("id", "zip", "plate", "phone", "account", "duration", "month", "year", "code")
    value_tokens = ("price", "total", "amount", "value", "budget", "limit", "spend", "donation", "fee", "cost")
    numeric_values = []
    for key, value in inputs.items():
        lower_key = key.lower()
        if any(token in lower_key for token in skip_tokens):
            continue
        if not any(token in lower_key for token in value_tokens):
            continue
        if isinstance(value, (int, float)):
            numeric_values.append(float(value))
    return max(numeric_values) if numeric_values else 0.0


def _estimate_budget_delta(module_group: str, goal: str, inputs: dict[str, Any]) -> float:
    text = f"{module_group} {goal}".lower()
    dollar_amounts = [float(x) for x in re.findall(r"\$(\d+(?:\.\d+)?)", goal)]
    amount = max(dollar_amounts) if dollar_amounts else _extract_numeric_budget_hint(inputs)

    positive_markers = ("refund", "claim", "sale", "sell", "donation", "loan", "growth", "pool")
    negative_markers = (
        "buy",
        "purchase",
        "pay",
        "book",
        "order",
        "rent",
        "apply",
        "topup",
        "subscription",
        "membership",
        "repair",
    )

    if any(marker in text for marker in positive_markers):
        return amount
    if any(marker in text for marker in negative_markers):
        return -amount
    return 0.0


def _estimate_time_delta_hours(module_group: str) -> float:
    text = module_group.lower()
    if any(token in text for token in ("arrival", "tracking", "recovery", "renew", "long_haul")):
        return 24.0
    if any(token in text for token in ("appointment", "repair", "claim", "report", "transfer", "check_in")):
        return 2.0
    return 1.0


def _collect_predicates(modules: list[dict[str, Any]]) -> list[str]:
    predicates = set()
    for module in modules:
        for key in ("all_of", "any_of", "none_of"):
            predicates.update(module["requires"][key])
        predicates.update(module["effects"]["adds"])
        predicates.update(module["effects"]["removes"])
    return sorted(predicates)


MODULE_OVERRIDES = {
    "find_home": {
        "requires": {"all_of": [], "any_of": [], "none_of": ["lease_active"]},
        "effects": {"adds": ["lease_active", "address_known", "housing_secured"], "removes": []},
    },
    "bank_opening": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": ["bank_account_active"]},
        "effects": {"adds": ["bank_account_active", "payment_method_available"], "removes": []},
    },
    "utility_setup": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": ["utilities_active"]},
        "effects": {"adds": ["utilities_active", "electricity_active", "residency_record_verified", "address_confirmation_verified"], "removes": []},
    },
    "address_proof": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["address_proof_available", "residency_record_verified", "address_confirmation_verified"], "removes": []},
    },
    "address_change": {
        "requires": {"all_of": ["lease_active"], "any_of": ["address_proof_available", "residency_record_verified"], "none_of": []},
        "effects": {"adds": ["mailing_address_current", "address_records_aligned", "permit_readiness_verified"], "removes": []},
    },
    "mobile_plan_signup": {
        "requires": {"all_of": [], "any_of": [], "none_of": ["mobile_service_active"]},
        "effects": {"adds": ["mobile_service_active"], "removes": []},
    },
    "mobile_plan_switch": {
        "requires": {"all_of": ["mobile_service_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["mobile_plan_updated"], "removes": []},
    },
    "shopping": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["shop_order_exists", "shop_order_pending"], "removes": []},
        "may_trigger": ["payment_blocked_if_liquidity_frozen"],
    },
    "track_orders": {
        "requires": {"all_of": ["shop_order_exists"], "any_of": [], "none_of": []},
        "effects": {"adds": ["order_tracking_opened", "order_followup_prepared"], "removes": []},
    },
    "order_arrival": {
        "requires": {"all_of": ["shop_order_exists"], "any_of": [], "none_of": []},
        "effects": {"adds": ["shop_order_delivered", "delivery_visibility_confirmed"], "removes": ["shop_order_pending"]},
    },
    "price_protection": {
        "requires": {"all_of": [], "any_of": ["shop_order_exists", "shop_order_delivered"], "none_of": []},
        "effects": {"adds": ["price_protection_submitted", "order_price_secured"], "removes": []},
    },
    "return": {
        "requires": {"all_of": ["shop_order_delivered"], "any_of": [], "none_of": []},
        "effects": {"adds": ["return_requested", "post_purchase_remedy_requested"], "removes": []},
    },
    "warranty_claim": {
        "requires": {"all_of": ["shop_order_delivered"], "any_of": [], "none_of": []},
        "effects": {"adds": ["warranty_claim_submitted", "post_purchase_remedy_requested"], "removes": []},
    },
    "subscription_refund": {
        "requires": {"all_of": ["subscription_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["refund_requested", "subscription_exit_processed"], "removes": []},
    },
    "food_delivery": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["food_order_pending"], "removes": []},
    },
    "fresh_subscription": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["subscription_active"], "removes": []},
    },
    "housekeeping_booking": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["housekeeping_service_booked", "service_stack_prepared"], "removes": []},
    },
    "grocery_run": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["grocery_order_pending", "daily_order_bundle_prepared"], "removes": []},
    },
    "coupon_management": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["coupon_available", "order_price_secured", "service_stack_prepared", "daily_order_bundle_prepared"], "removes": []},
    },
    "second_hand_item_listing": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["market_listing_active", "resale_listing_activated"], "removes": []},
    },
    "second_hand_sale": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["sale_listing_active", "resale_listing_activated"], "removes": []},
    },
    "autopay": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["autopay_enabled"], "removes": []},
    },
    "complex_autopay": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["autopay_enabled", "payment_stack_prepared"], "removes": []},
    },
    "card_replacement": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["replacement_card_requested"], "removes": []},
    },
    "dispute_transaction": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["transaction_dispute_submitted"], "removes": []},
    },
    "investment_account": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": ["investment_account_active"]},
        "effects": {"adds": ["investment_account_active"], "removes": []},
    },
    "transfer_funds": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["transfer_completed", "payment_stack_prepared", "tax_funding_prepared"], "removes": []},
    },
    "tax_preparation": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["tax_documents_prepared", "tax_funding_prepared"], "removes": []},
    },
    "file_taxes": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["tax_filing_submitted"], "removes": []},
    },
    "bill_aggregation": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["bills_aggregated", "account_issue_triaged"], "removes": []},
    },
    "book_flight": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["flight_booked", "travel_booking_confirmed"], "removes": []},
    },
    "book_hotel": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["hotel_booked", "travel_booking_confirmed"], "removes": []},
    },
    "check_in": {
        "requires": {"all_of": ["flight_booked"], "any_of": [], "none_of": []},
        "effects": {"adds": ["check_in_completed"], "removes": []},
    },
    "flight_rebooking": {
        "requires": {"all_of": ["flight_booked"], "any_of": [], "none_of": []},
        "effects": {"adds": ["itinerary_rebooked"], "removes": []},
    },
    "airport_transfer": {
        "requires": {"all_of": ["flight_booked"], "any_of": [], "none_of": []},
        "effects": {"adds": ["airport_transfer_arranged"], "removes": []},
    },
    "expense_report": {
        "requires": {"all_of": [], "any_of": ["flight_booked", "hotel_booked"], "none_of": []},
        "effects": {"adds": ["expense_report_submitted"], "removes": []},
    },
    "commute_route": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["commute_route_checked"], "removes": []},
    },
    "transport_topup": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["transit_balance_topped_up"], "removes": []},
    },
    "doctor_appt": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["medical_appointment_booked"], "removes": []},
    },
    "insurance_policy": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["insurance_policy_active", "coverage_path_active"], "removes": []},
    },
    "medical_claim": {
        "requires": {"all_of": [], "any_of": ["insurance_policy_active", "health_plan_active"], "none_of": []},
        "effects": {"adds": ["medical_claim_submitted"], "removes": []},
    },
    "health_plan_activation": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["health_plan_active", "care_continuity_established", "coverage_path_active"], "removes": []},
    },
    "prescription_refill": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["prescription_refilled", "care_continuity_established"], "removes": []},
    },
    "vaccine_mgmt": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["vaccination_record_updated"], "removes": []},
    },
    "parking_permit_application": {
        "requires": {"all_of": ["address_known"], "any_of": [], "none_of": ["parking_permit_active"]},
        "effects": {"adds": ["parking_permit_active"], "removes": []},
    },
    "permit_renewal": {
        "requires": {"all_of": ["parking_permit_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["permit_renewed", "local_vehicle_compliance_verified"], "removes": []},
    },
    "renew_permit": {
        "requires": {"all_of": ["parking_permit_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["permit_renewed", "local_vehicle_compliance_verified"], "removes": []},
    },
    "permit_app": {
        "requires": {"all_of": ["address_known"], "any_of": [], "none_of": []},
        "effects": {"adds": ["permit_application_submitted"], "removes": []},
    },
    "library_service": {
        "requires": {"all_of": ["education_account_activated"], "any_of": [], "none_of": []},
        "effects": {"adds": ["library_pickup_reserved", "assignment_resources_provisioned"], "removes": []},
    },
    "course_enrollment": {
        "requires": {"all_of": ["education_account_activated"], "any_of": [], "none_of": []},
        "effects": {"adds": ["course_enrolled"], "removes": []},
    },
    "submit_assignment": {
        "requires": {"all_of": ["course_enrolled"], "any_of": [], "none_of": []},
        "effects": {"adds": ["assignment_submitted"], "removes": []},
    },
    "download_cert": {
        "requires": {"all_of": [], "any_of": ["course_enrolled", "skill_certified"], "none_of": []},
        "effects": {"adds": ["certificate_downloaded"], "removes": []},
    },
    "buy_ebook": {
        "requires": {"all_of": ["education_account_activated"], "any_of": [], "none_of": []},
        "effects": {"adds": ["ebook_owned", "assignment_resources_provisioned"], "removes": []},
    },
    "skill_certification": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["skill_certified"], "removes": []},
    },
    "event_tickets": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["event_ticket_booked"], "removes": []},
    },
    "password_reset_request": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["password_reset_code_requested"], "removes": []},
    },
    "password_reset_completion": {
        "requires": {"all_of": ["password_reset_code_requested"], "any_of": [], "none_of": []},
        "effects": {"adds": ["password_reset_completed"], "removes": []},
    },
    "password_recovery_e2e": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["password_reset_completed", "account_access_restored", "account_access_contained"], "removes": []},
    },
    "password_manager": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["credential_vault_updated", "security_hardening_completed", "access_surface_reviewed"], "removes": []},
    },
    "privacy_settings": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["privacy_settings_updated", "access_surface_reviewed", "account_exit_prepared"], "removes": []},
    },
    "2fa_setup": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["two_factor_enabled"], "removes": []},
    },
    "2fa_device": {
        "requires": {"all_of": ["two_factor_enabled"], "any_of": [], "none_of": []},
        "effects": {"adds": ["two_factor_device_updated"], "removes": []},
    },
    "security_rotation": {
        "requires": {"all_of": ["two_factor_enabled"], "any_of": [], "none_of": []},
        "effects": {"adds": ["secret_rotated", "security_hardening_completed"], "removes": []},
    },
    "security_audit": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["security_audit_completed"], "removes": []},
    },
    "download_data": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["account_data_exported", "account_exit_prepared"], "removes": []},
    },
    "data_deletion": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["deletion_request_submitted"], "removes": []},
    },
    "lost_card_freeze": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": ["card_frozen"]},
        "effects": {"adds": ["card_frozen", "crisis_intake_completed", "account_access_contained"], "removes": ["payment_method_available"]},
        "may_trigger": ["liquidity_frozen"],
    },
    "urgent_loan": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["emergency_liquidity_secured"], "removes": []},
    },
    "illness_reporting": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["illness_report_submitted", "crisis_intake_completed"], "removes": []},
    },
    "supply_disruption": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["supply_issue_reported", "crisis_intake_completed"], "removes": []},
    },
    "house_repair": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["home_repair_requested"], "removes": []},
    },
    "camera_check": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["camera_config_verified", "home_service_monitored"], "removes": []},
    },
    "smart_meter": {
        "requires": {"all_of": ["utilities_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["smart_meter_configured", "energy_control_configured"], "removes": []},
    },
    "smart_bulb_setup": {
        "requires": {"all_of": ["lease_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["smart_bulb_configured", "home_device_readiness_confirmed"], "removes": []},
    },
    "thermostat_schedule": {
        "requires": {"all_of": ["utilities_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["thermostat_schedule_configured"], "removes": []},
    },
    "firmware_update": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["firmware_updated", "home_device_readiness_confirmed", "home_service_monitored"], "removes": []},
    },
    "energy_optimize": {
        "requires": {"all_of": ["utilities_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["energy_usage_optimized", "energy_control_configured"], "removes": []},
    },
    "charity_donation": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["donation_completed", "social_contribution_completed"], "removes": []},
    },
    "gift_pooling": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["gift_pool_created", "social_contribution_completed", "social_commitment_recorded"], "removes": []},
    },
    "rsvp_event": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["event_rsvp_completed", "social_commitment_recorded"], "removes": []},
    },
    "roommate_expense_split": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["shared_expenses_settled"], "removes": []},
    },
    "conference_reg": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["conference_expense_logged", "conference_admin_recorded"], "removes": []},
    },
    "conference_registration": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["conference_registered", "conference_admin_recorded", "deadline_coordination_recorded"], "removes": []},
    },
    "job_search": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["job_application_followup_created"], "removes": []},
    },
    "update_linkedin": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["professional_profile_updated", "career_signal_strengthened"], "removes": []},
    },
    "email_tracking": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["email_thread_tracked", "career_signal_strengthened"], "removes": []},
    },
    "email_calendar": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["calendar_event_synced"], "removes": []},
    },
    "calendar_aggregation": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["calendar_event_created", "deadline_coordination_recorded"], "removes": []},
    },
    "budget_limit_update": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["budget_limit_updated"], "removes": []},
    },
    "cancel_subscription": {
        "requires": {"all_of": [], "any_of": [], "none_of": ["subscription_canceled"]},
        "effects": {"adds": ["subscription_canceled", "subscription_exit_processed"], "removes": ["subscription_active"]},
    },
    "check_balance": {
        "requires": {"all_of": ["bank_account_active"], "any_of": [], "none_of": []},
        "effects": {"adds": ["account_balance_reviewed", "account_issue_triaged"], "removes": []},
    },
    "billing_review": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["bills_reviewed", "permit_readiness_verified"], "removes": []},
    },
    "contact_support": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["support_contacted", "support_ticket_opened"], "removes": []},
    },
    "customer_service": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["support_contacted", "order_status_checked", "delivery_visibility_confirmed", "order_followup_prepared"], "removes": []},
    },
    "gear_rental": {
        "requires": {"all_of": [], "any_of": [], "none_of": ["rental_listing_active"]},
        "effects": {"adds": ["rental_listing_active"], "removes": []},
    },
    "investment_growth": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["investment_account_active", "investment_growth_verified"], "removes": []},
    },
    "lease_contract_registration": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["lease_record_registered", "housing_finance_prepared"], "removes": []},
    },
    "leave_review": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["product_review_submitted"], "removes": []},
    },
    "live_auction": {
        "requires": {"all_of": ["payment_method_available"], "any_of": ["bank_account_active"], "none_of": []},
        "effects": {"adds": ["auction_bid_placed"], "removes": []},
    },
    "logistics_fix": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["logistics_ticket_opened", "support_contacted"], "removes": []},
    },
    "long_haul_trip": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["visa_approved", "flight_booked", "trip_booked", "travel_booking_confirmed", "mobility_clearance_verified"], "removes": []},
    },
    "lease_management_review": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["lease_management_reviewed", "housing_finance_prepared"], "removes": []},
    },
    "movie_tickets": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["event_ticket_booked"], "removes": []},
    },
    "paper_submission": {
        "requires": {"all_of": [], "any_of": [], "none_of": ["paper_submitted"]},
        "effects": {"adds": ["paper_submitted"], "removes": []},
    },
    "receipt_archiving": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["receipt_archived"], "removes": []},
    },
    "reviews_blacklist": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["product_review_submitted", "merchant_blacklisted"], "removes": []},
    },
    "vehicle_address_update": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["vehicle_address_updated", "insurance_notified", "address_records_aligned", "local_vehicle_compliance_verified"], "removes": []},
    },
    "visa_requirements": {
        "requires": {"all_of": [], "any_of": [], "none_of": []},
        "effects": {"adds": ["visa_requirements_checked", "mobility_clearance_verified"], "removes": []},
    },
}


def _default_requires(module_group: str) -> dict[str, list[str]]:
    return {"all_of": [], "any_of": [], "none_of": []}


def _default_effects(module_group: str) -> dict[str, list[str]]:
    return {
        "adds": [],
        "removes": [],
    }


def _merge_state_rules(module_group: str) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    override = MODULE_OVERRIDES.get(module_group, {})
    requires = _default_requires(module_group)
    effects = _default_effects(module_group)
    for key, values in override.get("requires", {}).items():
        requires[key] = sorted(set(requires[key] + values))
    for key, values in override.get("effects", {}).items():
        effects[key] = sorted(set(effects.get(key, []) + values))
    may_trigger = override.get("may_trigger", [])
    return requires, effects, may_trigger


def _build_binding_id(task_dir: str) -> str:
    return f"BIND_{task_dir.upper().replace('-', '_')}"


def _load_member_context(member: dict[str, Any]) -> dict[str, Any]:
    task_dir = member["task_dir"]
    spec = json.loads((TASKS_ROOT / task_dir / "task_spec.json").read_text())
    oracle = json.loads((TASKS_ROOT / task_dir / "oracle_trace.json").read_text())
    return {
        "task_dir": task_dir,
        "task_id": member["task_id"],
        "spec": spec,
        "oracle": oracle,
    }


def _build_core_module(group: dict[str, Any], member_contexts: list[dict[str, Any]]) -> dict[str, Any]:
    first = member_contexts[0]
    prefix = first["task_dir"].split("-", 1)[0][0]
    theme = THEME_BY_PREFIX.get(prefix, "general")
    module_group = group["module_group"]
    requires, state_effects, may_trigger = _merge_state_rules(module_group)

    parameter_defaults_list = [
        _infer_parameter_defaults(ctx["spec"].get("inputs", {}), ctx["oracle"].get("steps", []))
        for ctx in member_contexts
    ]
    estimated_steps = max(1, max(len(ctx["oracle"].get("steps", [])) for ctx in member_contexts))
    budget_candidates = [
        _estimate_budget_delta(module_group, ctx["spec"].get("goal", ""), ctx["spec"].get("inputs", {}))
        for ctx in member_contexts
    ]
    budget_delta = max(budget_candidates, key=lambda value: abs(value)) if budget_candidates else 0.0

    effects = {
        "adds": sorted(set(state_effects["adds"])),
        "removes": sorted(set(state_effects["removes"])),
    }
    if may_trigger:
        effects["may_trigger"] = may_trigger

    return {
        "module_id": f"MODULE_{module_group.upper()}",
        "family": theme,
        "name": _titleize(module_group),
        "requires": requires,
        "effects": effects,
        "constraints": {
            "estimated_steps": estimated_steps,
            "budget_delta": budget_delta,
            "time_delta_hours": _estimate_time_delta_hours(module_group),
            "risk": RISK_BY_THEME.get(theme, "medium"),
        },
        "domains": sorted(
            {
                domain
                for ctx in member_contexts
                for domain in ctx["spec"].get("allowed_domains", [])
            }
        ),
        "parameters": _merge_parameter_schemas(parameter_defaults_list),
        "alternatives": [],
    }


def _build_binding(module_id: str, task_dir: str, task_id: str, spec: dict[str, Any], oracle: dict[str, Any]) -> dict[str, Any]:
    inputs = spec.get("inputs", {})

    success_criteria = spec.get("success_criteria", [])
    steps = oracle.get("steps", [])
    parameter_defaults = _infer_parameter_defaults(inputs, steps)
    writes_memory = _extract_mem_paths(success_criteria)
    writes_env = _extract_env_paths(success_criteria)
    observables = _extract_observables(success_criteria)
    observable_templates = [_parameterize_text(item, parameter_defaults) for item in observables]

    goal = spec.get("goal", "")
    binding = {
        "binding_id": _build_binding_id(task_dir),
        "module_id": module_id,
        "backing_task_id": task_id,
        "task_dir": task_dir,
        "description_template": _parameterize_text(_clean_goal(goal), parameter_defaults),
        "default_parameter_values": parameter_defaults,
        "observable_templates": observable_templates,
        "seed_example": {
            "description": _clean_goal(goal),
            "observables": observables,
        },
        "writes_memory": writes_memory,
        "writes_env": writes_env,
    }
    return binding


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text())
    modules = []
    bindings = []

    for group in catalog["groups"]:
        member_contexts = [_load_member_context(member) for member in group["members"]]
        module = _build_core_module(group, member_contexts)
        modules.append(module)
        for ctx in member_contexts:
            bindings.append(
                _build_binding(
                    module["module_id"],
                    ctx["task_dir"],
                    ctx["task_id"],
                    ctx["spec"],
                    ctx["oracle"],
                )
            )

    modules.sort(key=lambda x: x["module_id"])
    bindings.sort(key=lambda x: x["module_id"])
    library = {
        "version": 4,
        "description": "Core reusable workflow module library for planning, separated from execution bindings.",
        "modules": modules,
    }
    bindings_doc = {
        "version": 3,
        "description": "Template-level execution and evaluation bindings from workflow modules to the current atomic task library, with support for multiple bindings per abstract module.",
        "bindings": bindings,
    }
    OUTPUT_PATH.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")
    BINDINGS_OUTPUT_PATH.write_text(json.dumps(bindings_doc, ensure_ascii=False, indent=2) + "\n")
    predicate_vocab = {
        "version": 1,
        "description": "Canonical shared workflow predicate vocabulary extracted from the core workflow module library.",
        "naming_conventions": {
            "prefer_shared_predicates": True,
            "forbidden_prefixes_in_core_modules": ["module."],
            "forbidden_local_patterns_in_core_modules": ["*_context_available"],
            "discouraged_suffixes": {
                "_ready": "Prefer a concrete result-state name such as *_arranged, *_reserved, *_configured, or *_secured unless the predicate truly denotes a generic prerequisite state."
            },
            "discouraged_tokens": {
                "progress": "Prefer observable milestone states over vague progress markers unless no reusable outcome predicate exists.",
                "available": "Prefer concrete resource or artifact names when possible; keep *_available only for reusable prerequisite artifacts."
            },
            "allowlisted_discouraged_patterns": {
                "_ready": ["education_account_activated"],
                "available": ["address_proof_available", "coupon_available", "payment_method_available"],
                "progress": []
            },
            "preferred_suffixes": {
                "_active": "Durable capability, service, or resource is now in force.",
                "_ready": "Prerequisite preparation is complete and downstream steps may proceed.",
                "_updated": "Existing entity or profile has been modified.",
                "_reviewed": "Information-review step completed with no durable side effect beyond inspection.",
                "_checked": "A lighter-weight inspection or verification step completed.",
                "_requested": "A request has been issued but may still be pending.",
                "_submitted": "A form, report, filing, or application was submitted.",
                "_opened": "A ticket, case, or thread was opened.",
                "_booked": "A booking or reservation has been created.",
                "_approved": "An approval gate has been passed.",
                "_canceled": "A prior service or commitment has been canceled.",
                "_delivered": "A delivery outcome has completed.",
                "_archived": "A document or artifact has been archived."
            }
        },
        "predicates": _collect_predicates(modules),
    }
    PREDICATE_VOCAB_PATH.write_text(json.dumps(predicate_vocab, ensure_ascii=False, indent=2) + "\n")

    theme_counts = {}
    for module in modules:
        theme_counts[module["family"]] = theme_counts.get(module["family"], 0) + 1

    lines = [
        "# Workflow Module Library Summary",
        "",
        f"- modules: {len(modules)}",
        f"- module library: `{OUTPUT_PATH}`",
        f"- module bindings: `{BINDINGS_OUTPUT_PATH}`",
        f"- predicate vocabulary: `{PREDICATE_VOCAB_PATH}`",
        "",
        "## Theme Counts",
    ]
    for theme in sorted(theme_counts):
        lines.append(f"- `{theme}`: {theme_counts[theme]}")
    lines += [
        "",
        "## Notes",
        "- Core workflow modules now contain only planning-relevant semantics.",
        "- Source-task-specific execution and evaluation details have been moved into a separate binding file.",
        "- Remaining refinement should focus on predicate normalization and multi-path alternatives, not on reformatting the library.",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
