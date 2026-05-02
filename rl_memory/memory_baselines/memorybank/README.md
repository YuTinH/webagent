# MemoryBank Baseline

This baseline is a fuller structured-memory variant intended to sit between `memorybank_lite` and a more faithful MemoryBank reproduction.

## Design

- keep distinct memory types:
  - `fact`: persistent state facts extracted from `expected_memory.json`
  - `strategy`: task-specific guidance distilled from successful runs
  - `episode`: compact successful task summaries
  - `pitfall`: reusable failure warnings grouped by task family and failure type
  - `family_summary`: consolidated high-level summary per task family
  - `family_pitfall_summary`: consolidated failure summary per task family
  - `global_summary`: rolling summary across family summaries
- track:
  - `importance`
  - `strength`
  - `reinforcement_count`
  - `access_count`
  - `last_accessed_at`
- apply:
  - time decay
  - rehearsal / access bonuses
  - pruning with type-aware floors
- retrieve with:
  - lexical similarity
  - optional dense embedding similarity
  - tag overlap
  - task / family bonuses
  - type priors
 - consolidate with:
   - heuristic summarization by default
   - optional LLM summarization via OpenAI-compatible API

## Why this is closer to full MemoryBank

- separate semantic memory types rather than one flat store
- maintain memory strength dynamically based on rehearsal and retrieval
- distinguish stable facts from episodic summaries and pitfalls
- prefer concise structured prompt injection instead of a single mixed list
- support dense retrieval when `AGENT_MEMORYBANK_EMBED_MODEL` is configured
- support memory consolidation / summarization when `AGENT_MEMORYBANK_SUMMARIZER` is enabled

## Still intentionally omitted

- learned importance model
- user-personality portrait modules from the original companion setting
- hierarchical controller / planner

## Optional environment variables

- `AGENT_MEMORYBANK_EMBED_MODEL`:
  local path or HF id for the embedding encoder used in dense retrieval
- `AGENT_MEMORYBANK_EMBED_DEVICE`:
  defaults to `cpu`
- `AGENT_MEMORYBANK_SUMMARIZER`:
  `heuristic`, `llm`, or `off`
- `AGENT_MEMORYBANK_SUMMARIZER_MODEL`:
  summarizer model name when `AGENT_MEMORYBANK_SUMMARIZER=llm`
