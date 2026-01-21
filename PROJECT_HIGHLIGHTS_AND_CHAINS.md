# Web Agent Dynamic Suite V2 - 项目亮点与任务链指南

本文档全面总结了 Web Agent Dynamic Suite V2 项目的技术特色、核心亮点以及推荐的测试任务链。本项目旨在构建一个高保真、长周期、具备动态演化能力的 Web Agent 仿真环境。

---

## ✨ 核心亮点 (Project Highlights)

### 1. 模块化与可扩展的后端架构
*   **重构的 Server**: 将庞大的单体 `server.py` 重构为基于 `task_handlers` 的模块化架构。每个任务族（A-M, Z）都有独立的处理程序，极大地提高了代码的可维护性和扩展性。
*   **状态驱动 (State-Driven)**: 所有交互均基于统一的 `env` 状态树（内存）和 `memory_kv`（持久化 SQLite），实现了前端 UI 与后端逻辑的完美解耦与同步。

### 2. 首创“虚拟时间与世界演化”系统
*   **时间旅行 (Time Travel)**: 引入 `time_utils` 和 `/api/debug/time_travel` 接口，允许 Agent 或测试脚本“快进”时间（如跳过 3 天、30 天）。
*   **世界触发器 (World Triggers)**: 实现了 `world_triggers.py`，模拟真实世界的后台进程。当时间流逝时，系统会自动触发状态变更，例如：
    *   **签证审批**: 提交申请 -> 等待 3 天 -> 自动变更为“已通过”。
    *   **物流配送**: 订单确认 -> 等待 2 天 -> 自动变更为“已送达”。
    *   **理财收益**: 存款 -> 等待 30 天 -> 余额自动增加利息。

### 3. 高级与跨域交互能力 (Advanced Interactions)
*   **跨应用工作流 (Cross-App Workflow)**: 实现了如“从邮件提取信息并创建日历事件”的任务，考察 Agent 在不同上下文间的信息搬运能力。
*   **双盲验证与安全 (2FA & Security)**: 实现了完整的“忘记密码 -> 接收模拟短信验证码 -> 重置密码 -> 登录”闭环，模拟真实的安全挑战。
*   **自然语言交互 (Conversational AI)**: 集成了智能客服聊天机器人，Agent 必须通过自然语言查询订单状态，而非简单的点击操作。
*   **动态环境 (Dynamic Environment)**: 实现了实时竞拍系统，价格随时间动态波动，要求 Agent 具备实时观察和决策能力。

---

## 🗺️ 任务全景 (Task Landscape)

本项目完整实现了 V2 数据集规范中的 14 个任务族：

*   **A. 居住 (Housing)**: 找房、开户、公用事业、办手机卡、租约管理、地址证明。
*   **B. 消费 (Consumption)**: 购物、生鲜订阅、家政、外卖、优惠券、价格保护、二手交易。
*   **C. 售后 (Support)**: 物流工单、退货(API)、退款、保修、评价/黑名单。
*   **D. 金融 (Finance)**: 账单聚合、预算、自动扣款、换卡、税务、理财。
*   **E. 差旅 (Travel)**: 通勤、交通卡、订机票、订酒店、签证查询、报销、改签。
*   **F. 工作 (Work)**: 日历、会议注册、投稿、邮件追踪、发票归档。
*   **G. 健康 (Health)**: 预约医生、处方(G4)、理赔、体检计划、疫苗。
*   **H. 政府 (Gov)**: 改地址、车辆登记、签证申请(E7/H5)、停车证。
*   **I. 维修 (Repair)**: 房屋报修、家电维修、智能家居(I3)、电表、能源套餐。
*   **J. 学习 (Learning)**: 选课、图书馆、票务、设备租赁。
*   **K. 社交 (Social)**: 加群、分账、慈善。
*   **L. 隐私 (Privacy)**: 密码管理、数据删除、密钥轮换、2FA设备。
*   **M. 危机 (Crisis)**: 丢卡冻结、供应链中断、突发疾病。
*   **Z. 高级 (Advanced)**: 订单收货(Z1)、理财增长(Z2)、实时竞拍(Z3)、邮件转日历(Z4)、密码找回(Z5)、智能客服(Z6)。

---

## 🔗 推荐任务链 (Recommended Task Chains)

为了充分测试 Agent 的长期记忆和规划能力，建议按照以下顺序执行任务。前序任务的状态改变会直接影响后续任务的执行条件或上下文。

### 1. 🏙️ 新生活开启链 (New Life Chain)
**场景**: 刚搬到一个新城市，从零开始建立生活基础。
1.  **A1 (Find Home)**: 浏览并签署一份租房合同（生成 Lease ID）。
2.  **A2 (Bank Opening)**: 开设一个银行账户（获得资金源）。
3.  **A3 (Utility Setup)**: 为新住处开通水电网服务。
4.  **I3 (Smart Home Setup)**: 购买并配置智能灯泡（改善居住环境）。
5.  **B1 (Shopping)**: 购买生活必需品（如“无线鼠标”）。
6.  **Z1 (Order Arrival)**: **[时间跳跃]** 等待 3 天，确认商品已送达。

### 2. ✈️ 国际商务差旅链 (Global Business Trip Chain)
**场景**: 收到一封重要的会议邀请，需要安排跨国行程。
1.  **Z4 (Email to Calendar)**: 读取“项目启动会”邮件，将时间地点添加到日历。
2.  **E4 (Visa Requirements)**: 查询目的地（如日本）的签证要求。
3.  **E7 (Long-haul Trip)**: 申请签证 -> **[时间跳跃 5天]** -> 确认签证获批。
4.  **E1 (Book Flight)**: 签证搞定后，预订去程机票。
5.  **E2 (Book Hotel)**: 预订当地酒店。
6.  **E5 (Expense Report)**: 行程结束后，提交机票和酒店的报销单。

### 3. 💸 财务危机与恢复链 (Financial Crisis & Recovery Chain)
**场景**: 遭遇银行卡丢失和账户问题，需要紧急处理并恢复。
1.  **M1 (Lost Card)**: 发现银行卡丢失，立即冻结卡片（导致绑定该卡的服务支付失败）。
2.  **D4 (Card Replacement)**: 申请新卡，并更新所有绑定商户（Shop, Food, etc.）的支付信息。
3.  **Z5 (Password Recovery)**: (模拟) 此时忘记了银行密码，通过手机验证码重置密码以重新登录。
4.  **D1 (Check Balance)**: 登录后检查账户余额，确认资金安全。
5.  **Z6 (Customer Service)**: 发现有一笔异常扣款或订单状态不对，通过聊天机器人查询订单详情。

### 4. 📈 资产增值链 (Asset Growth Chain)
**场景**:通过理财和捡漏来增加资产。
1.  **D6 (Investment Account)**: 开设一个“成长基金”账户，存入 $1000。
2.  **Z2 (Investment Growth)**: **[时间跳跃 30天]**，见证余额增长到 $1050。
3.  **Z3 (Live Auction)**: 利用赚到的利息，参与一场实时竞拍，以低价拍得古董花瓶。

---

## 🛠️ 如何使用时间旅行功能

在支持的页面（如 `gov.local/visa-apply.html`, `shop.local/orders.html`, `bank.local/investments.html`），页面底部有一个隐藏的 **Debug 按钮**。

或者，您可以直接调用后端 API 进行全局时间跳跃：

```bash
curl -X POST http://localhost:8014/api/debug/time_travel \
     -H "Content-Type: application/json" \
     -d '{"days": 5, "hours": 0}'
```

这将触发服务器端的 `world_triggers`，自动更新所有受时间影响的业务状态。
