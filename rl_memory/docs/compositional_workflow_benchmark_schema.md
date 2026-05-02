# Compositional Workflow Benchmark 设计草案

## 1. 为什么要改 benchmark

当前 benchmark 的强项是：

- 跨任务持久状态
- 任务流执行
- counterfactual 与 failure taxonomy

但导师指出的核心问题是成立的：

- 如果模型把每个 atomic task 都学得很好
- 而任务流只是这些 atomic task 的固定串联
- 那么 workflow 分数很可能只是 atomic competence 的外推

这会削弱 benchmark 的新颖性。

真正值得补的能力不是：

- 会不会把既定子任务顺序执行完

而是：

- 在只给高层目标时，agent 能不能自己选择、拼接、替换、重排子任务模块

所以新的 benchmark 目标不应再是：

- fixed task chain execution

而应变成：

- goal-conditioned workflow composition

## 2. 新 benchmark 的核心定义

我们把现有 benchmark 拆成两层：

### 2.1 Level 1: Atomic Task Library

保留现在的 atomic tasks 作为基础执行单元。

每个 atomic task 继续负责：

- 一个局部网页交互目标
- 明确的 success criteria
- 对环境状态的真实写入

### 2.2 Level 2: Compositional Workflow Goals

新增一层高层目标实例。

agent 在评测时只看到：

- 一个高层自然语言目标
- 一组预算/时限/偏好/风险约束
- 当前初始世界状态

agent 看不到：

- 标准子任务列表
- 标准顺序
- 隐藏依赖图
- evaluator 的 gold decomposition

因此 agent 必须自己决定：

- 需要哪些模块
- 先做哪个
- 哪些模块是替代关系
- 哪些模块只在特定 world state 下才需要
- 中途失败后是否要换路径

## 3. 设计原则

### 3.1 高层目标对 agent 可见，模块图对 evaluator 可见

这是最关键的一条。

如果把子任务列表直接给 agent，那么 benchmark 只是在测：

- long-horizon execution

而不是：

- workflow decomposition and composition

### 3.2 多条正确路径

同一个高层目标不应该只有一条唯一金路径。

例如“在预算内完成搬家后安顿”可以有多种可接受组合：

- 找房 -> 签约 -> 开通水电 -> 设置 autopay
- 找房 -> 签约 -> 先只开电 -> 延后 broadband

只要满足目标和约束，就应视为成功。

### 3.3 模块依赖显式化

每个 atomic task 要补成 workflow module，至少要有：

- `requires`
- `produces`
- `consumes`
- `risk`
- `estimated_steps`

这样 evaluator 才能判断：

- agent 是不是选对了模块
- 顺序是不是合理
- 是否走了无效绕路

### 3.4 重规划必须计分

如果某条路径失败，benchmark 不应简单判死。

更强的信号是：

- agent 有没有发现失败
- 有没有切换备选模块
- 最后是否仍然满足目标

这部分是组合 benchmark 和普通长任务 benchmark 的核心区别。

### 3.5 workflow 层只新增一层，不推翻现有 task 体系

现有 `task_spec.json`、站点、handler、oracle trace 都可以保留。

新增工作主要是：

- 给 atomic tasks 补模块元数据
- 新增 workflow goal 样本
- 新增 hidden oracle graph

这样工程成本可控。

## 4. 三个数据对象

新的 benchmark 建议引入三个对象。

### 4.1 Workflow Module

这是 atomic task 的 workflow 化包装。

建议一条 module 对应一个现有 atomic task。

它描述的不是“怎么点”，而是“这个 task 在 workflow 里起什么作用”。

例如：

```json
{
  "module_id": "HOUSING_FIND_LEASE",
  "atomic_task_id": "A1-2026-01-001",
  "name": "Find and accept a lease",
  "requires": {
    "all_of": [],
    "any_of": [],
    "none_of": ["lease_active"]
  },
  "effects": {
    "adds": ["lease_active", "address_known"],
    "writes_memory": ["housing.lease.last.id", "housing.lease.last.term"]
  },
  "constraints": {
    "estimated_steps": 6,
    "budget_delta": -1200,
    "risk": "medium"
  }
}
```

