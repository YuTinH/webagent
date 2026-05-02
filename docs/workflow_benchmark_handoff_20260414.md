# Workflow Benchmark Handoff (2026-04-14)

## Scope
- Repo root: `/Users/masteryth/Documents/webagent`
- Remote active benchmark root: `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent`
- Current model under evaluation: `Qwen2.5-7B-Instruct`
- Active benchmark batch: `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20`

## What This Benchmark Actually Is

This is not a flat single-page task benchmark. It is a compositional workflow benchmark built from reusable atomic web tasks and hidden workflow oracles.

At a high level:
- A workflow goal gives the agent a high-level real-world objective in natural language.
- The agent is not told the gold decomposition into atomic tasks/modules.
- The hidden oracle defines legal module combinations, dependencies, target states, and reference successful paths.
- Evaluation allows novel success if the final target state is reached through legal transitions without violating hard constraints.

### Themes
Current `v20` workflow split covers 14 themes:
- `career`
- `crisis`
- `education`
- `support`
- `daily`
- `travel`
- `composite`
- `newcomer`
- `security`
- `home`
- `finance`
- `health`
- `social`
- `government`

### Split Size
From `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/manifest.json`:
- `train`: `4760` goals
- `dev`: `140` goals
- `test`: `140` goals

Each `dev/test` split has:
- `14` blueprints
- `10` sampled goals per blueprint

### Sample Structure
Each workflow sample is represented by:
- a workflow goal instance under:
  - `.../workflow_goal_instances/`
- a hidden workflow oracle under:
  - `.../workflow_oracles/`

A goal instance includes fields such as:
- `goal_id`
- `theme`
- `instruction`
- `visible_constraints`
- `initial_world_state`
- `target_state`
- `max_steps`
- `max_module_invocations`

The oracle side includes:
- `success_paths`
- `reference_invocations`
- module-level dependency/effect structure
- evaluation knobs such as invalid transition and redundancy penalties

### What Is Being Evaluated
The benchmark is designed to answer three questions:
- whether the final high-level goal was achieved
- whether the module sequence and state transitions were legal
- whether the goal was achieved with reasonable cost/efficiency

The intended interpretation is:
- `success_paths` are references, not the only allowed path
- `reference_invocations` are parameterized reference examples, not the only legal instantiation
- novel valid solutions should count as success

### Output / Scoring Concepts
Episode-level outputs include fields such as:
- `final_success`
- `success_type`
- `target_state_coverage`
- `invalid_transition_count`
- `hard_constraint_violations`
- `used_reference_path`
- `composite_score`

Important success labels:
- `reference_success`
- `novel_success`
- `recovered_success`
- `failure`

This means the benchmark is explicitly not “path imitation only”. It is a legality-aware, target-state-oriented workflow benchmark.

## Operating Principles
- Fix benchmark correctness, infra, and task-definition debt first.
- Do not relax global benchmark success accounting.
- Do not count failures as successes.
- Keep `per_goal runtime isolation`.
- Delay difficulty audit until correctness/infra is sufficiently clean.

## Authoritative Paths
- Use:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/sites`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/tasks`
- Do not use top-level stale copies:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/sites`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/tasks`

## QZCLI Usage Notes

### Dev Machine Identity
- Dev machine display name:
  - `webagent`
- Current notebook id:
  - `7b825dbc-6d73-4347-a944-4cfbd2325d7a`

### Stable Workflow
1. Refresh login if auth looks stale:

```bash
qzcli login
```

2. For first-time sessions or stale resource resolution, refresh cached resources:

```bash
qzcli res -u
```

3. Execute commands on the dev machine by name:

```bash
qzcli exec webagent --timeout 30 'pwd'
qzcli exec webagent --timeout 30 'ps -ef | grep run_workflow_benchmark.py | grep -v grep'
```

4. `exec` also works with notebook id when needed:

```bash
qzcli exec 7b825dbc-6d73-4347-a944-4cfbd2325d7a --timeout 30 'echo ping'
```

5. Sync local files to the dev machine with a remote path relative to the dev machine working directory:

```bash
qzcli sync webagent /Users/masteryth/Documents/webagent/codex_tmp/run_v43_full.sh codex_tmp/run_v43_full.sh
```

### Important Path Rule For `qzcli sync`
- Remote destination must be relative.
- Do not pass an absolute remote path such as:
  - `/inspire/.../codex_tmp/run_v43_full.sh`
