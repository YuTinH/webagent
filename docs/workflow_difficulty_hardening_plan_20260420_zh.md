# Workflow Benchmark 难度提升计划（2026-04-20）

## 1. 目标

这份计划解决的不是 “benchmark 有没有 bug”，而是 “benchmark 在 correctness / infra 基本收口后，如何继续保持区分度”。

后续所有 hardening（提难 / 收紧）工作都按下面两层目标执行：

### 1.1 硬约束

这部分必须保持全绿：

- `solvable_ratio = 1.000`
- `all_paths_executable_ratio = 1.000`
- 没有逻辑错误、环境错误、页面错误、脏初始状态、错误前置条件
- taskflow 必须符合现实语义，不能靠荒谬路径或人为陷阱降分

### 1.2 软目标

这部分不追求全绿，反而希望 baseline 掉下来：

- 将 `Qwen2.5-7B-Instruct` 的成功率压到大约 `20%`
- 更准确地说，目标区间是 `15% ~ 25%`
- 失败应主要来自：
  - 长链规划
  - 中间状态记忆
  - 多路径选择
  - 跨模块依赖理解
  - 任务闭环意识不足
- 失败不应主要来自：
  - benchmark 自身错误
  - 页面坏掉
  - 起始状态不合理
  - oracle path 本身走不通

## 2. 当前基线

当前 benchmark 的 correctness 基线已经足够好，可以开始系统性提难。

来自 `/Users/masteryth/Documents/webagent/docs/workflow_dataset_validity_report_v20.md`：

- `total_goals = 5040`
- `solvable_goals = 5040`
- `solvable_ratio = 1.000`
- `all_paths_executable_goals = 5040`
- `all_paths_executable_ratio = 1.000`
- `path_length.mean = 2.7616`
- `path_length.median = 2.0`

来自 `/Users/masteryth/Documents/webagent/docs/workflow_difficulty_audit_v20.md`：

- `shortest_path_len.mean = 2.4901`
- `shortest_path_len.median = 2.0`
- `target_state_size.mean = 2.1647`
- `share_shortest_path_le_2 = 0.619`
- `share_target_size_le_2 = 0.879`
- `share_step_budget_ratio_ge_15 = 0.403`
- `saturation_risk_score_counts = {2: 440, 3: 1530, 4: 2060, 5: 1010}`

来自 `/Users/masteryth/Documents/webagent/rl_memory/reports/workflow_chain_length_audit_v20.json` 的最新 round6/7 后链长审计：

- `active_blueprint_count = 504`
- `short_chain_blueprint_count = 365`
- `short_chain_goal_count = 3650`

当前仍然最需要优先收难度的 theme：

- `social`: `36` 个 short-chain blueprints / `360` 个 short-chain goals
- `career`: `32` / `320`
- `health`: `32` / `320`
- `daily`: `30` / `300`
- `education`: `30` / `300`
- `home`: `30` / `300`
- `security`: `30` / `300`
- `finance`: `29` / `290`
- `composite`: `28` / `280`
- `support`: `28` / `280`
- `travel`: `24` / `240`
- `crisis`: `19` / `190`

当前相对已经较难、应作为难度锚点（anchor themes，难锚点）的 theme：

- `government`
- `newcomer`

它们不是完全不动，但不应作为第一批 bulk hardening 的主战场。

## 3. 我们到底要提高什么难度

这里需要明确几个术语。

- `structural difficulty`：结构难度。指不依赖具体模型、只看 taskflow 本身的难度，例如路径长度、依赖深度、target 大小、多路径差异度。
- `realized difficulty`：实现难度。指模型真实跑出来有多难。
- `hardening`：提难 / 收紧。不是乱加噪音，而是系统性提高结构难度，同时不破坏 realism。
- `shortcut path`：捷径路径。表面上是多步 workflow，实际上存在语义很弱的短路成功路线。
- `cross-model gap`：模型间差距。更强模型应该明显优于更弱模型，否则 benchmark 不是太简单，就是太病态。
- `failure taxonomy`：失败归因。要区分“能力失败”和“benchmark 错误”。

我们要提高的是：

1. 规划深度
2. 依赖性
3. 闭环性
4. 路径分歧强度
5. 对中间状态和共享变量的使用要求

我们不要提高的是：

1. 页面噪音
2. 无意义 distractor
3. 不现实前置条件
4. 纯粹通过卡 step budget 来制造失败

## 4. 难度目标指标

后续 hardening 的目标不只看一个成功率，而是看一组指标一起变化。

### 4.1 结构目标

建议把全量 benchmark 的结构目标收敛到下面这个区间：

- `path_length.mean >= 3.6`
- `shortest_path_len.mean >= 3.5`
- `share_shortest_path_le_2 <= 0.10`
- `target_state_size.mean >= 3.0`
- `share_target_size_le_2 <= 0.40`
- `short_chain_blueprint_count <= 120`
- `short_chain_goal_count <= 1200`

