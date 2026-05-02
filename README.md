# Web Agent Dynamic Suite V2

Web Agent Dynamic Suite V2 是一个用于评估 Web Agent/LLM 的本地动态仿真环境，包含多站点 UI、后端状态变更、任务定义、oracle 回放和 agent 评测流水线。

快速入口：
- 论文亮点与证据摘要：`BENCHMARK_HIGHLIGHTS_FOR_PAPER.md`

当前版本已支持三维评分：
- `step_score`（基于检查点进度）
- `task_score`（任务完成率）
- `flow_score`（任务流完成率）

## 1. 项目能力概览

- 多站点仿真：`shop.local`、`bank.local`、`gov.local`、`health.local`、`work.local` 等。
- 持久化状态：`data.db` + `env/state.json`，任务行为会真实改写状态。
- 任务体系：`tasks/*/task_spec.json` + `oracle_trace.json`。
- 两套评测：
  - `oracle`（回放 oracle trace）
  - `agent`（LLM 决策执行）
- 动态任务流：`sampled_{theme}.json`（`newcomer/daily/career/leisure/crisis`）。

## 2. 环境准备

要求：
- Python 3.8+
- Playwright Chromium

安装：

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

初始化数据库：

```bash
python3 init_db.py
```

启动服务（默认 8014）：

```bash
python3 server.py
# 或指定端口
python3 server.py 8014
```

## 3. 快速自测

单任务 oracle 回放：

```bash
python3 run_task.py A1-find-home --headless
```

按大类批量核验（你当前常用）：

```bash
python3 verify_batch.py A
python3 verify_batch.py B
```

## 4. 任务流评测（Oracle）

用途：检查任务流定义和站点逻辑是否稳定，不依赖外部模型。

```bash
python3 -u chain_runner_oracle.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --summary-json audit_chain_oracle_100.json
```

可选参数：
- `--stop-on-first-fail-task`：链内遇到首个失败任务就停止后续任务。
- `--task-timeout-sec 180`：单任务超时保护。

## 5. 任务流评测（Agent）

用途：真实评测模型在任务流中的表现。

先配置模型环境变量（示例 1：OpenRouter）：

```bash
export AGENT_BASE_URL='https://openrouter.ai/api/v1'
export AGENT_MODEL='z-ai/glm-4.5-air:free'
export AGENT_API_KEY='<your_key>'
```

示例 2：GLM 原生 API：

```bash
export AGENT_BASE_URL='https://open.bigmodel.cn/api/paas/v4'
export AGENT_MODEL='glm-4-flash'
export AGENT_API_KEY='<your_glm_key>'
```

示例 3：本地 HF / RL checkpoint：

```bash
export AGENT_BACKEND='hf_local'
export AGENT_MODEL='zai-org/webrl-llama-3.1-8b'
export AGENT_PROMPT_PROFILE='webrl'
export AGENT_MAX_TOKENS='128'
```

说明：
- `AGENT_BACKEND=openai_compatible`：默认，适用于 OpenRouter、GLM 原生 API、vLLM/TGI/OpenAI-compatible 网关。
- `AGENT_BACKEND=hf_local`：直接从 HuggingFace / 本地目录加载模型，适合 WebRL 这类 RL checkpoint。
- `AGENT_PROMPT_PROFILE=webrl`：给 RL web-agent checkpoint 一个更贴近 policy 风格的单步动作提示。

运行（推荐默认策略）：

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

### 停止策略（重要）

`chain_runner_dynamic.py` 现在区分两层停止策略：

- 任务流级：
  - 默认继续跑后续任务（即便中间某个任务失败）。
  - 显式开启 `--stop-on-first-fail-task` 才会链内早停。

- 任务内 step 级：
  - 默认开启 `--stop-on-first-fail-step`。
  - 当某一步执行报错（例如 `SELECT` 打到非 `<select>`）会立刻终止该任务。
  - 可用 `--no-stop-on-first-fail-step` 关闭。

- 重复动作防卡死：
  - `--repeat-fail-threshold` 默认 `3`。
  - 同一动作连续重复达到阈值，任务直接失败（`repeat_action_threshold(n)`）。

