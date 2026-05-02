# Workflow Benchmark 难度基线审计（2026-04-17）

## 1. 当前结论

当前 benchmark 的 correctness / infra 已基本收口，下一阶段的核心问题不再是“逻辑有没有错”，而是“结构上是不是太容易”。

已有运行结果说明，`Qwen2.5-7B-Instruct` 在当前 clean benchmark 上已经接近饱和：

- `dev full strict`: `140/140`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_dev_full_v48_strict/results/dev_summary.json`
- `test full strict`: `140/140`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_test_full_v05_strict/results/test_summary.json`
- `train module-cover probe`: `42/42`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_train_probe_v02r_allmods_strict/results/train_summary.json`
- `train stratified sample`: `196/196`
  - `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_qwen25_7b_train_probe_v05_196_strict/results/train_summary.json`

这不能直接推出“整个 benchmark 没意义”，但可以明确说明：

- 当前版本的 benchmark 在 clean 之后，**对这类 7B planner+agent 配置已经明显偏饱和**。
- 下一步必须转向 **difficulty audit / difficulty calibration**，否则论文里很难证明 benchmark 仍有区分度。

## 2. 审计输入

结构难度分析脚本：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/analyze_workflow_difficulty.py`

自动输出：

- `/Users/masteryth/Documents/webagent/docs/workflow_difficulty_audit_v20.json`
- `/Users/masteryth/Documents/webagent/docs/workflow_difficulty_audit_v20.md`

审计对象：

- `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20`
- `/Users/masteryth/Documents/webagent/tasks/workflow_generation_blueprints.json`

## 3. 结构难度基线

全量 `v20` 的结构统计如下：

- blueprints: `504`
- goals: `5040`
- blueprint 平均 path 数: `2.002`
- blueprint path 平均 step 长度: `2.44`
- goal 最短成功路径平均长度: `2.2937`
- goal 最短成功路径中位数: `2`
- goal 平均成功路径数: `2.002`
- goal 平均 target state 大小: `2.0317`
- goal 平均 visible constraints 数: `2.8651`
- goal 平均 counterfactual axes 数: `4.0238`
- goal 平均 `max_steps`: `31.9544`
- goal 平均 `max_module_invocations`: `3.3532`
- `max_steps / shortest_path_len` 平均比值: `15.2496`
- `max_module_invocations - shortest_path_len` 平均 slack: `1.0595`

直接解释就是：

- 绝大多数 goal 的真正成功链很短。
- target state 通常只需要满足 `2` 个左右条件。
- 分支数几乎总是 `2`，而且很多时候不是强语义分叉，只是轻度变化。
- step budget 对最短成功路径普遍给得很松。

## 4. 饱和风险指标

为了判断“为什么这个 benchmark 会被做穿”，我定义了几类简单但直接的结构风险指标：

- `shortest_path_le_2`
- `target_size_le_2`
- `success_paths_le_2`
- `step_budget_ratio_ge_15`
- `module_budget_slack_le_1`

全量统计：

- 最短路径 `<= 2` 的 goal 占比：`0.706`
- target state 大小 `<= 2` 的 goal 占比：`0.970`
- 成功路径数 `<= 2` 的 goal 占比：`0.996`
- `max_steps / shortest_path_len >= 15` 的 goal 占比：`0.504`
- module budget slack `<= 1` 的 goal 占比：`0.732`

`saturation_risk_score` 分布：

- `score=2`: `190`
- `score=3`: `1200`
- `score=4`: `2530`
- `score=5`: `1120`

也就是说，`5040` 个 goal 里有 `3650` 个 goal 同时命中 `4` 个及以上的“易饱和”结构特征。

## 5. 最直接的问题：单模块和双模块 goal 太多

进一步拆开看：

- 单模块最短成功路径 goal 数：`470`
- 单模块占比：`0.0933`
- 最短成功路径 `<= 2` 的占比：`0.7063`

也就是说：

- 将近 `9.3%` 的 goal，本质上是一跳可解。
- 超过 `70%` 的 goal，本质上两跳内可解。

这已经足以解释为什么 clean 后的 benchmark 会被当前 agent 做穿。

## 6. 哪些 theme 最容易饱和

按 theme 看，最值得优先收难度的是这几类：

- `support`
  - shortest path mean: `1.9722`
  - step ratio mean: `16.7778`
- `crisis`
  - shortest path mean: `1.9444`
  - step ratio mean: `16.3056`
- `social`
  - shortest path mean: `1.8333`
  - step ratio mean: `16.912`
- `health`
  - shortest path mean: `1.8611`
  - step ratio mean: `16.5556`
- `security`
  - shortest path mean: `1.8611`
  - step ratio mean: `18.4676`
- `daily`
  - shortest path mean: `2.0`
  - step ratio mean: `16.6667`
- `travel`
  - shortest path mean: `2.0278`
  - step ratio mean: `16.3981`

相反，当前仍然相对像“难锚点”的 theme 是：

- `government`
  - shortest path mean: `3.4167`
  - share_short_path: `0.083`