对 `dev / test` 可以更严格一些：

- `shortest_path_len.mean >= 4.0`
- `share_shortest_path_le_2 <= 0.05`
- 至少一半 goal 的最长成功路径达到 `4~6` 步

### 4.2 模型目标

对 baseline 的目标：

- `Qwen2.5-7B-Instruct`: `15% ~ 25%`

对 stronger model 的目标：

- 不要求接近满分
- 但应显著高于 7B baseline
- 建议至少保持 `+15` 到 `+25` 个百分点的 gap

如果未来出现：

- 7B 掉到 `20%`
- 更强模型仍然能到 `40%~60%`

这说明 benchmark 的区分度是健康的。

如果所有模型一起塌到接近 `0%`，那不是提难成功，而是 benchmark 被做病了。

## 5. 提难原则

### 5.1 先加依赖，再加长度

最忌讳的是把一条 2 步路径机械改成 5 步路径，但 5 步之间没有真实依赖。

正确做法是：

- 每新增一步都应改变后续可行空间
- 每一步都应为最终 target 提供必要前置条件
- 至少一部分中间状态应在 instruction / visible constraints / path dependency 中真正可见

### 5.2 先补闭环，再补分支

很多现有 task 之所以容易，不是因为 agent 太强，而是因为 workflow 没有真正闭环。

例如：

- travel 不应停在 booking，而应走到 transfer / check-in / expense report
- support 不应停在 contact support，而应走到 return / warranty / review closure
- health 不应停在 activate plan，而应走到 appointment / refill / claim
- career 不应停在 conference registration，而应走到 receipt archive / calendar / tracking closure

### 5.3 多路径要“强差异”，不是“伪多路径”

两条 path 不能只是：

- 参数不同
- 顺序轻微互换
- alias module 替换

两条 path 应至少在下面某一个维度上显著不同：

- `module_set`
- `key_resource_path`
- `dependency_structure`
- `intermediate_shared_state`

### 5.4 realism 比降分更重要

benchmark 的目标是评估 workflow agent，不是设计陷阱题。

所以不能为了压低成功率而：

- 把售后流程从办银行卡开始
- 把租房流程从 unrelated module 开始
- 把医疗理赔写成没有保险上下文
- 把安全恢复写成毫无设备状态约束

## 6. 主要提难手段

### 6.1 路径延长

主要目标：

- 把大量 `1~2` 步成功路径抬到 `4~6` 步
- 尤其是当前 short-chain theme

但路径延长必须是现实链，而不是 filler step。

### 6.2 target state 扩大

当前 `target_state_size.mean` 只有 `2.1647`，太小。

建议把大量任务改成必须同时满足：

- 核心结果
- 中间手续完成
- 收尾动作完成

目标是让更多任务的 target state 达到 `3~4`

### 6.3 中间状态依赖增强

优先构造下面这类链：

- 第一步生成共享变量
- 第二步消费该变量
- 第三步再把结果带到第四步

也就是更积极地使用：

- `shared_variable_pools`
- `parameter_bindings`

这样 agent 不只是“知道去哪”，还必须“记得自己刚刚做了什么”。

### 6.4 路径 distinctness 强化

对双路径 blueprint，需要系统性检查：

- 两条路径是否真的依赖不同资源
- 是否会导向不同中间状态
- 是否在中间阶段形成不同 affordance

如果不是，就要么：

- 重写成强差异双路径
- 要么删除伪短路路径，只保留更合理的长路径

### 6.5 closure step 标准化

建议在多个 theme 内引入统一的闭环思路：

- `travel`: booking -> transfer -> check-in -> expense/receipt closure
- `support`: arrival/diagnosis -> support contact -> remedy -> review/blacklist closure
- `health`: activation/policy -> appointment -> refill/treatment -> claim
- `career`: registration/submission -> receipt/archive -> calendar/email tracking -> profile/report closure
- `security`: reset request -> reset completion -> 2FA device -> 2FA setup -> privacy/security review
- `home/newcomer`: housing/address proof -> lease/utility -> address update -> residency/permit closure

### 6.6 task-aware shortcut 收紧

correctness 修复后，很多 shared pages 变得对 canonical task 过于顺手，这会降低 realized difficulty。

这里要做的不是“把页面做坏”，而是：

- 减少一步到位入口
- 减少把关键动作直接暴露在 landing page 的情况
- 让用户必须先完成必要上下文，才看到后续 affordance

### 6.7 budget 收紧

这是次要手段，不是首要手段。

只在结构已经加厚之后再做：

- 适度降低 `max_steps`
- 适度降低 `max_module_invocations`

否则很容易把 benchmark 从“难”改成“卡阈值”。

## 7. 分轮推进计划

### 7.1 Round A：先收最饱和的 4 个 theme

优先处理：

- `social`
- `career`
- `health`
- `daily`

原因：

- short-chain 数量高
- 现实链条容易补长
- 风险可控

