#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
MODULES_PATH = ROOT / 'tasks' / 'workflow_module_library.json'


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def ensure_preconditions(state: set[str], requires: dict[str, list[str]], initial: set[str]) -> None:
    for predicate in requires.get('all_of', []):
        if predicate not in state:
            initial.add(predicate)
            state.add(predicate)

    any_of = [predicate for predicate in requires.get('any_of', []) if predicate]
    if any_of and not any(predicate in state for predicate in any_of):
        chosen = any_of[0]
        initial.add(chosen)
        state.add(chosen)

    for predicate in requires.get('none_of', []):
        state.discard(predicate)
        initial.discard(predicate)


def recompute_initial_state(blueprint: dict, modules_by_id: dict[str, dict]) -> list[str]:
    required_initial: set[str] = set(
        predicate
        for predicate in blueprint.get('initial_world_state', [])
        if isinstance(predicate, str)
    )
    for path in blueprint['paths']:
        state: set[str] = set(required_initial)
        for step in path['steps']:
            module = modules_by_id[step['module_id']]
            ensure_preconditions(state, module['requires'], required_initial)
            state -= set(module['effects'].get('removes', []))
            state |= set(module['effects'].get('adds', []))
    return sorted(required_initial)


def main() -> None:
    blueprints_doc = load_json(BLUEPRINTS_PATH)
    modules = load_json(MODULES_PATH)['modules']
    modules_by_id = {module['module_id']: module for module in modules}

    updated = 0
    for blueprint in blueprints_doc['blueprints']:
        new_initial = recompute_initial_state(blueprint, modules_by_id)
        if blueprint.get('initial_world_state') != new_initial:
            blueprint['initial_world_state'] = new_initial
            updated += 1

    BLUEPRINTS_PATH.write_text(json.dumps(blueprints_doc, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'blueprints': len(blueprints_doc['blueprints']),
        'updated_initial_world_state': updated,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
