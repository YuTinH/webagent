# Workflow Benchmark Reward 设计

本文档给出一个适合 Test-Time Training / RL 的 reward 方案。核心目标是：在 `final_success` 很稀疏时仍然能学习，同时不奖励不合理路径、非法状态转移或 benchmark/infra 问题。

## 设计原则

1. `final_success` 仍然是最终评测主指标，但不直接作为唯一训练 reward。
2. reward 必须有稠密进度信号，否则 Qwen 在 hard split 上大量 `0/1=0`，RL 没有梯度。
3. reward 必须有合法性门控，不能让 agent 靠 shortcut、乱点或不现实流程拿高分。
4. UI infra / selector / 页面实现问题不进入训练更新，避免把错误监督写入 memory 或模型。
5. reward 用于训练或 test-time adaptation，论文汇报时仍同时报告 success rate、average reward、composite score 和 failure attribution。

## 变量定义

现有 evaluator 已经提供：

| 变量 | 含义 |
| --- | --- |
| `S` | `final_success`，最终 workflow 是否成功，取值 0/1 |
| `C` | `target_state_coverage`，目标状态覆盖率 |
| `L` | 合法性分数，非法 module transition 越多越低 |
| `H` | hard constraints 是否满足，例如预算、deadline、must avoid |
| `E` | efficiency score，是否少走无关 module |
| `I` | `invalid_transition_count` |
| `V` | hard constraint violation 个数 |
| `P` | module/checkpoint progress，来自 atomic task 的 `step_progress` 或 checkpoint passed ratio |

如果某个 run 暂时没有 `P`，可退化为：

```text
P = C
```

但推荐后续把每个 atomic module 的 `step_progress` 记录进 workflow trace。

## Episode Reward

推荐主 reward：

```text
progress = 0.65 * C + 0.35 * P
quality  = 0.75 + 0.25 * E

R_positive = progress * quality
R_success  = 0.20 * S
R_penalty  = 0.35 * min(I, 3) + 0.50 * 1[V > 0] + 0.20 * max(0, V - 1)

R_episode = clip(R_positive + R_success - R_penalty, -1.0, 1.0)
```

解释：

- 只要没有完成任何目标或 checkpoint，`progress=0`，因此 no-op 不会因为合法、没违规而拿正 reward。
- `final_success` 只额外加 `0.20`，避免 reward 完全变成 sparse success。
- 非法状态转移和 hard constraint violation 是强惩罚，防止 reward hacking。
- `E` 只作为乘子，不单独给分；也就是说“很高效但没完成目标”不会拿高分。

## Module-Level Reward

对于 test-time RL 或 trajectory filtering，可以给每个 atomic module 单独打分：

```text
R_module = 0.75 * step_progress
         + 0.15 * module_success
         + 0.10 * selector_valid
         - 0.25 * repeat_loop
         - 0.30 * premature_done
         - 0.40 * invalid_action
```

其中：

- `step_progress`：该 module 的 checkpoint 进度。
- `module_success`：该 module 是否通过 required checkpoints。
- `selector_valid`：action 是否能被页面执行，不代表任务正确，只给很小权重。
- `repeat_loop`：重复执行同一 action 或 selector。
- `premature_done`：过早 `DONE()`，但目标没完成。
- `invalid_action`：非法 action、无法解析 action、明显越界 selector。

`R_module` 主要用于生成 memory/reflection/trajectory，而不是最终论文主指标。

## Block-Level Online Reward

在线适应按 block 更新时，使用 block 平均 reward：

```text
R_block = mean(R_episode_i for i in block)
```

为了判断方法是否真的学习，报告：

```text
Delta_R_block = R_block(method) - R_block(static)
```

这样即使 success rate 都是 0，也能看出 memory/reflexion 是否提高了目标覆盖率或 checkpoint 进度。

## Advantage 归一化

训练时不要直接用原始 reward，建议用主题/难度归一化 advantage：

```text
A_i = R_i - mean_reward(theme_i, difficulty_bucket_i)
```

难度桶可以按历史 Qwen 表现划分：

- `easy`：历史成功或 composite >= 0.95
- `medium`：0.70 <= composite < 0.95
- `hard`：composite < 0.70

这样可以避免模型只学习 easy theme，或者 hard theme 永远给负梯度。

## 数据进入训练的过滤规则

以下 instance 不进入模型/skill/memory 更新：

| 情况 | 处理 |
| --- | --- |
| 高置信 UI infra / selector / 页面实现错误 | `weight = 0`，只记录 audit |
| benchmark 逻辑错误或不可解 | `weight = 0`，需要修 benchmark |
| model 输出非法 action | 可以进入负样本，除非由 infra 导致 |
| repeat loop | 进入负样本 |
| premature done | 进入负样本 |
| final_success 或高 reward trajectory | 进入正样本 |

## 用于不同方法的策略

### MemoryBank / Reflexion

- `R_episode >= 0.75`：写正经验，记录可复用策略。
- `0.35 <= R_episode < 0.75`：写 partial progress，记录哪些 checkpoint 完成、哪些没完成。
- `R_episode < 0.35`：写 failure reflection，重点记录失败原因，不作为成功示范。

### Trajectory RAG

- workflow 成功：整条 workflow 可作为正 trajectory。
- workflow 失败但 module 成功：只写成功 atomic module 轨迹。
- module checkpoint 未过：不写正 trajectory，只写失败标签。

### RL / DPO / Rejection Sampling

对同一 goal 采样多个 rollout：

```text
positive = rollout with highest R_episode
negative = rollout with lowest R_episode
```

只有当：

```text
R_positive - R_negative >= 0.20
```

才生成 preference pair，避免噪声过大。

## 推荐论文报告指标

主指标：

- `final_success_rate`
- `average_episode_reward`
- `average_composite_score`
- `AULC_reward`
- `AULC_success`

诊断指标：

- `target_state_coverage`
- `checkpoint_progress`
- `invalid_transition_count`
- `hard_constraint_violation_rate`
- `repeat_loop_rate`
- `premature_done_rate`
- `UI/infra excluded count`

## 推荐默认版本

建议命名为：

```text
WFG-R1
```

一句话描述：

> WFG-R1 is a legality-gated dense reward that combines workflow target coverage, module checkpoint progress, success bonus, and penalties for invalid transitions and hard-constraint violations.

