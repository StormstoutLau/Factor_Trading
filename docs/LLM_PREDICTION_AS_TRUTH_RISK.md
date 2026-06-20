# LLM预测替代真实值的推断风险 · 问题跟踪

> 创建日期：2026-06-06
> 状态：活跃
> 来源：FormalProbability DSL 模块分析 + 学术文献调研
> 关联文档：[FormalProbability DSL 对 Blogger Distillation 的适用性分析](file:///D:/Textbook/docs/superpowers/status/2026-06-20-formalprobability-dsl-for-blogger-distillation.md)

---

## 一、问题定义

### 核心问题

在因子挖掘和Blogger蒸馏系统中，LLM用于从文本提取结构化信号（情绪、主题暴露、事件标签），这些预测值被直接当作真实值输入下游回测引擎。**即使LLM准确率达到90%+，剩余的系统性错误会导致推断偏差，且无法通过增大样本量消除。**

### 数学表述

```
传统（错误）路径：
  文本 → LLM → Ŷ (预测标签) → 当作Y (真实标签) → 回测 → 偏差推断

校正路径（DSL）：
  文本 → LLM → Ŷ (预测标签)
  文本 → 人工标注 → Y (真实标签，仅R=1时)
  校正：Ỹ = Ŷ - (R/π)(Ŷ - Y)  → E[Ỹ|X] = E[Y|X] → 无偏推断
```

### 定理依据

| 定理 | 来源 | 内容 | 影响 |
|------|------|------|------|
| Theorem 1 | DSL MainTheorems | IPW校正后，LLM质量不影响推断有效性 | 不需要等LLM完美 |
| Theorem 2 | DSL MainTheorems | LLM预测越准，标准误越小 | 投资LLM/人工标注有量化回报 |
| **Theorem 3** | DSL MainTheorems | **直接把LLM预测当真实值，偏差不可通过增大样本量消除** | **当前系统最严重的风险** |

---

## 二、学术文献追踪

### 核心论文

| 年份 | 论文 | 期刊/预印本 | 关键贡献 |
|------|------|-----------|---------|
| 1984 | Pagan, *Econometric Issues in the Analysis of Regressions with Generated Regressors* | IER | 理论源头：用估计值替代真实值的统计后果 |
| 2018 | Chernozhukov et al., *Double/Debiased Machine Learning* | Econometrics Journal | Neyman-正交矩 + 交叉拟合消除ML预测偏差 |
| 2023 | Angelopoulos et al., *Prediction-Powered Inference* | **Science** | 通用框架：用ML预测值做推断，置信区间保持有效覆盖 |
| 2025 | Ruan et al., *Can Language Models Boost the Power of Randomized Experiments Without Statistical Bias?* | arXiv:2510.05545 | CALM框架：LLM预测 + 异质性校准 = 一致推断 |
| 2025 | Kostikova et al., *LLM Analysis of 150+ Years of German Parliamentary Debates* | arXiv:2509.07274 | **与DSL完全一致的方法**：即使GPT-5达到人类水平，系统性错误仍会偏差下游结果 |

### 关键发现

> Kostikova et al. (2025): "即使最强的模型（GPT-5, gpt-oss-120B）达到人类水平的一致性，其错误仍然是**系统性的**，并且会**偏差下游结果**。LLM可以支持大规模文本分析，但**仅当其输出经过严格验证和统计校正时**。"

### 文献待追踪

- [ ] PPI的后续扩展（2024-2025的引用论文）
- [ ] 金融领域LLM标签偏差的实证研究
- [ ] DSL在高维/正则化场景的扩展

---

## 三、风险映射：我系统的影响面

| 系统模块 | 风险描述 | 严重程度 | 学术解方 |
|---------|---------|---------|---------|
| **Agent博主蒸馏** (`agents/`) | LLM提取→信号→回测，偏差累积传播 | 🔴 严重 | PPI + DSL校正 |
| **因子失效诊断** (计量论文) | 诊断框架依赖L2产出，噪声传播未量化 | 🟡 中等 | CALM校准框架 |
| **因子协方差** (L4 Barra桥) | 预测暴露替代真实暴露，协方差矩阵有偏 | 🔴 严重 | designAdjustedOutcome |
| **Judge模型评估** (L2.5) | Judge系统性偏差未被校准 | 🟡 中等 | JudgeCalibration |
| **因子预处理** (`factor_pipeline`) | 预处理假设因子值可靠，源头来自L2预测 | 🟡 中等 | 输入端校正 |

---

## 四、行动计划

### P0: JudgeCalibration 集成 (1-2周) ⬜ 未开始

- [ ] 对一小部分博主文章做人工标注（oracle，~100篇）
- [ ] 用Judge LLM对同一批文章打分
- [ ] 计算 `judgeBias` 和 `judgeStd`
- [ ] 检测 `hasSignificantBias` 是否显著
- [ ] 如果显著，实现 `surrogate_bound` 校正

### P1: 因子协方差的设计调整 (2-4周) ⬜ 未开始

- [ ] 选取少量股票人工标注因子暴露（黄金样本，~50只）
- [ ] 实现 `designAdjustedOutcome` 校正公式：`β̃ = β̂ - (R/π)(β̂ - β)`
- [ ] 用 β̃ 替代 β̂ 估计因子协方差矩阵
- [ ] 对比校正前后的回测结果差异
- [ ] 验证校正后推断有效性

### P2: ClusteredVariance 集成 (1周) ⬜ 未开始

- [ ] 按行业聚类计算标准误
- [ ] 按时间维度聚类（处理自相关）
- [ ] 对比Naive SE vs Clustered SE

### P3: 回测引擎输入端校正层 (2-4周) ⬜ 未开始

- [ ] 在 `engine_v2.py` 的因子输入层添加校正模块
- [ ] 支持配置是否启用DSL校正
- [ ] 添加校正效果的TDD测试

### P4: 贝叶斯扩展 (长期) ⬜ 未开始

- [ ] 将DSL的ValidInference扩展到贝叶斯框架
- [ ] 证明 designAdjustedOutcome 的后验有效性
- [ ] 或考虑L3使用频率派估计，L4做贝叶斯汇总

---

## 五、变更日志

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-06-06 | 初始创建，完成问题定义、文献追踪、风险映射、行动计划 | AI + StormstoutLau |

---

## 六、相关资源

| 资源 | 路径/链接 |
|------|---------|
| DSL适用性分析 | [FormalProbability DSL for Blogger Distillation](file:///D:/Textbook/docs/superpowers/status/2026-06-20-formalprobability-dsl-for-blogger-distillation.md) |
| FormalProbability DSL | [FormalProbability/DSL/](file:///d:/Textbook/external_repos/FormalProbability/FormalProbability/DSL/) |
| PPI (Science 2023) | [Semantic Scholar](https://www.semanticscholar.org/paper/96f75d06ce8bc26128f0af0071b374d065bf7d64) |
| CALM (2025) | [arXiv:2510.05545](https://arxiv.org/abs/2510.05545) |
| DSL+LLM (2025) | [arXiv:2509.07274](https://arxiv.org/abs/2509.07274) |