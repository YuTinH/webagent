# Isolated Runtime Plan for OpenRLHF WebAgent Training

## Problem

Current training shares one mutable benchmark runtime across all rollouts:

- `data.db`
- `env/state.json`
- `tasks/*/task_spec.json`
- `tasks/*/oracle_trace.json`
- one HTTP server bound to one root directory

This forces us to serialize episodes with a global lock. The result is:

- rollout generation becomes effectively single-threaded
- invalid actions spend wall time in Playwright instead of GPU compute
- GPU utilization stays low even on `2 x H200 140GB`

## Goal

Remove the global lock and let multiple rollouts run safely in parallel.

The correct abstraction is:

- one isolated mutable runtime per rollout worker
- each runtime has its own DB, env state, task patches, and server port
- immutable assets are shared

## Design

### 1. Introduce a runtime root

Add a single runtime root override, for example:

- env var: `WEBAGENT_RUNTIME_ROOT`

All mutable/runtime path resolution should go through this root.

Instead of hardcoding repository root state, resolve:

- DB path from `${WEBAGENT_RUNTIME_ROOT}/data.db`
- env state from `${WEBAGENT_RUNTIME_ROOT}/env/state.json`
- patched task specs from `${WEBAGENT_RUNTIME_ROOT}/tasks/...`
- server site/task loading from `${WEBAGENT_RUNTIME_ROOT}`

If the env var is absent, fall back to the repo root for backward compatibility.

### 2. Per-worker sandbox directory

For each rollout worker, create a sandbox directory such as:

- `/tmp/webagent_runs/<run_id>/worker_<k>/`

Sandbox layout:

- `data.db`                     writable copy
- `env/`                        writable copy
- `tasks/`                      writable copy for patched specs/traces
- `sites/`                      shared symlink or bind mount
- `database/`                   shared symlink
- code files                    shared from repo root

The mutable state is isolated. The large static assets remain shared.

### 3. One server per worker

Run one benchmark server per sandbox, each on its own port.

For example:

- worker 0 -> port 18140
- worker 1 -> port 18141
- worker 2 -> port 18142

Each server reads only from its sandbox root.

That means `BrowserEnv` must accept a `base_url` or `server_port` argument instead of hardcoding `http://localhost:8014`.

### 4. Patch specs and traces inside sandbox only

Current `patch_spec()` and `patch_trace()` mutate files under repo `tasks/`.

That must become sandbox-local:

- patch `${runtime_root}/tasks/<task_id>/task_spec.json`
- patch `${runtime_root}/tasks/<task_id>/oracle_trace.json`

No repo-global mutation during training.

### 5. Reset mutable state per episode, not per process

Within one worker sandbox:

- `init_db.py` resets sandbox `data.db`
- env reset rewrites sandbox `env/state.json`
- task patching rewrites sandbox `tasks/`

This is enough to isolate episodes while reusing the same worker process and server.

That is much cheaper than creating a fresh sandbox for every episode.

## Minimal Implementation Path

### Phase 1: make paths runtime-root aware

Update these components to accept runtime root override:

- `server.py`
- `init_db.py`
- `chain_runner_dynamic.py`
- `task_handlers/*` that read/write `data.db`
- `agent/browser_env.py` for configurable base URL
- `rl_memory/openrlhf/agent_func_webagent.py`

This phase should preserve existing single-root behavior when the env var is absent.

### Phase 2: sandbox bootstrap

Create a runtime manager module, e.g.:

- `rl_memory/openrlhf/runtime_manager.py`

Responsibilities:

- allocate worker sandbox dir
- copy mutable files/directories
- symlink immutable dirs
- allocate a free port
- launch worker-local server
- return runtime metadata:
  - `runtime_root`
  - `server_url`
  - `worker_id`
  - `pid`

### Phase 3: bind one sandbox to one LLMRayActor

Each rollout actor should own exactly one sandbox.

This gives:

- no cross-actor state collision
- amortized startup cost
- stable server lifecycle

### Phase 4: remove global file lock

Once each actor has its own sandbox root, delete the current global lock logic from:

- `rl_memory/openrlhf/agent_func_webagent.py`

## Recommended Concurrency Model

Use one sandbox per rollout engine / actor, not per sample.

Reason:

- per-sample isolation is too expensive
- per-actor isolation is enough for correctness
- DB/env reset per episode is cheap relative to browser startup

## Performance Notes

### Keep shared

These should stay shared to reduce disk pressure:

- `sites/`
- `database/schema.sql`
- `database/seed_data.sql`
- code files
- model files

### Copy or overlay

These must be isolated:

- `data.db`
- `env/state.json`
- patched `tasks/*`

### Further optimization

If full `tasks/` copy is too expensive, switch to lazy copy-on-write:

- symlink all task files initially
- copy only the task files that will be patched in the current episode

## What This Fixes

This removes the current bottleneck where:

- all rollouts compete for one SQLite DB
- all rollouts overwrite one `env/state.json`
- all rollouts patch one global `tasks/`
- all actors queue behind one global lock

After this change, GPU utilization should improve because:

- multiple browser rollouts can proceed in parallel
- vLLM/actor work no longer waits on one serialized environment

## Recommended First Target

Implement a first working version with:

- `2` isolated worker sandboxes
- `2` server ports
- one sandbox bound to each rollout actor

Do not over-optimize file layout in the first pass. Correctness first.

## Files Most Likely To Change

- `/Users/masteryth/Documents/webagent/server.py`
- `/Users/masteryth/Documents/webagent/init_db.py`
- `/Users/masteryth/Documents/webagent/chain_runner_dynamic.py`
- `/Users/masteryth/Documents/webagent/agent/browser_env.py`
- `/Users/masteryth/Documents/webagent/rl_memory/openrlhf/agent_func_webagent.py`
- `/Users/masteryth/Documents/webagent/task_handlers/d_finance.py`
- other `task_handlers/*` that directly resolve repo-global DB/env paths
- new: `/Users/masteryth/Documents/webagent/rl_memory/openrlhf/runtime_manager.py`

## Immediate Next Step

Implement Phase 1 first:

- add `WEBAGENT_RUNTIME_ROOT`
- add configurable server base URL
- make DB/env/task patching runtime-root aware

Until that lands, any attempt to increase rollout concurrency will remain bottlenecked by the global mutable benchmark state.
