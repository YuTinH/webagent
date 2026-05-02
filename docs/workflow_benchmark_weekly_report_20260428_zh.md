# Workflow Benchmark 本周进展汇报（2026-04-28）

## 1. 本周核心结论

本周主要完成了三件事：

1. **把 benchmark 侧的 infra / UI / selector 确定性问题清理到可解释状态。**
   - 针对旧 run 中标记出的 `636` 个 high-confidence UI infra / selector / 页面实现问题，完成逐项 targeted regression。
   - 修复后 `636/636` 都收到 trace，`0` 个旧 high-confidence UI 问题复现。
   - 剩余失败主要是 agent 自身能力问题，例如重复动作、提前结束、动作顺序错误，而不是 benchmark 页面或 selector 坏掉。

2. **建立了 workflow 正确性与合理性验证框架。**
   - 从 taskflow 构建、module 前后置状态、oracle / checkpoint、realism audit、targeted logic audit 多层验证。
   - 目标是证明每个 workflow 在 agent 能力足够时存在可行解，并且路径符合现实业务逻辑。
   - 例如售后退款流程应从订单/售后入口开始，而不是先从办银行卡、开账户这类无关流程开始。

3. **开始搭建 test-time training / online adaptation 评测协议。**
   - 实现了 block-wise online adaptation：每 10 个 instance 后才允许更新 memory / reflection / trajectory store。
   - 实现了 dense reward `WFG-R1`，用于在 final success 很稀疏时衡量中间进度。
   - 初步比较了 `static`、`memorybank_lite`、`reflexion`、`trajectory_rag` 等方法。

## 2. 需要先说明的数据口径

这周的实验里有两个容易混淆的口径，需要汇报时明确区分。

### 2.1 旧版 dev full 表现

旧版 dev full run 中，Qwen2.5-7B-Instruct 曾达到很高成功率：

| run | split | goal 数 | final success | final success rate | average composite |
| --- | --- | ---: | ---: | ---: | ---: |
| `workflow_qwen25_7b_dev_full_v30_strict` | dev | 140 | 130 | 92.86% | 0.9839 |
| `workflow_qwen25_7b_dev_full_v48_strict` | dev | 140 | 140 | 100.00% | 1.0000 |

这个结果说明：如果 benchmark 太容易，或者存在 shortcut，Qwen2.5-7B 就已经能做得很好。因此导师提出的问题是合理的：如果 baseline 已经接近满分，benchmark 的区分度不足。

### 2.2 当前 hardened / online adaptation 实验口径

后来我们做了 shortcut 清理、任务链加长、现实路径约束和更严格的 workflow 检查。当前 online adaptation 的 `n=100` 不是直接复现旧 v30，而是在当前 hardened 版本上重新跑。

| 方法 | final success | average reward | target coverage | checkpoint progress | module reward |
| --- | ---: | ---: | ---: | ---: | ---: |
| `static` / vanilla Qwen2.5-7B | 0/100 | 0.2596 | 0.1070 | 0.5431 | 0.3564 |
| `reflexion` | 0/100 | 0.2620 | 0.1050 | 0.5536 | 0.3622 |
| `trajectory_rag` | 0/100 | 0.2903 | 0.1713 | 0.5112 | 0.3512 |

这里的 `static` 就是 vanilla baseline：不加 memory、不加 reflexion、不加 trajectory RAG，只用 Qwen2.5-7B 执行。

因此不能把旧版 `90/100` 和当前 `0/100` 解释成“加方法导致变差”。正确解释是：**benchmark 版本、任务难度和运行协议已经发生变化，当前 hardened 设置下 final success 很稀疏，所以需要同时看 checkpoint progress 和 dense reward。**

## 3. Infra / UI / Selector 修复与验证

### 3.1 修复内容

本周集中修复了 benchmark 侧高置信 deterministic 问题，主要包括：

| 类型 | 例子 | 修复方式 |
| --- | --- | --- |
| 上传控件不一致 | task 需要上传证明文件，但页面是文本型 file-name 字段 | `UPLOAD` 遇到非 file input 时改为填入文件名文本 |
| selector alias 不一致 | `#modal_confirm` vs `#modal-confirm` | 在执行层补充常见 selector alias |
| 页面选项缺失 | 售后 issue type 缺少 `wrong_item`、`quality_issue` 等 | 补齐页面 option，和 task/oracle 对齐 |
| 页面校验过严 | paper submission 强制要求非任务目标字段 | 将非 oracle 必要字段改为默认值或非强制 |

相关改动集中在：

