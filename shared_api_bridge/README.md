# Shared Disk API Bridge

This directory contains a minimal CPU/GPU bridge for the case where:

- the GPU partition cannot access the internet,
- the CPU partition can access the internet,
- both partitions can read and write the same shared path.

The flow is:

1. A GPU-side script writes a request JSON file into the shared directory.
2. A CPU-side relay polls that directory and forwards the request to the real API.
3. The CPU relay writes the response back into the shared directory.
4. The GPU-side script waits for the response file and prints the result.

## Files

- `cpu_disk_relay.py`: runs on the CPU partition and forwards queued HTTP requests.
- `gpu_submit_task.py`: runs on the GPU partition and submits one Anthropic-compatible task.
- `gpu_http_proxy.py`: runs on the GPU partition and exposes a local HTTP endpoint for Claude Code.

## Shared directory layout

The bridge expects a shared base directory like:

```text
/gpfs/your_shared_path/claude_proxy/
  requests/
  responses/
  logs/
```

The scripts create these directories automatically if they do not exist.

## CPU side

Run this on the CPU partition:

```bash
python3 shared_api_bridge/cpu_disk_relay.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --base-url https://open.bigmodel.cn/api/anthropic
```

If you do not want the API key to appear in request JSON files, inject it only on the CPU side:

```bash
python3 shared_api_bridge/cpu_disk_relay.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --base-url https://open.bigmodel.cn/api/anthropic \
  --default-api-key "$API_KEY" \
  --api-key-header x-api-key
```

If your upstream expects bearer auth instead:

```bash
python3 shared_api_bridge/cpu_disk_relay.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --base-url https://open.bigmodel.cn/api/anthropic \
  --default-api-key "$API_KEY" \
  --api-key-header Authorization \
  --auth-scheme bearer
```

## GPU side

Submit one task from the GPU partition:

```bash
python3 shared_api_bridge/gpu_submit_task.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --model claude-sonnet-4-5 \
  --api-key "$API_KEY" \
  --auth-mode x-api-key \
  --task "Summarize the following training log and list the top 3 issues."
```

If the CPU relay already injects the key, omit `--api-key` on the GPU side:

```bash
python3 shared_api_bridge/gpu_submit_task.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --model claude-sonnet-4-5 \
  --task-file /path/to/task.txt
```

You can also read the task from stdin:

```bash
cat /path/to/task.txt | python3 shared_api_bridge/gpu_submit_task.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --model claude-sonnet-4-5
```

## Notes

- The default API path is `/v1/messages`.
- The default Anthropic version header is `2023-06-01`.
- `gpu_submit_task.py` extracts text from common Anthropic-style and OpenAI-style response bodies.
- `cpu_disk_relay.py` is generic enough to forward other HTTP requests if you later want to build a local proxy on top of it.

## Claude Code on GPU

If you want normal interactive Claude Code instead of one-shot task submission, run a local proxy on the GPU partition:

```bash
python3 /Users/masteryth/Documents/webagent/shared_api_bridge/gpu_http_proxy.py \
  --shared-base /gpfs/your_shared_path/claude_proxy \
  --host 127.0.0.1 \
  --port 8317
```

Then point Claude Code at the local proxy:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8317
export ANTHROPIC_AUTH_TOKEN=dummy
export ANTHROPIC_MODEL=claude-sonnet-4-5
```

After that, Claude Code talks to the GPU local proxy, and the proxy uses the shared directory plus `cpu_disk_relay.py` to reach the real online API.
