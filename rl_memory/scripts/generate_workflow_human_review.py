#!/usr/bin/env python3
"""Generate a lightweight human-review bundle for a workflow split batch.

This is intentionally simple: it samples representative goals from selected splits,
summarizes instruction/target/path structure, and writes Markdown + JSON artifacts
that can be checked after each blueprint expansion round.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path('/Users/masteryth/Documents/webagent')
DEFAULT_META_ROOT = ROOT / '.task_sync_meta'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate a human-review summary for a workflow split batch')
    parser.add_argument('--batch-root', required=True, help='Path to generated workflow split batch root')
    parser.add_argument('--splits', nargs='*', default=['dev', 'test'], help='Splits to sample from')
    parser.add_argument('--max-per-theme', type=int, default=1, help='Max sampled goals per theme per split')
    parser.add_argument(
        '--priority-blueprint',
        action='append',
        default=[],
        help='Blueprint id to explicitly include in the review if present in any split. Can be passed multiple times.',
    )
    parser.add_argument('--output-json', help='Path to write JSON review summary')
    parser.add_argument('--output-md', help='Path to write Markdown review summary')
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def summarize_quality(split_root: Path) -> dict[str, Any]:
    audit = load_json(split_root / 'workflow_goal_quality_audit.json')
    return {
        'total_goals': audit['total_goals'],
        'multi_path_goals': audit['multi_path_goals'],
        'multi_path_ratio': audit['multi_path_ratio'],
        'meets_target': audit['meets_target'],
        'hard_fail_reasons': audit['hard_fail_reasons'],
        'summary': audit['summary'],
    }


def sample_split(split_root: Path, split: str, max_per_theme: int) -> dict[str, Any]:
    manifest = load_json(split_root / 'manifest.json')
    by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for goal_ref in manifest['goals']:
        by_theme[goal_ref['theme']].append(goal_ref)

    samples: list[dict[str, Any]] = []
    for theme in sorted(by_theme):
        for goal_ref in by_theme[theme][:max_per_theme]:
            goal = load_json(split_root / goal_ref['goal_file'])
            oracle = load_json(split_root / goal_ref['oracle_file'])
            samples.append(
                {
                    'split': split,
                    'theme': theme,
                    'blueprint_id': goal_ref['blueprint_id'],
                    'goal_id': goal_ref['goal_id'],
                    'instruction': goal['instruction'],
                    'initial_world_state': goal.get('initial_world_state', []),
                    'target_state': goal.get('target_state', []),
                    'composition_type': goal_ref['composition_type'],
                    'success_paths': [
                        {
                            'path_id': path['path_id'],
                            'required_modules': path['required_modules'],
                        }
                        for path in oracle.get('success_paths', [])
                    ],
                }
            )
    return {
        'split': split,
        'quality': summarize_quality(split_root),
        'samples': samples,
    }


def collect_priority_samples(batch_root: Path, priority_blueprints: list[str]) -> list[dict[str, Any]]:
    if not priority_blueprints:
        return []
    priority_set = set(priority_blueprints)
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for split_root in sorted(path for path in batch_root.iterdir() if path.is_dir() and (path / 'manifest.json').exists()):
        split = split_root.name
        manifest = load_json(split_root / 'manifest.json')
        for goal_ref in manifest['goals']:
            bid = goal_ref['blueprint_id']
            if bid not in priority_set or bid in seen:
                continue
            goal = load_json(split_root / goal_ref['goal_file'])
            oracle = load_json(split_root / goal_ref['oracle_file'])
            collected.append(
                {
                    'split': split,
                    'theme': goal_ref['theme'],
                    'blueprint_id': bid,
                    'goal_id': goal_ref['goal_id'],
                    'instruction': goal['instruction'],
                    'initial_world_state': goal.get('initial_world_state', []),
                    'target_state': goal.get('target_state', []),
                    'composition_type': goal_ref['composition_type'],
                    'success_paths': [
                        {
                            'path_id': path['path_id'],
                            'required_modules': path['required_modules'],
                        }
                        for path in oracle.get('success_paths', [])
                    ],
                }
            )
            seen.add(bid)
    return collected


def default_output_paths(batch_root: Path) -> tuple[Path, Path]:
    batch_name = batch_root.name
    return (
        DEFAULT_META_ROOT / f'{batch_name}_human_review.json',
        DEFAULT_META_ROOT / f'{batch_name}_human_review.md',
    )


def to_markdown(batch_root: Path, review: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f'# Workflow Human Review: {batch_root.name}')
    lines.append('')
    lines.append(f'- batch_root: `{batch_root}`')
    lines.append('')
    lines.append('## Structural Summary')
    for split_data in review['splits']:
        q = split_data['quality']
        s = split_data['split']
        lines.append(
            f'- `{s}`: {q["total_goals"]} goals, multi-path ratio {q["multi_path_ratio"]:.4f}, '
            f'subset-like {q["summary"]["subset_like_multi_path_goals"]}, '
            f'initial-target-overlap {q["summary"]["initial_target_overlap_goals"]}, '
            f'hard_fail_reasons={q["hard_fail_reasons"]}'
        )
    for split_data in review['splits']:
        lines.append('')
        lines.append(f'## {split_data["split"].upper()} Samples')
        for sample in split_data['samples']:
            lines.append(f'- `{sample["theme"]}` `{sample["blueprint_id"]}` `{sample["goal_id"]}`')
            lines.append(f'  instruction: {sample["instruction"]}')
            lines.append(f'  initial: {sample["initial_world_state"]}')
            lines.append(f'  target: {sample["target_state"]}')
            for path in sample['success_paths']:
                lines.append(f'  path `{path["path_id"]}`: {" -> ".join(path["required_modules"])}')
    if review.get('priority_samples'):
        lines.append('')
        lines.append('## Priority Blueprint Samples')
        for sample in review['priority_samples']:
            lines.append(
                f'- `{sample["split"]}` `{sample["theme"]}` `{sample["blueprint_id"]}` `{sample["goal_id"]}`'
            )
            lines.append(f'  instruction: {sample["instruction"]}')
            lines.append(f'  initial: {sample["initial_world_state"]}')
            lines.append(f'  target: {sample["target_state"]}')
            for path in sample['success_paths']:
                lines.append(f'  path `{path["path_id"]}`: {" -> ".join(path["required_modules"])}')
    lines.append('')
    lines.append('## Reviewer Notes')
    lines.append('- Fill in semantic issues here after reading the sampled instructions and paths.')
    return '\n'.join(lines) + '\n'


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root).resolve()
    out_json, out_md = default_output_paths(batch_root)
    if args.output_json:
        out_json = Path(args.output_json).resolve()
    if args.output_md:
        out_md = Path(args.output_md).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    review = {
        'batch_root': str(batch_root),
        'splits': [sample_split(batch_root / split, split, args.max_per_theme) for split in args.splits],
        'priority_blueprints': args.priority_blueprint,
        'priority_samples': collect_priority_samples(batch_root, args.priority_blueprint),
    }
    out_json.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    out_md.write_text(to_markdown(batch_root, review))
    print(json.dumps({'output_json': str(out_json), 'output_md': str(out_md)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
