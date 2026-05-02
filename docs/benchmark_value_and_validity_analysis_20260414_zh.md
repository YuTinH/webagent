# Workflow Benchmark 当前上下文交接（给新 thread / agent）

更新时间：2026-04-29

这份文档的目的不是写论文正文，而是给新开的 thread / agent 快速恢复上下文：现在项目在做什么、已经完成到什么程度、哪些结论可以相信、哪些口径不能混淆、下一步应该优先做什么。

## 1. 当前主线

我们现在围绕 `webagent` 的 workflow benchmark 做三件事：

1. **证明 benchmark 本身正确、可解、现实合理。**
   - 不是只看模型分数，而是先确认 workflow 资产、oracle、checkpoint、selector、页面实现没有系统性错误。

2. **处理导师对 benchmark 价值的质疑。**
   - 旧版 `dev` 上 Qwen2.5-7B-Instruct 曾经达到 90%+ 甚至 100%，所以需要解释：这是否说明 benchmark 太容易、没有价值。
   - 当前判断：旧版 dev 的高分说明早期 benchmark / dev split 存在饱和和 shortcut 风险，不代表 benchmark 作废。后续工作已经转向 hardening、difficulty audit、held-out 评测和 test-time adaptation。

3. **搭建 hardened benchmark + dense reward + online adaptation 实验协议。**
   - 当前 hardened 设置下 final success 很稀疏，所以不能只看 0/1 success。
   - 已实现 `WFG-R1` dense reward，用 checkpoint progress、target coverage、module reward 等指标衡量 partial progress。

## 2. 关键目录和文件

项目根目录：

- `/Users/masteryth/Documents/webagent`

当前 benchmark batch：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20`

关键文档：

- `/Users/masteryth/Documents/webagent/docs/workflow_dataset_validity_report_v20.md`
- `/Users/masteryth/Documents/webagent/docs/workflow_dataset_validity_report_v20.json`
- `/Users/masteryth/Documents/webagent/docs/workflow_difficulty_audit_v20.md`
- `/Users/masteryth/Documents/webagent/docs/workflow_difficulty_audit_v20.json`
- `/Users/masteryth/Documents/webagent/docs/workflow_benchmark_weekly_report_20260428_zh.md`
- `/Users/masteryth/Documents/webagent/docs/high_conf_ui_636_goal_validation_20260425_zh.md`
- `/Users/masteryth/Documents/webagent/docs/online_adaptation_reward_compare_20260426_zh.md`
- `/Users/masteryth/Documents/webagent/docs/workflow_reward_design_20260426_zh.md`
- `/Users/masteryth/Documents/webagent/docs/workflow_realism_audit_rules_20260423_zh.md`
- `/Users/masteryth/Documents/webagent/docs/grpo_smoke_plan_20260429_zh.md`

关键脚本：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark.py`
- `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_online_adaptation_blocks.py`
- `/Users/masteryth/Documents/webagent/rl_memory/scripts/reward_calculator.py`
- `/Users/masteryth/Documents/webagent/rl_memory/scripts/compare_reward_runs.py`
- `/Users/masteryth/Documents/webagent/rl_memory/scripts/audit_high_conf_ui_regression.py`

## 3. 当前已经完成的事实

### 3.1 v20 workflow 结构 validity 已经全量 clean

来自：

- `docs/workflow_dataset_validity_report_v20.md`

核心数字：

| 指标 | 数值 |
| --- | ---: |
| total goals | 5040 |
| solvable goals | 5040 |
| solvable ratio | 1.000 |
| all-paths-executable goals | 5040 |
| all-paths-executable ratio | 1.000 |
| invalid path count | 0 |

分 split：

| split | goals | solvable | all paths executable | invalid path count |
| --- | ---: | ---: | ---: | ---: |
| dev | 140 | 140/140 | 140/140 | 0 |
| test | 140 | 140/140 | 140/140 | 0 |
| train | 4760 | 4760/4760 | 4760/4760 | 0 |

解释：

