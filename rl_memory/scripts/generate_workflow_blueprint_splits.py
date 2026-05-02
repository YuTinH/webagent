#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
OUTPUT_PATH = ROOT / 'tasks' / 'workflow_blueprint_splits.json'
SUMMARY_PATH = ROOT / '.task_sync_meta' / 'workflow_blueprint_splits.md'


def assign_theme(theme_blueprints: list[dict]) -> dict[str, list[str]]:
    ordered = sorted(theme_blueprints, key=lambda bp: bp['blueprint_id'])
    count = len(ordered)
    split_map = {'train': [], 'dev': [], 'test': []}

    if count == 1:
        split_map['train'].append(ordered[0]['blueprint_id'])
        return split_map
    if count == 2:
        split_map['train'].append(ordered[0]['blueprint_id'])
        split_map['dev'].append(ordered[1]['blueprint_id'])
        return split_map
    if count == 3:
        split_map['train'].append(ordered[0]['blueprint_id'])
        split_map['dev'].append(ordered[1]['blueprint_id'])
        split_map['test'].append(ordered[2]['blueprint_id'])
        return split_map

    split_map['train'].append(ordered[0]['blueprint_id'])
    split_map['train'].append(ordered[1]['blueprint_id'])
    split_map['dev'].append(ordered[2]['blueprint_id'])
    split_map['test'].append(ordered[3]['blueprint_id'])
    for bp in ordered[4:]:
        split_map['train'].append(bp['blueprint_id'])
    return split_map


def main() -> None:
    library = json.loads(BLUEPRINTS_PATH.read_text())
    blueprints = library['blueprints']
    by_theme: dict[str, list[dict]] = defaultdict(list)
    blueprint_lookup = {bp['blueprint_id']: bp for bp in blueprints}
    for bp in blueprints:
        by_theme[bp['theme']].append(bp)

    splits = {'train': [], 'dev': [], 'test': []}
    for theme in sorted(by_theme):
        themed = assign_theme(by_theme[theme])
        for split_name, ids in themed.items():
            splits[split_name].extend(ids)

    for split_name in splits:
        splits[split_name].sort()

    split_summary = {}
    for split_name, ids in splits.items():
        split_summary[split_name] = {
            'count': len(ids),
            'themes': dict(sorted(Counter(blueprint_lookup[bp_id]['theme'] for bp_id in ids).items())),
        }

    payload = {
        'version': 1,
        'source_blueprint_library': str(BLUEPRINTS_PATH),
        'policy': {
            'split_unit': 'blueprint_id',
            'instance_assignment_rule': 'All workflow instances generated from the same blueprint_id must stay in the same split.',
            'theme_allocation_rule': {
                '1_blueprint': 'train only',
                '2_blueprints': 'train + dev',
                '3_blueprints': 'train + dev + test',
                '4_or_more_blueprints': 'two train, one dev, one test, extras to train',
            },
            'notes': [
                'This policy prevents train/dev/test leakage via parameter-only resampling from the same blueprint.',
                'Singleton themes stay in train until additional blueprints exist, to avoid brittle evaluation splits.',
            ],
        },
        'splits': splits,
        'summary': split_summary,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# Workflow Blueprint Splits',
        '',
        f'- source_blueprint_library: `{BLUEPRINTS_PATH}`',
        f'- split_file: `{OUTPUT_PATH}`',
        '',
        '## Counts',
    ]
    for split_name in ('train', 'dev', 'test'):
        lines.append(f"- `{split_name}`: {split_summary[split_name]['count']}")
    lines += ['', '## Theme Coverage']
    for split_name in ('train', 'dev', 'test'):
        lines.append(f'- `{split_name}`: {split_summary[split_name]["themes"]}')
    SUMMARY_PATH.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
