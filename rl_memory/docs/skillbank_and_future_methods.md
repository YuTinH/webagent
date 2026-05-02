# SkillBank 方法设想

## 1. 背景

目前这套 benchmark 上，几个结论已经比较稳定：

- 纯 base model 比 prompt-memory / retrieval 方法更强
- 模型的主要问题不是“记不住”
- 模型的主要问题是：
  - 一步输出多个动作
  - 过早 `DONE()`
  - selector 写法不兼容
  - 动作类型和控件类型不匹配
  - 容易重复同一个动作

所以如果后面要提自己的方法，继续往 prompt 里塞更多记忆，意义不大。更值得做的是：让模型学会稳定、可复用的操作模式。

这就是 `SkillBank` 的出发点。

## 2. 我们想做的是什么

`SkillBank` 不是再做一个“更重的 MemoryBank”。

它要解决的问题是：

- 一个任务不是完全从零开始做
- 很多任务都由重复出现的子过程组成
- 模型应该把这些子过程学成可复用的 skill
- 后续任务遇到相似局面时，应该优先复用 skill，而不是每一步都重新摸索

一句话说，就是：

- 从训练轨迹里逐步长出 skill
- 在训练中不断修 skill
- 在后续任务中用 skill 约束动作选择

## 3. 我怎么理解 skill

### 3.1 skill 不是任务

一个完整任务太大，不能叫 skill。

例如：

- “完成找房任务”
- “完成报税任务”

这类东西包含太多分支，不适合复用。

### 3.2 skill 也不是一句提示词

例如：

- “下次不要重复点击”
- “先确认页面状态”

这种更像 reflection，不是 skill。

### 3.3 skill 是一个可复用的子过程

这里的 skill，更接近：

- 一个跨任务复用的操作模式
- 带参数槽位
- 但最终仍然只输出一步 primitive action

所以 skill 既不是：

- 一整条轨迹

也不是：

- 一句抽象建议

它更像：

- 当前这一步处在什么行为模式里
- 在这个模式下，下一步动作应该优先是什么类型
- 什么情况下该继续，什么情况下该停

## 4. skill 的例子

### 4.1 排序类 skill

很多任务其实都有“先排序，再挑目标项”的过程：

- 找房时按价格排序
- 购物时按价格或评分排序
- 服务列表按某个指标排序

这个 skill 不能写成：

```text
SELECT(#sort-order, "price_low")
```

因为这只是一个具体动作，换个页面就没法复用。

更合理的 skill 应该是：

- `sort_listing`

它表达的是：

- 在列表页，先找到排序控件
- 选中目标排序方式
- 然后再进入下一步选择

它带的参数可以是：

- `sort_selector`
- `sort_value`

所以在不同任务里，它可以实例化成：

```text
SELECT(#sort-order, "price_low")
```

也可以是：

```text
SELECT(#ranking, "rating_high")
```

不变的是“排序”这个行为结构，变化的是具体参数。

### 4.2 填表并提交 skill

很多任务都长这样：

- 填几个字段
- 可能选一个下拉框
- 点击提交
- 等待成功标记

例如：

- 自动扣费设置
- 水电开通
- 医生预约
- 各类申请表单

这个 skill 可以叫：

- `fill_form_then_submit`

它不能直接等价于一串动作：

```text
TYPE(...) TYPE(...) SELECT(...) CLICK(...)
```

否则就会回到现在最严重的错误：

- `multi_action_output`

所以 skill 的作用不是替代执行器，而是约束单步决策：

1. 当前处于“填表”模式
2. 先选一个该填的字段
3. 字段填完后再进入提交
4. 提交后不能马上 `DONE()`，要先等成功信号

### 4.3 验证后结束 skill

现在一个很典型的问题是：

- 模型还没完成任务就先 `DONE()`

这说明需要一个专门的 skill：

- `verify_success_then_done`

它的作用是：

- 当任务接近完成时，不是直接结束
- 而是先检查成功标记、状态变化、或者关键字段是否真的写入
- 只有验证通过，才允许 `DONE()`

这个 skill 直接对应：

- `premature_done`

## 5. 为什么这个方向比 memory prompting 更合适

