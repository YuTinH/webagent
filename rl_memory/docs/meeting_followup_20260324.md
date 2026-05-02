# 导师会议后续整理（2026-03-24）

## 1. 先把 benchmark 这件事说清楚

### 1.1 我们这个 benchmark 的定位

这套 benchmark 不是“单个网页任务做没做完”的评测，而是“跨任务状态持续演化”的评测。

更准确地说，它考察的是三件事：

- 前序任务写入的状态，会不会影响后续任务
- agent 能不能在后续任务里正确利用、修复、或者规避这些状态
- 同一条任务流在轻微初始扰动下，会不会产生系统性偏差

如果只看任务数量，这个 benchmark 不一定比别人大；但如果看“跨任务因果结构”和“持续学习压力”，它的评测对象和很多现有 web benchmark 不一样。

### 1.2 我们自己的统计

基于当前发布评测集，统计如下：

- 主题数：`5`
- 任务流数：`500`
- 总步骤数：`3580`
- 单链步数：`6-8`
- 平均步数：`7.16`
- 唯一子任务数：`72`
- 当前主要主题：`newcomer / daily / career / leisure / crisis`
- 已提供 `oracle_trace_override` 的 step：`3033 / 3580`

仓库里还有一批任务实例与站点环境：

- 任务实例：`124`
- 本地站点至少覆盖：`shop.local / bank.local / gov.local / health.local / school.local / work.local`
- 评测维度：`step_score / task_score / flow_score`
- 还支持：
  - `clean / obfuscate`
  - `distractor_seed / obfuscation_seed`
  - `counterfactual`
  - `failure taxonomy`

### 1.3 跟同类 benchmark 应该怎么比

这里不能只比“任务数”，要按评测目标来比。

建议至少放下面几个 benchmark：

1. `Mind2Web`
2. `Online-Mind2Web`
3. `WebArena`
4. `VisualWebArena`
5. `WorkArena / WorkArena++`
6. `WebChoreArena`

### 1.4 对比维度

建议表格里放这些列：

- 环境类型：真实在线网站 / 本地可复现网站 / 企业软件
- 评测单位：单任务 / 长任务 / 任务流
- 是否跨任务持久状态
- 是否支持长程因果传播
- 是否支持 counterfactual
- 是否支持干扰和混淆控制
- 是否支持 strict checkpoint 评分
- 是否支持 oracle 回放
- 是否主要考察视觉 grounding
- 是否适合 continual learning / skill reuse

### 1.5 可以直接写进论文的对比结论

#### `Mind2Web`

优点：

- 真实网站多，覆盖广
- 高层目标，不是低层脚本指令
- 适合测 general web grounding

不足：

- 主要是单任务轨迹数据
- 不强调跨任务状态持续演化
- 更像“单任务 web grounding 数据集”，不是持续学习 benchmark

#### `Online-Mind2Web`

优点：

- 在线环境，更接近真实网页漂移
- 任务来自真实网站

不足：

- 可复现性和环境稳定性天然更差
- 仍然主要是单任务评测
- 不以跨任务因果结构为主要设计目标

#### `WebArena`

优点：

- 本地可复现
- 任务更长，环境更真实
- 有功能性评测

不足：

- 核心评测单位仍然是单个 long-horizon task
- 每个任务通常 reset
- 不直接评估“过去任务留下的状态对后续任务的影响”

#### `VisualWebArena`

优点：

- 强调视觉 grounding
- 更接近真实网页交互

不足：

- 重点是多模态理解，不是持续学习
- 仍然不是“任务流级别的状态传播 benchmark”

#### `WorkArena / WorkArena++`

优点：

- 企业软件环境真实
- WorkArena++ 开始强调 compositional planning

不足：

- 主要聚焦单平台知识工作流
- 更偏 enterprise software automation
- 不专门围绕跨任务状态因果和反事实扰动设计

#### `WebChoreArena`

优点：

- 已经开始强调 memory-heavy、calculation、multi-page 任务
- 比 WebArena 更难

不足：

- 还是以单任务为主
- 主要考察单任务内部的长程记忆与繁琐操作
- 不是“前一任务改变后一任务可行性”的 continual setting

### 1.6 我们 benchmark 的真正优势

这一部分不要写成“我们全都更强”，而要写成“我们测的东西不一样，而且更适合本文的方法动机”。

