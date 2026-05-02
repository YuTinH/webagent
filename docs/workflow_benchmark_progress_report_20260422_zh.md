# Workflow Benchmark 进展汇报（2026-04-22）

## 1. 一句话结论

这周我们的工作重点不是“继续把模型分数刷高”，而是先把 benchmark 本身修到一个可信状态，然后在这个基础上系统性地提高难度。

现在可以比较有把握地说三件事：

- benchmark 的 **结构正确性** 基本收口了，也就是“给出的 workflow 不是无解任务”。
- benchmark 的 **逻辑合理性** 有了比“人工抽样看了看”更强的证据，也就是“任务链条符合现实语义”。
- 在 clean 版本上，`Qwen2.5-7B-Instruct` 已经接近做穿；在本周持续 hardening 之后，它在最新一轮 train 全量中期结果上已经明显掉下来了，这说明 benchmark 重新开始有区分度了。

## 2. 这周我们主要做了什么

### 2.1 修 infra（基础设施）问题

这里的 `infra`，简单理解就是 benchmark 的运行底座，包括：

- 任务运行环境是否互相污染
- 页面和任务 id 是否绑对
- runtime 写回状态时会不会写错地方
- 评测日志是否足够详细，能不能定位失败原因

这周我们主要做了这些事：

- 把 workflow 评测切到更严格的隔离逻辑，避免不同 goal 之间共享运行状态造成污染。
- 收紧 shared page 和真实任务的绑定，避免“页面上动作做对了，但状态写到了错误任务上”。
- 清理了一批 runtime / selector / URL 映射相关问题，并保留了对应回归测试。
- 增强了 `workflow_module_selection_trace.json` 的记录粒度，让后续 rerun 可以直接看出：
  - planner 当时看到了哪些候选 module
  - 它原始输出了什么
  - 解析器是怎么理解它输出的
  - 有没有 fallback（回退）到默认候选
  - 最后 atomic executor（底层网页执行器）是怎么失败的

本地回归测试目前是：

- `tests.test_order_api_merge`
- `tests.test_selector_normalization`
- `tests.test_executor_url_mapping`
- 共 `12/12` 通过

这件事的意义是：

- 以前看到一个失败样本，我们经常只能知道“它失败了”；
- 现在我们更容易知道“它是 benchmark 本身有问题，还是 planner 选错了 module，还是网页执行没完成”。

### 2.2 修 logic（任务逻辑）问题

这里的 `logic`，可以理解成“workflow 任务链本身讲不讲得通”。

一个通俗例子：

- 如果用户任务是“完成售后补救”，合理路径应该是：
  - 先确认物流 / 收货状态
  - 再联系客服
  - 再申请退款或补偿
  - 最后安排后续跟进
- 不合理的路径是：
  - 先去开银行卡
  - 再回来做售后

后一种虽然表面上也是“多步任务”，但现实语义是错的，这种任务链不应该出现在 benchmark 里。

这周我们做的逻辑工作，核心就是把这类不合理路径收掉。

具体包括：

- 用 oracle 允许路径约束 planner 的候选 module，减少“语义有点像，但根本不该现在做”的误选。
- 修复一批 workflow 资产中的错误参数和错误目标绑定，避免任务被指向环境里不存在的对象。
- 针对已经暴露出问题的 goal，做 targeted logic re-audit（定点逻辑复审），不是凭感觉说“应该好了”，而是重新走完整条参考成功路径。

### 2.3 提高 benchmark 难度

这周我们不是随便“拉长任务”，而是有针对性地 harden（加难）那些过短、过容易形成 shortcut（捷径）的链条。

本质思路是：

- 不去人为加一些很怪的步骤；
- 而是把原本太短、太顺手、太容易一步到位的任务，改成更接近真实世界的 5 到 6 步链条。

比如：

- 不再让一个任务“完成密码管理器操作”就直接结束；
- 而是要求它和账号恢复、2FA、设备更新、信息归档等后续动作形成完整闭环。

## 3. 我们现在拿到了哪些“workflow 是对的”的证据

这部分最关键，因为导师最关心的其实不是“我们感觉没问题”，而是“你们如何证明这个 workflow 有可行解，而且逻辑合理”。

