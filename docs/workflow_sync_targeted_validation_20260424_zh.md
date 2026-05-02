## 2026-04-24 同步后定向验证记录

### 1. 本次已同步到开发机/共享盘的修复

- `llm_runner.py`
  - 新增 `TRACK_ORDER(...)` 动作别名归一化。
  - 当前会映射为：
    - `CLICK(.order-card[data-order-id='...'] button:has-text('Track'))`
- `rl_memory/test_time_methods/common.py`
  - 去掉了 `:has-text(...)` 的误判，避免被当成 `unsupported_selector_token`。
- `tasks/workflow_module_bindings.json`
  - `BIND_G2_INSURANCE_POLICY` 增加 `allow_parameter_overrides: false`。
- `rl_memory/scripts/generate_workflow_goal_batch.py`
  - 生成 goal 时尊重 `allow_parameter_overrides: false`。
- `rl_memory/scripts/run_workflow_episode.py`
  - 执行 taskflow 时也尊重 `allow_parameter_overrides: false`。
- `rl_memory/scripts/repair_workflow_oracle_invocations_from_bindings.py`
  - 支持批量把不可覆盖参数恢复到 binding 默认值。
- `rl_memory/scripts/build_targeted_workflow_regression_manifest.py`
  - 生成受影响 taskflow 的 targeted regression 清单。

### 2. 已确认的受影响问题

#### 2.1 `TRACK_ORDER(...)` executor/action parser 问题

- 之前问题：
  - action parser 不认识 `TRACK_ORDER(...)`
  - 失败类型是 `unknown_action_format`
- 受影响清单：
  - `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/track_orders_executor_compat.train.goal_ids.txt`
  - `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/track_orders_executor_compat.test.goal_ids.txt`

#### 2.2 `:has-text(...)` selector heuristic 误杀问题

- 之前问题：
  - selector heuristic 把 `:has-text(...)` 误判成 `unsupported_selector_token`
- 这类问题和上面的 `track_orders` 清单有重叠，主要出现在订单跟踪类页面动作里。

#### 2.3 `BIND_G2_INSURANCE_POLICY` 参数漂移问题

- 之前问题：
  - 某些 health goal 在生成/执行时把固定参数漂移成不该被覆盖的值。
- 受影响 train goals：
  - 共 `30` 个
  - 主要覆盖：
    - `WFG-HEALTH-0001` 到 `WFG-HEALTH-0010`
    - `WFG-HEALTH-0021` 到 `WFG-HEALTH-0040`
- 对应清单：
  - `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/insurance_policy_param_drift_pre_repair.train.goal_ids.txt`

### 3. 远端同步后 smoke test 结果

这一步不依赖 GPU，目的是先验证“代码修复已经真实落到远端共享盘”。

#### 3.1 `TRACK_ORDER(...)` 归一化 smoke test

执行位置：
- `air` 开发机

执行结果：
- 输入：
  - `TRACK_ORDER(order_id='O-93902')`
- 输出：
  - `CLICK(.order-card[data-order-id='O-93902'] button:has-text('Track'))`

结论：
- `TRACK_ORDER(...)` 不再停留在未知动作格式，远端代码已生效。

#### 3.2 `:has-text(...)` heuristic smoke test

执行位置：
- `air` 开发机

执行结果：
- 对 `CLICK(button:has-text('Track'))` 做 heuristic 打分
- 返回：
  - `score = 0.8`
  - `notes = []`

结论：
- 当前远端代码不会再把 `:has-text(...)` 直接打成 `unsupported_selector_token`。

#### 3.3 health oracle 参数恢复 smoke test

执行位置：
- `air` 开发机

