# GRPO Smoke 实验计划（2026-04-29）

## 目标

先验证 `static / vanilla Qwen2.5-7B` 是否能在我们的 WebAgent 环境中完成一次参数级 RL 更新。

本轮不叠加：

- Reflexion
- MemoryBank / MemoryBank Lite
- Trajectory RAG

原因是先要得到一个干净的 `static + GRPO` 增益，避免把参数更新效果和检索/记忆模块效果混在一起。

## 方法定义

本轮使用 OpenRLHF 的 PPO trainer，但 advantage estimator 设为 group-normalized：

```text
--advantage_estimator group_norm
--n_samples_per_prompt 4
--use_kl_loss
--kl_estimator k3
```

这里的 `group_norm` 对应 GRPO 的核心思想：对同一个 prompt / goal 采样多条 rollout，然后在组内做 reward 均值/方差归一化，得到相对 advantage。

## Reward

当前 OpenRLHF adapter 使用网页环境返回的 dense reward：

```text
reward = checkpoint_progress
       + task_success_bonus
       + flow_success_bonus
       - invalid_action_penalty
       - repeat_action_penalty
       - premature_done_penalty
```

它和我们后面 workflow-level 的 `WFG-R1` 思路一致：final success 仍重要，但 checkpoint progress 提供稠密中间信号。

## Smoke 配置

| 参数 | 值 |
| --- | ---: |
| base model | `Qwen2.5-7B-Instruct` |
| method | `static + GRPO` |
| `n_samples_per_prompt` | 4 |
| `max_samples` | 8 |
| `train_batch_size` | 4 |
| `rollout_batch_size` | 4 |
| `generate_max_len` | 96 |
| `prompt_max_len` | 1024 |
| LoRA rank | 16 |
| topology | 2 x H200, `dual_gpu_balanced` |

## 新增/修改文件

| 文件 | 作用 |
| --- | --- |
| `rl_memory/openrlhf/train_reinforce_clean.sh` | 增加 `KL_ESTIMATOR`、`MAX_SAMPLES`、`EVAL_STEPS` 参数透传。 |
| `rl_memory/openrlhf/train_grpo_clean.sh` | 新增 GRPO smoke launcher。 |
| `codex_tmp/launch_grpo_smoke_gpu.sh` | GPU 开发机后台启动脚本。 |

## 启动命令

GPU 开发机接口恢复后，同步上述文件，然后运行：

```bash
bash webagent/codex_tmp/launch_grpo_smoke_gpu.sh
```

日志会写到：

```text
/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/openrlhf_grpo_launch_logs/
```

## 成功标准

Smoke 阶段只看链路是否打通：

1. OpenRLHF 能加载模型和 LoRA。
2. Agent function 能启动 WebAgent 环境。
3. 同一 prompt 能采样多条 rollout。
4. reward 能正常回传。
5. 至少完成 1 次 policy update 并保存 checkpoint。

如果 smoke 通过，再扩大到：

- `max_samples=64/128`
- 对比 `static` vs `static + GRPO`
- 用当前 workflow benchmark 做 held-out evaluation

## 当前阻塞

2026-04-29 11:50 左右，GPU 开发机 `7b825dbc-6d73-4347-a944-4cfbd2325d7a` 的 Jupyter terminal API 返回 `503 Service Temporarily Unavailable`，本地无法通过 `qzcli exec/sync` 启动实验。

本地脚本已准备好；等开发机接口恢复后可直接同步并启动。
