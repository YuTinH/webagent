# Workflow Benchmark v18 数据集总结

## 1. 数据集定位

这版数据集不再把网页任务视为彼此独立的单题，而是把评测目标提升为：

- 给定一个**高层目标**和一组**可见约束**
- agent 需要自行决定要调用哪些子模块
- agent 需要自行决定模块顺序、替代路径和重规划方式
- evaluator 用隐藏的 oracle 判断最终目标是否达成

核心测试能力不再只是单题执行，而是：

- 高层目标分解
- 多模块组合规划
- 依赖感知执行
- 同目标下的多路径完成能力


## 2. 设计原则

### 2.1 高层目标驱动

agent 可见的是：

- instruction
- initial world state
- visible constraints
- target state

agent **看不到**：

- gold 子任务分解
- success paths
- hidden oracle

因此这版 benchmark 测的是 workflow composition，而不是 oracle-guided execution。


### 2.2 多路径完成

数据集要求大量样本满足：

- 同一个 target state
- 可以通过两条或以上**语义上不同**的模块组合完成

这里的“不同”不是简单换参数，也不是只多塞一个冗余模块，而是要求在以下维度里至少有实质差异：

- module set
- key resource path
- dependency structure
- intermediate shared state


### 2.3 模块化表示

当前数据集采用三层结构：

- core workflow module
  - 抽象模块语义，只描述 `requires / effects / constraints / domains / alternatives`
- binding
  - 抽象模块如何落到具体 atomic task
- invocation
  - 每个样本中的具体实例化版本，带参数和值

这样做的目的是把：

- 规划语义
- 页面执行
- 参数实例化

这三层分开，避免 schema 混乱。


### 2.4 共享状态词表

整套 benchmark 使用统一的 shared predicate vocabulary 来描述：

- 前置条件
- 后置效果
- 初始状态
- 目标状态

这一点非常关键，因为它保证了 workflow graph 在规模化扩展时仍然是闭合的，不会出现大量语义相同但命名漂移的状态。


## 3. 当前版本规模

当前正式版本为 **v18**。

### 3.1 主题数

共 `14` 个主题：

- `career`
- `composite`
- `crisis`
- `daily`
- `education`
- `finance`
- `government`
- `health`
- `home`
- `newcomer`
- `security`
- `social`
- `support`
- `travel`


### 3.2 模块层规模

- abstract modules: `108`
- bindings: `112`
- shared predicates: `149`


### 3.3 blueprint 层规模

- blueprints: `504`
- 每个主题：`36` 个 blueprints

其中：

- 前一阶段先构建了一批高质量、可人工审阅的核心 blueprints
- 后一阶段为了把训练规模推到实验可用量级，又增加了一批 **train-only expansion variants**
- 这些扩展变体只进入 `train`，不会扰动 `dev/test` 的评测分布


### 3.4 实例层规模