我建议收敛成下面五点。

#### 优势 1：评测单位是任务流，不是孤立任务

很多 benchmark 测的是：

- 当前任务会不会做

我们更关注：

- 前一个任务做完之后，后一个任务还能不能做对

这才是 continual learning / memory / skill reuse 真正需要面对的问题。

#### 优势 2：环境状态真实持久化

这里不是“每题重置页面”。

任务会真实改写：

- `env/state.json`
- `data.db`

因此后续任务面对的是被前序任务改变过的世界，而不是一个新的世界。

#### 优势 3：有反事实轴

这一点很关键。

很多 benchmark 只能说：

- 这个任务做成了没有

我们还能问：

- 如果只改一个关键初始状态键，整条任务流会从哪里开始分歧

这给“skill 是否真的有因果作用”提供了更好的检验方式。

#### 优势 4：可复现而且可诊断

我们有：

- 本地站点
- oracle replay
- clean / obfuscate
- distractor 控制
- failure taxonomy

这意味着：

- 适合做方法开发
- 适合做 ablation
- 不会被网页外部漂移完全淹没

#### 优势 5：更适合 skill / continual adaptation 方向

因为我们要做的不是：

- 单步点按钮

而是：

- 在跨任务上下文里复用并修正行为模式

所以这个 benchmark 和 `SkillBank` 的动机是对齐的。

### 1.7 但也要诚实写局限

这部分不能省。

目前相对外部 benchmark，我们的局限也很明显：

- 站点数量少于 `Mind2Web / Online-Mind2Web`
- 开放网页多样性不如真实互联网
- 视觉复杂度不如 `VisualWebArena`
- 企业流程深度不如 `WorkArena++`

所以更准确的表述不是“我们全面替代已有 benchmark”，而是：

- 我们补上了“跨任务状态传播 + 反事实 + 持续适应”这一块评测空白

---

## 2. test-time RL 这条线怎么走

### 2.1 先把范围说清楚

导师的偏好很明确：

- 尽量不要有单独训练阶段
- 方法最好发生在推理期

那这里的 `test-time RL` 不应该理解成：

- 线上再做一次 PPO

而应该理解成：

- 在推理时利用环境反馈做搜索、选择、信用分配和策略更新
- 但尽量不改大模型参数，或者只做极轻量的在线更新

### 2.2 我建议优先考虑的几类方法

#### 方法 A：`Best-of-N trajectory rollout + reward reranking`

思路：

- 当前 step 不只出一个动作，而是出 `N` 个候选动作
- 对每个候选动作向前 rollout 若干步
- 用 benchmark 自带的 checkpoint / success signal / heuristic reward 对 partial trajectory 打分
- 选择回报最高的那条继续执行

这条线的特点：

- 不需要训练
- 直接利用环境反馈
- 很像最轻量的 test-time RL

适合我们 benchmark 的原因：

- 我们本来就有 step / checkpoint / task 三层反馈
- 可以把这些反馈直接拿来做 test-time selection

主要风险：

- rollout 成本高
- 需要做缓存，否则太慢

#### 方法 B：`Tree Search for Web Agents`

思路：

- 把每一步动作当成树节点
- 在真实环境中做 best-first / MCTS 类搜索
- 用环境反馈和启发式 value 继续扩展

这条线更重，但更像“真正的 test-time RL / planning”。

适合我们 benchmark 的原因：

- 任务流长，单步贪心容易出错
- 我们现在的主要错误就是：
  - 提前 `DONE()`
  - 重复动作
  - action type error

搜索可以直接缓解这些局部决策失误。

不适合直接上的原因：

- 成本高
- 工程重

所以如果做，建议先做窄版，不要一上来就全树搜索。

#### 方法 C：`Action-level reranker / verifier-guided decoding`

思路：

- policy 先给多个动作候选
- verifier 根据当前页面、动作合法性、历史轨迹和近端回报打分
- 只执行最靠谱的动作

它不算完整 RL，但很接近“test-time policy improvement”。

优点：

- 成本低于 tree search
- 对我们现在的错误模式非常对症

尤其适合压这几类错：

- `multi_action_output`
- `premature_done`
- `action_type_error`
- `selector_parse_error`

#### 方法 D：`Skill-level bandit / delayed-reward controller`

这是我最推荐的方向。

思路：

