# RL Framework And Memory Method Recommendation

## Objective
This document scopes the first RL training stack for the webagent benchmark.

The target is not generic preference alignment. The target is multi-step agent training with:
- browser-like trajectories
- external environment interaction
- custom reward from checkpoints/task success/flow success
- explicit state carry-over across steps and tasks

## Recommended RL Framework

### Primary choice: OpenRLHF

OpenRLHF is the best first framework for this benchmark because it is already designed around agent execution instead of only single-turn prompt/completion optimization.

Why it fits this benchmark:
- supports agent-based training rather than only static text data
- supports multi-turn execution with external environments
- supports custom rewards, which matches our checkpoint/task/flow scoring
- supports scalable distributed training with Ray + vLLM
- already exposes recipes for REINFORCE-style agent RL

Practical recommendation:
- start with LoRA
- start with REINFORCE++ or RLOO-style setup before PPO
- train on clean flows first
- add perturbation robustness only after a clean baseline converges

Why not use TRL as the primary framework:
- TRL is strong for standard RLHF and post-training
- but for this benchmark, the environment interaction layer matters more than generic trainer availability
- TRL is better treated as a fallback or ablation stack, not the first implementation target

### Secondary choice: TRL

TRL remains useful for:
- small-scale ablations
- quick reward-model or online-RL experiments
- reproducing simpler GRPO/RLOO baselines

It is not the best first choice for our benchmark because the main engineering bottleneck is agent-environment integration rather than the optimizer itself.

### Not first-wave, but worth tracking: Agent Lightning

Agent Lightning is directly relevant because it targets RL training for arbitrary agents and emphasizes decoupling execution from training.

However:
- it is newer
- ecosystem maturity is lower than OpenRLHF
- it is better treated as a follow-up comparison or future extension

## Recommended Memory Baselines

We should evaluate memory methods at three levels of complexity.

### Baseline 1: Reflexion

Role:
- low-cost episodic memory baseline
- stores short textual reflections after success/failure
- injects them into future decisions

Why it fits:
- simple to bolt onto the current agent stack
- directly targets recurring mistakes and recovery
- good first control baseline before heavier memory systems

Expected use in this benchmark:
- write short reflections after failed tasks or chains
- optionally summarize repeated failure modes by task family
- retrieve the most relevant reflections for the next decision

Engineering cost:
- low

### Baseline 2: MemoryBank

Role:
- explicit long-term memory store
- memory entries have importance and time-aware retention

Why it fits:
- benchmark success depends on recalling earlier state changes
- MemoryBank is closer to persistent task-state memory than plain prompt replay
- useful for testing whether explicit retrieval improves long-range dependency handling

Expected use in this benchmark:
- store structured summaries of completed subtasks
- tag memory with task family, affected entities, and state changes
- retrieve top-k relevant memory for each new step

Engineering cost:
- medium

### Baseline 3: MemGPT / Letta-style hierarchical memory

Role:
- working memory plus archival memory
- agent can explicitly manage what stays in context and what moves to long-term storage

Why it fits:
- benchmark is designed around long trajectories and butterfly effects
- hierarchical memory is a better match than a flat retrieval buffer when history grows
- gives a stronger "stateful agent" baseline than simple episodic reflection

Expected use in this benchmark:
- keep only local task context in working memory
- persist prior task outcomes and environment deltas in archival memory
- retrieve and summarize archival memory when new tasks appear to depend on older states

Engineering cost:
- medium to high

## Recommended Training Order

### Phase 1
- OpenRLHF
- LoRA
- clean environment only
- reward = step checkpoints + task success + flow success - invalid/repeat penalties
- no explicit memory module

Goal:
- verify that the benchmark can support online RL training end-to-end

### Phase 2
- add Reflexion
- compare against no-memory baseline

Goal:
- measure whether episodic self-reflection helps with repeated failure modes

### Phase 3
- add MemoryBank
- compare retrieval memory against Reflexion

Goal:
- measure whether persistent explicit memory helps long-range dependency tasks

### Phase 4
- add MemGPT/Letta-style hierarchical memory

Goal:
- test whether memory management, not just retrieval, improves task-flow performance

## Recommended Metrics

Use the benchmark's native scoring for all RL experiments:
- step score
- task score
- flow score

Also log:
- repeat-action failure rate
- selector/option execution failure rate
- counterfactual performance delta
- clean vs perturbed performance delta

## Concrete Recommendation

For the first real implementation:
- RL framework: OpenRLHF
- first training algorithm: REINFORCE++ or RLOO-style setup
- first memory method: Reflexion
- second memory method: MemoryBank
- third memory method: MemGPT/Letta-style hierarchical memory

This order minimizes engineering risk while preserving a meaningful memory-method progression.