- `agent/browser_env.py`
- `llm_runner.py`
- `sites/shop.local/ticket.html`
- `sites/work.local/paper-submission.html`
- `rl_memory/scripts/audit_high_conf_ui_regression.py`

### 3.2 636-goal targeted regression

针对旧 full train run 中识别出的 `636` 个 high-confidence UI infra / selector / 页面实现问题，进行了逐项验证。

| 指标 | 数值 |
| --- | ---: |
| 目标 goal 数 | 636 |
| 收到 trace 数 | 636 |
| 缺失 trace 数 | 0 |
| Qwen 成功数 | 4 |
| Qwen 成功率 | 0.63% |
| remaining high-confidence UI issue goals | 0 |
| remaining high-confidence UI issue attempts | 0 |

结论：旧的高置信 benchmark-side UI infra 问题已经逐项清除。Qwen 成功率低不是坏事，这里本来就是在验证“benchmark 不坏”，不是验证“模型能做出来”。

### 3.3 剩余失败归因

修复后 636 个 targeted goal 中剩余失败主要为：

| failure category | 数量 | 解释 |
| --- | ---: | --- |
| `repeat_action_loop` | 573 | 模型重复执行相同或近似动作，状态没有推进。 |
| `premature_done` | 36 | 模型提前输出 DONE，但业务目标未满足。 |
| `criteria_or_checkpoint_failed` | 15 | 执行了一些动作，但最终 oracle/checkpoint 没通过。 |
| `element_not_found_or_timeout` | 8 | 复查后是模型动作顺序错误，不是 selector 缺失。 |

一个典型例子是 lease contract 场景：模型先打开 modal，填了合同号和结束日期，然后在租金还没填时点击确认，modal 关闭后再尝试填租金，导致找不到 `#new-rent`。字段本身存在，失败来自动作顺序错误。

## 4. Workflow 正确性与合理性保障

导师关心的问题是：我们的 taskflow 怎么证明不是拍脑袋构造的？本周针对这个问题补了多层验证。

### 4.1 构建时约束

每个 workflow 不只是自然语言 goal，而是由多个结构化对象共同定义：

| 组件 | 作用 |
| --- | --- |
| module library | 所有可复用子任务 module 的集合，例如查订单、申请退款、更新地址、提交证明等。 |
| module binding | 把抽象 module 绑定到具体页面、selector、输入字段和业务数据。 |
| precondition / effect | 定义 module 执行前需要什么状态，执行后产生什么状态。 |
| workflow oracle | 定义最终目标状态和必须满足的 hard constraints。 |
| checkpoint | 定义中间过程是否合理推进，例如是否先定位订单，再提交退款申请。 |

这样可以避免 workflow 只是自然语言拼接，而是有状态转移依据。

### 4.2 Realism audit 规则

realism audit 主要检查 workflow 是否符合现实业务场景，而不是只要可执行就算合理。

| 规则 | 含义 | 例子 |
| --- | --- | --- |
| 主题一致性 | workflow 内 module 应属于同一现实任务主题 | 售后退款不应从办银行卡开始。 |
| 起点合理性 | 用户目标应从现实中合理入口开始 | “退货退款”应从订单/售后页开始。 |
| 前置条件合理 | 如果需要前置状态，必须是现实任务需要的 | 申请停车证前可以有地址更新，但不应要求买电影票。 |
| 数据依赖真实 | 后一步使用的数据应来自前一步或用户输入 | 先查订单号，再对该订单发起退款。 |
| 无 shortcut | 不应有一键完成绕开关键业务步骤的路径 | 不能直接改数据库状态或隐藏按钮直接完成 oracle。 |
| 可解性 | agent 能力足够时必须有一条合法路径完成 | 页面、selector、输入、oracle 都要闭环。 |
| hard constraint 保持 | 预算、deadline、禁止条件等不能被违反 | 旅行改签不能超过预算或选错日期。 |

### 4.3 Logic audit 与 targeted validation

本周的验证策略不是“抽样看几个没问题”，而是把失败拆成可审计类别：

| 审计类型 | 目的 |
| --- | --- |
| targeted logic audit | 对极端主题、复杂主题、长链 workflow 做人工/脚本复核。 |
| UI infra audit | 判断失败是否来自页面、selector、控件实现。 |
| failure attribution | 判断失败来自模型动作、benchmark 逻辑、还是 infra。 |
| targeted regression | 修复后只重跑受影响 goal，避免完整 train split 过慢。 |
| global sanity run | 阶段性全局跑，确认修复没有引入大范围额外错误。 |