- 推理时不是直接在 primitive action 上做选择
- 而是在候选 skill 上做选择
- 每次 skill 被激活后，先不立刻判断好坏
- 等若干步后，根据延迟 reward 给 skill 分配信用
- 再更新 skill 的优先级和置信度

这更像：

- online option selection
- inference-time policy adaptation

它最符合导师现在的要求：

- 没有单独训练阶段也能做
- 能讲“推理时逐步提取并优化 skill”
- 能自然接 delayed reward

#### 方法 E：`真正的 TTRL（测试时参数更新）`

这条线严格来说也属于 test-time RL：

- 推理时利用无标签数据和 reward 做在线参数更新

但它有两个问题：

1. 其实已经带一点“训练味道”
2. 工程复杂度和不稳定性都高

所以这条线可以写进 related work，但我不建议作为当前主方法。

### 2.3 建议的优先级

如果只看“最可能做成”的顺序，我建议是：

1. `Action-level reranker / verifier`
2. `Skill-level bandit with delayed reward`
3. `Best-of-N rollout`
4. `Tree search`
5. `真正在线参数更新的 TTRL`

如果只押一条主方法，我建议押：

- `Skill-level bandit with delayed reward`

因为它既符合导师偏好，也最容易和 `SkillBank` 合并成一篇完整故事。

---

## 3. SkillBank 这条线要怎么改

导师提的质疑点是对的，而且都指向一个问题：

- 我们现在对 skill 的定义还不够硬
- 也还没有说明 skill 是怎么在推理期长出来、被评估、被更新的

下面我把这几件事拆开。

### 3.1 skill 不能只停留在低级动作

如果 skill 只是：

- 点击某个按钮
- 输入某个字段

那它其实不是 skill，只是 primitive action。

我建议明确分三层：

#### 第 0 层：primitive action

这是执行器层面的基本动作：

- `CLICK`
- `TYPE`
- `SELECT`
- `GOTO`
- `WAIT`
- `DONE`

这不是 skill。

#### 第 1 层：中级 skill

这是最值得复用的一层，也是当前方法的核心。

例如：

- `sort_listing`
- `fill_required_fields`
- `dismiss_overlay`
- `locate_target_item`
- `verify_success_then_done`

这类 skill 有两个特点：

- 跨多个任务都能复用
- 最终仍然约束单步 primitive action，而不是直接输出一串动作

#### 第 2 层：高级 skill

这是更完整的 option / subworkflow。

例如：

- `fill_form_then_submit`
- `compare_plans_then_choose`
- `resolve_state_conflict_then_retry`

这类 skill 不是一条 primitive action，但也不应该直接作为执行输出。它更像一个短程控制模式，会持续若干步，然后自行终止。

所以如果导师问“我们有没有高级 skill”，答案应该是：

- 有，但高级 skill 不是直接给执行器的一串动作
- 它是推理期的控制变量
- 真正执行的仍然是一条一条 primitive action

### 3.2 为什么不应该一开始全手工写死 skill

这点也同意导师。

如果一开始人为定义一整套固定 skill，容易出现两个问题：

1. 做成 task-specific shortcut
2. skill 本身没有增长能力

所以更合理的做法不是：

- 全手工列 skill 表

而是：

- 只保留一个很小的 seed taxonomy，作为初始化偏置
- 让另一个模型在推理时提出 candidate skill

### 3.3 我建议的 skill 生成方式

不要把“skill 提取”放在离线标注阶段一次做完。

建议改成推理期在线生成：

#### `Skill Proposer`

输入：

- 当前任务目标
- 当前页面观察
- 最近若干步动作历史
- 最近的 checkpoint 变化

输出：

- 一个候选 skill 描述
- skill 层级（中级 / 高级）
- skill 的适用条件
- skill 的终止条件
- skill 对动作类型的偏好

这相当于让另一个模型在推理时回答：

- “当前这一步最像在做哪类子过程？”

### 3.4 如何避免 skill 变成 task-specific memorization

这一点必须单独写。

如果 skill 直接绑定：

- `task_id`
- 具体 selector
- 具体域名模板

那它就没有泛化能力。

所以 skill 表示必须拆成：

#### 不变部分

- 行为模式
- 触发条件
- 偏好动作类型
- 终止条件

#### 可变部分

- 参数槽位
- 当前页面上的 grounding 对象