- 每个 goal 至少存在一条结构上可执行的成功路径。
- 所有声明的 success paths 都能通过 module precondition / effect 的 symbolic execution。
- 当前不能再说 v20 里还有已知 invalid path。

### 3.2 当前 workflow 已经是长链口径

来自：

- `docs/workflow_dataset_validity_report_v20.md`

关键统计：

| 指标 | 全局数值 |
| --- | ---: |
| path_length.mean | 5.0533 |
| path_length.median | 5.0 |
| path_length.min | 5 |
| path_length.max | 6 |
| success_path_count.mean | 1.8988 |

分 split：

| split | path_length.mean | success_path_count.mean |
| --- | ---: | ---: |
| dev | 5.04 | 1.7857 |
| test | 5.00 | 1.9286 |
| train | 5.0552 | 1.9013 |

注意：

- 早期文档里有过平均路径长度约 `2.43` 的旧口径，不要再当成当前状态引用。
- 当前 v20 是 5 步左右的 workflow 链。

### 3.3 realism / quality audit 当前没有硬失败

来自：

- `docs/workflow_dataset_validity_report_v20.md`
- `docs/workflow_realism_audit_rules_20260423_zh.md`

当前 audit snapshot：

| 审计项 | 当前结果 |
| --- | --- |
| `blueprint_split_hard_fail_reasons` | `[]` |
| `blueprint_realism_issue_count` | `0` |
| `batch_realism_issue_count` | `0` |
| `dev_goal_quality_hard_fail_reasons` | `[]` |
| `test_goal_quality_hard_fail_reasons` | `[]` |
| `train_goal_quality_hard_fail_reasons` | `[]` |

解释：

- 结构上可解不等于现实合理，所以另有 realism audit。
- 当前自动审计没有发现主题错配、明显不合理路径、初始即满足、自相矛盾等硬失败。
- 后续仍建议补 first-step relevance 和 detour rate 统计。

### 3.4 636 个 high-confidence UI infra 问题已逐项清零

来自：

- `docs/high_conf_ui_636_goal_validation_20260425_zh.md`

旧 full train run 中曾识别出 `636` 个 high-confidence UI infra / selector / 页面实现问题。修复后 targeted regression 结果：

| 指标 | 数值 |
| --- | ---: |
| 目标 goal 数 | 636 |
| 收到 trace 数 | 636 |
| 缺失 trace 数 | 0 |
| Qwen 成功数 | 4 |
| Qwen 成功率 | 0.63% |
| remaining high-confidence UI issue goals | 0 |
| remaining high-confidence UI issue attempts | 0 |

解释：

- 这轮不是为了让 Qwen 高分，而是验证旧的 deterministic benchmark-side UI/selector/page bug 是否复现。
- 结果是旧 high-confidence UI infra 问题没有复现。
- 剩余失败主要是模型行为问题，例如 repeat action loop、premature done、动作顺序错误、checkpoint 未满足。

相关修复文件：

- `agent/browser_env.py`
- `llm_runner.py`
- `sites/shop.local/ticket.html`
- `sites/work.local/paper-submission.html`
- `rl_memory/scripts/audit_high_conf_ui_regression.py`

## 4. 关于“Qwen dev 90%+”的正确口径

旧版 dev full run 中，Qwen2.5-7B-Instruct 曾经很高：

| run | split | goal 数 | final success | final success rate | average composite |
| --- | --- | ---: | ---: | ---: | ---: |
| `workflow_qwen25_7b_dev_full_v30_strict` | dev | 140 | 130 | 92.86% | 0.9839 |
| `workflow_qwen25_7b_dev_full_v48_strict` | dev | 140 | 140 | 100.00% | 1.0000 |

这个结果应该这样解释：

- 旧版 `dev` 已经接近饱和；
- 旧口径可能存在 shortcut、任务链偏短、checkpoint 约束不够强；
- 不能用旧版 dev 高分证明 benchmark 最终有足够区分度；
- 也不能反过来说 benchmark 没价值；
- 正确动作是做 hardening、difficulty audit、held-out test 和 cross-model gap。