### 4.2 Workflow Goal

这是对 agent 公开的高层目标实例。

它包含：

- 高层 instruction
- 约束条件
- 初始世界状态
- 规范化目标状态

其中规范化目标状态可以存在数据里，但不一定要原样暴露给 agent。

例如：

```json
{
  "goal_id": "WF-NEWCOMER-001",
  "instruction": "You moved to a new city. Set up a stable living situation within budget and make sure utilities and mailing access work this week.",
  "visible_constraints": {
    "budget_limit": 1800,
    "deadline_days": 7,
    "must_avoid": ["late_fee", "duplicate_subscription"]
  },
  "target_state": [
    "lease_active",
    "utility_electricity_active",
    "mailing_address_current"
  ]
}
```

### 4.3 Workflow Oracle

这是 evaluator 专用的隐藏图结构。

它描述：

- 哪些 modules 可用于达成目标
- 哪些是必要依赖
- 哪些是替代分支
- 哪些失败后有 recovery path
- 如何给 partial credit

agent 不应直接看到这部分。

## 5. Atomic Task 到 Workflow Module 的映射

推荐不要直接重写 `task_spec.json`。

更稳妥的做法是新增一层 sidecar metadata：

- 一个 atomic task 继续保留原始 `goal / success_criteria / oracle_trace`
- workflow 层拆成两个对象：
  - 核心 `workflow module`
  - sidecar `workflow module binding`

这里建议：

- 一个 `workflow module` 表达一个抽象 workflow capability
- 一个 module 可以挂多个 atomic task bindings
- 这样才能把“多个具体 task，其实都在做同一种事”收敛成同一个 planning object

核心 `workflow module` 最小字段如下：

- `module_id`
- `family`
- `name`
- `parameters`
- `requires.all_of`
- `requires.any_of`
- `requires.none_of`
- `effects.adds`
- `effects.removes`
- `constraints.estimated_steps`
- `constraints.budget_delta`
- `constraints.time_delta`
- `constraints.risk`
- `domains`
- `alternatives`

`workflow module binding` 最小字段如下：

- `binding_id`
- `module_id`
- `backing_task_id`
- `task_dir`
- `description_template`
- `default_parameter_values`
- `observable_templates`
- `writes_memory`
- `writes_env`
- `seed_example`

其中：

- `description_template` / `observable_templates` 是可复用模板
- `default_parameter_values` 只是当前 task 库导出的 seed defaults
- `seed_example` 只是一个参考实例，不应被当成 benchmark 固定值
- 多条 binding 可以共享同一个 `module_id`
- `binding_id` 才是具体执行绑定的唯一标识

如果要保留你们旧 benchmark 里“参数变化引起后续蝴蝶效应”的特性，还需要再引入第三层：

- `workflow module invocation`

它属于某个具体 workflow goal 样本，负责记录：

- 本次真正选用的 `parameter_values`
- 本次实例化后的 `description`
- 本次实例化后的 `expected_observables`
- 以及可选的 `instantiated_effects / instantiated_constraints`

这样拆的好处是：

- `workflow module` 只表达规划语义
- `binding` 只负责模块如何落到当前 task 库
- `invocation` 才表达每个 benchmark 样本里的动态参数变化
- 之后即使 atomic task 库替换，module schema 也不用跟着重写

建议 `requires / effects` 优先使用离散谓词，而不是一上来就用完整 DSL。

原因很简单：

- generator 更容易做图搜索
- evaluator 更容易判断依赖闭合
- 之后再把谓词映射到 DSL 即可

例如：