### 3.1 全量静态结构有效性：`5040/5040` 可解

我们重新跑了系统性的 dataset validity analysis（数据集有效性分析），结果写在：

- `/Users/masteryth/Documents/webagent/docs/workflow_dataset_validity_report_v20.md`
- `/Users/masteryth/Documents/webagent/docs/workflow_dataset_validity_report_v20.json`

里面最核心的数字是：

| 指标 | 数值 |
| --- | ---: |
| 总 goal 数 | `5040` |
| 至少存在一条可行成功路径的 goal 数 | `5040` |
| 可解率 `solvable_ratio` | `1.000` |
| 所有声明成功路径都可执行的 goal 数 | `5040` |
| `all_paths_executable_ratio` | `1.000` |
| 非法路径数 `invalid_path_count` | `0` |

按 split 看也是全绿：

| Split | Goal 数 | 可解 goal | 可解率 | 所有路径都可执行 | 非法路径数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev | `140` | `140` | `1.000` | `140` | `0` |
| test | `140` | `140` | `1.000` | `140` | `0` |
| train | `4760` | `4760` | `1.000` | `4760` | `0` |

这意味着：

- 从“结构上有没有解”这个问题看，我们现在已经不是靠人工抽样，而是对 `5040` 个 goal 全部做了程序化检查。
- 换句话说，现在不能再说“这个 benchmark 可能本身就有很多无解任务”。

### 3.2 现实合理性审计：问题数为 `0`

我们保留了 realism audit（现实合理性审计）结果：

- `workflow_blueprint_realism_audit.json`
- `workflow_batch_realism_audit.json`

当前统计是：

| 审计项 | 结果 |
| --- | ---: |
| `workflow_blueprint_realism_audit.issue_count` | `0` |
| `workflow_batch_realism_audit.issue_count` | `0` |
| `dev/test/train goal quality audit hard_fail_reasons` | 都为空 |

这意味着：

- 至少在自动化规则能覆盖的层面，我们没有再发现“任务主题明显不合理”“目标初始就满足”“路径自相矛盾”这类硬问题。

### 3.3 修复后的 support 逻辑回归：最终集合 `172/172` 全通过

仅靠静态检查还不够，所以我们还做了 reference-path logic audit（参考路径逻辑回归）。

可以把它理解成：

- benchmark 自己给出一条“标准可行路径”；
- 我们按这条路径真的去实例化、执行、判分；
- 看它最后能不能被 benchmark 自己判成成功。

修复后的最终 support 逻辑验证集合，一共是 `172` 条路径检查，结果是：

| 集合 | 通过 / 总数 |
| --- | ---: |
| support_logic_full_audit_v1_train | `62/62` |
| support_logic_full_audit_v2_test | `20/20` |
| support_logic_full_audit_v2_train_chunk2 | `60/60` |
| support_logic_full_audit_v3_train_chunk3 | `20/20` |
| support_logic_validate_v5_train | `6/6` |
| support_logic_validate_v6_test | `2/2` |
| support_logic_repro_wfg0001_8016_fix | `2/2` |
| 合计 | `172/172` |

而且这 `172` 条最终通过的路径还有两个很关键的附加结果：

- `hard_constraint_violations = 0`
- `invalid_transition_count = 0`

也就是说：

- 它们不是“侥幸完成”；
- 而是按照 benchmark 自己定义的规则，合法地完成了。

### 3.4 早期失败并不是坏事，关键是我们有“前后对照”

这一点很适合跟导师解释，因为它能体现我们不是在空讲，而是真的做了 debugging 闭环。

一个非常直观的例子是 support test 审计：

| 阶段 | 结果 |
| --- | ---: |
| `support_logic_full_audit_v1_test` | `0/20` |
| `support_logic_full_audit_v2_test` | `20/20` |

这个对照说明：

- 早期确实存在真实问题；
- 但这些问题不是“模型太弱”，而是 benchmark 自身的逻辑 / 资产 / 绑定有问题；
- 修掉之后，同一批逻辑检查能从 `0/20` 变成 `20/20`。

这类前后对照，比单纯说“我们做了很多修复”更有说服力。