- 干扰可复现控制（新增）：
  - `--distractor-level`：`off/low/medium/high`
  - `--distractor-seed`：固定干扰采样
  - `--obfuscation-seed`：固定混淆后缀生成
  - 同一参数组合可复现实验难度。

## 6. 三维评分定义

### 6.1 Step Score

基于检查点得分，统一归一化到 `%`：

- 单任务：`step_task = sum(w_i * p_i)`
- 其中：
  - `w_i`：第 i 个检查点归一化权重
  - `p_i`：通过度（当前实现默认 0/1）
- 总体：`step_score = total_step_earned / total_step_max * 100`

如果任务未配置显式检查点，会自动从 `success_criteria` 生成“中间态+终态”双检查点（required）。

### 6.2 Task Score

- `task_score = passed_tasks / total_planned_tasks * 100`

### 6.3 Flow Score

- `flow_score = passed_chains / total_chains * 100`

## 7. 检查点配置（task_spec.json）

可在任务中显式配置 `scoring_checkpoints`：

```json
{
  "scoring_checkpoints": [
    {
      "id": "cp_submit",
      "name": "提交关键动作",
      "assertion": "mem('autopay.utility.status') == 'active'",
      "weight": 0.7,
      "required": true,
      "depends_on": []
    },
    {
      "id": "cp_visible",
      "name": "结果可见",
      "assertion": "json('env','autopay.utility.status') == 'active'",
      "weight": 0.3,
      "required": true,
      "depends_on": ["cp_submit"]
    }
  ]
}
```

规则：
- `required=true` 的检查点必须通过，否则任务失败。
- `depends_on` 未满足时，该检查点记为失败（防止跳步刷分）。
- 未配置时会自动从 `success_criteria` 生成检查点。

## 8. 输出文件说明

### 8.1 任务级输出

Agent 执行后写入：
- `output/<task_id>/agent_result.json`

关键字段：
- `success`
- `end_reason`
- `repeat_fail` / `repeat_action` / `repeat_count`
- `step_error_abort`
- `checkpoint_score_percent`
- `checkpoint_results`

### 8.2 任务流级输出

`--summary-json` 文件包含：
- `run_config`（clean/obfuscate/seed/干扰强度）
- `chains`（每条链和每个任务细节）
- `metrics.step_score`
- `metrics.task_score`
- `metrics.flow_score`
- `metrics.weighted_score`
- `failure_analysis.bucket_counts`（`ability_failure` vs `executor_failure`）
- `failure_analysis.category_counts`（例如 `action_type_error`、`selector_parse_error`、`overlay_block`）

## 8.3 RL Baseline 接入

当前仓库已经支持把 RL 风格的 web-agent checkpoint 直接接入现有评分流水线，前提是它最终能输出单步动作。

建议优先测试：
- `zai-org/webrl-llama-3.1-8b`
- `zai-org/webrl-glm-4-9b`

两种接法：

1. 本地直接加载 HF checkpoint

```bash
pip install torch transformers accelerate
export AGENT_BACKEND='hf_local'
export AGENT_MODEL='zai-org/webrl-llama-3.1-8b'
export AGENT_PROMPT_PROFILE='webrl'
./run_rl_baseline.sh zai-org/webrl-llama-3.1-8b audit_rl_webrl_llama.json
```

2. 用 vLLM / TGI 起 OpenAI-compatible 服务

```bash
export AGENT_BACKEND='openai_compatible'
export AGENT_BASE_URL='http://localhost:8000/v1'
export AGENT_MODEL='zai-org/webrl-llama-3.1-8b'
export AGENT_PROMPT_PROFILE='webrl'
./run_rl_baseline.sh zai-org/webrl-llama-3.1-8b audit_rl_webrl_llama.json
```

兼容性说明：
- 你当前执行器使用 `CLICK/TYPE/SELECT/GOTO/WAIT/DONE` 协议。
- `llm_runner.py` 已补充对常见 RL / WebArena 风格输出的归一化解析，例如 `click [selector]`、`type [selector] [text]`、JSON action。
- 这不会放宽成功判定；只是在动作文本协议上做兼容层。

## 9. 常见问题

### Q1: 为什么会看到 `repeat_action_threshold(3)`？

表示 agent 在同一动作上循环（连续 3 次），被防卡死策略判为失败。这是预期行为。

### Q2: 为什么会出现 `step_error_abort`？