- `lease_active`
- `address_known`
- `utility_electricity_active`
- `parking_permit_approved`
- `autopay_bound_to_current_card`

## 6. Workflow Goal 样本格式

一个 workflow goal 至少应包含下面这些字段：

- `goal_id`
- `theme`
- `difficulty`
- `instruction`
- `visible_constraints`
- `initial_world_state`
- `target_state`
- `counterfactual_axes`
- `max_steps`
- `max_module_invocations`

其中：

- `instruction` 是给 agent 的自然语言
- `visible_constraints` 是 agent 可见约束
- `initial_world_state` 是结构化初始条件
- `target_state` 是规范化最终状态
- `counterfactual_axes` 用于生成 paired evaluation

### 6.1 例子：新城市安顿

```json
{
  "goal_id": "WF-NEWCOMER-001",
  "theme": "newcomer",
  "difficulty": 3,
  "instruction": "You moved into a new city this week. Make sure you have a valid place to live, basic utilities working, and your mailing address updated. Stay within the stated budget.",
  "visible_constraints": {
    "budget_limit": 1800,
    "deadline_days": 7,
    "must_avoid": ["late_fee", "duplicate_service_contract"]
  },
  "initial_world_state": {
    "lease_active": false,
    "utility_electricity_active": false,
    "mailing_address_current": false,
    "checking_balance": 2600
  },
  "target_state": [
    "lease_active",
    "utility_electricity_active",
    "mailing_address_current"
  ],
  "max_steps": 80,
  "max_module_invocations": 6
}
```

这个目标下，agent 不会被明确告知要做：

- `A1-find-home`
- `A3-utility-setup`
- `H1-address-change`

但 evaluator 可以知道这是一组可能的 gold decomposition。

## 7. Workflow Oracle 图结构

建议把 hidden oracle 设计成一个 AND-OR graph。

### 7.1 为什么不是单路径 gold trace

如果只有一条 gold path，问题会退化成：

- 轨迹模仿

而不是：

- workflow composition

AND-OR graph 能表达：

- 必须同时满足的模块
- 备选方案
- 条件分支
- recovery 分支

### 7.1.1 Dataset-Level Quality Requirement

workflow benchmark 不要求所有样本都是 multi-path。

但为了确保 benchmark 真正在测组合规划，而不是大号 task chain，建议把下面这条当成硬性数据质量要求：

- 至少 `50%` 的 workflow instances 必须是 `multi_path`

这里的 `multi_path` 不是指：

- 只是参数不同
- 只是模块顺序轻微交换
- 只是同模块 alias

只有在至少满足下面之一时，才能算作 `semantically distinct path`：

- 模块集合不同
- 关键资源路径不同
- 依赖结构不同
- 中间共享状态不同

建议每个 oracle 显式标注：

- `composition.composition_type`
- `composition.num_semantically_distinct_paths`
- `composition.distinctness_rule`

建议把这组要求集中维护在一份机器可读的质量配置里：

- `/Users/masteryth/Documents/webagent/tasks/workflow_quality_requirements.json`

并要求后续每次新增或重写 workflow instances 后，必须跑：

```bash
python3 /Users/masteryth/Documents/webagent/rl_memory/scripts/audit_workflow_goal_quality.py --strict
```

只有在下面两类条件同时满足时，数据批次才算通过：

- dataset-level `multi_path_ratio >= min_multi_path_ratio`
- goal-level 没有 composition 违规项

也就是说，后续 instance generation 不是“先生成再人工挑”，而是“生成后必须通过统一 quality gate”。

另外，`quality gate` 只能保证结构合法，不能替代语义抽样检查。

因此后续每次完成 `blueprint` 扩充后，固定执行下面这套流程：

1. 重生成 split batch
2. 运行 strict audits
3. 运行抽样检查脚本：

```bash
python3 /Users/masteryth/Documents/webagent/rl_memory/scripts/generate_workflow_human_review.py \
  --batch-root /Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/<batch_name>
```

