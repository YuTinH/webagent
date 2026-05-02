# Agent 超参数调优 Benchmark 汇报稿

这份文档是给汇报直接使用的版本。整体结构是：

1. `Preliminary / Motivation`：为什么要做这个 benchmark
2. `Related Work`：逐篇讲已有工作
3. `收束`：这些工作共同留下了什么空白，你的 benchmark 填的是什么坑

如果你明天要讲，我建议把 `Preliminary` 讲成 3 到 5 分钟，再用 10 到 15 分钟讲论文，最后 2 到 3 分钟收束到你自己的 benchmark。

---

## Preliminary

### 1. 为什么现在要研究 agent 的超参数调优能力

过去一年里，大家对 agent 的关注点主要集中在两类能力上：

- 一类是 `代码能力`，比如能不能读 repo、改代码、修 bug、通过测试。
- 一类是 `开放式研究/工程能力`，比如能不能做实验、跑训练、迭代提升模型效果。

但如果我们更仔细地看现有工作，会发现一个很关键的事实：

- 在很多 ML 任务里，agent 能带来的提升，并不一定来自提出了新的方法。
- 更常见的情况是，它通过更系统地尝试学习率、batch size、训练轮数、正则强度、搜索空间、scheduler 等配置，最终把 baseline 做上去。

也就是说，`超参数调优能力` 很可能是当前 agent 在 ML 场景中最早可用、也最值得独立测量的一种能力。

### 2. 为什么不能只用已有 benchmark

现有 benchmark 很有价值，但大多存在下面几类问题：

- `问题太宽`：很多 benchmark 测的是完整 ML workflow，agent 可以同时改代码、换模型、换数据处理、改训练流程。最后即使分数提高，也很难知道到底是因为 agent 会调参，还是因为它偷偷换了方法。
- `可归因性弱`：如果不限制 method space，就很难把结果解释为“这个 agent 更擅长 HPO”。
- `预算控制不够干净`：一些工作报告资源扩展或 pass@k，但没有把“固定预算下谁更会调参”单独抽出来。
- `repo realism 不足`：传统 HPO benchmark 往往在抽象搜索空间或 surrogate 环境里比较 optimizer，很少直接在真实 repo 上比较 agent。

所以，如果我们的研究目标是回答一个非常具体的问题：

`在不改变方法、预算有限的前提下，agent 到底能不能比别人更高效地把超参数调好？`

那么就需要一个更聚焦的 benchmark。

### 3. 你的 benchmark 在回答什么问题

你的 benchmark 可以被理解成在回答以下四个问题：

1. 当方法固定时，agent 是否还能稳定提升模型性能？
2. 在固定预算下，agent 的调参效率是否有显著差异？
3. 在真实 repo 环境中，agent 是否能理解已有训练接口、配置结构和评测脚本，并据此做有效搜索？
4. 如果我们只允许 agent 调超参数，那么现有 frontier agent 的上限到底在哪里？

这几个问题的共同点是：

- 它们比“agent 会不会做 ML”更细。
- 但又比“某个 optimizer 在某个 search space 上好不好”更贴近真实工程。

### 4. 为什么“固定方法，只调超参数”是一个好设定

这个设定的优点非常明显：

- `更公平`：不同 agent 不会因为擅长大改代码而占便宜。
- `更可比`：每个系统面对的是同一个方法、同一个 repo、同一类预算约束。
- `更可归因`：性能提升更大概率来自调参策略，而不是方法创新。
- `更现实`：很多工业场景并不允许 agent 随便重写 pipeline，但允许它改 config、改训练参数、改搜索策略。
- `更适合预算研究`：当 action space 被收窄以后，“每一次试验值不值得”就更容易被量化。

### 5. 你可以如何讲这个动机

如果你想用比较自然的口头表达，我建议这样说：

“我们关注的不是 agent 能不能发明新模型，而是它能不能在真实 repo 里，像一个熟练工程师一样，在有限预算下把已有方法调到更好。这个问题很重要，因为在很多现实场景中，真正高频、可落地、也最先创造价值的，并不是提出新方法，而是高效地做超参数调优。现有 benchmark 往往把调参、改代码、换方法混在一起测，所以我们想把这件事单独抽出来，做一个更干净、更可归因的 benchmark。” 

