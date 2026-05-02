# Round60 Train Failure Attribution Summary

## 背景

- 基线 run:
  `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_benchmark_shards/20260422_042758_round60_train_full_qwen25_7b_train`
- 基线模型: `Qwen2.5-7B-Instruct`
- 基线总结果: `403 / 4760 = 8.47%`
- 基线失败实例数: `4357`

这轮分析的目标不是继续看“成功率低不低”，而是回答一个更关键的问题:

`这 4357 个失败实例，到底是 agent 做不出来，还是 benchmark/taskflow 本身有问题？`

## 归因方法

我们先只做最关键的一层验证:

- 对全部失败实例跑 `reference + dry_run`

它的含义是:

- `reference`: 不再让模型自己规划，而是直接走 benchmark 的参考 module 路径
- `dry_run`: 不真正执行页面动作，只验证 workflow 路径、状态转移、target/oracle/evaluator 是否成立

因此，如果某个实例在这一设置下依然失败，就说明问题更可能在:

- taskflow 不可解
- target/oracle 写错
- evaluator 逻辑冲突
- benchmark 逻辑本身有 bug

相反，如果它在 `reference + dry_run` 下通过，就说明:

- 这个实例在 benchmark 逻辑层面是可解的
- taskflow / oracle / evaluator 没有暴露出结构性错误

## 执行情况

- 第一轮: `32-way` 并发全量扫描
- 中途发现 4 个 shard 因为 goal server 端口冲突退出
- 具体错误:
  `OSError: [Errno 98] Address already in use`
- 这不是 benchmark 逻辑问题，而是高并发运行时的端口竞争
- 随后把剩余 `247` 个 goal 单独抽出，用 `8-way` 低并发补跑
- 最终合并两轮结果后，得到完整覆盖:
  `4357 / 4357`

## 最终结论

- 已分析失败实例: `4357 / 4357`
- `benchmark_logic_or_eval`: `0 / 4357 = 0.00%`
- `agent_side`: `4357 / 4357 = 100.00%`

结论可以直接表述为:

`在目前这批失败实例里，没有发现 taskflow 不可解、target/oracle/evaluator 冲突、或 benchmark 逻辑层面的错误。`

也就是说，当前 `train full` 低成功率的主因不在 benchmark 逻辑层，而在 agent side。

## 全局失败模式

全局 agent-side failure category 分布如下:

- `none`: `1481`
- `repeat_action_loop`: `1091`
- `premature_done`: `1076`
- `element_not_found_or_timeout`: `291`
- `criteria_or_checkpoint_failed`: `207`
- `action_type_error`: `86`
- `executor_runtime_error`: `64`
- `selector_parse_error`: `53`
- `option_not_found`: `8`

这里可以简单理解为:

- `repeat_action_loop`: agent 在页面上反复做同一动作，卡住了
- `premature_done`: agent 任务没做完就提前 `DONE()`
- `element_not_found_or_timeout`: agent 找不到元素或等待超时
- `selector_parse_error` / `action_type_error`: agent 输出的动作格式本身有问题
- `criteria_or_checkpoint_failed`: 页面执行了一些动作，但最终没达到 oracle 要求
- `none`: trace 里没有结构化 failure category，但它仍然属于 agent-side 失败，因为同一实例在 `reference + dry_run` 下可解

## 按主题归因结果

| Theme | Failed | Benchmark Logic/Eval | 主导 agent-side failure |
|---|---:|---:|---|
| `career` | 340 | 0 | `premature_done 232`, `repeat_action_loop 62` |
| `composite` | 210 | 0 | `none 160`, `premature_done 18`, `criteria_or_checkpoint_failed 13` |
| `crisis` | 257 | 0 | `none 203`, `element_not_found_or_timeout 45` |
| `daily` | 340 | 0 | `none 181`, `repeat_action_loop 72`, `executor_runtime_error 50` |
| `education` | 320 | 0 | `premature_done 145`, `none 79`, `element_not_found_or_timeout 55` |
| `finance` | 181 | 0 | `none 93`, `element_not_found_or_timeout 40`, `repeat_action_loop 26` |
| `government` | 340 | 0 | `none 246`, `repeat_action_loop 53`, `element_not_found_or_timeout 32` |
| `health` | 340 | 0 | `premature_done 206`, `none 71`, `selector_parse_error 53` |
| `home` | 330 | 0 | `none 165`, `premature_done 57`, `element_not_found_or_timeout 56` |
| `newcomer` | 340 | 0 | `premature_done 239`, `none 48`, `element_not_found_or_timeout 37` |
| `security` | 339 | 0 | `repeat_action_loop 130`, `criteria_or_checkpoint_failed 104`, `none 100` |
| `social` | 340 | 0 | `repeat_action_loop 160`, `action_type_error 70`, `premature_done 63` |
| `support` | 340 | 0 | `repeat_action_loop 183`, `none 67`, `premature_done 62` |
| `travel` | 340 | 0 | `repeat_action_loop 282`, `criteria_or_checkpoint_failed 54` |

## 这一轮能证明什么

这一轮可以证明:

- benchmark 逻辑没有暴露出结构性错误
- taskflow 在参考路径下是可解的
- target / oracle / evaluator 没有在失败实例里出现系统性冲突

这一轮还不能单独证明:

- UI infra 是否绝对没有问题
- selector 是否稳定
- 页面实现是否和 task spec 永远完全一致

原因很简单:

- `reference + dry_run` 不碰页面
- 所以它只能证明 `benchmark logic` 没问题
- 不能单独证明 `page / selector / runtime infra` 没问题

## 下一步

下一步需要继续验证:

- `reference + agent`

它的作用是:

- 参考路径固定
- 真正执行页面动作

这样就可以把剩下的失败继续拆成:

- UI infra / selector / 页面实现问题
- agent 原子执行能力问题

优先建议检查的主题:

- `health`
- `home`
- `finance`
- `crisis`
- `government`

因为这些主题里 `element_not_found_or_timeout`、`selector_parse_error`、`none` 的占比更值得继续拆。

## 结果文件

- 归因汇总 JSON:
  `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_failure_attr_stage1only_round60_train_qwen25_7b_20260424_merged/train_stage1_failure_attribution_summary.json`
- 归因汇总 MD:
  `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/workflow_failure_attr_stage1only_round60_train_qwen25_7b_20260424_merged/train_stage1_failure_attribution_summary.md`
