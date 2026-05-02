# OpenRLHF Install And Launch Notes

## Recommended installation path

Use a dedicated environment for OpenRLHF. The official docs recommend installing inside an NVIDIA PyTorch container and then installing `openrlhf` or `openrlhf[vllm]`.

Reference:
- [OpenRLHF Quick Start](https://openrlhf.readthedocs.io/en/latest/quick_start.html)
- [OpenRLHF Agent-based Training Guide](https://openrlhf.readthedocs.io/en/latest/agent_training.html)

## Minimum practical stack

For the first clean-flow RL run, use:
- Python environment with CUDA-enabled PyTorch
- `openrlhf[vllm]`
- `ray[default]`
- `deepspeed`
- benchmark runtime dependencies already needed by webagent

## Recommended install steps

### Option A: inside an existing CUDA Python environment

```bash
pip install -U pip wheel setuptools
pip install \"openrlhf[vllm]\"
pip install \"ray[default]\" deepspeed
```

### Option B: editable install from source

```bash
git clone https://github.com/OpenRLHF/OpenRLHF.git
cd OpenRLHF
pip install -e .
pip install \"ray[default]\" deepspeed
```

## Sanity checks

```bash
python3 - <<'PY'
import torch
print('cuda', torch.cuda.is_available())
try:
    import openrlhf
    print('openrlhf ok')
except Exception as e:
    print('openrlhf import failed:', e)
PY
```

## Ray startup

Single-node first:

```bash
ray stop || true
ray start --head --node-ip-address 0.0.0.0 --num-gpus 1
```

If you later move to multi-GPU or multi-node, keep the same adapter but scale the Ray launch and OpenRLHF GPU allocation flags.

## First local checks before training

1. Start the benchmark server on `8014`
2. Run the local smoke test:

```bash
python3 /Users/masteryth/Documents/webagent/rl_memory/openrlhf/smoke_test_agent_func.py \
  --dataset /Users/masteryth/Documents/webagent/rl_memory/openrlhf/data/clean_pool_v1_1000_200_300/train.jsonl \
  --max-actions 20
```

3. Only after smoke passes, launch the first OpenRLHF training job

## Training launch pattern

OpenRLHF official docs recommend using `--agent_func_path` in multi-turn mode.

Reference behavior from the official docs:
- multi-turn mode uses `--agent_func_path`
- each sample is treated as an episode
- synchronous training is more stable than async for the first run

For this project, the training entry script is:

```bash
bash /Users/masteryth/Documents/webagent/rl_memory/openrlhf/train_reinforce_clean.sh
```

## First-run recommendation

Do not start with:
- async training
- perturbation mode
- heavy memory modules

Start with:
- clean train split
- synchronous multi-turn execution
- small LoRA-compatible base model
- one GPU if you only need to validate the pipeline
