# Web Agent Dynamic Suite V2 (Skin Edition)

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**Web Agent Dynamic Suite V2** 是一个专为评估和训练大语言模型（LLM）及 Web Agent 设计的高保真仿真环境。它模拟了一个包含电子商务、金融银行、政府服务、医疗健康、企业办公等多个相互关联的网站生态系统。

与传统的静态网页截图数据集不同，本项目提供了一个**全动态、可交互、状态持久化**的本地 Web 环境，支持从简单的表单提到复杂的跨天长程规划任务。

---

## 🌟 核心特性 (Key Features)

*   **全功能仿真网站**: 包含 `shop.local`, `bank.local`, `gov.local`, `health.local` 等 10+ 个模拟站点，拥有完整的前端 UI 和后端逻辑。
*   **真实状态管理**: 基于 SQLite 数据库和 JSON 状态树，所有操作（如下单、转账、预约）都会产生持久化的状态变更，支持多轮交互。
*   **模块化架构**: 采用 `task_handlers` 插件式设计，便于扩展新的任务逻辑而不破坏核心服务。
*   **虚拟时间系统**: 内置时间旅行机制，支持模拟“等待 3 天签证审批”或“等待 30 天理财收益”等长程任务。
*   **多样化任务库**: 预置了 70+ 个从基础操作到高级规划的测试任务（A-Z 系列），覆盖生活、工作、危机处理等多种场景。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备

确保您的系统已安装：
*   **Python 3.8+**
*   **Node.js & NPM** (用于 Playwright 浏览器自动化)

### 2. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器内核
playwright install chromium
```

*(如果项目根目录没有 `requirements.txt`，主要依赖包括 `playwright`, `flask` (如使用), 或标准库 `http.server` 扩展)*

### 3. 初始化数据库

在首次运行前，或者需要重置环境时，运行初始化脚本：

```bash
python3 init_db.py
```
*此操作会创建/重置 `data.db`，包含所有必要的表结构（用户、订单、KV 存储等）。*

### 4. 启动服务器

启动本地仿真服务器（默认端口 8014）：

```bash
python3 server.py 8014
```
*服务器启动后，您可以通过浏览器访问 `http://localhost:8014` 查看模拟网站导航页（如果有）或直接访问子站点如 `http://localhost:8014/shop.local/index.html`。*

---

## 🧪 运行任务 (Running Tasks)

本项目使用 `run_task.py` 脚本来自动执行和验证 Agent 任务。

### 基本用法

```bash
python3 run_task.py <task_id> [options]
```

### 示例

**1. 运行一个基础任务（如购物）：**
```bash
python3 run_task.py B1-shopping
```

**2. 以无头模式运行（不显示浏览器窗口，适合服务器环境）：**
```bash
python3 run_task.py B1-shopping --headless
```

**3. 运行一个高级长程任务（如 Z1 订单收货）：**
```bash
python3 run_task.py Z1-order-arrival --headless
```

### 验证原理
每个任务包含一个 `task_spec.json`（定义目标和验证标准）和一个 `oracle_trace.json`（参考执行轨迹）。`run_task.py` 会回放 Trace 中的操作，并在结束后检查数据库 (`memory_kv`) 或 URL 状态是否符合预期。

---

## 📂 项目结构 (Project Structure)

```text
webagent_dynamic_suite_v2_skin/
├── server.py               # 核心服务器入口，处理路由和 API 请求
├── init_db.py              # 数据库初始化脚本
├── run_task.py             # 任务执行与验证脚本
├── data.db                 # SQLite 数据库（存储业务数据和验证状态）
├── env/                    # 环境配置文件夹
│   ├── state.json          # 运行时内存状态快照
│   └── *_initial.json      # 各模块的初始状态模板
├── sites/                  # 前端静态资源 (HTML, CSS, JS)
│   ├── shop.local/         # 电商网站
│   ├── bank.local/         # 银行网站
│   ├── gov.local/          # 政府网站
│   └── ...
├── task_handlers/          # 后端业务逻辑模块 (按任务族分类)
│   ├── a_housing.py
│   ├── b_consumption.py
│   ├── world_triggers.py   # 时间触发器逻辑
│   └── ...
├── tasks/                  # 任务定义文件夹
│   ├── A1-find-home/
│   ├── Z1-order-arrival/
│   └── ...
└── PROJECT_HIGHLIGHTS.md   # 项目亮点与任务链详细说明
```

---

## 🕰️ 高级功能：时间旅行

对于涉及等待的任务（如 E7 签证申请、Z2 理财增长），系统提供了**时间旅行**功能。

*   **前端**: 在特定页面（如订单页、投资页）底部有隐藏的 Debug 按钮，点击可触发时间快进。
*   **后端原理**: `server.py` 接收到 `/api/debug/time_travel` 请求后，会调用 `task_handlers/world_triggers.py`，根据流逝的时间自动更新订单状态、审批进度或账户余额。

---

## 🤝 贡献指南

如果您想添加新的任务：
1.  在 `tasks/` 下创建新目录（如 `N1-new-task`）。
2.  编写 `task_spec.json` 定义任务目标和验证规则。
3.  (可选) 编写 `oracle_trace.json` 提供参考轨迹。
4.  如果需要新的后端逻辑，请在 `task_handlers/` 中修改对应模块或创建新模块，并在 `server.py` 中注册。

---

*Web Agent Dynamic Suite V2 - Empowering the next generation of autonomous agents.*
