# MemoryBank-lite Baseline

This baseline is a lightweight structured-memory approximation of MemoryBank.

## Goal

Provide a no-training memory baseline that is more state-oriented than Reflexion.

## Design

- store structured memory entries after each task
- prefer successful task-state deltas using `expected_memory.json` as a whitelist
- also store one compact task summary entry per run
- merge repeated entries by memory identity
- decay memory strength over time
- prune low-value entries when the store grows
- retrieve top-k relevant entries lexically, with importance and recency boosts
- prepend retrieved memory to the next instruction

## Why "lite"

This is not a full MemoryBank reproduction. It intentionally omits:

- embedding retrieval
- richer semantic importance modeling
- complex long-horizon memory scheduling

## Current approximation of MemoryBank behavior

- `importance`: higher for identifiers, addresses, dates, statuses, and scalar state
- `reinforcement_count`: repeated writes to the same memory key boost retained importance
- `forgetting`: exponential time decay via `AGENT_MEMORYBANK_DECAY_DAYS`
- `pruning`: drop low-value entries and cap total size via `AGENT_MEMORYBANK_MAX_ITEMS`

## Expected comparison

- stronger state recall than Reflexion
- lower engineering cost than a full MemoryBank or hierarchical-memory system
