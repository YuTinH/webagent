# Workflow Benchmark 周进展汇报（2026-04-14）

## 1. 本周工作的总体目标

本周的核心目标不是单纯把模型分数做高，而是先把 benchmark 本身修正到一个可信状态：

1. 任务流要合理，不能出现“语义不相关但被错误选中”的模块链。
2. benchmark 和 agent 的交互链路要清楚，知道输入是什么、输出是什么、每一层组件在做什么。
3. benchmark 自身的逻辑、任务资产和基础设施（infra）问题要尽量清干净。

这里有一个原则需要特别强调：

- 我们**没有放宽 benchmark 的全局成功判定标准**。
- 我们做的是修 benchmark 的 correctness（正确性）和 infra（基础设施）问题，而不是把失败算成成功。
- 只有在 benchmark 足够 clean 之后，才会进入下一阶段的 difficulty audit（难度审计）。

---

## 2. 本周最重要的结论

### 2.1 benchmark 可信度相比周初有明显提升

周初我们看到的一个代表性严格结果只有：

- `40/140 = 28.57%`

这个结果当时不能直接解释成“模型能力弱”，因为里面混了很多 benchmark 自身的问题，比如：

- shared runtime 污染
- shared page 记错 task id
- task spec、oracle、页面行为互相矛盾
- 页面参数指向了环境里根本不存在的目标

本周经过系统修复后，历史最好 full strict 结果已经达到：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v43_strict/results/dev_summary.json`
- `131/140 = 93.57%`

这说明 benchmark 的主要问题已经从“大面积系统性错误”收缩到了“少量具体 residual（残留问题）”。

### 2.2 当前最新全量回归还在继续

当前正在跑的是：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v46_strict`

截至我写这份周报时，`v46` 的 partial（阶段性结果）是：

- `completed_goals = 82`
- `final_success_count = 81`
- 在已完成部分里，当前成功率约 `98.78%`

而且从已完成的主题看，下面这些主题已经全绿：

- `career`
- `crisis`
- `education`
- `support`
- `daily`
- `travel`
- `composite`

`newcomer` 目前是 `9/10`，只剩一个明确 residual 在收尾。

### 2.3 本周仍然没有开始 difficulty audit

原因很直接：

- benchmark 还没有完全 clean 到可以开始谈“难度是不是过低”
- 当前仍然优先修 correctness / infra / task-definition

这不是保守，而是为了避免把“脏 benchmark 上的低分”误当成 benchmark 有难度。

---

## 3. 第一部分：把任务流合理化

这一部分解决的是：高层 workflow goal 到底应该分解成哪些 module（模块），以及这些模块之间的顺序和依赖是不是合理。

### 3.1 为什么这件事重要

我们的 benchmark 不是普通的单网页任务集，而是 workflow benchmark。

也就是说：

- 用户给 agent 的是一个高层目标
- agent 需要自己决定下一步该调用哪个模块
- benchmark 背后有 hidden oracle（隐藏工作流真值）约束哪些模块链是合法的

如果模块链本身不合理，就会出现一种假失败：

- 模型不是不会做
- 而是 benchmark 把它引到了不该走的路径上

### 3.2 本周做了什么

#### 3.2.1 收紧 planner 的候选模块集合

以前 workflow planner 会出现一个问题：

- 语义相近的模块会被错误地当成候选
- 但这些模块实际上不属于该 blueprint（任务蓝图）的合法路径

例如：

- 外卖售后、物流修复、退货、客服联系，这些本来应该留在 `support` 主题内部
- 但 earlier versions 里可能会被漂到语义相近却完全不该走的金融或其他模块上

本周修复后：

- planner 现在会受 oracle 允许路径、模块依赖、可达状态约束
- 这使得“外卖售后不需要从银行卡创建开始”这种明显不合理的路径被排除了

换句话说，本周我们做的是：

- 把 workflow decomposition（工作流分解）从“语义上差不多”改成“oracle 合法且目标可达”

#### 3.2.2 修正 shared page 的任务绑定

我们确认过一个很关键的问题：

- 同一个页面可能被多个任务模块复用
- 但页面前端以前只写死了一个 task id
- 这样 workflow 在运行时即使动作做对了，也可能把状态写到错误任务上

这会导致：

- 页面上看起来完成了
- 但 benchmark 读不到正确的状态更新
- 最终被判失败

本周修复后：

- 页面不再用 workflow runtime 的合成 id
- 而是使用真实的 `binding_task_id`

这一步直接提升了我们对 workflow 合法性的信心，因为现在“动作属于哪个任务”这件事终于对齐了。