目前高置信 UI infra 问题已经清零；仍需持续做的是更大范围的 workflow logic audit，尤其是长链任务和跨主题任务。

## 5. Benchmark 难度增强

旧版 dev 上 Qwen2.5-7B 能达到非常高成功率，因此本周开始对 benchmark 做 difficulty hardening。

主要方向：

1. **清除 shortcut。**
   - 避免页面中存在过于直接的一键完成路径。
   - 避免 oracle 只检查一个容易被误触发的最终字段。

2. **增加长链 workflow。**
   - 不只 government，其他主题也加入 4 到 5 步甚至更长的真实任务链。
   - 例如先收集信息，再更新资料，再提交申请，再验证状态。

3. **强化 checkpoint。**
   - final success 很稀疏时，中间 checkpoint 能反映 agent 是否沿正确路径推进。
   - 这也为后续 RL / test-time training 提供 dense signal。

4. **保留现实合理性。**
   - 难度增加不能靠不合理跳转或故意卡页面实现。
   - 难点应来自多步依赖、信息整合、状态保持、抗干扰，而不是 infra bug。

当前 hardened 后，Qwen 在 online adaptation `n=100` 上 final success 为 `0/100`，但 checkpoint progress 仍有 `0.5431`，说明模型并不是完全无法行动，而是经常卡在完成全部 workflow 的后半段或关键约束上。

## 6. Test-Time Training / Online Adaptation 评测协议

导师建议把评测做成 test-time training / RL 形式。本周已经实现了一个初版协议。

### 6.1 Block-wise online adaptation

协议如下：

1. 把测试流按 block 划分，例如每 10 个 instance 一个 block。
2. 一个 block 内只能读取进入 block 前已有的 memory / reflection / trajectory。
3. block 内产生的新经验先写入 delta store。
4. block 结束后，才把 delta merge 到下一 block 的 snapshot。
5. 这样可以避免同一个 block 内的信息泄漏。

通俗解释：模型不能做第 3 个题时偷看第 1、2 个题刚刚产生的经验，只有做完一组题之后，经验才能用于下一组题。

### 6.2 已实现方法

| 方法 | 含义 |
| --- | --- |
| `static` | 不做任何测试时更新，即 vanilla Qwen2.5-7B baseline。 |
| `reflexion` | 把失败/成功经验写成反思文本，下个 block 检索使用。 |
| `memorybank_lite` | 写入轻量 memory entries，下个 block 检索相关经验。 |
| `trajectory_rag` | 写入部分 trajectory，下个 block 用相似任务轨迹辅助决策。 |

相关脚本：

- `rl_memory/scripts/run_online_adaptation_blocks.py`
- `rl_memory/scripts/make_online_adaptation_goal_list.py`
- `rl_memory/scripts/compare_online_adaptation_runs.py`
- `rl_memory/scripts/reward_calculator.py`
- `rl_memory/scripts/compare_reward_runs.py`

## 7. Reward 设计：WFG-R1

因为 hardened benchmark 上 final success 变得很稀疏，如果只用 0/1 成功率，RL 或 test-time training 很难学习。因此实现了 dense reward `WFG-R1`。

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

通俗解释：

- 做对最终任务当然加分。
- 没做完最终任务，但完成了中间 checkpoint，也给部分分。
- 违反业务约束、走非法状态转移，要扣分。
- 不奖励无意义乱点或 shortcut。

### 7.1 n=30 初步实验

| 方法 | final success | avg reward | target coverage | checkpoint progress | module reward |
| --- | ---: | ---: | ---: | ---: | ---: |
| static | 0/30 | 0.1129 | 0.0794 | 0.1750 | 0.0500 |
| memorybank_lite | 0/30 | 0.1076 | 0.0772 | 0.1639 | 0.0462 |
| reflexion | 0/30 | 0.2040 | 0.0844 | 0.4260 | 0.2303 |
| trajectory_rag | 0/30 | 0.2312 | 0.1128 | 0.4511 | 0.2884 |

这轮说明：即使 final success 都是 0，dense reward 仍能区分不同方法。`trajectory_rag` 和 `reflexion` 在中间进度上明显优于 static。

### 7.2 n=100 实验

| 方法 | final success | avg reward | target coverage | checkpoint progress | module reward |
| --- | ---: | ---: | ---: | ---: | ---: |
| static / vanilla Qwen2.5-7B | 0/100 | 0.2596 | 0.1070 | 0.5431 | 0.3564 |
| reflexion | 0/100 | 0.2620 | 0.1050 | 0.5536 | 0.3622 |
| trajectory_rag | 0/100 | 0.2903 | 0.1713 | 0.5112 | 0.3512 |

