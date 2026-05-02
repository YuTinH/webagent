# Test-Time Online Adaptation Reward 对比记录（2026-04-26）

## 实验设置

- Goal stream：stratified dev 30 goals。
- Block size：10。即每 10 个 instance 后才允许把本 block 的经验合并到下一 block 使用。
- Agent 配置：`atomic_max_steps=25`，`agent_max_tokens=96`。
- Reward：`WFG-R1` dense reward，用来衡量“虽然没完全成功，但离正确 workflow 有多近”。
- Baseline：`static`，即不做测试时更新。

## 四方法结果

| 方法 | 成功率 | 平均 reward | 相对 static | 目标状态覆盖率 | checkpoint progress | module reward |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| static | 0/30 | 0.1129 | +0.0000 | 0.0794 | 0.1750 | 0.0500 |
| memorybank_lite | 0/30 | 0.1076 | -0.0053 | 0.0772 | 0.1639 | 0.0462 |
| reflexion | 0/30 | 0.2040 | +0.0911 | 0.0844 | 0.4260 | 0.2303 |
| trajectory_rag | 0/30 | 0.2312 | +0.1183 | 0.1128 | 0.4511 | 0.2884 |

## 分 block 变化

| block | static | memorybank_lite | reflexion | trajectory_rag |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0.0000 / cp=0.0000 / cov=0.0000 | 0.0000 / cp=0.0000 / cov=0.0000 | 0.1091 / cp=0.3118 / cov=0.0000 | 0.1591 / cp=0.3618 / cov=0.0500 |
| 1 | 0.0785 / cp=0.1500 / cov=0.0400 | 0.1155 / cp=0.2000 / cov=0.0700 | 0.2360 / cp=0.4887 / cov=0.1000 | 0.2431 / cp=0.4903 / cov=0.1100 |
| 2 | 0.2602 / cp=0.3750 / cov=0.1983 | 0.2072 / cp=0.2917 / cov=0.1617 | 0.2668 / cp=0.4775 / cov=0.1533 | 0.2914 / cp=0.5014 / cov=0.1783 |

## 解释

这轮实验的成功率全部是 0/30，所以如果只看 final success，会得出“所有方法都没用”的结论。但 WFG-R1 reward 能反映更细粒度的进展：

- `checkpoint progress` 表示 agent 完成了多少 workflow 中间检查点。比如没完成最终售后退款，但已经正确进入订单页、定位订单、打开退款入口，也会得到部分进度分。
- `target state coverage` 表示最终目标状态中有多少关键条件已经满足。
- `module reward` 表示子任务层面的局部行为质量，比如是否进入了正确页面、是否避免明显非法 action、是否没有提前 done。

从 dense reward 看，`trajectory_rag` 明显优于 static，平均 reward 提升 `+0.1183`；`reflexion` 也有明显提升，平均 reward 提升 `+0.0911`。这说明测试时经验写入虽然还没有直接转化成 full success，但确实能让 agent 的行为更接近正确 workflow。

## 当前判断

- 这套 reward 可以作为 test-time training / RL 协议的训练或筛选信号。
- 下一步应该在 GPU 开发机恢复后做更大规模 run，例如 `n=100` 或按主题分层抽样，比较 static / reflexion / trajectory_rag。
- 当前 `qzcli list` 没有看到运行中的交互式 GPU 开发机，因此本轮没有继续在 CPU 机上启动大规模 agent 实验。

## 远端报告路径

- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/online_adaptation/reward_strat_s25_t96_four_method_compare.md`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/online_adaptation/20260426_084344_reward_reflexion_strat_n30_bs10_s25_t96_dev/workflow_rewards.md`
- `/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/online_adaptation/20260426_084344_reward_trajectory_rag_strat_n30_bs10_s25_t96_dev/workflow_rewards.md`