### 6. Preliminary 的结论

这一部分最后可以收成一句话：

`我们做这个 benchmark，不是因为现有工作不重要，而是因为现有工作已经提示我们：agent 在 ML 上最先显现、也最值得精细测量的能力之一，就是超参数调优。`

---

## 论文展开

下面的讲法按三组来组织：

1. `Agent 做 ML benchmark`
2. `Agent 做 HPO 的方法`
3. `传统 HPO benchmark`

这样讲的好处是逻辑清楚：

- 第一组说明大方向已经成立。
- 第二组说明“agent 做 HPO”已经有人在做。
- 第三组说明 benchmark protocol 该怎么设计。

---

## 一、Agent 做 ML 的 Benchmark

### 1. MLGym

论文：
[MLGym: A New Framework and Benchmark for Advancing AI Research Agents](https://arxiv.org/abs/2502.14499)

一句话概括：

`MLGym` 想测的是，AI agent 能不能在真实、开放式的 ML research task 上持续做出 baseline improvement。

为什么重要：

- 这篇论文很关键，因为它已经明确告诉我们，当前 agent 在 ML 任务上的提升，很多时候主要来自更好的超参数，而不是提出了全新方法。
- 这几乎是你做 benchmark 的直接动机来源。

它做了什么：

- 提出了一个 `Gym-style` 的 AI research agent 环境。
- 发布了 `MLGym-Bench`，包含 13 个开放式研究任务。
- 任务覆盖 CV、NLP、RL、博弈论、SAT 等。
- agent 可以访问代码、shell、数据和工具，做的是完整实验循环，而不是答静态题。
- 论文还定义了 capability levels，把当前评测重点放在 `Level 1: Baseline Improvement`。

它怎么评测：

- 不是简单看 pass/fail。
- 而是看 agent 最终把 baseline 提高了多少。
- 用 performance profile 和 AUP 这类跨任务聚合指标，统一比较不同模型。

主要结论：

- frontier 模型已经能在不少任务上提升 baseline。
- 但提升的来源更多是调参数、改训练细节、扩大试验覆盖，而不是提出真正新颖的研究思路。

这篇论文和你的关系：

- 这是你汇报里最应该强调的一篇。
- 它说明“agent 在 ML 上的有效能力”不一定首先表现为方法创新，而是表现为更系统的实验与调参。
- 你的 benchmark 相当于把 MLGym 里隐含存在的 `hyperparameter improvement` 能力单独拿出来，做更可控的测量。

你可以这样讲：

“MLGym 的价值在于，它已经把开放式 ML research task 做成了标准 benchmark。但更有意思的是，它的实验结论提示我们，agent 当前最稳定的收益很多来自调参，而不是方法创新。所以我们进一步问：如果把方法固定住，只测调参，这种能力到底能被多清楚地刻画出来？” 

### 2. MLE-Dojo

论文：
[MLE-Dojo: Interactive Environments for Empowering LLM Agents in Machine Learning Engineering](https://arxiv.org/abs/2505.07782)

一句话概括：

`MLE-Dojo` 想把 MLE agent 的评测从静态 benchmark 推进到真正可交互、可执行、可训练的环境。

为什么重要：

- 它证明了 ML engineering benchmark 不一定只能是“给一道题，交一份答案”。
- agent 可以在环境里反复试验、debug、训练、再提交。

它做了什么：

- 提出一个 `Gym-style`、`interactive`、`fully executable` 的 MLE 环境。
- 基于 `200+` 个真实 Kaggle challenge 构建数据集。
- 包含 `150` 个训练任务和 `50` 个评测任务。
- 显式覆盖 data processing、architecture search、hyperparameter tuning、debugging 等能力。

主要贡献：

- 不只提供 benchmark，还提供 agent training environment。
- 任务规模大，而且带 train/eval split，适合后续做 SFT 或 RL。
- 把“交互式 MLE”做成了一个明确的研究方向。

主要结论：

- 多步交互能帮助 agent 在真实 MLE task 上取得进展。
- 但在长时程规划、复杂错误恢复和持续稳定提升上仍有限。
- 论文还专门分析了 cost-performance 关系。

这篇论文和你的关系：

- 它说明“交互式 ML 环境”这条路线已经很成熟。
- 但它的 scope 很宽，同时测 data processing、debugging、架构搜索和 HPO。
- 你的 benchmark 更聚焦，只看固定方法下的 HPO，因此可归因性更强。

你可以这样讲：

“MLE-Dojo 告诉我们，agent 在 MLE 里应该被放进可交互环境，而不是静态题库里。但它测的是全流程能力，我们进一步想 isolate 出其中最关键也最现实的一部分，也就是固定方法下的调参能力。” 

### 3. MLAgentBench

论文：
[MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation](https://arxiv.org/abs/2310.03302)

一句话概括：

`MLAgentBench` 是较早系统化评测“语言 agent 能不能做 ML experimentation”的工作。

它做了什么：

- 让 agent 在真实任务里读代码、改代码、运行实验、检查结果并继续迭代。
- benchmark 覆盖标准数据集、Kaggle challenge 和较新的研究任务。
- 不只记录最终结果，也记录全过程 trace。
- 评价维度包括 competence、reasoning 和 efficiency。

为什么重要：

- 这篇文章很早就指出，ML experimentation 是一个不同于普通代码补全或单函数修复的问题。
- 它强调的是完整实验循环，而不是孤立代码片段。

主要结论：

- frontier 模型在一部分任务上能做出改进。
- 但成功率波动很大。
- 常见失败包括 hallucination、debugging 失败和长程规划问题。

这篇论文和你的关系：

- 你可以把它作为“agent 做 ML 实验 benchmark”的早期代表。
- 但它不限制 agent 只能调超参数，agent 仍然可以改 pipeline、改方法。
- 你做的事情是在此基础上进一步缩窄 action space，使性能提升更容易解释。

你可以这样讲：

“MLAgentBench 已经证明，把 ML experimentation 本身作为 benchmark 是有意义的。但它的问题空间太宽，导致一旦 agent 成功，我们很难判断它到底是靠调参赢的，还是靠改方法赢的。我们的 benchmark 想解决的正是这个归因问题。” 

### 4. MLE-bench

论文：
[MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering](https://arxiv.org/abs/2410.07095)

一句话概括：

`MLE-bench` 把 agent 放到一个离真实 Kaggle workflow 很近的离线比赛环境里，直接看它能不能达到人类比赛成绩。

它做了什么：

- 构建了 `75` 个 Kaggle competition 组成的 benchmark。
- 每个任务都包含比赛描述、数据集、本地 grading code 和 leaderboard 参照。
- 用 Kaggle medal 规则把 agent 成绩映射到 bronze、silver、gold。
- 系统分析了 runtime、pass@k、resource scaling、contamination 和 rule-breaking。

为什么重要：

- 这篇论文最大的价值是评测协议非常真实。
- 它不是抽象地说“分数更高了”，而是把 agent 放回真实人类 competition 的坐标系里。
- 它也很重视预算问题和多次尝试的收益。

主要结论：

- 最好的设置是 `o1-preview + AIDE`。
- 在 `16.9%` 的比赛上达到至少 bronze medal。
- 更多 runtime、更多尝试次数通常能带来更好结果。
- 但真正难的地方仍然是 debug 和从错误路径中恢复。

这篇论文和你的关系：

- 这是你写“预算受限 benchmark”时最应该引用的工作之一。
- 它说明预算、尝试次数、资源扩展本身就是 agent 评测的重要维度。
- 但它测的是 end-to-end ML engineering，而不是 method-fixed HPO。

你可以这样讲：

“MLE-bench 很重要，因为它让我们看到，agent 在真实 ML engineering 中的表现高度依赖预算和尝试次数。我们和它的不同点在于，它测的是完整 Kaggle 流程，而我们只关心在固定方法下，agent 如何把每一次 trial 用得更值。” 

### 5. ML-Dev-Bench

论文：
[ML-Dev-Bench: Comparative Analysis of AI Agents on ML development workflows](https://arxiv.org/abs/2502.00964)

一句话概括：

`ML-Dev-Bench` 评测的是 agent 在真实 ML development workflow 各个子环节里的能力差异。

它做了什么：

- 设计了 `30` 个 task。
- 覆盖 dataset handling、model training、debugging、model implementation、API integration、model performance improvement。
- 用 `Calipers` 做评测。
- 比较了 ReAct、OpenHands、AIDE 等 scaffold。

为什么重要：

- 这篇论文把“ML 工作流”拆成多个可比较子任务，而不是只给一个整体分数。
- 这样就能更清楚地看到 agent 到底擅长哪里，不擅长哪里。

主要结论：

- OpenHands-Sonnet 和 ReAct-Sonnet 的整体成功率相对最好。
- 在 dataset handling、API integration、部分 training/debugging 上，agent 已经能做不少事。
- 但在 `Model Performance` 这种开放式性能提升任务上，几乎所有 agent 都接近 `0%`。

这篇论文和你的关系：

- 它提供了一个非常强的论据：开放式性能改进是 agent 的明显短板。
- 你的 benchmark 可以被理解成把这个最难的子类再进一步提纯，专门研究其中的 HPO 部分。

你可以这样讲：

“ML-Dev-Bench 的结果非常有启发性，因为它不是说 agent 哪都不行，而是告诉我们：一旦任务变成开放式性能提升，现有 agent 的成功率会急剧下降。我们的 benchmark 可以被看作专门把这一类任务里的 HPO 部分抽出来做精细分析。” 

### 6. ML-Bench

论文：
[ML-Bench: Evaluating Large Language Models and Agents for Machine Learning Tasks on Repository-Level Code](https://arxiv.org/abs/2311.09835)

一句话概括：

`ML-Bench` 关心的是 agent 和 LLM 能不能在真实 ML repo 上理解上下文并完成 repository-level 任务。

它做了什么：

- 基于 `18` 个 GitHub ML repository 构造 benchmark。
- 共 `9,641` 个样本。
- 同时有 `ML-LLM-Bench` 和 `ML-Agent-Bench` 两种设定。
- 任务大量来自 README、argument、script interface 和多文件上下文。

为什么重要：

- 你的 benchmark 也是 repo-level 的，因此这篇论文非常相关。
- 它说明 repo-scale context 并不是普通 coding benchmark 能覆盖的。
- agent 要做对事情，必须理解训练脚本接口、配置组织方式以及 repo 内部依赖。

主要结论：

- GPT-4o 在 LLM setting 和 agent setting 上都表现不错。
- repo-level 任务里，README、脚本调用和 bash orchestration 是关键难点。

这篇论文和你的关系：

- 它不是性能优化 benchmark，而是 repo-level ML task benchmark。
- 但它能很好地支撑你的一个核心设计点：`为什么要在真实 repo 上测，而不是只在抽象配置空间上测。`

你可以这样讲：

“ML-Bench 说明，repo 级任务本身就是一类独立难题。对于调参 agent 来说，这一点同样成立，因为它不是在一个抽象搜索空间里优化，而是要先理解 repo 提供了什么训练入口、哪些参数可调、怎么启动和评估。” 

### 7. TML-Bench

论文：
[TML-Bench: Benchmark for Data Science Agents on Tabular ML Tasks](https://arxiv.org/abs/2603.05764)

一句话概括：

`TML-Bench` 是一个把预算维度明确写进 protocol 的 data science agent benchmark。

它做了什么：

- 聚焦 tabular ML / Kaggle 风格任务。
- 在 `4` 个 competition 上评测 `10` 个开源模型。
- 明确设置 `240s`、`600s`、`1200s` 三档预算。
- 每个组合运行 `5` 次，关注稳定性。

为什么重要：

- 它最大的贡献不是任务规模，而是评测方式。
- 它非常清楚地把“时间预算”当作 benchmark 的核心自变量，而不是附加说明。

主要结论：

- 更大的预算通常会带来更好的表现。
- 但预算扩展并不总是平滑或稳定的。
- 结果需要同时看平均表现、成功率和波动性。

这篇论文和你的关系：

- 如果你想强调自己的 benchmark 是 `budget-aware` 的，TML-Bench 很值得引用。
- 虽然它不是 repo-level，也不是 HPO-only，但它已经把预算敏感评测做得很明确。

你可以这样讲：

“TML-Bench 的启发在于，它把 budget-sensitive evaluation 变成了协议的一部分，而不是实验附录。对于我们这种固定预算下比较调参能力的 benchmark 来说，这种设计思路非常值得借鉴。” 

---

## 二、Agent 做 HPO 的方法论文

### 8. AgentHPO

论文：
[Large Language Model Agent for Hyper-Parameter Optimization](https://arxiv.org/abs/2402.01881)

一句话概括：

`AgentHPO` 是最直接的 “LLM agent 做超参数优化” 论文。

它做了什么：

- 提出一个双 agent 结构。
- `Creator` 负责根据历史结果和任务背景生成下一轮超参数配置。
- `Executor` 负责真正运行实验并记录日志。
- 系统保留实验日志，最后还能输出可解释的优化总结。

为什么重要：

- 这篇论文直接告诉我们，把 HPO 交给 agent 做，本身已经是一个成立的问题。
- 它也说明，LLM 在这里不只是写代码，还可以做 trial-to-trial 的策略更新。

主要结论：

- 在 `12` 个任务上，AgentHPO 明显优于 random search。
- 在部分任务上超过人类最佳 trial。
- GPT-4 明显优于 GPT-3.5。

这篇论文和你的关系：

- 这是你的 related work 里必须重点讲的一篇。
- 但它更像是一个 `method paper`，不是一个统一 benchmark。
- 你的 benchmark 可以为这类方法提供公平、统一、repo-level、budget-controlled 的评测平台。

你可以这样讲：

“AgentHPO 的意义在于，它已经证明了 agent 做 HPO 是可行的，而且并不只是随机乱试。但它研究的是一个具体系统，而我们更关心的是如何设计统一 benchmark，去评测不同 agent 在真实 repo 上做 HPO 的能力差异。” 

### 9. BudgetMLAgent

论文：
[BudgetMLAgent: A Cost-Effective LLM Multi-Agent System for Automating Machine Learning Tasks](https://arxiv.org/abs/2411.07464)

一句话概括：

`BudgetMLAgent` 关注的是，怎么让 ML agent 在成本更低的情况下依然保持较强表现。

它做了什么：

- 提出一个多 agent、低成本优先的系统。
- 关键组件包括 profiling、retrieval、LLM cascade、ask-the-expert。
- 先用便宜模型做大部分工作，必要时再升级到更强更贵的模型。
- 在 MLAgentBench 上做评测。

为什么重要：

- 它把 `cost` 从一个被动统计量，变成了系统设计目标。
- 这和你 benchmark 的“有限预算”主题高度一致。

主要结论：

- 单纯便宜模型的表现不够好。
- 但通过 cascade 和 expert 调用，系统可以在成本显著降低的同时保持较强 performance。
- 论文报告了相对昂贵单 agent 的大幅成本节约。

这篇论文和你的关系：

- 它说明预算不是次要问题，而是 agent 设计中的核心约束。
- 你的 benchmark 则进一步把预算约束标准化，变成比较不同 agent 的统一 protocol。

你可以这样讲：

“BudgetMLAgent 关注的是怎么在成本受限时做系统设计，而我们的 benchmark 关注的是怎么在预算受限时做公平评测。两者的共同点是，都把 budget 当作一等公民。” 

---

## 三、传统 HPO Benchmark / Challenge

### 10. HPOBench

论文：
[HPOBench: A Collection of Reproducible Multi-Fidelity Benchmark Problems for HPO](https://arxiv.org/abs/2109.06716)

一句话概括：

`HPOBench` 是传统 HPO benchmark 里非常经典的一篇，重点是可复现和多保真。

它做了什么：

- 收集并统一了大量 benchmark family。
- 总数超过 `100` 个 multi-fidelity benchmark problem。
- 提供 raw、surrogate、tabular 多种形式。
- 采用容器化保证可复现性。
- 同时支持多 fidelity dimension 和多指标评测。

为什么重要：

- 它不是 agent benchmark，但它非常清楚地告诉我们，HPO benchmark 该如何设计才更可信。
- 例如 heterogeneity、reproducibility、multi-fidelity 都不能忽视。

主要结论：

- 不同 benchmark family 的异质性很大。
- 单一 benchmark 很容易高估某一类 optimizer。
- benchmark 设计本身会影响对方法优劣的判断。

这篇论文和你的关系：

- 你的 benchmark 虽然是 agent benchmark，但在 protocol 上可以大量借鉴 HPOBench。
- 特别是对可复现性、预算控制和任务多样性的强调。

你可以这样讲：

“HPOBench 的价值不在于它和我们的问题完全一样，而在于它为 HPO benchmark 提供了一套设计原则。我们虽然测的是 agent，但只要 benchmark 涉及超参数优化，这些原则就仍然适用。” 

### 11. YAHPO Gym

论文：
[YAHPO Gym -- An Efficient Multi-Objective Multi-Fidelity Benchmark for Hyperparameter Optimization](https://arxiv.org/abs/2109.03670)

一句话概括：

`YAHPO Gym` 关注的是如何用高效、faithful 的 surrogate benchmark 来大规模评测 HPO 方法。

它做了什么：

- 提供 `14` 个 scenario、`700+` 个多保真 HPO problem。
- 支持 single-objective 和 multi-objective 设定。
- 同时比较了多种 single-objective 和 multi-objective optimizer。

为什么重要：

- 它不只是扩展规模，更重要的是讨论 benchmark fidelity。
- 论文指出，某些 tabular benchmark 可能会给出不忠实的 optimizer 排名。

主要结论：

- surrogate benchmark 不只是更快，还可能在方法排序上更可靠。
- 评测效率和评测真实性之间需要仔细平衡。

这篇论文和你的关系：

- 如果你以后想为自己的 repo benchmark 做一个 cheaper proxy，YAHPO Gym 是很重要的参考。
- 它提醒你：不能只追求省钱，还要保证 method ranking 不失真。

你可以这样讲：

“YAHPO Gym 给我们的启发是，benchmark 不只是任务越多越好，关键还在于它是不是 faithful。即使未来我们想做更便宜的 replay 或 surrogate 版本，也需要验证排序是否仍然可信。” 

### 12. HPO-B

论文：
[HPO-B: A Large-Scale Reproducible Benchmark for Black-Box HPO based on OpenML](https://arxiv.org/abs/2106.06257)

一句话概括：

`HPO-B` 是一个非常大规模的 black-box HPO benchmark，尤其强调 transfer setting。

它做了什么：

- 基于 OpenML 构建大规模 meta-dataset。
- 覆盖 `176` 个 search space、`196` 个 dataset。
- 总计 `6.4M` 次 hyperparameter evaluation。
- 明确支持 non-transfer 和 transfer HPO 两种设定。

为什么重要：

- 它把 transfer HPO 从零散实验推进到了大规模、标准化比较。
- 这说明 HPO benchmark 不一定只能围绕单任务，而可以研究跨任务迁移。

主要结论：

- transfer HPO 方法整体上优于 non-transfer baseline。
- 评测时需要同时看 regret、rank 和 CD diagram，而不是只看单一数字。

这篇论文和你的关系：

- 如果你未来扩展 benchmark，研究 agent 能否利用跨 repo 的历史调参经验，HPO-B 是最重要的传统参照之一。
- 即使当前不做 transfer，这篇也能帮助你说明 protocol 要多指标、要大规模。

你可以这样讲：

“HPO-B 说明，一旦 benchmark 足够大，我们就不只是比较单任务上的最好结果，而是能研究迁移、泛化和元学习。对 agent benchmark 来说，这也是一个很自然的未来方向。” 

### 13. Bayesian Optimization is Superior to Random Search for Machine Learning Hyperparameter Tuning

论文：
[Bayesian Optimization is Superior to Random Search for Machine Learning Hyperparameter Tuning: Analysis of the Black-Box Optimization Challenge 2020](https://arxiv.org/abs/2104.10201)

一句话概括：

这篇论文分析的是 `Black-Box Optimization Challenge 2020`，重点在 challenge protocol 和真实 HPO 任务上的方法比较。

它做了什么：

- 用真实 ML tuning task 构建 challenge。
- 采用 practice leaderboard、hidden feedback leaderboard、hidden final leaderboard 三层结构。
- final leaderboard 只评一次，降低 overfitting leaderboard 的风险。
- 要求方法开源，并禁止 final evaluation 中的人类在线干预。

为什么重要：

- 这篇论文最强的地方不是某个具体 optimizer，而是它的评测协议。
- 它把 hidden test、single-shot final eval、固定预算、开源提交这些关键设计都说得很清楚。

主要结论：

- 多数队伍显著超过 random search。
- 相当一部分队伍超过强基线 TuRBO。
- 结果表明，在真实 ML HPO 上，Bayesian optimization 确实优于随机搜索。

这篇论文和你的关系：

- 如果你想把 benchmark 设计得更像 challenge，这篇非常值得借鉴。
- 特别适合借它来说明为什么需要 hidden test repo、固定预算和统一最终评测。

你可以这样讲：

“这篇论文提醒我们，一个好的 benchmark 不只是任务集合，还包括严谨的 protocol。尤其是 hidden evaluation、单次 final test 和固定预算，这些设计会直接决定 benchmark 是否容易被投机。” 

---

## 如何把这些论文串成一场汇报

### 一种自然的讲法

你可以按下面这个逻辑顺序讲：

1. 先讲 `MLGym`
2. 再讲 `MLE-Dojo`、`MLAgentBench`、`MLE-bench`、`ML-Dev-Bench`、`ML-Bench`、`TML-Bench`
3. 接着讲 `AgentHPO` 和 `BudgetMLAgent`
4. 最后讲 `HPOBench`、`YAHPO Gym`、`HPO-B`、`BBO Challenge`

这个顺序的优点是：

- 先用 MLGym 定义问题
- 再用一系列 agent benchmark 说明领域已经成熟
- 再用 AgentHPO 说明“agent 做 HPO”不是空想
- 最后用传统 HPO benchmark 说明 benchmark protocol 应该怎么设计

### 每一段的过渡句

从 Preliminary 到相关工作：

“既然我们认为超参数调优是 agent 在 ML 里一个值得被单独测量的核心能力，那么接下来就要看现有工作分别做到了哪一步，还缺什么。” 

从 Agent benchmark 过渡到 AgentHPO：

“前面这些工作说明，agent 做 ML 实验和工程已经是成立的问题。接下来更具体的问题是，agent 能不能把 HPO 本身做好？” 

从 AgentHPO 过渡到传统 HPO benchmark：

“如果说 AgentHPO 这类工作证明了 agent 可以做 HPO，那么传统 HPO benchmark 的文献则在回答另一个问题：这种能力应该如何被严谨评测？” 

从 related work 收束到你的 benchmark：

“综合这些工作可以看到，现有文献已经分别研究了 ML agent、LLM-based HPO 和传统 HPO benchmark，但仍然缺少一个 repo-level、method-fixed、budget-controlled 的 agent HPO benchmark。我们的工作正是想补上这块空白。” 

---

## 最后怎么落到你的 benchmark

你最后可以用三句话把全场收住：

第一句：

`现有 agent benchmark 已经说明，agent 能在真实 ML 环境里做实验和改进。`

第二句：

`现有 HPO/agent-HPO 工作也说明，超参数调优本身是一个清晰、重要、而且可以被系统化研究的问题。`

第三句：

`但目前仍然缺少一个专门面向真实 repo、固定方法、预算受限场景的 benchmark，用来干净地评测 agent 的超参数调优能力，这正是我们想做的事情。`

---

## 如果你时间有限，最值得重点讲的 6 篇

如果你的汇报时间比较短，我建议重点讲下面 6 篇：

- `MLGym`
- `MLE-bench`
- `ML-Dev-Bench`
- `AgentHPO`
- `HPOBench`
- `HPO-B`

它们分别对应：

- 为什么这个问题值得做
- 为什么预算很重要
- 为什么开放式性能提升很难
- 为什么 agent 做 HPO 是成立的
- 为什么 benchmark protocol 要严谨
- 为什么未来可以扩展到 transfer / meta-HPO

