# RL Dataset Split Plan

## Goal
We need a split that is suitable for training memory-aware agents without contaminating the benchmark test set.

The split unit must be the full task flow, not the individual subtask.

## Why Split By Flow

If we split by subtask, the same dependency patterns and requirement sequences can leak from train into test.

That is not acceptable for this benchmark because the main signal is:
- cross-step dependency
- long-range dependency
- conflict recovery
- counterfactual sensitivity

Therefore, the split unit is one full chain.

## Deduplication Key

Before splitting, each chain should be assigned a semantic signature based on:
- theme
- ordered task_id sequence
- ordered requirement_id sequence
- hash of initial_state

This prevents near-duplicate flows from crossing splits.

## Recommended Split Strategy

### Pilot split from the current 500-flow pool

The current sampled pool contains:
- 500 clean flows
- 100 per theme
- 6 to 8 steps per flow

This pool is enough for:
- initial RL pipeline debugging
- reward shaping tests
- first memory ablations

It is not enough for a strong final RL training result.

Recommended pilot split:
- train: 300 flows
- val: 100 flows
- test-clean: 100 flows

Per theme:
- train: 60
- val: 20
- test-clean: 20

This keeps the pilot split balanced and fully reproducible.

### Full training pool after multi-seed expansion

The benchmark cannot produce 600 flows per theme in a single sampling run under the current per-theme task cap.

So the correct approach is:
1. generate multiple clean flow pools with different seeds
2. merge them
3. deduplicate by semantic signature
4. split afterward

Recommended full clean pool target:
- train-clean: 1000 to 1500 flows
- val-clean: 200 to 300 flows
- test-clean: 300 to 500 flows

Conservative target for the first proper RL study:
- train-clean: 1000
- val-clean: 200
- test-clean: 300

This is feasible after multi-seed generation and more realistic than forcing a larger one-shot split.

## Additional Evaluation Sets

The benchmark should expose three evaluation conditions.

### Test-Clean
- clean environment
- no obfuscation
- no distractors

Purpose:
- measure core task-flow competence

### Test-Counterfactual
- same task-flow skeleton as test-clean
- modified initial state or key world-state attributes

Purpose:
- measure whether the agent responds to state changes rather than memorizing a fixed flow

### Test-Perturbed
- clean mode off
- obfuscation on
- distractor level medium

Purpose:
- measure UI robustness separately from task semantics

## Recommended Protocol

### Training
- use only clean flows
- do not train on counterfactual or perturbed evaluation sets in the first wave

### Validation
- use clean validation flows only
- use validation to tune reward weights and memory hyperparameters

### Final evaluation
- report results on:
  - test-clean
  - test-counterfactual
  - test-perturbed

## Planning Numbers

### Immediate pilot
- source pool: 500 clean flows
- split: 300 / 100 / 100

### First expanded RL pool
- target after multi-seed merge: 1500 clean flows
- split: 1000 / 200 / 300

### If the pool grows further
Once the deduplicated clean pool exceeds 2000, move to:
- 1200 to 1500 train
- 300 val
- 500 test-clean

Counterfactual and perturbed test sets should remain fixed and separate.

## Release Principle

Benchmark testing and RL training must be separated.

Recommended rule:
- benchmark public test set remains fixed
- RL training pool is maintained separately under `rl_memory/`
- all experimental runs must record the exact split manifest they used

This keeps the benchmark reproducible and avoids accidental train-test drift.
