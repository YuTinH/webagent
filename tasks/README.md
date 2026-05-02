# Tasks Guide

本目录存放任务定义。当前仓库已从早期 MVP 扩展为多主题动态任务流，不再是“仅 10 个固定任务”。

---

## 1. 目录结构

每个任务目录通常包含：

- `task_spec.json`
- `oracle_trace.json`
- `expected_memory.json`（部分任务）

示例：

```text
tasks/
├── A1-find-home/
│   ├── task_spec.json
│   ├── oracle_trace.json
│   └── expected_memory.json
├── D3-autopay/
│   ├── task_spec.json
│   ├── oracle_trace.json
│   └── expected_memory.json
└── ...
```

---

## 2. task_spec.json 关键字段

最常用字段：

- `task_id`
- `family`
- `goal`
- `inputs`
- `preconditions`
- `success_criteria`

评分相关（当前版本新增）：

- `scoring_checkpoints`（可选）

当 `scoring_checkpoints` 缺失时，runner 会自动由 `success_criteria` 生成等权检查点。

---

## 3. scoring_checkpoints 示例

```json
{
  "scoring_checkpoints": [
    {
      "id": "cp_1",
      "name": "关键状态达成",
      "assertion": "mem('autopay.utility.status') == 'active'",
      "weight": 0.7,
      "required": true,
      "depends_on": []
    },
    {
      "id": "cp_2",
      "name": "结果可见",
      "assertion": "json('env','autopay.utility.status') == 'active'",
      "weight": 0.3,
      "required": true,
      "depends_on": ["cp_1"],
      "when": "NOT[mem('world_state.financial_context.liquidity') == 'frozen']"
    }
  ]
}
```

说明：
- `weight` 运行时会归一化。
- `required=true` 的检查点必须通过，否则任务失败。
- `depends_on` 可限制跳步得分。
- `when`（可选）用于分支化判定：仅当条件为真时该 checkpoint 才激活并参与计分/必过校验。

---

## 4. 任务执行方式

### A. Oracle 单任务

```bash
python3 run_task.py A1-find-home --headless
```

### B. 批量按大类验证

```bash
python3 verify_batch.py A
python3 verify_batch.py B
```

### C. 任务流 Oracle

```bash
python3 -u chain_runner_oracle.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --summary-json audit_chain_oracle_100.json
```

### D. 任务流 Agent

```bash
python3 -u chain_runner_dynamic.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --distractor-level medium \
  --distractor-seed 20260220 \
  --obfuscation-seed 20260220 \
  --summary-json audit_agent_100.json
```

---

## 5. 输出文件

- Oracle 单任务：`output/<task_id>/result.json`
- Agent 单任务：`output/<task_id>/agent_result.json`
- 任务流汇总：`--summary-json` 指定文件

summary 的评分字段：
- `metrics.step_score`
- `metrics.task_score`
- `metrics.flow_score`

---

## 6. 注意事项

- `chain_runner_dynamic.py` 会按 scenario 临时 patch 任务 spec/trace（用于指令与断言对齐），建议在干净副本运行。
- `chain_runner_oracle.py` 内置快照恢复，结束时会还原被 patch 文件。
- 如果任务无 `success_criteria`，该任务可能被视为“无断言任务”，建议逐步补充检查点以增强可评测性。
