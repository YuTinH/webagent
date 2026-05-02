# Web Agent Dynamic Suite V2 - 扩展任务链剧本

本文档定义 8 条可用于压力测试的长程任务链模板，重点考察跨任务状态依赖、蝴蝶效应和异常恢复能力。

说明：
- 这些链是“剧本模板”，不是唯一标准集。
- 实际批量评测请优先使用 `sampled_{theme}.json` + runner。

---

## 1. 🎓 勤奋学生链 (The Diligent Student)

场景：模拟新学期学习与生活安排。  
核心考察：学术资源获取 + 社交财务管理。

1. `A4-mobile-plan`
2. `J1-course-enroll`
3. `F1-calendar-aggregation`
4. `J2-library-service`
5. `B1-shopping`
6. `K2-roommate-split`

## 2. 🏥 健康管理闭环 (The Health Guardian)

场景：从日常保健到突发疾病应对。  
核心考察：预防性规划 + 危机补救。

1. `G5-health-plan`
2. `B2-fresh-subscription`
3. `G6-vaccine-mgmt`
4. `M3-illness-reporting`
5. `G1-doctor-appt`
6. `G4-gym-membership`
7. `G3-medical-claim`

## 3. 🛡️ 隐私安全保卫战 (The Security Hardening)

场景：检测账号风险后进行系统性加固。  
核心考察：安全响应速度 + 验证流程稳定性。

1. `L3-security-audit`
2. `Z5-password-recovery`
3. `L1-password-manager`
4. `L4-2fa-device`
5. `L2-data-deletion`

## 4. 🏠 智能家居发烧友 (The Smart Home Enthusiast)

场景：打造自动化节能居住环境。  
核心考察：设备管理 + 数据驱动决策。

1. `A3-utility-setup`
2. `B1-shopping`
3. `I1-smart-bulb-setup`
4. `I4-smart-meter`
5. `I5-energy-optimize`

## 5. 🛒 购物售后链 (The Regretful Shopper)

场景：复杂电商售后链路。  
核心考察：权益维护 + 逆向物流处理。

1. `B1-shopping`
2. `Z1-order-arrival`
3. `B5-price-protection`
4. `C5-leave-review`
5. `C2-return`
6. `C1-logistics-fix`

## 6. 🚗 车主与市政链 (The Car Owner)

场景：搬家后的行政联动变更。  
核心考察：多证件联动与流程依赖。

1. `H1-address-change`
2. `H2-vehicle-address-update`
3. `G2-insurance-policy`
4. `H4-parking-permit`
5. `D1-check-balance`

## 7. 💼 自由职业者链 (The Freelancer)

场景：在家办公下的行政与财务闭环。  
核心考察：文档处理 + 税务合规。

1. `F3-paper-submission`
2. `F5-receipt-archive`
3. `D5-tax-preparation`
4. `D1-check-balance`
5. `D3-autopay`

## 8. 🎉 派对组织者链 (The Party Planner)

场景：组织社区活动。  
核心考察：资源统筹 + 多方协调。

1. `K1-plan-party`
2. `B1-shopping`
3. `B4-food-delivery`
4. `J3-event-tickets`
5. `K2-roommate-split`
6. `K3-charity-donation`

---

## 运行建议（已统一到当前评测口径）

### A. 生成任务流

```bash
python3 scenario_generator_v3.py
```

输出：
- `sampled_newcomer.json`
- `sampled_daily.json`
- `sampled_career.json`
- `sampled_leisure.json`
- `sampled_crisis.json`

### B. Oracle 基线评测（不依赖模型）

```bash
python3 -u chain_runner_oracle.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --summary-json audit_chain_oracle_100.json
```

### C. Agent 评测（真实模型）

```bash
python3 -u chain_runner_dynamic.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --summary-json audit_agent_100.json
```

### D. 停止策略（重要）

- 默认：链内任务失败后继续执行后续任务。
- 可选：`--stop-on-first-fail-task` 启用链级早停。
- 默认：任务内 `step` 执行错误即停（`--stop-on-first-fail-step`）。
- 可选：`--no-stop-on-first-fail-step` 关闭 step 级早停。

### E. 评分口径

统一使用三维分数：
- `step_score`（检查点进度）
- `task_score`（任务完成率）
- `flow_score`（任务流完成率）

统一使用 `step_score` / `task_score` / `flow_score` 口径。
