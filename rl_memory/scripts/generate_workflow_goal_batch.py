#!/usr/bin/env python3
import argparse
import copy
import json
import random
from collections import defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path('/Users/masteryth/Documents/webagent')
MODULE_LIBRARY = ROOT / 'tasks' / 'workflow_module_library.json'
BINDING_LIBRARY = ROOT / 'tasks' / 'workflow_module_bindings.json'
BLUEPRINT_LIBRARY = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
QUALITY_REQUIREMENTS = ROOT / 'tasks' / 'workflow_quality_requirements.json'
DEFAULT_OUTPUT_ROOT = ROOT / 'tasks' / 'generated_workflow_batches'


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        raise KeyError(f'missing template variable: {key}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Generate scalable workflow goal/oracle batches from reusable blueprints.'
    )
    parser.add_argument('--blueprints', default=str(BLUEPRINT_LIBRARY))
    parser.add_argument('--modules', default=str(MODULE_LIBRARY))
    parser.add_argument('--bindings', default=str(BINDING_LIBRARY))
    parser.add_argument('--requirements', default=str(QUALITY_REQUIREMENTS))
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument('--batch-name', required=True)
    parser.add_argument('--count-per-blueprint', type=int, default=10)
    parser.add_argument('--blueprint-ids-file')
    parser.add_argument('--blueprint-ids', nargs='*')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--force', action='store_true')
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def filter_blueprints(blueprints: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    requested_ids: set[str] = set()
    if args.blueprint_ids_file:
        payload = load_json(Path(args.blueprint_ids_file))
        if isinstance(payload, dict):
            if 'blueprint_ids' in payload:
                requested_ids.update(payload['blueprint_ids'])
            else:
                for value in payload.values():
                    if isinstance(value, list):
                        requested_ids.update(item for item in value if isinstance(item, str))
        elif isinstance(payload, list):
            requested_ids.update(item for item in payload if isinstance(item, str))
    if args.blueprint_ids:
        requested_ids.update(args.blueprint_ids)

    if not requested_ids:
        return blueprints

    filtered = [blueprint for blueprint in blueprints if blueprint['blueprint_id'] in requested_ids]
    found_ids = {blueprint['blueprint_id'] for blueprint in filtered}
    missing = sorted(requested_ids - found_ids)
    if missing:
        raise SystemExit('unknown blueprint ids requested:\n- ' + '\n- '.join(missing))
    return filtered


def render_template(text: str, context: dict[str, Any]) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value

    normalized = {key: normalize(value) for key, value in context.items()}
    return text.format_map(SafeFormatDict(normalized))


def deep_render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return render_template(value, context)
    if isinstance(value, list):
        return [deep_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: deep_render(item, context) for key, item in value.items()}
    return value


def resolve_binding_value(raw: Any, shared_vars: dict[str, Any]) -> Any:
    if isinstance(raw, str) and raw.startswith('@'):
        key = raw[1:]
        if key not in shared_vars:
            raise KeyError(f'unknown shared variable reference: {raw}')
        return shared_vars[key]
    return raw


def select_binding(step: dict[str, Any], bindings_by_module: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    candidates = bindings_by_module[step['module_id']]
    binding_id = step.get('binding_id')
    if binding_id is not None:
        for binding in candidates:
            if binding['binding_id'] == binding_id:
                return binding
        raise KeyError(f"unknown binding_id for {step['module_id']}: {binding_id}")

    binding_task_id = step.get('binding_task_id')
    if binding_task_id is not None:
        for binding in candidates:
            if binding['backing_task_id'] == binding_task_id:
                return binding
        raise KeyError(f"unknown binding_task_id for {step['module_id']}: {binding_task_id}")

    return candidates[0]


def sample_shared_variables(blueprint: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    sampled = {}
    for name, pool in blueprint.get('shared_variable_pools', {}).items():
        sampled[name] = copy.deepcopy(rng.choice(pool))
    sampled['blueprint_id'] = blueprint['blueprint_id']
    sampled['theme'] = blueprint['theme']
    return sampled


def initial_state_predicates(initial_world_state: Any) -> set[str]:
    if isinstance(initial_world_state, list):
        return {predicate for predicate in initial_world_state if isinstance(predicate, str)}
    if isinstance(initial_world_state, dict):
        state = set()
        for key, value in initial_world_state.items():
            if value is True:
                state.add(key)
        return state
    raise TypeError(f'unsupported initial_world_state type: {type(initial_world_state).__name__}')


def preconditions_satisfied(requires: dict[str, Any], state: set[str]) -> bool:
    all_of = set(requires.get('all_of', []))
    any_of = set(requires.get('any_of', []))
    none_of = set(requires.get('none_of', []))
    if not all_of.issubset(state):
        return False
    if any_of and not (any_of & state):
        return False
    if none_of & state:
        return False
    return True


def validate_path(
    blueprint: dict[str, Any],
    path: dict[str, Any],
    modules_by_id: dict[str, dict[str, Any]],
) -> tuple[bool, list[str], set[str]]:
    issues: list[str] = []
    state = initial_state_predicates(blueprint['initial_world_state'])
    for index, step in enumerate(path['steps'], start=1):
        module = modules_by_id[step['module_id']]
        if not preconditions_satisfied(module['requires'], state):
            issues.append(
                f"step_{index}:{step['module_id']}:preconditions_unsatisfied:{module['requires']}"
            )
        state -= set(module['effects'].get('removes', []))
        state |= set(module['effects'].get('adds', []))
    missing_targets = [pred for pred in blueprint['target_state'] if pred not in state]
    if missing_targets:
        issues.append(f'missing_target_predicates:{missing_targets}')
    return (not issues), issues, state


def instantiate_step(
    goal_id: str,
    invocation_index: int,
    step: dict[str, Any],
    modules_by_id: dict[str, dict[str, Any]],
    bindings_by_module: dict[str, list[dict[str, Any]]],
    shared_vars: dict[str, Any],
) -> dict[str, Any]:
    module = modules_by_id[step['module_id']]
    binding = select_binding(step, bindings_by_module)
    params = copy.deepcopy(binding.get('default_parameter_values', {}))
    if binding.get('allow_parameter_overrides', True):
        for key, raw_value in step.get('parameter_bindings', {}).items():
            params[key] = resolve_binding_value(raw_value, shared_vars)

    render_context = dict(shared_vars)
    render_context.update(params)
    description_template = binding.get('description_template', module['name'])
    observables = [
        render_template(template, render_context)
        for template in binding.get('observable_templates', [])
    ]
    invocation = {
        'invocation_id': f'{goal_id}-M{invocation_index}',
        'module_id': step['module_id'],
        'binding_id': binding['binding_id'],
        'binding_task_id': binding['backing_task_id'],
        'parameter_values': params,
        'description': render_template(description_template, render_context),
        'expected_observables': observables,
        'instantiated_effects': {
            'adds': module['effects'].get('adds', []),
            'removes': module['effects'].get('removes', []),
        },
    }
    return invocation


def derive_module_nodes(
    blueprint: dict[str, Any],
    modules_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    membership: dict[str, set[str]] = defaultdict(set)
    path_kind: dict[str, str] = {}
    for path in blueprint['paths']:
        path_kind[path['path_id']] = path['kind']
        for step in path['steps']:
            membership[step['module_id']].add(path['path_id'])

    out = []
    total_paths = len(blueprint['paths'])
    for module_id in sorted(membership):
        present_in = membership[module_id]
        if len(present_in) == total_paths:
            role = 'required'
        elif any(path_kind[path_id] == 'recovery' for path_id in present_in):
            role = 'recovery'
        else:
            role = 'alternative'
        out.append(
            {
                'module_id': module_id,
                'role': role,
                'produces': modules_by_id[module_id]['effects'].get('adds', []),
            }
        )
    return out


def derive_dependency_edges(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    edge_membership: dict[tuple[str, str], set[str]] = defaultdict(set)
    path_kind: dict[str, str] = {}
    for path in blueprint['paths']:
        path_id = path['path_id']
        path_kind[path_id] = path['kind']
        step_ids = [step['module_id'] for step in path['steps']]
        for current, nxt in zip(step_ids, step_ids[1:]):
            edge_membership[(current, nxt)].add(path_id)

    edges = []
    total_paths = len(blueprint['paths'])
    for (src, dst), present_in in sorted(edge_membership.items()):
        if total_paths == 1 or len(present_in) == total_paths:
            kind = 'hard'
        elif any(path_kind[path_id] == 'recovery' for path_id in present_in):
            kind = 'recovery'
        else:
            kind = 'alternative'
        edges.append({'from': src, 'to': dst, 'kind': kind})
    return edges


def distinct_required_module_sets(paths: list[dict[str, Any]]) -> int:
    return len({tuple(path['required_modules']) for path in paths})


def composition_for_paths(blueprint: dict[str, Any], success_paths: list[dict[str, Any]]) -> dict[str, Any]:
    composition_type = 'multi_path' if len(success_paths) > 1 else 'single_path'
    return {
        'composition_type': composition_type,
        'num_semantically_distinct_paths': distinct_required_module_sets(success_paths),
        'distinctness_rule': blueprint['distinctness_rule'],
    }


def build_goal(
    goal_id: str,
    blueprint: dict[str, Any],
    shared_vars: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    instruction = render_template(rng.choice(blueprint['instruction_templates']), shared_vars)
    goal = {
        'goal_id': goal_id,
        'theme': blueprint['theme'],
        'difficulty': blueprint['difficulty'],
        'instruction': instruction,
        'visible_constraints': deep_render(blueprint['visible_constraints'], shared_vars),
        'initial_world_state': deep_render(blueprint['initial_world_state'], shared_vars),
        'target_state': deep_render(blueprint['target_state'], shared_vars),
        'counterfactual_axes': deep_render(blueprint.get('counterfactual_axes', []), shared_vars),
        'max_steps': blueprint['max_steps'],
        'max_module_invocations': blueprint['max_module_invocations'],
        'notes': render_template(blueprint.get('notes_template', blueprint['blueprint_id']), shared_vars),
    }
    return goal


def build_oracle(
    goal_id: str,
    blueprint: dict[str, Any],
    modules_by_id: dict[str, dict[str, Any]],
    bindings_by_module: dict[str, list[dict[str, Any]]],
    shared_vars: dict[str, Any],
) -> dict[str, Any]:
    reference_invocations: list[dict[str, Any]] = []
    success_paths: list[dict[str, Any]] = []
    invocation_index = 1

    for path in blueprint['paths']:
        path_invocation_ids = []
        for step in path['steps']:
            invocation = instantiate_step(
                goal_id,
                invocation_index,
                step,
                modules_by_id,
                bindings_by_module,
                shared_vars,
            )
            reference_invocations.append(invocation)
            path_invocation_ids.append(invocation['invocation_id'])
            invocation_index += 1
        success_paths.append(
            {
                'path_id': path['path_id'],
                'required_modules': [step['module_id'] for step in path['steps']],
                'optional_modules': [],
                'reference_invocation_ids': path_invocation_ids,
                'terminal_predicates': list(blueprint['target_state']),
            }
        )

    checkpoint_predicates = sorted(
        set(blueprint['target_state'])
        | {pred for path in blueprint['paths'] for step in path['steps'] for pred in modules_by_id[step['module_id']]['effects'].get('adds', [])}
    )
    oracle = {
        'goal_id': goal_id,
        'composition': composition_for_paths(blueprint, success_paths),
        'module_nodes': derive_module_nodes(blueprint, modules_by_id),
        'dependency_edges': derive_dependency_edges(blueprint),
        'success_paths': success_paths,
        'reference_invocations': reference_invocations,
        'evaluation': {
            'final_success': list(blueprint['target_state']),
            'checkpoint_predicates': checkpoint_predicates,
            'unnecessary_module_penalty': 0.2,
            'invalid_transition_penalty': 1.25,
            'recovery_bonus': 0.5 if any(path['kind'] == 'recovery' for path in blueprint['paths']) else 0.0,
        },
    }
    return oracle


def validate_blueprint(
    blueprint: dict[str, Any],
    modules_by_id: dict[str, dict[str, Any]],
    requirements: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    success_path_stubs = []
    for path in blueprint['paths']:
        for step in path['steps']:
            if step['module_id'] not in modules_by_id:
                issues.append(f"unknown_module:{blueprint['blueprint_id']}:{step['module_id']}")
        ok, path_issues, _ = validate_path(blueprint, path, modules_by_id)
        if not ok:
            for issue in path_issues:
                issues.append(f"invalid_path:{blueprint['blueprint_id']}:{path['path_id']}:{issue}")
        success_path_stubs.append(
            {
                'path_id': path['path_id'],
                'required_modules': [step['module_id'] for step in path['steps']],
            }
        )

    composition_type = 'multi_path' if len(blueprint['paths']) > 1 else 'single_path'
    distinct_count = distinct_required_module_sets(success_path_stubs)
    max_jaccard = None
    required_sets = [set(path['required_modules']) for path in success_path_stubs]
    if len(required_sets) > 1:
        max_jaccard = max(
            len(a & b) / len(a | b) if (a | b) else 1.0
            for a, b in combinations(required_sets, 2)
        )

    if composition_type == 'multi_path':
        multi_rules = requirements['multi_path']
        if len(blueprint['paths']) < multi_rules['min_success_paths']:
            issues.append(f"multi_path_too_few_paths:{blueprint['blueprint_id']}")
        if distinct_count < multi_rules['min_semantically_distinct_paths']:
            issues.append(f"multi_path_not_distinct_enough:{blueprint['blueprint_id']}")
        if max_jaccard is not None and max_jaccard > multi_rules['max_required_set_jaccard']:
            issues.append(f"multi_path_overlap_too_high:{blueprint['blueprint_id']}:{max_jaccard:.3f}")
    else:
        if len(blueprint['paths']) != requirements['single_path']['max_success_paths']:
            issues.append(f"single_path_count_invalid:{blueprint['blueprint_id']}")
    return issues


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    modules_by_id = {m['module_id']: m for m in load_json(Path(args.modules))['modules']}
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in load_json(Path(args.bindings))['bindings']:
        bindings_by_module[binding['module_id']].append(binding)
    requirements = load_json(Path(args.requirements))
    blueprints = filter_blueprints(load_json(Path(args.blueprints))['blueprints'], args)

    batch_root = Path(args.output_root) / args.batch_name
    goal_dir = batch_root / 'workflow_goal_instances'
    oracle_dir = batch_root / 'workflow_oracles'
    if batch_root.exists() and any(batch_root.iterdir()) and not args.force:
        raise SystemExit(f'batch directory already exists and is not empty: {batch_root}')
    goal_dir.mkdir(parents=True, exist_ok=True)
    oracle_dir.mkdir(parents=True, exist_ok=True)

    blueprint_issues = []
    for blueprint in blueprints:
        blueprint_issues.extend(validate_blueprint(blueprint, modules_by_id, requirements))
    if blueprint_issues:
        raise SystemExit('blueprint validation failed:\n- ' + '\n- '.join(blueprint_issues))

    manifest_entries = []
    multi_instances = 0
    total_instances = 0
    goal_id_counters: dict[str, int] = defaultdict(int)
    for blueprint in blueprints:
        for _ in range(args.count_per_blueprint):
            goal_id_counters[blueprint['goal_id_prefix']] += 1
            index = goal_id_counters[blueprint['goal_id_prefix']]
            shared_vars = sample_shared_variables(blueprint, rng)
            goal_id = f"{blueprint['goal_id_prefix']}-{index:04d}"
            goal = build_goal(goal_id, blueprint, shared_vars, rng)
            oracle = build_oracle(goal_id, blueprint, modules_by_id, bindings_by_module, shared_vars)
            (goal_dir / f'{goal_id}.json').write_text(json.dumps(goal, ensure_ascii=False, indent=2) + '\n')
            (oracle_dir / f'{goal_id}.json').write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + '\n')
            composition_type = oracle['composition']['composition_type']
            total_instances += 1
            if composition_type == 'multi_path':
                multi_instances += 1
            manifest_entries.append(
                {
                    'goal_id': goal_id,
                    'theme': blueprint['theme'],
                    'blueprint_id': blueprint['blueprint_id'],
                    'composition_type': composition_type,
                    'goal_file': f'workflow_goal_instances/{goal_id}.json',
                    'oracle_file': f'workflow_oracles/{goal_id}.json',
                }
            )

    manifest = {
        'version': 1,
        'batch_name': args.batch_name,
        'generated_on': str(date.today()),
        'seed': args.seed,
        'count_per_blueprint': args.count_per_blueprint,
        'blueprint_library': str(Path(args.blueprints)),
        'quality_requirements': str(Path(args.requirements)),
        'projected_multi_path_ratio': (multi_instances / total_instances) if total_instances else 0.0,
        'goals': manifest_entries,
    }
    (batch_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

    print(json.dumps({
        'batch_root': str(batch_root),
        'goal_count': total_instances,
        'multi_path_count': multi_instances,
        'projected_multi_path_ratio': manifest['projected_multi_path_ratio'],
        'next_audit_command': f"python3 {ROOT / 'rl_memory' / 'scripts' / 'audit_workflow_goal_quality.py'} --oracle-dir {oracle_dir} --requirements {Path(args.requirements)} --output-json {batch_root / 'workflow_goal_quality_audit.json'} --output-md {batch_root / 'workflow_goal_quality_audit.md'} --strict",
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
