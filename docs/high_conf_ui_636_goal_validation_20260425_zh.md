# High-confidence UI Infra 636 Goal 逐项验证记录

日期：2026-04-25

## 验证目标

这轮验证只回答一个问题：旧 full train run 中标记出的 636 个 high-confidence UI infra / selector / 页面实现问题，在修复后是否还会复现。

这里的 high-confidence 指的是确定性 benchmark 问题，例如：

- `UPLOAD` 对文本型输入框调用 `set_input_files`。
- 页面实际 selector 与执行器/模型常见 selector 存在确定性别名不一致，例如 `#modal_confirm` vs `#modal-confirm`。
- 下拉框缺少 taskflow 合理需要的选项，例如售后 issue type 中缺少 `broken_seal`、`partial_delivery`、`quality_issue`、`wrong_item`。
- 页面字段校验比 task/oracle 更严格，导致真实任务目标已满足但页面不允许提交。

不计入 high-confidence UI infra 的情况：

- 模型自己输出不存在的自由 selector。
- 模型动作顺序错误，例如先点击确认再补填字段。
- 模型重复同一动作导致 `repeat_action_loop`。
- 模型提前 `DONE()` 导致 `premature_done`。
- 模型没有完成业务目标导致 `criteria_or_checkpoint_failed`。

## 修复内容

| 文件 | 修复点 |
| --- | --- |
| `agent/browser_env.py` | `UPLOAD` 遇到非 file input 时改为填入文件名文本，兼容 `#proof-file-name`、`#paper-file`、`#assignment-file-name`、`#doc-name` 等合成页面字段。 |
| `llm_runner.py` | 增加常见 selector alias，例如 `#modal_confirm -> #modal-confirm`；同时补充 lease 表单的 `#new_rent -> #new-rent` 等别名。 |
| `sites/shop.local/ticket.html` | 对齐售后 issue type 选项，补充 `broken_seal`、`partial_delivery`、`quality_issue`、`wrong_item` 等。 |
| `sites/work.local/paper-submission.html` | 将 abstract/track 改为默认值，不再作为强制页面提交条件，因为 task/oracle 只要求 title/journal/file。 |
| `rl_memory/scripts/audit_high_conf_ui_regression.py` | 新增逐项审计脚本，输出每个 goal 的 trace 覆盖、成功状态、失败类别、首个失败模块、首个错误片段、是否仍命中 high-confidence UI 问题。 |

## 636-goal targeted regression

运行目录：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_155033_high_conf_ui_636_verify_train`

审计输出：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_155033_high_conf_ui_636_verify_train/high_conf_ui_regression_audit_final/`

关键文件：

- `high_conf_ui_regression_goal_audit.csv`：636 个 goal 的逐项表。
- `high_conf_ui_regression_audit.json`：机器可读完整统计和明细。
- `high_conf_ui_regression_summary.md`：自动生成的摘要。

## 结果统计

| 指标 | 数值 |
| --- | ---: |
| 目标 goal 数 | 636 |
| 收到 trace 数 | 636 |
| 缺失 trace 数 | 0 |
| Qwen 成功数 | 4 |
| Qwen 成功率 | 0.63% |
| remaining high-confidence UI issue goals | 0 |
| remaining high-confidence UI issue attempts | 0 |

结论：636 个旧 high-confidence UI infra / selector / 页面实现问题已经逐项验证，修复后没有复现。

## 旧问题来源分布

| 旧 run 中受影响模块 | goal/attempt 数 |
| --- | ---: |
| `MODULE_ADDRESS_PROOF` | 391 |
| `MODULE_PAPER_SUBMISSION` | 70 |
| `MODULE_SUBMIT_ASSIGNMENT` | 55 |
| `MODULE_BILL_AGGREGATION` | 54 |
| `MODULE_FOOD_DELIVERY` | 51 |
| `MODULE_CONTACT_SUPPORT` | 5 |
| `MODULE_LOGISTICS_FIX` | 5 |
| `MODULE_TRACK_ORDERS` | 4 |
| `MODULE_DISPUTE_TRANSACTION` | 1 |
| `MODULE_TAX_PREPARATION` | 1 |

## 修复后剩余失败分类

| failure category | 数量 | 解释 |
| --- | ---: | --- |
| `repeat_action_loop` | 573 | 模型重复执行动作，没有推进任务状态。 |
| `premature_done` | 36 | 模型提前结束，业务目标尚未满足。 |
| `criteria_or_checkpoint_failed` | 15 | 执行动作后最终 oracle/checkpoint 未达标。 |
| `element_not_found_or_timeout` | 8 | 集中在 lease contract 场景，经复查是模型动作顺序问题，不是页面缺 selector。 |

## 对 8 个 element_not_found_or_timeout 的复查

受影响 goal：

- `WFG-NEWCOMER-0122`
- `WFG-NEWCOMER-0123`
- `WFG-NEWCOMER-0124`
- `WFG-NEWCOMER-0125`
- `WFG-NEWCOMER-0126`
- `WFG-NEWCOMER-0128`
- `WFG-NEWCOMER-0129`
- `WFG-NEWCOMER-0130`

对应模块：`MODULE_LEASE_CONTRACT_REGISTRATION`。

复查发现：trace 中模型执行顺序为：

1. `CLICK(#add-lease-btn)` 打开 modal。
2. `TYPE(#new-id, ...)` 填合同号。
3. `SELECT(#new-end-date, ...)` 填结束日期。
4. `CLICK(#modal-confirm)` 提前确认。
5. `TYPE(#new-rent, ...)` 尝试补填租金。

第 4 步确认时租金为空，modal 被关闭；第 5 步再找 `#new-rent` 时字段已经不存在，因此 timeout。也就是说，字段本身在页面中存在，selector alias 也已经正常化，失败原因是 agent 动作顺序错误，而不是 benchmark 页面实现错误。

补充 targeted run：

`/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/targeted_regressions/20260425_165920_lease_alias_8_verify_train`

该 run 再次确认 8 个 goal 的失败仍由上述动作顺序导致，不应归类为 high-confidence UI infra bug。

## 总结

本轮不是为了提高 Qwen 成功率，而是为了证明旧的 benchmark-side UI infra / selector / 页面实现问题已经被逐项清除。最终 636/636 都有 trace，0 个旧 high-confidence UI 问题复现；剩余失败主要反映模型在当前更难 taskflow 上的执行能力不足。
