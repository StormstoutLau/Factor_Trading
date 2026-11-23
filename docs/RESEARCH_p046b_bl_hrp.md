# RESEARCH：P-046b BL / HRP 优化器（组合优化扩展第二批）

> **批次**: P-046b · **Step 1 调研** · 日期 2026-11-23
> **判档**: **T1**（`core/portfolio.py` + `core/config.py`，可能触及 `core/engine_v2.py` 的优化调用面；BL/HRP 均为 opt-in，默认 `equal_weight` 路径与 golden 22 预期零漂移）
> **上游**: [RESEARCH_p046 §1.3/§5.4/§14.8](RESEARCH_p046_portfolio_optimization.md)（L2 新增优化器 / D1-D2 / HRP 一手原文三细节）；[DESIGN_p046](DESIGN_p046_portfolio_optimization.md)；[IMPL_p046](IMPL_p046_portfolio_optimization.md)；[CHECKLIST_p046](CHECKLIST_p046_portfolio_optimization.md)；[PROGRESS §1.4 P-046b](PROGRESS.md#L186)
> **代码证据时点**: HEAD `8f8b912`（P-055 关闭；代码面 `git status --short` 仅文档改动）
> **基座**: DeepSeek-V4.1-Flash（Step 2 复审须 reviewer ≠ author）
> **取证声明**: 本仓源码 E3（逐字读取 + 行号）；**E2 探针 2 组**（§4，脚本可重放）；外部证据 **A1-A26** 分级登记于 §5（A = 全文/官方文档/源码逐字可复核；B = 仅书目/摘要，不得逐字引用）；**A20-A26 为 Step 5 新增源码级锚点**（PyPI 指定版本 wheel + 运行时对拍）。**本文不自评 PASS**——结论留给 Step 2 异构复审。
> **范围裁决待定**: D3 扩展约束是否纳入本批（U-P046b-1）；BL 先验/观点来源（U-P046b-2/3）；`_apply_constraints_legacy` 删除（U-P046b-8）。
> **架构/性能补强（2026-11-23）**: §14 新增 G-P046b-12..17 / U-P046b-12..17（松耦合 / 扩展 / 性能 / 约束 / 多阶段），Step 3 DESIGN 必须逐项裁决。

---

## 0. 本文定位

| 本文件已定 | 留给后续 |
|---|---|
| 题干还原与不做清单（§1） | U-P046b-1..17 的用户/设计裁决（§10 + §14.9） |
| 代码事实基线（§2，@`8f8b912`） | Step 2 异构复审（本文不自评 PASS） |
| 缺口 G-P046b-1..11（§3） | Step 3 DESIGN 的接口签名与数值容差 |
| 取证 E1-E4（§4） | Step 4 设计复审 |
| 外部证据 A1-A6（§5） | Step 5 IMPL / Step 6 复审 |
| 方案矩阵与推荐（§6） | Step 7 CHECKLIST / Step 9 落码 |
| 不变式 I-P046b-1..8（§7） / DoD（§8） | |
| 基线 / 目标读数（§9） | |
| 遗留四项消化（§11） | |

---

## 1. 触发与题干

### 1.1 触发

用户在 P-055 关闭后要求「分析下一步任务」，并选择「台账收口 + P-046b」。依据：

- 关键路径 `042→043→044→045/046/047→059→048→050→051→052→053→054→055` 已全部关闭（[UPGRADE_MASTER_PLAN L277](UPGRADE_MASTER_PLAN.md#L277)）。
- P-046b 是 §1.4 待办表中**唯一无阻塞的 P2 功能批**：硬前置 U-P046-12（HRP 一手原文）已于 2026-11-20 解结（[RESEARCH_p046 §14.8](RESEARCH_p046_portfolio_optimization.md#L528-L558)）。
- P-046c（矩阵式凯利 + 非等风险预算）与 P-046b 同模块，宜紧随其后。

### 1.2 题干（总纲 L262 逐字）

| 项 | 原文 |
|---|---|
| 题干 | `BL/HRP/约束（F2，核心自研 + PyPortfolioOpt 仅对拍）` |
| 前置 | `已裁决（Q7）` |
| 验收 | `权重约束不变量；参考解对拍；synthetic 协方差可跑通` |

### 1.3 本批范围（建议）

| 层 | 内容 | 本批处置 |
|---|---|---|
| L2a | **HRP**（层次风险平价） | **纳入**：论文三细节逐字实现（两级距离 / single linkage / 保序递归二分） |
| L2b | **BL**（Black-Litterman） | **纳入**：后验收益估计 + 复用既有 MVO；先验/观点来源待裁决（U-P046b-2/3） |
| L2c | **D3 扩展约束**（行业上限 / 换手 / 跟踪误差） | **建议延后**（U-P046b-1）：需行业映射 + 当前权重/基准输入，改动面与 P-046b 不成比例 |
| L3 | 矩阵式凯利 / 非等风险预算 | **不做**，归 P-046c |
| D4 | max_sharpe | **不做**（收益噪声大，RESEARCH_p046 §5.4 已建议后置） |

### 1.4 明确不做

| # | 不做 | 依据 |
|---|---|---|
| N1 | 不把 PyPortfolioOpt 设为运行时依赖 | Q7「仅对拍」；`pypfopt` 实测未安装（§2.5） |
| N2 | 不改默认 `equal_weight` 路径与 golden 22 | 回归风险最小化 |
| N3 | 不引入杠杆 / 期货 / 多资产 | 归 P-050/P-058 |
| N4 | 不改 P-048 overlay 三层缩放公式 | 已锁（DESIGN_p048 §6） |
| N5 | 不做盘中 / 高频再优化 | 日频口径 |
| N6 | 不在本批删除 `_apply_constraints_legacy`（除非满足 §11 的三条件） | P-046a 登记的删除门槛 |

---

## 2. 代码事实基线（@`8f8b912`）

### 2.1 优化器族与工厂

| 事实 | 证据 |
|---|---|
| 现有优化器：`EqualWeightOptimizer` / `MinVarianceOptimizer` / `MeanVarianceOptimizer` / `RiskParityOptimizer` | [portfolio.py L315-L575](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L315-L575) |
| `build_optimizer` 词表：`equal_weight` / `min_variance` / `mean_variance` / `mvo` / `risk_parity`；未知 method 抛 `ValueError` | [portfolio.py L610-L629](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L610-L629) |
| `BaseOptimizer._apply_constraints`：上限型只截断留现金；可行型二分缩放至 Σw=1 | [portfolio.py L278-L294](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L278-L294) |
| `_apply_constraints_legacy`：旧 clip→clip→归一，**生产禁用**，仅 AC-C-01a 对拍 | [portfolio.py L296-L300](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L296-L300) |
| `_cov_for`：注入协方差优先（`.loc` 截取），否则走 `estimate_cov` 单一入口 | [portfolio.py L302-L312](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L302-L312) |
| `MeanVarianceOptimizer` 目标：`max μᵀw − risk_aversion·wᵀΣw`，约束 `Σw=1`、`min≤w≤max` | [portfolio.py L472-L492](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L472-L492) |
| `RiskParityOptimizer` 零方差分支：`break` 保持等权，`message=""` | [portfolio.py L527-L542](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L527-L542) |

### 2.2 配置面

| 事实 | 证据 |
|---|---|
| `OptimizerConfig` 字段：`method/max_weight/min_weight/industry_max_weight/round_lot/target_count/select_top/risk_aversion/risk_parity_tol/risk_parity_max_iter/cov_method/cov_lookback/cov_shrinkage` | [config.py L271-L300](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L271-L300) |
| `__post_init__` 仅校验 `max_weight`、`min_weight`、`min_weight<max_weight`、`target_count≥1` | [config.py L302-L315](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L302-L315) |
| `industry_max_weight` / `cov_shrinkage` 在生产面**零消费**；`round_lot` 由 `target_positions` 消费；`round_lot_optimize` 函数零引用 | §11；`Grep` 见 §11.1 |
| 无 BL/HRP 专有字段（`tau` / `prior` / `views` / `linkage`） | 同上 |

### 2.3 引擎接线

| 事实 | 证据 |
|---|---|
| `_optimize_with_diagnostics` 按位置传 3 参：`factor_scores, returns, cov_matrix`；自定义优化器无 `optimize_with_diagnostics` 时回退 2 参 `optimize` | [engine_v2.py L78-L100](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L78-L100) |
| 优化器在 `__init__` 由 `build_optimizer(self.cfg.optimizer)` 构建（或注入） | [engine_v2.py L316-L320](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L316-L320) |
| 每次再平衡先 `estimate_cov(returns_data, cov_method)`，再调用优化器 | [engine_v2.py L1362-L1368](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1362-L1368) |
| 诊断落账：`result.infeasible_kind` 非空或 `message` 非空 → `record_detail(stage="rebalance", error_type="InfeasibleConstraints")` | [engine_v2.py L1370-L1384](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1370-L1384) |
| `IOptimizer` Protocol 只要求 `optimize(signals, returns_data)`；`BaseOptimizer.optimize` 为其兼容包装 | [interfaces.py L231-L240](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L231-L240) / [portfolio.py L252-L259](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L252-L259) |

### 2.4 数据面（BL 先验的关键）

| 事实 | 证据 |
|---|---|
| `DataManager.mktcap` 为可选属性：仅当 `cfg.mktcap_file` 非空时加载，否则返回 `None` | [data.py L179-L183](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L179-L183) |
| 因子中性化消费 `dm.mktcap`（`neutralize_mktcap=True` 且非 None） | [factor.py L349-L353](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L349-L353) |
| 优化调用面**不接收**市值权重；引擎当前只传 `factor_scores/returns/cov` | §2.3 |
| 结论 | 若 BL 采用市值先验，必须新增引擎→优化器的市值权重通道；否则只能退化为等权/零先验 |

### 2.5 测试与依赖基线

| 项 | 值 | 证据 |
|---|---|---|
| 全量 collect | **1441**（1440 passed + 1 skipped） | P-055 门禁 |
| `-k p046` collect | **55** | `pytest --collect-only -q -k p046`（本次） |
| P-046 测试文件 | `test_p046_constraints.py` / `test_p046_cov.py` / `test_p046_engine.py`，共 **37** 个 `def test_` | `Select-String`（本次） |
| `pypfopt` | **未安装**（`find_spec` 为 None） | 本次探针 |
| `scipy` / `numpy` / `pandas` | **1.17.1 / 2.4.6 / 3.0.3** | `.venv` 实测 |
| `scikit-learn` | 1.9.0（LedoitWolf 已用） | P-046a |
| `pyproject` optional extras | 仅 `dev` / `services`；**无 `[research]`** | `pyproject.toml` L58+ |

### 2.6 门禁基线（P-055 关闭）

pytest **1440 passed / 1 skipped** / golden **22** / `-k p054` **120** / mypy **159·0** / black **319** / `tests/*.py` **156** / `core/*.py` **51** / `live/**/*.py` **19** / `services/*.py` **13** / lint-imports **3 kept** / `uv lock --check` **0** / compose **0**。

---

## 3. 缺口清单（G-P046b-1..11）

| ID | 缺口 | 现状证据 | 影响 |
|---|---|---|---|
| **G-P046b-1** | 无 BL 后验估计 | `Grep` 无 `black_litterman` / `posterior`；`build_optimizer` 无 BL 分支 | 题干 L2b 未实现 |
| **G-P046b-2** | 无 HRP | 无 `linkage` / `leaves_list` / 递归二分 | 题干 L2a 未实现 |
| **G-P046b-3** | 无先验收益输入 | 优化器只接收 `factor_scores/returns/cov`；`MeanVarianceOptimizer` 用 `returns.mean()` | BL 缺 Π |
| **G-P046b-4** | 无观点（P/Q/Ω）输入 | `OptimizerConfig` 无 views 字段 | BL 缺 Q/P/Ω |
| **G-P046b-5** | 无 BL 诊断 | `OptimizationResult` 无 `posterior` / `tau` 字段 | 可观测性不足 |
| **G-P046b-6** | HRP 退化未定义 | 1 资产 / 零方差 / 非 PSD / NaN 输入无规格 | I-P046-5 风险 |
| **G-P046b-7** | pypfopt 对拍无入口 | 未装、无 `[research]` extra | A8 只能走 synthetic 闭式 |
| **G-P046b-8** | 死配置/死函数未清理 | `industry_max_weight` 零消费；`cov_shrinkage` 零消费；`round_lot_optimize` 零引用 | A7 遗留 |
| **G-P046b-9** | AST 扫描口径不可复现 | 基线 22 用 P-029 命令（5 目录 + cli.py）；P-046a 复用扫描得 26（口径不同） | F-S9-P046-2 |
| **G-P046b-10** | 零方差无诊断 message | `RiskParityOptimizer` 只 `break`，`message=""`；若补 `"zero_vol"` 会被引擎误标 `InfeasibleConstraints` | F-S10-P046-1 |
| **G-P046b-11** | `estimate_cov` 两处语义偏差 | 退化分支无 warning 且用选定 method 补零；`codes` 静默取交集（文档说 reindex） | F-S10-P046-2/3 |

---

## 4. 取证（E1-E4）

### 4.1 E1：HRP 论文数值链复现（可重放）

**命令**：`.venv\Scripts\python.exe` 内联脚本（§4.1 附代码）；**种子**：无（确定性）。

| 项 | 论文值（SSRN 2708678，pp.5-6 / §14.8） | 本次实测 | 结论 |
|---|---|---|---|
| `d_{i,j}=sqrt(½(1−ρ))`（ρ 例） | `[0,0.3873,0.6325; …; 0.6325,0.7746,0]` | `[[0,0.3873,0.6325],[0.3873,0,0.7746],[0.6325,0.7746,0]]` | **逐位吻合** |
| `d̃_{i,j}=sqrt(Σ_n(d_{n,i}−d_{n,j})²)` | `[0,0.5659,0.9747; 0.5659,0,1.1225; 0.9747,1.1225,0]` | 同左 | **逐位吻合** |
| `scipy.linkage(..., method="single")` | 原文 single linkage（nearest point） | `Z=[[0,1,0.5659,2],[2,3,0.9747,3]]`；`leaves_list=[2,0,1]` | 与原文一致；叶序由 scipy 确定性给出 |
| 递归二分（3 资产，Σ=diag(0.04,0.09,0.16) 按叶序重排） | 算法见 §14.8 细节 3 | `w(order)=[0.1475,0.5902,0.2623]`，Σw=**1.0000**（Step 4 复审独立复算订正，F-4-8：原记 [0.1665,0.5771,0.2565] 与所述 Σ 不可复现） | 算法可复现；权重仅作实现自洽，**不作 golden** |

> 说明：论文 Example 1-2 只给距离链，不给权重；P-046b 的 golden 应以「距离链逐位 + 权重由测试内独立复算 α」构成，禁止硬编码上表权重（**RESEARCH_p046 §8 A5 禁录制规则**，F-R4-P046b-4 订正引用）。

### 4.2 E2：BL 后验公式与性质（可重放）

**设定**：Σ=`[[0.04,0.01,0.02],[0.01,0.09,0.03],[0.02,0.03,0.16]]`，`w_mkt=[0.5,0.3,0.2]`，δ=3 → `Π=[0.081,0.114,0.153]`；单条绝对观点 `P=[1,0,0]`、`Q=0.10`、`Ω=τPΣPᵀ`。

| 性质 | 实测 | 结论 |
|---|---|---|
| 无观点（K=0） | 后验 = Π（公式退化为 `[(τΣ)⁻¹]⁻¹[(τΣ)⁻¹Π]`） | 可作为测试 |
| `Ω=τPΣPᵀ` 时 τ 消去 | τ=0.05 与 τ=0.5 后验**完全相同**（`[0.0905,0.116375,0.15775]`） | 与 pypfopt 文档一致（A3） |
| `Ω→0` | 观点资产后验 → **Q=0.10**（`[0.1,0.11875,0.1625]`） | 极限测试 |
| `Ω→∞` | 后验 → **Π**（`[0.081,0.114,0.153]`） | 极限测试 |
| 单观点只改变观点资产权重？ | `(δΣ)⁻¹post` = `[0.579167,0.3,0.2]`；其余两资产**恰好不变** | **一般性质（非本例特有，F-R2-P046b-2 订正）**：默认 `Ω=τPΣPᵀ` 下 `w = w_mkt + (1/(2δ))·Pᵀ(PΣPᵀ)⁻¹(Q−PΠ)`，单绝对观点 `P=eᵢ` 时倾斜仅在 i 列非零；Step 2 复审以随机 5×5 Σ（seed=42）复算 non-view \|tilt\|max ≈ **8.9e-16**。→ 建议 Step 3 将其纳入 BL 闭式测试 |

### 4.3 E3：代码面静态核验

- 逐字读取 [portfolio.py](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py)、[config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py)、[engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py) 相关段落（§2 行号）。
- `Grep` 核验：无 `black_litterman` / `linkage` / `leaves_list` / `posterior`；`industry_max_weight` / `cov_shrinkage` / `round_lot_optimize` 的消费面见 §11.1。
- `git status --short`：代码面干净（仅文档改动）；`git diff --stat -- core live` 空。

### 4.4 E4：外部实现口径核验

| 来源 | 级别 | 要点 |
|---|---|---|
| Idzorek 2004（A1） | A（PDF 全文） | BL 后验公式 `E[R]=[(τΣ)⁻¹+PᵀΩ⁻¹P]⁻¹[(τΣ)⁻¹Π+PᵀΩ⁻¹Q]`；先验 `Π=λΣw_mkt`；观点可为绝对/相对；置信度 0-100% |
| pypfopt 文档/源码（A3） | A（官方文档 + 源码页） | `tau=0.05`（0,1]；`omega=None/"default"` → `diag(diag(τPΣPᵀ))`；`pi="equal"` → `1/N`；`pi=None` → **零向量 + warning**；`pi="market"` 需 `market_caps`；`risk_aversion` 默认 1 |
| López de Prado 2016（A4，仓内 §14.8） | A（SSRN 全文） | 两级距离 / single linkage / 保序二分 α 拆分三细节逐字锚定 |
| scipy `linkage` 官方（A5） | A（官方文档） | `method="single"` = `min(dist(u[i],v[j]))`，即 Nearest Point Algorithm；输入可为 condensed distance matrix |

---

## 5. 外部证据登记（A1-A26）

| ID | 证据 | 来源 | 级别 | 本批用途 |
|---|---|---|---|---|
| **A1** | Idzorek (2004) *A Step-by-Step Guide to the Black-Litterman Model* | `https://people.duke.edu/~charvey/Teaching/BA453_2006/Idzorek_onBL.pdf`（July 20, 2004 版） | **A** | 后验公式（§2.1）、先验公式（Formula 1）、绝对/相对观点定义（§2.2） |
| **A2** | He & Litterman (1999) 白皮书 | 仓内 [RESEARCH_p046 E11](RESEARCH_p046_portfolio_optimization.md#L451)（Duke 镜像，20 页） | **A** | `Π=δΣw_mkt`；`δ=25` 示例；`w*=(δΣ)⁻¹μ` |
| **A3** | PyPortfolioOpt 官方文档 + `black_litterman` 源码页 | `https://pyportfolioopt.readthedocs.io/en/latest/BlackLitterman.html` / `_modules/pypfopt/black_litterman.html` | **A**（实现参照） | 默认 `tau=0.05`；`default_omega=diag(diag(τPΣPᵀ))`；`pi` 三态；`risk_aversion=1` |
| **A4** | López de Prado (2016) *Building Diversified Portfolios that Outperform Out-of-Sample* | SSRN 2708678（仓内 [§14.8](RESEARCH_p046_portfolio_optimization.md#L528-L558)） | **A** | HRP 三细节逐字实现 |
| **A5** | scipy `hierarchy.linkage` 官方文档 | `https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html` | **A** | single linkage 语义；condensed matrix 输入 |
| **A6** | Black & Litterman (1992) *Global Portfolio Optimization* | FAJ 48(5), 28-43；DOI `10.2469/faj.v48.n5.28` | **B**（书目） | **不得逐字引用正文**（扫描件无文本层）；公式一律引 A1/A2 |
| **A7** | Meucci (2010) *The Black-Litterman Approach: Original Model and Extensions* | SSRN 1117574；`https://cdn.interactiveadvisors.com/documents/third-party/ssrn-id1117574.pdf`（17 页，Oct 12 2010；短版 Wiley Encyclopedia of Quantitative Finance） | **A**（全文） | 后验 (16)-(19)；**计算更稳表示 (20)**：`μ_BL = π + τΣPᵀ(τPΣPᵀ+Ω)⁻¹(v−Pπ)`；Ω=(1/c)PΣPᵀ (12)；τ≈1/T (8)；λ≈1.2；后验下带约束 MVO（Allocation 段，Step 2 定点复审订正页码口径） |
| **A8** | Walters (2014) *The Black-Litterman Model in Detail* | SSRN 1314585（June 20 2014） | **B**（元数据/摘要；全文未取得） | 实现综述；**不用于公式结论**，仅作后续实现对照 |
| **A9** | Riskfolio-Lib 官方文档 7.4 | `https://riskfolio-lib.readthedocs.io/en/latest/index.html` | **A**（官方文档） | 社区案例：HRP/HERC（37 risk measures）、NCO、BL/Bayesian BL/Augmented BL；基于 CVXPY；单一 `Portfolio` + `model` 切换（`Classic/BL/FM/BLFM`——枚举引自官方文档摘要 v7.3，latest 直抓因页面截断未达参数段；Step 2 定点复审标注口径） |
| **A10** | skfolio 官方文档 + arXiv 论文 | `https://skfolio.org/user_guide/prior.html` / `.../optimization.html`；arXiv 2507.04176 | **A**（官方文档 + 全文） | 社区案例：`Prior` 估计器与 `optimization` 分离；`ReturnDistribution`；BL 作为 prior；HRP 作为 optimizer；scikit-learn `fit` API；统一框架 |
| **A11** | Raffinot (2018) *The Hierarchical Equal Risk Contribution Portfolio* | SSRN 3237540 | **B**（SSRN 摘要） | HERC 扩展点；**不用于公式** |
| **A12** | López de Prado (2019) *A Robust Estimator of the Efficient Frontier* | SSRN 3469961 | **B**（SSRN 摘要） | NCO 扩展点；**不用于公式** |
| **A13** | Boyd, Busseti, Diamond, Kahn, Koh, Nystrup, Speth (2017) *Multi-Period Trading via Convex Optimization* | arXiv 1705.00109；FnT Optimization 3(1):1-76（arXiv v1 页眉为 1-74，Step 2 定点复审注） | **A**（全文） | 单期/多期凸优化；交易/持有成本；holding/trading/soft constraints；多期只执行第一步（MPC）；支撑 §14.5/§14.6 |
| **A14** | Parnas (1972) *On the Criteria To Be Used in Decomposing Systems into Modules* | CACM 15(12):1053-1058；`https://www.cs.ubc.ca/~gregor/teaching/papers/p1053-parnas.pdf` | **A**（全文） | 模块分解以信息隐藏/接口稳定为准则；支撑估计器/优化器/约束/上下文边界 |
| **A15** | Cockburn (2005) *Hexagonal Architecture (Ports & Adapters)* | `https://alistair.cockburn.us/hexagonal-architecture/`（HaT TR 2005.02） | **A**（全文） | 应用核心不依赖 UI/DB；支撑 `PriorProvider`/`ConstraintSpec`/`OptimizationContext` 作为端口 |
| **A16** | pluggy 官方文档 | `https://pluggy.readthedocs.io/en/stable/` | **A**（官方文档） | pytest 插件管理核心（1400+ 插件）；hook specs + plugin manager；支撑 Registry 统一（R2）参考，但本批不重构 |
| **A17** | scipy `spatial.distance.pdist` 官方文档 | `https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.pdist.html` | **A**（官方文档） | condensed pairwise distance；HRP `d̃` 用 `pdist` 避免 O(N³) 广播（Step 2 定点复审直抓核验：「Returns a condensed distance matrix Y」） |
| **A18** | sklearn `LedoitWolf` 文档 + 锁版源码 | 仓内 [RESEARCH_p046 E2](RESEARCH_p046_portfolio_optimization.md#L442) | **A**（官方 + 源码） | 收缩强度 `mu=tr(S)/p`、`beta/delta` 汇总全截面 → 子集化改变数值；支撑 §14.4 警告（**定点复审数值探针升级**：LW `shrinkage` full=0.9248 vs 子集=1.0，子矩阵 max|diff|=4.1e-5；sample/EWMA 子集==全矩阵子块 `atol=1e-15`） |
| **A19** | PyPortfolioOpt `Other Optimizers`（HRP）官方文档 | `https://pyportfolioopt.readthedocs.io/en/latest/OtherOptimizers.html` | **A**（官方文档） | HRP 四步概述；`HRPOpt` 独立于 `EfficientFrontier` → 组合式 API 先例 |
| **A20** | PyPortfolioOpt **1.5.5** `pypfopt/black_litterman.py` 源码（PyPI wheel 逐字） | `pyportfolioopt==1.5.5`（`uv pip install --no-deps --target`） | **A**（源码） | L346-356 `default_omega=diag(diag(τPΣPᵀ))`；L400-408 `post=π+τΣPᵀ·solve(τPΣPᵀ+Ω, Q−Pπ)`（L403 注释「avoid inversion」）；L430-453 隐含权重；L277-278 `pi="equal"`=平直 1/N（与本仓 D4 分歧）；L229-235 未知观点资产抛错（与 D5 分歧） |
| **A21** | PyPortfolioOpt **1.5.5** `pypfopt/hierarchical_portfolio.py` 源码 | 同上 | **A**（源码） | L77-93 逆方差簇权重；L95-105 `to_tree(...).pre_order()`；L107-140 二分 + `α=1−v₁/(v₁+v₂)`；**L165-168 `squareform(d)` 而非 `pdist(d)`**（与论文第二级距离分歧）；无零方差守卫 |
| **A22** | skfolio **1.14.4** `prior/_black_litterman.py` 源码 | `skfolio==1.14.4` | **A**（源码） | 默认 Ω 同式；L277-285 `post=π+_v·solve(_a,_b)+rf`、`posterior_cov=Σ+τΣ−_v·solve(_a,_v.T)`（后验 Σ 分歧，D7）；默认 prior `EquilibriumMu`（δΣw_mkt） |
| **A23** | skfolio **1.14.4** HRP 三文件源码 | `cluster/_hierarchical.py` / `seriation/_hierarchical.py` / `optimization/hierarchical/_seriation/_hrp.py` | **A**（源码） | L189-197 `squareform`+`linkage`；L127-132 `leaves_list`；L485-488 零/非有限风险抛 `OptimizationError`；L512 α 公式；L514-521 约束在拆分因子层（与 D12 后投影分歧）；默认 linkage Ward（与 D9 single 分歧） |
| **A24** | Riskfolio-Lib **7.4.1** `src/HCPortfolio.py` 源码 | `riskfolio-lib==7.4.1` | **A**（源码） | L381-382 `squareform`+`linkage`；L239-243 MV 下 `1/risk²` 逆方差、无零风险守卫；L433-506 递归二分 α |
| **A25** | pypfopt 1.5.5 × pandas **3.0.3** 运行时实证 | 本机实跑（`HRPOpt(cov_matrix=...).optimize()`） | **A**（可重放） | `_raw_hrp_allocation` L120 `pd.Series(1, ...)` 为 int64 → L138-139 `*= alpha` 抛 `TypeError: Invalid value ... for dtype 'int64'` → pypfopt 仅手工对拍、不得进 CI（Q7 强化） |
| **A26** | scipy **1.17.1** `leaves_list` vs `to_tree(...).pre_order()` | 本机实跑（论文 Example） | **A**（可重放） | 两者输出相等；叶序口径闭合（F-R3） |

**A20-A26 取证降级链**：GitHub raw / jsDelivr 直抓均返回空（WebFetch local crawler）→ 降级 PyPI 镜像 wheel（版本号可解析）→ 本地逐字读取 + 运行时对拍；**未取 GitHub commit hash**，不引 master 分支结论。

**源码级对拍读数（Step 5）**：BL 后验 `[0.0905, 0.116375, 0.15775]` 与 τ 消去、隐含权重 `[0.579167, 0.3, 0.2]` 均与 pypfopt 逐位一致；HRP 随机 6×6（seed=7）叶序 `pdist(d)=[5,1,2,3,0,4]` vs `squareform(d)=[5,2,1,3,0,4]`，权重 `max|Δ|=0.0152` → **对拍边界**见 [IMPL_p046b §4](IMPL_p046b_bl_hrp.md)。

**不得引用清单（沿用 RESEARCH_p046 §14.5）**：BL 1992 正文逐字；HRP 付费墙 JPM 版页码（以 SSRN preprint 为准）；pypfopt 内部求解链路差异（只引文档/源码可见部分）；Walters 2014 全文未取得 → 不引逐字；HERC/NCO 仅摘要 → 不引公式/数值。

### 5.1 社区案例对照（实现层）

| 库 | 架构事实 | 与本批设计的关系 |
|---|---|---|
| **PyPortfolioOpt** | `BlackLittermanModel` 独立于 `EfficientFrontier`；`HRPOpt` 独立；用法为 `bl_returns()` → `EfficientFrontier(rets, cov)`（A3）；HRP 四步概述、与其他优化器并列（A19） | **支持 P1/P2**：估计器与优化器分离、组合式 API；社区先例 |
| **skfolio** | `prior` 估计器（含 `BlackLitterman`）与 `optimization` 分离；`ReturnDistribution` 统一中间物；所有模型共享 scikit-learn `fit` API（A10） | **最强先例**：直接支撑 B2' 组合、`PriorProvider`/`ReturnDistribution`、配置隔离；与本批 §14 设计原则一致 |
| **Riskfolio-Lib** | 单一 `Portfolio` 类 + `model` 参数（`Classic/BL/FM/BLFM`）；HRP/HERC 覆盖 37 risk measures、NCO；基于 CVXPY（A9） | **广度/反例参考**：功能全但配置集中在单一类；本仓选择拆分以降低耦合，不照搬 |

> **参数口径提醒**：τ 存在经验差异——Meucci (2010) 建议 `τ≈1/T`（A7 eq.8），pypfopt 默认 `τ=0.05`（A3）；默认 `Ω=τPΣPᵀ` 时 τ 消去，故默认路径不受影响；**自定义 Ω 时须显式裁决 τ**（并入 U-P046b-5）。λ 亦依赖市场/频率/口径（Meucci 示例 λ≈1.2；He-Litterman 示例 δ=25），本仓复用 `risk_aversion`，**不硬编码 25/1.2**。

### 5.2 锚点对 §14 设计原则的支撑

| 原则 | 外部支撑 |
|---|---|
| P1 估计器/优化器分离 | A7 Meucci (16)-(21)；A10 skfolio prior/optimization；A3/A19 PyPortfolioOpt |
| P2 组合优于继承 | A10 skfolio；A3/A19 PyPortfolioOpt；A14 Parnas 接口稳定 |
| P3 配置隔离 | A10 skfolio `ReturnDistribution`/prior 对象；A9 Riskfolio 单一 `Portfolio` 作为反例 |
| P4 单一工厂 | A16 pluggy hookspec/plugin manager；A14 模块边界 |
| P5 向后兼容 | A14 Parnas 信息隐藏/稳定接口；A15 Ports & Adapters |
| P6 约束即数据 | A13 Boyd holding/trading/soft constraints；[RESEARCH_p046 E4/E9/E10](RESEARCH_p046_portfolio_optimization.md#L444)（cvxpy / MSCI 方法论） |
| P7 单期/多期边界 | A13 Boyd single vs multi-period（only first trade executed） |
| P8 复杂度显式 | A7 Meucci (20) 稳定表示；A17 scipy `pdist`；A18 sklearn LW |

---

## 6. 方案矩阵

### 6.1 BL 落地形态

| 方案 | 内容 | 改动面 | 风险 | 评价 |
|---|---|---|---|---|
| **B1** 仅估计器 | `black_litterman_posterior(cov, prior, P, Q, omega, tau)` 纯函数；不接 `build_optimizer` | 新函数 + 测试 | 低 | 不能直接用于回测 |
| **B2'** 估计器 + 优化器（**组合委托**；§14.2 C1 修订） | `black_litterman_posterior()` 纯函数 + `BlackLittermanOptimizer` 持有 `BaseOptimizer` 委托；`BLConfig` 嵌套配置；无观点时后验=先验 | `portfolio.py` + `config.py` | 低-中 | **推荐**：可复用到 min_variance / risk_parity；接口清晰、可测、opt-in |
| **B3** 优化器 + 因子分数派生观点 | `bl_view_mode="scores"`：P=I，Q=zscore(scores)×scale | 额外映射规则 | 中 | 需产品定义；可作为 B2 的可选扩展 |
| **B4** 外部 pypfopt | 运行时依赖 | 依赖/锁 | 高 | 违反 Q7 |

### 6.2 BL 先验来源

| 方案 | 内容 | 依赖 | 评价 |
|---|---|---|---|
| **P1** 等权先验 | `Π = δΣ(1/N)` | 无 | 无观点时等价于最小方差（可解释）；默认可用 |
| **P2** 市值先验 | `Π = δΣw_mkt`，引擎注入 `dm.mktcap.loc[date, selected]` | 需 `mktcap_file`；需新增引擎→优化器通道 | 经济含义最强；数据缺失时回退 P1 |
| **P3** 零先验 | `Π=0`（pypfopt `pi=None` 行为） | 无 | 仅适合「纯观点混合」；不推荐默认 |

### 6.3 BL 观点来源

| 方案 | 内容 | 评价 |
|---|---|---|
| **V1** 显式配置 | `bl_views: dict[str, float]`（绝对观点），可选 `bl_view_confidences` | 最小可用；观点静态，适合人工覆盖 |
| **V2** 因子分数派生 | P=I，Q=标准化分数×`bl_view_scale` | 与因子策略一致，但映射规则需产品裁决 |
| **V3** 无观点 | 后验=先验 | 等价于「均衡收益 MVO」；可作为默认降级 |

### 6.4 HRP 落地形态

| 方案 | 内容 | 依赖 | 评价 |
|---|---|---|---|
| **H1'** 论文逐字实现（三纯函数） | `correlation_distance` → `quasi_diagonal_order`（`linkage(single)`+`leaves_list`）→ `recursive_bisection`；距离用 `pdist`/`squareform` | scipy（已装） | **推荐**（§14.3/§14.4 修订）；E1 已复现距离链；避免 O(N³) 广播 |
| **H2** 仅用 pypfopt `HRPOpt` | 外部依赖 | pypfopt | 违反 Q7；且文档只给四步概述，细节不如论文 |
| **H3** 近似（相关距离 + 等权聚类） | 简化 | 无 | 不满足题干「参考解对拍」 |

### 6.5 D3 扩展约束

| 方案 | 内容 | 评价 |
|---|---|---|
| **D3-A** 纳入本批 | 行业上限 + 换手 + 跟踪误差 | 需行业映射、当前权重、基准；改动面大，golden 风险高 |
| **D3-B** 延后 | 本批只做 BL/HRP；`industry_max_weight` 保持冻结/删除二选一；**新增 `ConstraintSpec` 钩子 + HRP 后投影限制声明**（§14.5） | **推荐**；P-046b 聚焦题干 L2 |

---

## 7. 不变式（I-P046b-1..8）

| ID | 不变式 | 验证方式 |
|---|---|---|
| I-P046b-1 | HRP 权重非负、`Σw=1`、且在 `[min_weight,max_weight]` 内（可行域） | 闭式 + 参数化 |
| I-P046b-2 | HRP 距离链 `d` / `d̃` 与论文 Example 1-2 逐位一致（`atol=1e-4`） | E1 golden |
| I-P046b-3 | HRP 使用 single linkage 与保序二分；叶序由 `linkage`+`leaves_list` 确定性给出（无并列距离时唯一）；**仅保持簇内相邻性的叶序变体**不改变权重——任意叶置换会改变二分切分，不在不变式范围（F-R3-P046b-3 口径收窄） | 读码 + 2 组簇保序叶序断言 |
| I-P046b-4 | BL 无观点时后验=先验；`Ω→0` 时观点资产→Q；`Ω→∞` 时→先验 | 闭式极限 |
| I-P046b-5 | BL 默认 `Ω=diag(diag(τPΣPᵀ))` 时 τ 消去（两个 τ 结果一致） | E2 |
| I-P046b-6 | BL 后验收益有限、无 NaN；协方差沿用原 Σ（或显式 posterior Σ），二者只能择一并在文档固定 | 闭式 + 读码 |
| I-P046b-7 | 退化输入（1 资产 / 零方差 / 非 PSD / NaN）不产生 NaN；HRP 走显式分支 | 3 组退化用例 |
| I-P046b-8 | 默认 `equal_weight` 与 golden 22 零漂移 | 全量 + golden |

---

## 8. DoD（A-P046b-1..8）

| ID | 验收项 |
|---|---|
| A-P046b-1 | HRP 输出满足 I-P046b-1/2/3/7；至少 1 组论文距离链 golden + 2 组 synthetic 权重闭式 |
| A-P046b-2 | BL 输出满足 I-P046b-4/5/6；至少 1 组「无观点=先验」+ 1 组「单观点后验」+ 2 组极限 |
| A-P046b-3 | `build_optimizer` 新增 `hrp` / `black_litterman` 分支；未知 method 行为不变 |
| A-P046b-4 | BL/HRP 均为 opt-in；默认配置与 golden 22 零漂移 |
| A-P046b-5 | 遗留四项：`zero_vol` message、`estimate_cov` warning、`codes` 语义、AST 口径（§11）。**删除面零残留断言须声明 `config_v2`（FROZEN/TD-2）冻结例外**（F-R1-P046b-1） |
| A-P046b-6 | mypy 0 / black unchanged / `-k p046` 增量符合 Step 7 目标 / `uv lock --check` 0 |
| A-P046b-7 | 不新增运行时依赖；pypfopt 对拍为可选手工（不影响门禁） |
| A-P046b-8 | 文档回写：RESEARCH/DESIGN/IMPL/CHECKLIST 与 PROGRESS 状态链一致 |
| A-P046b-9 | 性能基准报告：N=50/200/500 的 cov/HRP/BL 量级；不设 SLO；全维协方差瓶颈与 `pdist`/Woodbury 实现约束落档（§14.4） |
| A-P046b-10 | 架构决策落档：B2' 组合、嵌套配置、工厂路线 R1、`ConstraintSpec` 钩子、单期/多阶段边界（§14.2-§14.7） |

---

## 9. 基线 / 目标读数

| 项 | 基线（P-055 关闭） | P-046b 目标 |
|---|---|---|
| pytest 全量 | **1440 passed / 1 skipped**（collect 1441） | 1440 + Δ（Δ = 新增用例，预计 +25~35） |
| `-k p046` | **55** | 55 + Δ′ |
| `-k golden` | **22** | **22 零重录** |
| mypy | **159 files / 0** | 159（若新增 `core/*.py` 则 +1）/ 0 |
| black | **319** | 319 + 新文件已格式化 |
| `tests/*.py` | **156** | 156 + 新文件数 |
| `core/*.py` | **51** | 51（若新增模块则 +1） |
| AST `except Exception` | core 外 **22**（P-029 口径）/ core **30** | 口径固化；不新增裸 except |
| `uv lock --check` | **0** | **0**（不新增运行时依赖） |

---

## 10. 未决项（U-P046b-1..17）

| ID | 未决项 | 选项 | 当前倾向 |
|---|---|---|---|
| **U-P046b-1** | D3 扩展约束是否纳入本批 | D3-A / D3-B | **D3-B 延后**（§6.5） |
| **U-P046b-2** | BL 先验来源 | P1 等权 / P2 市值 / P3 零 | **P1 默认 + P2 可选**（需引擎通道时另行立项） |
| **U-P046b-3** | BL 观点来源 | V1 显式配置 / V2 因子分数 / V3 无 | **V1 + V3 降级**；V2 待产品裁决 |
| **U-P046b-4** | 后验协方差是否替换原 Σ | 原 Σ / posterior Σ | **原 Σ**（与 pypfopt 示例一致，减少二次口径） |
| **U-P046b-5** | Ω 默认 vs Idzorek 置信度 | 默认 / Idzorek | **默认**（He-Litterman）；Idzorek 作为后续扩展 |
| **U-P046b-6** | pypfopt 对拍是否入 CI | 是 / 否 | **否**（A8 允许 synthetic 闭式） |
| **U-P046b-7** | HRP 退化策略 | 等权 / 抛错 / 显式诊断 | 待 Step 3：1 资产=1.0；零方差=等权 + message |
| **U-P046b-8** | `_apply_constraints_legacy` 是否删除 | 删 / 留 | **留**（三条件未满足，P-046a 已登记） |
| **U-P046b-9** | `zero_vol` 的 engine `error_type` | `InfeasibleConstraints` / 新类型 | 待 Step 3：建议独立 `ZeroVariance` 或 `message` 前缀分流 |
| **U-P046b-10** | `estimate_cov(codes=...)` 语义 | KeyError / 交集 + warning / 删参数 | **交集 + warning**（最小破坏）或 KeyError（与文档一致） |
| **U-P046b-11** | AST 扫描口径 | P-029 五目录 + cli.py / 全仓非 core | **P-029 口径**为唯一基线（22）；全仓口径另表登记，不混用 |
| **U-P046b-12** | BL 落地形态 | 继承 MVO / **组合委托** | **组合（B2'）**；估计器纯函数（§14.2 C1） |
| **U-P046b-13** | 工厂统一时机 | 本批接 Registry / **本批走 map + 后续独立批** | **后续独立批**；P-046b 只加 map 分支（§14.3） |
| **U-P046b-14** | 是否引入 `OptimizationContext` | 本批最小引入 / 延后 | **Step 3 决定**；若引入保持旧 3 参兼容（§14.2 C3） |
| **U-P046b-15** | 性能基准与高维守卫 | 只报告 / 加守卫 / 设 SLO | **报告 + `HRP_MAX_ASSETS` 可配置守卫；不设 SLO**（§14.4） |
| **U-P046b-16** | HRP 带约束语义 | 后投影近似 / 约束风险平价 | **本批后投影 + 明确限制**；严格约束归后续（§14.5） |
| **U-P046b-17** | 多阶段 DP 边界 | 优化器内实现 / **独立 policy 层** | **独立 policy 层；优化器保持单期纯函数**（§14.6） |

---

## 11. 遗留四项消化方案

### 11.1 死配置/死函数现状（Grep @`8f8b912`）

| 项 | 生产消费 | 处置建议 |
|---|---|---|
| `industry_max_weight` | 无（仅 `config_v2` 冻结模块校验） | D3 延后 → **保留字段并加「D3 未接线」注释**；或本批删除（需用户裁决） |
| `cov_shrinkage` | 无（已标废弃） | **删除**（P-046a 已建议；无消费）。**范围限定 `core/config.py`**：`config_v2.py` L137 同名字段属 FROZEN/TD-2 冻结模块，**不得修改**（P-046a C-4 先例）；验收「零残留」须显式声明该冻结例外（F-R1-P046b-1） |
| `round_lot` | `target_positions` 消费 | **保留**（不是死配置） |
| `round_lot_optimize` | 无引用 | **删除**（死函数） |

### 11.2 F-S9-P046-2（AST 口径）

- **唯一基线命令**（P-029 I1，可重放）：
  ```powershell
  $py -c "import ast,pathlib;r=pathlib.Path('.');s=[p for d in ['agents','filter','scripts','batch_backtest','strategy_evaluation'] for p in (r/d).rglob('*.py')]+[r/'cli.py'];print(sum(1 for p in s if p.exists() for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='Exception'))"
  ```
- 预期 **22**（P-029 基线）；P-046a 的「core 外 26」是**不同目录集**，不得与 22 混用。P-046b 只报 P-029 口径，若需全仓口径另立附表并注明范围。

### 11.3 F-S10-P046-1..3

| ID | 修复方案 | 风险 |
|---|---|---|
| F-S10-P046-1（`zero_vol` message） | 在 `RiskParityOptimizer` 零方差分支返回 `message="zero_vol"`；同时把引擎 `record_detail` 的 `error_type` 改为按 message 前缀分流（`zero_vol` → `ZeroVariance`） | 需同步 engine 分类；不新增抛错 |
| F-S10-P046-2（退化 warning） | `estimate_cov` 有效行 <2 时 `logger.warning("effective_rows<2，回退零协方差/选定 method")`；文档写明补零后仍走选定 method | 仅日志；输出不变 |
| F-S10-P046-3（`codes` 语义） | 二选一：① 改 `reindex` 补 0（符合原文档）② 缺失码 `KeyError` ③ 交集 + warning。建议 **③ 最小破坏**，Step 3 定 | 当前零生产调用方，风险低 |

---

## 12. 步骤表（Step 1-10）

| Step | 内容 | 状态 |
|---|---|---|
| 1 | 调研（本文） | ✅ 2026-11-23 |
| 2 | 异构复审（reviewer ≠ author） | 待执行 |
| 3 | DESIGN（接口签名、D1-Dn、I1-In、U 收敛） | 待执行 |
| 4 | 设计复审 | 待执行 |
| 5 | IMPL（BL/HRP 逐处代码 + 测试映射） | 待执行 |
| 6 | IMPL 复审 | 待执行 |
| 7 | CHECKLIST（M/T/C/I/D/F 组） | 待执行 |
| 8 | 四文档一致性 | 待执行 |
| 9 | TDD 落码 + 门禁 | 待执行 |
| 10 | 验收 + 异构复审 + 提交授权 | 待执行 |

---

## 13. Step 2 复审包（给 reviewer 的最小核对清单）

1. **题干覆盖**：L2a/L2b 是否都有落点；D3 延后是否越权（需用户裁决，见 U-P046b-1）。
2. **代码事实**：§2 的 12 处行号是否仍指向 `8f8b912`；`build_optimizer` 词表、引擎 3 参调用、`mktcap` 可选性是否属实。
3. **外部证据**：A1 公式与 A3 默认值是否逐字一致；A4 三细节是否与 §14.8 一致；A6 是否被误引。
4. **数值链**：E1 的 `d` / `d̃` 是否与论文逐位一致；E2 的 τ 消去与极限是否可重放。
5. **遗留四项**：§11 的处置是否覆盖 F-S9-P046-2 + F-S10-P046-1~3；AST 口径是否混用。
6. **不变式/DoD**：I-P046b-1..8 是否可机械验证；A8 的「synthetic 闭式」是否足够替代 pypfopt。
7. **范围控制**：是否夹带 P-046c（凯利/预算）/ D3 / 策略层改动。

---

## 14. 架构与性能补充调研（2026-11-23，Step 1 补强）

> **触发**：用户要求补充评估「松耦合 / 易扩展升级 / 计算性能 / 高维 / 带约束 / 多阶段动态规划」。
> **性质**：不改变 §1-§13 的事实与证据结论；新增 6 项缺口（G-P046b-12..17）与 6 项未决（U-P046b-12..17），交 Step 3 DESIGN 裁决。Step 2 复审的事实性 PASS 仍有效（其范围为代码事实/数值链/外部锚）。
> **实测环境**：`.venv` Python 3.12 / numpy 2.4.6 / scipy 1.17.1 / pandas 3.0.3；T=60；单次运行，仅作量级参考，**不设 SLO**。

### 14.1 总评

| 维度 | 现有 RESEARCH 覆盖 | 评级 | 主要缺口 |
|---|---|---|---|
| 松耦合 | B1 纯估计器方向正确；但 B2 用继承、`OptimizerConfig` 单块、引擎 3 参位置调用 | **中** | 继承耦合 / 配置膨胀 / 上下文接口刚性 |
| 易扩展升级 | `build_optimizer` 可加词表；但已有 `PluginRegistry` 休眠、无组件复用契约 | **中低** | 双工厂漂移；HRP/BL 未拆可复用纯函数 |
| 计算性能 / 高维 | 未覆盖（无复杂度、无基准、无守卫） | **低** | 全维协方差先于选股；HRP 距离矩阵实现风险；BL 用了 N×N 逆 |
| 带约束优化 | D3 延后；BL/MVO 走 cvxpy，HRP 走后投影 | **低** | 无 `ConstraintSpec` 抽象；HRP 约束语义未定义 |
| 多阶段动态规划 | 未涉及（当前单期再平衡） | **不适用（边界正确）** | 需明确「优化器保持单期纯函数」的边界与未来 policy 层 |

**结论：方向正确、架构层次不足。** P-046b 的 Step 1/2 在正确性与证据上扎实；但若按原 B2/H1 直接落码，会形成「可运行但难升级」的实现。建议按 §14.7 修订方案矩阵后，再进入 Step 3。

### 14.2 松耦合分析（5 处）

| # | 现状耦合点 | 问题 | 建议 |
|---|---|---|---|
| C1 | **B2 继承 `MeanVarianceOptimizer`** | BL 后验估计与 MVO 强绑定；无法复用到 min_variance / risk_parity；继承会复制 cvxpy 逻辑 | **组合优于继承（B2'）**：`black_litterman_posterior()` 纯函数 + `BlackLittermanOptimizer` 持有一个 `BaseOptimizer` 委托；后验 μ 交给被委托优化器。估计器可独立测试。**社区先例**：skfolio 的 `Prior` 与 `optimization` 分离（A10）；PyPortfolioOpt 的 `BlackLittermanModel` 与 `EfficientFrontier` 分离（A3/A19） |
| C2 | **`OptimizerConfig` 单块** | 加 `bl_tau/bl_prior/bl_views` + HRP 参数后成为「god object」；所有 method 携带无关字段；与冻结的 `config_v2` 形成双写风险 | 嵌套 `BLConfig` / `HRPConfig`（`field(default_factory=...)`），仅在 method 匹配时读取；`config_v2` 零改动；`OptimizerConfig.__post_init__` 保持原校验 |
| C3 | **引擎 3 参位置调用** | 未来 D3/市值先验/多阶段需要 `market_weights/current_weights/benchmark/industry`；继续加参会破坏所有子类与测试桩 | 定义 `OptimizationContext`（可选字段）并加**可选** `context` 关键字参数；旧 3 参路径保留；`IOptimizer` 2 参 Protocol 不动。Step 3 决定是否本批引入 |
| C4 | **约束逻辑在 `BaseOptimizer._apply_constraints`** | BL/MVO 用 cvxpy 内部约束，HRP 用后投影；D3 行业/换手/跟踪误差无处安放 | 抽出 `ConstraintSpec`（箱体 + 行业上限 + 换手 + 跟踪误差 + 数据引用）；凸优化器映射为 cvxpy 约束；HRP 明确为「后投影近似」 |
| C5 | **市值数据由引擎直取** | BL 市值先验若直接读 `dm.mktcap`，优化器耦合 `DataManager` | `PriorProvider` 可调用对象（`equal` / `market` / `zero`）；引擎仅在 `mktcap` 可用时注入 market provider；优化器只依赖 provider 协议（Ports & Adapters 思路，A15） |

### 14.3 易扩展升级路径

**工厂现状（关键事实）**：`core/registry.py` 已有 `PluginRegistry` + `register_optimizer` 装饰器（L47-172 / L236-254）；`engine_plugins.RegistryPlugin` 已注册 4 个内置优化器（L297-357）；但**引擎实际走 `build_optimizer` 硬编码 map**（`engine_v2 L320`），`RegistryPlugin` 仅被 `tests/test_engine_plugins.py` / `tests/test_mypy_layera_smoke.py` 引用 → **注册中心处于休眠状态**。成熟插件系统先例是 pluggy 的 hookspec/plugin manager（pytest 1400+ 插件，A16）；但引入插件系统需要稳定 hook 契约与初始化顺序，本批不重构（A14 模块边界原则）。

| 路线 | 内容 | 风险 | 建议 |
|---|---|---|---|
| **R1（本批）** | 仅在 `build_optimizer` 增加 `hrp` / `black_litterman` 分支；Registry 保持现状；登记「统一工厂」技术债 | 低 | **推荐**；不夹带工厂重构 |
| **R2（后续独立批）** | 让 `build_optimizer` 委托 `PluginRegistry`（内置注册 + 外部注册），删除硬编码 map | 中（循环导入/初始化时机/既有测试） | 独立 T1 批次；P-046b 不碰 |
| R3（不推荐） | 在 `portfolio.py` 再建本地注册表 | 高（三套工厂） | 否 |

**组件化建议**：
- HRP 拆三个纯函数：`correlation_distance`（两级距离）、`quasi_diagonal_order`（`linkage(single)`+`leaves_list`）、`recursive_bisection`（保序二分/α）；`HRPOptimizer` 只做薄适配。未来层次类方法（HERC/NCO 等）可复用前两层，不在本批实现。
- BL 拆：`posterior_returns`（纯函数）、`ViewSet`（P/Q/Ω/confidence）、`PriorProvider`；未来 Idzorek 置信度、因子派生观点、稳健 BL 均可复用。
- 诊断：优先复用现有 `message`/`method`；若需后验收益等中间量，用可选 `metadata` 映射，避免持续给冻结的 `OptimizationResult` 加字段。

### 14.4 计算性能与高维（实测，量级参考）

**表 A：全维协方差 vs 选中子集（LedoitWolf + PSD，T=60）**

| N | 全维 `estimate_cov` | 子集 50 | 倍数 |
|---|---|---|---|
| 200 | 0.015 s | 0.001 s | ~15× |
| 500 | 0.150 s | 0.001 s | ~150× |
| 1000 | 0.426 s | 0.002 s | ~213× |

**表 B：HRP 距离链 + 聚类（`pdist` + `linkage(single)`）**

| N | `pdist(D)` | `linkage`+`leaves` | 合计 | condensed 内存 |
|---|---|---|---|---|
| 200 | 0.031 s | 0.001 s | 0.032 s | 0.15 MB |
| 500 | 0.016 s | 0.001 s | 0.018 s | 1.0 MB |
| 1000 | 0.127 s | 0.003 s | 0.130 s | 3.8 MB |

> 表 B 为单次运行；N=200 与 N=500 的 `pdist` 计时受噪声影响（量级均 <0.05 s），不作为 SLO。

**表 C：BL 后验两种解法（K=1）**

| N | N×N 逆矩阵解法 | Woodbury（K×K） | 加速 |
|---|---|---|---|
| 200 | 0.063 s | <0.001 s | — |
| 500 | 0.064 s | 0.001 s | ~64× |
| 1000 | 0.294 s | 0.011 s | ~27× |

**四条硬结论**：
1. **引擎在选股前计算全维协方差**：`engine_v2 L1350-1364` 的 `returns_data` 列 = 全部 `dm.stock_codes`，`estimate_cov` 后由 `_cov_for` 再取子集。N=1000 时全维 ~0.43 s，而子集 50 仅 ~0.002 s（~200×）。这是**既有的高维主瓶颈**，不是 BL/HRP 引入；P-046b 不改 SSOT，但必须记录并给出未来「先选股后估协方差」的独立批次入口。**等价性警告（定点复审数值探针确认）**：`sample` / `ewma` 为列向估计器，子集化数学等价（探针：子集==全矩阵子块，`atol=1e-15`）；但默认 `cov_method="ledoit_wolf"` 的收缩强度依赖全截面（`tr(S)/p`、`beta/delta` 汇总所有资产，A18）——探针实测 20 资产 vs 5 资产子集 `shrinkage` **0.9248 vs 1.0**、子矩阵 max|diff| **4.1e-5**，**子集化会改变数值**，不能直接等价替换，须独立批 + 数值影响评估（可能触及 golden/既有权重）。
2. **HRP 距离必须用 `pdist(D)` / `squareform`**：E1 的 3 资产演示用了 `(N,N,N)` 广播；N=1000 时该写法分配 ~8 GB（1000³×8B），不可进生产。实现改为 `pdist(D, metric="euclidean")`，O(N²) 内存（A17）。
3. **BL 必须用 Woodbury/master identity**：`post = Π + τΣPᵀ(τPΣPᵀ+Ω)⁻¹(Q−PΠ)`，只解 K×K；Ω 为对角阵，避免 `inv(Σ)`。K=N（每资产一条观点）时退化为 O(N³)，需在文档声明。**退化守卫**：K=0 直接返回 Π（不进入 Woodbury）；若 `PΣPᵀ` 对角为 0（零方差观点组合）则 Ω 奇异，必须显式处理（抖动/跳过该观点/抛错），不得直接 `solve`。**外部支撑**：Meucci (2010) eq.(20) 给出同一稳定表示（A7）。
4. **有效维度受 `target_count` 约束**：默认 50，BL/HRP 在选中子集上均 <0.01 s 量级；高维风险主要来自 `target_count` 放大与全维协方差。建议加 `HRP_MAX_ASSETS` 守卫（超过阈值告警/抛错可配置）与 N=50/200/500 基准矩阵；**只报告、不设 CI SLO**（与 R8/U-P055-4 口径一致）。

### 14.5 带约束优化

| 方法 | 约束能力 | 结论 |
|---|---|---|
| BL + MVO | cvxpy 箱体约束现成；D3 行业上限/换手/跟踪误差均为凸约束，可自然加入 | **强**：BL 后验 μ 直接进入约束 MVO，是未来 D3 的主路径（Boyd 2017 的 holding/trading/soft constraints 框架可复用，A13；cvxpy E4） |
| HRP | 非凸层次分配；`_apply_constraints` 是**后投影**，会改变层次权重与风险平价性质 | **弱**：严格约束需「约束风险平价 / 以 HRP 为先验的 QP / 迭代投影」；P-046b 必须声明为近似，不得宣称 D3 支持（A13 §4.4-4.6 仅覆盖凸约束，不适用于 HRP 层次分配） |
| 现有箱体 | `_apply_constraints` 上限型只截断留现金；可行型二分缩放 | 保留；HRP 后投影现金残差需测试 |

**建议**：本批只定义 `ConstraintSpec` 数据结构与箱体映射（不实现 D3），使未来 D3 不破坏优化器签名；HRP 的约束语义写入 DESIGN 限制节。

### 14.6 多阶段动态规划边界

- 当前引擎是**单期再平衡**：每个调仓日优化器输出目标权重，无状态转移、交易成本、 regime 概率。
- 多阶段 DP 需要：状态（当前权重/成本基础/regime）、动作（目标权重）、转移（收益/成本）、目标（多期效用）、求解器（SDP/MPC/场景树）。这些**不属于 BL/HRP**。
- **架构边界**：优化器保持**无状态、单期、纯函数**；未来新增 `PortfolioPolicy` / `MultiPeriodPlanner` 层，在节点上调用单期优化器。`OptimizationContext` 可为未来状态预留字段，但本批不引入 DP 逻辑、不改 `OptimizerConfig` 为有状态对象。**外部先例**：Boyd et al. (2017) 明确区分 single-period 与 multi-period 优化，多期规划「只执行第一步」的 MPC 口径（A13 §5）。
- 与 P-057（regime）/P-051c（生命周期）的衔接放在未来策略层，不在本批。

### 14.7 对 §6 方案矩阵的修订

| 原方案 | 修订 | 理由 |
|---|---|---|
| B2（继承 MVO） | **B2'（组合：估计器 + 任意 BaseOptimizer）** | C1 松耦合；BL+min_variance/risk_parity 可复用 |
| H1（论文逐字实现） | **H1'（三纯函数 + 薄适配 + `pdist`）** | 复用/性能；避免 O(N³) 广播 |
| P2（市值先验） | 保留，但改为 **`PriorProvider("market")`** | 解耦 DataManager |
| D3-B（延后） | 保留，增加 **`ConstraintSpec` 钩子 + HRP 约束限制声明** | 未来升级不破签名 |
| DoD | 增 **A-P046b-9（性能基准报告）** / **A-P046b-10（架构决策落档）** | 见 §8 |

### 14.8 新增缺口（G-P046b-12..17）

| ID | 缺口 | 证据 |
|---|---|---|
| G-P046b-12 | BL 继承耦合 + `OptimizerConfig` 单块膨胀 | §14.2 C1/C2；`portfolio.py L434-L502` |
| G-P046b-13 | 双工厂：`build_optimizer` 实际生效，`PluginRegistry` 休眠 | `engine_v2 L320`；`engine_plugins L297-357`；仅测试引用 |
| G-P046b-14 | 引擎 3 参位置接口，无 `OptimizationContext` | `engine_v2 L78-100/L1366` |
| G-P046b-15 | 无性能基准/高维守卫；全维协方差先于选股 | §14.4 表 A；`engine_v2 L1350-1364` |
| G-P046b-16 | 无 `ConstraintSpec`；HRP 后投影语义未定义 | §14.5；`portfolio.py L278-294/L549` |
| G-P046b-17 | 无多阶段边界与 policy 缝 | §14.6；当前单期循环 |

### 14.9 新增未决（U-P046b-12..17）

| ID | 未决项 | 选项 | 当前倾向 |
|---|---|---|---|
| **U-P046b-12** | BL 落地形态 | 继承 MVO / **组合委托** | **组合（B2'）**；估计器纯函数 |
| **U-P046b-13** | 工厂统一时机 | 本批接 Registry / **本批走 map + 后续独立批** | **后续独立批**；P-046b 只加 map 分支 |
| **U-P046b-14** | 是否引入 `OptimizationContext` | 本批最小引入 / 延后 | **Step 3 决定**；若引入则保持旧 3 参兼容 |
| **U-P046b-15** | 性能基准与守卫 | 只报告 / 加守卫 / 设 SLO | **报告 + `HRP_MAX_ASSETS` 可配置守卫；不设 SLO** |
| **U-P046b-16** | HRP 带约束语义 | 后投影近似 / 约束风险平价 | **本批后投影 + 明确限制**；严格约束归后续 |
| **U-P046b-17** | 多阶段 DP 边界 | 优化器内实现 / **独立 policy 层** | **独立 policy 层；优化器保持单期纯函数** |

### 14.10 结论与 Step 3 输入

- 现有调研的**正确性/证据**充分（Step 2 PASS），但**架构与性能**未展开；按原方案直接落码会留下「继承耦合 / 配置膨胀 / 工厂漂移 / 高维无守卫」四项技术债。
- Step 3 DESIGN 必须逐项裁决 U-P046b-12..17，至少落实：B2' 组合、嵌套配置、HRP 三纯函数 + `pdist`、BL Woodbury、`ConstraintSpec` 钩子、单期/多阶段边界、性能基准口径。
- 本补充**零代码变更**；不改变 §1-§13 的任何事实结论。

### 14.11 Step 3 设计原则（建议写成 DESIGN 硬约束）

> 外部锚点映射见 §5.2；以下原则在 Step 3 作为硬约束。

| # | 原则 | 机械验收点（Step 7 CHECKLIST 可引用） |
|---|---|---|
| P1 | **估计器与优化器分离** | `black_litterman_posterior` / HRP 三函数可在不构造优化器时单测；优化器类只做适配 |
| P2 | **组合优于继承** | `BlackLittermanOptimizer` 不继承 `MeanVarianceOptimizer`；被委托优化器可注入 |
| P3 | **方法级配置隔离** | `BLConfig` / `HRPConfig` 嵌套；非本 method 字段不读取；`config_v2` 零改动 |
| P4 | **单一工厂路径** | 本批只改 `build_optimizer`；不新增第三套注册表；Registry 统一另立批 |
| P5 | **接口向后兼容** | 旧 3 参 `optimize_with_diagnostics` 调用不改；`IOptimizer` 2 参 Protocol 不动 |
| P6 | **约束即数据** | `ConstraintSpec` 与优化器解耦；凸优化器映射 cvxpy；HRP 声明后投影近似 |
| P7 | **单期纯函数边界** | 优化器无状态；多阶段 DP 归未来 `PortfolioPolicy`，不写入 `OptimizerConfig` |
| P8 | **算法复杂度显式** | HRP 用 `pdist`（O(N²) 内存）；BL 用 Woodbury（K×K 解）；禁止 `inv(Σ)` 与 `(N,N,N)` 广播；性能基准只报告不设 SLO |

| 反模式（禁止） | 检测方式 |
|---|---|
| `BlackLittermanOptimizer(MeanVarianceOptimizer)` 继承 | AST/读码断言基类为 `BaseOptimizer` |
| `np.linalg.inv(cov)` 求后验 | Grep `inv(` 在 BL 路径命中 |
| `(N,N,N)` 距离广播 | 读码断言使用 `pdist`/`squareform` |
| `portfolio.py` import `DataManager` | import-linter/读码断言 portfolio 不依赖数据层 |
| 给 `OptimizerConfig` 加 10+ 个 method 专属平铺字段 | 读码断言嵌套配置 |
| 在 `build_optimizer` 之外再建注册表 | Grep 注册装饰器/字典 |

---

## 15. 状态链

- **2026-11-23**：用户「分析下一步任务」→ 选择「台账收口 + P-046b」；P-055 台账收口完成（提交 `8f8b912` + CI `45132788783` 四 job 全绿）。
- **2026-11-23**：**Step 1 调研落盘（本文）**——代码事实 @`8f8b912`；E1 HRP 距离链复现；E2 BL 后验 τ 消去/极限；外部锚 A1-A6；缺口 G-P046b-1..11；方案矩阵 B1-B4 / P1-P3 / V1-V3 / H1-H3 / D3-A/B；未决 U-P046b-1..11。
- **2026-11-23**：**Step 2 异构复审 PASS**（[REVIEW_p046b_step2](REVIEW_p046b_step2_research.md)，**GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash**）：12 组代码事实逐行号命中；E1/E2 数值链独立重写重放 10/10 PASS；外部锚 A1-A6 与已取全文逐字一致；AST P-029 口径 = **22**、`-k p046` = **55** 复核一致；无 P-046c/D3/策略层夹带。**发现 1 P2 + 3 P3，当轮全修并回写本文**——F-R1（`cov_shrinkage` 删除须声明 `config_v2` FROZEN 冻结例外）/ F-R2（单观点倾斜为**一般性质**，随随机 Σ 复算 non-view tilt ≈ 8.9e-16，§4.2 订正）/ F-R3（I-P046b-3 叶序口径收窄为簇保序变体）/ F-R4（§4.1 A5 引用歧义订正）。
- **2026-11-23**：**Step 1 补强：架构与性能补充调研**（§14）——松耦合 5 处（继承→组合、配置隔离、`OptimizationContext`、`ConstraintSpec`、`PriorProvider`）；工厂现状核实（`build_optimizer` 生效、`PluginRegistry` 休眠）；性能实测（全维 cov vs 子集 50：N=1000 **0.426 s vs 0.002 s**；HRP `pdist+linkage` N=1000 **0.130 s**；BL N×N 逆 vs Woodbury N=1000 **0.294 s vs 0.011 s**）；新增 **G-P046b-12..17 / U-P046b-12..17**；**零代码变更**。
- **2026-11-23**：**外部锚点扩至 A1-A19**（§5）——新增 A7 Meucci 2010（BL 稳定表示 eq.20，A 全文）/ A8 Walters 2014（B）/ A9 Riskfolio-Lib（HRP/HERC/NCO/BL，A 官方文档）/ A10 skfolio（Prior 与 optimization 分离，A 文档+arXiv）/ A11 HERC（B）/ A12 NCO（B）/ A13 Boyd 2017（单期/多期凸优化，A 全文）/ A14 Parnas 1972（模块化，A 全文）/ A15 Cockburn 2005（Ports & Adapters，A 全文）/ A16 pluggy（插件管理，A 官方）/ A17 scipy pdist / A18 sklearn LW / A19 PyPortfolioOpt HRP；新增 §5.1 社区案例对照与 §5.2 锚点-原则映射。
- **2026-11-23**：**A7-A19 定点复审 PASS**（[REVIEW_p046b_step2 §6](REVIEW_p046b_step2_research.md)，GLM ≠ 作者）：13/13 锚点核验（A9 部分核验 + 口径标注；A8/A11/A12 维持 B 级未越界）；**0 P1/P2 + 3 P3 引用精化当轮回写**——F-R5（A13 正式版 1-76 vs arXiv v1 页眉 1-74）/ F-R6（A7 去未核页码）/ F-R7（A9 枚举口径标注 + A17 本轮直抓闭合）；**A18 升级为数值探针**（LW `shrinkage` 0.9248 vs 1.0、max|diff| 4.1e-5；sample/EWMA 列向不变），§14.4 硬结论 1 证据增强。
- **2026-11-23**：**Step 3 DESIGN 完成**（[DESIGN_p046b_bl_hrp](DESIGN_p046b_bl_hrp.md)）——U-P046b-1..17 全部关闭；D1-D20 / I1-I12；BL 组合式（纯估计器 + 共享 `_solve_mean_variance`，不继承）；HRP 三纯函数 + `pdist`；嵌套 `BLConfig`/`HRPConfig`；`warning_kind` + 引擎 `ZeroVariance`；遗留四项修复；测试映射 23 例；门禁目标 1463/78/22/160/322/158/51/19/13。**零代码变更**。
- **2026-11-23**：**Step 4 DESIGN 异构复审 PASS**（[REVIEW_p046b_step3_design](REVIEW_p046b_step3_design.md)，GLM-5.3-Flash ≠ 作者）——§13 十项 8 直接 PASS + 2 项修订后 PASS；门禁基线 7 组实测全吻合（black 319 / AST 22·30 / mypy 159·0 / collect 1441·55·120·22）；数值探针 BL 7/7 + HRP 论文链逐位；**2 P2 + 6 P3 当轮全修**（F-4-1 全零 cov 等权特判 + `zero_vol`、F-4-2 HRP `_precheck` 三分支规格化；F-4-3 `import math` 定案、F-4-4 explicit 先验多余资产 warning、F-4-5 `np.divide` 防警告、F-4-6 叶序 N<2 守卫、F-4-7 bench 脚本 mypy/black 义务、F-4-8 本文 §4.1 权重行订正）。DESIGN §4/§5/§6/§10/§11 已按修订落字，门禁目标维持不变。
- **2026-11-23**：**Step 5 IMPL 落盘**（[IMPL_p046b_bl_hrp](IMPL_p046b_bl_hrp.md)）——T1-T12 任务拆解；接口签名 + 回退点；低效排除表 11 行；**新增源码级锚点 A20-A26**（pypfopt 1.5.5 / skfolio 1.14.4 / Riskfolio-Lib 7.4.1，PyPI wheel 逐字 + 运行时对拍）；跨实现读数：BL 后验/τ 消去/隐含权重逐位一致，**HRP 第二级距离 `pdist(d)` vs `squareform(d)` 叶序分歧、权重 max|Δ|=0.0152 → 对拍边界成文**；pypfopt 1.5.5 × pandas 3.0.3 HRP 运行时 `TypeError`（A25）→ 仅手工对拍；测试 23 例红→绿计划；门禁命令。F-5-1..F-5-3 登记。**零代码变更 / 未提交**。
- **2026-11-23**：**Step 6 实施文档复审 PASS**（[REVIEW_p046b_step5_impl](REVIEW_p046b_step5_impl.md)，GLM-5.3-Flash ≠ 作者）——规范两大硬约束全过：**版本存在性**（3 包 wheel METADATA 实读全 T1 命中：pyportfolioopt 1.5.5 / skfolio 1.14.4 / riskfolio-lib 7.4.1；运行时 pandas 3.0.3 / numpy 2.4.6 / scipy 1.17.1）+ **签名可实现性**（14 项接口可实现、新符号全域 grep 0 冲突）；**锚点行号机械核验 16/16 PASS**（A20-A26 声明的文件+行号+逐字要点）；DESIGN↔IMPL 对齐 D1-D20→T1-T12 无悬空；门禁算术复核全过；**0 P1 / 0 P2 / 4 P3 当轮全修**（F-6-1 派生接口 `_upper_result` 补登 F-5-4、F-6-2 warning_kind 回退点措辞、F-6-3 MinVariance 零改动声明、F-6-4 upper+zero_vol 组合 `ZeroVariance` 优先）；门禁目标不变。
- **2026-11-23**：**Step 7 CHECKLIST 落盘**（[CHECKLIST_p046b_bl_hrp](CHECKLIST_p046b_bl_hrp.md)）——**70 项 DoR/DoD**（A 8 / B 10 / C 11 / D 9 / E 12 / F 6 / G 9 / H 5）；RULE-1 实测列 0 预填（68 `[待 Step 9]` + 1 `[待 Step 8]` + 1 `[待 Step 10]`）；RULE-2 机械计数 70 且序号连续；门禁目标冻结（1464 collect / 1463 passed / 78 / 22 / 120 / 160 / 322 / 158 / 51 / 19 / 13 / 22·30 / 3 kept / 0）；§10 范围守卫 N1-N10。**零代码变更 / 未提交**。
- **2026-11-23**：**Step 8 一致性复审 PASS**（[CHECKLIST_p046b §12](CHECKLIST_p046b_bl_hrp.md)，GLM-5.3-Flash ≠ Step 7 作者）——**机械校验器 78/78**（初跑 76/78，2 项校验器正则误报修正后全过）；规范九项全过；D1-D20→T1-T12→CHECKLIST 70 项无悬空；I1-I12↔E1-E12 双射、U1-U17=17/17、F 链 0 missing、A20-A26+版本号双登记一致；H1 回填 ✅。
- **2026-11-23**：**Step 9 TDD PASS**——红态 2 收集错误（`ImportError: BLConfig/HRPConfig`）→ 绿态全量 **1463 passed + 1 skipped**（collect **1464**）/ `-k p046` **78** / golden **22** / `-k p054` **120** / mypy **160·0** / black **322** / AST **22·30** / `lint-imports` **3 kept** / `uv lock` **0**；外部锚 A20-A26 的对拍边界按 F-5-3 执行（pypfopt 仅手工对拍、未进 CI）；**F-S9-P046b-1** 实现细化（HRP 部分零方差先过滤子域）见 DESIGN D11/§6.4 与 IMPL §3.7。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS**（[CHECKLIST_p046b §14](CHECKLIST_p046b_bl_hrp.md)，审计基座 GLM-5.3-Flash ≠ 作者）——Phase 0-4 全过；门禁独立重放全绿；A20-A26 对拍边界（F-5-3）执行无越界；数值探针 6/6；**0 P0-P2 + 1 观察 O-R5-P046b-1**。
- **H5 已执行并批次关闭（2026-11-23）**：提交 `f272638` + CI run `45163412591` 四 job 全绿；CHECKLIST 70/70。**P-046b 批次关闭（Step 1-10 全通过）**。
