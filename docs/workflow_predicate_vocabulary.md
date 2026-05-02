# Workflow Predicate Vocabulary

This file defines the naming discipline for workflow-state predicates used by:

- `/Users/masteryth/Documents/webagent/tasks/workflow_module_library.json`
- `/Users/masteryth/Documents/webagent/tasks/workflow_goal_instances/*.json` (future)
- `/Users/masteryth/Documents/webagent/tasks/workflow_oracles/*.json` (future)

## Purpose

Workflow planning only works if `requires`, `effects`, `initial_world_state`, and `target_state` all speak the same state language.

The rule is simple:

- prefer shared state predicates
- avoid task-local bookkeeping predicates in core modules
- use stable suffixes so new predicates are interpretable without extra documentation

## Core Rules

Use these in core workflow modules:

- shared predicates such as `lease_active`, `payment_method_available`, `support_ticket_opened`

Do not use these in core workflow modules:

- `module.*`
- `*_context_available`

Those local trace fields may still exist in debugging or execution layers, but not in planning semantics.

## Preferred Suffixes

- `_active`: a durable capability, service, resource, or contract is in force
- `_ready`: use sparingly; only when no more concrete result-state exists and the predicate really means generic downstream readiness
- `_updated`: an existing entity or profile has been modified
- `_reviewed`: an information-review step completed
- `_checked`: a lighter inspection or verification step completed
- `_requested`: a request was issued and may still be pending
- `_submitted`: a form, filing, or application was submitted
- `_opened`: a ticket, case, or thread was opened
- `_booked`: a booking or reservation was created
- `_approved`: an approval gate was passed
- `_canceled`: a prior service or commitment was canceled
- `_delivered`: a delivery outcome completed
- `_archived`: a document or artifact was archived

## Design Guidance

- prefer nouns over UI verbs: `support_ticket_opened`, not `click_support_button`
- prefer cross-module state when possible: `bills_reviewed`, not `library_card_seen`
- prefer end-state semantics over page-local semantics: `payment_card_updated`, not `cards_page_saved`
- if two tasks produce the same reusable state, they should use the same predicate
- prefer concrete outcomes over generic readiness:
  - `airport_transfer_arranged`, not `ground_transfer_ready`
  - `library_pickup_reserved`, not `library_reservation_ready`
  - `housing_secured`, not `housing_ready`
  - `transit_balance_topped_up`, not `transit_balance_ready`
  - `smart_meter_configured`, not `smart_meter_ready`
- prefer observable milestones over vague “progress” labels:
  - `job_application_followup_created`, not `job_search_progress`
- prefer service-specific booking states over generic “active” labels:
  - `housekeeping_service_booked`, not `service_booking_active`

## Current Shared Predicate Examples

- housing and address
  - `lease_active`
  - `address_known`
  - `address_proof_available`
  - `mailing_address_current`
  - `lease_record_registered`
  - `lease_management_reviewed`
  - `housing_secured`

- finance and payments
  - `bank_account_active`
  - `payment_method_available`
  - `autopay_enabled`
  - `budget_limit_updated`
  - `payment_card_updated`
  - `account_balance_reviewed`

- support and commerce
  - `support_contacted`
  - `support_ticket_opened`
  - `order_status_checked`
  - `logistics_ticket_opened`
  - `product_review_submitted`
  - `merchant_blacklisted`
  - `shop_order_exists`
  - `shop_order_pending`
  - `shop_order_delivered`

- travel
  - `flight_booked`
  - `hotel_booked`
  - `airport_transfer_arranged`
  - `check_in_completed`
  - `trip_booked`
  - `visa_approved`
  - `visa_requirements_checked`

- education and mobility
  - `library_pickup_reserved`
  - `commute_route_checked`
  - `transit_balance_topped_up`
  - `smart_meter_configured`
  - `thermostat_schedule_configured`

- work and services
  - `job_application_followup_created`
  - `housekeeping_service_booked`

- security
  - `two_factor_enabled`
  - `two_factor_device_updated`
  - `password_reset_code_requested`
  - `password_reset_completed`
  - `account_access_restored`
  - `security_audit_completed`

## Source of Truth

The machine-readable exported vocabulary is:

- `/Users/masteryth/Documents/webagent/tasks/workflow_predicate_vocabulary.json`

That file is generated from the current core workflow module library and should stay synchronized with it.