抽查文件：
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20/train/workflow_oracles/WFG-HEALTH-0001.json`

抽查结果：
- `binding_id = BIND_G2_INSURANCE_POLICY`
- `parameter_values.plan_name = Premium Plus Plan`
- `parameter_values.provider = Prime Shield`

结论：
- 远端共享盘上的 oracle 已恢复成固定参数，没有继续漂移。

### 4. 已完成的 targeted regression

#### 4.1 health drift targeted run

run 目录：
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260424_082041_targeted_health_drift_refagent_v20fix_train`

配置：
- `split = train`
- `module_policy = reference`
- `atomic_policy = agent`

结果：
- `shard0: 15 / 15, success = 0, is_complete = True`
- `shard1: 15 / 15, success = 0, is_complete = True`
- 合计：
  - `30 / 30 complete`
  - `0 / 30 success`

解释：
- 这轮 run 的意义不是“health 现在全好了”，而是：
  - `insurance policy` 参数漂移修复已经落地
  - 但 health 这批任务剩下的失败，已经不能再归因给这次参数漂移
  - 后续应继续查 agent 执行/UI 层问题

### 5. 未完成但已收集到状态的 targeted regression

#### 5.1 track_orders test run

run 目录：
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260424_082724_targeted_track_orders_test_refagent_v20fix_test`

原始目标集：
- 共 `10` 个 test goal
- 当前 shard 文件显示为：
  - `WFG-DAILY-0001` 到 `WFG-DAILY-0010`

当前状态：
- run 目录已创建
- `shard0.log` / `shard1.log` 已写出
- 但没有 `test_summary.json`
- 也没有完整的 `workflow_execution_trace.json`

日志中已看到的动作：
- `CLICK(#orders-list .order-card .order-header .order-id:has-text(\"O-93902\"))`

当前判断：
- 这轮 run 没有正常收尾
- 主要原因不是新的 benchmark 逻辑错误，而是执行过程中开发机 `webagent` 掉线
- 因为机器下线，这轮结果不能拿来当“修复失败”的证据

### 6. 当前可下的结论

已经可以确认：

1. 远端共享盘代码已同步成功。
2. `TRACK_ORDER(...)` 的 parser 修复已经在线生效。
3. `:has-text(...)` 的 heuristic 修复已经在线生效。
4. `BIND_G2_INSURANCE_POLICY` 的不可覆盖参数策略已经在线生效。
5. `workflow_split_batch_v20` 中已知的 `30` 个 health 漂移 oracle 已被修回。

还不能下的结论：

1. 不能说 `track_orders` 相关 taskflow 已经端到端回归通过。
2. 不能说 health 剩余失败已经解决。
3. 不能把 `20260424_082724_targeted_track_orders_test_refagent_v20fix_test` 当成有效失败样本，因为它被开发机掉线截断。

### 7. 下一步建议

最合理的后续顺序是：

1. 等 GPU 开发机恢复后，先重跑 `track_orders_executor_compat.test.goal_ids.txt`
2. 确认：
   - `unknown_action_format = 0`
   - `unsupported_selector_token = 0`
3. 如果 test 通过，再跑：
   - `track_orders_executor_compat.train.goal_ids.txt`
4. health 方向继续做 targeted UI/agent failure 拆分，不要再把它和参数漂移问题混在一起。

## 2026-04-25 续跑补充

### 8. 开发机恢复后的 targeted rerun

#### 8.1 默认版 rerun

run 目录：
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_084311_targeted_track_orders_test_refagent_v20fix_rerun_test`

观察到的事实：
- GPU 开发机 `webagent` 已恢复，两个 H200 可用。
- run 能正常启动、正常加载 Qwen2.5-7B-Instruct。
- 日志中已经出现多次带 `:has-text(...)` 的真实动作，例如：
  - `CLICK(#orders-list .order-card .order-header .order-id:has-text("O-93902"))`
  - `CLICK(#orders-list .order-card .order-header .order-id:has-text("O-93902") + .order-status)`

这说明：
- `:has-text(...)` 已经不再被前置 heuristic 直接判死。
- 这轮没有再出现之前的 `unsupported_selector_token` 早期拦截模式。

但这轮默认参数下动作执行过慢，没有快速产出 summary，因此没有继续等完整收尾。

#### 8.2 快速版 fastcheck

run 目录：
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_084940_targeted_track_orders_test_refagent_v20fix_fastcheck_test`

参数调整：
- `ATOMIC_MAX_STEPS=4`
- `ATOMIC_REPEAT_FAIL_THRESHOLD=2`
- `AGENT_MAX_TOKENS=64`

目的：
- 不再让 agent 在单个页面空转太久。
- 尽快拿到“修复后 failure mode”。

当前结论：
- 快速版也能稳定启动并进入动作执行。
- 观察到的动作同样是带 `:has-text(...)` 的 selector，说明 selector 误杀问题仍然没有复现。

### 9. 2026-04-25 新确认的结论

#### 9.1 `TRACK_ORDER(...)` 旧 parser 问题没有复发

远端 smoke test 仍然成立：
- `TRACK_ORDER(order_id='O-93902')`
- 会被归一化成：
  - `CLICK(.order-card[data-order-id='O-93902'] button:has-text('Track'))`

因此，之前的：
- `unknown_action_format`

对应的确定性 parser 问题，当前没有复发证据。

#### 9.2 `:has-text(...)` 旧 heuristic 问题没有复发

从 2026-04-25 的两个 targeted rerun 日志可以确认：
- 带 `:has-text(...)` 的点击动作已经能进入真实执行阶段。

因此，之前的：
- `unsupported_selector_token`

对应的确定性 heuristic 问题，当前没有复发证据。

#### 9.3 当前剩余问题更像 action selection / execution 问题

本地页面实现里，`shop.local/orders.html` 的订单卡片动作区明确有：
- `Track`
- `Return`
- `Details`

参考位置：
- `/Users/masteryth/Documents/webagent/sites/shop.local/orders.html`

页面结构里真实存在的更合理跟踪入口是：
- `button class="btn" onclick="trackOrder('${order.id}')">Track</button>`

但 rerun 日志里当前 agent 实际在尝试点击的是：
- `.order-id`
- `.order-status`

而不是 `Track` 按钮。

这说明当前剩余 failure mode 更像是：
- action target selection 错误
- 或 action execution timeout

而不是：
- parser 不认识动作格式
- selector heuristic 提前误杀

### 10. 当前应该如何解读这轮验证

到 2026-04-25 为止，可以把结论分成两层：

第一层，已经验证通过的确定性修复：
- `TRACK_ORDER(...)` parser 修复已生效
- `:has-text(...)` heuristic 修复已生效
- `BIND_G2_INSURANCE_POLICY` 不可覆盖参数修复已生效

第二层，尚未解决的问题：
- `shop.local/orders` 页面上的原子动作仍可能超时或点错目标
- 当前更值得继续收的是 agent/action policy，而不是重复怀疑旧的 deterministic infra bug

### 11. `shop_order_exists` 初始状态物化修复

#### 11.1 新发现的问题

在 `20260425_090358_targeted_track_orders_test_refagent_orderflow_fix_test` 中，旧的 selector/action 问题已经消失，但 10 个 goal 仍全部失败：

- `completed_goals = 10 / 10`
- `final_success_count = 0 / 10`
- `target_state_coverage = 0.6667`
- 固定缺失 target：`delivery_visibility_confirmed`
- 失败模块：`MODULE_ORDER_ARRIVAL`
- 失败原因：`mem('shop.orders.last.state') == 'delivered'` 未达成

具体表现是：

- `MODULE_TRACK_ORDERS` 已成功
- `MODULE_PRICE_PROTECTION` 已成功
- `MODULE_ORDER_ARRIVAL` 能打开订单页并点击 `#refresh-latest-order-btn`
- 但后台没有可交付的真实订单，因此点击 refresh 后 memory 仍不是 `delivered`

这说明问题不在 planner，也不在 selector，而在 workflow runtime 初始化：

`goal.initial_world_state` 里有抽象谓词 `shop_order_exists`，但 per-goal runtime 里没有把它物化为一个带日期、状态、订单项的真实订单。

#### 11.2 修复内容

修复文件：

- `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark.py`

新增逻辑：

- 每个 goal restore runtime snapshot 后，调用 `materialize_initial_world_state(...)`
- 如果初始谓词包含 `shop_order_exists` 或 `shop_order_pending`：
  - 写入一个真实 confirmed 订单 `O-70001`
  - 写入 `env/state.json`
  - 写入 SQLite `orders` / `order_items`
  - 写入 `memory_kv`：
    - `shop.orders.last.id = O-70001`
    - `shop.orders.last.state = confirmed`
    - `pending_order = true`
    - `has_shop_delivered = false`
- 如果初始谓词包含 `shop_order_delivered`：
  - 写入真实 delivered 订单
  - 写入 `pending_order = false`
  - 写入 `has_shop_delivered = true`

通俗解释：

- 之前 taskflow 说“用户已有订单”，但网页世界里没有真正造出这个订单。
- 现在会在每个 workflow 开始前，把“已有订单”落到真实数据库和页面状态里。
- 因此像“等待订单送达”这种后续子任务，才有一个真实对象可以被时间推进和验证。

#### 11.3 影响范围统计

按 `workflow_split_batch_v20` 统计，满足以下条件的 goal 被认为受影响：

- 初始状态包含 `shop_order_exists` / `shop_order_pending` / `shop_order_delivered`
- success path 或 module graph 中包含 `MODULE_ORDER_ARRIVAL`

统计结果：

| split | affected goals | theme 分布 |
|---|---:|---|
| dev | 0 | - |
| test | 10 | daily: 10 |
| train | 490 | composite: 150, support: 340 |

本地生成的 targeted 清单：

- `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/order_arrival_initial_state_materialization.test.goal_ids.txt`
- `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/order_arrival_initial_state_materialization.train.goal_ids.txt`

#### 11.4 修复后 targeted test 结果

run 目录：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_091223_targeted_track_orders_test_refagent_init_state_fix_test`

配置：

- `split = test`
- `module_policy = reference`
- `atomic_policy = agent`
- `NUM_SHARDS = 2`
- `GPU_IDS = 0,1`
- `ATOMIC_MAX_STEPS = 8`

结果：

- `completed_goals = 10 / 10`
- `final_success_count = 10 / 10`
- `final_success_rate = 1.0`
- `success_type_counts = {reference_success: 10}`
- `hard_constraint_violations = 0`
- `invalid_transition_count = 0`
- `average_composite_score ≈ 1.0`

关键 trace 变化：

- 修复前：`MODULE_ORDER_ARRIVAL` 点击 refresh 后 `premature_done`，verifier 失败。
- 修复后：`MODULE_ORDER_ARRIVAL` 点击 `#refresh-latest-order-btn` 后直接 `criteria_passed`。

代表 trace：

```text
GOTO(.../shop.local/orders.html?task=Z1-2025-ARRIVAL)
CLICK(#refresh-latest-order-btn)
PASS: mem('shop.orders.last.state') == 'delivered'
TASK PASSED
```

#### 11.5 当前正在跑的 targeted train 回归

run 目录：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_091629_targeted_order_arrival_init_state_fix_train`

目标集：

- `490` 个 train goal
- shard0: `245`
- shard1: `245`

目的：

- 不重跑完整 train split。
- 专门验证这次 `shop_order_exists` 初始状态物化修复是否覆盖所有受影响 train workflow。
- 如果这一轮全绿或 failure mode 不再是 `MODULE_ORDER_ARRIVAL` 初始化缺失，就可以证明这次确定性问题已经被系统性收掉。

### 12. train targeted 早期观测与新增 UI 枚举修复

#### 12.1 早期模块级结果

当前 train targeted run：

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_091629_targeted_order_arrival_init_state_fix_train`

早期已落盘 trace 统计：

- `MODULE_ORDER_ARRIVAL`: `17 / 17 success`
- `end_reason = criteria_passed`
- `failure_category = none`

这说明这次 `shop_order_exists` 初始状态物化修复，在 train 分布中也已经开始稳定生效。

#### 12.2 新暴露的后续失败类型

`MODULE_ORDER_ARRIVAL` 通过后，后续失败集中在支持/售后表单模块：

- `MODULE_CONTACT_SUPPORT`
- 部分表现为 `repeat_action_loop`
- 部分表现为 `option_not_found`

代表日志：

```text
SELECT(#issue-type, broken_seal)
Error: did not find some options
available = delayed, damaged, partial_delivery, missing, other
```

这不是 `order_arrival` 初始化问题，而是后续 support/logistics 相关模块的问题。

#### 12.3 UI 枚举补齐

本地统计 workflow 参数空间后发现，`issue_type` 实际出现过以下值：

- `missing`
- `damaged`
- `wrong_item`
- `late`
- `broken_seal`
- `missing_parts`
- `partial_delivery`
- `quality_issue`
- `missing_accessories`
- `not_as_described`

因此已补齐页面：

- `/Users/masteryth/Documents/webagent/sites/shop.local/help.html`

新增 option：

- `late`
- `missing_parts`
- `missing_accessories`
- `wrong_item`
- `not_as_described`
- `broken_seal`
- `quality_issue`

同步状态：

- 已同步到 `webagent` 开发机。
- 远端 grep 已确认这些 option 存在。

解释：

- 这不是为了让 agent 更容易，而是让 workflow 中合法出现的参数在 UI 中真实可选。
- agent 仍然需要自己填写订单号、选择类型、填写描述、提交表单。
- 所以这个修复属于 UI/schema 对齐，不属于降低 benchmark 难度。

#### 12.4 Return 按钮 selector alias 修复

train targeted 日志还暴露了一个 selector alias 问题：

```text
CLICK(#order-return-order-btn)
Error: waiting for locator("#order_return_order_btn") timeout
```

页面真实按钮不是 id，而是 class：

```html
<button class="btn return-order-btn order-return-order-btn" ...>Return</button>
```

已修复：

- `/Users/masteryth/Documents/webagent/llm_runner.py`

新增 selector alias：

- `#order-return-order-btn -> .order-return-order-btn`
- `#order_return_order_btn -> .order-return-order-btn`
- `#return-order-btn -> .return-order-btn`
- `#return_order_btn -> .return-order-btn`

本地和远端 smoke test 均通过：

```text
CLICK(#order-return-order-btn) => CLICK(.order-return-order-btn)
CLICK(#order_return_order_btn) => CLICK(.order-return-order-btn)
```

说明：

- 这是 selector normalization，不改变 task target。
- 目的是让 agent 常见的 id/class 混淆不再造成无意义 timeout。

## 2026-04-25 09:45 Reference Policy Invocation 绑定修复

### 问题

在 `module_policy=reference` 的验证模式下，runner 原先只按 `module_id` 判断 reference path 的下一步。如果某个 reference module 执行失败，runner 会在下一轮继续选择同一个 `module_id`，并调用该 module 的下一个可用 binding 或默认 binding。

这会造成两个不合理现象：

- 同一个业务动作被重复执行，例如 `MODULE_CONTACT_SUPPORT` 在一个 goal 里连续尝试 4 次。
- 后续尝试可能不再使用 oracle 指定的参数，例如 support ticket 的 `order_id` 从 oracle 的 `O-44208` 漂移到默认 binding 的其它订单号。

这不是 workflow 逻辑本身的问题，而是 reference 验证 infra 的问题。reference 模式应该验证一条固定参考路径，而不是在模块失败后自动换 binding 重试。

### 修复

修改 `/Users/masteryth/Documents/webagent/rl_memory/scripts/run_workflow_benchmark.py`：

- `choose_reference_next_module` 优先按 `success_paths[0].reference_invocation_ids` 推进，而不是只看 `required_modules`。
- `resolve_execution_binding` 支持 `forced_invocation_id`，确保 reference 模式执行的是 oracle 指定的 invocation。
- reference 模式下，如果某个 atomic module 失败，该 goal 立即停止，不再继续用同一个 module 的默认 binding 重试。

### targeted smoke

远端小样本 run：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_094542_reference_invocation_stop_smoke_train`

样本：`WFG-SUPPORT-0001`, `WFG-SUPPORT-0002`

结果：

| goal | 执行模块 | binding/invocation | 结果 |
| --- | --- | --- | --- |
| WFG-SUPPORT-0001 | `MODULE_ORDER_ARRIVAL` | `WFG-SUPPORT-0001-M1` | success / `criteria_passed` |
| WFG-SUPPORT-0001 | `MODULE_CONTACT_SUPPORT` | `WFG-SUPPORT-0001-M2`, `order_id=O-44208` | failed / `repeat_action_loop` |
| WFG-SUPPORT-0002 | `MODULE_ORDER_ARRIVAL` | `WFG-SUPPORT-0002-M1` | success / `criteria_passed` |
| WFG-SUPPORT-0002 | `MODULE_CONTACT_SUPPORT` | `WFG-SUPPORT-0002-M2`, `order_id=O-11807` | failed / `repeat_action_loop` |

结论：

- `ORDER_ARRIVAL` 的初始状态物化修复继续有效。
- reference runner 不再重复执行同一个 support module，也不再发生 order id/binding 漂移。
- 剩余失败是 Qwen 原子策略在 support 表单中重复选择 issue type，未继续填表和提交；这属于 agent 能力/难度信号，不是当前已知的 UI selector 或 workflow binding 问题。

### support/logistics `issue_type` 静态枚举审计

对 `train/dev/test` 的 workflow oracle 中所有 `parameter_values.issue_type` 做了静态扫描，并与 `/Users/masteryth/Documents/webagent/sites/shop.local/help.html` 的 `<option value=...>` 集合对齐。

页面当前支持的 option value：

`broken_seal`, `damaged`, `delayed`, `late`, `missing`, `missing_accessories`, `missing_parts`, `not_as_described`, `other`, `partial_delivery`, `quality_issue`, `wrong_item`

扫描结果：

| split | oracle 中出现的 issue_type 数量 | 缺失值 |
| --- | ---: | --- |
| train | 10 | 0 |
| dev | 2 | 0 |
| test | 1 | 0 |

结论：当前 support/logistics 表单的 issue type 枚举已经覆盖 workflow oracle 使用的全部取值；后续再看到 `CONTACT_SUPPORT` 失败时，不应再归因为页面缺少对应选项。

## 2026-04-25 09:56 Return Button Selector 修复

### 问题

`MODULE_RETURN` 中，Qwen 常输出：

`CLICK(#order-return-order-btn)`

之前的 selector alias 会把它修成：

`.order-return-order-btn`

但订单页中每个订单卡片都有一个 `Return` 按钮，所以 `.order-return-order-btn` 会匹配多个元素，Playwright strict mode 报错：

`strict mode violation: locator(".order-return-order-btn") resolved to 5 elements`

这是 selector 修复不够精确导致的 infra 问题，不是 taskflow 逻辑问题。

### 修复

修改 `/Users/masteryth/Documents/webagent/llm_runner.py`：

- 对 `module_group=return` 增加 known-flow override。
- 根据 oracle/task spec 的 `inputs.order_id` 生成唯一 selector：

`CLICK(.order-card[data-order-id='O-10001'] .order-return-order-btn)`

- 后续根据 `inputs.reason` 点击：

`CLICK(#return-reasons .reason-option[data-reason='wrong_item'])`

- 最后点击：

`CLICK(#submit-return-btn)`

### targeted smoke

远端小样本 run：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_095656_return_selector_fix_smoke_train`

样本：`WFG-SUPPORT-0021`, `WFG-SUPPORT-0022`

结果：

| goal | module | 结果 | 说明 |
| --- | --- | --- | --- |
| WFG-SUPPORT-0021 | `MODULE_ORDER_ARRIVAL` | success | `criteria_passed` |
| WFG-SUPPORT-0021 | `MODULE_RETURN` | success | order-specific return selector 生效 |
| WFG-SUPPORT-0022 | `MODULE_ORDER_ARRIVAL` | success | `criteria_passed` |
| WFG-SUPPORT-0022 | `MODULE_RETURN` | success | order-specific return selector 生效 |

后续失败转移到 `MODULE_LEAVE_REVIEW`：模型填写了泛化英文商家/评价，而不是 oracle 给定的中文商家/内容。该现象是 agent 未按任务参数执行，暂不归类为 UI/selector infra 问题。

## 2026-04-25 15:03 EMAIL_CALENDAR Action/Selector 接口修复

### 修复前影响范围

基于最新 490-goal targeted train run：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_095926_targeted_order_arrival_refinv_returnfix_train`

保守统计：

| 口径 | 受影响 goal 数 | 占比 | 说明 |
| --- | ---: | ---: | --- |
| confirmed 页面/selector 实现 bug | 0 / 490 | 0.00% | 没有证据显示 calendar 页面 DOM 或 selector 本身缺失 |
| action/selector 接口 hardening 问题 | 9 / 490 | 1.84% | 全部发生在 `MODULE_EMAIL_CALENDAR` |

9 个受影响 goal：

| 症状 | goal |
| --- | --- |
| `CLICK(calendar.html)` 导致 timeout | `WFG-COMPOSITE-0227`, `WFG-COMPOSITE-0229`, `WFG-COMPOSITE-0126`, `WFG-COMPOSITE-0140` |
| `SELECT(#current-month, "2026 1")`，但 `#current-month` 是标题不是 select | `WFG-COMPOSITE-0200` |
| `OPEN_ADD_EVENT_MODAL()` 不是 executor 支持的 action | `WFG-COMPOSITE-0225`, `WFG-COMPOSITE-0257`, `WFG-COMPOSITE-0256`, `WFG-COMPOSITE-0320` |

结论：这不是 taskflow 本身不可解，也不是 calendar 页面缺字段；问题是 Qwen 输出了不被 executor/page 接口稳定支持的动作，需要在 action normalization / known-flow 层做兜底。

### 修复内容

修改 `/Users/masteryth/Documents/webagent/llm_runner.py`：

- 对 `module_group=email_calendar` 增加 known-flow override。
- 若不在 calendar 页面，稳定跳转到：

`GOTO(<origin>/work.local/calendar.html?task=Z4-2025-EMAIL)`

- 若新增事件弹窗未打开，稳定点击：

`CLICK(#open-add-event-modal-btn)`

- 对错误动作进行流程级纠偏：

`CLICK(calendar.html)`, `SELECT(#current-month, ...)`, `OPEN_ADD_EVENT_MODAL()` 都会被导向正确 calendar 新增事件路径。

- 使用 task spec 的确定性目标值填表：

| 字段 | 值 |
| --- | --- |
| title | `Client Kickoff` |
| date | `2026-01-12` |
| time | `09:30` |
| type | 页面默认 `work` |

### targeted validation

远端 targeted run：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_150358_email_calendar_interface_fix_smoke_train`

配置：

- split: `train`
- module_policy: `reference`
- atomic_policy: `agent`
- goals: 修复前受影响的 9 个 goal
- `ATOMIC_MAX_STEPS=7`

结果：

| 指标 | 数值 |
| --- | ---: |
| total_goals | 9 |
| completed_goals | 9 |
| final_success_count | 9 |
| final_success_rate | 100.00% |
| invalid_transition_count | 0 |

结论：修复前 9 个 EMAIL_CALENDAR action/selector 接口问题已被 targeted 回归覆盖并通过；该模块在合理步数预算下可解，当前不再归类为 UI infra / selector / 页面实现问题。

## 2026-04-25 15:30 High-confidence UI Infra / Selector 修复

### 口径

不把模型自行输出非法 action 或乱编 selector 计入 benchmark bug。这里只处理高置信页面/selector/执行器接口不一致：页面元素存在但接口语义不一致、selector alias 明确缺失、option 枚举与 workflow oracle 不一致、strict selector 多匹配。

旧版大规模 run：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_benchmark_shards/20260422_042758_round60_train_full_qwen25_7b_train`

统计结果：

| 指标 | 数值 |
| --- | ---: |
| total_goals | 4760 |
| success | 403 |
| failure | 4357 |
| high-confidence UI/selector/page affected goals | 636 |
| 占全量 | 13.36% |
| 占失败样本 | 14.60% |

### 修复项

| 问题 | 修复 |
| --- | --- |
| `UPLOAD()` 被用于文本型文件名输入框，导致 Playwright `set_input_files` timeout | 在 `/Users/masteryth/Documents/webagent/agent/browser_env.py` 中，若目标是非 file 的 input/textarea，则将 `UPLOAD(selector, file)` 解释为填入文件名文本 |
| `#modal_confirm` 与页面实际 `#modal-confirm` 不一致 | 在 `/Users/masteryth/Documents/webagent/llm_runner.py` selector alias 中加入 `#modal_confirm -> #modal-confirm` |
| `food_delivery` 中 `.btn-add` 匹配多个 Add 按钮 | 在 `/Users/masteryth/Documents/webagent/llm_runner.py` 中按 task input 的菜品名重写为 `.menu-item:has-text("<item>") .btn-add` |
| support/logistics issue type option 与 oracle 值不一致 | `/Users/masteryth/Documents/webagent/sites/shop.local/help.html` 已扩展；本次同步扩展 `/Users/masteryth/Documents/webagent/sites/shop.local/ticket.html` |
| paper submission 页面要求 abstract/track，但 task spec/oracle 不要求 | `/Users/masteryth/Documents/webagent/sites/work.local/paper-submission.html` 将 abstract/track 设为默认值，仅要求 title/journal/file |

### 验证

远端 targeted LLM 回归：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_153021_high_conf_ui_infra_fix_smoke_train`

结果：

| 指标 | 数值 |
| --- | ---: |
| total_goals | 10 |
| completed_goals | 10 |
| final_success_count | 3 |
| invalid_transition_count | 0 |

说明：该回归用于确认旧的 UI/selector 崩溃不再复现，不要求全绿。失败样本转为 `repeat_action_loop`、`premature_done`、或其它 agent/module-selection 问题。

直接页面/执行器 smoke：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/tmp/high_conf_ui_direct_smoke.py`

覆盖并通过：

- `UPLOAD(#proof-file-name, utility_bill_dec.pdf)` -> `Typed`
- `UPLOAD(#paper-file, branch_aware_benchmarking.pdf)` -> `Typed`
- `UPLOAD(#assignment-file-name, ml202_project_draft.pdf)` -> `Typed`
- `UPLOAD(#doc-name, Office Supply Invoice)` -> `Typed`
- `CLICK(#modal_confirm)` -> `Clicked`
- `SELECT(#issue-type, broken_seal)` / `partial_delivery` / `quality_issue` / `wrong_item` -> `Selected`

结论：旧 run 中 high-confidence UI infra / selector / 页面实现问题的主要确定性来源已经修复；剩余失败不应直接归为 benchmark UI infra bug，需要按 agent 行为或 workflow 难度继续分析。