当前 hardened / online adaptation 设置下的 `n=100` 结果：

| 方法 | final success | average reward | target coverage | checkpoint progress | module reward |
| --- | ---: | ---: | ---: | ---: | ---: |
| `static` / vanilla Qwen2.5-7B | 0/100 | 0.2596 | 0.1070 | 0.5431 | 0.3564 |
| `reflexion` | 0/100 | 0.2620 | 0.1050 | 0.5536 | 0.3622 |
| `trajectory_rag` | 0/100 | 0.2903 | 0.1713 | 0.5112 | 0.3512 |

注意：

- `static` 就是 vanilla Qwen2.5-7B，不加 memory、不加 reflexion、不加 trajectory RAG。
- 这不是旧 v30/v48 的复现，而是 hardened 设置下的新口径。
- 不能把旧 `90%+` 和当前 `0/100` 简单对比成“方法让模型变差”。benchmark 版本、任务难度、运行协议已经变了。

## 5. 当前 difficulty audit 状态

来自：

- `docs/workflow_difficulty_audit_v20.md`

全局 goal-level 统计：

| 指标 | 数值 |
| --- | ---: |
| shortest_path_len.mean | 3.1766 |
| shortest_path_len.median | 3.0 |
| num_success_paths.mean | 1.8552 |
| target_state_size.mean | 2.8135 |
| visible_constraint_count.mean | 3.6964 |
| counterfactual_axis_count.mean | 4.0238 |
| max_steps.mean | 44.2024 |
| max_module_invocations.mean | 3.6647 |

saturation-risk indicators：

| 指标 | 数值 |
| --- | ---: |
| share_shortest_path_le_2 | 0.316 |
| share_target_size_le_2 | 0.546 |
| share_success_paths_le_2 | 0.996 |
| share_step_budget_ratio_ge_15 | 0.559 |
| share_module_budget_slack_le_1 | 0.917 |

解释：

- 当前结构 validity clean，但不能说 difficulty 已经最终充分。
- 仍有一部分 goal shortest path 偏短、target state 偏小、step budget 偏宽。
- hardening 的方向是清除 shortcut、加长任务链、增强 checkpoint，而不是靠坏页面或坏 selector 制造难度。

## 6. 当前 reward / online adaptation 状态

### 6.1 WFG-R1 dense reward

来自：

- `docs/workflow_reward_design_20260426_zh.md`
- `docs/online_adaptation_reward_compare_20260426_zh.md`

核心公式：

```text
progress = 0.65 * target_state_coverage + 0.35 * checkpoint_progress
quality  = 0.75 + 0.25 * efficiency_score

R_positive = progress * quality
R_success  = 0.20 * final_success
R_penalty  = 0.35 * min(invalid_transition_count, 3)
           + 0.50 * has_hard_constraint_violation
           + 0.20 * extra_hard_constraint_violations

R_episode = clip(R_positive + R_success - R_penalty, -1.0, 1.0)
```

作用：

- final success 很稀疏时，仍能衡量 partial progress。
- 区分 checkpoint progress、target-state coverage、module-level 行为质量。
- 惩罚 invalid transition 和 hard constraint violation。

### 6.2 n=30 四方法初步结果

| 方法 | 成功率 | 平均 reward | 相对 static | 目标状态覆盖率 | checkpoint progress | module reward |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| static | 0/30 | 0.1129 | +0.0000 | 0.0794 | 0.1750 | 0.0500 |
| memorybank_lite | 0/30 | 0.1076 | -0.0053 | 0.0772 | 0.1639 | 0.0462 |
| reflexion | 0/30 | 0.2040 | +0.0911 | 0.0844 | 0.4260 | 0.2303 |
| trajectory_rag | 0/30 | 0.2312 | +0.1183 | 0.1128 | 0.4511 | 0.2884 |

解释：

- final success 全是 `0/30`。
- 但 dense reward 显示 `trajectory_rag` 和 `reflexion` 在中间进度上优于 static。
- 这说明 reward 能区分方法，不代表已经证明方法能提升 final success。

