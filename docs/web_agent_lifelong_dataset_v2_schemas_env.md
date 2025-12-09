# 终身学习 / 自进化 Web Agent 数据集（V2+：任务 I/O Schema 与环境方案）
**主线**：在新城市长期生活的数字助理（扩展版）  
**版本**：v2.1（含 Schema 与环境设计）  
**最后更新**：2025-11-16（UTC+8）

> 本文在 v2（64 个任务、13 大任务族）基础上，补充：
> 1) **统一 I/O JSON Schema（跨任务族可复用）**；  
> 2) **任务族级别的示例输入/输出**；  
> 3) **操作轨迹（action trace）与评测断言（assertions DSL）**；  
> 4) **交互环境可行性与实现方案（MVP → 扩展）**；  
> 5) **合规与安全设计**。

---

## 1. 通用 I/O Schema（草案）

### 1.1 TaskSpec（任务规范）
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TaskSpec",
  "type": "object",
  "required": ["task_id", "family", "goal", "inputs", "preconditions", "success_criteria"],
  "properties": {
    "task_id": {"type": "string", "description": "全局唯一任务 ID，如 B6-2025-01-001"},
    "family": {"type": "string", "enum": ["A","B","C","D","E","F","G","H","I","J","K","L","M"]},
    "episode_id": {"type": "string", "description": "同一轨迹中的 episode/回合 ID"},
    "priority": {"type": "integer", "minimum": 0, "default": 0},
    "seed": {"type": "integer", "description": "随机种子，影响 DOM 扰动与数据扰动"},
    "time": {"type": "string", "format": "date-time"},
    "persona": {"type": "object", "description": "用户人物画像（预算/口味/健康目标等）"},
    "goal": {"type": "string", "description": "自然语言目标"},
    "inputs": {
      "type": "object",
      "description": "结构化输入（例如地址、订单号、合同号等）",
      "additionalProperties": true
    },
    "allowed_domains": {
      "type": "array",
      "items": {"type": "string"},
      "description": "本任务允许访问的站点（MVP 阶段为镜像/合成站点）"
    },
    "preconditions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "需要成立的前置条件（可绑定到记忆条目）"
    },
    "memory_keys": {
      "type": "array",
      "items": {"type": "string"},
      "description": "本任务会读写的长期记忆字段键名"
    },
    "success_criteria": {
      "type": "array",
      "items": {"type": "string"},
      "description": "成功条件（使用 Assertions DSL）"
    },
    "artifacts": {
      "type": "array",
      "items": {"type": "string"},
      "description": "任务产出（如报告、发票、收据、截图）的逻辑名称"
    },
    "rubrics": {
      "type": "object",
      "description": "评分权重，如 {\"SR\":1.0, \"LH-F1\":0.5}",
      "additionalProperties": {"type": "number"}
    }
  }
}
```

### 1.2 Trace（操作轨迹）
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Trace",
  "type": "object",
  "required": ["task_id", "steps"],
  "properties": {
    "task_id": {"type": "string"},
    "agent_version": {"type": "string"},
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["t", "act"],
        "properties": {
          "t": {"type": "number", "description": "相对时间（秒）"},
          "url": {"type": "string"},
          "frame": {"type": "string", "description": "iframe 名称或 'main'"},
          "act": {"type": "string", "enum": ["open","click","type","select","submit","scroll","wait","upload","download","api","assert"]},
          "selector": {"type": "string", "description": "CSS/XPath/ARIA Selector"},
          "value": {"type": "string", "description": "输入值或期望值（type/select/assert 用）"},
          "screenshot_id": {"type": "string"},
          "note": {"type": "string"}
        }
      }
    }
  }
}
```