之前做的几条线，基本都是把额外信息塞进 prompt：

- Reflexion
- MemoryBank
- Trajectory RAG

这几条线的问题不是“思路完全错”，而是它们在这个 benchmark 上很容易带来副作用：

- prompt 变长
- 当前页面信息被稀释
- 模型更容易受历史提示干扰
- 动作控制反而更差

`SkillBank` 想解决的是另一个层面的问题：

- 不是多给模型一些背景文字
- 而是让模型在动作层面形成稳定的行为结构

这更符合我们现在看到的主要误差来源。

## 6. SkillBank 应该放在哪里

我建议把 skill 分成三个层面来理解。

### 6.1 外部 skill bank

这是技能库本体，放在模型外面。

形式可以是：

- `json`
- `sqlite`

里面存的不是完整轨迹，而是 skill 的结构信息，比如：

- `skill_id`
- 适用页面或任务类型
- 参数槽位
- 偏好的动作类型
- 成功信号
- 常见失败模式

### 6.2 训练数据里的 skill 标签

训练时，每个样本不只是：

- 当前状态 -> 下一步动作

还应该带：

- 当前状态 -> skill_id -> 下一步动作

这样模型学到的不只是某一步怎么点，还包括：

- 当前这一步属于哪种技能

### 6.3 推理时的 active skill

推理时，当前 step 应该有一个“活跃 skill”。

这个 skill 可以来自：

- 当前状态预测
- 上一步的 skill 延续

它的作用是：

- 限制下一步动作的类型和停止条件

但最终给执行器的，仍然只能是一条 primitive action。

## 7. 训练中如何逐步提取 skill

这里我理解你导师说的重点不是“先手工整理好 skill 再训练”，而是：

- skill 要在训练过程中自己长出来
- 后面还要能继续被修

我建议拆成四步。

### 7.1 先做 bootstrap

第一步还是要有一个初始 skill 集合，不然在线更新没有起点。

这个初始 skill 可以从这些数据里抽：

- `sampled_*.json` 里的 `oracle_trace_override`
- `tasks/*/oracle_trace.json`

做法：

1. 把动作统一成 benchmark 的 executor 格式
2. 把长轨迹切成较短的子段
3. 把相似子段聚类
4. 把聚类结果抽象成参数化 skill

这个阶段的目的很简单：

- 先有一版可用 skill 库
- 先有一版 skill 标签

### 7.2 用 skill 标签做 SFT

有了 bootstrap 之后，第二步不是直接做 online RL，而是先做稳定版本：

- `skill-labeled SFT`

训练目标不再只是：

- `state -> action`

而是：

- `state -> skill`
- `state + skill -> action`

第一版可以用很简单的形式做：

```text
SKILL(sort_listing)
ACTION(SELECT(#sort-order, "price_low"))
```

或者做成双目标：

- 一个头预测 `skill_id`
- 一个头预测 `action`

### 7.3 训练中在线更新 skill

这一步才是“逐步提取并优化 skill”的核心。

训练过程中，每条 rollout 都在给 skill 提供新的证据：

- 这个 skill 在当前状态下是不是用对了
- 这个 skill 用完之后有没有带来进展
- 这个 skill 会不会导致 loop
- 这个 skill 会不会诱导错误动作类型
- 这个 skill 的结束条件是不是太松

每个 skill 至少应该维护：

- `usage_count`
- `success_count`
- `failure_count`
- `success_rate`
- `domains_seen`
- `task_families_seen`
- `common_failure_signatures`
- `preferred_action_types`
- `termination_confidence`

在线更新时，至少要支持：

1. `reinforce`
- 好用的 skill 增强权重

2. `penalize`
- 经常失败的 skill 降权

3. `merge`
- 把本质一样的 skill 合并

4. `split`
- 把过于宽泛、在不同场景表现不一致的 skill 拆开

5. `prune`
- 删掉长期无用或者明显误导的 skill

### 7.4 推理时用 skill 约束动作

推理时不能把 skill 变成一串宏动作直接输出。

应该是：

1. 先预测当前最合适的 skill
2. 再在这个 skill 条件下生成一步 primitive action

