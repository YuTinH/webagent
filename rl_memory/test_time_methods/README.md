# Test-Time Methods

这里放两条不需要单独训练主模型的推理期 baseline：

- `best_of_n`
  - 参考 inference-time scaling / rejection sampling 这一类 `Best-of-N` baseline
  - 关键机制：
    - 在当前 observation 上采样 `N` 个候选动作
    - 每个候选都在独立临时 runtime 中执行一步并打分
    - 最后提交分数最高的那个动作
  - 当前实现针对本 benchmark 做了文本化适配：
    - 候选采样沿用现有 action grammar 和启发式硬剪枝
    - 候选排序使用真实 progress delta + value prompt + action heuristic 的混合分数

- `tree_search`
  - 参考 `Tree Search for Language Model Agents`
  - 关键机制：
    - 从当前决策点开始，在真实环境状态空间里展开候选动作序列
    - 使用独立的 value prompt 对展开后的状态打分
    - 采用 best-first / budgeted search，最后提交最佳分支的第一步动作
  - 当前实现针对本 benchmark 做了文本化适配：
    - 状态评估输入是文本 observation、URL、最近动作历史
    - 每个搜索节点都在独立临时 runtime 中恢复并执行，避免污染主环境

- `verifier`
  - 参考 `Multimodal Auto Validation For Self-Refinement in Web Agents`
  - 关键机制：
    - 先提出候选动作
    - 用独立 verifier prompt 判断动作是否合法、是否贴合当前页面、是否仍在朝目标推进
    - 根据 verifier 反馈做 1-2 轮 refinement，再提交动作
  - 当前实现针对本 benchmark 做了文本化适配：
    - validator 以当前 observation、候选动作、分支执行后的 observation/status 为输入
    - 输出 verdict / on-track / feedback