表示某一步执行指令发生硬错误（例如元素类型不匹配），在 `--stop-on-first-fail-step` 策略下该任务立即终止。

### Q3: 任务流评测时，失败任务后为什么还继续执行？

默认就是继续执行后续任务，以适配“并非所有任务存在强蝴蝶效应”的场景。若要链内首败即停，显式加 `--stop-on-first-fail-task`。

## 10. 建议评测流程

- 先用 `oracle` 跑小样本，确认站点和任务逻辑稳定。
- 再用 `agent` 跑小样本 smoke（每主题 1~5 条）。
- 最后跑正式规模（例如每主题 20 条，共 100 条）。

示例 smoke：

```bash
python3 -u chain_runner_dynamic.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 1 \
  --headless \
  --max-steps 8 \
  --repeat-fail-threshold 3 \
  --summary-json audit_agent_smoke.json
```

## 11. 任务流生成

使用生成器重建任务流样本：

```bash
python3 scenario_generator_v3.py \
  --chains-per-theme 100 \
  --max-repeat-per-task 1 \
  --theme-task-cap 30 \
  --min-steps 6 \
  --max-steps 8 \
  --min-dependent-steps 2 \
  --min-long-dependency-steps 1 \
  --long-dependency-gap 3 \
  --min-conflict-steps 1 \
  --seed 42
```

新参数（用于增强持续学习/记忆评测）：
- `--min-dependent-steps`：每条链中最少“显式依赖前序任务状态”的步数
- `--min-long-dependency-steps`：每条链中最少“长程依赖”步数
- `--long-dependency-gap`：定义长程依赖的最小步距（source->target）
- `--min-conflict-steps`：每条链中最少“旧值/新值覆盖冲突”步数
- `--dependency-boost` / `--long-dependency-boost` / `--conflict-boost`：采样时对对应样本类型的权重提升
- `--constraint-retries`：每条链的约束重试次数（默认 6，优先满足上述下限）

## 12. 反事实评测（新增）

用途：同一任务流只改初始状态的一个关键变量，比较后续完成度变化，量化前置影响敏感度。

```bash
python3 -u chain_runner_counterfactual.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --clean-mode \
  --no-obfuscate-mode \
  --summary-json audit_chain_counterfactual_100.json
```

### 12.1 推荐：始终保存完整 runtime log（逐行 ✅/❌）

为避免只留下结果 JSON、丢失逐行执行日志，推荐统一使用：

```bash
export AGENT_BASE_URL='https://open.bigmodel.cn/api/paas/v4'
export AGENT_MODEL='glm-4.6'
export AGENT_API_KEY='<your_key>'

./run_counterfactual_agent_logged.sh \
  --limit-per-theme 5 \
  --impact-profile strong \
  --headless true \
  --tag glm46_5x5
```

该脚本会同时产出：
- 结果文件：`audit_chain_counterfactual_agent_logged_<model>_<timestamp>_<tag>.json`
- 逐行日志：`logs/runtime_counterfactual_agent_<model>_<timestamp>_<tag>.log`

并且会在启动前检查 benchmark server 是否可访问（默认 `http://localhost:8014`）。

可选参数：
- `--target-key <key>`：强制只改某个 `initial_state` 字段（例如 `card_frozen`）
- `--seed`：固定 mutation 采样
- `--impact-profile balanced|strong`：反事实扰动强度（`strong` 优先采样高杠杆状态键）

输出指标：
- `impact_rate`：反事实后表现发生变化的链占比
- `baseline_task_score` vs `counterfactual_task_score`
- `avg_task_drop` / `avg_step_drop`

会输出：
- `sampled_newcomer.json`
- `sampled_daily.json`
- `sampled_career.json`
- `sampled_leisure.json`
- `sampled_crisis.json`

## 12. 评测注意事项

- `chain_runner_dynamic.py` 会根据 scenario 就地 patch 任务文件（`tasks/*/task_spec.json` 和部分 `oracle_trace.json`）。建议在干净副本中跑，或先做文件备份。
- Oracle runner（`chain_runner_oracle.py`）内置了快照恢复逻辑，会在结束时还原被 patch 的任务文件。
- 评测过程日志会写入 `evaluation.log`，便于排查失败原因。
