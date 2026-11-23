# RESEARCH：P-046c F2 收尾（矩阵式凯利 + 非等风险预算 + F2 约束缺口）

> **批次**: P-046c · **T1**（`core/portfolio.py` 求解器扩展 / `core/sizing.py` 凯利语义 / `core/config.py` 嵌套配置 / 视裁决而定 `core/engine_v2.py` 可选上下文；BL/HRP 已闭，本批全部 **opt-in**）
> **上游**: [P-046a RESEARCH](RESEARCH_p046_portfolio_optimization.md)（G-P046-4 / G-P046-7 / G-P046-8 / G-P046-9）；[P-046b DESIGN](DESIGN_p046b_bl_hrp.md)（N1 / N3 显式延后）；[P-047 DESIGN](DESIGN_p047_position_sizing.md)（F-S8-P047-2 对角近似与矩阵式归属）；[主计划](UPGRADE_MASTER_PLAN.md)（F2 §1.2 L180 / 关键路径 L277）；[PROGRESS](PROGRESS.md)（P-046c 行）
> **状态**: **Step 1 调研落盘（2026-11-23，DeepSeek-V4.1-Flash）+ Step 2 异构复审 PASS（2026-11-23，GLM-5.3-Flash ≠ 作者；0 P1/P2 + 4 P3 当轮全修 + 2 观察，[REVIEW_p046c_step2](REVIEW_p046c_step2_research.md)）**；零代码变更 / 未提交；下一步 Step 3 DESIGN（U7/U9 建议先裁决）
> **基线读数（@`3495683`，P-046b 关闭，Step 10 独立复跑）**: pytest collect **1464**（**1463 passed + 1 skipped**）/ `-k p046` **78** / `-k golden` **22（零重录）** / `-k p054` **120** / mypy **160 files · 0** / black `--check .` **322** / AST `except Exception` core 外 **22** / core **30** / `lint-imports` **3 kept** / `uv lock --check` **0** / `tests/*.py` **158** · `core/*.py` **51** · `live/**/*.py` **19** · `services/*.py` **13**

---

## 0. 本文定位

本文只回答「P-046c 要解决什么、现状证据是什么、可选方案与代价是什么、哪些必须裁决」，**不写设计与代码**。所有代码事实带文件 + 行号；所有外部包锚点为本轮从 wheel 源码逐行读取；数值结论均带可重放探针读数（§15）。

---

## 1. 触发与题干

### 1.1 触发

1. **主计划关键路径已清零**：[UPGRADE_MASTER_PLAN L277](UPGRADE_MASTER_PLAN.md) 的 `P-042→043→044→045/046/047→059→048→050→051→052→053→054→055` 已全部关闭；P-046b（BL/HRP）于 2026-11-23 关闭（§3.95/§3.96）。
2. **F2 口径未全交付**：主计划 F2 要求「BL / HRP / **最大夏普** / 约束优化（**换手 L1、个股/行业上限、跟踪误差**）」（[L180](UPGRADE_MASTER_PLAN.md)）。P-046b 显式延后了 N1（行业/换手/跟踪误差）与 N3（max_sharpe），`core/portfolio.py` 对四者 **0 消费**（§2/§3）。
3. **两个 L3 遗留项**：P-047 把矩阵式凯利与非等风险预算转入 P-046c（[DESIGN_p047 L121/L328](DESIGN_p047_position_sizing.md)；[PROGRESS L187/L195](PROGRESS.md)）；现仓 `RiskParityOptimizer` **无预算参数**（§2）。
4. **Step 1 新发现（P1）**：现有 `RiskParityOptimizer` 在等权起点出现负风险贡献时**静默 break 并返回等权**，对合法 PSD 协方差产生非风险平价组合且零诊断（§4 E1）。该缺陷同时阻断「非等风险预算」扩展，必须先裁决。

### 1.2 题干（本批要回答）

- **Q1**：矩阵式凯利 `f=Σ⁻¹μ` 落在哪一层（`portfolio.py` 新优化器 vs `sizing.py` 矩阵方法），如何保证长多、约束与数值稳定？
- **Q2**：非等风险预算（budget 向量 `b`）用何种求解器（cvxpy log-barrier vs 乘性迭代），如何与既有 `RiskParityOptimizer` 语义/数值兼容？
- **Q3**：F2 的 max_sharpe / 行业上限 / 换手 L1 / 跟踪误差四项，本批实现哪些、延后哪些、死配置如何处置（零悬空）？

### 1.3 范围与非目标

| 做 | 不做 |
|---|---|
| 风险预算求解（含修复既有 ERC 静默退化） | 重做 BL / HRP（P-046b 已闭） |
| 矩阵式凯利（opt-in，长多 + 约束） | 多阶段 DP / `PortfolioPolicy`（P-046c 题干外） |
| max_sharpe（opt-in，Charnes-Cooper） | 行业/换手/跟踪误差若需新引擎上下文，显式延后并登记（见 §11） |
| 死配置 `industry_max_weight` 的明确去向 | 删除 `round_lot` / `round_lot_optimize`（P-053 归属，§2.3） |
| 测试 + 门禁 | 新运行时依赖（pypfopt/skfolio/riskfolio 仅手工对拍） |

---

## 2. 代码事实基线（@`3495683`）

### 2.1 优化器与求解器

| # | 事实 | 证据 |
|---|---|---|
| C1 | `OptimizerConfig` 现有方法：`equal_weight` / `min_variance` / `mean_variance` / `mvo` / `risk_parity` / `black_litterman` / `bl` / `hrp`；**无 kelly / max_sharpe** | [portfolio.py L881-L903](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L881-L903)；[config.py L322](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L322) |
| C2 | `RiskParityOptimizer` 为乘性迭代：`w_new = w · mean(RC)/RC`；**无 budget 参数**；`np.any(risk_contrib <= 0)` 时**直接 break**（无 message / warning） | [portfolio.py L717-L794](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L717-L794)，关键 break L749-L750 |
| C3 | `RiskParityOptimizer` 仅在 `portfolio_variance <= 0` 时置 `zero_vol`；负风险贡献 break **不置**任何诊断 | [portfolio.py L738-L750](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L738-L750)、L762-L794 |
| C4 | `BlackLittermanOptimizer` 已共享 `_solve_mean_variance`；`_upper_result` 仅 MVO/BL/HRP 消费；`MinVarianceOptimizer` 零改动 | [portfolio.py L520-L586](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L520-L586)、L589-L650、L685-L714 |
| C5 | 全仓 `core/` 无 `max_sharpe` / `tracking_error`；`industry_max_weight` 在 `portfolio.py` 零消费 | 本轮 `Grep core/` 取证；[config.py L325](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L325) |
| C6 | `round_lot_optimize` 仅定义、零调用（全取整为 0 时除零返回 NaN） | [portfolio.py L849-L878](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L849-L878)；P-046a D-3 归属 P-053 |
| C7 | `cov_shrinkage` 字段保留但**零消费**（P-046a 已标 deprecated） | [config.py L340](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L340)；P-046a D-3/D-7 |