- `newcomer`
  - shortest path mean: `3.4444`
  - share_short_path: `0.083`

这说明后续 hardening 不应该一刀切，而应该优先从已经明显饱和的 theme 收起。

## 7. 哪些 module 最值得先改

以“最短成功路径只有 1 个 module”为标准，当前最常见的单模块入口是：

- `MODULE_PASSWORD_MANAGER`: `80`
- `MODULE_GIFT_POOLING`: `70`
- `MODULE_LONG_HAUL_TRIP`: `70`
- `MODULE_COUPON_MANAGEMENT`: `60`
- `MODULE_HEALTH_PLAN_ACTIVATION`: `60`
- `MODULE_FIRMWARE_UPDATE`: `60`
- `MODULE_CONFERENCE_REGISTRATION`: `20`
- `MODULE_LOST_CARD_FREEZE`: `20`
- `MODULE_EVENT_TICKETS`: `10`
- `MODULE_MOVIE_TICKETS`: `10`
- `MODULE_CUSTOMER_SERVICE`: `10`
- `MODULE_PRIVACY_SETTINGS`: `10`

这批 module 就是第一批最值得 harden 的对象，因为它们一改，会带动大量 goal 难度一起上升。

## 8. 当前 benchmark 为什么会“看起来不难”

现在的结果不是单一原因，而是两层叠加：

第一层：结构本身偏短。

- 路径短
- target 小
- 分支少
- budget 松

第二层：shared page correctness 修复之后，很多页面已经变得对 canonical task 非常顺手。

这是正确性修复带来的副作用，不是 bug，但确实会降低 realized difficulty。例如这批 shared page 在修 correctness 时都增强了 task-aware affordance：

- `/Users/masteryth/Documents/webagent/sites/trip.local/flights.html`
- `/Users/masteryth/Documents/webagent/sites/work.local/email-tracking.html`
- `/Users/masteryth/Documents/webagent/sites/work.local/email-detail.html`
- `/Users/masteryth/Documents/webagent/sites/food.local/restaurant.html`
- `/Users/masteryth/Documents/webagent/sites/market.local/list-item.html`
- `/Users/masteryth/Documents/webagent/sites/housing.local/index.html`
- `/Users/masteryth/Documents/webagent/sites/gov.local/renew.html`

这些修改在 correctness 阶段是必要的；但如果下一阶段不做 difficulty calibration，就会让 benchmark 的“真实执行难度”低于它的 nominal workflow complexity。

## 9. 下一步 hardening 原则

后续收难度，我建议遵守下面几条，不然很容易把 benchmark 改坏：

1. 先改单模块和双模块 goal，不先碰最复杂 theme。
2. 先提高“依赖性”，不要只机械拉长路径。
3. 先把 target state 从 `1~2` 提高到 `3~4`，而不是先无脑加噪音。
4. 先降低 task-aware shortcut，再考虑增加 distractor。
5. 保留 `government` / `newcomer` 作为较难锚点，避免所有 theme 都被统一改成一个样子。

## 10. 建议的第一批 tightening 方案

优先级建议如下：

### 第一批：直接处理单模块热点

优先重写这些 module 的 canonical workflow，使其最短路径不再是一跳完成：

- `MODULE_PASSWORD_MANAGER`
- `MODULE_GIFT_POOLING`
- `MODULE_LONG_HAUL_TRIP`
- `MODULE_COUPON_MANAGEMENT`
- `MODULE_HEALTH_PLAN_ACTIVATION`
- `MODULE_FIRMWARE_UPDATE`

目标：

- 把这批 module 的最短成功路径从 `1` 提高到 `2~3`
- target state 从 `1~2` 提高到 `3`
- 尽量用现实依赖，而不是人造步骤

### 第二批：收 step budget

当前全局平均 `step_ratio = 15.2496` 偏松。

建议先把最饱和 theme 的 `max_steps / shortest_path_len` 收到大约 `8~12` 区间，而不是统一一刀切。

### 第三批：提高分支的“语义差异”

当前虽然平均 path 数接近 `2`，但很多不是强分叉。

后续应该让 multi-path 真正代表：

- 不同模块组合
- 不同依赖顺序
- 不同现实策略

而不是表面上两条 path，实际上只差一个参数。

## 11. 建议的执行顺序

1. 先基于上面的单模块热点，挑 `6` 个 module 做第一轮 hardening。
2. 每改一批后，继续用当前 clean benchmark 跑：
   - `dev full`
   - `test full`
   - `train 196-goal stratified run`
3. 观察 `Qwen2.5-7B-Instruct` 是否从接近满分回落到更有区分度的区间。
4. 再决定是否需要第二轮 global hardening。

## 12. 一句话结论

当前 benchmark 已经基本 clean，但它的结构难度分布明显偏短、偏小、偏松；下一阶段最应该做的不是继续修 logic/infra，而是系统性提高单模块和双模块 goal 的依赖复杂度，尤其优先处理 `support / crisis / social / health / security / daily / travel` 这些已经明显饱和的 theme。