#### 3.2.3 修正 workflow 资产里的非法参数

本周最典型的例子是 `newcomer` 主题。

我们最终定位到：

- `MODULE_FIND_HOME` 在 workflow oracle 里用的是 `propertyId = PROP-101`
- 但当前 housing 环境里实际存在、并且应该用于这条链路的房源是 `PROP-EXT-10`

结果就是：

- agent 在列表页只能不停切换排序
- 永远进不到目标房源详情页
- 最终表现成 `repeat_action_loop`

这看起来像模型在乱点，但根因其实是：

- benchmark 资产把任务指向了一个当前环境中并不存在的目标

这周我已经把这条链统一改正：

- `/Users/masteryth/Documents/webagent/tasks/workflow_module_bindings.json`
- `/Users/masteryth/Documents/webagent/tasks/workflow_generation_blueprints.json`
- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/.../workflow_oracles/*.json`

统一从 `PROP-101` 改为真实存在的 `PROP-EXT-10`。

#### 3.2.4 用 targeted repair 验证修复是否命中

为了避免“改了很多但不知道哪一刀有用”，本周我没有只跑 full run，而是做了定点 repair run。

最重要的两个例子：

- `support` residual 定向回归后已经 `5/5`
- `newcomer` residual 定向回归后已经 `4/4`

对应路径：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v44_support_newcomer_strict/results/dev_summary.json`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_repair_v45_newcomer_strict/results/dev_summary.json`

这说明本周不是在“堆 patch 刷分”，而是在一条一条地把任务流资产收回到合法、可达、可解释的状态。

---

## 4. 第二部分：详细分析 benchmark 和 agent 的交互流程

这部分的工作目标是：把 benchmark 真正拆解成一个清晰的执行链，搞清楚每一步谁在输入、谁在输出、谁在决策、谁在判分。

### 4.1 高层输入是什么

对 agent 来说，输入的不是某个 atomic task（原子任务），而是 workflow-level goal（工作流级目标）。

workflow goal instance 一般包括：

- 自然语言 instruction（任务描述）
- visible constraints（用户可见约束）
- initial world state（初始状态）
- target state（最终要达到的状态）
- max steps / max module invocations（预算上限）

路径在：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/dev/workflow_goal_instances`

### 4.2 隐藏的 oracle 在做什么

agent 看不到 oracle，但 benchmark 在用它定义：

- 哪些模块组合是合法的
- 模块之间的依赖关系
- 哪些 path 是 reference success paths（参考成功路径）
- 最终目标状态是什么
- 非法跳转、冗余模块等该怎么扣分

路径在：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/dev/workflow_oracles`

### 4.3 planner 在做什么

核心文件：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark.py`

planner 的职责是：

- 根据当前 workflow state
- 从 module library 中选出下一步该调用哪个 module

本周在这一层主要修了：

- 候选模块集合约束
- 可达性检查
- blueprint 合法路径过滤

这层如果不对，就会出现：

- agent 被送到不该去的模块
- 后面即使做对动作也不可能成功

### 4.4 原子任务实例化在做什么

核心文件：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_episode.py`

这一层负责把 workflow module 变成一个具体可执行的 atomic task：

- task spec
- oracle trace
- parameter values
- binding task id

本周这里修了几个关键问题：

- 参数实例化污染
- binding task id 保持正确
- runtime task inputs 能真正注入到页面环境里

### 4.5 agent 实际输出什么

核心文件：

- `/Users/masteryth/Documents/webagent/llm_runner.py`

agent 会基于页面 observation 输出动作，例如：

- `CLICK(...)`
- `TYPE(...)`
- `SELECT(...)`
- `DONE()`

从 benchmark 的角度看，这些动作不是直接“完成任务”，而是交给执行器去解释和执行。

### 4.6 browser / executor 层在做什么

核心文件：

- `/Users/masteryth/Documents/webagent/agent/browser_env.py`

这一层负责：

- 打开页面
- 采集 observation
- 执行 DOM 动作
- 处理 select、click、modal、fallback

本周在这一层修的内容非常多，典型包括：

- `TYPE(...)` 误打到 button-like 元素上的兼容处理
- 非标准 select UI 的 fallback
- shared page 的 runtime task input 注入
- 页面 task-aware affordance（任务感知型引导控件）

### 4.7 页面和 handler 在做什么

页面 JS 主要在：

- `/Users/masteryth/Documents/webagent/sites/static/common.js`

业务 handler 在：

- `/Users/masteryth/Documents/webagent/task_handlers/...`

页面动作最后会写到：

- memory
- env state
- 页面业务状态

这一步如果 task id 绑错、handler 写回错、页面 affordance 不够，就会产生大量假失败。

### 4.8 evaluator 是怎么判分的

最后 benchmark 会在两层判分：

1. atomic task 层
- 看 `success_criteria`
- 看 `scoring_checkpoints`

2. workflow 层
- 看 target state 是否达成
- 看 invalid transition 是否发生
- 看 hard constraints 是否违反

输出字段包括：

- `success_type`
- `target_state_coverage`
- `invalid_transition_count`
- `hard_constraint_violations`
- `composite_score`

本周一个重要成果是：

- 我们已经能把失败准确归因到具体层级
- 不再把所有失败都笼统归成“模型能力不够”

---

## 5. 第三部分：优化 benchmark 的内在逻辑和 infra

这是本周工作量最大的一块。

### 5.1 runtime isolation 修复

之前 benchmark 存在 shared runtime 污染问题：

- 前一个 goal 的状态会影响后一个 goal

这会让 full run 结果不再可信。

本周已经统一改成：

- `per_goal runtime isolation`

也就是说：

- 每个 goal 有自己独立的 runtime root
- 每个 goal 的环境、站点、数据库副本互相隔离

这一步的意义非常大，因为它让 full strict run 重新具备了正式统计价值。

### 5.2 authoritative 路径统一

本周还做了一件很基础但很重要的事：

- 把远端 authoritative benchmark 路径统一到：
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent`

之前顶层有很多历史副本，例如：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/sites`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/tasks`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/v1`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent.zip`

这些目录容易制造混淆，也会让同步、运行和定位问题时出现“到底哪份代码在生效”的不确定性。

现在原则已经明确：

- `/webagent` 是唯一权威工作目录

### 5.3 qzcli 使用链路稳定化

本周我们不只是修 benchmark，也修了远端执行 benchmark 的工具链。

当前稳定做法是：

- `qzcli login`
- `qzcli res -u`
- `qzcli exec webagent ...`
- `qzcli sync webagent ...`

并且已经总结出几个关键操作规则：

1. dev machine 名称是：
- `webagent`

2. notebook id 是：
- `7b825dbc-6d73-4347-a944-4cfbd2325d7a`

3. `qzcli sync` 的远端路径必须写相对路径，而不是绝对路径

这条链路稳定下来以后，我们才能高效地：

- 同步 patch
- 起 targeted repair
- 起 full strict
- 查 partial summary
- 读 log 和 trace

### 5.4 task-definition consistency 修复

本周修了很多 task spec / oracle / page 行为互相不一致的问题。

代表性修复包括：

- `/Users/masteryth/Documents/webagent/tasks/B10-coupon-management/task_spec.json`
- `/Users/masteryth/Documents/webagent/tasks/I2-appliance-repair/task_spec.json`
- 多个 `oracle_trace.json`

这类问题如果不修，会出现一种很隐蔽的假失败：

- 页面按一种逻辑执行
- task spec 按另一种逻辑判定
- oracle 又假设第三种流程

最后 benchmark 看起来在“严格评测”，其实是在拿三份互相冲突的真值做比较。

### 5.5 页面 affordance 和 shared page 修复

本周修的代表性页面包括：

- `/Users/masteryth/Documents/webagent/sites/food.local/subscription.html`
- `/Users/masteryth/Documents/webagent/sites/school.local/library.html`
- `/Users/masteryth/Documents/webagent/sites/bank.local/open-account.html`
- `/Users/masteryth/Documents/webagent/sites/social.local/charity.html`
- `/Users/masteryth/Documents/webagent/sites/shop.local/coupons.html`
- `/Users/masteryth/Documents/webagent/sites/shop.local/help.html`
- `/Users/masteryth/Documents/webagent/sites/housing.local/index.html`
- `/Users/masteryth/Documents/webagent/sites/housing.local/property.html`
- `/Users/masteryth/Documents/webagent/sites/housing.local/listings.html`

主要修的是：

- task-aware 默认值
- shared page 的 task id 绑定
- 关键按钮/弹窗/表单的行为语义
- agent 可以稳定识别和点击的 affordance

### 5.6 evaluator / debug logging 清理

之前很多 benchmark log 里混了大量逐条 DSL 判断的 debug 输出，例如：

- `DEBUG: Eval Atom: ...`
- `DEBUG: DSL mem check: ...`
- `DEBUG: AssertionDSL json check: ...`

这些信息排查时有用，但对正常 benchmark 运行不是必须的，而且会把 log 冲得非常难读。

本周已经处理成：

- 默认静默
- 只有显式开调试开关时才打印

这不影响成功判定，只是提高了日志可读性和排障效率。

---

## 6. 本周量化进展

如果把本周的结果变化浓缩成一条线，大致是：

### 周初

- 严格全量结果只有 `40/140 = 28.57%`
- 大量失败并不能解释成 agent 弱
- 更多是 benchmark 的 runtime、page、task-definition、workflow 资产问题

### 周中

- 历史最好 full strict 跑到：
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v43_strict/results/dev_summary.json`
  - `131/140 = 93.57%`

### 当前

- `support` residual 已通过 targeted repair 收掉
- `newcomer` residual 已通过 targeted repair 收掉
- `v46` 还在跑，但在已完成的 `82` 个里：
  - `81` 个成功
  - 当前只显式看到 `1` 个明确 residual

这说明 benchmark 的问题已经从：

- “大面积系统性不可信”

收缩到了：

- “个别页面/执行兼容残留”

这是本周最重要的实质性进展。

---

## 7. 专业术语简明解释

下面这些术语建议在汇报时顺手解释一下，避免显得太“黑箱”。

### workflow
中文可以解释为“工作流”。

含义是：

- 一个高层目标不是一步完成
- 而是要经过多个 atomic modules（原子模块）串起来完成

### module
中文可以解释为“模块”或“可复用原子任务单元”。

例如：

- 开银行卡
- 上传地址证明
- 更新车辆地址
- 联系客服

这些都是 module。

### planner
中文可以解释为“规划器”。

它的作用是：

- 在当前状态下决定下一步该调用哪个模块

### oracle
中文可以解释为“隐藏真值结构”或“隐藏参考工作流”。

它不是直接给 agent 看，而是 benchmark 用它来定义：

- 合法路径
- 依赖关系
- 成功状态
- 非法跳转惩罚

### binding_task_id
中文可以解释为“真实绑定任务 id”。

它的作用是：

- 告诉共享页面：你当前到底在为哪个具体任务服务

如果这个 id 错了，就会出现动作做对了、状态却写错位置的情况。

### per_goal runtime isolation
中文可以解释为“每个 goal 单独隔离运行环境”。

作用是：

- 防止上一个任务污染下一个任务

### targeted repair
中文可以解释为“定向修复验证”。

意思是：

- 不先跑全量
- 而是先挑出残留失败样本
- 只修这几个问题，再小范围验证是否命中

### residual
中文可以解释为“残留问题”。

意思是：

- 大问题已经修掉之后
- 还剩下的一小部分具体失败点

### correctness
中文可以解释为“正确性”。

在这里指的是：

- benchmark 的任务逻辑、资产、路径、状态判定是否真实且自洽

### infra
中文可以解释为“基础设施”。

在这里主要包括：

- runtime
- 执行链路
- 同步工具
- 日志
- 环境隔离

### difficulty audit
中文可以解释为“难度审计”。

含义是：

- 在 benchmark 已经正确之后
- 再检查 benchmark 是否过于容易、是否还能真实拉开 agent 能力差距

这个阶段我们还没有正式开始。

---

## 8. 当前判断

如果用一句话总结本周工作的性质：

- 本周我们做的，不是“为了让 agent 高分去改 benchmark”，而是“先把 benchmark 从不够可信的状态，修到一个基本可信、接近收口的状态”。

也就是说：

1. benchmark 现在比周初可信得多
2. 当前失败开始更像真实 residual，而不是大面积资产错误
3. 这为下一阶段的 difficulty audit 提供了前提

---

## 9. 下周建议

接下来建议分三步走：

1. 先等 `v46` 跑完
- 看全量严格回归里还剩多少真正的 residual

2. 如果还有极少量 correctness/infra 残留
- 继续 targeted repair
- 不直接开 difficulty audit

3. 只有在全量 strict 基本 clean 后
- 再进入 difficulty audit
- 核查 benchmark 是否因为修 correctness 而变得过于容易

---

## 10. 一句话汇报版本

如果要用一句话向导师概括本周工作，可以说：

> 本周我主要不是在调模型，而是在系统性修 benchmark 本身：一方面把 workflow 任务流和模块路径收回到合理、可达的状态，另一方面把 benchmark 和 agent 的交互链、页面绑定、任务资产和运行基础设施梳理清楚。当前 benchmark 的主要问题已经从早期的大面积逻辑/infra 错误收缩到少量具体 residual，严格全量结果也已经从早期的低成功率提升到接近稳定可用的阶段，下一步是在确认 correctness 基本收口之后，再开始做 benchmark 难度审计。
