# 论文主图与实验图链接清单

说明：

- 当前 shell 环境无法直接把远程 PDF/图片下载为本地 PNG，因为外网 DNS 在 shell 中被重定向到了 `198.18.0.x`。
- 因此，这里保存的是 `可直接打开的图像 URL`、`表格位置`、`页码/章节定位`。
- 对能拿到稳定图像 URL 的论文，我直接给出 Markdown 图片和原链接。
- 对 ar5iv 转换失败或只有表格没有独立 figure 的论文，我保存 `source + section/table/page ref`。

## 1. MLGym

来源：
[paper](https://arxiv.org/abs/2502.14499)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2502.14499/assets/x1.png)

![MLGym main](https://ar5iv.labs.arxiv.org/html/2502.14499/assets/x1.png)

实验主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2502.14499/assets/x2.png)

![MLGym results](https://ar5iv.labs.arxiv.org/html/2502.14499/assets/x2.png)

说明：

- 主图是 Figure 1，环境/agent/computer 三方交互框架图。
- 实验图是 Figure 2，Best Attempt@4 与 Best Submission@4 的 performance profile。

## 2. MLE-Dojo

来源：
[paper](https://arxiv.org/abs/2505.07782)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2505.07782/assets/x4.png)

![MLE-Dojo overview](https://ar5iv.labs.arxiv.org/html/2505.07782/assets/x4.png)

实验图：
[direct image](https://ar5iv.labs.arxiv.org/html/2505.07782/assets/x9.png)

![MLE-Dojo cost-performance](https://ar5iv.labs.arxiv.org/html/2505.07782/assets/x9.png)

补充图：
[task diversity](https://ar5iv.labs.arxiv.org/html/2505.07782/assets/x2.png)

说明：

- 主图用 Figure 4，比 Figure 1 更能体现环境结构。
- 实验图选 Figure 9，直接展示 cost-performance 关系，和你的“有限预算”主题最相关。

## 3. MLAgentBench

来源：
[paper](https://arxiv.org/abs/2310.03302)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2310.03302/assets/ranew.png)

![MLAgentBench main](https://ar5iv.labs.arxiv.org/html/2310.03302/assets/ranew.png)

实验图：
[direct image](https://ar5iv.labs.arxiv.org/html/2310.03302/assets/x3.png)

![MLAgentBench average improvement](https://ar5iv.labs.arxiv.org/html/2310.03302/assets/x3.png)

说明：

- 主图是 benchmark overview。
- 实验图是 Figure 4，展示不同任务上相对 baseline 的平均改进。

## 4. MLE-bench

来源：
[paper](https://arxiv.org/abs/2410.07095)
[OpenReview PDF](https://openreview.net/pdf/5ae71a36cd002781ebfc8b012440d031b9df8225.pdf)

主图定位：

- Figure 1 在 PDF 第 2 页附近。
- 关键文字：offline Kaggle environment，description + dataset + grading code + leaderboard。

实验图 / 实验页定位：

- Figure 2 在 PDF 第 3 页附近，展示不同 agent scaffold 的真实 trajectory。
- 资源扩展和 contamination 讨论在后文结果与分析部分。

说明：

- ar5iv HTML 转换失败，因此当前环境下没有提取到稳定图片 URL。
- 这篇建议后续在可联网 shell 环境里再单独导出 PNG。

## 5. ML-Dev-Bench

来源：
[paper](https://arxiv.org/abs/2502.00964)

主要实验 artifact：

- [Table 2 / ar5iv HTML](https://ar5iv.labs.arxiv.org/html/2502.00964v3)

说明：

- 这篇论文几乎没有可单独抽出的 figure，主要结果是表格。
- 最重要的是：
  - Table 1: task categories
  - Table 2: category-wise success rates
  - Table 3: task-level comparison

推荐引用位置：

- `ar5iv` 开头的 Table 1, Table 2, Table 3

## 6. ML-Bench

来源：
[paper](https://arxiv.org/abs/2311.09835)

主图：
[direct image](https://ar5iv.org/html/2311.09835/assets/figures/main.png)

![ML-Bench main](https://ar5iv.org/html/2311.09835/assets/figures/main.png)

实验图：

- 由于 ar5iv 重定向限制，图像未能直接展开，但目标资源路径已经定位到：
  - `https://ar5iv.labs.arxiv.org/html/2311.09835/assets/x3.png`
  - `https://ar5iv.labs.arxiv.org/html/2311.09835/assets/x4.png`

结果表：

- Main results：Table 3（Pass@1 / Pass@2 / Pass@5）
- Error analysis：Figure 5 / `x4.png`

说明：

- 如果后面换到可联网 shell，优先把 `main.png`、`x3.png`、`x4.png` 拉下来。

## 7. TML-Bench

来源：
[paper](https://arxiv.org/abs/2603.05764)

说明：

- 当前环境没有成功提取到 ar5iv figure asset。
- 这篇最关键的信息其实已经在 abstract 里：
  - 4 个 competition
  - 240s / 600s / 1200s 三档预算
  - 每个组合 5 次运行
  - 报告 median、success rate、variability

建议后续导出的优先位置：

- main benchmark figure
- budget scaling figure
- aggregate comparison figure

## 8. AgentHPO

来源：
[paper](https://arxiv.org/abs/2402.01881)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2402.01881/assets/x2.png)

![AgentHPO main](https://ar5iv.labs.arxiv.org/html/2402.01881/assets/x2.png)

实验图：
[direct image](https://ar5iv.labs.arxiv.org/html/2402.01881/assets/x5.png)

![AgentHPO trajectory](https://ar5iv.labs.arxiv.org/html/2402.01881/assets/x5.png)

说明：

- 主图是 Figure 2，显示 Creator/Executor/Exp Logs 的完整流程。
- 实验图这里选 GPT-4 trajectory 相关图，体现 AgentHPO 的搜索行为。

## 9. BudgetMLAgent

来源：
[paper](https://arxiv.org/abs/2411.07464)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2411.07464/assets/Figures/budgetmlagent.png)

![BudgetMLAgent main](https://ar5iv.labs.arxiv.org/html/2411.07464/assets/Figures/budgetmlagent.png)

实验结果定位：

- 主要结果集中在 Table 2 与 Section 4.4。
- 这里没有稳定抽出的单独 results figure，核心结果是 success rate / average cost 表格。

说明：

- 这篇对你最重要的不是视觉图，而是 Table 2 里的“成功率-成本”联合比较。

## 10. HPOBench

来源：
[paper](https://arxiv.org/abs/2109.06716)

主图替代：
[code example figure](https://ar5iv.labs.arxiv.org/html/2109.06716/assets/figures/other/code.png)

![HPOBench code example](https://ar5iv.labs.arxiv.org/html/2109.06716/assets/figures/other/code.png)

实验图代表 panel：
[ECDF panel](https://ar5iv.labs.arxiv.org/html/2109.06716/assets/more_figures/ecdf/tabular_lr.png)

![HPOBench ECDF panel](https://ar5iv.labs.arxiv.org/html/2109.06716/assets/more_figures/ecdf/tabular_lr.png)

说明：

- Figure 1 的总览图没有直接抽出成稳定 asset，但 Figure 2 和 Figure 3 的 asset 路径已经定位。
- 如果后续单独下载，建议再补一张完整的 Figure 1 overview。

## 11. YAHPO Gym

来源：
[arXiv](https://arxiv.org/abs/2109.03670)
[PMLR](https://proceedings.mlr.press/v188/pfisterer22a.html)

说明：

- 当前环境没有提取出稳定的 figure asset。
- 这篇建议后续优先导出：
  - benchmark overview figure
  - surrogate vs tabular comparison figure
  - single-objective / multi-objective optimizer comparison figure

## 12. HPO-B

来源：
[paper](https://arxiv.org/abs/2106.06257)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2106.06257/assets/resources/figure1-averages.png)

![HPO-B non-transfer](https://ar5iv.labs.arxiv.org/html/2106.06257/assets/resources/figure1-averages.png)

实验图：
[direct image](https://ar5iv.labs.arxiv.org/html/2106.06257/assets/resources/figure2-averages.png)

![HPO-B transfer](https://ar5iv.labs.arxiv.org/html/2106.06257/assets/resources/figure2-averages.png)

说明：

- Figure 1 对应 non-transfer HPO。
- Figure 2 对应 transfer HPO / surrogate-acquisition comparison。
- 这两张图很适合放到你 related work 的配图素材里。

## 13. Bayesian Optimization is Superior to Random Search... (BBO Challenge 2020)

来源：
[paper](https://arxiv.org/abs/2104.10201)

主图：
[direct image](https://ar5iv.labs.arxiv.org/html/2104.10201/assets/x1.png)

![BBO final leaderboard](https://ar5iv.labs.arxiv.org/html/2104.10201/assets/x1.png)

实验图：
[direct image](https://ar5iv.labs.arxiv.org/html/2104.10201/assets/x3.png)

![BBO warm-start leaderboard](https://ar5iv.labs.arxiv.org/html/2104.10201/assets/x3.png)

说明：

- Figure 1 是 final leaderboard vs random search。
- Figure 3 是 warm-start leaderboard vs random search。
- 这两张图最能体现“固定预算下，BO 显著优于随机搜索”的 challenge message。