默认检查：

- `dev`
- `test`
- 每个 theme 每个 split 抽 `1` 个代表样本

输出位置默认在：

- `/Users/masteryth/Documents/webagent/.task_sync_meta/<batch_name>_human_review.json`
- `/Users/masteryth/Documents/webagent/.task_sync_meta/<batch_name>_human_review.md`

这个步骤的目的不是替代严格审计，而是专门抓下面这类问题：

- instruction wording 和 path 语义不匹配
- target state 虽然合法但不够自然
- path 虽然不是 subset-like，但仍然显得牵强
- 某个 theme 出现明显不合语境的前缀模块

### 7.2 结构示意

```text
Goal: stable_living_ready
  AND:
    - lease_active
    - utility_ready
    - mailing_ready

lease_active
  OR:
    - HOUSING_FIND_LEASE
    - HOUSING_TRANSFER_LEASE

utility_ready
  OR:
    - UTIL_SETUP_ELECTRICITY + UTIL_SETUP_WATER
    - UTIL_BUNDLE_PLAN

mailing_ready
  OR:
    - GOV_ADDRESS_CHANGE
    - BANK_BILLING_ADDRESS_UPDATE + POSTAL_FORWARDING
```

这样同一个 goal 就可以支持多条正确解。

### 7.3 Invocation-Aware Oracle

oracle 不应只保存模块名。

为了保留旧 benchmark 里“参数变化引起后续蝴蝶效应”的特性，建议 hidden oracle 额外保存：

- `reference_invocations`
- 每条 `success_path` 对应的 `reference_invocation_ids`

也就是说：

- `module_nodes` 负责描述抽象可行图
- `reference_invocations` 负责给出当前 workflow 样本里的具体参数实例

例如同一个模块：

- `MODULE_2FA_DEVICE`

在不同 workflow 样本里可以分别实例化成：

- `new_device_name = Pixel 9 Pro`
- `new_device_name = Galaxy Fold 7`

这时 downstream observable、部分状态写入、甚至某些约束都可以随 invocation 改变。

## 8. Scalable Instance Generation

如果目标是最终做出成百上千级别的 workflow samples，就不应继续手工维护 `workflow_goal_instances/*.json`。

建议固定采用下面这条分层生成链：

1. `workflow_module_library.json`
2. `workflow_module_bindings.json`
3. `workflow_generation_blueprints.json`
4. `generate_workflow_goal_batch.py`
5. `audit_workflow_goal_quality.py --strict`

对应文件：

- `/Users/masteryth/Documents/webagent/tasks/workflow_generation_blueprints.json`
- `/Users/masteryth/Documents/webagent/schemas/workflow_generation_blueprint_library.json`
- `/Users/masteryth/Documents/webagent/rl_memory/scripts/generate_workflow_goal_batch.py`

### 8.1 为什么需要 Blueprint 层

如果直接从 module library 随机拼接：

- 很容易产生脏依赖
- 很难稳定控制 multi-path 占比
- 很难保证语义上不同路径真的不同

blueprint 层的作用是：

- 先人工定义“哪类 workflow 目标值得大量扩展”
- 再把参数扰动、路径替代、counterfactual 统一模板化
- 在必要时显式固定 `binding_id`，把抽象 module 绑定到某个特定 atomic 页面版本

这样扩大到数百上千样本时，扩的是：

- 合法实例数

而不是：

- 垃圾组合数

### 8.2 批量生成协议

示例命令：

```bash
python3 /Users/masteryth/Documents/webagent/rl_memory/scripts/generate_workflow_goal_batch.py \
  --batch-name batch_v1 \
  --count-per-blueprint 50 \
  --seed 20260404
```

