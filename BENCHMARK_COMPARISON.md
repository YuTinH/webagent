# Benchmark 能力图谱与竞品对比分析

本文档详细拆解了 **Web Agent Dynamic Suite V2** 所考察的核心能力维度，并将其与当前主流的 Web Agent Benchmark（如 WebArena, Mind2Web）进行深度对比，阐述本项目的独特性与学术价值。

---

## 🧠 1. 能力考察图谱 (Capabilities Spectrum)

我们不仅仅考察 Agent 的“手眼协调”能力，更侧重于考察其作为“数字社会公民”的**认知与生存能力**。

### A. 基础层：感知与操作 (Perception & Grounding)
*   **多模态感知**: 不仅是 HTML 文本，还需要处理动态 UI 元素（Toast 弹窗、模态框、实时刷新的价格板）。
*   **精准交互**: 在复杂的表单（如 A2 开户）中进行精确的字段映射和数据录入。

### B. 进阶层：记忆与状态 (Memory & State)
*   **跨任务长程记忆**: 必须能够跨越数十个任务周期，检索并复用关键信息（如 A1 获得的地址、D6 设定的预算）。
*   **身份一致性 (Persona Consistency)**: 在 Bank, Gov, Shop 等不同站点间维持统一的数字身份。

### C. 核心层：时序与规划 (Temporal & Planning)
*   **异步任务管理**: 理解“时间流逝”的概念。例如 Z1 任务中，Agent 必须知道“下单后不能立刻收货，必须等待 3 天”。
*   **主动性与耐心**: 在 Z3 拍卖和 Z6 客服中，Agent 必须展现出观察环境变化并适时介入的能力，而非盲目操作。

### D. 高级层：适应与迁移 (Adaptability & Transfer)
*   **环境适应 (Context Adaptation)**: 面对“蝴蝶效应”（如 A1 选址导致的 E1 通勤费变化），Agent 能够动态调整决策策略（放弃打车改坐地铁）。
*   **异常鲁棒性**: 在 M 系列任务（丢卡、断供）中，展现出从错误状态中恢复的能力。
*   **跨域整合**: 在 Z4 任务中，打通“邮件”与“日历”的数据孤岛，完成非结构化到结构化数据的转换。

---

## ⚔️ 2. 竞品对比分析 (Comparative Analysis)

| 维度 (Dimension) | **WebArena / Mind2Web** | **VisualWebArena** | **Dynamic Suite V2 (Ours)** |
| :--- | :--- | :--- | :--- |
| **环境性质 (Environment)** | **静态快照 (Static Snapshot)**<br>任务间状态重置，环境无自主演化。 | **静态 + 视觉增强**<br>侧重视觉元素，但逻辑依然静态。 | **动态演化世界 (Evolving World)**<br>引入虚拟时间轴，世界状态随时间流逝而自动演变（如签证获批、利息到账）。 |
| **任务粒度 (Granularity)** | **原子级 (Atomic)**<br>单次交互，如“买这个杯子”。 | **原子级** | **终身级 (Lifelong)**<br>长链条任务（办卡->购物->理财），任务间存在长达数月的逻辑依赖。 |
| **因果关系 (Causality)** | **无 / 弱**<br>各任务相互独立。 | **无** | **全局蝴蝶效应 (Global Butterfly Effect)**<br>早期决策（如租房位置）会隐式地改变后期任务的难度和最优解（如通勤成本）。 |
| **交互模式 (Interaction)** | **单向指令**<br>人发指令，Agent 执行。 | **单向指令** | **双向/多轮博弈**<br>包含实时竞拍（与系统博弈）、客服对话（多轮自然语言交互）、双盲验证（手机验证码）。 |
| **考察核心 (Core Metric)** | **Grounding Success**<br>(点对了没？) | **Visual Understanding**<br>(看懂了没？) | **Survival & Adaptation**<br>(活下来了吗？活得好吗？) |

---

## 💎 3. 核心优势总结 (Unique Selling Points)

1.  **Time as a First-Class Citizen**: 我们是首个引入**虚拟时间系统**的 Web Agent Benchmark。这使得考察 Agent 的长期规划能力成为可能。
2.  **Consequences Matter**: 在我们的环境中，Agent 的错误（如乱花钱、泄露隐私）会有长期的负面后果（如信用分下降、账号被盗），这比单纯的 `True/False` 评分更具现实意义。
3.  **Rich Interconnectivity**: 我们打破了网站间的孤岛，构建了一个包含 Gov, Bank, Shop, Work 等 10+ 个站点的**互联生态**，真实模拟了人类的互联网生活。

---

*这份对比分析清晰地展示了 Dynamic Suite V2 在“持续学习”和“高拟真环境”方面的代际领先优势。*
