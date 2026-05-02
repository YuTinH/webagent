# Workflow Benchmark 实验用法

## 入口
- 批量实验脚本：`/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark.py`
- 通用 2GPU launcher：`/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark_local_2gpu.sh`
- Qwen2.5-7B wrapper：`/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark_qwen25_7b_local_2gpu.sh`
- Qwen2.5-14B wrapper：`/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark_qwen25_14b_local_2gpu.sh`

## 设计
- 高层：模型在 workflow level 选择下一个 `module`
- 低层：系统把 `module` 映射到具体 `binding` 和 atomic task，再交给同一个模型执行网页动作
- 评测：最后用 hidden oracle 做 episode-level evaluation

## 当前正式数据集
- batch: `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20`
- realism gate: 已通过
- goal quality gate: 已通过

## 推荐起跑方式
先跑 `dev`：

```bash
RUN_ROOT=/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev \
WORKFLOW_SPLIT=dev \
SERVER_PORT=8060 \
CUDA_VISIBLE_DEVICES=0,1 \
/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark_qwen25_7b_local_2gpu.sh
```

14B：

```bash
RUN_ROOT=/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_14b_dev \
WORKFLOW_SPLIT=dev \
SERVER_PORT=8062 \
CUDA_VISIBLE_DEVICES=0,1 \
/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark_qwen25_14b_local_2gpu.sh
```

## 常用参数
- `WORKFLOW_SPLIT=train|dev|test`
- `WORKFLOW_LIMIT=20`：先小规模 smoke
- `WORKFLOW_MODULE_POLICY=llm|heuristic|reference`
- `WORKFLOW_ATOMIC_POLICY=agent|dry_run`
- `WORKFLOW_BATCH_ROOT=/.../workflow_split_batch_v20`
- `AGENT_MODEL=/.../Qwen2.5-7B-Instruct` 或 `Qwen2.5-14B-Instruct`

## 输出
- 总结：`$RUN_ROOT/results/<split>_summary.json`
- Markdown 总结：`$RUN_ROOT/results/<split>_summary.md`
- 单题输出：`$RUN_ROOT/results/<split>/<goal_id>/`
  - `workflow_execution_trace.json`
  - `workflow_execution_evaluation.json`
  - `workflow_module_selection_trace.json`
  - `workflow_run_summary.json`

## 已验证的 smoke
本地已跑通：
- `reference + dry_run`
- `heuristic + dry_run`

说明：
- workflow batch runner 本身通了
- goal -> module trace -> evaluation 这条链是通的
- 真正的 `llm + agent` 路径需要在有模型和 server 的机器上跑