### 6.3 block-wise online adaptation 协议

当前协议：

1. goal stream 按 block 划分，例如每 10 个 instance 一个 block。
2. block 内只能读取进入 block 前已有的 memory / reflection / trajectory。
3. block 内产生的新经验先写入 delta store。
4. block 结束后，delta 才 merge 到下一 block 的 snapshot。

目的：

- 避免同一个 block 内的信息泄漏。
- 让 test-time adaptation / online learning 评测更干净。

## 7. 现在可以相信的结论

可以对新 agent 直接沿用：

1. `workflow_split_batch_v20` 静态结构 validity 已经全量 clean。
2. `dev/test/train` 都是 `solvable_ratio = 1.000`、`all_paths_executable_ratio = 1.000`、`invalid_path_count = 0`。
3. 当前 path length 已经是 5 步左右的长链口径。
4. realism / quality audit 当前没有硬失败。
5. 旧的 636 个 high-confidence UI infra / selector / 页面实现问题已经 targeted regression 清零。
6. 旧版 dev 高分说明旧口径有饱和风险，不应再当成最终 benchmark 难度证据。
7. hardened 设置下 final success 很稀疏，但 checkpoint progress 和 reward 能显示 partial progress。
8. WFG-R1 reward 和 block-wise online adaptation 协议已经有初版可用。

## 8. 现在不能过度声称的内容

不要写：

- benchmark 已经最终足够难；
- 所有 split 的真实 agent rollout 都 fully clean；
- `0/100` final success 单独证明 benchmark 完美；
- dense reward 已经证明 test-time adaptation 能显著提升 final success；
- Qwen 旧版 dev 90%+ 和当前 hardened 0/100 可以直接横向比较。

更准确的说法：

- 静态结构和高置信 infra 证据已经比较强；
- difficulty 和 workflow logic audit 仍要继续做；
- final success 稀疏后，必须同时报告 dense reward、checkpoint progress、target coverage；
- 后续需要 apples-to-apples hardened baseline 和更大规模 online adaptation。

## 9. 下一步优先级

### P0：apples-to-apples hardened baseline

目标：

- 用当前 hardened benchmark 单独跑标准 vanilla Qwen2.5-7B baseline。
- 不要和旧 v30/v48 混在一起比较。
- 输出 final success、WFG-R1、target coverage、checkpoint progress、module reward、invalid transition、hard constraint violation。

### P1：first-step relevance / detour rate 统计

目标：

- 回应导师“售后为什么不是从售后开始”这类质疑。
- 统计每个 goal 的首个合法 module 是否和主题/目标语义一致。
- 统计 success path 是否包含不合理跨域绕路。
- 按 theme 输出 domain-start consistency 和 detour rate。

### P1：difficulty bucket 分析

目标：

- 按 shortest path length、target state size、difficulty level、theme 分桶。
- 看 vanilla baseline 和 test-time methods 在各 bucket 的 reward / progress / success。
- 用 cross-bucket 或 cross-model gap 证明 benchmark 有区分度。

### P2：扩大 online adaptation

目标：

- 补齐 `memorybank_lite n=100`。
- 扩大 static / reflexion / trajectory_rag / memorybank_lite 对比。
- 固定 block size、goal stream、agent 参数和 reward 版本。

### P2：继续 targeted workflow logic audit

优先检查：

- 长链任务；
- 极端主题；
- 跨站点依赖任务；
- shortest path 过短或 target state 过小的 saturation-risk candidates。

## 10. 给新 agent 的一句话任务理解

当前不是在单纯“调高 Qwen 分数”，而是在把 workflow benchmark 从早期 correctness / infra 修复阶段推进到论文可用的 benchmark 论证阶段：我们已经有 v20 全量结构 validity、realism audit、636 项高置信 UI infra 回归和 WFG-R1 / online adaptation 初版结果；下一步重点是 apples-to-apples hardened baseline、first-step / detour 合理性统计、difficulty bucket 分析和更大规模 online adaptation。