这会在：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_batches/batch_v1`

下生成：

- `workflow_goal_instances/`
- `workflow_oracles/`
- `manifest.json`

每个 path step 默认只需要写 `module_id`。

当同一个 `module_id` 下存在多个语义差异明显的 bindings 时，step 可以额外写：

- `binding_id`
- 或 `binding_task_id`

这两个字段是可选的 pin。只有在需要固定具体落地页面版本时才用，避免 blueprint 被过度绑死在当前 task 库上。

例如当前 10 个 blueprints、每个扩 50 个实例时，会直接得到 500 个样本。

### 8.3 强制质量验收

批量生成后，必须立刻跑：

```bash
python3 /Users/masteryth/Documents/webagent/rl_memory/scripts/audit_workflow_goal_quality.py \
  --oracle-dir /Users/masteryth/Documents/webagent/tasks/generated_workflow_batches/batch_v1/workflow_oracles \
  --requirements /Users/masteryth/Documents/webagent/tasks/workflow_quality_requirements.json \
  --output-json /Users/masteryth/Documents/webagent/tasks/generated_workflow_batches/batch_v1/workflow_goal_quality_audit.json \
  --output-md /Users/masteryth/Documents/webagent/tasks/generated_workflow_batches/batch_v1/workflow_goal_quality_audit.md \
  --strict
