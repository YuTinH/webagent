# RL Memory Workspace

This directory is reserved for RL and memory-based baselines on the webagent benchmark.

## Layout
- `docs/`: framework selection notes, memory-method notes, split design.
- `configs/`: training and evaluation configs.
- `scripts/`: data generation, split, training, and evaluation scripts.
- `splits/`: generated train/val/test flow lists and metadata.
- `runs/`: logs, summaries, and checkpoints metadata.

## Scope
This folder is intentionally separated from the main benchmark pipeline so that:
- benchmark generation/oracle remains stable;
- RL training artifacts do not pollute the core dataset directory;
- train/test split logic can evolve independently.
