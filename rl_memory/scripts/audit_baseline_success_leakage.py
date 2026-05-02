#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = ROOT / 'tasks'
STATE_PATH = ROOT / 'env' / 'state.json'
DB_PATH = ROOT / 'data.db'

import sys
sys.path.insert(0, str(ROOT))
from agent.assertions_dsl import AssertionDSL  # noqa: E402


class _MockLocator:
    def count(self) -> int:
        return 0
    def inner_text(self) -> str:
        return ''
    def get_attribute(self, _name: str) -> str | None:
        return None


class _MockPage:
    url = 'about:blank'
    def locator(self, _selector: str) -> _MockLocator:
        return _MockLocator()


def load_env() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))


def load_memory() -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT key, value FROM memory_kv').fetchall()
    conn.close()
    memory: dict[str, Any] = {}
    for row in rows:
        memory[row['key']] = row['value']
    return memory


def env_lookup(env: dict[str, Any], channel: str, path: str) -> Any:
    if channel != 'env':
        raise KeyError(channel)
    cur: Any = env
    for part in str(path).split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def iter_task_specs() -> list[Path]:
    return sorted(TASKS_ROOT.glob('*/task_spec.json'))


def main() -> None:
    env = load_env()
    memory = load_memory()
    dsl = AssertionDSL(_MockPage(), memory, lambda channel, path: env_lookup(env, channel, path))

    records: list[dict[str, Any]] = []
    passed_counter: Counter[str] = Counter()
    total = 0

    for spec_path in iter_task_specs():
        total += 1
        spec = json.loads(spec_path.read_text(encoding='utf-8'))
        criteria = [str(x).strip() for x in spec.get('success_criteria', []) if str(x).strip()]
        if not criteria:
            continue
        passed: list[str] = []
        failed: list[str] = []
        errors: list[str] = []
        for criterion in criteria:
            try:
                if dsl.evaluate(criterion):
                    passed.append(criterion)
                else:
                    failed.append(criterion)
            except Exception as exc:
                errors.append(f'{criterion} :: {exc}')
                failed.append(criterion)
        if passed:
            record = {
                'task_id': spec.get('task_id', spec_path.parent.name),
                'task_dir': spec_path.parent.name,
                'passed_count': len(passed),
                'criteria_count': len(criteria),
                'passed_criteria': passed,
                'failed_criteria': failed,
                'error_count': len(errors),
            }
            records.append(record)
            for criterion in passed:
                if criterion.startswith("mem('"):
                    passed_counter['mem'] += 1
                elif criterion.startswith("json('env'"):
                    passed_counter['env'] += 1
                elif criterion.startswith('url()'):
                    passed_counter['url'] += 1
                else:
                    passed_counter['other'] += 1

    records.sort(key=lambda x: (-x['passed_count'], x['task_id']))
    out = {
        'total_task_specs': total,
        'flagged_task_specs': len(records),
        'passed_assertion_type_counts': dict(passed_counter),
        'records': records,
    }
    out_json = ROOT / 'docs' / 'baseline_success_leakage_audit.json'
    out_md = ROOT / 'docs' / 'baseline_success_leakage_audit.md'
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lines = [
        '# Baseline Success Leakage Audit',
        '',
        f'- Total task specs: {total}',
        f'- Flagged task specs: {len(records)}',
        f'- Passed assertion types: {dict(passed_counter)}',
        '',
        '## Flagged Tasks',
        '',
    ]
    for rec in records:
        lines.append(f"- `{rec['task_id']}` (`{rec['task_dir']}`): {rec['passed_count']}/{rec['criteria_count']} criteria already pass at baseline")
        for criterion in rec['passed_criteria'][:5]:
            lines.append(f'  - `{criterion}`')
    out_md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(out_json)
    print(out_md)
    print(json.dumps({'flagged_task_specs': len(records), 'passed_assertion_type_counts': dict(passed_counter)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