- Correct form:
  - `codex_tmp/run_v43_full.sh`

### Current Practical Patterns
- Read a summary file:

```bash
qzcli exec webagent --timeout 60 'cat /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v43_strict/results/dev_summary.json'
```

- Read a partial summary when a run is still active:

```bash
qzcli exec webagent --timeout 60 'cat /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v43_strict/results/dev_summary.partial.json'
```

- Check remote process state:

```bash
qzcli exec webagent --timeout 30 'ps -ef | grep -E "run_workflow_benchmark.py|run_v43_full.sh" | grep -v grep'
```

- Tail nohup logs:

```bash
qzcli exec webagent --timeout 30 'tail -n 80 /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/codex_tmp/v43_full.nohup.log'
```

### Known Operational Notes
- We previously patched the local `qzcli` so that `exec` is usable for this workflow:
  - it can work by dev-machine name or notebook id
  - it no longer depends on a dirty reused Jupyter terminal
- If `exec` starts failing after working before, first check:
  - login freshness
  - `qzcli res -u`
  - whether the dev machine interactive environment was stopped and restarted
- If DNS to `qz.sii.edu.cn` fails, that is a host/network issue, not a benchmark issue.

## Best Known Historical Full Results
- Best completed full strict run so far:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v30_strict/results/dev_summary.json`
  - `130/140 = 92.86%`
- Later full runs showed residual correctness regressions:
  - `v31 = 126/140`
  - `v41 = 129/140`

## Major Correctness / Infra Fixes Already Landed

### 1. Runtime / Harness
- `per_goal` runtime isolation is in place.
- Shared runtime contamination issue was fixed.

### 2. Shared-page task binding
- Pages now use real binding task ids instead of workflow runtime synthetic ids.
- Key files:
  - `/Users/masteryth/Documents/webagent/agent/browser_env.py`
  - `/Users/masteryth/Documents/webagent/llm_runner.py`
  - `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_episode.py`
  - `/Users/masteryth/Documents/webagent/agent/executor.py`
  - `/Users/masteryth/Documents/webagent/sites/static/common.js`

### 3. Planner / module reachability filtering
- Candidate module selection is constrained by oracle-supported modules.
- This prevents semantically similar but blueprint-invalid modules from being selected.
- Key file:
  - `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark.py`

### 4. Workflow task instantiation string pollution
- Naive string replacement used to corrupt instantiated task values such as:
  - `SAVE20 -> SAVE20.0`
  - `20.0 -> 20.0.0`
- Fixed in:
  - `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_episode.py`

### 5. Agent action execution compatibility
- Real fix landed in `browser_env`, not only `executor`.
- `TYPE(...)` on button-like elements can now be coerced to click when appropriate.
- Key file:
  - `/Users/masteryth/Documents/webagent/agent/browser_env.py`

### 6. Shared-page affordance / task-id / handler fixes
- Representative pages already repaired:
  - `/Users/masteryth/Documents/webagent/sites/food.local/subscription.html`
  - `/Users/masteryth/Documents/webagent/sites/school.local/library.html`
  - `/Users/masteryth/Documents/webagent/sites/bank.local/open-account.html`
  - `/Users/masteryth/Documents/webagent/sites/social.local/charity.html`
  - `/Users/masteryth/Documents/webagent/sites/energy.local/smart-meter.html`
  - `/Users/masteryth/Documents/webagent/sites/shop.local/coupons.html`
  - `/Users/masteryth/Documents/webagent/sites/shop.local/appliance-repair.html`
  - `/Users/masteryth/Documents/webagent/sites/trip.local/transport-card.html`
  - `/Users/masteryth/Documents/webagent/sites/gov.local/renew.html`
  - `/Users/masteryth/Documents/webagent/sites/work.local/calendar.html`
  - `/Users/masteryth/Documents/webagent/sites/work.local/paper-submission.html`
  - `/Users/masteryth/Documents/webagent/sites/work.local/email-tracking.html`
  - `/Users/masteryth/Documents/webagent/sites/social.local/split.html`

### 7. Task asset consistency fixes
- Representative task assets corrected:
  - `/Users/masteryth/Documents/webagent/tasks/B10-coupon-management/task_spec.json`
  - `/Users/masteryth/Documents/webagent/tasks/I2-appliance-repair/task_spec.json`
  - multiple task `oracle_trace.json` files

## Residuals From `v31` That Were Later Targeted
- `v31` exposed correctness/infra residuals in:
  - `daily`
  - `support`
  - `newcomer`
  - `home`

These were then targeted and individually validated:
- `support` targeted residuals fixed
- `newcomer` targeted residuals mostly fixed
- `daily` targeted residuals fixed
- `home` targeted `MODULE_FIRMWARE_UPDATE` fixed

Representative targeted repair runs:
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v42a_strict`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v42b_strict`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v42f_home_strict`

