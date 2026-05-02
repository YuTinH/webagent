# Workflow Realism Audit 规则说明

生成时间：2026-04-23

本文说明我们当前 benchmark 中 `realism audit` 的规则含义、覆盖范围和典型例子。这里的 `realism` 可以理解为“现实合理性”：一个 workflow 不仅要在系统里能执行，还要像真实世界中用户会走的办事流程。

## 1. 核心定义

`realism audit` 检查的是：taskflow 是否具备现实世界里的必要前置语境。

换句话说，它不是只看“有没有一条成功路径”，而是看“这条路径是不是符合人类真实办事顺序”。

典型例子：

- 合理：用户已有已送达订单，然后申请退货。
- 不合理：用户没有任何订单，直接进入售后退货。
- 合理：用户已有银行账户，然后申请挂失银行卡。
- 不合理：用户为了处理银行卡挂失，先从开户开始。
- 合理：用户已有航班预订，然后办理值机或改签。
- 不合理：用户没有任何订票记录，直接办理值机。

## 2. 规则来源

当前规则分两层：

- 配置文件：`/Users/masteryth/Documents/webagent/tasks/workflow_quality_requirements.json`
- 执行脚本：`/Users/masteryth/Documents/webagent/rl_memory/scripts/audit_workflow_blueprint_realism.py`
- batch 级审计脚本：`/Users/masteryth/Documents/webagent/rl_memory/scripts/audit_workflow_batch_realism.py`

其中 `audit_workflow_blueprint_realism.py` 是核心规则实现，`audit_workflow_batch_realism.py` 会把生成后的 goal/oracle 转成相同视图，再复用同一套规则。

## 3. Realism Audit 和其他 Audit 的区别

`realism audit` 主要回答：这个流程像不像真实世界。

它不主要回答：

- 这个任务够不够难。
- agent 是否容易 shortcut。
- 多条路径是否足够语义不同。
- 初始状态是否已经接近完成目标。
- benchmark 的整体难度是否能把 Qwen 压到目标区间。

这些属于 `difficulty audit`、`goal quality audit` 或 shortcut hardening 的范围。

因此，`realism audit` 更像是“现实前置条件检查”，而不是“难度检查”。

## 4. 订单、售后、订阅场景

相关规则函数：`audit_order_and_subscription_context`

### 4.1 售后任务必须有订单语境

如果 workflow 包含售后相关模块或目标，例如：

- 联系客服
- 物流修复
- 退货
- 保修
- 售后补救

那么初始状态中必须有订单语境：

- `shop_order_exists`
- 或 `shop_order_delivered`

否则会报：

- `order_context_missing_existing_order`

解释：售后不能凭空发生。真实场景里，用户一定是先有订单，再有售后问题。

### 4.2 售后任务不能用无关 bootstrap 起步

订单售后任务里禁止出现这些 bootstrap 模块：

- `MODULE_BANK_OPENING`
- `MODULE_SHOPPING`

否则会报：

- `order_context_contains_bootstrap_order_module`

解释：如果目标是处理已有订单售后，就不应该先去开户或先购物。这种路径虽然可能在图上连得通，但现实语义是错的。

### 4.3 收货后动作必须有已送达语境

如果 workflow 涉及这些“收货后才能做”的动作：

- 退货
- 保修
- 写评价
- 拉黑商家

那么必须满足以下条件之一：

- 初始状态已有 `shop_order_delivered`
- 路径中包含 `MODULE_ORDER_ARRIVAL`
- target 本身包含送达相关状态

否则会报：

- `order_context_missing_delivered_order_state`

解释：没有收到货就不能申请退货、写评价或走保修。

### 4.4 已经送达时不要重复送达

如果初始状态已经有 `shop_order_delivered`，但路径里又出现 `MODULE_ORDER_ARRIVAL`，会被认为是冗余 bootstrap。

会报：

- `order_context_contains_redundant_delivery_bootstrap`

解释：这不是逻辑不可行，但路径设计不干净。既然任务一开始已经是“订单已送达”，就不应该再走一次“订单送达”。

### 4.5 订阅退出任务必须有活跃订阅

如果 workflow 是取消订阅或订阅退款，例如包含：

- `MODULE_CANCEL_SUBSCRIPTION`
- `MODULE_SUBSCRIPTION_REFUND`

那么初始状态必须有：

- `subscription_active`

否则会报：

- `subscription_context_missing_active_subscription`

解释：没有活跃订阅，就不能直接取消订阅或申请订阅退款。

### 4.6 订阅退出任务不能先新开订阅

订阅退出任务里不允许出现：

- `MODULE_FRESH_SUBSCRIPTION`

否则会报：

- `subscription_context_contains_bootstrap_subscription_module`

解释：取消订阅任务不应该通过“先新开一个订阅”来构造可取消对象。

## 5. 银行账户问题场景

相关规则函数：`audit_bank_issue_context`

如果 workflow 包含银行账户问题相关模块，例如：