### 1.3 Memory KV（长期记忆片段）
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MemoryKV",
  "type": "object",
  "required": ["key", "value", "ts", "source"],
  "properties": {
    "key": {"type": "string"},
    "value": {},
    "ts": {"type": "string", "format": "date-time"},
    "source": {"type": "string", "description": "写入来源，如 'B1/order#1234'"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

---

## 2. Assertions DSL（评测断言迷你语言）

### 2.1 原子谓词（Atoms）
- `exists("<selector>")`：页面存在该元素；  
- `text("<selector>") == "<str>"` / `includes("<str>")`；  
- `attr("<selector>","<name>") == "<value>"`；  
- `count("<selector>") >= N`；  
- `url().includes("<path>")`；  
- `mem("<key>") == "<expected>"`（对照长期记忆）；  
- `json("<channel>","<path>") == <value>`（对环境侧 JSON API/数据库检查，如订单状态）；

### 2.2 组合子（Combinators）
- `ALL[ ... ]`：逻辑与；  
- `ANY[ ... ]`：逻辑或；  
- `NOT[ ... ]`：逻辑非；  
- `WITHIN(seconds, Expr)`：在时限内满足；  
- `EVENTUALLY(Expr)`：最终满足；  
- `STABLE(seconds, Expr)`：持续满足 N 秒；

### 2.3 示例
```txt
ALL[
  url().includes("/orders/"),
  text("#order-id") == mem("orders.last.id"),
  ANY[
    text(".status") == "refunded",
    text(".status") == "refund_in_progress"
  ]
]
```

---

## 3. 任务族级示例（输入/输出/断言）

> 仅展示每个任务族 1–2 个代表任务；完整 64 任务可按此模板批量生成。

### A. 居住与基础设施 —— A3 公共事业开通
- **Goal**：为地址 `mem.address.primary` 开通电/水/网，并记录合同号。  
- **Inputs**：`{"services":["electricity","water","broadband"], "plan":"postpaid-auto"}`  
- **Success**（DSL）：
  ```txt
  ALL[
    url().includes("/utility/confirm"),
    text("#service-electricity .status") == "active",
    text("#service-water .status") == "active",
    text("#service-broadband .status") == "active",
    json("env","contracts.electricity.status") == "active",
    mem("contracts.electricity.id") != ""
  ]
  ```
- **Artifacts**：`["contract_pdf","broadband_account"]`

### B. 消费与本地生活 —— B6 价格保护
- **Goal**：发现订单 `inputs.order_id` 的商品降价后，自动提交价保申请。  
- **Inputs**：`{"order_id":"O-98321","price_drop_threshold":20}`  
- **Success**：
  ```txt
  ALL[
    url().includes("/support/price-protection"),
    text(".result") == "submitted",
    json("env","orders.O-98321.claims.price_protect.state") == "submitted"
  ]
  ```

### C. 售后与反馈 —— C4 保修索赔
- **Inputs**：`{"serial":"TV-42-2025-XY9","order_id":"O-10123"}`  
- **Success**：
  ```txt
  ALL[
    text("#claim-status") == "accepted",
    json("env","warranty.TV-42-2025-XY9.state") == "RMA_issued"
  ]
  ```

### D. 金融与预算 —— D4 信用卡到期换卡
- **Inputs**：`{"old_last4":"1234","new_last4":"7777"}`  
- **Success**：
  ```txt
  ALL[
    count(".merchant-binding.updated") >= 5,
    json("env","payments.cards.active_last4") == "7777",
    NOT[text(".merchant-binding.error")]
  ]
  ```

### E. 出行与差旅 —— E6 长途旅行改签
- **Inputs**：`{"pnr":"PNR9ZZ","policy":"min-cost"}`  
- **Success**：
  ```txt
  ALL[
    text("#pnr") == "PNR9ZZ",
    text("#ticket-status") == "rebooked",
    json("env","trips.PNR9ZZ.history[-1].action") == "rebook"
  ]
  ```

### F. 工作与效率 —— F2 学术会议注册
- **Inputs**：`{"conference":"CL-2026","invoice_title":"Your Lab"}`  
- **Success**：
  ```txt
  ALL[
    text("#registration-status") == "paid",
    json("env","invoices.last.conference") == "CL-2026"
  ]
  ```

### G. 健康与保险 —— G3 医疗理赔
- **Inputs**：`{"visit_id":"V-5567","policy_id":"P-9001"}`  
- **Success**：
  ```txt
  ALL[
    text("#claim-state") == "processing",
    json("env","claims.V-5567.state") == "processing"
  ]
  ```

### H. 政府与合规 —— H3 居留许可续期
- **Inputs**：`{"permit_id":"RP-2024-77","slot":"2025-12-01T10:00"}`  
- **Success**：
  ```txt
  ALL[
    text("#appointment-state") == "booked",
    json("env","permits.RP-2024-77.next_appointment") == "2025-12-01T10:00"
  ]
  ```

### I. 维修与智能家居 —— I5 能源优化与套餐切换
- **Inputs**：`{"plan":"green_offpeak","meter_id":"M-321"}`  
- **Success**：
  ```txt
  ALL[
    text("#plan-active") == "green_offpeak",
    json("env","meters.M-321.plan") == "green_offpeak"
  ]
  ```

### J. 学习与兴趣 —— J1 在线课程报名
- **Inputs**：`{"course_id":"DL101","notify_before_days":3}`  
- **Success**：
  ```txt
  ALL[
    text("#enroll-state") == "enrolled",
    json("env","courses.DL101.state") == "enrolled"
  ]
  ```

### K. 社交与社区 —— K2 室友 AA 制分摊
- **Inputs**：`{"month":"2025-10","members":["A","B"],"rules":"equal"}`  
- **Success**：
  ```txt
  ALL[
    text("#split-state") == "settled",
    json("env","settlements.2025-10.state") == "settled"
  ]
  ```

### L. 隐私与安全 —— L3 数据泄露监测与密钥轮换
- **Inputs**：`{"providers":["mail","cloud","dev"],"rotate":"mfa+api"}`  
- **Success**：
  ```txt
  ALL[
    count(".rotation-complete") >= 3,
    json("env","security.last_rotation.providers") == ["mail","cloud","dev"]
  ]
  ```

### M. 危机与异常 —— M1 丢失银行卡处理
- **Inputs**：`{"card_last4":"1234","reissue":true}`  
- **Success**：
  ```txt
  ALL[
    text("#card-state") == "blocked",
    json("env","payments.cards.1234.state") == "blocked",
    count(".merchant-binding.updated") >= 5
  ]
  ```

---

## 4. 交互环境可行性与实现方案

> 目标：在**不依赖真实生产网站**的前提下，提供**逼真、可控、可扩展**的 Web 环境，支持 DOM 扰动、流程多样性与状态持久化。

### 4.1 MVP（合成多站点沙盒）
- **前端**：Next.js/React + Tailwind；每个“站点”是独立应用（电商、外卖、银行、旅行、政府、健康等），共用 UI 组件库但**随机化 DOM id/class**；  
- **后端**：Node/Express + SQLite（或 Postgres），提供统一 **Env JSON API**（`/env/...`）暴露订单、账单、合同、设备等可验证字段；  
- **路由控制**：Nginx 反代，配置站点二级域名（`shop.local`, `bank.local` 等）；  
- **鉴权模拟**：用户名/密码 + 可选 OTP（以“模拟短信”组件展示）；  
- **支付/扣费**：全部模拟，无真实金流；  
- **扰动器**：DOM 扰动、数据扰动、网络扰动；  
- **审计与回放**：Playwright 中间件记录**操作轨迹 + 截图**；提供**确定性种子**重放。

### 4.2 扩展（镜像模式 + 真实模式）
- **镜像模式**：抓取公共站点的**模板页面**，去标识化后接入沙盒后端，实现真实的 DOM 复杂度与流程；  
- **真实模式**：白名单小范围真实网站、**测试账号**与 robots/ToS 合规前提下运行（科研内网控制）。

### 4.3 关键难点与解决策略
- 登录/2FA、文件上传/下载、跨站状态一致性、时间旅行、可验证性（统一写入 Env JSON）。

---

## 5. 评测与日志
- 与 v2 指标对齐（SR、LH-F1、MemRet@k/MRR、Bind-Update、Resilience@Shift、Claim-E2E）；  
- 标准 Trace、统一种子、导出 `env_final.json`、发布 Oracle 轨迹。

---

## 6. 合规与安全
- Faker 去标识化；  
- MVP/镜像不触达真实生产站点；  
- 容器沙箱与出网策略；  
- episode 级状态清理；  
- 开源许可建议：Apache-2.0 / CC-BY-4.0。

---

## 7. 下一步
1) 先落地 **10 个代表任务** 的 TaskSpec/DSL/Env JSON；  
2) 接入扰动与时间旅行；  
3) 扩展至 30+ / 64 任务并发布基线。

