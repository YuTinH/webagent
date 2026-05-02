#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
BATCH_ROOT = ROOT / 'tasks' / 'generated_workflow_split_batches' / 'workflow_split_batch_v20'
GENERATOR_PATH = ROOT / 'rl_memory' / 'scripts' / 'generate_workflow_goal_batch.py'

SIG_EXPENSE_ARCHIVE = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_EXPENSE_REPORT', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_CONFERENCE_REG'),
    ('MODULE_BOOK_HOTEL', 'MODULE_EXPENSE_REPORT', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_CONFERENCE_REG'),
)
SIG_JOB_SIGNALING = (
    ('MODULE_UPDATE_LINKEDIN', 'MODULE_JOB_SEARCH', 'MODULE_CALENDAR_AGGREGATION', 'MODULE_CONFERENCE_REGISTRATION'),
    ('MODULE_EMAIL_TRACKING', 'MODULE_JOB_SEARCH', 'MODULE_CALENDAR_AGGREGATION', 'MODULE_CONFERENCE_REGISTRATION'),
)
SIG_PUBLICATION_SIGNALING = (
    ('MODULE_EMAIL_TRACKING', 'MODULE_PAPER_SUBMISSION', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_UPDATE_LINKEDIN'),
    ('MODULE_CONFERENCE_REGISTRATION', 'MODULE_PAPER_SUBMISSION', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_UPDATE_LINKEDIN'),
)
SIG_SUBMISSION_DEADLINE_SYNC = (
    ('MODULE_EMAIL_TRACKING', 'MODULE_PAPER_SUBMISSION', 'MODULE_CALENDAR_AGGREGATION', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_CONFERENCE_REGISTRATION', 'MODULE_PAPER_SUBMISSION', 'MODULE_CALENDAR_AGGREGATION', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_SUBMISSION_COORDINATION = (
    ('MODULE_CALENDAR_AGGREGATION', 'MODULE_PAPER_SUBMISSION', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_UPDATE_LINKEDIN'),
    ('MODULE_CONFERENCE_REGISTRATION', 'MODULE_PAPER_SUBMISSION', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_UPDATE_LINKEDIN'),
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def load_generator_module():
    spec = importlib.util.spec_from_file_location('workflow_goal_generator', GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'failed to load generator from {GENERATOR_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_step_lookup(paths: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in paths:
        for step in path.get('steps', []):
            module_id = step.get('module_id')
            if module_id and module_id not in lookup:
                lookup[module_id] = copy.deepcopy(step)
    return lookup


def build_global_step_lookup(blueprints: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for blueprint in blueprints:
        for module_id, step in base_step_lookup(blueprint.get('paths', [])).items():
            lookup.setdefault(module_id, step)
    return lookup


def step_from_lookup(
    local_lookup: dict[str, dict[str, Any]],
    global_lookup: dict[str, dict[str, Any]],
    allowed_shared_vars: set[str],
    module_id: str,
) -> dict[str, Any]:
    if module_id in local_lookup:
        step = copy.deepcopy(local_lookup[module_id])
    elif module_id in global_lookup:
        step = copy.deepcopy(global_lookup[module_id])
    else:
        step = {'module_id': module_id}

    bindings = step.get('parameter_bindings')
    if isinstance(bindings, dict):
        referenced = {
            value[1:]
            for value in bindings.values()
            if isinstance(value, str) and value.startswith('@')
        }
        if not referenced.issubset(allowed_shared_vars):
            step.pop('parameter_bindings', None)
    return step


def build_path(
    local_lookup: dict[str, dict[str, Any]],
    global_lookup: dict[str, dict[str, Any]],
    allowed_shared_vars: set[str],
    path_id: str,
    module_ids: list[str],
    kind: str = 'alternative',
) -> dict[str, Any]:
    return {
        'path_id': path_id,
        'kind': kind,
        'steps': [
            step_from_lookup(local_lookup, global_lookup, allowed_shared_vars, module_id)
            for module_id in module_ids
        ],
    }


def replace_preferred_outcomes(existing: dict[str, Any], outcomes: list[str]) -> dict[str, Any]:
    updated = copy.deepcopy(existing)
    updated['preferred_outcomes'] = outcomes
    return updated


def stable_goal_seed(goal_id: str, blueprint_id: str) -> int:
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round53'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def unique_extend(items: list[str], extras: list[str]) -> list[str]:
    out: list[str] = []
    for item in list(items) + list(extras):
        if item not in out:
            out.append(item)
    return out


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'career':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_EXPENSE_ARCHIVE:
        target_state = unique_extend(list(bp.get('target_state', [])), ['calendar_event_created'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the expense-archive career workflow only after travel spend is captured, receipts are archived, conference administration is recorded, and the related milestone is placed on the calendar.',
                'Close the expense-archive route by booking the travel leg first, filing expenses, archiving receipts, recording conference administration, and ending with a calendar milestone.',
            ],
            'notes_template': 'Generated from {blueprint_id}; expense-archive career workflows should end with an explicit calendar milestone after conference administration is recorded.',
            'distinctness_rule': 'Follow one full expense-archive route to completion and do not stop before conference administration and the calendar milestone are both completed.',
            'paths': [
                (
                    'path_flight_expense_archive_conf_calendar',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_EXPENSE_REPORT',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_CONFERENCE_REG',
                        'MODULE_CALENDAR_AGGREGATION',
                    ],
                ),
                (
                    'path_hotel_expense_archive_conf_calendar',
                    [
                        'MODULE_BOOK_HOTEL',
                        'MODULE_EXPENSE_REPORT',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_CONFERENCE_REG',
                        'MODULE_CALENDAR_AGGREGATION',
                    ],
                ),
            ],
        }

    if sig == SIG_JOB_SIGNALING:
        target_state = unique_extend(list(bp.get('target_state', [])), ['receipt_archived'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the job-signaling workflow only after the outreach signal is established, job follow-up is created, deadlines are coordinated, conference registration is recorded, and the supporting receipt is archived.',
                'Close the job-signaling route by strengthening the signal first, creating the follow-up, coordinating deadlines, registering the conference, and ending with archived supporting receipts.',
            ],
            'notes_template': 'Generated from {blueprint_id}; job-signaling workflows should continue through receipt archiving after conference registration.',
            'distinctness_rule': 'Follow one full job-signaling route to completion and do not stop before conference registration and receipt archiving are both completed.',
            'paths': [
                (
                    'path_linkedin_job_calendar_conf_archive',
                    [
                        'MODULE_UPDATE_LINKEDIN',
                        'MODULE_JOB_SEARCH',
                        'MODULE_CALENDAR_AGGREGATION',
                        'MODULE_CONFERENCE_REGISTRATION',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
                (
                    'path_email_job_calendar_conf_archive',
                    [
                        'MODULE_EMAIL_TRACKING',
                        'MODULE_JOB_SEARCH',
                        'MODULE_CALENDAR_AGGREGATION',
                        'MODULE_CONFERENCE_REGISTRATION',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
            ],
        }

    if sig == SIG_PUBLICATION_SIGNALING:
        target_state = unique_extend(list(bp.get('target_state', [])), ['deadline_coordination_recorded'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the publication-signaling workflow only after the paper is submitted, records are archived, the professional signal is updated, and the publication follow-up is coordinated on the calendar.',
                'Close the publication-signaling route by completing the submission first, archiving the record, updating the professional signal, and ending with coordinated calendar follow-up.',
            ],
            'notes_template': 'Generated from {blueprint_id}; publication-signaling workflows should continue into deadline coordination after the professional signal is updated.',
            'distinctness_rule': 'Follow one full publication-signaling route to completion and do not stop before the paper is submitted, the signal is updated, and deadline coordination is recorded.',
            'paths': [
                (
                    'path_email_submission_archive_linkedin_calendar',
                    [
                        'MODULE_EMAIL_TRACKING',
                        'MODULE_PAPER_SUBMISSION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_UPDATE_LINKEDIN',
                        'MODULE_CALENDAR_AGGREGATION',
                    ],
                ),
                (
                    'path_conf_submission_archive_linkedin_calendar',
                    [
                        'MODULE_CONFERENCE_REGISTRATION',
                        'MODULE_PAPER_SUBMISSION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_UPDATE_LINKEDIN',
                        'MODULE_CALENDAR_AGGREGATION',
                    ],
                ),
            ],
        }

    if sig == SIG_SUBMISSION_DEADLINE_SYNC:
        target_state = unique_extend(list(bp.get('target_state', [])), ['professional_profile_updated'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the submission-deadline workflow only after the paper is submitted, deadlines are coordinated, records are archived, and the professional profile is updated to reflect the submission.',
                'Close the submission-deadline route by completing submission work first, coordinating the calendar, archiving the records, and ending with a profile update that reflects the submission.',
            ],
            'notes_template': 'Generated from {blueprint_id}; submission-deadline workflows should end with an explicit profile update after calendar coordination and archiving.',
            'distinctness_rule': 'Follow one full submission-deadline route to completion and do not stop before submission, archiving, and the final profile update are all completed.',
            'paths': [
                (
                    'path_email_submission_calendar_archive_linkedin',
                    [
                        'MODULE_EMAIL_TRACKING',
                        'MODULE_PAPER_SUBMISSION',
                        'MODULE_CALENDAR_AGGREGATION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_UPDATE_LINKEDIN',
                    ],
                ),
                (
                    'path_conf_submission_calendar_archive_linkedin',
                    [
                        'MODULE_CONFERENCE_REGISTRATION',
                        'MODULE_PAPER_SUBMISSION',
                        'MODULE_CALENDAR_AGGREGATION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_UPDATE_LINKEDIN',
                    ],
                ),
            ],
        }

    if sig == SIG_SUBMISSION_COORDINATION:
        target_state = unique_extend(list(bp.get('target_state', [])), ['email_thread_tracked'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the submission-coordination workflow only after the paper is submitted, records are archived, the professional signal is updated, and the follow-up thread is tracked by email.',
                'Close the submission-coordination route by coordinating the deadline first, completing the submission packet, updating the professional signal, and ending with tracked follow-up communication.',
            ],
            'notes_template': 'Generated from {blueprint_id}; submission-coordination workflows should continue into tracked follow-up communication after signaling is updated.',
            'distinctness_rule': 'Follow one full submission-coordination route to completion and do not stop before the paper is submitted, the signal is updated, and follow-up email tracking is completed.',
            'paths': [
                (
                    'path_calendar_submission_archive_linkedin_email',
                    [
                        'MODULE_CALENDAR_AGGREGATION',
                        'MODULE_PAPER_SUBMISSION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_UPDATE_LINKEDIN',
                        'MODULE_EMAIL_TRACKING',
                    ],
                ),
                (
                    'path_conf_submission_archive_linkedin_email',
                    [
                        'MODULE_CONFERENCE_REGISTRATION',
                        'MODULE_PAPER_SUBMISSION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_UPDATE_LINKEDIN',
                        'MODULE_EMAIL_TRACKING',
                    ],
                ),
            ],
        }

    return None


def main() -> None:
    generator = load_generator_module()
    modules_doc = load_json(generator.MODULE_LIBRARY)
    modules_by_id = {m['module_id']: m for m in modules_doc['modules']}
    bindings_doc = load_json(generator.BINDING_LIBRARY)
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings_doc['bindings']:
        bindings_by_module[binding['module_id']].append(binding)
    requirements = load_json(generator.QUALITY_REQUIREMENTS)

    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc['blueprints']
    global_lookup = build_global_step_lookup(blueprints)

    patched_blueprints: dict[str, dict[str, Any]] = {}
    validation_issues: list[str] = []

    for bp in blueprints:
        spec = spec_for_blueprint(bp)
        if spec is None:
            continue

        blueprint_id = bp['blueprint_id']
        local_lookup = base_step_lookup(bp.get('paths', []))
        allowed_shared_vars = set(bp.get('shared_variable_pools', {}).keys())
        target_state = spec['target_state']

        bp['difficulty'] = spec['difficulty']
        bp['max_steps'] = spec['max_steps']
        bp['max_module_invocations'] = spec['max_module_invocations']
        bp['target_state'] = copy.deepcopy(target_state)
        bp['instruction_templates'] = copy.deepcopy(spec['instruction_templates'])
        bp['visible_constraints'] = replace_preferred_outcomes(bp.get('visible_constraints', {}), target_state)
        bp['notes_template'] = spec['notes_template']
        bp['distinctness_rule'] = spec['distinctness_rule']
        bp['paths'] = [
            build_path(
                local_lookup,
                global_lookup,
                allowed_shared_vars,
                path_id,
                module_ids,
            )
            for path_id, module_ids in spec['paths']
        ]

        issues = generator.validate_blueprint(bp, modules_by_id, requirements)
        if issues:
            validation_issues.extend(issues)
        patched_blueprints[blueprint_id] = copy.deepcopy(bp)

    if validation_issues:
        raise SystemExit('round53 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    refreshed_counts = {'dev': 0, 'test': 0, 'train': 0}
    for split in ['dev', 'test', 'train']:
        manifest = load_json(BATCH_ROOT / split / 'manifest.json')
        for ref in manifest.get('goals', []):
            blueprint_id = ref['blueprint_id']
            if blueprint_id not in patched_blueprints:
                continue

            blueprint = patched_blueprints[blueprint_id]
            rng = random.Random(stable_goal_seed(ref['goal_id'], blueprint_id))
            shared_vars = generator.sample_shared_variables(blueprint, rng)
            goal = generator.build_goal(ref['goal_id'], blueprint, shared_vars, rng)
            oracle = generator.build_oracle(
                ref['goal_id'],
                blueprint,
                modules_by_id,
                bindings_by_module,
                shared_vars,
            )
            save_json(BATCH_ROOT / split / ref['goal_file'], goal)
            save_json(BATCH_ROOT / split / ref['oracle_file'], oracle)
            refreshed_counts[split] += 1

    print(
        json.dumps(
            {
                'patched_blueprints': sorted(patched_blueprints.keys()),
                'patched_blueprint_count': len(patched_blueprints),
                'refreshed_counts': refreshed_counts,
            },
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