- `MODULE_CARD_REPLACEMENT`
- `MODULE_DISPUTE_TRANSACTION`
- `MODULE_CHECK_BALANCE`
- `MODULE_LOST_CARD_FREEZE`
- `MODULE_URGENT_LOAN`

那么必须有账户上下文。满足以下任一即可：

- 初始状态已有 `bank_account_active`
- target 本身就是 `bank_account_active`
- 路径中包含 `MODULE_BANK_OPENING`

如果没有账户上下文，会报：

- `bank_issue_missing_account_context`

另外，如果路径里包含 `MODULE_BANK_OPENING`，但 target 并不是开户成功，则会报：

- `bank_issue_contains_bootstrap_bank_opening`

解释：开户只应该用于“目标就是开通账户”的任务；不能为了处理银行卡挂失、交易争议、查余额等问题，临时先开户。

合理例子：

- 初始状态：`bank_account_active`
- 任务：冻结遗失银行卡

不合理例子：

- 初始状态：无银行账户
- 路径：开户 -> 冻结遗失银行卡

## 6. 出行预订场景

相关规则函数：`audit_travel_context`

如果 workflow 包含这些需要已有 booking 的模块：

- `MODULE_FLIGHT_REBOOKING`
- `MODULE_CHECK_IN`

那么必须满足以下任一：

- 初始状态已有 `flight_booked`
- 初始状态已有 `travel_booking_confirmed`
- 在当前路径中，前面已经出现过订票 bootstrap 模块

当前允许的订票 bootstrap 模块：

- `MODULE_BOOK_FLIGHT`
- `MODULE_LONG_HAUL_TRIP`

否则会报：

- `travel_missing_booking_context`

解释：改签和值机都依赖已有航班预订。不能没有票就直接值机或改签。

## 7. Newcomer 主题：居住锚点

相关规则函数：`audit_newcomer_theme`

如果 `newcomer` 主题中出现居住相关模块，例如：

- `MODULE_ADDRESS_PROOF`
- `MODULE_UTILITY_SETUP`
- `MODULE_ADDRESS_CHANGE`

那么必须满足以下任一：

- 初始状态已有 `lease_active`
- 路径中包含 `MODULE_FIND_HOME`

否则会报：

- `newcomer_missing_housing_anchor`

解释：新来到一个城市时，地址证明、水电开通、地址变更都需要居住锚点。用户不能在没有住所或租约的情况下直接办理这些事项。

## 8. Government 主题：居住/地址锚点

相关规则函数：`audit_government_theme`

如果 `government` 主题中出现地址或居住强相关模块，例如：

- 停车许可申请
- 车辆地址更新
- permit 申请或续期
- 地址变更

那么必须满足以下任一：

- 初始状态已有 `lease_active`
- 初始状态已有 `address_proof_available`
- 初始状态已有 `residency_record_verified`
- 路径中包含 `MODULE_FIND_HOME`
- 路径中包含 `MODULE_ADDRESS_PROOF`
- 路径中包含 `MODULE_UTILITY_SETUP`

否则会报：

- `government_missing_residency_anchor`

解释：很多政务事项依赖真实住址或居住记录。没有住址语境就直接申请停车许可或更新车辆地址，是不合理的。

## 9. Education 主题：课程和证书前置条件

相关规则函数：`audit_education_theme`

### 9.1 交作业必须先有课程

如果路径里有：

- `MODULE_SUBMIT_ASSIGNMENT`

那么必须满足以下任一：

- 初始状态已有 `course_enrolled`
- 当前路径前面已有 `MODULE_COURSE_ENROLLMENT`

否则会报：

- `education_assignment_missing_course_context`

解释：用户必须先选课，才有对应课程作业可提交。

### 9.2 下载证书必须先有课程或认证完成语境

如果路径里有：

- `MODULE_DOWNLOAD_CERT`

那么必须满足以下任一：

- 初始状态已有 `course_enrolled`
- 初始状态已有 `skill_certified`
- 当前路径前面已有 `MODULE_COURSE_ENROLLMENT`
- 当前路径前面已有 `MODULE_SKILL_CERTIFICATION`

否则会报：

- `education_certificate_missing_completion_context`

解释：证书不是凭空下载的，需要先有学习或认证完成的来源。

## 10. Health 主题：理赔必须有保险覆盖

相关规则函数：`audit_health_theme`

如果路径里有：

- `MODULE_MEDICAL_CLAIM`

那么必须满足以下任一：

- 初始状态已有 `coverage_path_active`
- 初始状态已有 `health_plan_active`
- 初始状态已有 `insurance_policy_active`
- 当前路径前面已有 `MODULE_INSURANCE_POLICY`
- 当前路径前面已有 `MODULE_HEALTH_PLAN_ACTIVATION`

否则会报：

- `health_claim_missing_coverage_context`

解释：医疗理赔需要已有保险计划或保险单。没有保险覆盖就直接提交理赔，在现实中不成立。

## 11. Home 主题：住宅/水电锚点

相关规则函数：`audit_home_theme`

如果路径中出现住宅强相关模块，例如：