### 2.2 Sizing 与凯利

| # | 事实 | 证据 |
|---|---|---|
| C8 | `kelly_fraction_scale` 为**逐标的对角近似** `f* = μ/σ²`，`scale = clip(fraction·f*, 0, 1)`；负 μ → 0 | [sizing.py L180-L197](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L180-L197) |
| C9 | `apply_sizing(method="kelly")` 需要 `codes` + `cov` + `expected_returns`，逐标的缩放后**不做组合层归一**（仅总权重 >1 时等比缩放） | [sizing.py L243-L359](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L243-L359) |
| C10 | `method="risk_parity"` 在 sizing 层**只输出诊断**（`rc_pct=...`），权重不变（U-P047-2） | [sizing.py L306-L311](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L306-L311) |
| C11 | `risk_contributions` 为有符号贡献 `RC_i = w_i(Σw)_i/σ_p`，`pct=RC/σ_p`；负贡献时 pct 可为负 / >1 | [sizing.py L223-L235](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L223-L235) |

### 2.3 配置、接口与引擎输入

| # | 事实 | 证据 |
|---|---|---|
| C12 | `OptimizerConfig` 字段：`industry_max_weight`（L325）/ `round_lot`（L326）/ `cov_shrinkage`（L340）；`__post_init__` 仅校验 max/min/target_count | [config.py L311-L358](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L311-L358) |
| C13 | `round_lot` **不是死配置**：引擎在 `build_target_positions(..., round_lot=self.cfg.optimizer.round_lot)` 消费 | [engine_v2.py L1508-L1517](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1508-L1517) |
| C14 | `IOptimizer` Protocol 仍为 **2 参** `optimize(signals, returns_data=None)`；引擎实际调用 `optimize_with_diagnostics(factor_scores, returns, cov)` **3 参** | [interfaces.py L231-L249](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L231-L249)；[engine_v2.py L1366-L1368](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1366-L1368) |
| C15 | 引擎 optimizer 输入仅 `returns_data`（lookback 不含当日）+ `cov_matrix`（单一入口）；**不传行业、基准、上一期权重** | [engine_v2.py L1350-L1368](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1350-L1368) |
| C16 | 行业数据**已加载且可用**：`DataManager.industry`（日期 × 股票）；engine 仅用于过滤/中性化，未传给 optimizer | [data.py L164-L169](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L164-L169)、L383；[filter/industry.py L64-L166](file:///f:/Coding/Factor_Trading_v3.0/filter/industry.py#L64-L166) |
| C17 | `BacktestConfig.benchmark` 为 **「暂留接口」** 字符串，无基准收益/权重数据加载 | [config.py L455](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L455) |
| C18 | `config_v2.py` 为冻结资产：**生产代码零引用**，仅 `tests/test_config_v2.py` 使用；`industry_max_weight` / `cov_shrinkage` 同名字段存在 | [config_v2.py L13](file:///f:/Coding/Factor_Trading_v3.0/core/config_v2.py#L13)、L128、L137、L143 |
| C19 | 现有测试对 risk_parity 只断言 **无 NaN / Σw=1 / 约束**，**无风险贡献相等断言**，且无负相关用例 | [test_p046_constraints.py L21](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p046_constraints.py#L21)、L85-L92 |
| C20 | `build_target_positions` 已承担整手落地；`round_lot` 属其参数，不属 optimizer | [target_positions.py L49-L50](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L49-L50)、L131-L132 |

---

## 3. 缺口清单 G-P046c-1..10

| ID | 缺口 | 级别 | 影响 | 归属 |
|---|---|---|---|---|
| **G-P046c-1** | **ERC 静默退化**：等权起点任一 `RC<=0` → break 返回等权，零诊断；合法 PSD 负相关协方差即触发 | **P1** | 风险平价名不符实；风险预算扩展无基础 | P-046c 必修 |
| **G-P046c-2** | 非等风险预算缺失：`RiskParityOptimizer` 无 `budget` 参数；乘性迭代直接扩展会产生负权重（§4 E2） | P2 | L3-2 未交付 | P-046c |
| **G-P046c-3** | 矩阵式凯利缺失：仅对角 `μ/σ²`；`Σ⁻¹μ` 长多不可直接用（负权重、病态） | P2 | L3-1 未交付 | P-046c |
| **G-P046c-4** | max_sharpe 缺失（N3 延后） | P2 | F2 未全交付 | P-046c |
| **G-P046c-5** | 行业上限死配置：`industry_max_weight` 零消费；引擎有行业数据但不传入 optimizer | P2 | F2 未全交付 + 死配置 | P-046c 裁决（实现 / 延后 P-046d） |
| **G-P046c-6** | 换手 L1 缺失：optimizer 无上一期权重输入 | P3 | 换手控制不可用 | 延后 P-046d（需 `OptimizationContext`） |
| **G-P046c-7** | 跟踪误差缺失：无基准权重/收益；`cfg.benchmark` 为占位字符串 | P3 | TE 约束不可用 | 延后 P-046d / P-058 |
| **G-P046c-8** | `OptimizationContext` 缺失：行业/上期权重/基准均无统一输入通道 | P2 | 约束扩展的架构前置 | P-046d（若 P-046c 不做行业上限） |
| **G-P046c-9** | 死配置/死函数归属不清：`industry_max_weight`（P-046b→P-046c）、`cov_shrinkage`（deprecated）、`round_lot`（P-053，实际消费）、`round_lot_optimize`（P-053，零调用） | P3 | 技术债残留 | P-046c 只处置 `industry_max_weight`；其余按 P-046a D-3 / P-053 |
| **G-P046c-10** | 测试缺口：无负相关 ERC、无预算向量、无矩阵凯利/max_sharpe、无死配置效力断言 | P2 | 回归无保护 | P-046c |

---

## 4. 数值取证 E1-E7（可重放，§15）

### E1（P1）现有 ERC 静默退化

**两资产闭式例**：`σ=[0.2,0.3]`，`ρ=-0.9`，协方差特征值 `[0.0054936978, 0.1245063022]`（PSD）。

| 项 | 读数 |
|---|---|
| 现有 `RiskParityOptimizer` 权重 | `[0.5, 0.5]`（等权） |
| 现有 RC 占比 | `[-0.636364, 1.636364]` |
| 诊断 | `message=""`，`warning_kind=None`（**无任何提示**） |
| 解析 ERC | `[0.6, 0.4]`（两资产 ERC 权重 ∝ 逆波动率） |
| 与解析解偏差 | **0.10** |
| cvxpy log-barrier 参考解 | `[0.6, 0.4]`，RC `[0.499993, 0.500007]` |

**五资产随机 SPD（seed=1）**：现有 `[0.2,0.2,0.2,0.2,0.2]`；真 ERC `[0.200212,0.401383,0.278986,0.074362,0.045056]`；**max|diff|=0.2014**。

**根因**：[portfolio.py L749-L750](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L749-L750) 在等权起点检测到负 RC 即 break，返回初值；无任何 `message/warning_kind`。

### E2 非等风险预算：求解器选择

`b=[0.4,0.3,0.15,0.1,0.05]`，同一 5×5 SPD：

- **cvxpy log-barrier**（`bᵀ log w ≥ 0, w≥0`）：`w=[0.225442,0.422340,0.287002,0.034918,0.030297]`，RC `[0.400057,0.299957,0.149971,0.099988,0.050028]`，**max|RC−b|=5.67e-05**。
- **乘性迭代直接扩预算**：`w=[1.514333,-1.517127,0.689956,0.382551,-0.069712]`——RC 精确但**负权重**（长空），不能用于股票长多。
- **性能**（cvxpy，uniform b）：N=50 **0.018-0.136s** / N=200 **0.127-0.348s** / N=500 **0.913-0.964s**（RC 误差 ≤1e-6；**单次测量、机器相关，仅量级参考**——F-R2-3）。

### E3 矩阵凯利：对角 vs 矩阵，条件数与长多

5 资产（μ=[0.08,0.06,0.05,0.04,0.03]）：

- 对角 `μ/σ²` 归一：`[0.293267,0.392354,0.199011,0.108469,0.006899]`。
- 矩阵 `Σ⁻¹μ` 裁剪负值后归一：`[0.191994,0.430071,0.364948,0.0,0.012987]`；**max|diag−matrix_clip|=0.165937**。
- 50 资产（seed=7）：`cond(Σ)=3.78e3`；原始 `Σ⁻¹μ` **max|w|=13.36、22 个负权重**。
- Ledoit-Wolf 收缩后：`cond=12.9`，但 `max|w|=1996.41`、10 个负权重（μ 与小特征方向对齐）。
- 岭 α=1e-2：`cond=3.29e2`、`max|w|=1.69`、仍有 15 个负权重。
- **结论**：矩阵凯利必须用**长多 QP/约束**（如 `max μᵀw − (1/(2f))wᵀΣw`，`w≥0, Σw=1, w≤max_weight`），不能直接逆矩阵归一。

### E4 max_sharpe：Charnes-Cooper 变换与 pypfopt 对拍

5 资产，`rf=0.02`，`w≤0.6`：

- cvxpy 变换解：`[0.164545,0.478144,0.345451,0.0,0.011859]`，Sharpe **1.38575528**。
- **pypfopt 1.5.5 `max_sharpe` 逐位一致：max|diff|=5.55e-17**。
- 无箱体时与闭式 `Σ⁻¹(μ−rf)` 归一 max|diff|=1.94e-16。
- 暴力 Dirichlet 采样（20 万）最优 1.38071117（低于精确解 5.04e-03，采样次优，符合预期）。

### E5 行业上限：solver 内 vs 后投影

5 资产、3 行业（`[0,0,1,1,2]`）、`cap=0.4`：

- **solver 内**组和 `[0.4,0.4,0.2]`（精确 ≤ cap）。
- **先求解后「截断+归一」**组和 `[0.515420,0.473385,0.011194]`——**0.5154 > 0.4，违反上限**。
- **结论**：行业上限必须进入 solver（或做严格投影），后投影不成立。

### E6 死配置效力

`RiskParityOptimizer` 在 `industry_max_weight=None` vs `0.2` 下权重 **max|diff|=0.00e+00**——字段完全无效。

### E7 修复 ERC 的数值漂移与性能

- 正相关等相关（ρ=0.3，vols 0.2-0.4）：现有 `[0.282638,0.226110,0.188425,0.161507,0.141319]` vs cvxpy `[0.282643,0.226110,0.188422,0.161503,0.141321]`，**max|diff|=5.37e-06**，RC 均精确 0.2。
- 60×20 随机收益样本协方差：现有与 cvxpy 权重 **max|diff|=0.0000**，RC 均 0.05。
- **结论**：把求解器替换为「快速乘性路径 + 负 RC/非均匀预算/不收敛时 cvxpy 回退」可做到**对现有行为零漂移**（快速路径即原实现）且异常路径修复；与 cvxpy 参考解之差为 5.37e-06（E7 equicorr，非漂移，F-R2-1）。纯 cvxpy 路径 N=500 约 0.9-1.0s/日（单次测量、机器相关，F-R2-3），需在设计期裁决性能预算。

---

## 5. 外部证据锚点

### 5.1 A 级（本轮从 wheel 源码逐行读取）

| ID | 包/版本 | 位置 | 关键内容 | 用途 |
|---|---|---|---|---|
| **A1** | pypfopt **1.5.5** | `pypfopt/efficient_frontier/efficient_frontier.py` L225-L293 | `max_sharpe`：变量变换、`(μ−rf)ᵀw=1`、`Σw=k`、约束按 k 缩放、`w=y/k`；源码引用 Cornuejols & Tutuncu (2006) | max_sharpe 设计 |
| **A2** | pypfopt 1.5.5 | 同文件 L332-L378 | `efficient_risk`：`variance <= target_variance` 参数化约束；最小波动下界校验 | 波动目标语义 |
| **A3** | pypfopt 1.5.5 | `pypfopt/objective_functions.py` L168-L226 | `transaction_cost = k·‖w−w_prev‖₁`；`ex_ante_tracking_error=(w−w_b)ᵀΣ(w−w_b)`；`ex_post_tracking_error` | 换手/跟踪误差口径 |
| **A4** | pypfopt 1.5.5 | `pypfopt/risk_models.py` L356 / L418 / L438 | `CovarianceShrinkage`、`shrunk_covariance`、`ledoit_wolf` | 矩阵凯利收缩选项 |
| **A5** | skfolio **1.14.4** | `skfolio/optimization/convex/_risk_budgeting.py` L27-L44、L95-L101 | 风险预算凸问题：`min Risk(w) s.t. budgetᵀlog(w) ≥ 0, 1ᵀw=s, Aw≤s·b, w≥0`；`risk_budget=None` → 等风险 | 预算 ERC 求解器 |
| **A6** | skfolio 1.14.4 | `skfolio/optimization/convex/_mean_risk.py` L792-L905、L1106-L1109 | `MeanRisk` 的 `risk_aversion` 与 `MAXIMIZE_RATIO`（max Sharpe）分支 | 凯利/夏普参数化 |
| **A7** | riskfolio-lib **7.4.1** | `riskfolio/src/Portfolio.py` L3465-L3493、L4315-L4335 | `rp`：`b` 风险贡献目标、`bᵀlog(w)≥c`、`Aw≤b`；实现用 `ExpCone` 等价的 log 约束 | 预算 ERC 第二参考 |

### 5.2 B 级（书目级；本轮未取全文，不用于实现关键断言）

| ID | 文献 | 用途 |
|---|---|---|
| **B1** | Kelly, J. L. (1956). *A New Interpretation of Information Rate*. Bell System Technical Journal 35(4): 917-926. | 凯利准则原始定义 |
| **B2** | Thorp, E. O. (2006/2008). *The Kelly Criterion in Blackjack Sports Betting and the Stock Market*. Handbook of Asset and Liability Management. | 连续时间/分数凯利 `f*=Σ⁻¹μ` |
| **B3** | Maillard, S., Roncalli, T., Teïletche, J. (2010). *The Properties of Equally Weighted Risk Contribution Portfolios*. Journal of Portfolio Management 36(4). | ERC 性质与解存在性 |
| **B4** | Roncalli, T. (2013). *Introduction to Risk Parity and Budgeting*. Chapman & Hall/CRC. | 风险预算向量 `b` 与 log-barrier 形式 |
| **B5** | Michaud, R. O. (1989). *The Markowitz Optimization Enigma: Is "Optimized" Optimal?* FAJ 45(1). | 矩阵逆的估计误差放大 |
| **B6** | Jagannathan, R., Ma, T. (2003). *Risk Reduction in Large Portfolios: Why Imposing the Wrong Constraints Helps*. Journal of Finance 58(4). | 约束作为收缩、长多约束的必要性 |
| **B7** | DeMiguel, V., Garlappi, L., Uppal, R. (2009). *Optimal Versus Naive Diversification*. Review of Financial Studies 22(5). | 1/N 基准与估计误差 |
| **B8** | Cornuejols, G., Tutuncu, R. (2006). *Optimization Methods in Finance*. | max_sharpe 凸变换（pypfopt 源码 L230-L231 直接引用） |

> **口径**：A 级 = 本轮逐行读取 wheel 源码；B 级 = 标准书目，未本轮全文核验，不得单独支撑实现决策（实现决策至少需 A 级 + 本地探针双证）。

---

## 6. 方案矩阵

### 6.1 风险预算与 ERC 修复（G-P046c-1/2）

| 方案 | 内容 | 优点 | 代价 |
|---|---|---|---|
| **B1a** | 原地替换 `RiskParityOptimizer` 为「快速乘性路径 + 回退」；**回退触发 = 负 RC、非均匀预算、或 max_iter 内 RC 未达 tol**（现有代码对该情形同样静默返回末次 w，F-R2-4） | **对现有行为零漂移**（快速路径即原实现；与 cvxpy 参考差 5.37e-06，E7）；异常路径（含静默不收敛）修复；一个类 | 求解器分支增加复杂度；N=500 最坏 ~0.9-1.0s（单次测量，F-R2-3） |
| B1b | 新建 `RiskBudgetOptimizer`（method=`risk_budget`），旧 RP 只加诊断不修 | 零行为变更 | 旧 RP 仍错（P1 未修）；两个类语义重叠 |
| B1c | 全部改 cvxpy log-barrier（无快速路径） | 实现最简单 | 正常路径 ~0.9s/日（N=500），性能退化 |

**建议**：**B1a**。默认 `budget=None` → 等预算；`budget` 归一校验、非负、与 `selected` 交集；负 RC 时走 cvxpy 并置诊断（如 `fallback="convex_erc"`），不静默。

### 6.2 矩阵凯利（G-P046c-3）

| 方案 | 内容 | 优点 | 代价 |
|---|---|---|---|
| **B2a** | 新建 `KellyOptimizer`（method=`kelly`），复用 `_solve_mean_variance(expected_returns, cov, ..., risk_aversion=1/fraction)` | 复用 P-046b 求解器；长多/箱体/upper 语义一致；代码少 | 需给 `_solve_mean_variance` 增可选 `risk_aversion` 覆盖 |
| B2b | 在 `sizing.py` 增 `method="kelly_matrix"`，组合层缩放 | 不新增优化器 | sizing 层无箱体/不可行语义；与 portfolio 层重复 |

**建议**：**B2a**；`KellyConfig(fraction=0.5)` 嵌套；μ 用 `returns.mean()`（与 MVO 同源）；默认 opt-in。P-047 对角 `kelly` 行为**不变**（sizing 层零改动）。**命名消歧提醒（F-R2-5 观察）**：`OptimizerConfig.method="kelly"`（拟新增）与 `SizingConfig.method="kelly"`（P-047 对角）同名不同层；且 portfolio.py 已有 `budget` 一词（`_scale_to_budget` 权重预算语义）与新「风险预算」撞词——Step 3 须在 docstring/文档中显式声明层次与语义。

### 6.3 max_sharpe（G-P046c-4）

| 方案 | 内容 | 优点 | 代价 |
|---|---|---|---|
| **B3a** | 新建 `MaxSharpeOptimizer`，Charnes-Cooper 变换 + `_apply_constraints` 的 k 缩放版本 | 与 pypfopt 逐位对拍（E4 5.55e-17）；复用 upper/empty 语义 | 需实现约束缩放与 k 退化处理 |
| B3b | 用 MVO 网格搜索风险厌恶逼近 | 复用现有 | 非精确、慢、不可断言 |

**建议**：**B3a**；`MaxSharpeConfig(risk_free_rate=0.0)`；`max(μ) <= rf` → `ValueError`（pypfopt L244-L247 同口径）；upper 型（n×max<1）→ `_upper_result`（留现金，与既有 U1-A 一致）。

### 6.4 行业上限 / 换手 / 跟踪误差（G-P046c-5/6/7/8）

| 方案 | 内容 | 结论 |
|---|---|---|
| B4a | P-046c 内实现行业上限（给 `optimize_with_diagnostics` 增可选 `industry`，引擎传 `dm.industry.loc[date]`；solver 内加组约束） | 可行（E5 精确），但需改接口/引擎/全部优化器约束路径；scope 扩 |
| **B4b** | 本批**显式延后**行业/换手/TE 到 **P-046d**（`OptimizationContext`：industry + prev_weights + benchmark），同时把 `industry_max_weight` 从 `core/config.py` 移除或标 deprecated（`config_v2` 冻结例外） | 建议；P-046c 聚焦求解器侧，P-046d 做上下文侧，避免同批双扩 |
| B4c | 只对 cvxpy 优化器实现行业上限，EW/RP/HRP 跳过并 warning | 语义不统一，不建议 |

**建议**：**B4b**，并在 PROGRESS 新建 **P-046d** 行（F2 上下文侧）承接行业/换手/TE；P-046c 内把 `industry_max_weight` 处置为「删除（config.py）+ config_v2 冻结例外声明」或「保留 deprecated + P-046d 接线」二选一（U-P046c-7）。

> **补充调研修订（2026-11-23）**：U7 改为 **B4d**——**行业上限本批实现（引擎级严格投影，E8 500 资产 0.022s 精确；E12 改动面 1 vs 7）**，换手 L1 / 跟踪误差延后 P-046d（换手需进入目标函数、TE 缺基准数据）；U9 改为 **保字段 + 接线消费（首选）**。证据与社区锚点见 [RESEARCH_p046c_u7_u9_supplement](RESEARCH_p046c_u7_u9_supplement.md)。

### 6.5 死配置归属（G-P046c-9）

| 字段/函数 | 归属 | P-046c 动作 |
|---|---|---|
| `industry_max_weight` | P-046b 延后 → P-046c/P-046d | 删除（仅 `core/config.py`，`config_v2` 冻结例外）或保留 deprecated 并指向 P-046d |
| `cov_shrinkage` | P-046a D-3/D-7（deprecated，零消费） | **不动**（删除会破坏旧 JSON 反序列化；P-046a 已裁决） |
| `round_lot` | P-053（引擎实际消费，C13） | **不动** |
| `round_lot_optimize` | P-053（零调用，C6） | **不动**（P-046a D-3 已归属） |

---

## 7. 不变式 I-P046c-1..10

| ID | 不变式 | 验证 |
|---|---|---|
| I1 | 默认 `equal_weight` 路径与 golden 22 **零漂移**（零重录） | 全量 + golden |
| I2 | 修复后 ERC：负相关两资产例返回 `[0.6,0.4]`（±1e-6），RC 偏差 <1e-4；不得再静默等权 | 新用例 |
| I3 | 预算 `b` 非负、sum>0、与 selected 对齐；RC 比例与 `b` 误差 <1e-3 | 新用例 + 闭式 |
| I4 | 矩阵凯利长多权重非负、`Σw≤1`、无 NaN；无约束时与 `Σ⁻¹μ` 归一 <1e-10 | 新用例 |
| I5 | max_sharpe 与 pypfopt 1.5.5 在箱体下 **<1e-10**；无箱体与闭式 <1e-10 | 对拍用例 |
| I6 | 行业上限若实现，必须 solver 内生效（组和 ≤cap+1e-9）；不得后投影冒充（E5 反例） | 新用例 |
| I7 | 换手/TE 若延后，必须有 PROGRESS 行 + 明确触发条件（零悬空） | 台账核对 |
| I8 | 零新运行时依赖；pypfopt/skfolio/riskfolio 仅手工对拍、不进 CI | `git status` + grep |
| I9 | 门禁不劣化：1463+1 / 78 / 22 / 120 / 160·0 / 322 / 22·30 / 3 kept / 0 / 158·51·19·13 | 全量 |
| I10 | `config_v2.py` FROZEN 零 diff（若删 `industry_max_weight`，只改 `core/config.py` 并声明冻结例外） | `git status` |

---

## 8. DoD（A-P046c-1..10）

| ID | 交付判据 |
|---|---|
| A1 | 修复 ERC 静默退化：负相关两资产 + 五资产随机 SPD 用例通过；诊断字段非空 |
| A2 | 预算 ERC：`budget` 配置 + 求解器；RC 比例误差 <1e-3；与 skfolio/riskfolio 口径对照 |
| A3 | 矩阵凯利：`KellyOptimizer`（opt-in），长多/箱体/upper/empty 语义与既有优化器一致；P-047 对角行为不变 |
| A4 | max_sharpe：`MaxSharpeOptimizer`（opt-in），与 pypfopt 1.5.5 对拍 <1e-10 |
| A5 | 行业/换手/TE 处置：实现或**显式延后**（P-046d 行 + 触发条件 + 验收口径），零悬空 |
| A6 | 死配置：`industry_max_weight` 有明确去向；`cov_shrinkage`/`round_lot`/`round_lot_optimize` 按归属不动 |
| A7 | 新增测试覆盖：负相关 ERC、预算向量、矩阵凯利、max_sharpe、死配置效力（≥20 例，具体数 Step 3 冻结） |
| A8 | golden 22 零重录；全量 1463 + 新增 passed；`-k p046` / `-k p054` 不回归 |
| A9 | mypy 160·0 / black 322 / AST 22·30 / lint 3 kept / uv lock 0 / 文件计数不劣化 |
| A10 | 四文档 + 台账；Step 10 异构终审 0 P1 |

---

## 9. 基线 / 目标读数

| 指标 | 基线 @`3495683` | Step 1 目标（Step 3 冻结） |
|---|---|---|
| pytest | 1464 collect / 1463 passed + 1 skipped | +N（A7，Step 3 冻结） |
| `-k p046` | 78 | ≥78（不改既有） |
| `-k golden` | 22（零重录） | 22（零重录） |
| `-k p054` | 120 | 120 |
| mypy | 160·0 | 160·0（不新增文件） |
| black | 322 | 322（不新增文件） |
| AST | 22 / 30 | 22 / 30 |
| lint / lock | 3 kept / 0 | 3 kept / 0 |
| 文件计数 | 158·51·19·13 | 158·51·19·13（不新增模块；若新增则登记） |

---

## 10. 未决项 U-P046c-1..12

| ID | 未决项 | 建议默认 | 需用户/Step 3 裁决 |
|---|---|---|---|
| U1 | ERC 修复方式：原地替换 vs 新建类 | **原地替换 + 快速路径/回退**（B1a） | 是 |
| U2 | `budget` 配置形态：`dict[str,float]` vs `Sequence[float]` | `dict[str,float]`，缺失补 1/N、多余丢弃 warning | 是 |
| U3 | 矩阵凯利归属：`portfolio` 新优化器 vs `sizing` | **`KellyOptimizer`（B2a）** | 是 |
| U4 | 凯利 fraction 语义：`risk_aversion=1/f` vs 独立缩放 | `risk_aversion=1/fraction`（与 MVO 同源） | 是 |
| U5 | max_sharpe 无风险利率来源：`MaxSharpeConfig` vs `BacktestConfig.risk_free_rate` | 嵌套 `MaxSharpeConfig(risk_free_rate=0.0)` | 是 |
| U6 | max_sharpe upper（n×max<1）语义 | `_upper_result` 留现金（U1-A 一致） | 是 |
| U7 | 行业/换手/TE：本批实现 vs 延后 P-046d | **B4d（补充调研修订）**：行业上限本批（引擎级严格投影）；换手/TE 延后 P-046d（[补充调研](RESEARCH_p046c_u7_u9_supplement.md)） | **已裁决（2026-11-23）：B4d** |
| U8 | 换手/TE 数据来源与 API 形态 | P-046d 的 `OptimizationContext`（industry/prev_weights/benchmark） | 是（P-046d） |
| U9 | `industry_max_weight`：删除 vs 保留 deprecated | **保字段 + 接线消费（首选）**；若 U7 延后则 deprecated + warning，不删除（[补充调研](RESEARCH_p046c_u7_u9_supplement.md)） | **已裁决（2026-11-23）：保字段 + 接线** |
| U10 | ERC 求解器性能预算：纯 cvxpy vs 混合 | 混合（正常路径乘性、异常 cvxpy） | 是 |
| U11 | 诊断载体：复用 `message/warning_kind` vs 新字段 | 复用 `message` + 既有诊断；不新增枚举 | 是 |
| U12 | 对拍是否仅在本地（pypfopt/skfolio/riskfolio 不进 CI） | 仅本地手工对拍（Q7/I8） | 否（既定） |

---

## 11. 遗留项处置表（F2 缺口，零悬空）

| 项 | 现状 | P-046c 处置 | 后续 |
|---|---|---|---|
| BL / HRP | 已交付（P-046b） | 不动 | — |
| max_sharpe | 缺失（N3） | **实现**（B3a） | — |
| 行业上限 | 死配置（`industry_max_weight`） | **本批实现（B4d 引擎级严格投影）**，字段接线消费 | 换手/TE 仍归 P-046d |
| 换手 L1 | 缺失（无 prev weights） | **延后 P-046d** | P-046d |
| 跟踪误差 | 缺失（无基准数据） | **延后 P-046d** | P-046d / P-058 |
| 矩阵凯利 | 缺失（L3-1） | **实现**（B2a） | — |
| 非等风险预算 | 缺失（L3-2） | **实现**（B1a） | — |
| ERC 静默退化 | **P1 缺陷** | **修复**（B1a） | — |
| `cov_shrinkage` | deprecated 零消费 | 不动（P-046a D-3/D-7） | — |
| `round_lot` / `round_lot_optimize` | 前者引擎消费、后者零调用 | **不动**（P-053 归属） | P-053 |

> 若 U7 裁决为「P-046c 内实现行业上限」，则 B4a 替代 B4b，P-046d 仅承接换手/TE；scope 与测试数相应上调。

> **补充调研后的实际建议（2026-11-23）**：行业上限采用 **B4d 引擎级严格投影**（非 B4a in-solver、非 B4b 全延后）；换手/TE 延后 P-046d。详见 [RESEARCH_p046c_u7_u9_supplement](RESEARCH_p046c_u7_u9_supplement.md)。

---

## 12. 步骤表（Step 1-10）

| Step | 内容 | 产出 |
|---|---|---|
| 1 | 调研（本文） | RESEARCH + 缺口/方案/未决/DoD |
| 2 | 异构复审 | REVIEW_p046c_step2_research.md |
| 3 | DESIGN | DESIGN_p046c_f2_closeout.md（D/I/AC/门禁） |
| 4 | DESIGN 异构复审 | REVIEW_p046c_step3_design.md |
| 5 | IMPL | IMPL_p046c_f2_closeout.md（T1-TN / 签名 / 锚点 / 红→绿） |
| 6 | IMPL 异构复审 | REVIEW_p046c_step5_impl.md |
| 7 | CHECKLIST | CHECKLIST_p046c_f2_closeout.md（A-H 组） |
| 8 | 一致性复审 | 机械校验器 |
| 9 | TDD | 红→绿 + 门禁 |
| 10 | ADD 审计 + RULE-5 异构终审 | 审计报告 + 提交授权 |

---

## 13. Step 2 复审包（给 reviewer 的最小核对清单）

1. **代码事实**：C1-C20 的文件 + 行号是否逐一命中；`RiskParityOptimizer` 的 break 语义是否如 E1 所述。
2. **P1 判定**：E1 两资产闭式例是否可独立复现（`[0.5,0.5]` vs `[0.6,0.4]`，RC `[-0.636,1.636]`）；是否同意 P1。
3. **数值**：E2-E7 是否可重放；bootstrap 种子/矩阵是否明示；pypfopt 对拍是否 5.55e-17。
4. **外部锚**：A1-A7 的包/版本/行号是否与 wheel 一致；B1-B8 是否被误用于实现关键结论。
5. **方案矩阵**：B1a/B2a/B3a/B4b 的取舍理由是否成立；是否有更简方案。
6. **未决项**：U1-U12 是否有必须前置裁决的项（尤其 U7 scope、U1 行为变更、U9 死配置）。
7. **不变式/DoD**：I1-I10 / A1-A10 是否可机械验证；门禁数字是否与 @`3495683` 一致。
8. **范围守卫**：是否夹带 P-046d/P-053/P-046b 重做；是否引入新依赖。

---

## 14. 状态链

- **2026-11-23**：用户「分析下一步任务」→ 选择 **P-046c F2 收尾**；主计划关键路径已清零（P-046b 关闭）。
- **2026-11-23**：**Step 1 调研落盘（本文）**——代码事实 C1-C20 @`3495683`；缺口 G-P046c-1..10（**1 P1 + 5 P2 + 4 P3**）；数值取证 E1-E7（含 ERC 静默退化 P1、预算 ERC、矩阵凯利病态、max_sharpe 与 pypfopt 5.55e-17、行业上限后投影反例、死配置 0 效力、修复漂移 5.37e-06）；外部锚 A1-A7（源码级）+ B1-B8（书目级）；方案 B1a/B2a/B3a/B4b；未决 U1-U12；DoD A1-A10。**零代码变更 / 未提交**。
- **2026-11-23**：**Step 2 异构复审 PASS**（[REVIEW_p046c_step2](REVIEW_p046c_step2_research.md)，**GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash**）——C1-C20 **20/20**；E1-E7 复审者独立重写重放 **7/7**（E1-2A/5A、E2 w/rc、E3、E4、E5、E6、E7 逐位命中；E2 timing 机器相关已加注）；A1-A7 对 wheel **7/7**、B 级无越界；门禁基线独立复跑全命中（collect 1464 / 子集 220 / 全量 **1463+1** / mypy 160·0 / black 322 / AST 22·30 / lint 3 kept / lock 0 / 计数 158·51·19·13）；**0 P1 / 0 P2 / 4 P3 当轮全修**（F-R2-1「零漂移」措辞、F-R2-2 E3/E7 构造补登、F-R2-3 性能单次测量注、F-R2-4 快速路径不收敛回退分支）+ 2 观察（kelly/budget 命名消歧、U2 混合归一与 I4 正权重闭式限定 → Step 3 精化）；**E1 的 P1 判定同意**（两资产 ERC ⟺ `w1σ1=w2σ2` ⟺ 逆波动率，独立推导成立）；**U7 scope 建议（延后 P-046d）认可**。
- **2026-11-23**：**U7/U9 补充调研**（[RESEARCH_p046c_u7_u9_supplement](RESEARCH_p046c_u7_u9_supplement.md)）——输入可得性（行业可得 / prev weights 引擎可得 / benchmark 不可得）；社区锚点（pypfopt `add_sector_constraints` L366-L403、skfolio `groups` L392-L401 + `previous_weights` L301 + `BenchmarkTracker` L24-L58、riskfolio `assets_constraints` L34-L70 + `hrp_constraints` L1595 + `turnover` L113-L115/L3005-L3009）；E8 严格投影 500 资产 0.022s 精确（朴素后处理 +0.0709 违反）；E12 改动面 1 vs 7；**修订 U7→B4d（行业上限本批、换手/TE 延后）、U9→保字段接线**；登记 F-R2-U7-1 / F-R2-U9-1 + 2 观察。
- **2026-11-23**：**用户裁决 U7/U9**（[补充调研 §7](RESEARCH_p046c_u7_u9_supplement.md)）——**U7=B4d**（行业上限本批引擎级严格投影；换手/TE 延后 P-046d）；**U9=保字段 + 接线消费**。U7/U9 关闭，进入 Step 3。
- **2026-11-23**：**Step 2b 定点复审 PASS**（[REVIEW_p046c_step2b](REVIEW_p046c_step2b_u7u9.md)，GLM-5.3-Flash ≠ 补充调研作者）：E8/E11/E12 独立重写重放逐位/精确命中（E8 dev=L2 口径锁定）；社区锚点对 wheel 12/13 + 1 名称修正（riskfolio 实为 `kindbench`）；pydantic deprecated / PEP 702 / 本仓 3.12.11 实测确认；**0 P1/P2 + 3 P3 当轮全修**（F-R2b-1/2/3）+ 1 观察；**裁决维持有效**。
- **2026-11-23**：**Step 3 DESIGN 完成**（[DESIGN_p046c_f2_closeout](DESIGN_p046c_f2_closeout.md)）——U-P046c-1..12 全部关闭；D1-D22 / I1-I12；39 例测试冻结；门禁目标 1503 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13；E4 构型复算逐位命中（Sharpe 1.3857552798）；PROGRESS 新建 P-046d 行。
- **2026-11-23**：**Step 4 异构复审 PASS**（[REVIEW_p046c_step3_design](REVIEW_p046c_step3_design.md)，GLM-5.3-Flash ≠ 作者）——D4 KKT / D10 pypfopt 等价 / 门禁算术（mypy CI 范围不含 tests）独立成立；**1 P2 + 2 P3 当轮全修**（F-4-1 零漂移范围限定 + diag 预判定位为新增防护（部分零方差凸回退病态解 w₃≈2.7e6 新证据）/ F-4-2 伪代码 zero_vol 误判 max_iter / F-4-3 C8-C10 补显式 max_weight）+ 3 观察；门禁目标维持不变。
- **2026-11-23**：**Step 5 IMPL 落盘**（[IMPL_p046c_f2_closeout](IMPL_p046c_f2_closeout.md)）——T1-T9；源码级锚点 A27-A36（skfolio 自由尺度 `factor=cp.Variable()`、riskfolio `k=cp.Variable()`、pypfopt Charnes-Cooper/quadratic_utility、组约束矩阵）；跨实现读数 max_sharpe **5.55e-17**；**新证据：`Σw=1` 与 `bᵀlog w≥0` 对 n≥2 不可行**（F-5-1）；派生 F-5-1..F-5-3；门禁目标不变。
- **下一步**：Step 6 IMPL 异构复审。
- **2026-11-23**：**Step 6 复审 PASS + Step 7 CHECKLIST 落盘**——[REVIEW_p046c_step5_impl](REVIEW_p046c_step5_impl.md)（锚点 16/16、3 P3 全修）；[CHECKLIST_p046c_f2_closeout](CHECKLIST_p046c_f2_closeout.md)（80 项、实测列 0 预填、门禁目标 1503/117/22/120/160·0/325/22·30/3 kept/0/161·51·19·13）。
- **2026-11-23**：**Step 8 一致性复审 PASS**——机械校验器 v3 124/124（初跑 117/124：4 校验器正则/切分误报 + 2 文档 P3 当轮修 + 1 跟随；复跑 122/124：再修 1 连写正则误报 + 1 用例引用缺口当轮修）；J1/J5 回填 ✅；reviewer GLM-5.3-Flash ≠ CHECKLIST 作者 DeepSeek-V4.1-Flash；详见 [CHECKLIST_p046c_f2_closeout §14](CHECKLIST_p046c_f2_closeout.md)。
- **2026-11-23**：**Step 9 TDD PASS**——39 例红→绿（红态 2 收集错误）；门禁全命中 1503（1502+1）/ 117 / 22 / 120 / 160·0 / 325 / 161·51·19·13 / 22·30 / 3 kept / 0；派生 **F-S9-P046c-1**（A6 构型改等相关）；O-4-1 探针：sizing/overlay 腿实测不放大（clip≤1）、外部权重 0.4→0.3 压回；详见 [CHECKLIST_p046c_f2_closeout §15](CHECKLIST_p046c_f2_closeout.md)。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS**（[CHECKLIST_p046c_f2_closeout §16](CHECKLIST_p046c_f2_closeout.md)）——门禁独立重放 10/10 全绿；探针独立重写重放 8/8（R1a 逐位复现本文 §15 E1 原值）；**0 P0-P2 + 1 观察 O-R5-P046c-1**；E1 P1 修复经终审确认闭合。
- **下一步**：用户授权提交（J6）→ 批次关闭。

---

## 15. 附：探针与原始读数（可重放）

环境：`.venv\Scripts\python.exe`（Python 3.12.11 / numpy 2.4.6 / pandas 3.0.3 / scipy 1.17.1 / cvxpy 既有依赖）；外部包：`%TEMP%\p046b_pkgs`（pypfopt 1.5.5 / skfolio 1.14.4 / riskfolio-lib 7.4.1，PyPI wheel）。

关键读数（与 §4 对应）：

```
E1 2A: current [0.5,0.5]; rc [-0.636364,1.636364]; analytic [0.6,0.4]; cvxpy [0.6,0.4] rc [0.499993,0.500007]
E1 5A: current [0.2]*5; true [0.200212,0.401383,0.278986,0.074362,0.045056]; max|diff|=0.2014
E2 budget b=[0.4,0.3,0.15,0.1,0.05]: cvxpy rc max|diff|=5.67e-05; naive w has negatives
E2 timing: N=50 0.136s / N=200 0.348s / N=500 0.913s
E3: diag vs matrix_clip max|diff|=0.165937; 50A cond=3.78e3, max|w|=13.36, neg=22; LW max|w|=1996.41
E4: cvxpy vs pypfopt max|diff|=5.55e-17; no-box closed-form max|diff|=1.94e-16; Sharpe=1.38575528
E5: in-solver group sums [0.4,0.4,0.2]; post-projection [0.515420,0.473385,0.011194] (violates cap)
E6: industry_max_weight max|diff|=0.00e+00
E7: equicorr old-vs-cvxpy max|diff|=5.37e-06; sample 20A max|diff|=0.0000
```

构造补充（**F-R2-2 当轮补登**，Step 2 复审要求）：

```
E1/E2/E4/E5/E6 共用 5x5 SPD：rng=default_rng(1)；m~N(0,1)^(5x5)；a=m@m.T/5+eye*0.01；S=diag(linspace(0.15,0.35,5))@a@diag(...)。
E3 50A：r50=default_rng(7) 依次抽 m50~N(0,1)^(50x50) → S50=m50@m50.T/50+eye*1e-4；mu50~N(0.05,0.02)^50；
       LW 样本 X=N(0,0.01)^(120x50) @ chol(S50+eye*1e-6).T（同一 r50 流，LedoitWolf 在 X 上拟合）。
E7 equicorr：vols=linspace(0.2,0.4,5)、rho=0.3（等相关阵 R，fill_diagonal 1）、S=outer(vols,vols)*R；scores=arange(5,0,-1)。
E7 sample 20A：rng=default_rng(2026)；common~N(0,0.01)^(60x1)；X=common*0.7+N(0,0.008)^(60x20)；S20=cov(X,ddof=1)；scores=linspace(3,1,20)。
E2 性能为单次测量（机器相关；Step 2 复审重放 0.018/0.127/0.964s，量级一致，F-R2-3）。
```

> 说明：全部矩阵/种子构造已在 §4 与上方标明（E3 LW 与 E7 sample 构造为 Step 2 复审补登）；本文不保存临时脚本（中间产物按规范不入库）。