目标：

- 每个 theme 至少改 `20~30` 个 blueprints
- 将主流 path 从 `2~3` 步提升到 `4~5` 步
- 每个改动后的 blueprint 至少多一个 closure target

建议产物：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/extend_workflow_chains_round8.py`

### 7.2 Round B：处理中等风险但数量很大的 theme

优先处理：

- `education`
- `home`
- `security`
- `finance`
- `composite`

重点：

- 引入更强的 shared-state dependency
- 清理伪多路径
- 提升 target state 大小

建议产物：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/extend_workflow_chains_round9.py`

### 7.3 Round C：继续收 support / travel / crisis

优先处理：

- `support`
- `travel`
- `crisis`

重点：

- 把“入口合理、闭环不足”的任务补成完整 workflow
- 继续减少两跳可解任务

建议产物：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/extend_workflow_chains_round10.py`

### 7.4 Round D：只做选择性 anchor enrichment

只小幅处理：

- `government`
- `newcomer`

原则：

- 它们本来就是较难 theme
- 不做 bulk hardening
- 只补 realism / path distinctness / parameter dependency
- 保留它们作为“已有高难锚点”

## 8. 各 theme 的推荐现实链模板

下面这些不是唯一答案，但可以作为 hardening 的主模板。

### 8.1 support

- `order tracking -> order arrival -> contact support -> return`
- `customer service -> order diagnosis -> logistics fix -> warranty claim`
- `post-purchase remedy -> follow-up -> review / blacklist closure`

### 8.2 travel

- `visa/booking clearance -> booking -> airport transfer -> check-in -> expense report`
- `long-haul bundle -> rebooking -> transfer -> check-in`

### 8.3 health

- `insurance policy / plan activation -> doctor appointment -> prescription refill -> medical claim`
- `coverage verification -> vaccine / clinic visit -> claim / continuity closure`

### 8.4 security

- `password reset request -> reset completion -> 2FA device -> 2FA setup`
- `recovery bundle -> device trust -> privacy settings -> security hardening closure`

### 8.5 career

- `conference registration -> receipt archiving -> calendar aggregation -> email tracking`
- `submission -> deadline sync -> archive / profile update`

### 8.6 home / newcomer

- `find home -> lease registration -> address proof -> utility setup`
- `address proof -> address change -> permit / residency closure`

### 8.7 education

- `course enrollment -> assignment / certification -> library / certificate retrieval`
- `learning path selection -> certification -> download / archive closure`

## 9. 每一轮 hardening 的验收流程

每轮 hardening 完成后，必须按下面顺序验收。

### 9.1 静态正确性回归

运行：

- `analyze_workflow_dataset_validity.py`
- `audit_workflow_goal_quality.py --strict`
- `audit_workflow_batch_realism.py --strict`
- `audit_workflow_chain_lengths.py`

通过标准：

- `solvable_ratio = 1.000`
- `all_paths_executable_ratio = 1.000`
- strict quality audit 通过
- realism audit 无新增 issue

### 9.2 定向 smoke

只跑被修改的 goals：

- 先跑 touched goal smoke
- 再跑按 theme 的 targeted probe

目的：

- 快速确认没有引入结构性坏例

### 9.3 难度校准

结构正确后，再跑 baseline 难度校准：

- `train` 用于快速回归和 failure taxonomy
- `dev/test` 用于看真正的区分度

看的是：

- 成功率是否下降
- 下降是不是来自能力失败而不是 benchmark 错误

### 9.4 failure taxonomy 复盘

每轮都要把失败分成两类：

- benchmark 错误
- agent 能力失败

只有当失败主要落在第二类，hardening 才算成功。

## 10. 停止条件

满足下面条件时，可以认为 benchmark 难度基本达标：

1. 静态 correctness / realism 继续全绿
2. `Qwen2.5-7B-Instruct` 落到 `15% ~ 25%`
3. stronger model 明显高于 7B baseline
4. dev / test 不再被 baseline 轻易打穿
5. 失败主要是规划 / 记忆 / 依赖理解失败，而不是 infra 问题

## 11. 近期执行顺序

当前建议的实际顺序是：

1. 等当前双卡 smoke 跑完，确认 round7 改动仍然没有引入 correctness / infra 回归
2. 基于最新结果，先开始 Round A
3. 优先新增 `/Users/masteryth/Documents/webagent/rl_memory/scripts/extend_workflow_chains_round8.py`
4. Round A 完成后重新生成 batch，并重新跑 validity / quality / realism / chain-length audit
5. 若结构层面通过，再做一轮小规模 baseline probe，看成功率是否开始明显下探
6. 之后进入 Round B 和 Round C

## 12. 一句话原则

后续不是追求 “agent 全绿”，而是追求：

- `benchmark 本身必须全对`
- `baseline 必须明显做不动`
- `更强模型仍然能做得更好`

这三点同时成立，benchmark 才是健康且有论文价值的。
