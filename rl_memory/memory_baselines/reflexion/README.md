# Reflexion Baseline Scaffold

This directory contains the first memory-baseline scaffold for the benchmark.

## Goal

Implement a low-cost episodic memory baseline before adding heavier long-term memory systems.

## Basic idea

After each task or chain:
- summarize failure or success
- store the reflection in a small persistent memory file
- retrieve the most relevant reflections for future decisions

## Scope of this scaffold

Implemented:
- persistent reflection store
- simple lexical retrieval
- prompt augmentation helper

Not yet implemented:
- automatic reflection generation with a separate judge model
- retrieval re-ranking
- compression/forgetting policy

## Suggested first experiment

1. Run the base agent on the clean train split
2. Store task-level reflections for failed tasks
3. Re-run with top-k retrieved reflections prepended to the prompt
4. Compare:
   - repeat-action loop rate
   - step score
   - task score
   - flow score