例如：

- skill 是 `sort_listing`
- 但 `sort_selector` 和 `sort_value` 是当前页面实例化出来的

这样 skill 才能在不同子任务复用。

---

## 4. 如何在推理时评估 skill 是否有效

这也是必须回答的问题。

不能只说“用了以后分数更高”，那太粗了。

我建议从四个层面评估。

### 4.1 局部有效性

skill 激活后，是否立刻降低这些错误：

- 非法动作
- 多动作输出
- 过早 `DONE()`
- selector 错误

这说明 skill 至少改善了局部动作控制。

### 4.2 短程贡献

skill 激活后的若干步内，是否带来：

- checkpoint 增长
- 页面状态向目标推进
- 关键字段被正确写入

这可以记成 `delta_step_reward`。

### 4.3 长程贡献

skill 在当前任务或后续任务上，是否提高：

- task success
- flow success
- recovery 成功率

这可以记成 `delta_task_reward` 或 `delta_flow_reward`。

### 4.4 复用价值

同一个 skill 在不同 family / theme / site 上重复使用时，是否仍然有正收益。

如果一个 skill 只能在一个任务上有用，那它不算我们想要的 skill。

### 4.5 我建议的在线指标

每个 skill 维护这些字段：

- `usage_count`
- `success_count`
- `failure_count`
- `avg_step_gain`
- `avg_task_gain`
- `avg_flow_gain`
- `reuse_success_rate`
- `domains_seen`
- `families_seen`
- `common_failure_signatures`
- `termination_confidence`

这些字段能直接支持后面的更新和裁剪。

---

## 5. 如何在后续推理中继续优化 skill

这里就要接导师说的 delayed reward。

### 5.1 为什么必须用 delayed reward

因为 skill 的作用通常不是一步就能看出来。

例如：

- `fill_form_then_submit`
- `resolve_state_conflict_then_retry`

它们可能前几步没有直接成功，但为后面成功创造了条件。

如果只用即时 reward，很容易错杀有价值 skill。

### 5.2 一个可行的信用分配方式

当某个 skill 在第 `t` 步被激活后，不马上定生死，而是等到：

- 下一个 checkpoint
- 当前 task 结束
- 或整条 chain 结束

再回头给这个 skill 分配信用。

可以把 reward 拆成三部分：

#### 即时奖励

- 当前动作是否合法
- 有没有避免明显错误

#### 任务级延迟奖励

- 当前 task 是否完成
- 当前 task 的 step / task 得分变化

#### 流级延迟奖励

- 它是否改善了后续任务的可行性
- 是否减少了状态冲突带来的失败

最后用加权和更新该 skill 的信任度。

### 5.3 skill 的在线更新规则

我建议先从简单版本做起：

#### 强化

当某个 skill 多次带来正收益时：

- 提高优先级
- 提高触发概率
- 增强该 skill 的参数先验

#### 降权

当某个 skill 经常导致：

- loop
- premature done
- action_type_error

就降低它的优先级。

#### 拆分

如果同一个 skill 在不同场景表现分化很大，就把它拆成两个 skill。

#### 合并

如果两个 skill 的触发条件和收益模式长期接近，就合并。

#### 淘汰

如果一个 skill 长期复用失败，且没有跨任务收益，就删除。

### 5.4 一句最重要的话

skill 不应该是静态知识库，而应该是：

- 推理时被提出
- 被选择
- 被信用分配
- 被持续修正

这样它才是“在线 skill learning”，不是另一种 prompt memory。

---

## 6. 一个更像论文方法的版本

如果把这条线收成一个方法，我建议写成下面这样。

### 方法名候选

- `SkillBank`
- `Online SkillBank`
- `Delayed-Reward SkillBank`
- `SkillBandit`

如果要兼顾清晰和可讲性，我更倾向：

- `Online SkillBank`

### 方法结构

#### 模块 1：`Skill Proposer`

根据当前目标、页面状态和最近轨迹，在线提出候选 skill。

#### 模块 2：`Skill Retriever`

从已有高置信 skill 中检索相似 skill，和新候选 skill 一起组成候选集。

#### 模块 3：`Skill Selector`

用 bandit/UCB/Thompson sampling 之类的方法，在候选 skill 中选择当前激活 skill。

#### 模块 4：`Skill-conditioned Policy`

在 active skill 条件下，只输出一条 primitive action。