解读：

- `static` 是 vanilla Qwen2.5-7B，不加任何测试时更新。
- `reflexion` 的 checkpoint progress 略高于 static：`0.5536` vs `0.5431`。
- `trajectory_rag` 的 target coverage 明显更高：`0.1713` vs `0.1070`，因此总 reward 更高。
- 三组 final success 都为 0，说明当前 hardened 设置下 full workflow 成功非常难。

这组结果暂时不能说明 test-time 方法能提升 final success，但说明 dense reward 可以捕捉到不同方法在中间进度上的差异。

## 8. 当前可以向导师强调的点

### 8.1 Benchmark 价值问题

导师质疑“Qwen 都能 90%，benchmark 意义是什么”是合理的。我们的应对不是回避，而是：

1. 先承认旧版 dev 上 Qwen 表现过高，说明旧 benchmark 区分度不足。
2. 用 systematic hardening 清除 shortcut、加长任务链、增强 checkpoint。
3. 用 targeted audit 证明难度增加不是靠 infra bug，而是靠真实 workflow 复杂度。
4. 最新 hardened 设置下 final success 已经显著下降，但仍有 checkpoint progress，说明任务不是纯不可解。

### 8.2 Workflow 正确性问题

我们不是“采样看了看”，而是建立了可复查的证据链：

- module library 和 module binding 定义可执行空间。
- precondition / effect 定义状态转移。
- oracle 和 checkpoint 定义成功与中间进度。
- realism audit 检查现实合理性。
- targeted regression 检查修复是否有效。
- failure attribution 区分 benchmark 问题和模型问题。

### 8.3 Infra 问题现状

目前高置信 UI infra / selector / 页面实现问题已经完成一次大规模逐项验证：

- `636/636` 收到 trace。
- `0` 个旧 high-confidence UI 问题复现。
- 最新 online adaptation run 中 `invalid_transition_rate = 0.0`，`hard_constraint_violation_rate = 0.0`。

因此可以谨慎表述为：**目前没有发现剩余高置信 UI infra / selector / 页面实现问题，但 workflow logic 仍会继续做 targeted audit。**

## 9. 下周计划

1. **做 apples-to-apples baseline 对齐。**
   - 用当前 hardened benchmark 单独跑标准 vanilla Qwen2.5-7B baseline。
   - 明确区分旧 v30/v48 表现和当前版本表现。

2. **继续 workflow logic audit。**
   - 优先检查长链任务、极端主题、跨站点依赖任务。
   - 对发现的问题做 targeted repair + targeted validation。

3. **扩大 online adaptation 实验。**
   - 补齐 `memorybank_lite n=100`。
   - 在更大样本上比较 static / reflexion / trajectory_rag / memorybank_lite。
   - 同时报告 final success、checkpoint progress、target coverage、WFG-R1 reward。

4. **做论文可用统计。**
   - 统计 workflow 长度分布、主题分布、checkpoint 数量分布。
   - 统计 solvable ratio、realism audit pass rate、infra issue excluded count。
   - 统计 Qwen 在不同难度桶上的表现，证明 benchmark 有区分度。

## 10. 本周产出文件

| 文件 | 作用 |
| --- | --- |
| `docs/high_conf_ui_636_goal_validation_20260425_zh.md` | 636 个 high-confidence UI infra 问题逐项验证记录。 |
| `docs/workflow_reward_design_20260426_zh.md` | WFG-R1 reward 设计文档。 |
| `docs/online_adaptation_reward_compare_20260426_zh.md` | n=30 online adaptation reward 对比。 |
| `docs/workflow_realism_audit_rules_20260423_zh.md` | realism audit 规则说明。 |
| `rl_memory/scripts/audit_high_conf_ui_regression.py` | high-confidence UI regression 审计脚本。 |
| `rl_memory/scripts/run_online_adaptation_blocks.py` | block-wise online adaptation runner。 |
| `rl_memory/scripts/reward_calculator.py` | WFG-R1 reward 计算脚本。 |
| `rl_memory/scripts/compare_reward_runs.py` | 多 run reward 对比脚本。 |

## 11. 一句话总结

本周我们把工作重点从“让 Qwen 跑出高分”转向“证明 benchmark 本身正确、合理、可解且有区分度”：高置信 UI infra 问题已经完成 636 项逐项清零；workflow 正确性开始通过 module 状态转移、oracle/checkpoint、realism audit 和 targeted validation 建立证据链；同时初步实现了 test-time adaptation 协议和 WFG-R1 dense reward，为后续 RL / test-time training 实验打基础。
