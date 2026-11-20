# RESEARCH：P-046 组合优化扩展（portfolio optimization / F2）

> **批次**: P-046 · **Step 1 调研** · 日期 2026-11-20
> **执行序**: P-048 关闭后（关键路径 `045/046/047 → 059 → 048 ✅ → **046** → 050`）
> **判档**: **T1**（`core/portfolio.py` 语义面 + `core/config.py` 字段语义 + 协方差单一入口；**golden 18 零重录**——P-059 builder 显式 `max_weight=1.0`，见 §6.2）
> **上游**: [UPGRADE_MASTER_PLAN.md](UPGRADE_MASTER_PLAN.md) L262 题干（F2）+ 前置「已裁决（Q7）」；P-047 遗留三项（F-S4-P047-1 / U-P047-2 / F-S8-P047-2）；用户指令「对 P-046 立项先进行详细调研」
> **代码证据时点**: HEAD `b5f69a7`（P-048 关闭回填；`git status --short` 空）
> **基座**: 正文 DeepSeek-V4.1-Flash
> **取证声明**: 本仓源码 E3（逐字读取，标 HEAD + 行号）；**E2 探针 7 组**（§4，脚本可重放，含种子）；**外部证据 14 条已分级登记于 §14**（A = 全文逐字可复核 / B = 仅书目或书目+二手公式锚 / C = 摘要级、不得用于结论），三项建议的证据强度与「不得引用清单」同见 §14。**2026-11-20 补强**：E1/E1b/E9-E14 为一手全文（UZH 官方 PDF、MSCI 方法论 PDF、NBER WP、JFE 接受稿），E8 由负结果转为 pypfopt 1.6.0 运行时实测
> **Step 0 裁决（2026-11-20）**：U-P046-1 = `U1-A→B2 / U1-B→B1 / U1-C→既有 / U1-D→B1`；U-P046-2 = `C1`（sklearn `LedoitWolf`）+ `C3`；U-P046-3 = `i`（引擎统一注入 Σ）。决策记录与连带效果见 §10.1

---

## 0. 本文定位

| 本文件已定 | 留给后续 |
|---|---|
| 题干还原与不做清单（§1） | Step 0 用户裁决（§10 U-P046-1/2/5） |
| 代码事实基线（§2，@`b5f69a7`） | Step 2 异构复审（本文不自评 PASS） |
| 缺口 G-P046-1..9（§3） | Step 3 DESIGN 的接口签名与数值容差 |
| 取证 F-P046-1..8（§4） | Step 4 复审 |
| 方案矩阵与推荐（§5） | Step 5+ 实施 |
| 任务拆分 B1-B3 + 回退点（§6） | |
| 不变式 I-P046-1..8（§7） | |
| DoD A1-A10（§8） | |
| 基线 / 目标读数（§9） | |

---

## 1. 触发与题干

### 1.1 触发

用户要求「分析下一步任务」后裁决对 P-046 立项，并指令「先进行详细调研」。P-046 是 P-047 明确指向的承接批次：[DESIGN_p047](DESIGN_p047_position_sizing.md) L34（`U-P047-2` 非等预算归 P-046）、L121（矩阵式凯利归 P-046）、L283/L308（「clip 后非 ERC」登记 P-046，G9 禁止 P-047 内改）、L481（遗留清单）。

### 1.2 题干（总纲 L262 逐字）

| 项 | 原文 |
|---|---|
| 题干 | `BL/HRP/约束（F2，核心自研 + PyPortfolioOpt 仅对拍）` |
| 前置 | `已裁决（Q7）` |
| 验收 | `权重约束不变量；参考解对拍；synthetic 协方差可跑通` |

### 1.3 题干的三层含义

| 层 | 内容 | 与现仓关系 |
|---|---|---|
| L1 语义修复 | 「权重约束不变量」要求约束**真的成立** | 现仓不成立（F-P046-1） |
| L2 新增优化器 | BL / HRP（Q7 裁决：核心自研，PyPortfolioOpt 仅对拍） | 现仓无（`COV`/`build_optimizer` 仅 4 法） |
| L3 遗留求解 | 矩阵式凯利 + 非等风险预算（P-047 显式转来） | 现仓无 |

### 1.4 明确不做

| # | 不做 | 依据 |
|---|---|---|
| N1 | 不把 PyPortfolioOpt 设为运行时依赖 | Q7「仅对拍」；`pypfopt` 实测**未安装**（§5.5） |
| N2 | 不改 P-059 的 18 条 golden 期望值 | builder 已 `max_weight=1.0`（F-P046-9，安全） |
| N3 | 不在本批引入杠杆 / 多资产 / 期货 | 属 P-050 |
| N4 | 不改 overlay 的三层缩放公式 | P-048 已锁（DESIGN_p048 §6） |
| N5 | 不做盘中 / 高频再优化 | 日频口径 |
| N6 | 不做因子挖掘 / 择时 | 属 P-049 / 策略层 |

---

## 2. 代码事实基线（@`b5f69a7`）

### 2.1 优化器族（`core/portfolio.py` 447 行）

| 符号 | 行 | 事实 |
|---|---|---|
| `COV_ESTIMATORS` | L26-30 | 3 档：`sample` / `ledoit_wolf` / `ewma` |
| `_ledoit_wolf_shrinkage` | L33-64 | 自研；`factor_cov = np.outer(mu, mu)`（L51）；`pi`/`rho`/`gamma`/`kappa` L54-59 |
| `_ewma_covariance` | L67-95 | 手写 `for` 循环（L91-93），`lambda_param=0.94` 硬编码（L67） |
| `BaseOptimizer._apply_constraints` | L128-146 | clip upper（L138）→ clip lower（L141）→ **归一化（L144）** |
| `EqualWeightOptimizer` | L149-190 | L187 调用 `_apply_constraints` |
| `MinVarianceOptimizer` | L192-255 | cvxpy `quad_form`；`problem.solve()` **未指定 solver**（L245） |
| `MeanVarianceOptimizer` | L257-324 | `expected_returns = returns.mean()`；失败回退等权（静默 `logger.warning`） |
| `RiskParityOptimizer` | L326-391 | 乘性迭代 L366-382；`portfolio_vol` 无零防护（L368）；归一化 L385 → `_apply_constraints` L389 |
| `round_lot_optimize` | L394-424 | **全仓零调用点**（§4 F-P046-5） |
| `build_optimizer` | L426-447 | 4 个 method 分支；未知 → `ValueError` |

### 2.2 配置面（`core/config.py` L269-297）

| 字段 | 默认 | 运行时消费 |
|---|---|---|
| `method` | `equal_weight` | ✅ `build_optimizer` L426 |
| `max_weight` | **`0.10`** | ✅ `_apply_constraints` L138 |
| `min_weight` | `0.0` | ✅ L141 |
| `industry_max_weight` | `None` | ❌ **零消费**（仅 `config_v2` L143 校验） |
| `round_lot` | `True` | ❌ **零消费**（整手在 `target_positions`） |
| `target_count` | `50` | ✅ |
| `risk_aversion` | `1.0` | ✅ MVO |
| `risk_parity_tol` / `_max_iter` | `1e-6` / `500` | ✅ |
| `cov_method` | **`ledoit_wolf`** | ✅ 但**退化为 sample**（F-P046-2） |
| `cov_lookback` | `60` | ✅ engine L1071 |
| `cov_shrinkage` | `0.1` | ❌ **零消费**（LW 内部自算） |

### 2.3 引擎接线（`core/engine_v2.py`）

| 行 | 事实 |
|---|---|
| L1071-1081 | `date_index >= cov_lookback` → 构造 `returns_data`（宽 `cov_lookback × n_codes`） |
| **L1083** | `optimizer.optimize(tradable_stocks, returns_data)` — **只传 returns，不传 cov_matrix** |
| L1087-1099 | `except Exception` → `diagnostics.record` + `emit(ERROR)` + **`return`（当日完全不调仓）** |
| L1101-1119 | P-048 overlay：`np.atleast_2d(np.cov(returns_data.to_numpy().T))`（L1106）**独立再算一次协方差** |

---

## 3. 缺口清单

| ID | 缺口 | 类型 | 级别 |
|---|---|---|---|
| **G-P046-1** | `_apply_constraints` 归一化在 clip 之后 → `max_weight`/`min_weight` 可被推翻 | 语义缺陷 | **P1** |
| **G-P046-2** | 约束不可行（`target_count × max_weight < 1`）时无裁决语义，现状静默超限 | 语义缺陷 | **P1** |
| **G-P046-3** | `cov_method="ledoit_wolf"`（默认）**结构性恒等于 sample**：`ρ=Σs_ij²` 而 `π` 为**标量**（pandas<3.0 按列 → `Σs_ii²`，此时 `ρ−π=Σ_{i≠j}s_ij² ≥ 0` 有恒等证明；pandas 3.0.3 实测 → 全 panel 方差 `float64`），两条路径下实测 `κ<0 ⇒ shrinkage=0`；且收缩目标为秩 1 外积。**三重缺陷（π 语义随 pandas 版本漂移 + ρ 定义错配 + 目标矩阵错配）**，见 §4.1 P2 / E1/E1b 逐字 | 实现缺陷 | **P1** |
| **G-P046-4** | ERC 在 `portfolio_vol≈0` 时除零 → 权重全 `NaN` | 鲁棒性 | **P1** |
| **G-P046-5** | 非 PSD 协方差 → cvxpy `DCPError` → 整日跳过调仓（无 PSD 投影/回退） | 鲁棒性 | P2 |
| **G-P046-6** | 协方差**双口径**：optimizer 走 `cov_method`，overlay 走裸 `np.cov` | 架构旁路 | P2 |
| **G-P046-7** | 死配置三件套 + 死函数（`industry_max_weight` / `cov_shrinkage` / `round_lot` / `round_lot_optimize`，后者全取整为 0 时返回 `NaN`） | 技术债 | P3 |
| **G-P046-8** | 缺 BL / HRP / max_sharpe / 行业·换手·跟踪误差约束 | 功能缺口（题干 L2） | — |
| **G-P046-9** | 矩阵式凯利 `Σ⁻¹μ` / 非等风险预算求解器 | 功能缺口（题干 L3） | — |

---

## 4. 取证

### 4.1 E2 探针（可重放）

> 脚本 `%TEMP%\p046_probe.py`；`.venv\Scripts\python.exe`；`numpy 2.4.6` / `scipy 1.17.1` / `cvxpy 1.9.1` / `sklearn 1.9.0`；种子 `default_rng(20261120)`。

| F | 探针 | 输入 | 实测输出 | 判定 |
|---|---|---|---|---|
| **F-P046-1** | P1 约束失效 | `5×0.20`（sum=1），`max_weight=0.10` | 输出 `[0.2,0.2,0.2,0.2,0.2]`，`max=0.2` → **超限 100%** | ✅ 复现 |
| | P1b min 路径 | `[0.8,0.05×4]`，`max=0.30 / min=0.05` | 输出 `[0.6,0.1,0.1,0.1,0.1]` → `max=0.6` **超 0.30** | ✅ 复现 |
| **F-P046-2** | P2 与 sklearn 对拍（60×5） | 同一收益窗 | 本仓 diag `[2.65,2.77,3.94,3.92,1.98]e-4`；sklearn diag `[2.90,2.93,3.22,3.21,2.74]e-4`；sklearn 收缩系数 **0.7531**；最大绝对差 **7.63e-05**（相对 23.7%） | ✅ 复现 |
| | P4 与 sample 对比 | 60×5 随机 | `ledoit_wolf` 与 `np.cov` 的 diag 均值、等权组合 σ **逐位相同**（`0.00060198` / `0.01071877`，分歧 **0.00%**） | ✅ 证明收缩为 0 |
| **F-P046-3** | P3 ERC 约束破坏（5 资产，目标 1/5） | `max_weight` 四档 | `0.10`→`w` 全 `0.2`，`RC%=[0.0584,0.1158,0.1877,0.2704,0.3677]`（**最大偏离 0.1677**）；`0.20`→偏离 `0.1049`；`0.40`/`1.0`→`w=[0.3396,0.2238,0.1712,0.1425,0.1229]`、`RC%` **全 0.2** | ✅ 复现 P-047 F-S4 |
| **F-P046-4** | P5 退化输入 | 60×5 常数收益 → 零协方差 | `ledoit_wolf`/`ewma` 迹均为 `0.0`；`RiskParityOptimizer` 输出 `[nan×5]` | ✅ 除零确认 |
| **F-P046-5** | P6 死函数 | `total=100`，价 `1000/2000`，`lot=100` | `round_lot_optimize` → `[nan, nan]`（`0/0`） | ✅ NaN 确认 |
| **F-P046-6** | P7 非 PSD | 协方差改一元素至 `0.5`（最小特征值 **−0.4357**） | `MinVarianceOptimizer` → `cvxpy.error.DCPError`；引擎 L1087-1099 捕获后 **`return`**（当日零调仓） | ✅ 复现 |

**P2 机理复核（E3 + 一手全文，见 §14 E1/E1b/E2）**：[portfolio.py L54-L59](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L54-L59)

- **证据链订正（关键）**：本仓变量命名 `π/ρ/γ/κ` 与 `shrinkage = κ/T` 的骨架**来自 Ledoit & Wolf (2003) *JEF* 的单指数目标收缩**（§14 **E1** 全文，Theorem 1 / Lemma 1/3 / Theorem 2 / Eq.(10)），**不是** LW (2004) *JMVA*。后者（§14 **E1b** 全文）是 identity 目标，全文**不使用 π/ρ/γ**，只用 μ、α²、β²、δ²（p.368）与 Eq.(14) `Σ̂*=(b̄²/d̂²)μ̂I+(â²/d̂²)S`。→ 先前「LW 2004 的 π/ρ/γ」提法本身有误，须以 E1 为准。
- **次级证据升级为 A（逐字）**：E1 Theorem 1（p.608-609）「π = Σ_iΣ_j AsyVar[√T s_ij]」「ρ = Σ_iΣ_j AsyCov[√T f_ij, √T s_ij]」「γ = Σ_iΣ_j(φ_ij−σ_ij)²」。本仓 `rho = Σ_ij s_ij²` 是**样本协方差平方和**，既非 AsyCov、也不含目标 `f_ij` → **定义错配（A 级）**，不再标注为推断。
- **闭式/实测结论（新增，含 pandas 版本分叉）**：`rho = Σ_ij s_ij²`；而 `pi = np.sum(np.var(returns, ddof=1) ** 2)` 的语义**随 pandas 版本漂移**——
  - **pandas < 3.0**（`axis=None` 旧行为，按列）：`π = Σ_i s_ii²` ⇒ `π − ρ = −Σ_{i≠j} s_ij² ≤ 0` ⇒ **κ ≤ 0 有恒等证明**（仅全对角时 κ=0）。
  - **pandas 3.0.3（本仓 `.venv` 实测）**：`np.var(df, ddof=1)` 返回 **`float64` 标量**（全 panel 方差）⇒ `π = (pooled var)²`，与 LW 的 `π̂` 无任何对应关系（连"按资产"都不是）。
  - **两条路径的实测**（60×6，种子 7，本仓 venv pandas 3.0.3 / numpy 2.4.6）：`pi=1.448791e-08`、`sum(diag²)=8.910358e-08`、`rho=9.931296e-08`、`kappa=−0.879584`、`alpha=0.0`、调用 `_ledoit_wolf_shrinkage` 后 **`max|Σ̂_LW − S| = 0.0`**。与 F-P046-2 P4（分歧 0.00%）互为印证。
  - → **可断言的是「本仓 install 环境 α≡0」**；「恒等于 sample」在 pandas<3.0 有证明、在 3.0.3 为实测。**不得表述为与版本无关的恒等式**。