当前正式实验批次：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v18`

实例数：

- `train = 4760`
- `dev = 140`
- `test = 140`
- `total = 5040`


## 4. Split 设计

当前 split 的单位是 **blueprint_id**，而不是实例。

这意味着：

- 同一个 blueprint 展开的所有实例必须留在同一个 split
- 不允许 train/dev/test 只通过“换参数”共享同一 blueprint

这样做的目的，是防止 benchmark 退化成：

- 训练时见过同构模板
- 测试时只是换了数字、用户名、设备名

当前 `v18` 的 split 结果为：

- train blueprints: `476`
- dev blueprints: `14`
- test blueprints: `14`

其中 dev/test 保持稳定且紧凑，训练集通过额外 blueprint 扩容。


## 5. 质量控制

这版数据集不是“先生成再人工看”，而是有明确的硬门槛。

当前启用的关键质量规则包括：

- `multi_path_ratio >= 0.5`
- `subset-like multi-path` 禁止
- `initial state overlaps target state` 禁止
- multi-path 必须具有真正不同的 required module sets
- blueprint-level split leakage 禁止

当前 `v18` 的质量结果：

### train

- total goals: `4760`
- multi-path goals: `4750`
- multi-path ratio: `0.9978991596638656`
- subset-like multi-path goals: `0`
- initial-target-overlap goals: `0`
- hard fail reasons: `[]`

### dev

- total goals: `140`
- multi-path goals: `140`
- multi-path ratio: `1.0`
- subset-like multi-path goals: `0`
- initial-target-overlap goals: `0`
- hard fail reasons: `[]`

### test

- total goals: `140`
- multi-path goals: `140`
- multi-path ratio: `1.0`
- subset-like multi-path goals: `0`
- initial-target-overlap goals: `0`
- hard fail reasons: `[]`


## 5.5 运行链路原型

除了数据集本身，现在也已经补了一条最小可用的 workflow 运行原型：

- runner：
  - `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_episode.py`
- evaluator：
  - `/Users/masteryth/Documents/webagent/rl_memory/scripts/evaluate_workflow_episode.py`

这条链路当前已经能做：

1. 读取一条 `workflow_goal_instance`
2. 读取对应 `workflow_oracle`
3. 选择一条 reference path
4. 把 `module` 解析成具体 `binding`
5. 再实例化成一个 atomic subtask
6. 产出 episode 级 execution trace 和 evaluation

也就是说，我们现在不仅有 workflow 数据，还已经有了一条最小可用的 episode 运行与判分链路。


## 6. 与旧版 benchmark 的核心差异

相较于旧版更偏原子题执行的 benchmark，这版数据集的核心升级点在于：

- 从 atomic tasks 升级到 high-level workflow goals
- 从固定 chain 升级到 hidden multi-path decomposition
- 从页面题目升级到状态驱动的 workflow composition
- 从 instance-level split 升级到 blueprint-level split
- 保留参数变化带来的连锁状态变化，而不是把样本做死

因此，新的 benchmark 更适合回答下面这类问题：

- 单题做得好，是否真的意味着 workflow 也做得好？
- agent 是否能够在多种可行路径中自行选择合适的子模块组合？
- agent 是否能够在隐藏依赖和可替代路径下完成高层目标？


## 7. 当前版本的使用建议

如果要开始跑正式实验，建议直接使用：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v18`

如果需要同步到服务器，建议使用完整同步包：

- `/Users/masteryth/Documents/webagent/releases/webagent_full_task_sync_bundle_v18_20260407`

原因是这份同步包不仅包含 workflow 层文件，也包含已经清洗过的完整 `tasks/` 目录，适合服务器尚未同步早期子任务修正的情况。


## 8. 代表性样例

下面给几组可以直接拿去汇报的例子。

### 8.1 新生安顿类：同一目标，不同住房后续路径

Blueprint：

- `BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL`

目标状态：

- `housing_finance_prepared`
- `mobile_service_active`

两条成功路径：

1. 路径 A
- `MODULE_FIND_HOME`
- `MODULE_LEASE_CONTRACT_REGISTRATION`
- `MODULE_MOBILE_PLAN_SIGNUP`

2. 路径 B
- `MODULE_FIND_HOME`
- `MODULE_LEASE_MANAGEMENT_REVIEW`
- `MODULE_MOBILE_PLAN_SIGNUP`

这个例子体现的是：

- 两条路径都从“先解决住房”开始
- 但中间可以通过“合同登记”或“租约管理复核”两种不同模块来完成同一个高层目标
- 这不是换参数，而是真正不同的中间模块组合

一个实际生成样本：

- goal id: `WFG-NEWCOMER-0171`
- instruction:
  - `Finish the newcomer workflow with housing finance prepared and mobile service active.`

其中实例化参数还会落到具体值，例如：

- `MODULE_FIND_HOME`
  - `propertyId = PROP-101`
  - `leaseTerm = 6`
- `MODULE_MOBILE_PLAN_SIGNUP`
  - `plan = unlimited`
  - `user_name = Test User`

也就是说，workflow 层是抽象组合，但实例层仍然保留具体参数和后续状态影响。


### 8.2 支持/售后类：同一售后目标，两条不同补救路径

Blueprint：

- `BP_SUPPORT_REMEDY_SUPPORT_DUAL`

一个更合理的具体实例：

- goal id: `WFG-SUPPORT-0021`

初始状态：

- `shop_order_delivered`

目标状态：

- `support_contacted`
- `warranty_claim_submitted`

两条成功路径：

1. 路径 A
- `MODULE_CONTACT_SUPPORT`
- `MODULE_WARRANTY_CLAIM`

2. 路径 B
- `MODULE_LOGISTICS_FIX`
- `MODULE_WARRANTY_CLAIM`

这个例子体现的是：