## `v42` Full Run
- Path:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v42_strict`
- Result:
  - did not complete
  - failed due to remote disk quota exhaustion
- Observed error:
  - `OSError: [Errno 122] Disk quota exceeded`

Old run directories were then cleaned to free space before restarting a fresh full run.

## `v43` Final Result
- Run root:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v43_strict`
- Nohup log:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/codex_tmp/v43_full.nohup.log`
- Launch script:
  - `/Users/masteryth/Documents/webagent/codex_tmp/run_v43_full.sh`
- Remote script copy:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/codex_tmp/run_v43_full.sh`

### Final summary
- File:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v43_strict/results/dev_summary.json`
- Final result:
  - `131/140 = 93.57%`
  - `average_composite_score = 0.9784`
- This is the best completed full strict run so far, better than `v30` (`130/140`).

### Per-theme result
- `10/10`:
  - `career`
  - `crisis`
  - `education`
  - `daily`
  - `travel`
  - `composite`
  - `security`
  - `home`
  - `finance`
  - `health`
  - `social`
  - `government`
- not yet clean:
  - `support = 5/10`
  - `newcomer = 6/10`

### Remaining 9 failures
- `support`
  - `WFG-SUPPORT-0001`
  - `WFG-SUPPORT-0002`
  - `WFG-SUPPORT-0008`
  - `WFG-SUPPORT-0009`
  - `WFG-SUPPORT-0010`
- `newcomer`
  - `WFG-NEWCOMER-0003`
  - `WFG-NEWCOMER-0005`
  - `WFG-NEWCOMER-0007`
  - `WFG-NEWCOMER-0009`

### Residual failure patterns

#### Support residual
Representative failing module pattern:
- `MODULE_CONTACT_SUPPORT`:
  - `repeat_action_loop`
- `MODULE_LOGISTICS_FIX`:
  - `premature_done`
- `MODULE_WARRANTY_CLAIM`:
  - success
- `MODULE_RETURN`:
  - `element_not_found_or_timeout`

Interpretation:
- This still looks like benchmark/page interaction residual on the logistics/return branch.
- It is not simply random planner collapse:
  - `invalid_transition_count = 0`
  - failure shape is highly uniform across all 5 failed support goals

#### Newcomer residual
Representative failing module pattern:
- `MODULE_FIND_HOME`:
  - `premature_done` or `repeat_action_loop`
- `MODULE_BANK_OPENING`:
  - success
- `MODULE_ADDRESS_PROOF`:
  - success
- theme-level failure metadata:
  - `target_state_coverage = 0.5`
  - `invalid_transition_count = 2`

Interpretation:
- This still looks like workflow/planner residual, not purely agent weakness.
- Successful newcomer samples already show a correct path like:
  - `FIND_HOME -> BANK_OPENING -> VEHICLE_ADDRESS_UPDATE`
- Failed samples drift into:
  - `FIND_HOME -> BANK_OPENING -> ADDRESS_PROOF`
  while leaving the workflow only half complete.

## Immediate Next Step
- `v43` shows the benchmark is much cleaner than before, but it is still not fully ready for difficulty audit.
- Next work should stay in correctness/infra mode:
  1. inspect `support` residuals on the logistics/return branch
  2. inspect `newcomer` residuals on the invalid-transition fallback path
  3. rerun a narrow probe for those 9 failures before starting any difficulty audit

## Difficulty Audit Status
- Not started yet.
- `v43` is not sufficient to start it yet.
- Reason:
  - the remaining failures still look like correctness/infra/planner residuals, not clearly agent-only failures.

## Debug Log Noise Control
- Assertion/evaluator debug spam such as:
  - `DEBUG: Eval Atom: ...`
  - `DEBUG: DSL mem check: ...`
  - `DEBUG: AssertionDSL json check: ...`
  is not required for normal benchmark runs.
- These logs were changed to be opt-in instead of default-on.
- Updated files:
  - `/Users/masteryth/Documents/webagent/agent/assertions_dsl.py`
  - `/Users/masteryth/Documents/webagent/agent/executor.py`
  - `/Users/masteryth/Documents/webagent/agent/state_propagation.py`
  - `/Users/masteryth/Documents/webagent/task_handlers/m_crisis.py`
  - `/Users/masteryth/Documents/webagent/task_handlers/d_finance.py`
- Default behavior now:
  - quiet
- To re-enable debug logging explicitly:

```bash
export WEBAGENT_DEBUG_LOGS=1
export WEBAGENT_DEBUG_ASSERTIONS=1
```

## Top-level Cleanup Status
- Confirmed stale / deletable:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/sites`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/tasks`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/__MACOSX`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/v1`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent.zip`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/llm_runner.py`
- Keep:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/codex_tmp`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/envs`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/models`

