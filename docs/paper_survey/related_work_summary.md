# Agent 超参数调优 Benchmark 相关工作综述

这份笔记按两条主线整理：

1. `Agent/LLM 做 ML 实验或工程` 的 benchmark 与系统
2. `传统 HPO benchmark / challenge`，即不一定是 agent，但非常适合拿来对照你的评测协议

你的设定是：

- 多个高质量 repo
- agent 在固定预算下自主运行
- 不允许改方法，只允许调超参数
- 评测 agent 在“调参能力”而非“发明新方法”上的表现

就这个目标而言，最接近的前作是：

- `MLGym`
- `MLE-Dojo`
- `MLE-bench`
- `ML-Dev-Bench`
- `AgentHPO`
- `BudgetMLAgent`

其中又以 `MLGym` 和 `AgentHPO` 最值得重点引用：

- `MLGym` 直接指出当前 frontier agent 的提升往往主要来自更好的超参数，而不是提出新方法。
- `AgentHPO` 是最直接的“LLM/agent 做 HPO”方法论文。

## 一、Agent / LLM Benchmark 与系统

### 1. MLGym (2025)

论文：
[MLGym: A New Framework and Benchmark for Advancing AI Research Agents](https://arxiv.org/abs/2502.14499)

核心问题：

- 作者想评测的是 AI research agent 能否在真实、开放式 ML research 任务中做“基线改进”。
- 这和你的 benchmark 很接近，因为它不只看代码正确性，而是看 agent 是否能通过实验迭代把指标做上去。

方法 / benchmark 设计：

- 提出一个 `Gym-style` 的 AI research agent 环境。
- 发布 `MLGym-Bench`，包含 13 个开放式研究任务，覆盖 CV、NLP、RL、game theory、SAT 等。
- 任务允许 agent 访问代码、数据、shell、工具，并以多种 artifact 为评价对象，而不只是 unit test 或单个 CSV。
- 论文还定义了 capability levels，明确当前 benchmark 主要评估 `Level 1: Baseline Improvement`。
- 使用统一的 performance profile / AUP 指标，对不同任务上的 agent 表现做跨任务聚合比较。

主要贡献：

- 把“AI research agent benchmark”正式做成了 Gym 环境，便于以后用 RL / curriculum / open-ended learning 训练 agent。
- 证明了“开放式 ML 研究任务”可以被标准化评测，而不是只能靠静态 coding benchmark。
- 给出了多模型实证：Claude-3.5-Sonnet、Llama-3.1 405B、GPT-4o、o1-preview、Gemini-1.5 Pro。

关键实验结论：

- 当前 frontier 模型确实能提升给定 baseline。
- 但提升通常来自 `更好的超参数`，而不是新 hypothesis、新算法、新架构。
- 这和你要测的“agent 是否擅长调参”高度同向。

对你 benchmark 的启发：

- 这是最直接支持你论文动机的引用之一，因为它明确把“改进主要来自调参”说清楚了。
- 你可以把自己的 benchmark 定位成：`把 MLGym 中隐含存在的 hyperparameter-improvement 能力，单独抽出来做更干净、更可控、更预算敏感的测量。`

### 2. MLE-Dojo (2025)

论文：
[MLE-Dojo: Interactive Environments for Empowering LLM Agents in Machine Learning Engineering](https://arxiv.org/abs/2505.07782)

核心问题：

- 现有 benchmark 往往是静态的，或者只允许一次性提交，不能很好反映真实 MLE workflow 里的反复试验、debug、再训练。

方法 / benchmark 设计：

- 提出一个 `Gym-style`、`interactive`、`fully executable` 的 MLE agent 环境。
- 基于 `200+` 个真实 Kaggle challenge 构建任务池。
- 数据集里有 `150` 个训练任务和 `50` 个评测任务。
- 覆盖 tabular、CV、NLP、time series 等多种场景。
- 任务显式包含 data processing、architecture search、hyperparameter tuning、code debugging。
- 环境提供 observation/action 接口、标准化数据结构、真实反馈、可用于 SFT 和 RL 的 trajectory 采样。

主要贡献：

- 把 benchmark 从“静态单次做题”推进到了“可交互、可训练、可长期迭代”的 agent 环境。
- 规模很大，而且有训练集/测试集分离，这点对 agent 训练研究非常重要。
- 不只是 benchmark，也是一套 agent training infrastructure。

关键实验结论：

- 作者在 50 个 evaluation task 上评测了 8 个 frontier LLM。
- 模型能通过多步交互带来可观改进，但在长时程规划、复杂错误修复上仍明显受限。
- 论文还分析了成本与性能关系，以及 step-wise performance dynamics。

对你 benchmark 的启发：

- 它说明“交互式 MLE benchmark”已经成为清晰的研究方向。
- 但它的任务范围很宽，不专注于“只能调超参数”。
- 你的 benchmark 可以看作在它之上进一步做 `problem factorization`：把 ML engineering 中最可比、最可控的一部分，也就是 HPO，单独拉出来测。

### 3. MLAgentBench (2024)

论文：
[MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation](https://arxiv.org/abs/2310.03302)

核心问题：

- 想知道语言模型驱动的 agent 是否能完成 ML experimentation loop：读代码、改代码、运行实验、看结果、继续迭代。

方法 / benchmark 设计：

- 提出一套 open-ended ML experimentation benchmark。
- agent 可以执行文件读写、代码运行、结果检查等动作。
- benchmark 覆盖 canonical 数据集、Kaggle challenge 和较新的 research problem。
- 评价维度包括 competence、process/reasoning、efficiency。
- 论文同时实现了一个 LLM-based research agent，用于在环境中自动循环做实验。

方法细节：

- 任务以“task description + files/data/starter code”的形式给 agent。
- 环境会记录完整 interaction trace，既能看最终结果，也能分析中间行为。
- 作者强调过程可解释性，例如 hallucination、debugging failure、long-horizon planning failure。

主要贡献：

- 较早系统性提出“把 ML experimentation 本身作为 agent benchmark”。
- 不只看最终分数，也看 trace、reasoning 和效率。
- 为之后的 MLGym、MLE-Dojo、BudgetMLAgent 等工作提供了直接基础。

关键实验结论：

- Abstract 里写的是 `13` 个任务，正文里也出现了更细粒度的任务拆分；核心结论不受这个版本差异影响。
- Claude / GPT-4 类模型已能在部分任务上做出像样的改进，但成功率高度不稳定。
- 对新 Kaggle challenge 和 BabyLM 一类更新的任务明显更弱。
- 常见失败模式是 hallucination、debugging 失败、长程规划不稳定。

对你 benchmark 的启发：

- 这是“agent 做 ML experimentation”这条线的重要前作。
- 但它允许 agent 修改整个 pipeline，不限制“不能改方法”。
- 你的 benchmark 可以明确说明：相比 MLAgentBench，你进一步控制了 method space，使评测更聚焦、更可归因。

### 4. MLE-bench (2024 / ICLR 2025)

论文：
[MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering](https://arxiv.org/abs/2410.07095)

核心问题：

- 想评测 agent 在真实 ML engineering 上到底到了什么水平，并且希望能和人类 Kaggle 选手做直接比较。

方法 / benchmark 设计：

- 把 benchmark 设计成 `offline Kaggle competition environment`。
- 共 `75` 个 Kaggle competition，外加开发集。
- 每个任务包含：
  - competition description
  - dataset
  - local grading code
  - human leaderboard snapshot
- 用 Kaggle medal 规则做归一化，直接把 agent 成绩映射到 bronze / silver / gold。
- 作者还做了 resource scaling、contamination、plagiarism/rule-breaking 检查。

主要贡献：

- 建立了一个高度贴近真实 Kaggle workflow 的 agent benchmark。
- 把“agent 成绩”和“真实人类 leaderboard”放到同一坐标系里，这是非常强的评测设计。
- 不只给 main result，还系统分析了 runtime、hardware、pass@k 等资源扩展。

关键实验结论：

- 最佳 setup 是 `o1-preview + AIDE`。
- 该 setup 在 `16.9%` 的比赛上达到至少 bronze medal 水平。
- performance 随多次尝试、更多运行时长而提升，例如 pass@1 到 pass@8 会显著上升。
- 论文明确指出：agent 更容易在“可由已知套路解决”的比赛上得分，真正困难的是 debug 和从错误路径中恢复。

对你 benchmark 的启发：

- 如果你要写“有限预算”这一段，MLE-bench 非常关键，因为它已经把 runtime / pass@k / compute scaling 放进实验设计里。
- 不同点在于：MLE-bench 是 end-to-end ML engineering，允许更宽泛的 pipeline 改动；你的 benchmark 更强调 `fixed method + HPO only`。
- 因而你的 benchmark 可以被看作：在 MLE-bench 的“宏观 ML engineering 能力”下面，再单独测一层“纯调参能力”。

### 5. ML-Dev-Bench (2025)

论文：
[ML-Dev-Bench: Comparative Analysis of AI Agents on ML development workflows](https://arxiv.org/abs/2502.00964)

核心问题：

- 现有 benchmark 往往偏 Kaggle 或 repo code generation，但真实 ML 开发还包括 dataset handling、API integration、debugging、在现有模型上继续改造等 workflow。

方法 / benchmark 设计：

- 提供 `30` 个 carefully designed tasks。
- 任务类型包括：
  - dataset handling
  - model training
  - debugging
  - model implementation
  - API integration
  - model performance improvement
- 使用 `Calipers` 作为评测框架。
- 任务用 binary success/failure 评测，并带有 artifact-level validation。
- 比较了 ReAct、OpenHands、AIDE 三种 agent/scaffold。

主要贡献：

- 把 applied ML development workflow 系统化成一个 benchmark。
- 很适合作为“repo-level / workflow-level ML tasks”的前作。
- 论文的一大价值是失败分布很清晰，不会只给一个 aggregate score。

关键实验结论：

- OpenHands-Sonnet 约 `50%` 成功率，ReAct-Sonnet 约 `47%`，其余组合明显更低。
- 在 dataset handling、API integration、部分 model training/debugging 上成功率可观。
- 但 `Model Performance` 这一类开放式性能改进任务里，所有 agent 都接近 `0%`。

对你 benchmark 的启发：

- 这篇很能支持你的论点：`开放式性能提升` 本身是 agent 的薄弱项。
- 你的 benchmark 可以视作把 ML-Dev-Bench 里“Model Performance”这一最难类别进一步提纯成 HPO-only setting。

### 6. ML-Bench (2023/2024)

论文：
[ML-Bench: Evaluating Large Language Models and Agents for Machine Learning Tasks on Repository-Level Code](https://arxiv.org/abs/2311.09835)

核心问题：

- repo-level ML code understanding 明显比 function-level code generation 更难，尤其是在需要结合 README、参数说明、脚本接口和多文件关系时。

方法 / benchmark 设计：

- 基于 `18` 个 GitHub ML repository，构建 `9,641` 个标注样本。
- 设计两套设置：
  - `ML-LLM-Bench`：给 LLM 做 text-to-code / text-to-script
  - `ML-Agent-Bench`：让 agent 在 Linux sandbox 中端到端执行任务
- 重点是从 README、argument mining、script interfaces 里挖任务。

主要贡献：

- 把“ML repo 上的真实任务”正式 benchmark 化。
- 对你这种 `repo-level benchmark` 工作特别相关，因为它明确告诉你：repo-scale context 是单独的问题。
- 也提供了一个 agent-vs-LLM 的双设置。

关键实验结论：

- GPT-4o 在 ML-LLM-Bench 上 `Pass@5 > 50%`。
- 在更难的 ML-Agent-Bench 上，GPT-4o 报告了 `76.47%` success rate。
- 作者还专门分析了 hallucination、README 依赖、bash script generation、data leakage 等问题。

对你 benchmark 的启发：

- 这是最直接的 `repo-level ML benchmark` 相关工作之一。
- 但它主要测“理解已有 ML repo 并正确调用/修改”的能力，而不是固定方法下的性能优化。
- 你的 benchmark 可以借它来证明：repo 级设定本身就重要，而你进一步强调 `repo 级调参`。

### 7. TML-Bench (2026)

论文：
[TML-Bench: Benchmark for Data Science Agents on Tabular ML Tasks](https://arxiv.org/abs/2603.05764)

核心问题：

- tabular/Kaggle-style agent 是否真的可靠，尤其是在严格时间预算下。

方法 / benchmark 设计：

- 聚焦 tabular ML。
- 在 `4` 个 Kaggle competition 上评测 `10` 个开源模型。
- 显式设定 `240s / 600s / 1200s` 三档预算。
- 每个 model-task-budget 组合运行 `5` 次。
- 以“能否生成合法 submission + hidden private holdout 分数”作为核心判定。

主要贡献：

- 非常明确地把 `time budget` 放进 benchmark。
- 不只看平均分，还看 success rate 和 run-to-run variability。
- 这对 agent benchmark 很重要，因为很多系统在单次 lucky run 上能成功，但稳定性差。

关键实验结论：

- aggregate 下 MiniMax-M2.1 最好。
- 预算增大一般会提高平均表现，但 scaling 不是单调稳定的。
- 论文明确强调可靠性与可重复性，而不只是最高分。

对你 benchmark 的启发：

- 这是你写“预算敏感协议”时最适合引用的工作之一。
- 它不是 repo-level，也不是 HPO-only，但它证明了：`budget-aware evaluation` 已经是必要维度，而不是附加项。

### 8. AgentHPO (2024/2025)

论文：
[Large Language Model Agent for Hyper-Parameter Optimization](https://arxiv.org/abs/2402.01881)

核心问题：

- 传统 AutoML/HPO 依然存在 setup 复杂、trial 效率低、缺少可解释性的问题。
- 作者问：能否把 HPO 直接交给一个 LLM-based agent 来做，而且保留“像人类调参一样”的解释过程？

方法 / 系统设计：

- 提出 `AgentHPO`。
- 核心是两个 specialized agents：
  - `Creator`：理解任务背景、生成下一轮 HP 配置
  - `Executor`：实际运行实验、记录结果
- 输入可以是自然语言层面的 dataset/task background，而不只是复杂代码配置。
- 系统保留实验日志，并在优化结束后生成可解释的总结。

主要贡献：

- 比较早、也比较直接地提出了 `LLM agent-based HPO` 框架。
- 把“trial log + reasoning + explanation”纳入 HPO 产物，而不是只给最终最优点。
- 把 HPO 问题包装成更 human-like 的交互式流程。

关键实验结论：

- 在 `12` 个任务上评测，覆盖 CV、NLP、RecSys、tabular、GNN。
- AgentHPO 明显优于 random search，并在部分任务上超过人类最佳 trial。
- GPT-4 明显优于 GPT-3.5。
- 作者还分析了 optimization trajectory，指出 LLM 的搜索策略与随机搜索不同，更接近一种带启发式的试探过程。

对你 benchmark 的启发：

- 这是你 related work 里必须重点写的一篇，因为它直接研究“agent 做 HPO”。
- 但它更偏 `method paper`，不是严格的 benchmark paper。
- 你的 benchmark 可以视作给 AgentHPO 这类系统提供一个更公平、method-fixed、repo-level 的统一评测平台。

### 9. BudgetMLAgent (2024)

论文：
[BudgetMLAgent: A Cost-Effective LLM Multi-Agent System for Automating Machine Learning Tasks](https://arxiv.org/abs/2411.07464)

核心问题：

- 许多 ML agent 方法依赖昂贵的单一大模型，成本高，实际可扩展性差。

方法 / 系统设计：

- 提出一个 `cost-effective multi-agent ML system`。
- 核心组件包括：
  - profiling
  - retrieval from logs
  - LLM cascade
  - ask-the-expert calls
- 以低成本/免费模型（例如 Gemini）作为基座，在必要时调用 GPT-3.5/GPT-4 作为 cascade 或 expert。
- 在 MLAgentBench 上做评测。

主要贡献：

- 把“成本”正式作为 agent 设计目标，而不是事后统计。
- 提供一种 mixture-of-experts / cascade 式的工程化思路。
- 让“低价 agent 是否能接近高价单体模型”成为可实验验证的问题。

关键实验结论：

- 纯 no-cost/low-cost 单 agent 表现明显低于 GPT-4 / Claude。
- 但在 profiling + cascade + expert 之后，系统能显著提高成功率。
- 论文报告，相比 GPT-4 或 Claude 单 agent，BudgetMLAgent 在某些设置下同时做到显著成功率提升与 `90%-99%` 级别的成本下降。

对你 benchmark 的启发：

- 如果你要把“预算”写成 benchmark 第一公民，这篇是非常好的 related work。
- 它并不限制 agent 只能调超参数，但它为“预算受限下的 ML agent”提供了最直接的系统设计前作。

## 二、传统 HPO Benchmark / Challenge

### 10. HPOBench (2021)

论文：
[HPOBench: A Collection of Reproducible Multi-Fidelity Benchmark Problems for HPO](https://arxiv.org/abs/2109.06716)

核心问题：

- HPO 社区缺少真实、多样、低成本、标准化的 benchmark，尤其缺少适合多保真优化的 benchmark。

方法 / benchmark 设计：

- 提出 `HPOBench`。
- 包含 `7` 个已有 benchmark family 和 `5` 个新的 family。
- 总数超过 `100` 个 multi-fidelity benchmark problem。
- 通过容器化来保证 benchmark 的可复现性。
- 同时提供 `raw / surrogate / tabular` 多种形式，兼顾真实度与评测成本。
- 新 family 还支持多 fidelity dimension 和多 metric。

主要贡献：

- 把“可复现”和“可扩展”作为 benchmark 设计核心，而不只是提供一堆任务。
- 让多保真 HPO 可以系统化对比。
- 做了示范性的大规模实验，评测 `13` 个 optimizer、`6` 个 optimization tool。

关键实验结论：

- 论文用大规模比较展示了 advanced methods 与 random baseline、多保真方法与单保真方法的差异。
- 也展示了不同 benchmark family 的异质性，说明单一 benchmark 容易误导。

对你 benchmark 的启发：

- 这篇是“标准 benchmark 设计原则”的重要基础文献。
- 你的 benchmark 虽然是 agent benchmark，但在协议设计上可以借鉴它对 reproducibility、budget、heterogeneity 的强调。

### 11. YAHPO Gym (2021/2022)

论文：
[YAHPO Gym -- An Efficient Multi-Objective Multi-Fidelity Benchmark for Hyperparameter Optimization](https://arxiv.org/abs/2109.03670)

核心问题：

- 传统 tabular benchmark 在 HPO 排序上可能并不忠实，且不支持足够高效、多目标、多保真的实验。

方法 / benchmark 设计：

- 提出 surrogate-based HPO benchmark。
- 共 `14` 个 scenario，合计 `700+` 个 multi-fidelity HPO problem。
- 所有问题都支持 `multi-objective`。
- 作者同时给出 single-objective 与 multi-objective benchmark suite。
- 并比较 `7` 个 single-objective optimizer 和 `7` 个 multi-objective optimizer。

主要贡献：

- 把 surrogate-based、多目标、多保真三者合在一起，做成一个统一 benchmark。
- 不只是提供数据，还批判性比较了 surrogate benchmark 和 tabular benchmark 的差异。
- 论文的重要观点是：`tabular benchmark 可能给出不忠实的 optimizer 排名`。

关键实验结论：

- surrogate benchmark 不仅效率高，而且在 method ranking 上比一些 tabular benchmark 更可靠。
- 这篇对 HPO benchmark 社区影响很大，因为它不只是扩展任务数量，也在讨论 benchmark fidelity 本身。

对你 benchmark 的启发：

- 你的 benchmark 如果未来想做 “cheap replay / simulator / surrogate judge”，YAHPO Gym 是最合适的技术参照之一。
- 它也提醒你：如果以后想做 cheaper version，不能只追求快，还要验证 method ranking 是否 faithful。

### 12. HPO-B (2021)

论文：
[HPO-B: A Large-Scale Reproducible Benchmark for Black-Box HPO based on OpenML](https://arxiv.org/abs/2106.06257)

核心问题：

- transfer-learning HPO 论文很多，但缺少统一的大规模 meta-dataset 和统一 protocol，导致结果难以复现。

方法 / benchmark 设计：

- 从 OpenML 构建大规模 meta-dataset。
- 包含 `176` 个 search space、`196` 个 dataset、总计 `6.4M` hyperparameter evaluations。
- 明确区分 non-transfer 与 transfer HPO setting。
- 给出数据划分、protocol、initialization、regret/rank/CD-diagram 等推荐评测方式。

主要贡献：

- 把 transfer HPO 的 benchmark 从“小而散”的经验性比较，推进到大规模标准化比较。
- 数据量非常大，足以支撑 meta-learning / transfer-learning 研究。
- 还提供了 continuous variant。

关键实验结论：

- 论文显示 transfer HPO 方法整体优于非 transfer 方法。
- FSBO、RGPE 等方法在 aggregate comparison 中很强。
- 作者强调不要只报一种指标，而要同时看 regret、rank、critical difference。

对你 benchmark 的启发：

- 如果你未来想扩展出 “agent 是否能从多个 repo 的历史调参记录迁移到新 repo” 这一子任务，HPO-B 是最直接的传统参照物。
- 它在 protocol 上的严谨性也值得借鉴。

### 13. Black-Box Optimization Challenge 2020 分析论文 (2021)

论文：
[Bayesian Optimization is Superior to Random Search for Machine Learning Hyperparameter Tuning: Analysis of the Black-Box Optimization Challenge 2020](https://arxiv.org/abs/2104.10201)

核心问题：

- 想在真实 ML tuning task 上公平比较黑盒优化器，而不是停留在合成函数 benchmark。

方法 / benchmark / challenge 设计：

- 基于真实 ML 模型与数据集构造 optimization problem。
- 使用 local practice / hidden feedback leaderboard / hidden final leaderboard 三层结构。
- final leaderboard 只评一次，以降低对 leaderboard 的过拟合。
- baseline 包含多个开源 optimizer，以及 random search。
- submissions 必须开源，且 final evaluation 不允许 human-in-the-loop。

主要贡献：

- 这是一个很强的 `protocol paper`。
- 它把 hidden objective、single-shot final evaluation、practice-vs-test split、open-source submissions 等关键设计都讲清楚了。
- 对之后的 HPO benchmark / challenge 设计非常有启发。

关键实验结论：

- `61/65` 个队伍超过 random search baseline。
- `23` 个队伍超过最强 starter baseline TuRBO。
- 结果很有力地说明：在真实 ML HPO 问题上，Bayesian optimization / black-box optimization 明显优于 random search。

对你 benchmark 的启发：

- 如果你想让 agent benchmark 更像 challenge，而不是普通 benchmark，这篇最值得借鉴。
- 特别适合引用在 protocol 设计里：
  - hidden test repo / hidden seeds
  - 单次 final eval
  - 不允许人工在线调参
  - 预算固定

## 三、如何把这些工作映射到你的 benchmark

如果你要写论文里的 related work，我建议用下面这个 framing：

- `ML agent benchmark` 一类工作，关注 agent 能否完成完整的 ML experimentation / engineering workflow，例如 MLGym、MLE-Dojo、MLAgentBench、MLE-bench、ML-Dev-Bench、ML-Bench、TML-Bench。
- `LLM for HPO` 一类工作，直接探索 agent/LLM 是否能进行超参数优化，例如 AgentHPO、BudgetMLAgent。
- `Traditional HPO benchmark` 一类工作，提供标准化、多保真、多目标、transfer-learning protocol，例如 HPOBench、YAHPO Gym、HPO-B、BBO Challenge 2020 分析。

然后强调你的 benchmark 的独特点：

- 与 `MLGym / MLAgentBench / MLE-bench / ML-Dev-Bench` 相比，你把问题收窄到 `fixed method + HPO only`，从而能更干净地测量 agent 的调参能力。
- 与 `AgentHPO / BudgetMLAgent` 相比，你提供的是 `benchmark`，而不是特定系统。
- 与 `HPOBench / YAHPO / HPO-B` 相比，你关注的是 `agent 在真实 repo 上做 HPO`，而不是传统 optimizer 在抽象搜索空间上的表现。

## 四、建议你在论文里重点引用的组合

最核心的一组：

- `MLGym`：支撑“当前 agent 的提升主要来自调参而非新方法”
- `AgentHPO`：支撑“LLM/agent 做 HPO 已经是明确研究方向”
- `MLE-bench`：支撑“预算、Kaggle-style、真实 ML engineering 评测协议”
- `ML-Dev-Bench`：支撑“repo/workflow 级 applied ML task benchmark”
- `HPOBench` / `YAHPO Gym` / `HPO-B`：支撑“传统 HPO benchmark 与 protocol 背景”

如果只写一个简洁但有说服力的 related work 段落，我会优先放：

- MLGym
- MLE-bench
- AgentHPO
- HPOBench
- YAHPO Gym
- HPO-B

