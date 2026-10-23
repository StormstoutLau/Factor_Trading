# LLM预测替代真实值的推断风险 · 问题跟踪

> 创建日期：2026-06-06
> 最后更新：2026-06-20（新增讨论过程记录 · 第九章）
> 状态：活跃
> 来源：FormalProbability DSL 模块分析 + 学术文献调研 + 四轮方法论审计
> 关联文档：[FormalProbability DSL 对 Blogger Distillation 的适用性分析](file:///D:/Textbook/docs/superpowers/status/2026-06-20-formalprobability-dsl-for-blogger-distillation.md)

---

## 一、问题定义

### 核心问题

在因子挖掘和Blogger蒸馏系统中，LLM用于从文本提取结构化信号（情绪、主题暴露、事件标签），这些预测值被直接当作真实值输入下游回测引擎。**即使LLM准确率达到90%+，剩余的系统性错误会导致推断偏差，且无法通过增大样本量消除。**

### DSL 的本质：小样本人工校准 + IPW 校正传播

DSL 的 `designAdjustedOutcome` 公式不需要标注全部数据：

```
Ỹ = Ŷ - (R/π)(Ŷ - Y)
     │    │      │
     │    │      └─ 人工标注值（仅 R=1 时存在，仅需 1-5% 样本）
     │    └─ 采样率的倒数（IPW 权重，标注越少权重越大）
     └─ LLM 预测值（全量，100% 数据）
```

**关键洞察**：1% 的人工标注足以校正 99% 的 LLM 预测。不是"又回到人工标注"，而是"用极小成本撬动全量推断有效性"。

### 数学表述

```
传统（错误）路径：
  文本 → LLM → Ŷ (预测标签) → 当作 Y (真实标签) → 回测 → 偏差推断

校正路径（DSL）：
  文本 → LLM → Ŷ (预测标签)
  文本 → 人工标注 → Y (真实标签，仅 R=1 时)
  校正：Ỹ = Ŷ - (R/π)(Ŷ - Y)  → E[Ỹ|X] = E[Y|X] → 无偏推断
```

### 定理依据

| 定理 | 来源 | 内容 | 影响 |
|------|------|------|------|
| Theorem 1 | DSL MainTheorems | IPW校正后，LLM质量不影响推断有效性 | 不需要等LLM完美 |
| Theorem 2 | DSL MainTheorems | LLM预测越准，标准误越小 | 投资LLM/人工标注有量化回报 |
| **Theorem 3** | DSL MainTheorems | **直接把LLM预测当真实值，偏差不可通过增大样本量消除** | **当前系统最严重的风险** |

---

## 二、原创性分析

### 方法论不新，但有三重新贡献

| 组件 | 来源 | 年代 | DSL 的增量 |
|------|------|------|-----------|
| IPW 逆概率加权 | Horvitz & Thompson | 1952 | — |
| 设计推断框架 | Neyman, Cochran | 1934-1977 | — |
| 预测驱动推断 | Angelopoulos et al. (Science) | 2023 | — |
| **形式化证明** | DSL | 2025 | Lean4 证明定理，前提显式声明 |
| **LLM 偏差适配** | DSL | 2025 | JudgeCalibration 专门处理 LLM 系统性偏差 |
| **模块化 DSL** | DSL | 2025 | 可复用管道，不要求用户理解证明细节 |

### 学术定位

在论文中应诚实声明：
> "Our framework builds on the design-based inference tradition (Neyman 1934; Cochran 1977) and the prediction-powered inference framework (Angelopoulos et al. 2023). The novel contribution is formal verification in Lean4, adaptation to LLM-specific bias structures, and a modular DSL."

### 人工标注偏见的争议与应对

**争议**：人工标注也有系统性偏差，Y 不是绝对真值。

**DSL 的应对**：

| 应对 | 机制 | 效果 |
|------|------|------|
| JudgeCalibration | 显式建模 `judgeBias = E[Ŷ_judge - Y_consensus]` | 检测并量化标注者偏差 |
| 多标注者聚合 | Y = Aggregate(Y₁, Y₂, ..., Yₖ) | 个体偏差被投票消除 |
| 操作定义 | Y 是"至少 3 人中 2 人同意" | 不声称形而上学的真实 |
| 形式化前提 | 定理精确声明前提 "IF E[Y|X] is well-defined" | 前提不成立时定理不适用 |

**论文中应诚实讨论**：
> "For inherently subjective tasks, the 'true' label is a statistical construct rather than an objective reality. Our guarantees are with respect to the operationalized Y, not an unobservable ground truth."

---

## 三、学术文献追踪

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

## 四、DSL 元理论 vs 标注验证：形式化闭环分析

### 四层验证模型（经过四轮方法论审计后收敛）

```
┌──────────────────────────────────────────────────────┐
│  Layer 1: 统计有效性 (DSL)                            │
│  → 校正公式保证推断有效                                │
│  → Lean4 证明元定理                                    │
├──────────────────────────────────────────────────────┤
│  Layer 2: 标注类型/结构验证 (Pydantic/Schema)         │
│  → direction ∈ {bullish,bearish,neutral}             │
│  → 日期格式、字段类型检查                              │
│  → 不需要 Lean4，用 schema 验证即可                    │
├──────────────────────────────────────────────────────┤
│  Layer 3: 标注内部一致性 (规则引擎，当前阶段)           │
│  → claim 文本 vs direction 矛盾检测                   │
│  → certainty vs verifiable 矛盾检测                   │
│  → 多 opinion 间矛盾检测                              │
│  → 规则稳定后（>6个月，>10000条）可考虑 Lean4 迁移     │
├──────────────────────────────────────────────────────┤
│  Layer 4: 域有效性 (LLM Judge + 市场反馈)             │
│  → 推理链是否金融上合理                                │
│  → certainty 是否与证据匹配                            │
│  → 市场走势作为延迟 ground truth（金融独有优势）        │
│  → DSL 的 JudgeCalibration 负责统计偏差校正            │
│  → LLM Judge 负责语义判断（两者分开实现）              │
└──────────────────────────────────────────────────────┘
```

### 关键区分

**DSL 的 Lean4 证明是元理论层面的**：证明"校正公式的统计性质"，不涉及任何一条具体标注的正确性。类比：你证明了 OLS 估计量的一致性，但不验证每一行数据是否填对。

**标注验证需要的是另一套工具**：Layer 2 用 Pydantic/Schema，Layer 3 用规则引擎，Layer 4 用 LLM Judge + 市场反馈。Lean4 只在 Layer 3 的复杂约束（>100条规则，含跨实体推理，规则已稳定）场景下才优于规则引擎。

### 重要区分：JudgeCalibration ≠ LLM Judge

| | JudgeCalibration | LLM Judge |
|---|---|---|
| 输入 | (Ŷ_judge, Y_oracle) 对的集合 | 单条标注 |
| 输出 | `judgeBias = E[Ŷ_judge - Y_oracle]` | "这条标注方向是否合理" |
| 本质 | 统计偏差校正 | 语义判断 |
| 运行模式 | 批量数据 | 可单条运行 |
| 归属 | Layer 4 统计层 | Layer 4 语义层 |

### 金融领域独有优势：时间维度 ground truth

市场走势提供延迟 ground truth——如果 LLM 标注了 "certainty=high, direction=bullish"，而该股票三个月后跌了 30%，标注就是错的。这个反馈机制是金融市场独有的，其他标注领域（政治倾向、情感分析）没有。Layer 4 的"市场反馈"不是通用的，是金融领域的天然优势。

### 收敛决策：Layer 3 工具选择

**当前阶段：规则引擎。** 理由：规则还在演化，过早形式化等于做两次。等系统运行 6 个月、处理 10000+ 标注、规则稳定后，再评估是否迁移到 Lean4。此决策可逆。

| 约束复杂度 | 推荐工具 | 原因 |
|-----------|---------|------|
| <50条，频繁变化 | 规则引擎 | 快速修改，低学习成本 |
| 50-100条 | 规则引擎 ≈ Lean4 | 取决于规则稳定性 |
| >100条，已稳定 | Lean4 | 证明项可审计，跨实体推理 |

---

## 五、风险映射：我系统的影响面

| 系统模块 | 风险描述 | 严重程度 | 学术解方 |
|---------|---------|---------|---------|
| **Agent博主蒸馏** (`agents/`) | LLM提取→信号→回测，偏差累积传播 | 🔴 严重 | PPI + DSL校正 |
| **因子失效诊断** (计量论文) | 诊断框架依赖L2产出，噪声传播未量化 | 🟡 中等 | CALM校准框架 |
| **因子协方差** (L4 Barra桥) | 预测暴露替代真实暴露，协方差矩阵有偏 | 🔴 严重 | designAdjustedOutcome |
| **Judge模型评估** (L2.5) | Judge系统性偏差未被校准 | 🟡 中等 | JudgeCalibration |
| **因子预处理** (`factor_pipeline`) | 预处理假设因子值可靠，源头来自L2预测 | 🟡 中等 | 输入端校正 |

---

## 六、行动计划

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

### P5: Layer 3 一致性验证 (后续) ⬜ 未开始

- [ ] 实现 Pydantic Schema 验证（Layer 2，类型/结构检查）
- [ ] 实现规则引擎一致性检查（Layer 3，当前阶段）
- [ ] 规则稳定后（>6个月，>10000条）评估 Lean4 迁移

---

## 九、讨论过程记录：六轮迭代收敛

### 背景

用户提供了 FormalProbability DSL 文档（`2026-06-20-formalprobability-dsl-for-blogger-distillation.md`），要求分析 DSL 对 Blogger Distillation 系统的适用性。DSL 的核心主张是：**即使 LLM 预测准确率达到 90%，直接将预测值当作真实值输入下游推断，会导致不可逆的偏差（Theorem 3）**。

从这一核心主张出发，展开了六轮递进式讨论，每一轮都在前一伦的基础上深化一个维度。

---

### 第一轮：问题普遍性 & 学术溯源

**用户提问**：
> "FormalProbability 的 DSL 模块证明了：即使近似正确（90%准确率），也会导致推断不可逆地失效。分析这种问题在如今 LLM 提取的范式下是否普遍存在，是否有学术研究正式讨论过该问题。"

**分析过程**：

1. **问题普遍性判断**：LLM 预测替代真实值的陷阱在以下场景普遍存在：
   - 情感分析 → 因子信号（Blogger Distillation 的核心链路）
   - 主题分类 → 行业暴露（L2 → L4 Barra 桥）
   - 事件检测 → 事件驱动策略（事件标签 → 回测信号）
   - 关键：LLM 错误是**系统性**的而非随机的——模型对某类文本（模糊表述、讽刺、专业术语）一致地犯错，这种系统性偏差无法通过增大样本量稀释。

2. **学术文献溯源**：问题的理论根源可追溯到 1984 年 Pagan 的"Generated Regressors"经典论文，但直到 2023 年 Angelopoulos et al. 在 Science 上发表 PPI 框架，才给出了通用解。完整文献链：
   ```
   Pagan (1984) → DML (2018) → PPI (2023) → CALM (2025) → DSL+LLM (2025)
   ```

3. **关键发现**：Kostikova et al. (2025) 在 arXiv:2509.07274 中独立得出了与 DSL 完全一致的结论——即使 GPT-5 达到人类水平，系统性错误仍会偏差下游结果。这为 DSL 的主张提供了独立验证。

**产出**：确认问题的学术严肃性，建立了文献追踪体系（见第三章）。

---

### 第二轮：方案 C 的本质识别

**用户提问**：
> "也就是说，方案 C 实际上就是加入人工校准环节。"

**分析过程**：

1. **本质确认**：是的，方案 C 就是在 LLM 全量预测的基础上，对小比例样本（1-5%）进行人工标注，然后用 IPW 公式校正全部预测值。

2. **关键洞察点**：这不是"又回到人工标注"的倒退，而是"用极小成本撬动全量推断有效性"的杠杆操作：
   - 传统方案：标注 100% 数据 → 成本极高
   - 纯 LLM 方案：标注 0% 数据 → 偏差不可消除
   - DSL 方案：标注 1-5% 数据 → 校正 100% 推断 → 偏差可控

3. **数学直觉**：`Ỹ = Ŷ - (R/π)(Ŷ - Y)` 的本质是"用少量真实值 Y 去修正大量预测值 Ŷ 的系统性偏差"。IPW 权重 `1/π` 的含义是：如果只标注了 1% 的样本，那么每条标注的"权重"是 100 倍——它代表的不是自己，而是 100 条同类预测的校正信息。

**产出**：明确了 DSL 的实践路径，消除"又回到人工标注"的误解。

---

### 第三轮：原创性争议 & 人工标注的学术正当性

**用户提问**：
> "这种方法具有原创性吗？还是说人工校准环境标注员的主观偏差容易在学术上引起争议？"

**分析过程**：

1. **原创性逐层拆解**：
   - IPW 本身 → 1952 年 Horvitz & Thompson，不新
   - 设计推断框架 → 1934-1977 年 Neyman/Cochran，不新
   - 预测驱动推断 → 2023 年 Angelopoulos et al. (Science)，不新
   - **DSL 的三重增量**：① Lean4 形式化证明（前提显式声明），② LLM 偏差适配（JudgeCalibration），③ 模块化 DSL（可复用管道）

2. **人工标注偏见的争议**：这确实是学术评审中可能被攻击的点——"Y 也不是绝对真值，人工标注也有系统性偏差"。DSL 的四层防御：
   - JudgeCalibration：显式建模 `judgeBias = E[Ŷ_judge - Y_consensus]`，量化标注者偏差
   - 多标注者聚合：个体偏差被投票消除
   - 操作定义：Y 是"至少 3 人中 2 人同意"，不声称形而上学真实
   - 形式化前提：定理精确声明前提条件，前提不成立时定理不适用

3. **论文中的诚实策略**：建议在论文中直接声明 Y 是操作定义而非绝对真值，并在 limitation 部分诚实讨论。这种做法在计量经济学中是标准操作，不会被学术界视为缺陷。

**产出**：建立了原创性分析框架（见第二章），明确了学术定位和争议应对策略。

---

### 第四轮：Lean4 形式化验证的边界

**用户提问**：
> "DSL 里面形式化工作，实际上是严格证明了人工校准+IPW校正传播的数学性质。那么 LLM 在参与标注的过程中是否使用 Lean4 形式化验证机制来做判断闭环？"

**分析过程**：

1. **关键区分**：DSL 的 Lean4 证明是**元理论层面**的——证明的是"校正公式的统计性质"（如 E[Ỹ|X] = E[Y|X]），不涉及任何一条具体标注的正确性。类比：证明 OLS 估计量的一致性，但不验证每一行数据是否填对。

2. **标注验证需要的是另一套工具**：
   - 类型/结构验证 → Pydantic Schema（不是 Lean4）
   - 内部一致性 → 规则引擎（当前阶段不是 Lean4）
   - 域有效性 → LLM Judge + 市场反馈（不是 Lean4）
   - 只有规则稳定后（>100条，>10000条标注），复杂约束才考虑 Lean4

3. **四层验证模型的诞生**：这一轮讨论直接催生了四层验证模型框架（见第四章）：
   ```
   Layer 1: 统计有效性 (DSL Lean4) → 元理论
   Layer 2: 类型/结构 (Schema) → 数据层
   Layer 3: 内部一致性 (规则引擎) → 标注层
   Layer 4: 域有效性 (LLM Judge) → 语义层
   ```

4. **JudgeCalibration ≠ LLM Judge** 的区分也在这一轮明确：
   - JudgeCalibration：统计偏差校正，输入是 (Ŷ_judge, Y_oracle) 对的集合，输出是 `judgeBias`
   - LLM Judge：语义判断，输入是单条标注，输出是"这条标注方向是否合理"

**产出**：建立了四层验证模型，明确了 Lean4 的适用边界（元理论层面），区分了 JudgeCalibration 和 LLM Judge。

---

### 第五轮：用户对四层分析的元分析

**用户自行分析**（完整记录）：

> 我刚刚也做了一次分析，下面是我的分析过程：

用户对四层验证模型进行了逐层的能力边界评估：

| 层级 | 用户的判断 | 核心逻辑 |
|------|-----------|---------|
| Layer 1 (DSL) | ✅ 正确 | 统计有效性已被 Lean4 证明，前提条件清晰 |
| Layer 2 (Schema) | ✅ 正确 | 类型/结构检查是确定的，不需要推理 |
| Layer 3 (规则引擎) | ⚠️ 怀疑 | 规则引擎能覆盖多少一致性检查？规则会不会膨胀？ |
| Layer 4 (LLM Judge) | ⚠️ 怀疑 | LLM Judge 本身也在制造"预测替代真实"的问题——用 LLM 验证 LLM？ |

**用户的核心担忧**：
1. Layer 3 的规则引擎是否足够强大？会不会出现规则膨胀后无法维护？
2. Layer 4 的 LLM Judge 是否引入了新的偏差源？这不是"用 LLM 验证 LLM"的循环论证吗？
3. 四层模型是否在整体上形成闭环？还是各层之间有未覆盖的裂缝？

---

### 第六轮：对元分析的再分析 & 收敛

**用户要求**：
> "分析一下，给出收敛结论。"

**分析过程**：

1. **Layer 3 的规则引擎问题**：
   - 用户担心规则膨胀 → 确认：当前阶段规则数量少（<50条），规则引擎完全够用
   - 决策阈值：>100条规则 + >10000条标注 + 规则已稳定 → 迁移到 Lean4
   - 关键：此决策可逆，不是一次性选择。规则引擎先跑，稳定后再评估是否迁移

2. **Layer 4 的"用 LLM 验证 LLM"问题**：
   - 这确实是一个真实的担忧，但不是循环论证
   - 原因：LLM Judge 的输入是**单条标注**（语义合理性），而 DSL 校正的输入是**批量标注对**（统计偏差）。两者操作的数据类型不同，解决的问题不同
   - 金融领域的独有优势：**时间维度的延迟 ground truth**——市场走势提供了最终的验证信号。如果 LLM 标注了 "certainty=high, direction=bullish"，而该股票三个月后跌了 30%，标注就是错的。这个反馈机制是其他标注领域（政治倾向、情感分析）没有的
   - Layer 4 的设计是"LLM Judge（语义）+ 市场反馈（GT）+ JudgeCalibration（统计校正）"三重机制，不是单一的 LLM Judge

3. **四层模型的整体闭环判断**：
   ```
   Layer 1 → 保证推断有效性（统计层面）
   Layer 2 → 保证数据格式正确（结构层面）
   Layer 3 → 保证标注不自相矛盾（一致性层面）
   Layer 4 → 保证标注在金融上合理（语义层面）
   
   各层之间确实有未覆盖的裂缝（如跨层交互效应），但这是任何多层验证系统的固有特征。
   关键是：每一层都独立提供了可验证的保证，裂缝的存在不否定各层的有效性。
   ```

4. **收敛决策**：
   - Layer 3 当前阶段：规则引擎（理由：规则在演化，过早形式化 = 做两次）
   - Layer 3 迁移条件：>6个月 + >10000条标注 + 规则稳定 → 评估 Lean4 迁移
   - Layer 4 的 LLM Judge 不是"用 LLM 验证 LLM"，而是三重机制中的一环
   - 金融领域的时间维度 GT 是天然优势，可以持续校准 Layer 4 的判断

**产出**：收敛决策（见第四章末尾），明确了各层的工具选择和迁移条件。

---

### 讨论总结

| 轮次 | 用户问题 | 核心发现 | 文档产出 |
|------|---------|---------|---------|
| 1 | 问题普遍性？学术研究？ | 确认学术严肃性，建立文献链 | 第三章 |
| 2 | 方案 C = 人工校准？ | 确认本质，澄清"1%撬动99%"杠杆 | 第一章 |
| 3 | 方法原创性？标注争议？ | 三重增量，四层防御 | 第二章 |
| 4 | Lean4 做判断闭环？ | 元理论 vs 数据层区分，四层模型诞生 | 第四章 |
| 5 | 用户自行元分析 | Layer 3/4 的边界性质疑 | 第九章本节 |
| 6 | 对元分析的再分析 | Layer 3 可逆决策，Layer 4 三重机制，收敛 | 第四章末尾 |

**方法论启示**：这六轮讨论展示了一个典型的"裂缝探测 → 建造检测工具 → 模块化 → 放入系统"认知循环。每一轮都在前一轮的基础上发现了新的裂缝（Layer 3 规则膨胀、Layer 4 循环论证），然后建造了新的检测工具来修补裂缝，最终收敛到一个可操作的行动框架。

---

## 十、变更日志

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-06-06 | 初始创建，完成问题定义、文献追踪、风险映射、行动计划 | AI + StormstoutLau |
| 2026-06-06 | 新增：DSL本质分析（小样本人工校准 + IPW校正传播） | AI + StormstoutLau |
| 2026-06-06 | 新增：原创性分析（学术定位 + 人工标注争议应对） | AI + StormstoutLau |
| 2026-06-06 | 新增：四层验证模型（经过四轮方法论审计后收敛） | AI + StormstoutLau |
| 2026-06-06 | 新增：JudgeCalibration vs LLM Judge 区分 | AI + StormstoutLau |
| 2026-06-06 | 新增：金融独有优势（时间维度 ground truth） | AI + StormstoutLau |
| 2026-06-06 | 新增：Layer 3 收敛决策（当前用规则引擎，稳定后评估 Lean4） | AI + StormstoutLau |
| 2026-06-06 | 新增：P5 Layer 3 一致性验证任务 | AI + StormstoutLau |
| 2026-06-20 | 新增：第九章"讨论过程记录"——六轮迭代讨论的完整推理链条 | AI + StormstoutLau |

---

## 十一、相关资源

| 资源 | 路径/链接 |
|------|---------|
| DSL适用性分析 | [FormalProbability DSL for Blogger Distillation](file:///D:/Textbook/docs/superpowers/status/2026-06-20-formalprobability-dsl-for-blogger-distillation.md) |
| FormalProbability DSL | [FormalProbability/DSL/](file:///d:/Textbook/external_repos/FormalProbability/FormalProbability/DSL/) |
| PPI (Science 2023) | [Semantic Scholar](https://www.semanticscholar.org/paper/96f75d06ce8bc26128f0af0071b374d065bf7d64) |
| CALM (2025) | [arXiv:2510.05545](https://arxiv.org/abs/2510.05545) |
| DSL+LLM (2025) | [arXiv:2509.07274](https://arxiv.org/abs/2509.07274) |