例如：

- 如果当前 skill 是 `fill_form_then_submit`
  - 就不应该轻易输出 `DONE()`

- 如果当前 skill 是 `verify_success_then_done`
  - 就应该优先检查状态，而不是继续乱点

- 如果当前 skill 是 `sort_listing`
  - 更合理的动作类型是 `SELECT` 或 `CLICK`
  - 而不是 `TYPE`

## 8. 泛化能力怎么保证

这是这条方法成不成立的关键。

如果最后长出来的 skill 只是：

- task id 的别名
- 某个 selector 的记忆
- 某个页面上的固定套路

那它就不是真的 skill，只是换了个名字做记忆。

我觉得至少要满足下面几点。

### 8.1 用行为模式做 skill，不用 task 名字做 skill

应该是：

- `sort_listing`
- `fill_form_then_submit`
- `verify_success_then_done`

而不是：

- `utility_setup_submit`
- `shopping_sort_price`

后者很容易变成 task-specific shortcut。

### 8.2 用参数槽位承接页面差异

skill 本体应该是稳定的，
变化的东西交给 slot：

- selector
- option value
- text value
- success marker

这样 skill 才能跨任务复用。

### 8.3 尽量做 role-based grounding，而不是死记 selector

比起直接记：

- `#submit-btn`

更应该记：

- `submit_button`
- `sort_control`
- `primary_action_button`

然后在当前页面再把这些角色落到具体元素上。

### 8.4 聚类时强调跨任务共享

例如这些都应该尽量归到同一个 skill 家族：

- 房源列表排序
- 商品列表排序
- 服务列表排序

它们页面不同，但行为结构一致。

## 9. 第一版怎么做最稳

我不建议第一版就做成很重的 end-to-end online latent skill learning。

那样工程风险太高。

更稳的版本是：

### V1

- 从 oracle trace bootstrap 一版初始 skill bank
- 做 skill-labeled SFT
- 推理时用 skill 约束下一步 primitive action
- 在线只更新 skill 的统计量，不做复杂结构变化

### V2

- 在 SFT 基础上加 DPO
- 用常见失败模式做 rejected actions
- 开始根据训练结果调整 skill 的可靠性和结束条件

### V3

- 再加 merge / split / prune
- 让 skill 库本身在训练中发生结构变化

## 10. 和其他方法的关系

如果只看训练方法，后面值得做的还是：

1. `SFT`
2. `DPO`
3. `SkillBank`

其中：

- `SFT` 是基础线
- `DPO` 是把常见坏动作压下去
- `SkillBank` 是真正的方法贡献

另外两个有价值但不一定是主方法的方向：

### 10.1 Grammar-constrained decoding

这条很实用，因为它直接打当前最严重的问题：

- multi-action
- 非法动作格式
- 不合法的 `GOTO`

它更像一个强工程增强项。

### 10.2 Stop-condition verifier

单独判断什么时候可以 `DONE()`。

这条很适合压：

- `premature_done`

但从方法角度看，它更像 `SkillBank` 的配套模块，而不是完整主方法。

## 11. 建议的实验顺序

### 先做

1. 跑通现在的 `SFT`
2. 在 `SFT` 基础上跑 `DPO`
3. 看动作格式和停止条件是否明显改善

### 再做

4. 从 oracle trace 抽第一版 bootstrap skill bank
5. 做 `skill-labeled SFT`
6. 跑第一版 `SkillBank`

### 最后做

7. 加在线 skill refinement
8. 做以下对比：
   - `base`
   - `SFT`
   - `SFT + DPO`
   - `SkillBank-SFT`
   - `SkillBank-SFT + online refinement`

## 12. 总结

这条 benchmark 上，目前更像是动作控制问题，不是长期记忆问题。

所以后面的主方法不应该继续围绕“再加一点记忆提示”来做，而应该围绕：

- 如何让模型形成稳定、可复用、可优化的操作技能

这也是为什么我觉得 `SkillBank` 值得做。

它如果做成“训练中逐步提取、逐步优化、跨子任务复用”的版本，方法上是说得通的，实验上也和你们现在的现象一致。