#### 模块 5：`Delayed Reward Updater`

根据 checkpoint、task、flow 三层回报给 skill 分配信用，并更新 skill 统计。

### 这个方法的优点

1. 不需要预先写死一整套 skill
2. skill 可以在推理中增长
3. skill 的更新可以靠 delayed reward 支持
4. skill 可以跨任务复用
5. 最终输出仍然符合现有执行器的单步动作接口

---

## 7. 现在最值得做的几条方法

如果按投入产出比排，我建议是：

1. `Action reranker / verifier`
2. `Online SkillBank + delayed reward`
3. `Best-of-N rollout`
4. `Tree search`

其中：

- `Action reranker / verifier` 适合作为一个强 baseline
- `Online SkillBank + delayed reward` 适合作为你们自己的方法

---

## 8. 我建议的下一步

### 8.1 论文动机部分

先写 benchmark 对比表，把“我们补的是哪块空白”说清楚。

### 8.2 方法部分

不要再把 `SkillBank` 写成“离线抽 skill + 检索 skill”。

应该改成：

- 推理时提出 skill
- 用 delayed reward 在线评估
- 在后续任务中继续修 skill

### 8.3 实验部分

建议至少做这几组：

1. `Base`
2. `Base + verifier`
3. `Base + online skill proposer`
4. `Base + online skill proposer + delayed reward`
5. `Base + online skill proposer + delayed reward + cross-task reuse`

然后做 ablation：

- 去掉 delayed reward
- 去掉 skill reuse
- 去掉 skill hierarchy
- 去掉 skill proposer，只保留手工 seed skill

这样导师现在问的几个问题，实验上都能对应起来。

---

## 8.5 可以直接拿来做对比试验的方法

这里分两类：

1. 严格偏 `test-time RL / test-time policy improvement`
2. 虽然不一定严格叫 RL，但属于推理时自我改进或推理时搜索，和我们的方法最接近

### A. 建议优先做的主对比

#### 1. `Tree Search for Language Model Agents`

- 来源：`https://arxiv.org/abs/2407.01476`
- 性质：推理期搜索，不改模型参数
- 核心做法：
  - 在真实环境里做 best-first tree search
  - 用环境反馈和启发式 value 扩展候选动作分支
- 为什么适合拿来和我们比：
  - 它是少数直接在真实 web agent 上证明“test-time compute 能换性能”的方法
  - 和我们 benchmark 的交互形式最接近

建议在我们 benchmark 上的简化复现方式：

- 不做全树搜索
- 先做 `depth-2` 或 `depth-3`
- 每步保留 `top-k` 候选动作
- 用 checkpoint 增益 + 动作合法性做打分

#### 2. `TTRL: Test-Time Reinforcement Learning`

- 来源：`https://arxiv.org/abs/2504.16084`
- 性质：严格意义上的 test-time RL
- 核心做法：
  - 在测试阶段利用无标签数据和 surrogate reward 做在线 RL
- 为什么适合拿来对比：
  - 它正好对应导师说的“test-time RL”
  - 可以作为“严格 test-time RL”代表方法

但要注意：

- 这条线已经带一点“测试时训练”的味道
- 不完全符合“纯推理，不改参数”的最严格口径

所以更合适的定位是：

- 作为 test-time RL 强对比
- 不作为我们主方法的实现路线

#### 3. `DeepVerifier` 类 verifier-guided inference-time refinement

- 来源：`https://arxiv.org/abs/2601.15808`
- 性质：推理期验证和自我修正，不改模型参数
- 核心做法：
  - 先生成候选输出
  - 再用 verifier / rubric 反馈迭代修正

为什么适合：

- 我们现在最严重的问题就是动作 contract 不稳定
- verifier 类方法正好适合压：
  - multi-action
  - premature done
  - selector / action type mismatch

它不是严格 RL，但很适合作为：

- test-time improvement baseline

### B. 和 SkillBank 很接近，适合 related work + 可能的补充对比

#### 4. `SkillWeaver`

- 来源：`https://arxiv.org/abs/2504.07079`
- 性质：web agent 的 skill 自发现和自优化
- 核心做法：
  - agent 在新网站上自主发现 skill
  - 练习 skill
  - 把经验蒸馏成可复用 API

为什么值得看：