- **目标矩阵错配（E3 文档 + E1b/E2 源码）**：收缩目标 `factor_cov = np.outer(mu, mu)` 是**秩 1 外积**（量纲 `mean²`，实测 Frobenius `2.04e-05`）；E3/sklearn 为 `(TrΣ̂/p)·I`（标量乘单位阵）；E1 中 `F` 是单指数模型协方差（`f_ij = s_i0 s_j0 / s_00`）。三者互不相同 → 即使换成正确 π/ρ，目标仍错。
- 附带：E1 p.613 明示「Different shrinkage targets … The formula for **ρ** would need to be readjusted on a case-by-case basis, but the formulas for **π and γ** would not change」→ 目标可换，但 ρ 必须随之换；本仓换目标却未换 ρ。
- 结论：默认 `cov_method="ledoit_wolf"` **从未执行收缩**（install 环境 `α≡0`，`max|Σ̂−S|=0.0`）；其成因是**定义错配 + 目标错配 + π 语义的版本漂移**三者叠加，而非参数微调偏差（G-P046-3 成立，级别 P1）。

### 4.2 E3 静态核验

| 项 | 结果 |
|---|---|
| `round_lot_optimize` 调用点 | **0**（全仓 `*.py` grep 仅定义处） |
| `industry_max_weight` 消费 | **0**（`config.py` L282 定义 + `config_v2.py` L143-144 校验，无运行时读取） |
| `cov_shrinkage` 消费 | **0**（`config.py` L297 + `config_v2.py` L137，无读取） |
| `cfg.round_lot` 消费 | **0**（整手在 `target_positions.py` L130 独立实现） |
| `config_v2` 行业上限校验方向 | L143 要求 `industry_max_weight ≤ max_weight` —— **语义倒置**（行业上限通常应 ≥ 个股上限），且该字段无运行时实现，校验无对象 |
| `problem.solve()` solver | 未指定（L245 / L315），依赖 cvxpy 默认链，数值容差不可控 |
| 协方差旁路 | `engine_v2` L1106 裸 `np.cov` vs 优化器 `cov_method`；**当前巧合一致**（F-P046-2 使 LW≡sample），修 LW 后即暴露分歧 |

### 4.3 F-P046-9（关键安全事实，E3）

