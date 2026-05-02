# SkillBank V1

This is a lightweight first-pass SkillBank baseline for the benchmark.

## Scope

- bootstrap a reusable external skill bank from `tasks/*/oracle_trace.json`
- retrieve relevant skills for each task using lexical matching plus task-family bias
- prepend retrieved skills to the task instruction
- convert retrieved skills into lightweight action-scoring bias at inference time
- update skill usage/success/failure statistics online after each task

## What it is not

- not latent skill learning
- not macro-action execution
- not end-to-end online structure editing with merge/split/prune

## Current design

- skill units are behavior templates derived from oracle traces
- retrieval returns a few candidate reusable skills
- the active skill is a prompt-side control signal plus a lightweight action reranker
- retrieved skill signatures bias the expected next primitive action
- successful online trajectories can be merged back into the bank as runtime skills
- the executor still receives exactly one primitive action per step

## Intended role

This is the V1 baseline that corresponds to the project note:

- external skill bank
- bootstrap from oracle traces
- inference-time skill conditioning
- online updates only for statistics, not structural editing
