#!/usr/bin/env python3
"""
Task Validator - Verify all task definitions are valid
"""

import json
import os
from pathlib import Path
from jsonschema import validate, ValidationError


def validate_task_directory(task_dir):
    """Validate a single task directory"""
    errors = []
    warnings = []

    # Check required files exist
    required_files = ['task_spec.json', 'oracle_trace.json', 'expected_memory.json']
    for filename in required_files:
        filepath = task_dir / filename
        if not filepath.exists():
            errors.append(f"Missing file: {filename}")

    if errors:
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # Load and validate each file
    try:
        # Load task spec
        with open(task_dir / 'task_spec.json') as f:
            task_spec = json.load(f)

        # Load oracle trace
        with open(task_dir / 'oracle_trace.json') as f:
            oracle_trace = json.load(f)

        # Load expected memory
        with open(task_dir / 'expected_memory.json') as f:
            expected_memory = json.load(f)

        # Basic validation
        if 'task_id' not in task_spec:
            errors.append("task_spec missing task_id")

        if 'steps' not in oracle_trace:
            errors.append("oracle_trace missing steps")

        # Check task_id consistency
        if task_spec.get('task_id') != oracle_trace.get('task_id'):
            warnings.append(f"task_id mismatch: spec={task_spec.get('task_id')}, trace={oracle_trace.get('task_id')}")

        # Check memory sources
        for key, entry in expected_memory.items():
            if 'source' in entry and entry['source'] != task_spec.get('task_id'):
                warnings.append(f"Memory entry {key} has mismatched source")

        # Validate against schema (if available)
        schema_dir = Path(__file__).parent.parent / 'schemas'
        if schema_dir.exists():
            try:
                with open(schema_dir / 'task_spec.json') as f:
                    task_schema = json.load(f)
                validate(instance=task_spec, schema=task_schema)
            except ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")
            except FileNotFoundError:
                warnings.append("Schema file not found, skipping validation")

    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {e}")
    except Exception as e:
        errors.append(f"Unexpected error: {e}")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def main():
    """Validate all tasks"""
    tasks_dir = Path(__file__).parent

    print("="*80)
    print("🔍 TASK VALIDATOR")
    print("="*80)

    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])

    results = {}
    for task_dir in task_dirs:
        print(f"\n📋 Validating {task_dir.name}...")
        result = validate_task_directory(task_dir)
        results[task_dir.name] = result

        if result['valid']:
            print(f"  ✅ Valid")
        else:
            print(f"  ❌ Invalid")
            for error in result['errors']:
                print(f"     Error: {error}")

        if result['warnings']:
            for warning in result['warnings']:
                print(f"     ⚠️  Warning: {warning}")

    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)

    total = len(results)
    valid = sum(1 for r in results.values() if r['valid'])
    invalid = total - valid

    print(f"\nTotal tasks: {total}")
    print(f"✅ Valid: {valid}")
    print(f"❌ Invalid: {invalid}")

    if invalid == 0:
        print("\n🎉 All tasks are valid!")
        return 0
    else:
        print(f"\n⚠️  {invalid} task(s) need attention")
        return 1


if __name__ == "__main__":
    exit(main())