- 问题订单已经存在，不需要再从“开户-下单”开始 bootstrap
- 一条偏“客服升级后走保修”
- 一条偏“先做物流修复，再走保修索赔”
- 最终都能到达同一个高层补救目标

这类样本比简单 chain 更强，因为它要求 agent 在多个可行售后策略中选路。


### 8.3 安全类：单模块快捷路径 vs 多模块加固路径

Blueprint：

- `BP_SECURITY_SURFACE_HARDEN_DUAL`

目标状态：

- `access_surface_reviewed`
- `security_hardening_completed`

两条成功路径：

1. 路径 A
- `MODULE_PASSWORD_MANAGER`

2. 路径 B
- `MODULE_2FA_SETUP`
- `MODULE_PRIVACY_SETTINGS`
- `MODULE_SECURITY_ROTATION`

这个例子体现的是：

- 同一安全目标既可以通过一个“高内聚模块”快速完成
- 也可以通过多个细粒度模块逐步完成
- 这种设计能够区分：
  - 会不会调用单个高价值模块
  - 会不会自行组合多个低层模块实现同一目标

一个实际生成样本：

- goal id: `WFG-SECURITY-0181`
- instruction:
  - `Finish the security workflow with the access surface reviewed and hardening completed.`

实例化时也会带具体参数，例如：

- `MODULE_PASSWORD_MANAGER`
  - `site = Overleaf`
  - `username = paper.drafts@example.com`
- `MODULE_SECURITY_ROTATION`
  - `providers = [mail, cloud, dev]`


### 8.4 旅行类：显式组合路径 vs 单模块闭合路径

Blueprint：

- `BP_TRAVEL_BOOKING_CLEARANCE_DUAL`

目标状态：

- `travel_booking_confirmed`
- `mobility_clearance_verified`

两条成功路径：

1. 路径 A
- `MODULE_BOOK_FLIGHT`
- `MODULE_VISA_REQUIREMENTS`

2. 路径 B
- `MODULE_LONG_HAUL_TRIP`

这个例子体现的是：

- 一条路径要求 agent 显式完成“订票 + 清关/签证检查”的组合
- 另一条路径由一个更强的旅行模块一次性闭合多个状态
- 这使得 benchmark 不只测“模块拼接”，也测“是否会优先调用高价值复合模块”

一个实际生成样本：

- goal id: `WFG-TRAVEL-0181`
- instruction:
  - `Finish the travel workflow with booking confirmed and mobility clearance verified.`

其中实例化参数是具体的，比如：

- `MODULE_BOOK_FLIGHT`
  - `departure = 北京`
  - `destination = 上海`
  - `depart_date = 2025-12-31`
- `MODULE_VISA_REQUIREMENTS`
  - `destination_country = France`
  - `passport_country = China`
- `MODULE_LONG_HAUL_TRIP`
  - `destination = Japan`


### 8.5 复合任务类：跨主题模块组合

Blueprint：

- `BP_COMPOSITE_PAYMENT_VISIBILITY_DUAL`

目标状态：

- `payment_stack_prepared`
- `delivery_visibility_confirmed`

两条成功路径：

1. 路径 A
- `MODULE_BANK_OPENING`
- `MODULE_SHOPPING`
- `MODULE_COMPLEX_AUTOPAY`
- `MODULE_ORDER_ARRIVAL`

2. 路径 B
- `MODULE_BANK_OPENING`
- `MODULE_TRANSFER_FUNDS`
- `MODULE_CUSTOMER_SERVICE`

这个例子非常适合拿去汇报，因为它能直接说明：

- 新 benchmark 已经不再受旧的 `A/B/C...` 任务类边界限制
- 一个高层目标可以横跨：
  - 金融
  - 消费/订单
  - 客服
  - 支付

也就是说，新的 workflow 数据集允许真正的跨类组合，而不是只在单一旧 task family 里做链式执行。


## 9. 当前结论

到 `v18` 为止，这版 workflow benchmark 已经达到一个可以直接进入实验的状态：

- 主题覆盖完整
- blueprint 数量达到 `500+`
- 实例规模达到 `5000+`
- 质量门槛已经硬化
- dev/test 没有因为扩容而被污染

所以当前最合理的下一步，不是继续无上限扩容，而是基于 `workflow_split_batch_v18` 开始正式方法实验，并在实验反馈基础上再决定是否继续做更大规模的后续版本。