```

只有在 audit 通过时，这批样本才允许进入正式 benchmark pool。

也就是说，后续 benchmark 扩展的工作流应该固定为：

- 先改 blueprint
- 再批量生成
- 再严格审计
- 最后才纳入正式数据集

## 8. 评分设计

workflow 层不建议只看 `pass/fail`。

建议至少保留四个分量。

### 8.1 Final Goal Success

最终目标状态是否满足。

这仍然是主分。

### 8.2 Composition Efficiency

agent 是否调用了必要模块，是否做了太多无关模块。

例如：

- 目标只需要 `3` 个模块
- agent 做了 `7` 个，还引入无关副作用

这应被扣分。

### 8.3 Dependency Correctness

agent 是否满足必要前置条件。

例如：

- 没拿到 permit 就去 contest ticket
- 没有 current card 就重绑 autopay

这类不是简单“执行失败”，而是 workflow reasoning 错误。

### 8.4 Recovery / Replanning

agent 在模块失败后是否能换路径继续完成目标。

例如：

- parking permit 被拒后，改走 resubmit path
- 某支付方式失效后，切换到替代支付路径

这是新 benchmark 很值得测的一项。

### 8.5 Counterfactual Stability

只改一个初始状态键后：

- agent 的模块选择是否随之合理变化
- 还是仍然机械走旧路径

这会比单次成功率更能说明 agent 是否真的在做规划。

## 9. 生成 pipeline

为了避免全部手写，建议 workflow benchmark 生成器分四步。

### 9.1 给现有 atomic tasks 打模块标签

先补 sidecar metadata：

- `requires`
- `effects`
- `constraints`

### 9.2 从目标状态采样 workflow goal

例如随机采样：

- `target_state = {lease_active, utility_ready, address_current}`
- 再随机采样约束：
  - `budget_limit`
  - `deadline_days`
  - `risk_preference`

### 9.3 在 module graph 上求所有可行解

对 evaluator 而言，提前求出：

- 最小可行 module sets
- recovery path
- 替代路径

这就是 hidden oracle 的来源。

### 9.4 实例化环境

把：

- 初始 world state
- 页面数据
- handler 状态
- sampled entities

对齐到同一份 workflow goal 上。

## 10. 和当前 benchmark 的关系

这不是替换，而是升级。

### 10.1 当前 benchmark 保留的部分

- atomic task 执行器
- 站点环境
- state persistence
- oracle trace
- checkpoint scoring
- counterfactual infrastructure

### 10.2 新增的部分

- workflow module metadata
- workflow goal dataset
- hidden composition graph
- composition-aware evaluator

所以你们完全可以写成：

- Level 1: Atomic Persistent Web Tasks
- Level 2: Compositional Workflow Goals

这比直接说“我们又做了一个新 benchmark”更稳。

## 11. 最小 prototype 建议

不要一上来覆盖全部主题。

建议先做 `3` 个主题，每个主题 `5-10` 个 workflow goals。

### 11.1 Newcomer

适合做：

- 找房
- utility setup
- address update
- parking/permit
- autopay

优势是依赖最天然。

### 11.2 Daily

适合做：

- 账单
- 购物
- 售后
- 预算协调

优势是资源约束明显。

### 11.3 Crisis

适合做：

- 丢卡
- 重绑支付
- 延误赔付
- permit rejection recovery

优势是 recovery path 更强。

## 12. 论文里可以怎么讲 novelty

建议核心 claim 不要写成：

- 我们有更多任务

而要写成：

- Atomic task mastery does not imply workflow composition ability.

然后强调你们测的是：

- implicit decomposition
- module selection
- dependency-aware ordering
- alternative path selection
- recovery and replanning
- counterfactual sensitivity

这就和普通 single-task / fixed-chain benchmark 拉开了。

## 13. 建议的近期落地顺序

### Phase 1

给 `20-30` 个最常用 atomic tasks 补 module metadata。

### Phase 2

手工写 `15-20` 个 workflow goals，用来验证 protocol。

### Phase 3

实现 hidden oracle graph evaluator。

### Phase 4

跑一个 sanity study，验证下面这个命题是否成立：

- strong atomic agent != strong workflow-composition agent

如果这个 gap 能跑出来，这条 benchmark 线就立住了。

## 14. 一句话结论

新的 benchmark 不应该再把“子任务链”直接给 agent。

更合理的设计是：

- 保留现有 atomic tasks 作为模块库
- 新增高层 workflow goals
- 让 agent 自己做模块选择、顺序规划、替代路径选择和失败后重规划

这样 benchmark 的新意才足够强，也更能支撑 `SkillBank` 或后续 workflow-planning 方法。

## 15. 质量门槛与切分

workflow dataset 的质量控制，不能只靠人工抽查。

现在建议把下面三层都做成硬门槛：

- predicate vocabulary audit
- workflow goal quality audit
- blueprint-level split audit

### 15.1 为什么 split 必须按 blueprint 切

如果 train/dev/test 只是从同一个 blueprint 里换参数采样，例如：

- 用户名换一个
- 金额换一个
- 设备名换一个

那本质上还是同一类组合结构，评测会被高估。

因此当前规则是：

- split unit = `blueprint_id`
- 同一个 `blueprint_id` 展开的所有 instances 必须留在同一个 split

### 15.2 当前 split policy

当前实现见：

- `/Users/masteryth/Documents/webagent/tasks/workflow_blueprint_splits.json`

以及：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/generate_workflow_blueprint_splits.py`
- `/Users/masteryth/Documents/webagent/rl_memory/scripts/audit_workflow_blueprint_splits.py`

当前分配规则：

- 1 个 blueprint 的 theme：先留在 `train`
- 2 个 blueprint 的 theme：分到 `train + dev`
- 3 个 blueprint 的 theme：分到 `train + dev + test`
- 4 个及以上 blueprint 的 theme：至少 `2 train + 1 dev + 1 test`

这样做的目的不是追求完美均衡，而是先防止结构泄漏。

### 15.3 当前推荐的生成与审计顺序

1. 更新 task/module/binding 基础库
2. 运行：
   - `generate_workflow_module_library.py`
3. 运行：
   - `audit_workflow_predicate_vocabulary.py --strict`
4. 更新/扩展 blueprints
5. 运行：
   - `generate_workflow_blueprint_splits.py`
6. 运行：
   - `audit_workflow_blueprint_splits.py --strict`
7. 再批量生成 workflow goals
8. 最后运行：
   - `audit_workflow_goal_quality.py --strict`

顺序不要反过来。先扩样本、再补 audit，代价会越来越大。
