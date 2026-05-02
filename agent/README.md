# Agent Runtime Guide

本目录包含两类执行能力：

- Oracle 执行器：`agent/executor.py`
- LLM Agent 执行器：`llm_runner.py` + `chain_runner_dynamic.py`

为避免误解：当前仓库已经支持自主 agent 流程，不再是“仅 oracle 回放”。

---

## 1. 依赖

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

---

## 2. Oracle 单任务执行

```bash
python3 run_task.py A1-find-home --headless
```

输出：`output/<task_id>/result.json`

用途：验证任务规范与站点逻辑，不依赖外部模型。

---

## 3. LLM 单任务执行

先配置模型：

```bash
export AGENT_BASE_URL='https://open.bigmodel.cn/api/paas/v4'
export AGENT_MODEL='glm-4-flash'
export AGENT_API_KEY='<your_key>'
```

运行：

```bash
python3 llm_runner.py A1-find-home \
  --start_url 'http://localhost:8014/housing.local/index.html' \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --stop-on-first-fail-step \
  --headless
```

输出：`output/A1-find-home/agent_result.json`

关键字段：
- `success`
- `end_reason`
- `repeat_fail` / `repeat_action` / `repeat_count`
- `step_error_abort`
- `checkpoint_score_percent`
- `checkpoint_results`

---

## 4. LLM 任务流执行（推荐）

```bash
python3 -u chain_runner_dynamic.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --summary-json audit_agent_100.json
```

评分输出在 summary 的 `metrics`：
- `step_score`
- `task_score`
- `flow_score`
- `weighted_score`

---

## 5. 停止策略

- 链级：默认不中断后续任务。
- 链级早停：`--stop-on-first-fail-task`。
- 任务内 step 级：默认开启首错即停（`--stop-on-first-fail-step`）。
- 关闭 step 级早停：`--no-stop-on-first-fail-step`。
- 循环动作失败：`--repeat-fail-threshold`（默认 3）。

---

## 6. 主要模块

- `agent/executor.py`：Oracle 执行器（回放 trace + DSL 验证）
- `agent/assertions_dsl.py`：断言 DSL
- `agent/browser_env.py`：LLM agent 浏览器执行环境
- `agent/llm_client.py`：模型调用客户端
- `llm_runner.py`：单任务 LLM agent 驱动
- `chain_runner_dynamic.py`：任务流 LLM 评测
- `chain_runner_oracle.py`：任务流 Oracle 评测

---

## 7. 调试建议

- 优先看 `end_reason`、`repeat_fail`、`step_error_abort`。  
- 查看 `evaluation.log` 和 `output/<task_id>/agent_result.json`。  
- 如果是选择器或控件类型错误，先确认页面元素是否为 `<select>`/`<input>`，再看动作规范。
