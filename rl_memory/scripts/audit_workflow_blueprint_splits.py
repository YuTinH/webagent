#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
SPLITS_PATH = ROOT / 'tasks' / 'workflow_blueprint_splits.json'
DEFAULT_OUTPUT_JSON = ROOT / '.task_sync_meta' / 'workflow_blueprint_split_audit.json'
DEFAULT_OUTPUT_MD = ROOT / '.task_sync_meta' / 'workflow_blueprint_split_audit.md'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit blueprint-level split assignments.')
    parser.add_argument('--blueprints', default=str(BLUEPRINTS_PATH))
    parser.add_argument('--splits', default=str(SPLITS_PATH))
    parser.add_argument('--output-json', default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument('--output-md', default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument('--strict', action='store_true')
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def issue(level: str, code: str, detail: str) -> dict[str, str]:
    return {'level': level, 'issue': code, 'detail': detail}


def main() -> None:
    args = parse_args()
    blueprint_doc = load_json(Path(args.blueprints))
    split_doc = load_json(Path(args.splits))
    blueprints = blueprint_doc['blueprints']
    blueprint_lookup = {bp['blueprint_id']: bp for bp in blueprints}
    all_blueprint_ids = set(blueprint_lookup)
    by_theme: dict[str, list[str]] = defaultdict(list)
    for bp in blueprints:
        by_theme[bp['theme']].append(bp['blueprint_id'])

    issues: list[dict[str, str]] = []
    split_names = ('train', 'dev', 'test')
    assigned: dict[str, list[str]] = {name: list(split_doc['splits'].get(name, [])) for name in split_names}
    assignment_counter = Counter(bp_id for ids in assigned.values() for bp_id in ids)

    for bp_id, count in sorted(assignment_counter.items()):
        if count > 1:
            issues.append(issue('error', 'blueprint_assigned_to_multiple_splits', f'{bp_id} appears {count} times across splits.'))
        if bp_id not in all_blueprint_ids:
            issues.append(issue('error', 'unknown_blueprint_id_in_split', f'{bp_id} is not present in blueprint library.'))

    missing = sorted(all_blueprint_ids - set(assignment_counter))
    for bp_id in missing:
        issues.append(issue('error', 'unassigned_blueprint_id', f'{bp_id} is not assigned to any split.'))

    for split_name in split_names:
        if not assigned[split_name]:
            issues.append(issue('error', 'empty_split', f'{split_name} split is empty.'))

    theme_coverage = {name: Counter(blueprint_lookup[bp_id]['theme'] for bp_id in ids if bp_id in blueprint_lookup) for name, ids in assigned.items()}
    for theme, ids in sorted(by_theme.items()):
        count = len(ids)
        present = {split_name for split_name in split_names if theme_coverage[split_name].get(theme, 0) > 0}
        if count >= 3:
            missing_splits = [split_name for split_name in split_names if split_name not in present]
            for split_name in missing_splits:
                issues.append(issue('error', 'theme_with_3plus_blueprints_missing_split_coverage', f'Theme {theme} has {count} blueprints but is absent from {split_name}.'))
        elif count == 2:
            if 'train' not in present:
                issues.append(issue('error', 'theme_with_2_blueprints_missing_train', f'Theme {theme} has 2 blueprints but none are in train.'))
            if len(present) < 2:
                issues.append(issue('error', 'theme_with_2_blueprints_underdistributed', f'Theme {theme} has 2 blueprints but appears in only {sorted(present)}.'))
        elif count == 1:
            only_id = ids[0]
            if assignment_counter[only_id] != 1 or only_id not in assigned['train']:
                issues.append(issue('error', 'singleton_theme_not_kept_in_train', f'Singleton theme {theme} should stay in train until more blueprints exist.'))

    split_sizes = {name: len(ids) for name, ids in assigned.items()}
    total = sum(split_sizes.values())
    ratios = {name: (split_sizes[name] / total if total else 0.0) for name in split_names}
    if ratios['train'] < 0.4:
        issues.append(issue('warning', 'train_split_too_small', f"Train ratio is {ratios['train']:.3f}."))
    if ratios['dev'] < 0.1:
        issues.append(issue('warning', 'dev_split_too_small', f"Dev ratio is {ratios['dev']:.3f}."))
    if ratios['test'] < 0.1:
        issues.append(issue('warning', 'test_split_too_small', f"Test ratio is {ratios['test']:.3f}."))

    hard_fail_reasons = sorted({item['issue'] for item in issues if item['level'] == 'error'})
    report = {
        'version': 1,
        'blueprints_path': str(Path(args.blueprints)),
        'splits_path': str(Path(args.splits)),
        'total_blueprints': len(all_blueprint_ids),
        'split_sizes': split_sizes,
        'split_ratios': ratios,
        'theme_coverage': {name: dict(sorted(counter.items())) for name, counter in theme_coverage.items()},
        'issues': issues,
        'hard_fail_reasons': hard_fail_reasons,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# Workflow Blueprint Split Audit',
        '',
        f'- blueprints_path: `{Path(args.blueprints)}`',
        f'- splits_path: `{Path(args.splits)}`',
        f'- total_blueprints: {len(all_blueprint_ids)}',
        f"- split_sizes: {split_sizes}",
        f"- split_ratios: {ratios}",
        f"- strict_status: {'pass' if not hard_fail_reasons else 'fail'}",
        '',
        '## Theme Coverage',
    ]
    for split_name in split_names:
        lines.append(f"- `{split_name}`: {dict(sorted(theme_coverage[split_name].items()))}")
    lines += ['', '## Issues']
    if not issues:
        lines.append('- none')
    else:
        for item in issues:
            lines.append(f"- [{item['level']}] {item['issue']}: {item['detail']}")
    output_md.write_text('\n'.join(lines) + '\n')

    if args.strict and hard_fail_reasons:
        print('workflow blueprint split audit failed: ' + ', '.join(hard_fail_reasons), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