## 2026-04-14 Late Update

### Incorrect Remote Sync Incident
- There was one confirmed sync mistake:
  - debug/quiet-log related files were initially synced only to the wrong top-level remote paths:
    - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/agent/...`
    - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/task_handlers/...`
- The benchmark does **not** import from those top-level directories.
- The authoritative remote runtime paths are:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/agent/...`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/task_handlers/...`
- This was corrected and verified by matching remote hashes at the `/webagent/...` paths.
- The top-level duplicate directories are now just dirty leftovers and can be removed later:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/agent`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/task_handlers`

### Support Residual Resolution
- Narrow repair run:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v44_support_newcomer_strict/results/dev_summary.json`
- Final narrow result:
  - `support = 5/5`
  - `newcomer = 0/4`
- This confirmed that the earlier `support` residuals were benchmark/page interaction issues, not agent-only failures.

### Newcomer Root Cause
- The remaining `newcomer` failures were traced to a concrete benchmark asset mismatch:
  - workflow-instantiated `MODULE_FIND_HOME` tasks in `workflow_split_batch_v20` used `propertyId = PROP-101`
  - but the actual housing inventory in `/Users/masteryth/Documents/webagent/env/state.json` only exposes `PROP-EXT-10` as the valid target listing for the current A1 home-finding flow
- Effect on execution:
  - the housing page stayed on the listing page
  - the agent kept repeating `SELECT(#sort-order, ...)`
  - no property page transition happened
  - `MODULE_FIND_HOME` looped and the workflow only reached `0.5` coverage

### Files Patched For The Newcomer Asset Bug
- `/Users/masteryth/Documents/webagent/tasks/workflow_module_bindings.json`
  - `BIND_A1_FIND_HOME.default_parameter_values.propertyId`
  - changed from `PROP-101` to `PROP-EXT-10`
- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/dev/workflow_oracles/*.json`
  - all `MODULE_FIND_HOME` reference invocations bound to `A1-2025-HOME`
  - changed `propertyId` from `PROP-101` to `PROP-EXT-10`
- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/test/workflow_oracles/*.json`
  - same fix
- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/train/workflow_oracles/*.json`
  - same fix
- `/Users/masteryth/Documents/webagent/tasks/workflow_generation_blueprints.json`
  - removed stale `PROP-101` from `shared_variable_pools.property_id`
  - this is a generation-source hygiene fix to avoid regenerating invalid housing targets later

### Newcomer Verification Run
- Narrow rerun:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v45_newcomer_strict/results/dev_summary.json`
- Result:
  - `4/4`
  - all previously failing `newcomer` residuals turned into `novel_success`
- Verified goals:
  - `WFG-NEWCOMER-0003`
  - `WFG-NEWCOMER-0005`
  - `WFG-NEWCOMER-0007`
  - `WFG-NEWCOMER-0009`

### Current Mainline Run
- A new full strict regression run has been started on the corrected benchmark assets:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v46_strict`
- Remote launcher/log paths:
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/codex_tmp/run_v46_full.sh`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/codex_tmp/v46_full.launch.log`
- Early partial status at the time of this update:
  - `completed_goals = 4`
  - `final_success_count = 4`
  - `career = 4/4`

### Current Decision Rule
- Do **not** start difficulty audit yet.
- Wait for `v46` full strict to finish.
- If `support` and `newcomer` stay green in `v46`, then benchmark correctness/infra is close enough to begin difficulty review.
