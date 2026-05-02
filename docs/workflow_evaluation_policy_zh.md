# Workflow Benchmark 评测策略草案

## 1. 目标

新的 workflow benchmark 不应把评测退化成“是否复现预设路径”。

评测要回答的是三个问题：

- agent 最终是否达成了高层目标
- agent 的过程是否合法
- agent 是否以合理成本达成目标

因此，评测原则应当是：

- 结果优先
- 过程校验
- 效率次之

## 2. 核心原则

### 2.1 不要求严格复现 reference path

`workflow_oracle.json` 里的 `success_paths` 应理解为：

- reference paths
- evaluator 的参考成功组合
- partial credit 和诊断依据

而不是：

- 唯一允许的白名单路径

如果模型没有走 oracle 里预设的路径，但：

- 最终满足 `target_state`
- 整个模块序列合法
- 没有违反 hard constraints

那么不应直接判错。

### 2.2 允许 novel success

workflow benchmark 应允许模型走出预设之外的新路径。

只要该路径满足：

- 最终目标达成
- 状态转移合法
- 预算/时限/风险等硬约束满足

就应当记为：

- `novel_success`

而不是 fail。

### 2.3 额外模块不应直接导致失败

如果模型多走了一些无关紧要但合法的模块，例如：

- 多查了一次状态
- 多做了一个不破坏目标的辅助模块
- 顺序略绕，但最后结果正确

则应：

- 保持 success
- 根据冗余程度扣效率分

不应直接判失败。

### 2.4 非法过程即使结果对了也不能视为完整成功

以下情况即使最终碰巧满足 `target_state`，也不应视为完整成功：

- 模块前置条件未满足
- 依赖关系被跳过
- 进入禁止状态
- 超预算
- 超时限
- 超出 `max_steps` 或 `max_module_invocations`
- 通过明显不合理的状态污染达成目标

## 3. 四层判分结构

建议 evaluator 分四层打分，而不是只看 `pass/fail`。

### 3.1 Final Goal Success

检查：

- `target_state ⊆ final_state`

这是最核心的判定。

如果最终目标都没有达成，则不能算成功。

### 3.2 Transition Legality

对模型实际执行的 module trace 做逐步 replay：

- 当前 state 是否满足该模块的 `requires`
- 执行后 state 是否按 `effects` 正常更新
- 是否出现 dependency violation

这一层的目的是防止“野路子成功”。

### 3.3 Hard Constraint Satisfaction

检查：

- budget 是否超出
- deadline 是否超出
- forbidden outcomes 是否触发
- 步数是否超限
- module invocation 数是否超限

若这一层不满足，则应失败或大幅扣分。

### 3.4 Efficiency and Redundancy

如果 agent：

- 走了额外但合法的模块
- 选择了更绕的路径
- 做了不必要的辅助动作

则在这一层扣分。

这一层对应 oracle 里的：

- `unnecessary_module_penalty`
- `recovery_bonus`

## 4. 成功类型

建议 evaluator 显式区分成功类型，而不是把所有 success 混在一起。

### 4.1 Reference Success

模型走出的路径与 oracle 中某条 `success_path` 一致，或在模块集合上等价。

### 4.2 Novel Success

模型没有严格走 reference path，但：

- 最终目标达成
- 过程合法
- 硬约束满足

这种成功非常重要，因为它说明 benchmark 真正在测 workflow composition，而不是 path imitation。

### 4.3 Success With Extraneous Modules

模型成功了，但带有一些无关紧要的额外模块。

这种情况应：

- 记成功
- 扣效率分

### 4.4 Recovered Success

模型中途走错或失败，但后续：

- 发现问题
- 切换路径
- 最后仍完成目标

这种情况应：

- 记成功
- 可附带一定 `recovery_bonus`

## 5. 失败类型

建议失败类型至少区分：

- `final_goal_not_reached`
- `invalid_transition`
- `hard_constraint_violation`
- `dead_end_without_recovery`
- `max_steps_exceeded`
- `max_module_invocations_exceeded`

这样后面分析 agent 的问题时，才能知道：

- 是不会规划
- 还是规划对了但执行烂
- 还是执行对了但效率差

## 6. 以 WFG-TRAVEL-0340 为例

样本文件：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v18/train/workflow_goal_instances/WFG-TRAVEL-0340.json`
- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v18/train/workflow_oracles/WFG-TRAVEL-0340.json`

目标是：

- `travel_booking_confirmed`
- `mobility_clearance_verified`

oracle 里的两条 reference path 是：

1. `MODULE_BOOK_FLIGHT -> MODULE_VISA_REQUIREMENTS`
2. `MODULE_LONG_HAUL_TRIP`

### 6.1 标准成功

模型走：

- `MODULE_BOOK_FLIGHT -> MODULE_VISA_REQUIREMENTS`

则属于 `reference_success`。

### 6.2 合法新路径

如果模型走：

- `MODULE_BOOK_FLIGHT -> MODULE_HOTEL_BOOKING -> MODULE_VISA_REQUIREMENTS`

并且：

- `MODULE_HOTEL_BOOKING` 是合法模块
- 没违反 budget / deadline
- 最终仍满足 `travel_booking_confirmed` 和 `mobility_clearance_verified`

则应判为：

- `novel_success` 或 `success_with_extraneous_modules`

而不是 fail。

### 6.3 非法成功

如果模型通过一个前置条件不满足的模块，碰巧把状态补齐，
或者中途违反了 hard constraint，再把目标补回来了，
则不能算完整成功。

## 7. 建议的评测输出字段

建议每个 workflow episode 最终输出：

- `final_success: bool`
- `success_type: one_of(reference_success, novel_success, success_with_extraneous_modules, recovered_success, failure)`
- `target_state_coverage: float`
- `hard_constraints_satisfied: bool`
- `invalid_transition_count: int`
- `extraneous_module_count: int`
- `used_reference_path: optional path_id`
- `matched_reference_path_exactly: bool`
- `score_breakdown`

其中 `score_breakdown` 可以拆成：

- `goal_score`
- `legality_score`
- `constraint_score`
- `efficiency_score`
- `recovery_score`

## 8. 与当前 oracle schema 的关系

当前 `workflow_oracle.json` 已经支持：

- `success_paths`
- `reference_invocations`
- `evaluation.unnecessary_module_penalty`
- `evaluation.invalid_transition_penalty`
- `evaluation.recovery_bonus`

因此这份评测策略并不是推翻现有设计，而是把它的解释明确化：

- `success_paths` 是 reference，不是唯一白名单
- `reference_invocations` 是参考实例，不是唯一合法实例
- 最终判分应当允许 novel success

## 9. 当前实现状态

这套评测逻辑现在已经有了一个可运行的第一版实现：

- evaluator 脚本：
  - `/Users/masteryth/Documents/webagent/rl_memory/scripts/evaluate_workflow_episode.py`
- episode trace schema：
  - `/Users/masteryth/Documents/webagent/schemas/workflow_execution_trace.json`

当前实现已经支持：

1. `final_state` 检查
2. module-level transition replay
3. hard constraints 检查
4. `reference_success / novel_success / success_with_extraneous_modules / recovered_success` 区分

另外还补了一个最小 workflow runner 原型：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_episode.py`

这个 runner 现在可以先完成：

- 从 `goal/oracle` 里选一条 reference path
- 解析 `module -> binding -> atomic task`
- 实例化具体子任务文件
- 产出 execution trace
- 调 evaluator 给出 episode 级判分

因此当前状态已经不是只有“静态数据集”，而是有了一条最小可用的 workflow episode 运行链。
