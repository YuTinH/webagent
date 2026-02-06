# Web Agent Dynamic Suite V2: 持续学习与任务相关性深度大纲

本文档记录了项目在迈向顶级学术会议（如 NeurIPS, ICLR, ICML）过程中，关于 **持续学习 (Continual Learning, CL)** 和 **任务相关性 (Task Relatedness)** 的核心设计哲学与理论框架。

---

## 🚀 1. 核心愿景：从“操作员”到“数字社会生存者”

传统的 Web Agent Benchmark（如 WebArena, Mind2Web）主要考察 Agent 的**原子操作能力**（点击、输入）。而本项目的核心愿景是将 Web 环境建模为一个 **Stateful（有状态的）** 且 **Evolving（动态演化的）** 的数字社会。

在这个世界里，Agent 的目标不仅仅是完成孤立的任务，而是作为一名“长期的数字公民”去**生存、规划并持续进化**。

---

## 📊 2. 任务相关性 (Task Relatedness) 的三个维度

为了支持 CL 研究，我们定义了三个递进的任务相关性层级，这在论文中可以作为核心 Contribution：

### Level 1：显式依赖 (Explicit Dependency - Skill Chaining)
*   **现象**: Task B 的执行前提必须是 Task A 的成功输出。
*   **案例**: `A2 (办银行卡)` -> `B1 (在线购物)`。
*   **CL 价值**: 验证 Agent 构建和维护“工具链”的能力。如果不具备长期记忆，Agent 在执行 B1 时会忘记 A2 中获得的支付凭证。

### Level 2：隐式约束 (Implicit Constraint - Context Adaptation)
*   **现象**: Task A 的决策不影响 Task B 的可执行性，但改变了其**最优策略**或**奖励函数**。
*   **案例（蝴蝶效应）**: `A1 (租房选址)` -> `E1 (通勤规划)`。
    *   住在“中央大街”（市中心）时，打车是最优解（快且不贵）。
    *   住在“阳光海岸”（郊区）时，打车费暴涨，地铁变为最优解。
*   **CL 价值**: 考察 **上下文感知的策略自适应 (Context-Aware Policy Adaptation)**。Agent 必须学会在不同环境下灵活调整学到的技能，而非无脑复用。

### Level 3：知识迁移 (Knowledge Transfer - Meta Learning)
*   **现象**: 从 Task A 获得的抽象模式可以加速 Task B 的推理。
*   **案例**: `Z3 (实时拍卖)` -> `Z6 (智能客服)`。
    *   在拍卖中学会的“实时监测与等待”概念，可以迁移到客服对话中处理异步回复。
*   **CL 价值**: 验证 Agent 的 **元学习 (Meta-Learning)** 和跨域泛化能力。

---

## 🦋 3. 全局蝴蝶效应 (Global Butterfly Effect) 的实现逻辑

为了避免组合爆炸（$O(N^2)$ 的硬编码），我们采用了基于**“世界属性总线”**的设计：

1.  **属性化 (Attribute-Based)**: 任务修改的是全局属性（如 `LocationTier`, `HealthStatus`, `CreditScore`）。
2.  **消费化 (Consumption-Based)**: 后续任务读取这些属性并动态调整页面内容或 API 返回值。
3.  **验证逻辑**:
    *   **微观验证 (Task Level)**: 子任务是否完成。
    *   **宏观验证 (Scenario Level)**: Agent 的选择是否与前序任务建立的约束**保持一致 (Consistency)**。

---

## 📝 4. 剧情分 (Scenario Score) 与评估创新

我们提出了一种**混合评估模型**，专门用于衡量持续学习的质量：

*   **基础分 (Base Score)**: 完成原子任务的奖励。
*   **剧情奖励分 (Scenario Bonus)**: 如果 Agent 的行为符合长程上下文的“最优解”，则给予额外奖励。
    *   *示例*: 在“贫穷剧本”下选择廉价外卖，额外奖励 +5 分。这证明了 Agent 具备真正的“智能理解”而非简单的“流程执行”。

---

## 🎓 5. 学术叙事逻辑 (Thesis / Storyline)

在论文中，我们可以这样叙述：

1.  **Problem**: 现有的 Web Agent 测试集缺乏对长期状态依赖和环境动态演化的考察。
2.  **Observation**: 真实的 Web 交互是长程的，早期的决策（如地址选择）会像蝴蝶效应一样影响后续所有任务的代价。
3.  **Method**: 我们提出了 **Dynamic Suite V2**，引入了虚拟时间系统、世界触发器和基于属性的全局依赖引擎。
4.  **Experiment**: 展示一个 Agent 即使完成了所有单项操作，如果它不能根据 A1 的选择调整 E1 的策略，它的“持续学习表现”依然是低分的。
5.  **Conclusion**: 一个真正的智能体必须能够管理长期的、跨域的相关性。

---

## 🛠️ 6. 待完成的实证支持

为了支撑上述学术论点，后续需重点产出：
*   **对比数据**: 展示 Agent 在“无蝴蝶效应” vs “有蝴蝶效应”环境下的行为差异。
*   **记忆热图**: 可视化 Agent 在执行任务链时，对过去哪些任务的记忆调用频率最高。

---

*Web Agent Dynamic Suite V2 - 致力于定义下一代自主学习智能体的评测标准。*