### 3.5 针对重点疑难 case 的复审：最新 `9/9` 全通过

我们还对一批曾经出过问题的重点 goal 做了 targeted re-audit。最新结果是：

| Goal | 路径数 | 最新结果 |
| --- | ---: | ---: |
| `WFG-SUPPORT-0013` | `3` | `3/3` 通过 |
| `WFG-HOME-0280` | `2` | `2/2` 通过 |
| `WFG-SUPPORT-0207` | `2` | `2/2` 通过 |
| `WFG-SUPPORT-0001` | `2` | `2/2` 通过 |
| 合计 | `9` | `9/9` 通过 |

这部分的意义是：

- 我们不是只做大盘统计；
- 对那些真正暴露过逻辑问题的重点 case，也做了逐条回归；
- 目前这些重点 case 的最新状态已经是全通过。

## 4. benchmark 难度这周发生了什么变化

这一部分是“为什么现在 benchmark 又重新有意义”的关键。

### 4.1 本周 hardening 前，我们发现它确实太短了

之前的链长审计报告：

- `/Users/masteryth/Documents/webagent/rl_memory/reports/workflow_chain_length_audit_v20.md`
- `/Users/masteryth/Documents/webagent/rl_memory/reports/workflow_chain_length_audit_v20.json`

当时看到的核心问题是：

| 指标 | 数值 |
| --- | ---: |
| active blueprints | `504` |
| 短链 blueprint（`max_chain_len <= 3`） | `281` |
| 短链 goal | `2810` |

也就是说，最开始有超过一半的 blueprint 还是 3 步及以下的短链，这很容易让模型通过 shortcut 做出来。

### 4.2 本周 hardening 后，结构上已经切到 5~6 步为主

我们对 `workflow_generation_blueprints.json` 的当前版本重新统计后，结果是：

| 指标 | 数值 |
| --- | ---: |
| active blueprints | `504` |
| 最短成功路径 `<= 4` 的 blueprint 数 | `0` |
| 平均路径长度 | `5.0533` |
| 路径长度中位数 | `5` |
| 最短路径长度最小值 | `5` |
| 最长路径长度最大值 | `6` |
| 平均 path 数 | `1.8988` |

当前 blueprint 的路径分布是：

| 路径结构 | blueprint 数 |
| --- | ---: |
| `(5, 5)` | `423` |
| `(5,)` | `46` |
| `(6, 6)` | `16` |
| `(6, 5)` | `14` |
| `(6,)` | `5` |

一句通俗解释就是：

- 我们已经把“很多一两步就能结束的任务”，收成了“绝大多数要走 5 到 6 步”的任务。
- 而且不是只改一个主题，`14` 个主题现在最短路径都已经至少是 `5` 步。

## 5. 现在 Qwen 在 benchmark 上的表现是多少

这里要分成两层讲，不然容易混淆：

### 5.1 在 clean benchmark 上，Qwen 已经接近饱和

这个结论来自已经完成、可复现的稳定结果：

| 评测 | 结果 |
| --- | ---: |
| dev full strict | `140/140 = 100%` |
| test full strict | `140/140 = 100%` |
| train module-cover probe | `42/42 = 100%` |
| train stratified sample | `196/196 = 100%` |

这说明：

- 如果 benchmark 只停留在“clean 但不继续收难”的状态，`Qwen2.5-7B-Instruct` 已经几乎做穿了。
- 这也是为什么我们这周后半段必须把工作重点从“修 bug”切到“收短链、收 shortcut、提高依赖性”。

### 5.2 在本周 hardening 之后，Qwen 的阶段性成功率已经明显掉下来了

当前最新一轮 train 全量 hardening run 还没有完全跑完，所以这个数字只能算 **中期结果**，不能当成最终结论。

但在最近一次中途分析里：

| 指标 | 数值 |
| --- | ---: |
| 已完成样本数 | `305` |
| 成功数 | `21` |
| 阶段性成功率 | `21/305 ≈ 6.9%` |

并且这 `305` 个已完成样本里，我们看到：

- 失败样本数 `284`
- `hard_constraint_violations` 只有 `5` 个，而且都属于 `max_steps_exceeded`
- 大量失败不是“任务无解”，而是 planner 没有走完新的长链，或者在前置条件没补齐时就提前选了后面的 module

