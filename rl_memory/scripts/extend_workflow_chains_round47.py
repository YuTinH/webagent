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

SIG_ASSIGNMENT_CERT = (
    ('MODULE_COURSE_ENROLLMENT', 'MODULE_BUY_EBOOK', 'MODULE_SUBMIT_ASSIGNMENT', 'MODULE_DOWNLOAD_CERT'),
    ('MODULE_COURSE_ENROLLMENT', 'MODULE_LIBRARY_SERVICE', 'MODULE_SUBMIT_ASSIGNMENT', 'MODULE_DOWNLOAD_CERT'),
)
SIG_READING_ACCESS = (
    ('MODULE_COURSE_ENROLLMENT', 'MODULE_BUY_EBOOK', 'MODULE_DOWNLOAD_CERT', 'MODULE_EMAIL_CALENDAR'),
    ('MODULE_COURSE_ENROLLMENT', 'MODULE_LIBRARY_SERVICE', 'MODULE_DOWNLOAD_CERT', 'MODULE_EMAIL_CALENDAR'),
)
SIG_CERT_GEAR = (
    ('MODULE_COURSE_ENROLLMENT', 'MODULE_DOWNLOAD_CERT', 'MODULE_GEAR_RENTAL', 'MODULE_EMAIL_CALENDAR'),
    ('MODULE_SKILL_CERTIFICATION', 'MODULE_DOWNLOAD_CERT', 'MODULE_GEAR_RENTAL', 'MODULE_EMAIL_CALENDAR'),
)
SIG_CERT_EVENT = (
    ('MODULE_SKILL_CERTIFICATION', 'MODULE_DOWNLOAD_CERT', 'MODULE_EVENT_TICKETS', 'MODULE_EMAIL_CALENDAR'),
    ('MODULE_SKILL_CERTIFICATION', 'MODULE_DOWNLOAD_CERT', 'MODULE_MOVIE_TICKETS', 'MODULE_EMAIL_CALENDAR'),
)
SIG_RESOURCE_CERT = (
    ('MODULE_COURSE_ENROLLMENT', 'MODULE_LIBRARY_SERVICE', 'MODULE_DOWNLOAD_CERT', 'MODULE_EMAIL_CALENDAR'),
    ('MODULE_SKILL_CERTIFICATION', 'MODULE_BUY_EBOOK', 'MODULE_DOWNLOAD_CERT', 'MODULE_EMAIL_CALENDAR'),
)
SIG_RESOURCE_RENTAL = (
    ('MODULE_LIBRARY_SERVICE', 'MODULE_GEAR_RENTAL', 'MODULE_DOWNLOAD_CERT', 'MODULE_SUBMIT_ASSIGNMENT'),
    ('MODULE_BUY_EBOOK', 'MODULE_GEAR_RENTAL', 'MODULE_DOWNLOAD_CERT', 'MODULE_SUBMIT_ASSIGNMENT'),
)
SIG_RESOURCE_SUBMISSION_ALIGN = (
    ('MODULE_LIBRARY_SERVICE', 'MODULE_DOWNLOAD_CERT', 'MODULE_SUBMIT_ASSIGNMENT', 'MODULE_EMAIL_CALENDAR'),
    ('MODULE_BUY_EBOOK', 'MODULE_DOWNLOAD_CERT', 'MODULE_SUBMIT_ASSIGNMENT', 'MODULE_EMAIL_CALENDAR'),
)
SIG_STUDY_EVENT = (
    ('MODULE_LIBRARY_SERVICE', 'MODULE_SUBMIT_ASSIGNMENT', 'MODULE_EVENT_TICKETS', 'MODULE_EMAIL_CALENDAR'),
    ('MODULE_BUY_EBOOK', 'MODULE_SUBMIT_ASSIGNMENT', 'MODULE_MOVIE_TICKETS', 'MODULE_EMAIL_CALENDAR'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round47'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'education':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_ASSIGNMENT_CERT:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'course_enrolled',
                'assignment_resources_provisioned',
                'assignment_submitted',
                'certificate_downloaded',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the assignment packet only after the course is enrolled, resources are provisioned, the assignment is submitted, the certificate is downloaded, and the study calendar is synced.',
                'Close the coursework flow by enrolling first, securing resources, submitting the assignment, downloading the certificate artifact, and ending with a synced study calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; assignment-oriented education workflows should close with an explicit calendar handoff after certificate download.'
            ),
            'distinctness_rule': (
                'Either use the ebook route before assignment submission, certificate download, and calendar sync, '
                'or use the library-service route before the same assignment, certificate, and calendar closure.'
            ),
            'paths': [
                (
                    'path_course_ebook_submit_cert_calendar',
                    [
                        'MODULE_COURSE_ENROLLMENT',
                        'MODULE_BUY_EBOOK',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_course_library_submit_cert_calendar',
                    [
                        'MODULE_COURSE_ENROLLMENT',
                        'MODULE_LIBRARY_SERVICE',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_READING_ACCESS:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'course_enrolled',
                'assignment_resources_provisioned',
                'assignment_submitted',
                'certificate_downloaded',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the course-resource packet only after the course is enrolled, resources are provisioned, the assignment is submitted, the certificate is downloaded, and the study calendar is synced.',
                'Close the study-resource workflow by enrolling first, provisioning resources, submitting the assignment, downloading the certificate artifact, and ending with the calendar synced.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; course-resource education workflows should include a concrete submission step before the certificate and calendar closure.'
            ),
            'distinctness_rule': (
                'Either use the ebook route before submission, certificate download, and calendar sync, '
                'or use the library-service route before the same submission, certificate, and calendar closure.'
            ),
            'paths': [
                (
                    'path_course_ebook_submit_cert_calendar',
                    [
                        'MODULE_COURSE_ENROLLMENT',
                        'MODULE_BUY_EBOOK',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_course_library_submit_cert_calendar',
                    [
                        'MODULE_COURSE_ENROLLMENT',
                        'MODULE_LIBRARY_SERVICE',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_CERT_GEAR:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'certificate_downloaded',
                'rental_listing_active',
                'calendar_event_synced',
                'event_ticket_booked',
            ],
            'instruction_templates': [
                'Finish the certificate-rental packet only after the certificate is downloaded, the rental listing is active, the calendar is synced, and event access is booked.',
                'Close the certificate-rental workflow by generating the certificate artifact, activating the rental listing, syncing the related calendar event, and ending with event access booked.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; certificate-and-rental education workflows should continue into explicit event access after the calendar step.'
            ),
            'distinctness_rule': (
                'Either use the course-enrollment route before certificate download, rental activation, calendar sync, and ticket booking, '
                'or use the skill-certification route before the same certificate, rental, calendar, and event closure.'
            ),
            'paths': [
                (
                    'path_course_cert_gear_calendar_event',
                    [
                        'MODULE_COURSE_ENROLLMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_EMAIL_CALENDAR',
                        'MODULE_EVENT_TICKETS',
                    ],
                ),
                (
                    'path_skill_cert_gear_calendar_event',
                    [
                        'MODULE_SKILL_CERTIFICATION',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_EMAIL_CALENDAR',
                        'MODULE_EVENT_TICKETS',
                    ],
                ),
            ],
        }

    if sig == SIG_CERT_EVENT:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'skill_certified',
                'certificate_downloaded',
                'event_ticket_booked',
                'calendar_event_synced',
                'rental_listing_active',
            ],
            'instruction_templates': [
                'Finish the certificate-event packet only after the skill is certified, the certificate is downloaded, event access is booked, the calendar is synced, and the gear rental listing is active.',
                'Close the credential-event workflow by completing skill certification, downloading the certificate artifact, booking the event access, syncing the calendar, and ending with gear-rental readiness.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; credential-event education workflows should continue into equipment readiness after the event and calendar steps.'
            ),
            'distinctness_rule': (
                'Either use the event-ticket route before calendar sync and rental readiness, '
                'or use the movie-ticket route before the same calendar and rental closure.'
            ),
            'paths': [
                (
                    'path_skill_cert_event_calendar_gear',
                    [
                        'MODULE_SKILL_CERTIFICATION',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_EVENT_TICKETS',
                        'MODULE_EMAIL_CALENDAR',
                        'MODULE_GEAR_RENTAL',
                    ],
                ),
                (
                    'path_skill_cert_movie_calendar_gear',
                    [
                        'MODULE_SKILL_CERTIFICATION',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_MOVIE_TICKETS',
                        'MODULE_EMAIL_CALENDAR',
                        'MODULE_GEAR_RENTAL',
                    ],
                ),
            ],
        }

    if sig == SIG_RESOURCE_CERT:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'assignment_resources_provisioned',
                'certificate_downloaded',
                'rental_listing_active',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the resource-cert packet only after study resources are provisioned, the certificate is downloaded, the rental listing is active, and the study calendar is synced.',
                'Close the resource-certification workflow by provisioning resources first, downloading the certificate artifact, activating the rental listing, and ending with the calendar synced.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; resource-cert education workflows should continue into rental readiness before the final calendar closure.'
            ),
            'distinctness_rule': (
                'Either use the course-and-library route before certificate download, rental activation, and calendar sync, '
                'or use the skill-certification-and-ebook route before the same certificate, rental, and calendar closure.'
            ),
            'paths': [
                (
                    'path_course_library_cert_gear_calendar',
                    [
                        'MODULE_COURSE_ENROLLMENT',
                        'MODULE_LIBRARY_SERVICE',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_skill_ebook_cert_gear_calendar',
                    [
                        'MODULE_SKILL_CERTIFICATION',
                        'MODULE_BUY_EBOOK',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_RESOURCE_RENTAL:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'assignment_resources_provisioned',
                'rental_listing_active',
                'certificate_downloaded',
                'assignment_submitted',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the resource-rental packet only after study resources are provisioned, the rental listing is active, the certificate is downloaded, the assignment is submitted, and the calendar is synced.',
                'Close the resource-rental workflow by securing study resources, activating the rental listing, downloading the certificate artifact, submitting the assignment, and ending with the calendar synced.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; resource-rental education workflows should close with a calendar handoff after assignment submission.'
            ),
            'distinctness_rule': (
                'Either use the library-service route before certificate download, assignment submission, and calendar sync, '
                'or use the ebook route before the same certificate, assignment, and calendar closure.'
            ),
            'paths': [
                (
                    'path_library_gear_cert_submit_calendar',
                    [
                        'MODULE_LIBRARY_SERVICE',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_ebook_gear_cert_submit_calendar',
                    [
                        'MODULE_BUY_EBOOK',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_RESOURCE_SUBMISSION_ALIGN:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'assignment_resources_provisioned',
                'assignment_submitted',
                'certificate_downloaded',
                'rental_listing_active',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the resource-submission packet only after study resources are provisioned, the assignment is submitted, the certificate is downloaded, the rental listing is active, and the calendar is synced.',
                'Close the resource-submission workflow by securing study resources first, submitting the assignment, downloading the certificate artifact, activating the rental listing, and ending with the calendar synced.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; resource-submission education workflows should continue into rental readiness after submission and certificate steps.'
            ),
            'distinctness_rule': (
                'Either use the library-service route before submission, certificate download, rental activation, and calendar sync, '
                'or use the ebook route before the same submission, certificate, rental, and calendar closure.'
            ),
            'paths': [
                (
                    'path_library_submit_cert_gear_calendar',
                    [
                        'MODULE_LIBRARY_SERVICE',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_ebook_submit_cert_gear_calendar',
                    [
                        'MODULE_BUY_EBOOK',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_GEAR_RENTAL',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_STUDY_EVENT:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'assignment_resources_provisioned',
                'assignment_submitted',
                'certificate_downloaded',
                'event_ticket_booked',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the study-event packet only after study resources are provisioned, the assignment is submitted, the certificate is downloaded, event access is booked, and the calendar is synced.',
                'Close the study-event workflow by securing study resources first, submitting the assignment, downloading the certificate artifact, booking event access, and ending with the calendar synced.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; study-event education workflows should include certificate capture before the final event and calendar closure.'
            ),
            'distinctness_rule': (
                'Either use the library-service route before certificate download, ticket booking, and calendar sync, '
                'or use the ebook route before the same certificate, ticket, and calendar closure.'
            ),
            'paths': [
                (
                    'path_library_submit_cert_event_calendar',
                    [
                        'MODULE_LIBRARY_SERVICE',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_EVENT_TICKETS',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_ebook_submit_cert_movie_calendar',
                    [
                        'MODULE_BUY_EBOOK',
                        'MODULE_SUBMIT_ASSIGNMENT',
                        'MODULE_DOWNLOAD_CERT',
                        'MODULE_MOVIE_TICKETS',
                        'MODULE_EMAIL_CALENDAR',
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
        raise SystemExit('round47 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
                'patched_blueprints': sorted(patched_blueprints),
                'patched_blueprint_count': len(patched_blueprints),
                'refreshed_counts': refreshed_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