- `MODULE_SMART_METER`
- `MODULE_THERMOSTAT_SCHEDULE`
- `MODULE_ENERGY_OPTIMIZE`
- `MODULE_SMART_BULB_SETUP`
- `MODULE_HOUSE_REPAIR`

那么必须满足以下任一：

- 初始状态已有 `lease_active`
- 初始状态已有 `utilities_active`
- 当前路径前面已有 `MODULE_FIND_HOME`
- 当前路径前面已有 `MODULE_UTILITY_SETUP`

否则会报：

- `home_missing_residence_context`

解释：家居维护和能源优化都默认用户已经有住所或水电服务。没有住所就直接修房子或优化电表，不合理。

## 12. Social 主题：支付锚点

相关规则函数：`audit_social_theme`

如果路径里有：

- `MODULE_CHARITY_DONATION`

那么必须满足以下任一：

- 初始状态已有 `bank_account_active`
- 路径中包含 `MODULE_BANK_OPENING`

否则会报：

- `social_missing_payment_anchor`

解释：捐款类任务依赖支付能力。如果没有账户、卡、钱包等支付锚点，直接捐款不现实。

## 13. Career 主题：报销来源锚点

相关规则函数：`audit_career_theme`

如果路径里有：

- `MODULE_EXPENSE_REPORT`

那么必须满足以下任一：

- 路径中包含 `MODULE_BOOK_FLIGHT`
- 路径中包含 `MODULE_BOOK_HOTEL`
- 路径中包含 `MODULE_CONFERENCE_REG`
- 路径中包含 `MODULE_CONFERENCE_REGISTRATION`
- 初始状态已有 `travel_booking_confirmed`
- 初始状态已有 `conference_admin_recorded`

否则会报：

- `career_expense_missing_source_context`

解释：报销必须有来源，例如出差、酒店、会议注册。没有出差或会议上下文就直接报销，是不合理的。

## 14. Security 主题：重置和 2FA 前置条件

相关规则函数：`audit_security_theme`

### 14.1 完成密码重置前必须先请求重置

如果路径里有：

- `MODULE_PASSWORD_RESET_COMPLETION`

且路径中没有一体化恢复模块：

- `MODULE_PASSWORD_RECOVERY_E2E`

那么必须满足以下任一：

- 初始状态已有 `password_reset_code_requested`
- 当前路径前面已有 `MODULE_PASSWORD_RESET_REQUEST`

否则会报：

- `security_reset_completion_missing_request`

解释：不能跳过“请求验证码/重置链接”这一步，直接完成密码重置。

### 14.2 2FA 设备操作前必须先启用 2FA

如果路径里有：

- `MODULE_2FA_DEVICE`

那么必须满足以下任一：

- 初始状态已有 `two_factor_enabled`
- 当前路径前面已有 `MODULE_2FA_SETUP`

否则会报：

- `security_2fa_device_missing_setup_context`

解释：不能在未启用 2FA 的情况下直接管理 2FA 设备。

## 15. 当前覆盖范围和局限

当前配置中多个 theme 都是 enabled，例如：

- `career`
- `composite`
- `crisis`
- `daily`
- `education`
- `finance`
- `government`
- `health`
- `home`
- `newcomer`
- `security`
- `social`
- `support`
- `travel`

但真正有显式代码规则的主要是：

- 订单/售后/订阅上下文
- 银行账户上下文
- 出行 booking 上下文
- newcomer 居住锚点
- government 地址/居住锚点
- education 课程/证书锚点
- health 保险覆盖锚点
- home 住宅/水电锚点
- social 支付锚点
- career 报销来源锚点
- security 重置/2FA 前置条件

因此，`realism audit` 目前不是一个覆盖所有现实世界常识的通用判别器，而是一组针对我们 benchmark 高风险场景的硬规则检查。

## 16. 可以用于汇报的表述

我们没有只靠人工抽样判断 workflow 是否合理，而是把一批现实前置条件写成了可执行规则。

这些规则会检查 taskflow 是否存在“现实锚点”缺失问题。例如售后必须有订单，银行卡问题必须有账户，航班改签必须有 booking，医疗理赔必须有保险覆盖，报销必须有出差或会议来源。

这样做的意义是：benchmark 中的 taskflow 不只是形式上可解，而且要符合真实用户办事流程。若一个 workflow 能被 agent 做出来，但它的前置语境不真实，比如“为了售后先购物”或“为了挂失银行卡先开户”，它仍然会被 realism audit 拦下来。

## 17. 和难度增强的关系

`realism audit` 保证的是“合理”，不是“困难”。

后续如果要继续压低 Qwen 成功率，应该在 realism audit 全绿的前提下做 difficulty hardening，例如：

- 增加 4 到 6 步的真实长链任务。
- 减少单模块直接完成目标的 shortcut。
- 增加跨站点、跨状态依赖。
- 增加中间状态必须传递的任务。
- 增加语义相近但不可混用的干扰项。

但这些增强都必须遵守 realism audit 的前置语境约束，否则难度提升会变成“不合理任务”，不适合作为 benchmark。
