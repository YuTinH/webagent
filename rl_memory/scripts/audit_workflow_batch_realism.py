#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from audit_workflow_blueprint_realism import (
    audit_bank_issue_context,
    audit_career_theme,
    audit_education_theme,
    audit_government_theme,
    audit_health_theme,
    audit_home_theme,
    audit_newcomer_theme,
    audit_order_and_subscription_context,
    audit_security_theme,
    audit_social_theme,
    audit_travel_context,
)


ROOT = Path('/Users/masteryth/Documents/webagent')
DEFAULT_BATCH_ROOT = ROOT / 'tasks' / 'generated_workflow_split_batches' / 'workflow_split_batch_v19'
DEFAULT_REQUIREMENTS = ROOT / 'tasks' / 'workflow_quality_requirements.json'
DEFAULT_OUTPUT_JSON = ROOT / '.task_sync_meta' / 'workflow_batch_realism_audit.json'
DEFAULT_OUTPUT_MD = ROOT / '.task_sync_meta' / 'workflow_batch_realism_audit.md'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit generated workflow batches for human realism.')
    parser.add_argument('--batch-root', default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument('--requirements', default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument('--output-json', default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument('--output-md', default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument('--strict', action='store_true')
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def oracle_to_paths(oracle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            'path_id': path['path_id'],
            'steps': [{'module_id': module_id} for module_id in path.get('required_modules', [])],
        }
        for path in oracle.get('success_paths', [])
    ]


def make_workflow_view(
    goal: dict[str, Any],
    oracle: dict[str, Any],
    goal_ref: dict[str, Any],
) -> dict[str, Any]:
    return {
        'blueprint_id': goal_ref['blueprint_id'],
        'theme': goal['theme'],
        'initial_world_state': goal.get('initial_world_state', []),
        'target_state': goal.get('target_state', []),
        'paths': oracle_to_paths(oracle),
    }


def audit_goal(
    workflow_view: dict[str, Any],
    issues: list[dict[str, Any]],
    context_cfg: dict[str, Any],
    theme_cfg: dict[str, Any],
) -> None:
    audit_order_and_subscription_context(workflow_view, issues, context_cfg.get('order_support', {}))
    audit_bank_issue_context(workflow_view, issues, context_cfg.get('bank_account_issue', {}))
    audit_travel_context(workflow_view, issues, context_cfg.get('travel_booking', {}))
    audit_newcomer_theme(workflow_view, issues, theme_cfg.get('newcomer', {}).get('enabled', True))
    audit_government_theme(workflow_view, issues, theme_cfg.get('government', {}).get('enabled', True))
    audit_education_theme(workflow_view, issues, theme_cfg.get('education', {}).get('enabled', True))
    audit_health_theme(workflow_view, issues, theme_cfg.get('health', {}).get('enabled', True))
    audit_home_theme(workflow_view, issues, theme_cfg.get('home', {}).get('enabled', True))
    audit_social_theme(workflow_view, issues, theme_cfg.get('social', {}).get('enabled', True))
    audit_career_theme(workflow_view, issues, theme_cfg.get('career', {}).get('enabled', True))
    audit_security_theme(workflow_view, issues, theme_cfg.get('security', {}).get('enabled', True))


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root)
    requirements = load_json(Path(args.requirements))
    realism_cfg = requirements.get('realism', {})
    context_cfg = realism_cfg.get('contexts', {})
    theme_cfg = realism_cfg.get('themes', {})

    issues: list[dict[str, Any]] = []
    per_goal: list[dict[str, Any]] = []
    split_goal_counts: dict[str, int] = {}

    for split_dir in sorted(path for path in batch_root.iterdir() if path.is_dir() and (path / 'manifest.json').exists()):
        split = split_dir.name
        manifest = load_json(split_dir / 'manifest.json')
        split_goal_counts[split] = len(manifest.get('goals', []))
        for goal_ref in manifest.get('goals', []):
            goal = load_json(split_dir / goal_ref['goal_file'])
            oracle = load_json(split_dir / goal_ref['oracle_file'])
            workflow_view = make_workflow_view(goal, oracle, goal_ref)
            before = len(issues)
            audit_goal(workflow_view, issues, context_cfg, theme_cfg)
            goal_issues = issues[before:]
            for item in goal_issues:
                item['goal_id'] = goal_ref['goal_id']
                item['split'] = split
            per_goal.append(
                {
                    'goal_id': goal_ref['goal_id'],
                    'split': split,
                    'blueprint_id': goal_ref['blueprint_id'],
                    'theme': goal['theme'],
                    'issues': [item['issue'] for item in goal_issues],
                }
            )

    issue_type_counts = Counter(item['issue'] for item in issues)
    theme_issue_counts = Counter(item['theme'] for item in issues)
    split_issue_counts = Counter(item['split'] for item in issues)
    flagged_goals = sorted({item['goal_id'] for item in issues})

    report = {
        'version': 1,
        'batch_root': str(batch_root),
        'requirements': str(Path(args.requirements)),
        'split_goal_counts': split_goal_counts,
        'issue_count': len(issues),
        'flagged_goals': flagged_goals,
        'issue_type_counts': dict(sorted(issue_type_counts.items())),
        'theme_issue_counts': dict(sorted(theme_issue_counts.items())),
        'split_issue_counts': dict(sorted(split_issue_counts.items())),
        'issues': issues,
        'per_goal': per_goal,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# Workflow Batch Realism Audit',
        '',
        f'- batch_root: `{batch_root}`',
        f'- issue_count: {len(issues)}',
        '',
        '## Split Goal Counts',
    ]
    for split, count in sorted(split_goal_counts.items()):
        lines.append(f'- `{split}`: {count}')
    lines += ['', '## Issue Type Counts']
    if not issue_type_counts:
        lines.append('- none')
    else:
        for issue, count in sorted(issue_type_counts.items()):
            lines.append(f'- `{issue}`: {count}')
    lines += ['', '## Theme Issue Counts']
    if not theme_issue_counts:
        lines.append('- none')
    else:
        for theme, count in sorted(theme_issue_counts.items()):
            lines.append(f'- `{theme}`: {count}')
    lines += ['', '## Split Issue Counts']
    if not split_issue_counts:
        lines.append('- none')
    else:
        for split, count in sorted(split_issue_counts.items()):
            lines.append(f'- `{split}`: {count}')
    lines += ['', '## Issues']
    if not issues:
        lines.append('- none')
    else:
        for item in issues:
            path_suffix = f" [{item['path_id']}]" if 'path_id' in item else ''
            lines.append(
                f"- `{item['split']}` `{item['goal_id']}` `{item['blueprint_id']}`{path_suffix}: {item['issue']}"
            )
    output_md.write_text('\n'.join(lines) + '\n')

    if args.strict and issues:
        print('workflow batch realism audit failed', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
