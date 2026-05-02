# WebAgent Benchmark 评分系统

**版本**: v2.0  
**日期**: 2026-02-20  
**适用范围**: `chain_runner_dynamic.py` / `chain_runner_oracle.py` 当前实现

---

## 1. 目标

本评分系统用于统一评估 WebAgent 在任务流中的表现，提供三个互补维度：

- `step_score`: 任务步骤层面的完成进度（基于检查点）
- `task_score`: 任务是否完成
- `flow_score`: 任务流（chain）是否完整通过

该体系与当前执行器强绑定，使用动态任务流与检查点评分。

---

## 2. 三维评分定义

## 2.1 Step Score（检查点进度）

单任务步骤得分：

`step_task = Σ(w_i * p_i)`

其中：
- `w_i`: 第 `i` 个检查点归一化权重，`Σ(w_i)=1`
- `p_i`: 通过度，当前实现为二值（通过=1，失败=0）

总 Step Score：

`step_score = total_step_earned / total_step_max * 100`

说明：
- 若任务存在显式 `scoring_checkpoints`，按其权重计算。
- 若未配置 `scoring_checkpoints`，自动由 `success_criteria` 等权生成。
- `depends_on` 未满足时，后续检查点记失败（防止跳步刷分）。
- `when` 条件为假时，该 checkpoint 不激活，不参与 required 判定与分数归一化。

## 2.2 Task Score（任务完成率）

`task_score = passed_tasks / total_planned_tasks * 100`

- `passed_tasks`: 判定成功的任务数
- `total_planned_tasks`: 任务流中计划任务总数（不是已执行数）

## 2.3 Flow Score（任务流完成率）

`flow_score = passed_chains / total_chains * 100`

- `passed_chains`: 全任务成功的 chain 数
- `total_chains`: 评测链总数

## 2.4 Weighted Score（兼容指标）

`weighted_score = overall_score / overall_max * 100`

该指标来自 scenario 中 `difficulty` 的累积加权，保留用于与历史结果兼容，不作为主指标。

---

## 3. 任务成功判定

任务最终 `success` 判定遵循“严格成功”原则：

1. 所有 `required=true` 检查点必须通过。  
2. 若存在 `success_criteria`，也必须满足。  
3. 出现以下任一情况直接失败：
   - 重复动作阈值触发（`repeat_action_threshold(n)`）
   - step 执行错误且启用 step 级早停（`step_error_abort`）

这保证不会通过“放宽判定”来提高通过率。

---

## 4. 停止策略（与评分相关）

## 4.1 任务流级（Task-level）

- 默认：不中断 chain，后续任务继续执行。
- 可选：`--stop-on-first-fail-task` 启用链内首败即停。

## 4.2 任务内 step 级（Step-level）

- 默认开启：`--stop-on-first-fail-step`
- 含义：任务内某一步出现执行错误（如元素类型不匹配）立即终止该任务。
- 可关闭：`--no-stop-on-first-fail-step`

## 4.3 重复动作阈值

- 参数：`--repeat-fail-threshold`（默认 `3`）
- 含义：相同动作连续重复达到阈值，任务判失败。

---

## 5. 检查点数据结构

在 `task_spec.json` 中可配置：

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
      "depends_on": ["cp_submit"],
      "when": "NOT[mem('world_state.financial_context.liquidity') == 'frozen']"
    }
  ]
}
```

字段约束：
- `assertion` 必填（Assertion DSL）。
- `weight` 允许任意非负数，运行时会归一化。
- `required` 默认 `true`。
- `depends_on` 默认空数组。
- `when` 默认空（始终激活）；用于蝴蝶效应分支化 checkpoint。

---

## 6. 输出口径

## 6.1 任务级输出（Agent）

文件：`output/<task_id>/agent_result.json`

核心字段：
- `success`
- `end_reason`
- `repeat_fail` / `repeat_action` / `repeat_count`
- `step_error_abort` / `step_error_message`
- `checkpoint_mode`
- `checkpoint_score_percent`
- `checkpoint_results`

## 6.2 任务流级输出

`chain_runner_dynamic.py` 与 `chain_runner_oracle.py` 的 `--summary-json` 都包含：

- `chains`: 每条 chain 的逐任务明细
- `metrics.step_score`
- `metrics.task_score`
- `metrics.flow_score`
- `metrics.weighted_score`

---

## 7. 执行建议

推荐评测顺序：

1. 先跑 Oracle 小样本，确认环境和逻辑稳定。  
2. 再跑 Agent smoke（每主题 1~5 条）。  
3. 最后跑正式规模（每主题 20 条，共 100 条）。

Agent 100 条示例：

```bash
python3 -u chain_runner_dynamic.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --summary-json audit_agent_100.json
```

---

## 8. 当前体系特征

- 面向完整动态任务流
- 检查点驱动评分（可扩展、可自动生成）
- 与执行器状态、失败机制、输出文件完全一致