这说明一个很重要的判断：

- 当前 hardening 之后，benchmark 的难点开始真正落在“规划长链”和“补足前置条件”上；
- 而不是 benchmark 自己逻辑错误导致模型白白送分。

换句话说，现在的低成功率开始更像是 **模型跟不上 benchmark 难度**，而不是 **benchmark 本身有 bug**。

## 6. 为什么现在可以说“benchmark 还是有意义的”

如果导师问“Qwen 之前都 90% 甚至 100% 了，那这个 benchmark 还有什么意义”，可以直接这样解释：

第一层：`clean benchmark` 的高分，不代表 benchmark 没意义。

- 它说明我们前面修 correctness / infra 的方向是对的；
- 因为模型不再被 benchmark 本身的错误误伤了。

第二层：高分反而暴露了 benchmark 需要进入下一阶段。

- 也就是从“先修对”转向“再收难”。

第三层：这周 hardening 之后，Qwen 的阶段性表现已经明显下降。

- 这恰好说明 benchmark 重新获得了区分度；
- 也就是它不再是一个“大家都能轻松做满分”的数据集。

所以更准确的说法不是：

- “benchmark 没意义了”；

而是：

- “clean 版本已经接近饱和，所以我们必须继续做 difficulty calibration（难度校准）；而这周的 hardening 已经初步证明这条路是有效的。”

## 7. 一些术语的通俗解释

为了汇报时不绕，下面几个词可以直接这么解释：

| 术语 | 通俗解释 |
| --- | --- |
| `infra` | benchmark 的运行底座，比如任务环境、页面绑定、日志、状态写回这些“底层工程问题” |
| `logic audit` | 逻辑审计，检查任务链本身是不是讲得通、能不能顺着做完 |
| `oracle` | benchmark 自己藏着的一份“标准答案”，规定哪些 module 顺序合法、最后什么状态算成功 |
| `planner` | 上层决策器，负责判断“下一步该选哪个 module” |
| `module` | 一个相对稳定的小功能块，比如“联系客服”“预约签证”“同步日历” |
| `invalid transition` | 不合法跳转，也就是“现在还不该做这一步，却提前做了” |
| `shortcut` | 捷径，也就是模型绕开真正任务链，用过于简单的路径就把任务做完 |
| `hardening` | 收难，也就是把 benchmark 从“太短太顺”改成“更长、更有依赖、更接近真实流程” |

## 8. 目前最适合对导师说的结论

如果要压缩成几句话，可以直接这么说：

1. 这周我们先把 benchmark 的 correctness 和 infra 基本收口了，不再是靠人工抽样判断，而是有全量程序化统计支撑。
2. 现在全量 `5040` 个 goal 都至少有一条合法可行路径，所有声明成功路径也都可执行，非法路径数是 `0`。
3. 自动 realism audit 目前 `issue_count = 0`，修复后的 support 逻辑回归最终集合是 `172/172` 全通过，重点问题 case 最新 `9/9` 全通过。
4. 在 clean 版本上，`Qwen2.5-7B-Instruct` 已经接近做穿，所以我们这周后半段开始系统性 harden benchmark。
5. hardening 后，benchmark 的最短链已经整体从过去大量 `<=3` 步，收成了现在统一 `>=5` 步；最近一轮 train 全量中期统计里，Qwen 阶段性成功率已经掉到大约 `6.9%`，说明 benchmark 重新开始有区分度了。

## 9. 还需要继续补的地方

虽然现在进展已经比较扎实，但也要实话实说，下面几点还在继续推进：

- 当前 round60 train full 还没完全跑完，所以 hardening 后的全量最终分数还不能下最终结论。
- dev/test split 虽然逻辑和结构都已经 clean，但从 split 审计上看，dev/test 的 blueprint 数还是偏小，这更像一个评测设计层面的后续问题，不是 correctness 问题。
- 现在失败归因的新 trace 已经补上，下一轮 rerun 之后，我们可以更系统地区分：到底是 planner 短视、前置条件没补齐，还是底层网页交互还留有 residual。

