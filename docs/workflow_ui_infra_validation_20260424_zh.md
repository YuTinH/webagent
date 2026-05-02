# Workflow UI Infra Validation

## 目标

在已经确认 `benchmark logic / taskflow / oracle / evaluator` 没有结构性错误之后，继续验证:

- UI infra 是否有问题
- selector 支持层是否有问题
- 页面实现与 task spec / oracle 是否对齐

换句话说，这一轮要回答的是:

`在规划路径固定的情况下，页面执行链路本身是否还会系统性出错？`

## 验证方法

我们对一批高风险失败实例做 `reference + agent` targeted audit:

- `reference`: 固定 module path，去掉 planner 变量
- `agent`: 真正执行页面动作，保留真实的 UI 执行链路

这样如果仍然失败，问题就更可能落在:

- executor / action parser
- selector 支持层
- 页面实现与 task spec / oracle 不一致
- 或者 agent 在原子动作层面依旧不稳定

## 采样范围

本轮样本共 `32` 个 goal，覆盖 `8` 个主题:

- `health`
- `home`
- `finance`
- `crisis`
- `government`
- `daily`
- `support`
- `travel`

选样时优先覆盖这些可疑 failure category:

- `element_not_found_or_timeout`
- `selector_parse_error`
- `criteria_or_checkpoint_failed`
- `executor_runtime_error`

## 已确认的问题

### 1. Executor / Selector 支持层问题

这类问题已经被明确验证，不是单纯 agent 太弱。

代表 case:

- `WFG-SUPPORT-0007`
- `WFG-DAILY-0011`
- `WFG-DAILY-0013`

#### `WFG-SUPPORT-0007`

参考路径固定后，agent 在 `MODULE_ORDER_ARRIVAL` 上输出:

- `TRACK_ORDER(.order-item:has(div.item-name:contains("Wireless Mouse")))`

executor 返回:

- `Error: unknown_action_format`

这说明这里的问题不是 taskflow 不可解，而是:

- 当前 executor 不支持 `TRACK_ORDER(...)` 这一动作格式

#### `WFG-DAILY-0011` / `WFG-DAILY-0013`

agent 输出:

- `CLICK(#orders-list .order-card .order-header .order-id:contains("O-93902"))`

normalized 后变成:

- `CLICK(...:has-text("O-93902"))`

executor 返回:

- `invalid_action_heuristic[unsupported_selector_token]`

这说明这里存在 selector 支持层问题:

- 当前执行器不支持这类 selector token/heuristic

结论:

`UI infra / executor / selector support 确实存在真实问题。`

而且这类问题在参考路径固定后依旧稳定复现，因此不能再归因到 planner。

### 2. 页面状态 / 绑定 task spec 不一致

这类问题也已经被明确验证。

代表 case:

- `WFG-HEALTH-0001`
- `WFG-HEALTH-0005`
- `WFG-HEALTH-0007`
- `WFG-HEALTH-0009`

在 `WFG-HEALTH-0001` 中，同一个保险购买动作出现了两套不同的 evaluator:

- `WFG-HEALTH-0001-M1/task_spec.json`
  期待:
  - `plan_name == '尊享门诊计划'`
  - `provider == 'NorthLife'`

- `WFG-HEALTH-0001-R2/task_spec.json`
  期待:
  - `plan_name == 'Premium Plus Plan'`
  - `provider == 'Prime Shield'`

而页面点击 `#purchase-plan-premium-plus-btn` 后，实际写回状态与 `R2` 一致，`R2` 可以通过，`M1` 失败。

这说明至少存在一种不一致:

- module binding 的 evaluator 与页面真实写回状态不一致

它不一定是“页面 HTML 坏了”，但至少说明:

- `页面状态语义` 和 `部分 binding/oracle` 没对齐

结论:

`页面实现 / task binding / evaluator 对齐层面存在真实问题。`

## 已确认不是 UI infra 的问题

并不是所有可疑失败都来自页面。

代表 case:

- `WFG-TRAVEL-0027`

这个 case 中:

- `MODULE_BOOK_FLIGHT` 可以直接通过
- 但 `MODULE_FLIGHT_REBOOKING` 反复执行
  `SELECT(#rebook-policy, Flexible change policy)`
- 最终因为 `repeat_action_loop` 失败

这更像:

- agent 原子执行策略卡住
- 而不是页面本身坏掉

结论:

`可疑失败里同时混有 infra/page 问题和纯 agent 执行问题，不能一概而论。`

## 当前阶段结论

截至目前，已经可以明确说:

### 可以确认存在的问题

- `executor / action parser` 问题
- `selector heuristic` 支持层问题
- `页面状态写回` 与 `部分 binding/evaluator` 不一致的问题

### 还需要继续补看的部分

- `element_not_found_or_timeout` 高占比主题
  - `home`
  - `finance`
  - `government`
  - `crisis`

这些主题更适合继续判断:

- 是真的页面 selector 不稳定
- 还是 agent 在页面上没完成正确交互

## 结论一句话版本

`是的，UI infra / selector / 页面实现对齐层面确实存在问题；但这些问题不是全部失败的来源，另一部分失败仍然是 agent 自己的原子执行问题。`

## 相关运行目录

- targeted audit 结果目录:
  `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/ui_infra_audit_20260424/reference_agent`

- 样本集:
  `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/ui_infra_audit_20260424/suspect_goals.json`

- 样本 goal id:
  `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/ui_infra_audit_20260424/suspect_goal_ids.txt`
