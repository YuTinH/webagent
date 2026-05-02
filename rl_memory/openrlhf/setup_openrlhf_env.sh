#!/usr/bin/env bash
set -euo pipefail

# Minimal setup helper for a CUDA Python environment.

python3 -m pip install -U pip wheel setuptools
python3 -m pip install "openrlhf[vllm]" "ray[default]" deepspeed

python3 - <<'PY'
import torch
print("torch_cuda_available=", torch.cuda.is_available())
try:
    import openrlhf
    print("openrlhf_import=ok")
except Exception as exc:
    print("openrlhf_import=failed", exc)
PY
