#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path('/Users/masteryth/Documents/webagent')
MODULES_PATH = ROOT / 'tasks' / 'workflow_module_library.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Evaluate a workflow episode trace against a workflow goal/oracle pair.'
    )
    parser.add_argument('--goal', required=True, help='Path to workflow goal instance JSON.')
    parser.add_argument('--oracle', required=True, help='Path to workflow oracle JSON.')
    parser.add_argument('--trace', required=True, help='Path to workflow execution trace JSON.')
    parser.add_argument('--modules', default=str(MODULES_PATH), help='Path to workflow module library JSON.')
    parser.add_argument('--output-json', help='Where to write JSON evaluation output.')
    parser.add_argument('--output-md', help='Where to write Markdown evaluation summary.')
    return parser.parse_args()


def state_predicates(raw: Any) -> set[str]:
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    if isinstance(raw, dict):
        return {key for key, value in raw.items() if value is True}
    raise TypeError(f'unsupported state payload type: {type(raw).__name__}')


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


def is_subsequence(sequence: list[str], candidate: list[str]) -> bool:
    if not candidate:
        return True
    idx = 0
    for item in sequence:
        if item == candidate[idx]:
            idx += 1
            if idx == len(candidate):
                return True
    return False


def pick_reference_match(executed_success: list[str], success_paths: list[dict[str, Any]]) -> tuple[str | None, bool, int]:
    exact_match = None
    subseq_match = None
    for path in success_paths:
        required = path.get('required_modules', [])
        if executed_success == required:
            exact_match = path['path_id']
            return exact_match, True, 0
        if is_subsequence(executed_success, required):
            extras = max(0, len(executed_success) - len(required))
            if subseq_match is None or extras < subseq_match[2]:
                subseq_match = (path['path_id'], False, extras)
    if subseq_match is not None:
        return subseq_match
    return None, False, 0


def evaluate_episode(
    goal: dict[str, Any],
    oracle: dict[str, Any],
    trace: dict[str, Any],
    modules_doc: dict[str, Any],
) -> dict[str, Any]:
    modules_by_id = {module['module_id']: module for module in modules_doc['modules']}

    current_state = state_predicates(trace.get('starting_state_override', goal.get('initial_world_state', [])))
    replayed_state = set(current_state)
    invalid_transitions: list[dict[str, Any]] = []
    failed_steps: list[dict[str, Any]] = []
    unknown_modules: list[dict[str, Any]] = []
    successful_modules: list[str] = []
    estimated_step_cost = 0
    estimated_budget_spend = 0.0
    estimated_elapsed_hours = 0.0

    executed = trace.get('executed_modules', [])
    for index, entry in enumerate(executed, start=1):
        module_id = entry['module_id']
        status = entry.get('status', 'success')
        module = modules_by_id.get(module_id)
        if module is None:
            unknown_modules.append({'index': index, 'module_id': module_id})
            continue

        requires = module.get('requires', {})
        legal = preconditions_satisfied(requires, replayed_state)
        if not legal:
            invalid_transitions.append(
                {
                    'index': index,
                    'module_id': module_id,
                    'requires': requires,
                    'state_before': sorted(replayed_state),
                }
            )

        if status != 'success':
            failed_steps.append({'index': index, 'module_id': module_id, 'status': status})
            continue

        successful_modules.append(module_id)
        estimated_step_cost += int(module.get('constraints', {}).get('estimated_steps', 0) or 0)
        delta = float(module.get('constraints', {}).get('budget_delta', 0.0) or 0.0)
        if delta < 0:
            estimated_budget_spend += -delta
        estimated_elapsed_hours += float(module.get('constraints', {}).get('time_delta_hours', 0.0) or 0.0)

        if legal:
            replayed_state -= set(module.get('effects', {}).get('removes', []))
            replayed_state |= set(module.get('effects', {}).get('adds', []))

    evaluated_final_state = set(replayed_state)
    if 'final_state_override' in trace:
        evaluated_final_state = state_predicates(trace['final_state_override'])

    target_state = set(goal.get('target_state', []))
    target_hits = sorted(target_state & evaluated_final_state)
    target_misses = sorted(target_state - evaluated_final_state)
    target_state_coverage = (len(target_hits) / len(target_state)) if target_state else 1.0

    must_avoid = set(goal.get('visible_constraints', {}).get('must_avoid', []))
    forbidden_hits = sorted(must_avoid & evaluated_final_state)

    max_module_invocations = int(goal.get('max_module_invocations', 0) or 0)
    max_steps = int(goal.get('max_steps', 0) or 0)
    deadline_days = goal.get('visible_constraints', {}).get('deadline_days')
    budget_limit = goal.get('visible_constraints', {}).get('budget_limit')

    hard_constraint_violations: list[str] = []
    attempted_module_invocations = len(executed)
    if max_module_invocations and attempted_module_invocations > max_module_invocations:
        hard_constraint_violations.append('max_module_invocations_exceeded')
    actual_step_count = trace.get('actual_step_count', estimated_step_cost)
    if max_steps and actual_step_count > max_steps:
        hard_constraint_violations.append('max_steps_exceeded')
    actual_elapsed_hours = trace.get('actual_elapsed_hours', estimated_elapsed_hours)
    if deadline_days is not None and actual_elapsed_hours > float(deadline_days) * 24.0:
        hard_constraint_violations.append('deadline_exceeded')
    actual_budget_spend = trace.get('actual_budget_spend', estimated_budget_spend)
    if budget_limit is not None and float(actual_budget_spend) > float(budget_limit):
        hard_constraint_violations.append('budget_exceeded')
    if forbidden_hits:
        hard_constraint_violations.append('forbidden_outcome_triggered')
    if unknown_modules:
        hard_constraint_violations.append('unknown_module_executed')

    legality_satisfied = not invalid_transitions and not unknown_modules
    hard_constraints_satisfied = not hard_constraint_violations
    target_met = not target_misses

    matched_path_id, matched_exactly, extraneous_module_count = pick_reference_match(
        successful_modules,
        oracle.get('success_paths', []),
    )

    final_success = target_met and legality_satisfied and hard_constraints_satisfied

    success_type = 'failure'
    if final_success:
        if failed_steps:
            success_type = 'recovered_success'
        elif matched_path_id and matched_exactly:
            success_type = 'reference_success'
        elif matched_path_id and extraneous_module_count > 0:
            success_type = 'success_with_extraneous_modules'
        else:
            success_type = 'novel_success'

    penalties = oracle.get('evaluation', {})
    legality_penalty = float(penalties.get('invalid_transition_penalty', 1.0) or 1.0)
    unnecessary_penalty = float(penalties.get('unnecessary_module_penalty', 0.0) or 0.0)
    recovery_bonus = float(penalties.get('recovery_bonus', 0.0) or 0.0)

    legality_score = max(0.0, 1.0 - legality_penalty * len(invalid_transitions))
    constraint_score = 1.0 if hard_constraints_satisfied else 0.0
    efficiency_score = max(0.0, 1.0 - unnecessary_penalty * extraneous_module_count)
    recovery_score = recovery_bonus if success_type == 'recovered_success' else 0.0
    goal_score = target_state_coverage
    composite_score = min(
        1.0,
        (0.45 * goal_score) + (0.25 * legality_score) + (0.2 * constraint_score) + (0.1 * efficiency_score) + recovery_score,
    )

    return {
        'goal_id': goal['goal_id'],
        'final_success': final_success,
        'success_type': success_type,
        'target_state_coverage': target_state_coverage,
        'target_hits': target_hits,
        'target_misses': target_misses,
        'hard_constraints_satisfied': hard_constraints_satisfied,
        'hard_constraint_violations': hard_constraint_violations,
        'invalid_transition_count': len(invalid_transitions),
        'invalid_transitions': invalid_transitions,
        'failed_step_count': len(failed_steps),
        'failed_steps': failed_steps,
        'unknown_modules': unknown_modules,
        'used_reference_path': matched_path_id,
        'matched_reference_path_exactly': matched_exactly,
        'extraneous_module_count': extraneous_module_count,
        'executed_successful_modules': successful_modules,
        'replayed_final_state': sorted(replayed_state),
        'evaluated_final_state': sorted(evaluated_final_state),
        'score_breakdown': {
            'goal_score': goal_score,
            'legality_score': legality_score,
            'constraint_score': constraint_score,
            'efficiency_score': efficiency_score,
            'recovery_score': recovery_score,
            'composite_score': composite_score,
        },
        'resource_usage': {
            'attempted_module_invocations': attempted_module_invocations,
            'estimated_step_cost': estimated_step_cost,
            'actual_step_count': actual_step_count,
            'estimated_budget_spend': estimated_budget_spend,
            'actual_budget_spend': actual_budget_spend,
            'estimated_elapsed_hours': estimated_elapsed_hours,
            'actual_elapsed_hours': actual_elapsed_hours,
        },
    }