- 它和我们现在要做的 `SkillBank` 很接近
- 它能直接给我们提供两个对照点：
  - skill 如何被提出
  - skill 如何被固化成可复用单元

但它不一定能直接无改动复现到我们 benchmark，因为：

- 它更偏网站内 skill synthesis
- 我们这里更强调跨任务状态传播和 delayed reward

所以更适合：

- 作为最重要 related work
- 也可以做一个轻量思想对比，而不一定全量复现

#### 5. `WebCoach`

- 来源：`https://arxiv.org/abs/2511.12997`
- 性质：推理期跨 session 自我进化，不需要重新训练
- 核心做法：
  - 把历史轨迹整理成外部经验库
  - 在后续推理中检索并注入建议

为什么值得看：

- 它代表“无训练的 online self-improvement”
- 和我们的 `SkillBank` 形成鲜明对比：
  - 它偏 memory guidance
  - 我们偏 skill discovery + delayed reward

### C. 我建议的最终对比名单

如果考虑时间和复现成本，我建议把对比方法收敛成：

#### 主对比

1. `Base`
2. `Tree Search for Language Model Agents` 风格的 test-time search
3. `Verifier-guided reranking / refinement`
4. `我们的 Online SkillBank + delayed reward`

#### 扩展对比

5. `TTRL`
6. `SkillWeaver`（如果能轻量适配）

### D. 取舍建议

如果只做两个外部对比方法，我建议优先：

1. `Tree Search for Language Model Agents`
2. `Verifier-guided refinement`

原因：

- 两者都不要求正式训练阶段
- 都能直接落到我们的 benchmark 执行器上
- 都能明显和 `Online SkillBank` 区分开

如果再加第三个，再加：

3. `TTRL`

这样就形成三条清晰路线：

- 搜索型
- 验证型
- 严格 test-time RL 型

然后我们的方法是：

- `skill-level online adaptation with delayed reward`

---

## 9. 现在这条主线的判断

如果只看目前实验现象，最合理的结论是：

- 这个 benchmark 的主要问题不是“缺一个更重的 memory prompt”
- 而是“需要一种能在推理时逐步形成和修正行为模式的机制”

所以把主方法收敛到：

- `Online SkillBank + delayed reward`

是合理的。

---

## 附：后续写作时可直接引用的外部 benchmark / 方法来源

- `Mind2Web`
  - 论文：`https://proceedings.neurips.cc/paper_files/paper/2023/file/5950bf290a1570ea401bf98882128160-Paper-Datasets_and_Benchmarks.pdf`
  - 关键点：`2350` 个任务，`137` 个网站，真实网页，高层目标，平均页面元素规模大。

- `Online-Mind2Web`
  - 仓库：`https://github.com/OSU-NLP-Group/Online-Mind2Web`
  - 关键点：`300` 个在线任务，`136` 个真实网站，强调在线评测和环境更新。

- `WebArena`
  - 论文：`https://arxiv.org/abs/2307.13854`
  - 官方站点：`https://webarena.dev/`
  - 关键点：可复现本地环境，`812` 个 long-horizon task，四类主要网站域。

- `VisualWebArena`
  - 论文：`https://arxiv.org/abs/2401.13649`
  - 仓库：`https://github.com/web-arena-x/visualwebarena`
  - 关键点：`910` 个视觉 grounding 任务，强调多模态网页理解。

- `WorkArena / WorkArena++`
  - 仓库：`https://github.com/ServiceNow/WorkArena`
  - 关键点：`WorkArena-L1` 有 `33` 类 atomic task、`19,912` 个实例；`WorkArena++` 有 `682` 个组合任务。

- `WebChoreArena`
  - 论文：`https://arxiv.org/abs/2506.01952`
  - 官方站点：`https://webchorearena.github.io/`
  - 关键点：`532` 个 tedious web task，强调 memory-heavy、多页面和繁琐操作。

- `Tree Search for Language Model Agents`
  - 论文：`https://arxiv.org/abs/2407.01476`
  - 关键点：在真实网页环境上做 inference-time tree search，证明增加 test-time compute 能显著提升 web agent。

- `TTRL: Test-Time Reinforcement Learning`
  - 论文：`https://arxiv.org/abs/2504.16084`
  - 关键点：推理时利用无标签数据和 surrogate reward 做在线 RL，更接近“测试时训练”而不是纯推理搜索。
