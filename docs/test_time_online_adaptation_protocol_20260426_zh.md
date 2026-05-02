# Test-Time Online Adaptation 评测协议

本文档定义一个可复现的测试时学习/在线适应评测协议，用来比较 `static`、`reflexion`、`memorybank`、`memorybank_lite`、`trajectory_rag` 等方法在 workflow benchmark 上的增益。

## 核心设定

- `Static Eval`：普通一次性评测，模型在整个 split 上不更新任何记忆、skill 或 prompt。
- `Online Adaptation Eval`：按时间顺序把测试 instance 切成多个 block。每跑完一个 block，系统允许基于该 block 的轨迹更新 memory / reflection / trajectory corpus，然后进入下一个 block。
- `Block`：连续的一组测试 instance，例如每 10 或 100 个 goal 为一组。
- `Snapshot`：进入某个 block 之前已经存在的记忆库快照。
- `Delta Store`：当前 block 产生的新经验，只能在 block 结束后合并到下一轮 snapshot。

## 防止信息泄漏的规则

每个 block 必须满足：

1. 当前 block 内所有 instance 只能读取 `snapshot_before_block`。
2. 当前 block 产生的新经验只能写入 `delta_block_k`。
3. `delta_block_k` 不能被当前 block 内的其他 instance 检索到。
4. block 完成后，才允许执行 `snapshot_block_{k+1} = snapshot_block_k + delta_block_k`。
5. 下一个 block 才能读取合并后的新 snapshot。

这保证了我们测到的是“测试时跨批次学习能力”，不是同一个 batch 内互相偷看答案。

## 已接入的方法

| 方法 | 更新对象 | 读写隔离 | 说明 |
| --- | --- | --- | --- |
| `none` | 无 | 不写入 | static baseline |
| `reflexion` | 反思文本 | 支持 | 失败/成功后的自然语言反思，用于后续 prompt 增强 |
| `memorybank` | 结构化 memory entries | 支持 | 记录任务结果、关键状态、失败类别 |
| `memorybank_lite` | 轻量 memory entries | 支持 | 更便宜的 MemoryBank 版本，适合先做 pilot |
| `trajectory_rag` | 成功轨迹 corpus | 支持 | 把成功轨迹压缩为检索样例，后续相似任务可 RAG |

## 推荐指标

- `Success Rate`：最终成功率。
- `Block Success Rate`：每个 block 的成功率，看是否随在线更新上升。
- `AULC`：Area Under Learning Curve，可理解为所有 block success rate 的加权平均。
- `Delta over Static`：在线适应方法相对 static baseline 的绝对提升。
- `Failure Attribution`：失败是否来自 agent 能力、UI infra、selector、页面实现或 benchmark 逻辑。

## 当前实现入口

主入口：

```bash
python3 rl_memory/scripts/run_online_adaptation_blocks.py \
  --method memorybank_lite \
  --split dev \
  --limit 30 \
  --block-size 10 \
  --run-root rl_memory/runs/online_adaptation \
  --gpu-ids 1 \
  --num-shards 1 \
  --module-policy reference \
  --atomic-policy agent \
  --atomic-max-steps 10 \
  --atomic-repeat-fail-threshold 2 \
  --agent-max-tokens 64 \
  --tag pilot_memorybank_lite_n30_bs10
```

对照 static baseline：

```bash
python3 rl_memory/scripts/run_online_adaptation_blocks.py \
  --method none \
  --split dev \
  --limit 30 \
  --block-size 10 \
  --run-root rl_memory/runs/online_adaptation \
  --gpu-ids 0 \
  --num-shards 1 \
  --module-policy reference \
  --atomic-policy agent \
  --atomic-max-steps 10 \
  --atomic-repeat-fail-threshold 2 \
  --agent-max-tokens 64 \
  --tag pilot_static_n30_bs10
```

## 远程运行环境

当前 GPU 开发机：

```text
notebook_id: f5d6ccec-4d1c-4a48-8757-36338d0baa75
remote repo: /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent
env: /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/envs/webagent/bin/activate
model: /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/models/Qwen2.5-7B-Instruct
playwright: /inspire/hdd/project/exploration-topic/huaitianyu-253108120130/.cache/ms-playwright
```

## 解释方式

如果 `memorybank_lite` 在第 1 个 block 只有 2/10 成功，但第 2、3 个 block 上升到 4/10、5/10，而 static baseline 一直在 2/10 左右，那么可以说明 agent 从前面的测试经验中学到了一些可迁移模式。

如果成功率没有提升，也仍然有价值：这说明当前记忆形式没有有效转化为行动能力，后续需要改 memory schema、retrieval 或引入更强的 skill / prompt update。

