#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
SPLITS_PATH = ROOT / 'tasks' / 'workflow_blueprint_splits.json'
OUTPUT_ROOT = ROOT / 'tasks' / 'generated_workflow_split_batches'
SPLIT_AUDIT = ROOT / 'rl_memory' / 'scripts' / 'audit_workflow_blueprint_splits.py'
REALISM_AUDIT = ROOT / 'rl_memory' / 'scripts' / 'audit_workflow_blueprint_realism.py'
BATCH_REALISM_AUDIT = ROOT / 'rl_memory' / 'scripts' / 'audit_workflow_batch_realism.py'
BATCH_GENERATOR = ROOT / 'rl_memory' / 'scripts' / 'generate_workflow_goal_batch.py'
QUALITY_AUDIT = ROOT / 'rl_memory' / 'scripts' / 'audit_workflow_goal_quality.py'
QUALITY_REQUIREMENTS = ROOT / 'tasks' / 'workflow_quality_requirements.json'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Generate train/dev/test workflow batches from blueprint-level split assignments.'
    )
    parser.add_argument('--blueprints', default=str(BLUEPRINTS_PATH))
    parser.add_argument('--splits', default=str(SPLITS_PATH))
    parser.add_argument('--requirements', default=str(QUALITY_REQUIREMENTS))
    parser.add_argument('--output-root', default=str(OUTPUT_ROOT))
    parser.add_argument('--batch-name', required=True)
    parser.add_argument('--count-per-blueprint', type=int, default=10)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--force', action='store_true')
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def run_checked(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    blueprints_path = Path(args.blueprints)
    splits_path = Path(args.splits)
    requirements_path = Path(args.requirements)
    batch_root = Path(args.output_root) / args.batch_name

    if batch_root.exists():
        if not args.force:
            raise SystemExit(f'batch root already exists: {batch_root}')
        shutil.rmtree(batch_root)
    batch_root.mkdir(parents=True, exist_ok=True)

    run_checked(
        [
            sys.executable,
            str(REALISM_AUDIT),
            '--blueprints',
            str(blueprints_path),
            '--requirements',
            str(requirements_path),
            '--output-json',
            str(batch_root / 'workflow_blueprint_realism_audit.json'),
            '--output-md',
            str(batch_root / 'workflow_blueprint_realism_audit.md'),
            '--strict',
        ]
    )

    run_checked(
        [
            sys.executable,
            str(SPLIT_AUDIT),
            '--blueprints',
            str(blueprints_path),
            '--splits',
            str(splits_path),
            '--output-json',
            str(batch_root / 'workflow_blueprint_split_audit.json'),
            '--output-md',
            str(batch_root / 'workflow_blueprint_split_audit.md'),
            '--strict',
        ]
    )

    split_doc = load_json(splits_path)
    split_summary: dict[str, Any] = {}

    for split_index, split_name in enumerate(('train', 'dev', 'test')):
        blueprint_ids = split_doc['splits'].get(split_name, [])
        ids_path = batch_root / f'{split_name}_blueprint_ids.json'
        ids_path.write_text(
            json.dumps({'blueprint_ids': blueprint_ids}, ensure_ascii=False, indent=2) + '\n'
        )

        split_seed = args.seed + split_index
        run_checked(
            [
                sys.executable,
                str(BATCH_GENERATOR),
                '--blueprints',
                str(blueprints_path),
                '--blueprint-ids-file',
                str(ids_path),
                '--requirements',
                str(requirements_path),
                '--output-root',
                str(batch_root),
                '--batch-name',
                split_name,
                '--count-per-blueprint',
                str(args.count_per_blueprint),
                '--seed',
                str(split_seed),
                '--force',
            ]
        )

        split_dir = batch_root / split_name
        run_checked(
            [
                sys.executable,
                str(QUALITY_AUDIT),
                '--oracle-dir',
                str(split_dir / 'workflow_oracles'),
                '--requirements',
                str(requirements_path),
                '--output-json',
                str(split_dir / 'workflow_goal_quality_audit.json'),
                '--output-md',
                str(split_dir / 'workflow_goal_quality_audit.md'),
                '--strict',
            ]
        )

        manifest = load_json(split_dir / 'manifest.json')
        quality = load_json(split_dir / 'workflow_goal_quality_audit.json')
        split_summary[split_name] = {
            'blueprint_count': len(blueprint_ids),
            'goal_count': len(manifest['goals']),
            'multi_path_goals': quality['multi_path_goals'],
            'multi_path_ratio': quality['multi_path_ratio'],
            'batch_root': str(split_dir),
            'seed': split_seed,
        }

    top_manifest = {
        'version': 1,
        'batch_name': args.batch_name,
        'blueprints': str(blueprints_path),
        'splits': str(splits_path),
        'requirements': str(requirements_path),
        'count_per_blueprint': args.count_per_blueprint,
        'seed': args.seed,
        'summary': split_summary,
    }
    (batch_root / 'manifest.json').write_text(
        json.dumps(top_manifest, ensure_ascii=False, indent=2) + '\n'
    )

    run_checked(
        [
            sys.executable,
            str(BATCH_REALISM_AUDIT),
            '--batch-root',
            str(batch_root),
            '--requirements',
            str(requirements_path),
            '--output-json',
            str(batch_root / 'workflow_batch_realism_audit.json'),
            '--output-md',
            str(batch_root / 'workflow_batch_realism_audit.md'),
            '--strict',
        ]
    )

    print(
        json.dumps(
            {
                'batch_root': str(batch_root),
                'count_per_blueprint': args.count_per_blueprint,
                'summary': split_summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