P-059 builder [_scenarios_builder.py L107-L113](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_builder.py#L107-L113) 显式 `max_weight=1.0`；`test_cross_engine_equivalence.py` L60 同为 `1.0`；`test_invariants.py` L211 同为 `1.0`。**18 条 golden 与跨引擎对拍均不受约束修复影响。**

触发面收敛为：`target_count < 1/max_weight`（默认 `<10`）的配置。已知命中：`test_p023_quality_guardrails.py` L128、`test_p025_day_error_diagnostics.py` L178、`test_p026_silent_exception_governance.py` L229（均 `target_count=2` + 默认 `max_weight=0.1`）。三处须在 Step 3 逐一核对断言是否依赖权重数值。

---

## 5. 方案矩阵

### 5.1 约束处理（对 G-P046-1/2）

| 方案 | 做法 | 优点 | 缺点 | 推荐 |
|---|---|---|---|---|
| **A1** 迭代 water-filling | clip 超限部分释放后按剩余容量再分配，循环至可行或不可行 | 保持 `sum=1`、纯 numpy、零新依赖、可闭式断言 | 不可行时需额外语义（见 5.2） | ✅ **首选** |
| **A2** cvxpy 统一约束 | 所有权重问题加 `w ≤ max_weight` 硬约束 | 数学最干净、天然可行域裁剪 | 每次 rebalance 多一次求解；ERC 非凸不可直接表达 | 备选（仅用于 min_var/mvo） |
| **A3** 保持现状 | 不改 | 零风险 | 约束不变量持续为假，题干 L1 无法验收 | ❌ |

### 5.2 约束不可行裁决（`n × max_weight + (n−1) × min_weight < 1`）

| 方案 | 结果 | 兼容性 |
|---|---|---|
| **B1** fail-loud `ValueError` | 配置错误立即暴露 | 会打红 3 处既有单测（§4.3） |
| **B2** 残差留现金（`sum(w) < 1`） | 与 P-048 overlay `cash_residual` 语义一致 | 3 处单测权重变 `0.1`（sum=0.2），断言若不看权重则安全 |
| **B3** 自动放宽 `effective_max = max(max_weight, 1/n)` | 现状数值不变 | **静默偏离配置**，与「约束不变量」目标冲突 |
| **B4** 按 `method` 分流（等权豁免约束） | 等权不受限 | 语义分裂，ERC 问题仍在 |

**推荐 B2 + 显式诊断**（`diagnostics.clipped` 记录不可行证据），理由：与 P-048 的「残差留现金」先例一致；不制造静默偏离；3 处单测可通过显式 `max_weight=0.5` 修正而非改语义。

> **已被 §15.2.2 取代（2026-11-20，Step 3 回填 R-P046-6）**：本节原先隐含的可行性条件 `n·m + (n−1)·m0 < 1` **既不必要也不充分**（反例 `n=3, m=0.5, m0=0.4`：该式给 2.3≥1 判「可行」，实际 `n·m0=1.2>1` 属 U1-B）。正确判据为**区间和可行性** `n·m0 ≤ 1 ≤ n·m`，且 B1/B2 须**按 U1 分型分别指定**（§15.2.2 / §10.1）。本节仅保留为历史沿革。

### 5.3 协方差（对 G-P046-3/6）

| 方案 | 做法 | 权衡 |
|---|---|---|
| **C1** 改用 `sklearn.covariance.LedoitWolf` | 删自研 56 行，用成熟实现 | `scikit-learn>=1.3.0` **已在 pyproject L39**，零新增依赖；输出与自研不同（相对 23.7%）→ 影响所有非等权方法的权重 |
| **C2** 修自研公式 | 按 LW 2003（E1）重写：`ρ̂ = ΣΣ AsyCov[√T f_ij, √T s_ij]`（**目标相关，须随目标重算**，非 `Σ Cov(s_ij,s_kl)` 的泛写）、`π̂ = (1/T)Σ_t[(x_it−μ_i)(x_jt−μ_j)−s_ij]²` 求和、`F` 改为与目标一致的结构 | 保留零 sklearn 依赖；但等于重写标准算法（含目标特化），回归风险高于 C1 |
| **C3** 统一入口 `estimate_cov(returns, method, codes)` | optimizer 与 overlay 共用 | **必做**（与 C1/C2 正交）；消除 G-P046-6 |

**推荐 C1 + C3**：sklearn 已是声明依赖且已安装（1.9.0）；自研实现无任何测试覆盖（grep 无 `_ledoit_wolf_shrinkage` 的直测），替换成本低于修复成本。C3 作为硬要求，避免 P-048 overlay 继续走旁路。

### 5.4 新增优化器（对 G-P046-8）

| 方案 | 内容 | 依赖 | 备注 |
|---|---|---|---|
| **D1** BL（Black-Litterman） | 市场均衡先验 + 观点融合 → `μ_BL`，代入既有 MVO | 纯 numpy | Q7「核心自研」 |
| **D2** HRP（层次风险平价） | 相关距离 → 层次聚类 → 递归二分 | `scipy.cluster.hierarchy`（已装） | Q7「核心自研」 |
| **D3** 扩展约束 | 行业上限（复用 `industry_max_weight`）/ 换手 / 跟踪误差 | cvxpy | 需行业映射数据源（**待确认可用性**，U-P046-6） |
| **D4** max_sharpe | 需 `μ` 与 `Σ`；无风险利率输入 | numpy | 收益估计噪声大，建议后置 |

对拍策略：`pypfopt` 置于 `[research]` extra（**不装运行时**），仅 CI 可选 job 对拍；主门禁用闭式 synthetic 断言。

### 5.5 遗留求解（对 G-P046-9）

| 方案 | 内容 |
|---|---|
| **L3-1** 矩阵式凯利 | `f = Σ⁻¹μ`；需 `Σ` 可逆 + 收缩；与 P-047 对角近并存（`kelly_budget` 方法开关） |
| **L3-2** 非等风险预算 | 在 `RiskParityOptimizer` 增 `budgets: Sequence[float]`；目标改为 `b_i × σ_p`；用坐标下降（ccd）替代乘性迭代以改善收敛 |

### 5.6 依赖盘点（E1）

| 包 | 版本 | pyproject | 用途 |
|---|---|---|---|
| numpy | 2.4.6 | 已声明 | 全部 |
| scipy | 1.17.1 | L31 | HRP 聚类 |
| cvxpy | 1.9.1 | L34 | min_var / mvo / 扩展约束 |
| scikit-learn | 1.9.0 | L39 | **LedoitWolf** |
| pypfopt | **未装** | 未声明 | 仅对拍（`[research]` extra） |

---

## 6. 任务拆分与回退

### 6.1 三个子批（建议顺序）

| 子批 | 内容 | 影响面 | 风险 |
|---|---|---|---|
| **P-046a 语义修复** | A1 约束投影 + B2 不可行语义 + C1 替换 LW + C3 统一协方差入口 + G-P046-4 零方差防护 + G-P046-5 PSD 兜底 + G-P046-7 死配置清理 | `portfolio.py` / `config.py` / `engine_v2` L1083-1106 | 中（权重数值变化，golden 不受影响） |
| **P-046b 新增优化器** | D1 BL + D2 HRP +（可选）D3 约束扩展 | `portfolio.py` 新增类 + `build_optimizer` 分支 | 低（opt-in） |
| **P-046c 遗留求解** | L3-1 矩阵式凯利 + L3-2 风险预算（§1.3 的 L3 两层；**勿与 §14 证据编号 E1/E2 混淆**） | `portfolio.py` + `sizing` 侧开关 | 低（opt-in） |

### 6.2 回退点

| 子批 | 回退方式 |
|---|---|
| a | 单提交 atomic；`_apply_constraints` 保留旧行为为私有方法 `_apply_constraints_legacy` 仅测试期对照，不对外导出 |
| b | `build_optimizer` 新增 method 分支，未知 method 行为不变 |
| c | 新函数独立模块级符号，不修改既有签名 |

### 6.3 与 P-048 的耦合（必须先定）

P-048 overlay 在 L1101-1119 独立算 `np.cov`。C3 统一后，overlay 应改为接收**引擎层统一计算的协方差**，而非自算。这属于 **P-046a 的跨批改动**，须在 DESIGN 中明确：
- 选项 i：engine 在 L1080 处算一次 `cov`，同时传给 `optimizer.optimize(..., cov_matrix=cov)` 与 `apply_overlay(cov=cov)`；
- 选项 ii：overlay 保持自算（接受双口径）。

推荐 i（消除 G-P046-6），但需评估 P-048 已锁的 S15 场景数值——S15 用 `target_vol=None`，**不失效**（σ 不参与缩放）。

---

## 7. 不变式

| ID | 不变式 | 验证方式 |
|---|---|---|
| I-P046-1 | 可行域内：`min_weight ≤ w_i ≤ max_weight` 逐项成立 | 闭式断言 × 四 method |
| I-P046-2 | `sum(w) ≤ 1` 恒成立；不可行时 `sum(w) < 1` 且残差 = 现金 | 闭式 |
| I-P046-3 | 约束处理不引入负权重（无杠杆） | 闭式 |
| I-P046-4 | ERC：`Σ RC_i = σ_p`、`RC% = budgets` 在**未受约束**时成立 | 闭式（synthetic 对角/等相关） |
| I-P046-5 | 退化输入（零协方差 / 单资产 / 常数序列）不产生 `NaN`，走显式分支 | 闭式 × 3 |
| I-P046-6 | 非 PSD 输入：投影到最近 PSD 或 fail-loud，**不得静默跳过整日** | 闭式 |
| I-P046-7 | 协方差单一入口：overlay 与 optimizer 对同一窗口得到同一 `Σ` | 逐位相等 |
| I-P046-8 | 默认配置（`equal_weight` / `target_count=50` / `max_weight=0.10`）下输出与 `b5f69a7` 逐位相同 | golden 18 + 全量 932 |

---

## 8. DoD（A1-A10）

| ID | 验收项 |
|---|---|
| A1 | `_apply_constraints` 在可行域内满足 I-P046-1/2/3（≥6 组参数化） |
| A2 | 不可行配置按 B2 语义输出并写入诊断（≥3 例） |
| A3 | `cov_method="ledoit_wolf"` 与 sklearn `LedoitWolf` 逐位一致（1e-12） |
| A4 | `estimate_cov` 单一入口被 optimizer 与 overlay 共同调用（grep 断言） |
| A5 | ERC 零方差 / 零协方差 → 不产生 NaN（≥3 退化例） |
| A6 | 非 PSD → PSD 投影或显式 `ValueError`；engine 不出现「整日静默 return」 |
| A7 | 死配置处置：`industry_max_weight` / `cov_shrinkage` / `round_lot` / `round_lot_optimize` 四者**各有明确去向**（接线或删除，零残留） |
| A8 | BL / HRP 输出满足 I-P046-1/2/3，且与 `pypfopt` 对拍（若 extra 安装）或 synthetic 闭式解一致 |
| A9 | 矩阵式凯利与非等预算求解有闭式/参考解对拍；P-047 对角近似行为不变 |
| A10 | golden 18 零重录；全量 `932 + 新增` 通过；mypy / black / AST 22 / uv 不劣化 |

---

## 9. 基线 / 目标读数（@`b5f69a7`）

| 项 | 基线 | 目标 |
|---|---|---|
| pytest 全量 | **932** | `932 + Δ`（Δ = 新增测试数，预计 +35~45） |
| `-k golden` | **18 passed / 914 deselected** | **18 零重录** |
| `-k p059` collect | **63/932** | 63（若新增 P-059 场景另计） |
| mypy | **111 files 0** | 0 |
| black | **149 / 218 unchanged** | unchanged |
| AST `except Exception`（生产面） | **22**（core 内 29） | 不变（不新增裸 except） |
| `tests/*.py` | **106** | 106 + 新文件数 |
| `uv lock --check` | exit 0 | exit 0（P-046b 若加 `[research]` extra 需重锁） |
| 新增依赖 | 无 | `pypfopt` 仅 extra（可选） |

---

## 10. 未决项与净收敛

| ID | 未决项 | 建议 | 状态 |
|---|---|---|---|
| **U-P046-1** | 约束不可行语义（**按 U1-A/B/C/D 分型**） | **U1-A→B2 / U1-B→B1 / U1-C→既有 / U1-D→B1**（§15.8） | **✅ 已裁决 2026-11-20**（§10.1） |
| **U-P046-2** | LW 用 sklearn（C1）还是修自研（C2） | **C1**（依赖已在）+ **C3**（统一入口，必做） | **✅ 已裁决 2026-11-20**（§10.1） |
| **U-P046-3** | overlay 协方差改为引擎统一注入（选项 i/ii） | **i** | **✅ 已裁决 2026-11-20**（§10.1） |
| U-P046-4 | 死配置四件套去向（接线 / 删除 / 冻结标注） | `industry_max_weight` 接入 D3；`cov_shrinkage` 删除；`round_lot` 删除或标注冻结；`round_lot_optimize` 删除 | 已收敛（建议） |
| U-P046-5 | 三处 `target_count=2` 单测是否因约束修复变红 | Step 3 逐项核对；预计改为显式 `max_weight=0.5` | 已收敛（处置路径明确） |
| U-P046-6 | 行业映射数据源是否可用（D3 前置） | 无需降级；D3 可实现，样本数据无区分度 | **✅ 已核查 2026-11-20**（§13.1 C-3） |
| U-P046-7 | 矩阵式凯利 / 非等预算是否本批（P-046c） | 建议拆为 P-046c 独立提交，不阻塞 a/b | 已收敛（建议） |
| U-P046-8 | `pypfopt` 对拍是否进 CI | 建议 `[research]` extra + 可选 job，不进主门禁 | 已收敛（建议） |

### 10.1 Step 0 裁决记录（2026-11-20）

用户指令「U P046 1 2 3 按照建议执行」→ 三项均按 §15.8 / §10 建议原样采纳，无修改。

```yaml
DECISION-U-P046-1:
  U1-A_upper: B2          # 残差留现金 + 诊断
  U1-B_lower: B1          # fail-loud
  U1-C_empty: existing    # 空权重 + warning（portfolio.py L172-L174）
  U1-D_config: B1         # 配置期 fail-loud
  tolerance: 1e-12
  diagnostics_fields: [infeasible_kind, n, max_weight, min_weight, cash_residual]
  engine_error_policy: config_raise / numeric_skip
  decided_by: 用户
  decided_at: 2026-11-20
DECISION-U-P046-2:
  choice: C1              # sklearn.covariance.LedoitWolf（1.9.0 已装）
  coupling: C3            # estimate_cov 统一入口（必做）
  target: identity        # 与 E1b/E2 一致，不再自研 π/ρ/γ
  decided_at: 2026-11-20
DECISION-U-P046-3:
  choice: i               # engine 算一次 Σ，同时注入 optimizer 与 overlay
  scope: P-046a
  decided_at: 2026-11-20
```

**连带效果（裁决直接引发）**

| 项 | 效果 |
|---|---|
| U-P046-13（`np.var` 版本语义） | **消解**：自研 `_ledoit_wolf_shrinkage` 删除 → 不再依赖 `np.var(df, ddof=1)` 的 pandas 版本行为 |
| U-P046-9（是否中心化） | **消解为已知差异**：sklearn `assume_centered=False` 会中心化 → 收缩系数由 `α≡0` 变为非零，DESIGN 须记录「与 `b5f69a7` 旧口径不同」 |
| AC-C-08（dataclass / pydantic 等价） | **与冻结冲突**：`config_v2` 为 FROZEN（TD-2）→ 改判为「dataclass 单侧校验 + 记录冻结例外」（§13.1 C-4，Step 2 复审确认） |
| 5 处 `target_count=2` 构造点 | B2 生效后等权输出 `Σw=0.2`（残差 0.8）→ Step 3 逐条核对断言（U-P046-5，§13.1 C-1） |
| P-046b 的 BL / HRP | 不受三项裁决影响；HRP 仍卡在 **U-P046-12**（无一手原文）→ **不阻塞 P-046a**，须在 P-046b 前定夺 |

**外部证据强度（二轮补强后，见 §14）**：U-P046-1 = **中-强**（数学可行域为空 + cvxpy `infeasible` 语义 + pypfopt 1.6.0 四类边界实测 + MSCI 两篇方法论的有序 relax 规范；**仍无外部标准规定"不可行应留现金"**，属产品裁决）；U-P046-2 = **强（A 级全文）**（LW 2003 *JEF* 全文 π/ρ/γ 逐字 + LW 2004 *JMVA* 全文 + sklearn 1.9.0 源码；由「目标矩阵 + π/ρ 双重结构性错配」支撑；`κ≤0` 在 pandas<3.0 有恒等证明、在 3.0.3 为实测，install 环境 `α≡0`）；U-P046-3 = **弱-中**（E6/E7 全文亦不规定共享 Σ；支撑来自 pypfopt 的「cov 显式入参」接口先例 + 本仓 SSOT 原则）。

**零散未决项**：U-P046-9/10/11/12/13（§14.6）在裁决后的状态——**9 / 13 随 C1 消解**（自研函数删除），**10 按建议不加开关**，**11 已用锁版源码 + 运行时实测复核**，**12 仍待定**（HRP 无一手原文，不阻塞 P-046a，须在 P-046b 前定夺）。

**净收敛**：主表 8 项**全部清零**（U-P046-1/2/3 已裁决；U-P046-6 已核查；U-P046-4/5/7/8 处置路径明确）；零散 5 项中 **4 项消解、1 项（U-P046-12）限定在 P-046b**。→ **P-046a 的 Step 2 可以启动**；P-046b 启动前须先裁决 U-P046-12。

---

## 11. 与既有批次的边界

| 批次 | 边界 |
|---|---|
| P-047 | `apply_sizing` 接线仍归 **P-051**；P-047 的 `risk_contributions` 诊断保持不动（P-046 只改求解器） |
| P-048 | overlay 公式与策略族**不改**；仅协方差来源改注入（若 U-P046-3 选 i） |
| P-050 | 期货 / 空头不在本批；`eps`/保证金语义属 P-050 |
| P-051 | `build_optimizer` 注册表与策略模板的接线归 P-051；本批只保证 optimizer 可被装配 |

---

## 12. 步骤表

| Step | 内容 | 状态 |
|---|---|---|
| 1 | 调研（本文） | ✅ 2026-11-20 |
| 1.5 | 外部证据锚点补充调研（§14） | ✅ 2026-11-20（二轮已补一手全文 E1/E1b/E9-E13） |
| 0/裁决 | U-P046-1/2/3 裁决 + U-P046-6 事实核查 | ✅ 2026-11-20（§10.1 / §13.1） |
| 2 | 异构复审（非本文基座） | ✅ 2026-11-20（GLM-5.3-Flash，**PASS 附 3 前置**，§16） |
| 3 | DESIGN | ✅ 2026-11-20（[DESIGN_p046](DESIGN_p046_portfolio_optimization.md)；§2 答 R-P046-1/2/3） |
| 4 | 设计复审 | ✅ 2026-11-20（GLM-5.3-Flash，**有条件通过**，§17） |
| 5 | 实施 P-046a | ✅ 2026-11-20（[IMPL_p046](IMPL_p046_portfolio_optimization.md) + T1-T7 落码，§20） |
| 6 | IMPL 复审 | ✅ 2026-11-20（GLM-5.3-Flash，**有条件通过**，§18） |
| 7 | CHECKLIST | ✅ 2026-11-20（作者，[CHECKLIST_p046](CHECKLIST_p046_portfolio_optimization.md)：43 项，42×`[待 Step 9]` + 1×`[待 Step 10]`） |
| 8 | 文档一致性复审 | ✅ 2026-11-20（GLM-5.3-Flash，**PASS**，§19：2 MEDIUM + 3 LOW + 1 INFO 全部修复） |
| 9 | 验收回填 | ✅ 2026-11-20（作者基座；CHECKLIST 42 项实测回填 + F-S9-P046-1/2/3，§20） |
| 10 | 终审 + 提交 + CI | `[待 Step 10]` |
| — | P-046b / P-046c | 独立子批，Step 5 后另立 |

---

## 13. Step 2 复审包

### 13.1 仓内事实核查（已完成，2026-11-20）

| # | 核查对象 | 结论 |
|---|---|---|
| **C-1** | `target_count=2` 构造点是否显式约束 | 全部**未设** `max_weight` → 默认 `0.10`，`n=2` ⇒ `n·m=0.2<1` → **命中 U1-A**。**订正**：实为 **5 个构造点**（[test_p023 L128](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p023_quality_guardrails.py#L128)；[test_p025 L178](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p025_day_error_diagnostics.py#L178) / [L259](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p025_day_error_diagnostics.py#L259) / [L300](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p025_day_error_diagnostics.py#L300)；[test_p026 L229](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p026_silent_exception_governance.py#L229)），非原记的「三处」 |
| **C-2** | 不可行是否只在 `_apply_constraints` 发生 | **否**。`equal_weight`/`risk_parity` 走 [`_apply_constraints`](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L128-L146)；`min_variance`/`mean_variance` 走 cvxpy 硬约束 `sum(w)==1`（[L237-L241](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L237-L241) / [L306-L310](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L306-L310)），不可行时 **静默回退等权**（[L247-L249](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L247-L249) / [L316-L318](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L316-L318)）→ 等权再进 `_apply_constraints`，**归一化二次破坏上限**。§15 的 AC-C 只覆盖后者路径，**前者须在 Step 3 补 AC** |
| **C-3** | 行业映射数据源（U-P046-6） | ✅ 接口可用：`industry.pkl` 经 [data.py L375-L383](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L375-L383) 加载、[factor.py L337-L347](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L337-L347) 消费（行业中性化）。⚠️ 样本 [data/test_ashare/industry.pkl](file:///f:/Coding/Factor_Trading_v3.0/data/test_ashare/industry.pkl) 为 `100×50` DataFrame 且**全表取值恒为 `1`**（逐列 `nunique=1`）→ D3 可实现，单测须自造多行业映射 |
| **C-4** | `config_v2` 双写等价（AC-C-08） | **不可达成**：[config_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/config_v2.py#L12-L19) docstring 明示 **FROZEN（TD-2）**、生产零引用 → AC-C-08 须改判为「dataclass 单侧 `__post_init__` 校验 + 记录冻结例外」，**不得**为对齐而修改冻结模块 |
| **C-5** | min_var / mvo 的选股口径 | [L216](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L216) / [L281](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L281) 用 `nlargest(cfg.target_count)`，**无 `min()` 截断、无零值过滤**（与 equal_weight [L177](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L177) 不同）→ U1 判定取 n 时须按 method 分别取证 |

### 13.2 待异基座复审（✅ 已复审 2026-11-20，逐项意见见 §16.3）

1. **C-2 的治理方案**：cvxpy 路径的 `infeasible → 回退等权` 应保留、改为抛错、还是并入 B2？三条路对既有 `test_p025` 的影响不同；
2. `MeanVarianceOptimizer` 失败回退（[L316-L318](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L316-L318)）是否与 G-P046-5（非 PSD）合并治理；
3. C-4 的 AC-C-08 改判是否需用户追认（涉验收口径变更）；
4. `scipy.cluster.hierarchy` 在现有 pin（1.17.1）下 HRP 的数值稳定性（仅影响 P-046b）；
5. 是否为 P-046a 新增 P-059「约束不可行」场景（S16），或仅单测覆盖。

---

## 14. 外部证据锚点（补充调研，2026-11-20）

### 14.1 检索方法与分级纪律

- **检索面（两轮）**
  - 一轮（文档级）：scikit-learn 官方文档（API 页 + User Guide）、cvxpy 官方 API 文档、PyPortfolioOpt 官方文档与 GitHub `master` 源码、CrossRef 书目库。
  - 二轮（**一手全文级**，2026-11-20 补强）：UZH 经济系官方 PDF 镜像（Ledoit 个人页，LW 2003 *JEF* 19 页 / LW 2004 *JMVA* 47 页）、MSCI 官方方法论 PDF（Barra Factor Indexes Mar 2018 / Minimum Volatility Sep 2017）、NBER Working Paper 22208、JFE 接受稿（Barroso & Santa-Clara, Nov 2014 版）、Goldman Sachs IM Research（He & Litterman 1999）、**pypfopt 1.6.0 运行时实测**（`uv run --no-project --with PyPortfolioOpt`）。
- **分级**：**A** 全文/源码逐字可复核（PDF 标注页码，源码标注行号，实测标注版本+输出）／**B** 仅书目元数据或「书目 + 二手公式锚」／**C** 摘要级（**不得用于结论**）。
- **纪律**：每条登记「来源 URL + 级别 + 原文要点」；单列**负结果**（检索未证实/取不到全文的主张）与**不得引用清单**，防止后续批次误引本次未验证的说法。
- **PDF 抽取说明**：pypdf 6.11.0 抽取，希腊字母被降级为拉丁字符（π→`p`、ρ→`q`/`r`、γ→`c`/`g`、κ→`j`/`k`、μ→`m`、α²→`a2`、β²→`b2`、δ²→`d2`），本条已在各证据要点中还原；**还原依据为公式结构与上下文，非猜测**（如 `p ¼ ΣΣ AsyVar[√T s_ij]` 与 `q ¼ ΣΣ AsyCov[√T f_ij, √T s_ij]` 成对出现）。
- **抓取日期** 2026-11-20。版本面：sklearn 文档为 `stable`、pypfopt 文档为 `master`，但 **E2 已用本仓 `.venv` 的 sklearn 1.9.0 源码复核**、**E8 用 pypfopt 1.6.0 实测** → 版本漂移风险下调（U-P046-11 仍保留，Step 3 复跑 API 存在性）。

### 14.2 登记表

| ID | 证据 | 来源 | 级别 | 原文要点 |
|---|---|---|---|---|
| **E1** | Ledoit & Wolf (2003) *JEF* **全文** | doi:10.1016/S0927-5398(03)00007-0；PDF：`https://econ.uzh.ch/dam/jcr:ffffffff-961c-1dd9-ffff-ffff9961f70f/jef.pdf`（UZH 官方，19 页） | **A** | Theorem 1（p.608-609, Eq.4）：「π = Σ_iΣ_j AsyVar[√T s_ij]」= *the sum of asymptotic variances of the entries of the sample covariance matrix scaled by √T*；「ρ = Σ_iΣ_j AsyCov[√T f_ij, √T s_ij]」= *the sum of asymptotic covariances of the entries of the single-index covariance matrix with the entries of the sample covariance matrix*；「γ = Σ_iΣ_j(φ_ij−σ_ij)²」= *measure the misspecification of the single-index model*；「α* = (1/T)(π−ρ)/γ + O(1/T²)」。Lemma 1（p.610）：`π̂_ij = (1/T)Σ_t[(x_it−μ_i)(x_jt−μ_j) − s_ij]²`。Lemma 3：`γ̂_ij=(f_ij−s_ij)²`。Theorem 2：`κ̂=(π̂−ρ̂)/γ̂`。Eq.(10)（p.613）：`Σ̂=(κ̂/T)F+(1−κ̂/T)S`。p.613：「Different shrinkage targets would lend themselves just as well…The formula for **ρ** would need to be readjusted on a case-by-case basis, but the formulas for **π and γ** would not change.」 |
| **E1b** | Ledoit & Wolf (2004) *JMVA* **全文** | doi:10.1016/S0047-259X(03)00096-4；PDF：`https://econ.uzh.ch/dam/jcr:ffffffff-961c-1dd9-ffff-ffffceb83f14/wellCond.pdf`（UZH 官方，47 页） | **A** | **全文无 π/ρ/γ**（本节为关键订正）。p.368 内积 `⟨A1,A2⟩_S=tr(A1A2ᵀ)/p`，四标量 `μ=⟨Σ,I⟩_S`、`α²=‖Σ−μI‖²`、`β²=E‖S−Σ‖²`、`δ²=E‖S−μI‖²`；Lemma 2.1 `α²+β²=δ²`；Theorem 2.1 Eq.(5) `Σ*=(β²/δ²)μI+(α²/δ²)S`、Eq.(6) 损失 `α²β²/δ²`；p.369「μI can be interpreted as a **shrinkage target** and the weight β²/δ² … as a **shrinkage intensity**」、PRIAL = β²/δ² (Eq.9)；§3.3 Lemma 3.2-3.5 + Eq.(14) `Σ̂*=(b̄²/d̂²)μ̂I+(â²/d̂²)S`，`b̄²=(1/n²)Σ_k‖x_kx_kᵀ−S‖²`、`b̂²=min(b̄²,d̂²)`、`â²=d̂²−b̂²`；Theorem 3.2 一致性、Theorem 3.4 渐近最优 |
| **E2** | sklearn `LedoitWolf` API + **本仓锁版源码** | https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html；本地 `.venv\Lib\site-packages\sklearn\covariance\_shrunk_covariance.py` L297-L399 | **A** | 属性 `shrinkage_` =「Coefficient in the convex combination used for the computation」；`assume_centered=False` 默认。**源码复核（1.9.0）**：L365 `mu = np.sum(emp_cov_trace)/n_features`（=tr(S)/p）、L390 `beta = 1/(p·n)(β̂_/n − δ̂_)`、L392 `delta = δ̂_ − 2μ·tr(S) + p·μ²`、L399 `shrinkage = 0 if beta == 0 else beta/delta` → **实现的是 E1b 的 identity 目标，不含 π/ρ/γ** |
| **E3** | sklearn Covariance estimation §2.6.2 | https://scikit-learn.org/stable/modules/covariance.html | **A** | 收缩通式 `Σ_shrunk=(1−α)Σ̂+α·(TrΣ̂/p)·Id`；LW「compute the optimal shrinkage coefficient α that minimizes the Mean Squared Error」 |
| **E4** | cvxpy `Problem` API | https://www.cvxpy.org/api_reference/cvxpy.problems.html | **A** | `if problem.status not in ["infeasible", "unbounded"]`；`solve()`「reports that the problem was in fact infeasible or unbounded」；`SolverError – if the problem is infeasible or unbounded` |
| **E5** | PyPortfolioOpt `EfficientFrontier` docstring | raw.githubusercontent.com/robertmartin8/PyPortfolioOpt/master/pypfopt/efficient_frontier/efficient_frontier.py | **A** | `cov_matrix`「This **must** be positive semidefinite, otherwise optimization will fail」；`weight_bounds=(0, 1)` 默认 |
| **E6** | Barroso & Santa-Clara (2015) **接受稿全文** | doi:10.1016/j.jfineco.2014.11.010；PDF：`snifferquant.com/.../Momentum Has Its Moments(scaling Momentum by vol),2014.pdf`（39 页，首页「Forthcoming in the Journal of Financial Economics / This version: November 2014」） | **A**（接受稿） | p.5：「The Sharpe ratio improves from **0.53** for unmanaged momentum to **0.97** for its risk-managed version」；「excess kurtosis drops from **18.24** to **2.68**, and the left skew improves from **−2.47** to **−0.42**」；「minimum one-month return … **−78.96%** … **−28.40%**」；「maximum drawdown … **−96.69%** versus **−45.20%**」；p.7 原始动量「14.46% per year」 |
| **E7** | Moreira & Muir NBER WP 22208 **全文** | doi:10.1111/jofi.12513（期刊版）；PDF：`https://www.nber.org/system/files/working_papers/w22208/w22208.pdf`（57 页，April 2016） | **A**（WP 版） | p.3：「For the market portfolio our strategy produces an **alpha of 4.9%**, an Appraisal ratio of **0.33**, and an overall **25% increase** in the buy-and-hold Sharpe ratio」；p.9「The scaled market factor has an annualized alpha of **4.86%**」；p.12 appraisal ratio 跨因子区间 **0.33–0.91**；p.12「the increase in Sharpe ratios we document are likely to be **understated**」 |
| **E8** | PyPortfolioOpt 1.6.0 **不可行行为实测**（原负结果转正） | `uv run --no-project --with PyPortfolioOpt==1.6.0 python`（脚本与输出见 §15.5 表 B） | **A**（实测） | **构造期零校验**：`weight_bounds=(0,0.1)`（3 资产，`Σmax=0.3<1`）、`(0.6,1.0)`（`Σmin=1.8>1`）、`(0.5,0.3)`（单资产 `min>max`）三类 **初始化均不抛错**；调用 `max_sharpe()` 时抛 `OptimizationError('Please check your objectives/constraints or use a different solver.', 'Solver status: infeasible')`。**订正**：不存在 `ValueError` 预检查（原「抛 ValueError」主张作废）；对照组 `(0,0.40)`（`max ≥ 1/n`）求解成功 `w=[1/3,1/3,1/3]` |
| **E9** | MSCI *Barra Factor Indexes Methodology*（Mar 2018）App. VI | `https://www.msci.com/eqb/methodology/meth_docs/MSCI_Barra_Factor_Indexes_Methodology_Mar18.pdf`（25 页，**p.17**） | **A** | 「the constraints will be **relaxed sequentially** as follows, until an optimal solution is found: 1. Relax the turnover constraint and factor exposure constraints … achieved automatically using the **Soft Constraint** feature of the Barra Optimizer … 2. Relax the trade limit constraint by allowing **two times** the original Trade Limit … 3. Relax the constraint on index constituent weight … **±2.5%** … instead of ±2.0% 4. Relax the maximum number of index constituents to **1.25 times** …」+「The above constraint relaxation sequence is followed **mechanically**. In the event that no optimal solution is found after all the above constraints have been relaxed, the relevant Barra Factor Index **will not be rebalanced for that month**.」 |
| **E10** | MSCI *Minimum Volatility Indexes Methodology*（Sep 2017）App. III | `https://www.msci.com/eqb/methodology/meth_docs/MSCI_Minimum_Volatility_Methodology_Sep2017.pdf`（18 页，**p.12**；约束原文 p.11） | **A** | 「Relax the turnover constraint in steps of **5%**, up to a maximum of 30%」；「Relax the **minimum weight** constraint in steps of **0.01% up to a minimum of 0.01%**」（p.11 基准 `minimum weight = 0.05%`）→ **min 侧 relax 方向是逐步下调**；终态与 E9 同构：「will not be rebalanced」 |
| **E11** | He & Litterman (1999) *The Intuition Behind Black-Litterman Model Portfolios* | Goldman Sachs Investment Management Research，PDF：`people.duke.edu/~charvey/Teaching/BA453_2004/GS_The_intuition_behind.pdf`（20 页） | **A**（白皮书） | p.2 App. C.1：「Given the expected returns μ and the covariance matrix Σ, the unconstrained maximization problem max_w w′μ − (δ/2)w′Σw has a solution of **w* = (δΣ)⁻¹μ**」→ 反推即 `Π = δΣw_mkt`；p.4 脚注：「we use **δ = 25** as the risk aversion parameter representing the world average risk tolerance」 |
| **E12（负结果）** | Black & Litterman (1992) *Global Portfolio Optimization* 正文 | doi:10.2469/faj.v48.n5.28；镜像 PDF 16 页但**为纯图片扫描件（无文本层）** | **B**（书目） | 卷期页 *Financial Analysts Journal* **48**(5), 28-43（1992-09/10）已核实；**正文未 OCR → 不引用 BL 1992 的任何逐字表述**，BL 公式一律引 E11 |
| **E13（负结果）** | López de Prado (2016) HRP 全文 | doi:10.3905/jpm.2016.42.4.059；`pm-research.com/content/iijpormgmt/42/4/59` | **C**（仅摘要） | 摘要可读：「HRP applies modern mathematics (graph theory and machine-learning techniques) … unlike quadratic optimizers, HRP does not require the invert[ibility of the covariance matrix]」；**全文在 JPM 付费墙后**，镜像站被 Cloudflare 拦截 → **HRP 算法三步（树聚类 / 准对角化 / 递归二分）的细节不得引用原文**，若 L2 落地只能依据开源实现（如 `riskfolio-lib`）并在 DESIGN 中显式标注为「实现参照，非原文」 |

### 14.3 三项建议的加固与订正

#### U-P046-2（C1 改用 sklearn `LedoitWolf`）— 证据 **强（A 级全文）**，结论不变且加重

- E3 + E1b：LW（identity 目标）的收缩形式为 `(TrΣ̂/p)·I`（标量乘单位阵）；本仓 [portfolio.py L51](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L51) 为 `np.outer(mu, mu)`（秩 1 外积）→ **结构性不符，非参数可调问题**。
- E2 + 本地 1.9.0 源码：sklearn `mu=tr(S)/p`、`shrinkage=beta/delta`、`assume_centered=False` 默认 → **sklearn 落地的正是 E1b（identity），与 E1（单指数 π/ρ/γ）不是同一套**。
- **ρ 定义错配已由推断升级为 A 级**：E1 Theorem 1 逐字 `ρ = ΣΣ AsyCov[√T f_ij, √T s_ij]`；本仓 `rho = Σ s_ij²` 不含 `f_ij`、不是渐近协方差 → 定义错配。原 §4.1 的「降级为 E5（推断）」**撤销**（见 §4.1 已重写）。
- **新增闭式/实测结论**：`rho = Σs_ij²`；`π` 的语义随 pandas 版本漂移（<3.0 为 `Σs_ii²`，3.0.3 为全 panel 方差标量）→ install 环境实测 `κ=−0.879584`、`α=0`、`max|Σ̂_LW−S|=0.0` ⇒ 默认 LW **从未收缩**。→ G-P046-3 由「退化」改判为「**install 环境下恒等 no-op + 版本相关语义**」；C1 可直接消除该版本敏感点。
- **新增风险（E2 引出，待复核）**：sklearn 默认先中心化；本仓是否去均值**本次未核验**（探针因 α≡0 无法区分）→ 登记 **U-P046-9**。
- **结论**：C1（复用 sklearn）不仅修参数，还**同时**纠正目标矩阵与 π/ρ/γ 的定义体系 → 证据强度由「强」升为「A 级全文支撑」。

#### U-P046-1（B2 残差留现金）— 证据 **中-强（新增行业规范一手锚）**，性质不变

- **硬事实（无需外部锚点）**：`n × max_weight < 1` 且要求 `Σw = 1` ⇒ 可行域为空。
- E4：cvxpy 对此返回 `status="infeasible"`，部分路径直接抛 `SolverError` → **上层必须显式裁决，不能假定有解**。
- E5 + **E8（实测）**：pypfopt 1.6.0 对 `Σmax<1` / `Σmin>1` / `min>max` 三类**构造期均不报错**，统一在 `max_sharpe()` 时抛 `OptimizationError(..., 'Solver status: infeasible')` → 工业库**不做预校验、也不留现金**；本仓若要 fail-loud，**必须自己加**（与 §15.7 第 1 条 `__post_init__` 一致）。
- **E9/E10（新增，A 级逐字）**：MSCI Barra 指数方法论给出**机械式 relax 序列**：soft constraint（惩罚）→ 2× trade limit → 成分权重 ±2%→±2.5% → 成分数上限 ×1.25；全部放宽后仍无解则「**will not be rebalanced**」。MinVol 方法论则把 **min_weight 逐档下调**（0.05% → 0.01%）→ 对应本仓 **U1-B 不得上调 `m0`**（否则违 I-P046-2 无杠杆）的判断，与 E10 方向一致。
- **订正**：本文原「推荐 B2」的写法容易被读成有外部依据。实际情况是：外部证据只支持「**必须显式处理**不可行」+「**relax 必须有序且可审计**」，**不支持二选一**；B1 与 B2 均为合法产品语义。
- **E9 与本仓现状的同构点**：MSCI 终态「本月不调仓」≈ 本仓 [engine_v2 L1087-L1099](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1087-L1099) 的 `return`（整日零调仓）——**作为兜底可接受，但不得作为唯一手段**（MSCI 是先 relax、后放弃；本仓现状是直接放弃）。
- B2 的仓内依据（**已核实存在**）：P-048 [risk_overlay.py L114](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L114) 字段与 [L300](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L300) `cash_residual=1.0 − Σw`；且 DoD A1「约束不变量为真」要求「不可行时不得静默放宽」。
- **结论**：仍推荐 **B2 + 显式诊断**（U1-A）与 **B1**（U1-B/U1-D），但**明确标记为产品裁决**，最终由用户定夺；E9/E10 仅作**合理性佐证**，不构成「必须选 B1/B2」的强制依据。

#### U-P046-3（引擎统一协方差注入）— 证据 **弱-中**，结论不变

- E6/E7（**已升级为全文**）：vol targeting / volatility-managed 文献把「波动率估计」当作策略输入，**未规定**必须与横截面优化器共享同一 Σ → **不能从文献推出「必须统一」**。可引用的仅有效应量（E6：Sharpe 0.53→0.97、MDD −96.69%→−45.20%；E7：市场组合 α=4.9%、Sharpe +25%），**与 σ SSOT 无关**。
- 真正支撑「统一」的是：E5 的接口形态（`cov_matrix` 由调用方构造后显式传入，而非优化器内部按 method 自算）+ 本仓 `σ_p = sqrt(wᵀΣw)` 诊断自洽的 SSOT 要求。
- **结论不变**（选项 i），但论证基础从「文献要求」降为「接口先例 + 内部一致性」。
- 附带确认：P-048 的 S15 场景 `target_vol=None`，σ 不参与缩放 → 该改动对已锁场景数值零影响（§6.3 论断维持）。

### 14.4 建议变更汇总

| 项 | 原建议 | 补充调研后 | 变化性质 |
|---|---|---|---|
| U-P046-1 | B2 | B2（U1-A）+ B1（U1-B/U1-D），**标为产品裁决**；新增 E9/E10 行业 relax 序列佐证 | 证据加强（方案不变） |
| U-P046-2 | C1 | C1，证据升级为「目标矩阵 + π/ρ/γ 双重结构性错误，A 级全文」 | **加强** |
| U-P046-3 | i | i，证据降级为「接口先例 + SSOT」 | 降级（方案不变） |

### 14.5 不得引用清单（防幻觉）

| 主张 | 原因 |
|---|---|
| BL 1992 正文的逐字表述 | 全文为图片扫描件（无文本层），未 OCR（E12）；BL 公式一律引 E11（He-Litterman 1999） |
| HRP（López de Prado 2016）的算法三步细节 | 仅摘要级（E13），全文付费墙；只能引开源实现并标注「实现参照」 |
| `max_sharpe` / `efficient_risk` 的**内部实现差异** | 仅读 docstring 与类头；E8 只实测了"不可行时的异常类型"，未逐行核对权重求解链路 |
| 「Axioma / Barra 要求本仓必须留现金 / 必须放宽」 | E9/E10 描述的是**指数编制**流程（成分满仓），不能外推为本仓产品语义；只能引"有序 relax + 终态不调仓"这一形态 |
| LW 2003 的 ρ̂ **通用公式** | E1 Lemma 2 的 ρ̂ 公式是**单指数目标专用**（`f_ij=s_i0s_j0/s_00`）；本文不把它当作任意目标的通用式（原文 p.613 亦明示需 case-by-case 调整） |
| Moreira-Muir 的**期刊版**数值 | E7 引的是 NBER WP（Apr 2016），与 JF 2017 期刊版可能存在差异 → 引用时须标明版本 |

### 14.6 新增未决项

| ID | 未决项 | 处置 |
|---|---|---|
| **U-P046-9** | 本仓 `_ledoit_wolf_shrinkage` 是否中心化（对照 sklearn `assume_centered=False`） | Step 5 用已知均值序列构造对照 |
| **U-P046-10** | 是否提供 `infeasible_policy` 开关 | 建议**不加**（最小复杂度）；若选 B1 则硬编码 |
| **U-P046-11** | 外部文档抓取自主 `stable`/`master`，与锁版 sklearn 1.9.0 可能有差异 | 已用本地源码+运行时实测复核；Step 3 复跑 API 存在性即可 |
| **U-P046-12** | L2 若落 HRP：缺少原文可引，实现口径（linkage / 距离度量 / 递归二分细节）无一手依据 | Step 3 前二选一：①用 `riskfolio-lib` 实现并在 DESIGN 标注「实现参照」；②降级 HRP 为可选（不纳入本批 DoD） |
| **U-P046-13** | `np.var(df, ddof=1)` 语义随 pandas 版本漂移（<3.0 按列 → `Σs_ii²`；3.0.3 → 全 panel 标量，本仓实测） | 若选 C2（保留自研）必须显式 `axis=0` 并在 DESIGN 记录版本前提；选 C1（sklearn）则本项自动消解 |

**处置状态（2026-11-20 裁决后）**：**U-P046-9 / U-P046-13 随 C1 消解**（自研 `_ledoit_wolf_shrinkage` 删除，改由 sklearn 口径决定）；**U-P046-10 不加开关**（B1 路径硬编码）；**U-P046-11 已复核**（锁版源码 + 运行时实测）；**U-P046-12 待定**——仅阻塞 P-046b。

### 14.7 检索覆盖度自评

| 目标 | 状态 |
|---|---|
| LW 方法学 | ✅ **一手全文 2 篇**（E1 JEF 2003 / E1b JMVA 2004）+ sklearn 文档与锁版源码（E2/E3） |
| 不可行约束语义 | ✅ cvxpy 官方（E4）+ pypfopt 1.6.0 四类边界实测（E8）+ 工业库接口（E5） |
| vol targeting 依据 | ✅ **两篇全文**（E6 接受稿 / E7 NBER WP），效应量可引 |
| 约束 relax 的行业规范 | ✅ **MSCI 官方方法论 2 篇**（E9/E10，含页码与逐字序列） |
| BL 方法学 | ⚠️ 书目（E12）+ 一手白皮书公式锚（E11）；BL 1992 正文不可引 |
| HRP 方法学 | ❌ 仅摘要（E13）→ U-P046-12 |

---

## 15. U-P046-1 裁决规范与验收标准（产品决策项）

### 15.1 为什么必须先写验收标准

U-P046-1 **无外部标准可依**（§14.3 E4/E5 只支持「必须显式处理」，不规定处理方式）。若直接进入 Step 3，DESIGN 会在「不可行」的口径上反复：判定用 `target_count` 还是实际 n、上下限两种不可行是否同解、抛错被引擎吞掉算不算生效。本节先把口径、行为、验证三层固定下来，使裁决变成**填空**而非重新论证。

### 15.2 判定口径（P0：先于选项，必须无条件先定）

#### 15.2.1 记号与实际 n 的定义（易错点）

| 记号 | 定义 | 证据 |
|---|---|---|
| **n** | **选择后实际参与优化的标的数** = `len(selected_stocks)` | [portfolio.py L177](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L177) `target_count = min(cfg.target_count, len(valid_scores))`；L179/L181 `nlargest/nsmallest` |
| m / m0 | `max_weight` / `min_weight` | [config.py L280-L281](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L280-L281) |
| 全投资假设 | `Σw = 1`（P-046a 之前不变） | [portfolio.py L184](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L184) 等权 `1/len` |

> **禁止**用 `cfg.target_count` 判定：L170 已剔除 `NaN` 与 `0` 值，L177 又取 `min()` → 实际 n 可能**远小于** `target_count`，判定口径必须取选择后的真实 n。
>
> **口径分叉（2026-11-20 核查，§13.1 C-5）**：`min_variance` / `mean_variance` 的选股为 `nlargest(cfg.target_count)`，**不做 `min()` 截断、也不过滤 0 值**（[L216](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L216) / [L281](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L281)）。"n = 选择后真实标的数"的定义仍成立，但这两条路径的 n 可能含零值标的 → 判定前须按 method 分别取 n。

#### 15.2.2 四类不可行（分型是裁决的前提）

| 类型 | 条件 | 数学性质 | 能否「留现金」解决 |
|---|---|---|---|
| **U1-A 上限型** | `n·m < 1 − atol` | 上限总和不足 1 | ✅ 可以（`Σw = n·m`，残差现金） |
| **U1-B 下限型** | `n·m0 > 1 + atol` | 下限强制超额，可行域空 | ❌ **不能**（需 `Σw > 1`，违反无杠杆不变式） |
| **U1-C 空集** | `n = 0`（无有效分数） | 无标的可选 | 已有行为：空权重 + `warning`（[L172-L174](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L172-L174)） |
| **U1-D 配置矛盾** | `m0 ≥ m` | 配置非法 | 不适用（应校验拦下） |

> **关键订正**：本文 §5.2 曾把 B1/B2 当互斥单选。实际 U1-A 与 U1-B 的**可解空间不同**——B2 只对 U1-A 成立；U1-B 若选 B2 会输出 `Σw > 1`，直接违反 I-P046-2。因此裁决必须**按分型分别指定**。

#### 15.2.3 判定时点与容差

- **时点**：`optimize()` 内、`_apply_constraints` 调用**之前**（等权为 L187 之前；ERC 为 [L389](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L389) 之前）。不得放在 `__post_init__`（配置期不知道实际 n）。
- **容差**：`atol = 1e-12`；可行判据为 `n*m >= 1 - atol` 与 `n*m0 <= 1 + atol`。禁止用 `==` 比较。

#### 15.2.4 明确**不属**本裁决的失败模式

| 现象 | 归属 |
|---|---|
| 整手取整后买不起（`value_buffer=0.985`） | `target_positions` 层，与约束可行性无关 |
| 非 PSD 协方差 → `DCPError` | G-P046-5（另立，见 §3） |
| 求解器 `status="infeasible"`（cvxpy 硬约束路径） | 若 Step 3 选 A2 方案才出现，届时须按本节同口径处理 |
| 零方差窗口 → ERC NaN | G-P046-4（另立） |

### 15.3 公共验收标准（AC-C，任何选项均 MUST 通过）

| 编号 | 断言 | 证据形式 |
|---|---|---|
| **AC-C-01a** | `cov_method="sample"` 下，四 method 在可行域内的输出与旧实现**逐位相同**（`abs=1e-12`）——隔离「约束修复不改可行域内解」 | 以 `_apply_constraints_legacy` 为对照**运行期双跑**（不硬编码向量，A5 合规） |
| **AC-C-01b** | golden 18 零重录 | `-k golden` 18 passed |
| **AC-C-01c** | `ledoit_wolf` 下 `estimate_cov` 与 `sklearn.covariance.LedoitWolf().fit(X).covariance_` **逐位相等**；另附 2×2 手算闭式一例 | 对拍 + 闭式推导（禁录制） |
| **AC-C-02** | 恒有 `Σw ≤ 1 + 1e-12`（永不超过满仓） | 全参数化用例 |
| **AC-C-03** | 恒有 `-1e-12 ≤ w_i ≤ m + 1e-9`（无负权重、无超上限） | 全参数化用例 |
| **AC-C-04** | 无 `NaN`/`inf`，含 `Σw_raw = 0` 路径（当前 [L144](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L144) 除零无防护） | 退化输入用例 |
| **AC-C-05** | 幂等：同输入连续两次调用逐位相等 | 双调用断言 |
| **AC-C-06** | 确定性：无随机数、无时间依赖 | 静态读码 + 重复运行哈希 |
| **AC-C-07** | 不可行发生时**必有**结构化诊断（字段至少含 `infeasible_kind` / `n` / `max_weight` / `min_weight`） | 断言诊断对象 |
| **AC-C-08** | dataclass `OptimizerConfig` 增加 `__post_init__` 校验（`0<m≤1`、`m0≥0`、`m0<m`、`target_count≥1`）。~~与 pydantic 两处等价~~ → **改判**：`config_v2` 为 FROZEN（TD-2，§13.1 C-4），**不参与**；验收改为「dataclass 单侧校验 + 冻结例外记录」 | 参数化「非法配置逐条抛 `ValueError`」 |
| **AC-C-09** | 不改变 `target_count` 的既有选择逻辑（`min()` + 零值过滤） | 选择结果快照 |
| **AC-C-10** | **Σ 只算一次**（选项 i）：同一 rebalance 日内 optimizer 与 overlay 共享同一协方差对象，`estimate_cov` 全局调用计数 `== 1`（Step 8 由 F-S7-P046-3 建号） | monkeypatch 计数（CHECKLIST B12 首例） |

### 15.4 选项专属验收标准

#### B1 fail-loud（**已裁决**：U1-B 与 U1-D）

| 编号 | 断言 |
|---|---|
| AC-B1-01 | 触发时抛 **`InfeasibleConstraintError(ValueError)`**（专用类型，见 DESIGN §2.4 D-1），消息必须含 `method`、`n`、`max_weight`、`min_weight`、`required_max_weight=1/n`、以及 **`sum_max=n·m` 与 `sum_min=n·m0` 两项**（R-P046-7：原单一 `actual_max_weight` 对 U1-B 误导） |
| AC-B1-02 | 抛出发生在应用约束**前**，不产生任何部分权重（`optimize` 无副作用） |
| AC-B1-03 | 边界 `n*m = 1 − 1e-13` **不抛**（容差内视为可行） |
| AC-B1-04 | U1-A 与 U1-B 使用**可区分**的消息标识（便于下游分流与测试断言） |
| **AC-B1-05** | **引擎不得吞掉该错误**：现状 [engine_v2 L1087-L1099](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1087-L1099) `except Exception` → 记录 + `return`（整日不调仓）会把配置错误降级为静默跳过 → 必须区分「配置不可行」（冒泡）与「数值失败」（记录 + 跳过）。**口径澄清（Step 8，F-S7-P046-2）**：按 DESIGN §6.2 界定——**U1-D 冒泡**（`__post_init__`，启动即失败）、**U1-B 记录 + emit + 当日跳过**；「冒泡」仅指 U1-D |
| AC-B1-06 | **5 个** `target_count=2` 构造点（§13.1 C-1）须显式设定 `max_weight`（或预期 ValueError），不得靠宽松断言绕过 |

#### B2 残差留现金（**已裁决**：U1-A）

| 编号 | 断言 |
|---|---|
| AC-B2-01 | 通用式：`Σw = Σ_i min(w_i^scaled, m)`，**不再归一化**；`cash_residual = 1 − Σw`（`atol=1e-12`） |
| AC-B2-02 | 等权特例：`n=3, m=0.1` → 每项 `0.1`、`Σw=0.3`、残差 `0.7` |
| AC-B2-03 | 非等权（ERC）：保持相对关系，**仅截断不重归一化**；不得强制缩放到 `n·m` |
| AC-B2-04 | **U1-B 不得走 B2**（否则 `Σw > 1`）；必须回落到 B1 或 B3 |
| AC-B2-05 | 诊断含 `infeasible_kind="upper"`、`cash_residual`、`n`、`max_weight` |
| AC-B2-06 | `cash_residual` 与 P-048 `OverlayResult.cash_residual`（[L114](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L114)/[L300](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L300)）**同名同义**：均为 `1 − Σw` |
| **AC-B2-07** | B2 输出经 `target_positions` 转换后，未投资金 `= (1 − Σw) × total_value`（[L89-L91](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L89-L91) 仅对 `Σw>1` 告警、[L130](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L130) 不做归一化 → 无隐性杠杆、无二次缩放） | 端到端闭式断言 |
| **AC-B2-08** | U1-A 下 `min_variance` / `mean_variance` 输出恒为**各 `m`**（`Σw=n·m`），与目标函数无关 | 代数证明（DESIGN §4.3：`Σ=n·m` 且 `w_i≤m` ⇒ 全取上界）+ 参数化用例 |

#### B3 自动放宽（备选）

| 编号 | 断言 |
|---|---|
| AC-B3-01 | `m_eff = max(m, 1/n)`，输出 `Σw = 1`（满仓） |
| AC-B3-02 | `m_eff > m` 时必须有 `WARNING` 日志 + 诊断 `relaxed_max_weight`（无日志即判失败） |
| AC-B3-03 | `m_eff` 逐位可复现，且 `n` 变化时单调（`n` 增大 → `m_eff` 不增） |
| AC-B3-04 | 不得因放宽而修改 `cfg`（无副作用），`m_eff` 仅局部生效 |

#### B4 按 method 分流（备选）

| 编号 | 断言 |
|---|---|
| AC-B4-01 | `method="equal_weight"` 且 U1-A → 输出 `1/n`（豁免），其余 method 走裁决选项 |
| AC-B4-02 | 豁免必须写诊断 `exempted="equal_weight"`，否则视为静默 |

### 15.5 边界值矩阵（已实测浮点，`m=0.1` 族）

| n | m | `n·m` 实测 | 可行判定 | 期望分支 |
|---|---|---|---|---|
| 1 | 0.10 | `0.1` | ❌ | U1-A |
| 3 | 0.10 | `0.30000000000000004` | ❌ | U1-A |
| **10** | 0.10 | `1.0` | ✅ | 可行（边界用例） |
| 15 | 0.10 | `1.5` | ✅ | 可行 |
| **20** | 0.05 | `1.0` | ✅ | 可行（边界用例） |
| 7 | `1/7` | `1.0` | ✅ | 可行（浮点边界） |
| 20 | m0=0.06 | `n·m0=1.2` | ❌ | **U1-B** |

> 实测命令（`.venv` Python 3.12）：逐项打印 `n*m` 与 `n*m >= 1-1e-12`，上表为真实输出，非推算。

**表 B：工业库参照（pypfopt 1.6.0 运行时实测，2026-11-20，E8）**

| 用例 | `weight_bounds` | n | 构造期 | `max_sharpe()` | 说明 |
|---|---|---|---|---|---|
| A Σmax<1 | `(0.0, 0.10)` | 3 | 不抛错 | `OptimizationError(..., 'Solver status: infeasible')` | 对位 **U1-A** |
| B Σmin>1 | `(0.60, 1.0)` | 3 | 不抛错 | 同上 | 对位 **U1-B** |
| C 可行对照 | `(0.0, 0.40)` | 3 | 不抛错 | **成功** `w=[1/3,1/3,1/3]` | `max ≥ 1/n` |
| D 配置矛盾 | `(0.50, 0.30)` | 3 | **不抛错** | `infeasible` | 对位 **U1-D**；证明无 `min<max` 校验 |

> 复现：`uv run --no-project --with PyPortfolioOpt==1.6.0 python <脚本>`；脚本 4 个用例共用 `mu=0.05·1`、`Σ=0.04I+0.01`。
> 结论（写进 DESIGN 时可引）：「不可行在工业库中一律表现为**求解期 infeasible**，不存在构造期预校验」→ 本仓若要在 `__post_init__` 提前拦截（§15.7 #1），属**优于**工业库的行为，须在 AC 中显式声明为**本仓自选的严格性**，不得声称「业界通行」。

### 15.6 证据形式与门禁对接

| 项 | 要求 |
|---|---|
| 用例命名 | `test_u1_ac_<选项>_<编号>_<简述>`（如 `test_u1_ac_b2_02_equal_weight_three_names`） |
| 断言精度 | 权重用 `pytest.approx(abs=1e-12)`；上限用 `abs=1e-9` |
| 门禁 | 全量 `932 + Δ`；golden **18 零重录**；mypy 111→0；black 149·218；AST 22 不变 |
| CHECKLIST 映射 | 每条 AC 一行，实测列**零预填**（RULE-1） |
| 诊断证据 | 断言诊断对象的字段值，不依赖日志文本 |

### 15.7 裁决后的连带改动（MUST 清单）

| # | 改动 | 依据 |
|---|---|---|
| 1 | dataclass `OptimizerConfig` 增 `__post_init__`：`0 < m ≤ 1`、`m0 ≥ 0`、`m0 < m`、`target_count ≥ 1` | 现 L268-297 **零校验**；pydantic 已有 5 条；pypfopt 1.6.0 实测同样**零构造期校验**（E8 用例 D 不报错）→ 本仓加校验是**自选严格性**，须在 DESIGN 标注 |
| 2 | `config_v2.OptimizerConfig.cov_method` Literal **双向不一致**：缺 `ewma`（`COV_ESTIMATORS` 有）且多 `shrunk`（`COV_ESTIMATORS` 无）；FROZEN 不可改 → **仅记录冻结例外** | 双写不一致，与 AC-C-08 同族（R-P046-8） |
| 3 | `config_v2` 的 `industry_max_weight ≤ max_weight` 方向存疑（行业上限通常应 ≥ 个股上限） | §4.2 |
| 4 | `_apply_constraints` L144 除零防护 | AC-C-04 |
| 5 | 引擎 `except Exception`（L1087）区分「配置不可行」与「数值失败」 | AC-B1-05 |
| 6 | 三处 `target_count=2` 测试显式配置 | AC-B1-06 / U-P046-5 |
| 7 | (可选) P-059 新增「约束不可行」场景 S16 | §13-6 |
| 8 | DESIGN_p046 §约束语义 / CHECKLIST_p046 落 AC | 本文件 §15 |

### 15.8 推荐组合与决策记录模板

**已确认（2026-11-20，用户「按建议执行」）**：

| 分型 | 推荐选项 | 理由 |
|---|---|---|
| U1-A 上限型 | **B2 残差留现金 + 诊断** | 与 P-048 `cash_residual` 先例一致；使 `Σw ≤ 1` 不变量成立 |
| U1-B 下限型 | **B1 fail-loud** | 留现金无解（约束强制超额）；静默放宽会掩盖配置错误 |
| U1-C 空集 | **保持既有**（空权重 + warning） | L172-L174 行为已合理 |
| U1-D 配置矛盾 | **B1 fail-loud（配置期）** | 属配置非法，越早暴露越好 |

**决策记录模板**（Step 0 裁决时填写，落 PROGRESS）：

```yaml
DECISION-U-P046-1:
  U1-A_upper: B2          # B1 | B2 | B3
  U1-B_lower: B1          # B1 | B3
  U1-C_empty: existing    # 空权重 + warning
  U1-D_config: B1
  tolerance: 1e-12
  diagnostics_fields: [infeasible_kind, n, max_weight, min_weight, cash_residual]
  engine_error_policy: config_raise / numeric_skip
  decided_by: <用户>
  decided_at: <日期>
```

### 15.9 与 DoD 的映射

| DoD | 对应 AC |
|---|---|
| A2（不可行语义 ≥3 例） | AC-C-01a..09 + 所选选项专属 AC；边界矩阵 §15.5 提供 7 组参数 |
| A1（约束不变量） | AC-C-02/03 |
| A7（死配置处置） | §15.7-1/2/3 附带完成 |
| A10（golden 零重录） | AC-C-01b |

---

## 16. Step 2 异构复审报告（GLM-5.3-Flash，2026-11-20）

### 16.0 复审声明

- **复审基座**: GLM-5.3-Flash（与作者 DeepSeek-V4.1-Flash 异构，RULE-5 合规）；复审过程**未修改作者正文**，本节为追加，状态标记（§12/§13）为中性簿记。
- **复审对象**: 本文全文（含 §10.1 裁决、§13.1 仓内核查）及其引用的代码事实。
- **独立性**: 不采信作者结论，逐条以本仓源码 / 锁版第三方源码 / 探针复跑重新取证。
- **方法**: E3 静态读码 8 处 + E2 探针复跑 1 次 + 一手证据文本抽查 2 处 + AC/DoD/裁决三向一致性审查。
- **范围**: P-046a 语义修复为主审；P-046b/c 仅审边界（§16.3-4）。

### 16.1 独立事实核验（8/8 PASS）

| # | 核验对象 | 复审方法 | 结果 |
|---|---|---|---|
| R-A1 | engine_v2 L1083 只传 returns；L1087-1099 `except Exception`→record+emit+`return`；L1106 裸 `np.cov` | 读码 | ✅ 与 §2.3 逐字一致 |
| R-A2 | risk_overlay L114 `cash_residual` 字段；L300 `cash_residual=1.0−float(sum(out.values()))` | 读码 | ✅ B2 先例成立（AC-B2-06 可引） |
| R-A3 | config.py L268-297 dataclass **零校验**（无 `__post_init__`） | 读码 | ✅ §15.7-1 成立 |
| R-A4 | sklearn 1.9.0 `_shrunk_covariance.py`：L365 `mu`、L390 `beta`、L392 `delta`、L399 `shrinkage`；**L356 `X = X − X.mean(0)`（默认中心化）** | 锁版源码 | ✅ E2 全部命中，且直接证实 U-P046-9 |
| R-A5 | E1 Theorem 1 逐字（lw2003_pages.txt L319「sum of asymptotic variances of the entries」、L420 `pij ¼ AsyVar½`）；p.613 ρ case-by-case（L687「The formula for r would need to be readjusted on a case-by-」） | 原文抽查 | ✅ 与 §14.1 希腊字母降级映射（π→p、ρ→r）相符 |
| R-A6 | 探针可重放：复跑 `repo_lw_check.py` → `pi=1.448791e-08` / `rho=9.931296e-08` / `kappa=−0.879584` / `alpha=0.0` / `max|LW−S|=0.0` | 复跑 | ✅ 与 §4.1 **逐位一致** |
| R-A7 | §13.1 C-1..C-5（5 处 `target_count=2`、cvxpy 回退 L247-249/L316-318、industry.pkl 恒 1、config_v2 FROZEN L12-19、nlargest L216/L281） | 读码+探针 | ✅ 全部成立 |
| R-A8 | config_v2 `cov_method` Literal 含 `shrunk`（`COV_ESTIMATORS` 无此档）且缺 `ewma` | 读码 | ✅ §15.7-2 成立，且为**双向**不一致 |

### 16.2 复审发现

**级别**：B = Step 3 DESIGN 必答题（阻塞 DESIGN 定稿）/ M = DESIGN 落笔项 / L = 表述修正或建议。

| ID | 级别 | 发现 | 处置 |
|---|---|---|---|
| **R-P046-1** | **B** | **AC-C-01 与 C1 冲突**：AC-C-01 要求「可行域内输出与 `b5f69a7` 逐位相同（三 method 快照对比）」。若快照含 min_variance/mean_variance 且 `cov_method=ledoit_wolf`（默认），C1 替换后 α 由 0→非零，输出**必然变化** → AC-C-01 对这两 method 不可能成立。I-P046-8 不受影响（equal_weight 不消费 cov） | AC-C-01 改述二选一：①快照基线在 C1 落地后**重新固化**（先 C1、后快照，并在 DESIGN 标注新基线）；②收窄到 `equal_weight` |
| **R-P046-2** | **B** | **诊断通道未定义**：AC-C-05/07、AC-B2-05 要求结构化诊断对象（`infeasible_kind`/`n`/`cash_residual`），但 `optimize` 返回 `pd.Series` **无载体**；engine `_diagnostics.record` 仅记异常。§15.6 明禁「依赖日志文本」 | DESIGN 必答：①返回类型改 Result dataclass（动 4 处签名，须核对 P-044 D5 weights 模式直出与 P-051 注册表边界不受破坏）；②或旁路通道。P-048 `OverlayResult` 为同构先例 |
| **R-P046-3** | **B** | **cvxpy 路径的 B2 语义依赖巧合**：min_var/mvo `sum(w)==1` 硬约束在 U1-A 时必 infeasible → 静默回退等权（1/n 必超限）→ 进 `_apply_constraints` 后 B2 截断。数值**碰巧**等价于直接 clip，但：①浪费一次必败求解；②正确性依赖「回退权重恰好全超限」；③回退 `logger.warning` 与 B2 诊断语义混杂 | 可行性预检（U1 分型）**前置到选股后、求解前**，四 method 统一走 B1/B2 分支；cvxpy 只兜「数值失败」（与 G-P046-5 同层治理） |
| **R-P046-4** | M | **正面核验（RESEARCH 未声明）**：B2 的 `Σw<1` 与 target_positions **契约兼容**——[target_positions.py L89-L91](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L89-L91) 仅对 `Σw>1` 告警（隐性杠杆），[L130](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L130) `raw_quantity = weight × total_value × value_buffer / price` **不做 Σw 归一化** → 残差自然留现金、无隐性杠杆、无二次缩放 | 补 **AC-B2-07**（候选）：「B2 输出经 target_positions 转换后，未投资金 = (1−Σw)×total_value（闭式断言）」 |
| **R-P046-5** | M | **B1 异常类型须专用**：U1-D（配置期 `__post_init__`）与 U1-B（运行时 optimize 内）若同用裸 `ValueError`，engine L1087 `except Exception` 会把运行时 B1 也吞掉 → 违背 AC-B1-05 | DESIGN 引入专用异常（如 `InfeasibleConstraintError(ValueError)`），engine except 内 isinstance 分流：配置类冒泡、数值类记录+跳过；AST except 计数不变 |
| **R-P046-6** | L | **§5.2 旧可行性条件有误**：`n·m + (n−1)·m0 < 1` 既不必要也不充分（反例 n=3, m=0.5, m0=0.4：该式 2.3≥1 判「可行」，实际 n·m0=1.2>1 为 U1-B 不可行）。§15.2.2 双侧条件 `n·m<1 ∨ n·m0>1`（⟺ 区间和可行性 n·m0 ≤ 1 ≤ n·m）才是对的 | §5.2 补「已被 §15.2.2 取代」标注（作者回填） |
| **R-P046-7** | L | AC-B1-01 消息字段 `actual_max_weight=n*m` 对 U1-B 误导（实际违规量是 n·m0） | 消息改 `infeasible_measure`，或 U1-A/U1-B 各带 `sum_max`/`sum_min` |
| **R-P046-8** | L | §15.7-2 可加强：config_v2 双向不一致（缺 `ewma` + 多 `shrunk`）且 FROZEN 不可改 → 只能记录冻结例外（与 AC-C-08 改判同向） | DESIGN 记录，不改冻结模块 |
| **R-P046-9** | L | I-P046-6「不得静默跳过整日」与 engine_error_policy=numeric_skip（记录+跳过）需语义边界：「非静默」= 必须记录 + emit（L1087-1099 现状已做） | DESIGN 明确两层分工：optimizer 层修复/抛错为主，engine 层记录+跳过为兜底 |

### 16.3 §13.2 五项复审意见（逐项回答）

| # | §13.2 问题 | 复审意见 |
|---|---|---|
| 1 | cvxpy 路径 `infeasible→回退等权` 治理 | 采纳 R-P046-3：**预检前置，不保留回退路径**；若因回退面大而保留，须给诊断（不推荐） |
| 2 | MVO 静默回退是否与 G-P046-5 合并 | **合并**。cvxpy 求解失败（DCPError/infeasible/solver error）统一改「抛出 → engine 既有 except 语义接管」。test_p025 `test_optimize_failure_counted`（L253-261）依赖的是 `returns_data=None` 的 ValueError 路径，不依赖回退路径 → 预计无破坏，Step 3 复核 |
| 3 | AC-C-08 改判是否需用户追认 | **无需**。改判由硬事实强制（config_v2 FROZEN docstring L12-19），方向是「减少验证面」而非放宽 dataclass 侧验收；DESIGN 记录即可。若用户不认可，唯一恢复途径是解冻 config_v2（不建议） |
| 4 | HRP 数值稳定性 | 属 P-046b，且受 U-P046-12（无一手原文）制约 → **先裁决 U-P046-12 再评估**，本步不展开 |
| 5 | 是否新增 P-059 S16 场景 | **建议加**。单测只覆盖 optimizer 单元层；S16 走 engine 全链路锁定「B1 冒泡不被吞 / B2 残差现金落账」的端到端语义；P-048 S15 已有场景扩展先例，builder 参数化成本低 |

### 16.4 复审结论

**PASS（附 3 项 DESIGN 前置）**

- **事实层**：8 项独立核验全过，未发现幻觉；探针复跑逐位一致；一手证据抽查相符；§13.1 五项仓内核查成立。
- **逻辑层**：U1 分型数学（区间和可行性 ⟺ `n·m0 ≤ 1 ≤ n·m`）、B1/B2 分型裁决、E8 实测引用均成立；发现 AC-C-01 与 C1 一处内部冲突（R-P046-1）。
- **进入 Step 3 的前置**：R-P046-1 / R-P046-2 / R-P046-3 三题须在 DESIGN 给出明确答案；R-P046-4/5 为 DESIGN 落笔项；R-P046-6..9 为表述修正。
- 作者回填义务：§5.2 取代标注（R-P046-6）、AC-C-01 改述（R-P046-1）、AC-B2-07 增补（R-P046-4）——**Step 3 已全部完成**（见 [DESIGN_p046](DESIGN_p046_portfolio_optimization.md) §2.1 与本文 §15.3/§15.4）。

---

## 17. Step 4 设计复审报告（GLM-5.3-Flash，2026-11-20）

### 17.0 复审声明

- **对象**: [DESIGN_p046](DESIGN_p046_portfolio_optimization.md) @2026-11-20（354 行，含 D-R1/R2/R3 三答）；重点为 DESIGN §2 三决策、§4 分支矩阵、D-3（不删字段）、§9 R4（NaN 口径）。
- **方法**: E3 读码核验（`interfaces.py` / `strategy.py` / `portfolio.py` L230-L254 / golden 断言实现）+ E2 探针 1 组（cvxpy 1.9.1 默认 solver 约束违反 × 20 seeds；`sum(1/n)` 漂移）。
- **独立性**: 同 §16.0；复审未修改 DESIGN 正文，发现集中于本节。

### 17.1 独立核验（7/7 完成）

| # | 对象 | 复审方法 | 结果 |
|---|---|---|---|
| D-A1 | `IOptimizer` Protocol（[interfaces.py L230-L248](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L230-L248)）锁定 `optimize(signals, returns_data) -> pd.Series` | 读码 | ✅ D-R2 薄包装保兼容（签名不变）；但 DESIGN 未登记该契约面（→F-D-1） |
| D-A2 | [strategy.py L167/L216](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L167) 调用 `optimize`，L135 docstring「与引擎逐字同构」 | 读码 | ⚠️ DESIGN 影响面遗漏（→F-D-1） |
| D-A3 | min_var [L247-L254](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L247-L254)：失败回退等权；成功**直接返回 `w.value`，不过 `_apply_constraints`** | 读码 | ✅ 证实 D-R3 删回退分支的必要性；同时暴露可行路径后处理未明示（→F-D-2） |
| D-A4 | golden 比较 = `math.isclose`（rtol/atol 取自基线 JSON，[test_golden_baseline.py L53-L97](file:///f:/Coding/Factor_Trading_v3.0/tests/test_golden_baseline.py#L53-L97)；`_INT_PATHS` 精确计数） | 读码 | ✅ 非 `==` 比较 → 1e-16 级漂移安全（F-D-3 前提） |
| D-A5 | 探针（20 seeds，n=10，box `[0,0.15]`）：cvxpy 1.9.1 默认 **OSQP**；最差上界违反 `6.0e-21`、下界 `6.0e-21`、`\|sum−1\|` `2.2e-16` | 复跑 | ✅ AC-C-03 的 `1e-9` 容差实证安全 |
| D-A6 | 探针：`sum(1/n)` 仅 n=7 时 `0.9999999999999998` → 旧归一化漂移 `2.8e-17` | 复跑 | ✅ AC-C-01a / golden 容差内安全 |
| D-A7 | D-3（死配置不删）理由：JSON 反序列化兼容 + `test_config_v2` + config_v2 FROZEN | 读码 | ✅ 成立；「记录冻结例外」满足 A7「处置」语义 |

### 17.2 复审发现

| ID | 级别 | 发现 | 处置（作者 Step 5 前回填 DESIGN） |
|---|---|---|---|
| **F-D-1** | **MEDIUM** | **影响面遗漏**：`core/strategy.py` L167/L216 两个 `optimize` 调用点 + `IOptimizer` Protocol（interfaces.py L230-L248）未登记于 DESIGN §1.1/§6。后果：①U1-B/U1-D 异常将**首次穿透 strategy 路径**（原为静默超限）——方向符合 fail-loud，但须登记并在 `test_p046_engine` 加 strategy 路径用例；②`optimize` 签名被 Protocol 锁定，须显式声明「签名冻结、新增 `optimize_with_diagnostics` 不改 Protocol」 | DESIGN §1.3 补两条前置事实；§8.1 加 strategy 用例 |
| **F-D-2** | **MEDIUM** | **min_var/mvo 可行路径零后处理未明示**：旧实现成功时直接返回 `w.value`（D-A3）；若新实现追加 `_scale_to_budget` 后处理，AC-C-01a 对照基准即为「旧原始输出」→ 须明示「可行路径返回 solver 原始输出、不加投影」。且 AC-C-03 的 `1e-9` 依赖 OSQP 表现（D-A5 为良态问题实测），近奇异 Σ 可能更松 → `test_p046_cov` 加近奇异用例，AC-C-03 对 cvxpy 路径注明容差依据 | DESIGN §4.1 可行行加注；§8.1 加近奇异用例 |
| **F-D-3** | **MEDIUM** | **`_scale_to_budget` 短路条件未写入**：AC-C-01a 的逐位一致依赖「输入已满足预算（`\|Σ−budget\| ≤ tol`）时原样返回」的短路分支，DESIGN §4.2 未定义该条件；无短路时二分输出与旧归一化差 ~1e-16（容差内，但契约应显式） | §4.2 补短路条件与终态断言顺序 |
| F-D-4 | LOW | U1-B 为配置性根因、运行时逐日检出 → 引擎按日 skip + emit；建议首触发聚合（如 run 头部一次性 WARNING 或 `infeasible_days` 计数落账），避免长回测每日重复告警刷屏 | DESIGN §6.3 可选增强 |
| F-D-5 | LOW | §9 R4 影响面应扩展到 overlay：选项 i 使 overlay 也吃 listwise dropna 的 Σ；旧 `np.cov` 遇 NaN 会传染（可能依赖上游过滤）。行为变化方向为修复，但 `test_p046_engine` 须加「窗口含 NaN」用例 | §8.1 补用例 |
| F-D-6 | INFO | D-R3 的 n 口径分叉（equal_weight 滤 0 + `min()` 截断 vs min_var/mvo `nlargest` 原样，§13.1 C-5）→ `_precheck` 的 n 必须取各 method 选股后的 `len(selected_stocks)`，不得混用 `target_count` | DESIGN 已隐含；Step 5 落地时以断言固化 |
| F-D-7 | INFO | F-P046-6 旧路径（非 PSD → DCPError → 整日 return）在新设计下归 G-P046-5 抛出语义，行为等价（记录+emit+跳过），但诊断字段新增 `infeasible_kind` 缺省为 `None` → Step 5 须确认既有 `test_p026` 对 record 内容的断言不因新字段失败 | Step 5 复核 |

### 17.3 结论：**有条件通过**

- **事实层**：D-R1/R2/R3 三答的代码前提全部核实（Protocol 兼容、回退分支确认、golden 容差机制确认）；探针实证 OSQP 违反量级与归一化漂移均在容差内 → 三条 AC-C-01a/01b/01c 的容差组合**可行**。
- **通过条件**（作者在 Step 5 起草 IMPL 前回填 DESIGN）：F-D-1（影响面登记 + strategy 用例）、F-D-2（可行路径零后处理明示 + 近奇异用例）、F-D-3（短路条件写入 §4.2）。
- **记录项**：F-D-4..7 随 Step 5 落地，不阻塞。
- 复审基座异构合规；本节为追加，未修改 DESIGN 正文。

---

## 18. Step 6 IMPL 复审报告（GLM-5.3-Flash，2026-11-20）

> 依据 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 6 工具契约：检查实施细节与设计对齐；**依赖版本存在性核验**；接口签名可实现性。证据出口 = §18.1 版本核验表。

### 18.0 复审声明

- **对象**: [IMPL_p046](IMPL_p046_portfolio_optimization.md) @2026-11-20（503 行，T1-T7 + F-D-8..11）；对齐基准 = DESIGN_p046（含 Step 4 回填）。
- **方法**: E3 读码比对（IMPL 骨架逐条对照 `portfolio.py` / `engine_v2.py` / `diagnostics.py` / `risk_overlay.py` / `interfaces.py` 实码）+ E2 实测（依赖导入、`pyproject` 下限）。
- **独立性**: 同 §16.0；未修改 IMPL 正文。

### 18.1 版本核验表（Step 6 证据出口）

| 依赖 / stdlib | IMPL 引用位置 | 环境 / 版本 | 核验方式 | 结果 |
|---|---|---|---|---|
| `sklearn.covariance.LedoitWolf` | §2 导入、§3 `_lw_cov` | sklearn **1.9.0**（`.venv`） | import 实测 | ✅ 存在 |
| `cp.OPTIMAL` / `cp.OPTIMAL_INACCURATE` | §5.4/§5.5 状态判定 | cvxpy **1.9.1** | 属性实测 `optimal_inaccurate` | ✅ 存在 |
| `pandas.DataFrame.dropna/reindex/fillna/clip`、`np.linalg.eigh` | §3 `estimate_cov`/`_psd_project` | pandas **3.0.3** / numpy **2.4.6** | 既有代码同 API 在用（L226 `.loc` 等） | ✅ |
| `dataclasses.dataclass(frozen=True)`、`typing.Literal` | §2 类型层 | **requires-python ≥3.10**（pyproject），venv 3.12 | pyproject + venv 实测 | ✅ |
| 虚构三方库排查 | 全文 | — | 仅引用 repo 已装依赖（cvxpy/numpy/pandas/scipy/sklearn） | ✅ 无虚构 |

### 18.2 接口签名可实现性核验

| IMPL 引用 | 实码对照 | 结果 |
|---|---|---|
| `apply_overlay(..., cov=, codes=)`（§7.2） | [risk_overlay.py L253-L259](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L253-L259) **已有** `cov: Optional[np.ndarray]` + `codes` 参数（P-048 预留） | ✅ 就绪；T6 传 `cov.to_numpy()` + codes 序列 |
| `self._diagnostics.record_detail(date, stage, infeasible_kind=..., ...)`（§7.1） | [diagnostics.py L102](file:///f:/Coding/Factor_Trading_v3.0/core/diagnostics.py#L102) `record(date, stage, exc)` 仅收异常；[L133](file:///f:/Coding/Factor_Trading_v3.0/core/diagnostics.py#L133) `record_failure(date, stage, reason)` 仅收字符串；`DayErrorRecord`（L46-L55）为**冻结 dataclass、6 个固定字段**，无 detail 字段 | ❌ **虚构 API** → F-E-2 |
| `self.cfg.optimizer.cov_method`（§7.1） | engine L1071 同路径 `self.cfg.optimizer.cov_lookback` 在用 | ✅ |
| `_apply_constraints` 调用点仅 L187/L389（§4 注） | grep + 读码确认（min_var/mvo 不调用） | ✅ |
| `COV_ESTIMATORS` 仅 portfolio 内引用（§3.1 搁置项） | 消费点 L223/L288/L357 三处，**全部在 T4 替换面内** | ✅ 搁置的 grep 已代完成，可安全重构 |
| ERC 归一化在循环外（§5.6 删 L385 安全） | L382 循环结束 → L385 归一化 → L389 投影 | ✅ |
| F-D-8（MVO 覆盖注入 Σ） | [L286-L289](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L286-L289) `if returns is not None` 无条件重估 ✅；**且 else 分支（L290-L293）比 IMPL 记载更严重**：注入的全窗口 Σ 直接配 `len(selected)` 维变量 → `quad_form` **形状不匹配报错**，非仅「未 reindex」 | ✅ 修复必要，建议 IMPL §11 措辞升级 |
| min_var/mvo/rp 注入 cov 走 `.loc[selected, selected]`（§5.4/5.6） | 旧实现 L226/L360 **本就是 `.loc`**（缺失码 KeyError） | ✅ 与旧一致（但见 F-E-6 DESIGN 措辞冲突） |

### 18.3 与设计对齐核验

| 对齐点 | 结果 |
|---|---|
| `_precheck` 位置（选股后、求解前）+ 四型分流 + U1-A min_var/mvo 单点解 | ✅ 与 DESIGN §2.3/§4.1/§4.3 一致 |
| `_scale_to_budget` 短路（F-D-3）→ AC-C-01a 数学成立（`1/n ≤ m` 时短路返回；`sum(1/n)` 漂移 ≤2.8e-17 ≪ 1e-12） | ✅ |
| B2 语义（不归一化）+ ERC U1-A 保留相对比例 | ✅ |
| U1-D 配置期 `__post_init__`、U1-B 运行时抛 → engine 分流 | ✅（但分类见 F-E-2b） |
| **DESIGN §5.1「optimizer 对注入 cov reindex（缺失补 0）」vs IMPL `.loc`** | ⚠️ 冲突：旧实现即 `.loc`；为 AC-C-01a 保真应**改 DESIGN 措辞**而非改 IMPL（F-E-6） |
| `test_p025` 依赖的 `L211-212 ValueError` 路径 | ✅ 不受影响（普通 ValueError 非 InfeasibleConstraintError，分类仍 "solver"） |

### 18.4 复审发现

| ID | 级别 | 发现 | 处置（作者回填 IMPL） |
|---|---|---|---|
| **F-E-1** | **MEDIUM** | **AC-B1-01 消息缺 `method` 实名**：`_precheck(n, cfg)` 不接收 method，骨架消息为固定字面量「method 需 n=…」→ 违反 AC-B1-01（消息必须含 method） | `_precheck` 增 `method: str` 参数，消息内插真实 method 名 |
| **F-E-2** | **MEDIUM** | **diagnostics 集成面三重缺口**：①`record_detail` 虚构——须具体化扩展：`DayErrorRecord` 增 `detail: Optional[dict] = None`（frozen dataclass 加默认值字段向后兼容，`_index` 去重键不含该字段不受影响）+ `record_failure(..., **detail)` 或新方法；②**分类冲突**：[classify_day_error L68-70](file:///f:/Coding/Factor_Trading_v3.0/core/diagnostics.py#L68-L70) 对 stage="rebalance" 的 `ValueError` 一律 → `("solver", False)`，`InfeasibleConstraintError`（ValueError 子类）会被**误分类为 solver**——须在其前加类名字符串分支 `→ ("config", False)`（沿 L65-67 不 import 的先例）；③AC-C-07 的结构化字段（infeasible_kind/n/max/min/cash_residual）落 `detail` dict，禁入 message | T6 增「diagnostics 扩展」子任务（三件：字段/方法/分类分支），并补 `test_p046_engine` 断言 `category=="config"` |
| **F-E-3** | **MEDIUM** | **「低效排除表」缺失**：Step 5 工具契约硬约束「低效排除表非空」，IMPL 无此表（证据出口缺失） | IMPL 增 §12 低效排除表（候选条目：放弃 iterative clip-normalize 循环 / 不引入逐日双跑 cov / 不为死配置加运行时消费 / ERC 迭代内不加归一化） |
| F-E-4 | LOW | **OPTIMAL_INACCURATE 语义反转未登记**：旧 `!= cp.OPTIMAL` 视为失败（回退等权）；IMPL `not in (OPTIMAL, OPTIMAL_INACCURATE)` 视为成功。方向合理但属行为变化 | IMPL §8.3 增第 4 条登记 |
| F-E-5 | LOW | `estimate_cov` 有效行 <2 的回退用 `fillna(0.0)` 再算 sample——偏离 DESIGN §3.1「回退 sample」措辞（fillna 引入零收益伪样本） | 二选一：IMPL 登记为派生决策（Degenerate 输入语义），或改 DESIGN 措辞 |
| F-E-6 | LOW | DESIGN §5.1「reindex（缺失补 0）」与旧/IMPL `.loc` 行为冲突 | 作者改 DESIGN §5.1 措辞为「`.loc` 截取（缺失码 KeyError → 引擎捕获跳过），与 `b5f69a7` 一致」 |
| F-E-7 | LOW | min_var/mvo 空集行为变化（旧：空选股 → cvxpy 报错 → 引擎跳过；新：干净 empty 结果）未入 §8.3 | IMPL §8.3 增第 5 条 |
| F-E-8 | INFO | `_psd_project` 对已 PSD 矩阵的特征重建引入 ~1e-18 浮点差 → AC-C-01a（1e-12）内安全；如需逐位严格可对 sample 分支跳过投影 | 注明即可 |
| F-E-9 | INFO | §7.2 骨架未显式 `cov.to_numpy()` + codes 对齐 `apply_overlay` 的 ndarray 契约 | 实施时按 18.2 首行执行 |

### 18.5 结论：**有条件通过**

- **版本层**：5 项依赖/stdlib 核验全过，无虚构库（Step 6 契约核心 ✅）。
- **签名层**：8 项接口对照，7 项可实现/已预留；**`record_detail` 虚构**（F-E-2）是唯一阻断性签名问题。
- **对齐层**：分支矩阵/短路/B2/U1 分型与 DESIGN 一致；DESIGN §5.1 一处措辞须反向修正（F-E-6）。
- **进入 Step 9（实施）的条件**：作者回填 F-E-1（`_precheck` 加 method）、F-E-2（diagnostics 三件套）、F-E-3（低效排除表）；F-E-4/5/7 补登记；F-E-6 反向修 DESIGN。
- 复审基座异构合规（RULE-5）；本节为追加，未修改 IMPL 正文。

### 18.6 作者回填记录（2026-11-20，DeepSeek-V4.1-Flash）

| 发现 | 处置 | 落点 |
|---|---|---|
| F-E-1 | `_precheck(n, cfg, method: str)` + 消息内插真实 method；四处调用点补实参（含 `mean_variance` 显式骨架） | IMPL §2 / §5.3 / §5.4 / §5.5 / §5.6 |
| F-E-2 | 三件套具体化：`DayErrorRecord.detail` + `record_detail(...)` + `classify_day_error` 的 `InfeasibleConstraintError → ("config", False)` 前置分支；`"optimizer"` 新类别说明 | IMPL §7.1「diagnostics 集成三件套」+ §1.1 T6 + §1.2 文件清单 |
| F-E-3 | 新增 §12「低效排除表」（8 条） | IMPL §12 |
| F-E-4/5/7 | §8.3 增第 4/5/6 条行为变化登记 | IMPL §8.3 |
| F-E-6 | **反向修正 DESIGN**：`reindex（缺失补 0）` → `.loc` 截取、缺失码 KeyError、不 `fillna(0)` | DESIGN §5.1 |
| F-E-8/9 | §11 增两行（psd 重建浮点差、`cov` 的 ndarray 契约） | IMPL §11 |
| 结论 | Step 6 三项 MEDIUM 全部闭环，LOW/INFO 全部登记；**IMPL 可进入 Step 7 CHECKLIST** | — |

---

## 19. Step 8 文档一致性复审报告（GLM-5.3-Flash，2026-11-20）

> 依据 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 8：**识别并修复**四文档对齐问题。对象 = RESEARCH / DESIGN / IMPL / CHECKLIST 四文档现状（含 Step 6/7 回填后版本）。

### 19.0 方法

机械取证（grep 定位 + 行号读码）三对对齐：RESEARCH↔DESIGN、DESIGN↔IMPL、IMPL↔CHECKLIST；并复核 CHECKLIST §7 七条交接要点。

### 19.1 核验通过项

| 对齐点 | 证据 |
|---|---|
| 三项裁决 ↔ DESIGN §2 D-R1/R2/R3 | ✅ 一致 |
| Step 6 回填落点：DESIGN F-D-1（§1.3 strategy/Protocol）/ F-D-3（§4.2 短路）/ F-D-8 / F-E-6（§5.1 `.loc`）；IMPL `_precheck(..., method)` / diagnostics 三件套 / T6 含 `diagnostics.py` / §12 低效排除表 | ✅ 全部落地 |
| RESEARCH §15.4 B3/B4 标注「备选」 | ✅ 落选分支不进 CHECKLIST 正确（Step 8 已在 CHECKLIST §5 显式声明） |
| IMPL §8.2 ↔ CHECKLIST B13 五构造点 | ✅ 逐点一致 |
| CHECKLIST 零预填 | ✅ 42×`[待 Step 9]` + 1×`[待 Step 10]` |
| ID 命名空间 | ✅ DESIGN-D* / I1-I8 / AC-* / F-D-*/F-E-*/F-S7-* 无混用（CHECKLIST §7.3 已载） |

### 19.2 对齐缺口与修复（本步直接修复，6 处）

| ID | 级别 | 缺口 | 修复落点 |
|---|---|---|---|
| F-S8-P046-1 | MEDIUM | **IMPL §8.1 用例清单落后 CHECKLIST 41 目标约 10 函数**：constraints 缺 C-08/C-09/B1-04/B2-04/05/06/07 六项，cov 缺 EWMA 一项，engine 缺 U1-B 经引擎/U1-A 落账/p026 兼容三项；且 B1-05 误列 constraints 模块 | IMPL §8.1 全表重排（constraints 17 行 + cov 4 行 + engine 7 行）+ collect 分解注记（41 = 27+7+7） |
| F-S8-P046-2 | MEDIUM | **IMPL §9 门禁为旧读数**（「932 + Δ」「black 149·218 起」），与 CHECKLIST D1-D4 终态（973 / 152·221 / 109）冲突 | IMPL §9 改终态读数并注明原表述作废 |
| F-S8-P046-3 | LOW | **CHECKLIST B1 分解标签错位**：「C-02..C-09（7）+ B1 六项（8）」未说明 C-08 计入 B1 组、B1-05 测试物在 engine 模块 | CHECKLIST B1 改为显式分解（4+7+1+1+4+1+1+8=27）并注记跨模块归属 |
| F-S8-P046-4 | LOW | **AC-C-10 未建号**（F-S7-P046-3 遗留）：CHECKLIST B12 首例引用「选项 i」而非 AC 编号 | RESEARCH §15.3 增 AC-C-10 行；CHECKLIST B12 / IMPL §8.1 同步改引 AC-C-10 |
| F-S8-P046-5 | LOW | **AC-B1-05 口径歧义未闭环**（F-S7-P046-2 遗留）：RESEARCH 原文「配置不可行（冒泡）」与 DESIGN §6.2「U1-B 记录+跳过」冲突 | RESEARCH AC-B1-05 行加口径澄清：**U1-D 冒泡 / U1-B 记录+跳过**（引用 CHECKLIST C6 界定） |
| F-S8-P046-6 | INFO | IMPL §8.1 collect 注记初稿含未决式残留（「= 28？」） | 随 F-S8-P046-1 重写时消除 |

### 19.3 修复后计数链（终态，单一来源 = CHECKLIST §5）

- **41** = constraints **27**（01a×4 + C-02..07/09×7 + C-08×1 + B1-01×1 + B1-02×4 + B1-03×1 + B1-04×1 + B2×8）+ cov **7** + engine **7**；973 = 932 + 41
- B1-05 测试物 `test_engine_u1b_config_category` 在 engine 模块，计数归 B12；strategy 冒泡（F-D-1）为独立用例
- golden **18 + 0**；mypy **111 不变**；black **152·221**；`tests/*.py` **109**；AST **22（core 外）·30（core）**

### 19.4 结论

- **对齐修复后 PASS**：四文档计数链单一来源（CHECKLIST §5）、AC 编号全覆盖被裁决分支、口径歧义清零、回填落点全验证。
- Step 9 前无遗留对齐项；CHECKLIST 43 项实测列仍为零预填（42+1）。
- 复审基座异构合规（RULE-5）；本节修复均为文档对齐性最小改动，未触碰任何技术决策（D-R1/R2/R3、D-1..D-8 不变）。

---

## 20. Step 9 验收回填报告（作者基座 DeepSeek-V4.1-Flash，2026-11-20）

> 依据 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 9：按 IMPL T1-T7 落码 → 跑门禁 → 回填 CHECKLIST 42 项实测列。全部读数取自本机未提交工作区（`.venv\Scripts\python.exe`，`MPLBACKEND=Agg`）。

### 20.1 落码范围（T1-T7）

| 任务 | 落点 | 结果 |
|---|---|---|
| T1 类型层 | `core/portfolio.py`：`InfeasibleConstraintError` / `OptimizationResult` / `_Feasibility` / `_precheck(n, cfg, method)` | ✅ |
| T2 协方差 | `estimate_cov` 统一入口（sklearn `LedoitWolf` + listwise + `_psd_project`）；删除自研 `_ledoit_wolf_shrinkage` | ✅ |
| T3 投影 | `_clip_series` / `_scale_to_budget`（短路 + doubling + 二分 + 终态断言）/ `_apply_constraints` / `_apply_constraints_legacy` | ✅ |
| T4 四优化器 | `equal_weight` / `min_variance` / `mean_variance` / `risk_parity` 均实现 `optimize_with_diagnostics`；`optimize` 薄包装（签名不变） | ✅ |
| T5 config | `OptimizerConfig.__post_init__` 四条校验；`cov_shrinkage` 标注 deprecated 保留 | ✅ |
| T6 接线 | `core/engine_v2.py` 单一 Σ 注入 optimizer + overlay（删裸 `np.cov`）；`core/diagnostics.py` 三件套 | ✅ |
| T7 测试 | 3 个新模块（constraints / cov / engine），实测 collect **55** | ✅ |

### 20.2 门禁实测

| 门禁 | 计划 | 实测 |
|---|---|---|
| 全量 pytest | 973 | **987 passed**（932 + 55） |
| `-k golden` | 18 零重录 | **18 passed**；`tests/golden/` 零 diff |
| mypy（CI 逐字） | 111 files 0 | **111 files 0 issue** |
| black | 152 · 221 | **152 · 221**（0 reformatted） |
| `tests/*.py` | 109 | **109** |
| AST `except Exception` | core 外 22 / core 30 | core 外 **26** / core **30**（见 F-S9-P046-2） |
| `uv lock --check` | exit 0 | **0** |

### 20.3 新增用例 55 的机械分解

- constraints **38** = C-01a×4 + C-02×3 + C-03×3 + C-04×1 + C-05×1 + C-06×1 + C-07×1 + C-08×4 + C-09×1 + B1-01×1 + B1-02×4 + B1-03×1 + B1-04×1 + B2-01×1 + B2-02×1 + B2-03×1 + B2-04×1 + B2-05×1 + B2-06×1 + B2-07×1 + B2-08×4 + `test_cov_entry_used_by_optimizer`×1
- cov **10** = 计划 7 + I8 三 method 参数化 3（`test_all_methods_symmetric_psd`）
- engine **7**（含 AC-C-10 计数、U1-B config、U1-A optimizer、ERROR 事件、strategy 冒泡、零方差窗口、`test_p026` 兼容）

### 20.4 发现登记

| ID | 级别 | 内容 | 处置 |
|---|---|---|---|
| **F-S9-P046-1** | P3（计数偏移） | collect 41 → **55**（+14）：constraints 27 → 38（C-02/C-03 参数化 +4、C-08 展开 +3、B2-08 展开 +3、`test_cov_entry_used_by_optimizer` +1）；cov 7 → 10（I8 三 method +3）；全量 973 → **987** | 以实测为准回填 CHECKLIST；计划数不回改（§5 保留计划 + §8 记录实测） |
| **F-S9-P046-2** | P3（基线口径） | AST 基线「core 外 22」在复算脚本（生产面 rglob + AST，排除点目录）下为 **26**；无法复现 22 → 基线扫描口径未随文档固化 | core 外本批零 diff（`git status`），无新增；口径差异登记，P-046b 启动前固化扫描脚本 |
| **F-S9-P046-3** | P3（既有测试） | D6 预计改「5 处既有测试」，实际 **2 处**：`test_p031_strategy_engine_accounting.py` L73 补 `max_weight=1.0`（原断言依赖 clip→归一 0.5，属语义修正）、`test_p048_overlay_engine.py` vol 腿改用 sklearn `LedoitWolf` 复算 σ（overlay 复用单一 Σ 的合法后果，删硬编码 0.3004）；其余 3 个构造点（`test_p023:128` / `test_p025:178,259,300` / `test_p026:229`）断言不依赖权重数值，零改动 | 两处均按「语义修正」登记；无宽松断言 |

### 20.5 回退点状态

R1/R2/R3 与整体 revert **均未触发**（无需回退）；`_apply_constraints_legacy` 保留，删除条件见 PROGRESS §3.55.2。

### 20.6 声明

- 改动**未提交**（用户未授权）；D10 提交与 CI 待 Step 10。
- 作者基座 DeepSeek-V4.1-Flash；Step 10 终审须异构基座（RULE-5）。

---

## 21. Step 10 异构终审报告（ADD 审计，2026-11-20）

> **基座**: GLM-5.3-Flash（异构于作者 DeepSeek-V4.1-Flash，RULE-5 ✓）；**对象**: 提交 `15f608a`（原子实现提交，含 Step 1-9 全部产出）。
> **方法**: SPEC_PROCESS v1.7.2 Step 10 = ADD 四阶段审计 + 取证矩阵（RULE-6）+ 诚实结果列。

### 21.1 四阶段结论

| 阶段 | 审什么 | 结论 |
|---|---|---|
| Phase 0 Spec 质量门 | DESIGN 可审计性 | ✅ Step 4/8 已复审通过（§17/§19）；分支矩阵、AC 映射、门禁命令均为机械可核对形态 |
| Phase 1 完整性（design→code） | DESIGN §1.1 T1-T9 每项在代码有实现 | ✅ 九项逐一落码（取证矩阵第 8 行 E3 行号）；无缺失分支 |
| Phase 2 忠实度（双向对照） | 实现与设计一致 | ✅ 主体一致；**发现 3 项 P3 微偏差**（§21.3），无 P1/P2、无静默语义改写 |
| Phase 3 必要性（code→design） | 代码行为均有设计依据 | ✅ 全部派生行为已登记（mypy 修复×4、退化输入等权重建→I3、`feas=None` 默认参→F-D-10、2 参桩回退→D-R2、I8 三 method 用例→CHECKLIST B11、U1-C 落账→I5）；**盲区扫描 0 项未登记派生** |
| Phase 4 语义 | 意图层：不可行不再静默破坏约束 + Σ 单一入口 | ✅ golden 18 零漂移（兼容面）+ U1-A/B 显式用例 + E2 对抗全过；批次意图达成 |

### 21.2 取证矩阵（RULE-6，诚实结果列）

| 取证手段（等级） | 覆盖项 | 结果 |
|---|---|---|
| 全量 pytest（E1） | T1-T7 全部 AC / A1-A12 / B 组 / I1-I4 | ✅ **987 passed**（114.65s，终审重跑） |
| `-k golden` + `git status tests/golden/`（E1） | I7 / AC-C-01b | ✅ 18 passed；零 diff |
| mypy CI 逐字命令（E1） | A6 类型兼容 | ✅ 111 files 0 issue |
| black 双口径 + `tests/*.py` 计数（E1） | D4 | ✅ 152 · 221 unchanged；109 |
| `uv lock --check`（E1） | D7 | ✅ exit 0 |
| AST `except Exception` 扫描脚本（E1） | D5 | ✅ core 30 / core 外 26；`portfolio.py` 0 try-except、0 type-ignore |
| **E2 对抗脚本**（场景选择理由：边界轮 + 异常输入 + 退化输入） | A2/A3/A5/B5/B8/C2/C8 | ✅ 21/21（首轮 2 例**脚本口径错误**——U1-B 阈值误用 1e-13（正确语义 `>1+1e-12`）、空集与无数据混淆；修正后复跑全过，原样记录） |
| 静态读码行号（E3 `@15f608a`） | T1-T9 落点 | ✅ `_precheck` L77-95、`_scale_to_budget` L102-149（短路 L123-125 / 终态断言 L144-148）、`_psd_project` L190-196、`estimate_cov` L199-228、D-R2 接口 L243-259、legacy L296-300、minvar/mvo U1-A 单点解 L388-406/L452-470、零方差防护 L527-542、engine 单一 Σ L1109-1115 + record_detail L1117-1131 + except 兜底 L1134-1146 + overlay 复用 L1151-1156、config `__post_init__` L299-311、diagnostics config 分流 L64 + `record_detail` L167 |
| grep 盲区扫描（E4，扫描范围：① 静默归一化残留 `/sum()` ② `np.cov` 残留 ③ `cov_shrinkage` 消费者） | Phase 2/3 | **发现 0 项**：① 仅 `legacy`（对拍专用）与 `round_lot_optimize`（死面白名单）② 仅 `_cov_sample`（合法）与 `global_contagion.py`（本批范围外零 diff）③ 零消费 |
| 全文读码降级重扫（E4，engine_v2 优化段 L1100-1146 逐行） | I6 静默路径 | **发现 0 项**（第二角度复核后维持零发现，声明扫描范围如左） |
| `git diff` 白名单核对（E1） | D6 零 diff 面 | ✅ `config_v2` / `interfaces` / `risk_overlay` / `target_positions` / golden / scenarios 全部不在提交内 |

### 21.3 发现登记（P1=0 / P2=0 / P3=3 / INFO=1）

| ID | 级别 | 内容 | 处置 |
|---|---|---|---|
| **F-S10-P046-1** | P3 | DESIGN §4.4 / IMPL §5.5 规定零方差防护返回 `message="zero_vol"`；实现只 break 保持等权、`message=""`（[portfolio.py L527-542@15f608a](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L527-L542)）。行为面（无 NaN / 等权 / 不崩）已实现并被 `test_zero_variance_window` 固化，仅诊断消息缺失；且若直接补消息，engine L1117-1131 会把 zero_vol 误标 `error_type="InfeasibleConstraints"`——需先定义独立 error_type 语义 | **登记不修**，归 P-046b（非阻断；补消息须连带 engine 误标修正，超出本批冻结面） |
| **F-S10-P046-2** | P3 | `estimate_cov` 有效行 <2 退化分支：IMPL §4.2 骨架含 `logger.warning("回退 sample")`，实现无 warning，且补零后沿用**选定 method**（LW 时伪协方差非严格 0）而非 sample。数值方向已由 IMPL §8.3-6（F-E-5）登记为与 DESIGN「同向」的偏差 | **登记不修**；P-046b 补 warning（行为面无风险：输出仍经 `psd_fix` 保 PSD，`test_nan_listwise` 已锁不抛不 NaN） |
| **F-S10-P046-3** | P3 | `estimate_cov(codes=...)` 参数语义与 DESIGN §3.1 docstring 不符——文档「reindex（缺失列补 0）」，实现为**静默取交集**（E2 第 D 组实测：codes 含缺失码 → 返回交集列）。当前**零生产调用方**传 codes（engine / `_cov_for` 均不传），无行为影响 | **登记不修**；P-046b 收口（改 KeyError 或删参数，与 §5.1 F-E-6「缺失码 KeyError」口径对齐） |
| **F-S10-P046-4** | INFO | ① engine record_detail stage 实测 `"rebalance"`（∈STAGES ✓）而非 IMPL §7.2 骨架笔误的 `"rebalance_optimizer"`（∉STAGES）——实现正确；② DESIGN §2.3 代码块 `_precheck(n, cfg)` 签名未同步 F-E-1 的三参形态（以 CHECKLIST A2 为准） | 文档层面已知差异，随下次触碰相应文档时顺带修正；不单独开批 |

### 21.4 提交记录（D10）

| 项 | 值 |
|---|---|
| 实现原子提交 | **`15f608a`** `feat(P-046a): 组合优化语义修复——约束投影 + 协方差单一入口`（14 files，+3263/−240） |
| 白名单核对 | 4 源（portfolio/config/engine_v2/diagnostics）+ 3 新测试 + 2 既有测试（语义修正）+ 4 文档 + PROGRESS；零 diff 面全部不在提交内 ✅ |
| 终审文档提交 | 本节 + CHECKLIST D10 回填 + PROGRESS §3.55.3 + dev log（第二步提交） |
| CI 四 job | 提交为本地 master；**push 与 CI 触发未执行**（用户授权范围 = 终审 + 提交；push 须另行确认） |

### 21.5 终审结论

**PASS（有登记）**：P1/P2 清零，3 项 P3 微偏差均为「诊断消息/文档口径」级别、行为面已由测试与 E2 取证固化，处置全部登记至 P-046b 入口。ADD 循环收敛，P-046a 批次验收通过。