def main() -> None:
    args = parse_args()
    goal = load_json(Path(args.goal))
    oracle = load_json(Path(args.oracle))
    trace = load_json(Path(args.trace))
    modules_doc = load_json(Path(args.modules))
    result = evaluate_episode(goal, oracle, trace, modules_doc)

    final_success = result['final_success']
    success_type = result['success_type']
    target_state_coverage = result['target_state_coverage']
    hard_constraints_satisfied = result['hard_constraints_satisfied']
    invalid_transitions = result['invalid_transitions']
    hard_constraint_violations = result['hard_constraint_violations']
    extraneous_module_count = result['extraneous_module_count']
    matched_path_id = result['used_reference_path']

    if args.output_json:
        output_json = Path(args.output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if args.output_md:
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            '# Workflow Episode Evaluation',
            '',
            f"- goal_id: `{result['goal_id']}`",
            f"- final_success: {'yes' if final_success else 'no'}",
            f"- success_type: `{success_type}`",
            f"- target_state_coverage: {target_state_coverage:.3f}",
            f"- hard_constraints_satisfied: {'yes' if hard_constraints_satisfied else 'no'}",
            f"- invalid_transition_count: {len(invalid_transitions)}",
            f"- extraneous_module_count: {extraneous_module_count}",
            f"- used_reference_path: `{matched_path_id}`",
            '',
            '## Score Breakdown',
        ]
        for key, value in result['score_breakdown'].items():
            lines.append(f'- `{key}`: {value:.4f}')
        lines += ['', '## Violations']
        if not hard_constraint_violations and not invalid_transitions:
            lines.append('- none')
        else:
            for violation in hard_constraint_violations:
                lines.append(f'- `{violation}`')
            for violation in invalid_transitions:
                lines.append(f"- invalid_transition[{violation['index']}]: `{violation['module_id']}`")
        output_md.write_text('\n'.join(lines) + '\n')

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
