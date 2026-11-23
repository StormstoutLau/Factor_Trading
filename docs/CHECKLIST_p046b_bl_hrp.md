# CHECKLIST：P-046b BL / HRP 优化器（组合优化扩展第二批）

> **批次**: P-046b · **T1**（`core/portfolio.py` / `core/config.py` / `core/engine_v2.py` 诊断分流 + 2 个新测试文件 + 3 个既有测试增例 + 1 个基准脚本；BL/HRP 均 opt-in，golden 22 预期零漂移）
> **上游**: [DESIGN_p046b](DESIGN_p046b_bl_hrp.md)（D1-D20 / I1-I12 / §10 测试 / §12 门禁）+ [REVIEW_p046b_step3_design](REVIEW_p046b_step3_design.md)（F-4-1..F-4-8）+ [IMPL_p046b](IMPL_p046b_bl_hrp.md)（T1-T12 / §2 签名回退 / §4 A20-A26 / §5 低效排除 / §6 红→绿 / §9 F-5-1..F-5-4）+ [REVIEW_p046b_step5_impl](REVIEW_p046b_step5_impl.md)（F-6-1..F-6-4）
> **状态**: **P-046b 批次已关闭（2026-11-23，Step 1-10 全通过）**——Step 8 一致性复审 PASS（§12）／Step 9 TDD PASS（§13）／Step 10 ADD 审计 + RULE-5 异构终审 PASS（§14，审计基座 GLM-5.3-Flash ≠ 作者）；提交 `f272638` + CI run `45163412591` 四 job 全绿；实测列 **70/70 ✅**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 8]` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**；Step 10 回填后为 **70 × ✅**
> **行号口径**: 本文件锚 `8f8b912`；Step 9 落码后行号失效，实测证据改用「文件 + 符号名 + 用例名」
> **基线读数（@`8f8b912`，P-055 关闭）**: pytest collect **1441**（1440 passed + 1 skipped）/ `-k p046` **55** / `-k golden` **22** / `-k p054` **120** / mypy **159 files · 0** / black `--check .` **319** / `tests/*.py` **156** / `core/*.py` **51** / `live/**/*.py` **19** / `services/*.py` **13** / AST `except Exception` core 外 **22**、core **30** / `lint-imports` **3 kept** / `uv lock --check` exit **0**
> **目标读数（Step 7 冻结）**: pytest collect **1464**（**1463 passed + 1 skipped**）/ `-k p046` **78** / `-k golden` **22（零重录）** / `-k p054` **120** / mypy **160 files · 0**（+bench 脚本，CI 路径含 `scripts`）/ black **322**（+2 测试 +1 脚本）/ `tests/*.py` **158** / `core/*.py` **51**（不新增 core 模块）/ `live/**/*.py` **19** / `services/*.py` **13** / AST **22 · 30**（不新增裸 except）/ `lint-imports` **3 kept** / `uv lock --check` exit **0**

---

## 1. A 组：配置与类型契约（8 项，锚 DESIGN §4 + IMPL T1/T2）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `BLConfig` 字段 `prior: str="equal"` / `prior_returns: dict[str,float]\|None=None` / `views: dict[str,float]\|None=None` / `tau: float=0.05`；`__post_init__` 校验：prior 三值枚举、`0<tau≤1`、`explicit` 必有 `prior_returns`、mapping 键均为 str、值 `math.isfinite` | T1 落码 | 读码 + REPL 探针（5 非法/3 合法构造） | ✅ [config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L272-L294) 字段+校验齐备；Step 9 探针 5 非法构造全 ValueError、合法构造通过 |
| A2 | `HRPConfig` 字段 `linkage: str="single"` / `max_assets: int=2000`；`linkage!="single"` 与 `max_assets<1` 均抛 `ValueError` | T1 落码 | 读码 + REPL 探针 | ✅ [config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L297-L308)；探针 linkage="average" 与 max_assets=0 均 ValueError |
| A3 | `OptimizerConfig` 末尾新增 `bl` / `hrp` 两字段（`field(default_factory=...)`）；原 `__post_init__` 四校验逐字不变；`core/config_v2.py` **零 diff** | A1/A2 落码 | 读码 + `git status --short core/config_v2.py` 空 | ✅ `bl`/`hrp` 末字段（default_factory）；`git status --short core/config_v2.py` **空**；既有四校验零改动 |
| A4 | `OptimizationResult` **末尾**新增 `warning_kind: Optional[str]=None`；既有 9 处位置参数构造（portfolio.py）+ 引擎 kwargs 构造均不破（默认 None） | T2 落码 | 读码 + `pytest tests/test_p046_*` | ✅ 末尾 `warning_kind=None`；既有位置构造零改动；定向 40 passed |
| A5 | 公开纯函数签名与 DESIGN §4.3/§5.3 一致：`black_litterman_posterior(cov, prior, views, *, tau=0.05, omega=None)`、`correlation_distance(cov)`、`quasi_diagonal_order(dist)`、`recursive_bisection(cov, order)`；均为无状态纯函数 | T3/T6 落码 | 读码 + `inspect.signature` 探针 | ✅ inspect.signature 实测：`black_litterman_posterior(cov, prior, views, *, tau=0.05, omega=None)` / `correlation_distance(cov)` / `quasi_diagonal_order(dist)` / `recursive_bisection(cov, order)` |
| A6 | 两优化器 `optimize_with_diagnostics(factor_scores, returns=None, cov_matrix=None)` 3 参；`BaseOptimizer.optimize` 薄包装签名不变；`core/interfaces.py` 的 `IOptimizer` 2 参 Protocol **零 diff** | T5/T7 落码 | 读码 + `git status --short core/interfaces.py` 空 | ✅ 两优化器 3 参签名；`git status --short core/interfaces.py` 空 |
| A7 | 派生接口登记完整：`_solve_mean_variance(..., *, feas=None)` 与 `_upper_result(cfg, selected, method)`；`MinVarianceOptimizer` **零改动**（含 upper 内联消息）；`_upper_result` 仅 MVO/BL/HRP 消费（F-5-1/F-5-4/F-6-3） | T4 落码 | 读码 + `git diff core/portfolio.py` 中 MinVariance 区段为空 | ✅ `_solve_mean_variance(..., *, feas=None)` + `_upper_result(cfg, selected, method)`；`git diff -U0 core/portfolio.py` 无 ± 行含 MinVariance |
| A8 | 导入齐备：`core/config.py` 有 `import math`；`core/portfolio.py` 有 `import math`、`typing.Mapping/Sequence`、`scipy.cluster.hierarchy.{leaves_list,linkage}`、`scipy.spatial.distance.pdist`；无未使用导入（black/mypy 不报） | T1/T3/T6 落码 | 读码 + mypy/black | ✅ config.py `import math`；portfolio.py math/Mapping/Sequence/leaves_list/linkage/pdist；mypy 160·0 + black 322 通过 |

## 2. B 组：BL 实现（10 项，锚 DESIGN §5 + IMPL T3/T5）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | `_bl_prior`：`prior="equal"` → `δΣ(1/N)`（`δ=cfg.risk_aversion`，不硬编码 25/1.2）；`δ<=0` 或非有限 → `ValueError`；`"zero"` → 全零 Series | A1/A5 落码 | 读码 + 闭式探针 | ✅ equal→δΣ(1/N)（δ=risk_aversion，无硬编码）；zero→全零；δ≤0 ValueError；BL #1/#4 |
| B2 | `_bl_prior`：`"explicit"` 缺选中资产 → `ValueError`；`prior_returns` 含未入选资产 → `logger.warning` 后丢弃（F-4-4，与 views 过滤对称） | B1 落码 | 读码 + `caplog` 用例（BL #7） | ✅ explicit 缺资产 ValueError（#7）；多余资产 warning 后丢弃（F-4-4） |
| B3 | `black_litterman_posterior`：默认 `Ω=diag(τPΣPᵀ)`；**Woodbury + K×K `solve`**（全文件无 `np.linalg.inv`）；K=0 直接返回 prior（不进入 solve）；tau 越界抛 `ValueError` | A5 落码 | 读码 + grep `np.linalg.inv` 为空 + BL #1/#4 | ✅ 默认 Ω=diag(τPΣPᵀ)；Woodbury + K×K solve；`np.linalg.inv` 0 命中；K=0 早退；tau 越界 ValueError；BL #1/#4 |
| B4 | 异常路径：未知观点资产 → `ValueError`；`PΣPᵀ` 任一对角 `≤0`/非有限 → `ValueError`；omega 非 K 个正有限数 → `ValueError`；后验非有限 → `ValueError` | B3 落码 | 读码 + BL #5/#6 | ✅ 未知观点资产/零观点方差/omega 非正/后验非有限 均 ValueError；BL #5/#6 |
| B5 | `BlackLittermanOptimizer(BaseOptimizer)`：**不继承** `MeanVarianceOptimizer`；先验/观点/后验后调用 `_solve_mean_variance(..., "black_litterman", feas=feas)`；结果 `method=="black_litterman"` | B1-B4 落码 | 读码 + BL #9 | ✅ 组合非继承（#9 `assert not isinstance(MeanVarianceOptimizer)`）；method="black_litterman" |
| B6 | 观点过滤在优化器层：`views` 仅保留 `selected`；未入选 warning 后丢弃；无观点时后验=先验（K=0 路径） | B5 落码 | 读码 + BL #1/#8 | ✅ views 仅保留 selected，未入选 caplog warning「已丢弃」（#8）；无观点=先验（#1） |
| B7 | 三分支：`empty` → `_empty_result("black_litterman")`；`upper` → `infeasible_kind="upper"` + `cash_residual` + message（method 字段正确）；`lower` → `_precheck` 抛 `InfeasibleConstraintError` 原样上抛 | B5 落码 | 读码 + BL #10 | ✅ upper→infeasible_kind="upper"/cash_residual=0.4；lower 原样抛 `InfeasibleConstraintError`；empty→`_empty_result`（#10） |
| B8 | 数学性质逐条成立：K=0 逐位等于先验；默认 Ω 下 τ 消去（0.05 vs 0.5）；Ω→0 观点资产→Q、Ω→∞→先验；单观点闭式 `π+Σe_i(Q−π_i)/(2Σ_ii)` | B3/B5 落码 | BL #1-#5 | ✅ K=0 逐位=先验；τ 消去；Ω 极限；单观点闭式（#1-#5） |
| B9 | **F-R2 一般性**：随机 5×5 Σ（seed=42）下 `(δΣ)⁻¹post` 非观点资产位移 `<1e-10`、观点资产 `>1e-8` | B8 落码 | BL #3 | ✅ 随机 5×5 seed=42：非观点位移 <1e-10、观点资产 >1e-8（#3） |
| B10 | `tests/test_p046b_bl.py` 落盘 **11 例**（名称见 IMPL §6.2）；工厂 `black_litterman`/`bl` 均返回 BL 实例；未知 method 仍 `ValueError`（消息含合法值） | B1-B9 落码 | `pytest --collect-only -q tests/test_p046b_bl.py` = 11 + BL #11 | ✅ test_p046b_bl.py collect **11**；black_litterman/bl 同实例；未知 method ValueError「合法值」（#11） |

## 3. C 组：HRP 实现（11 项，锚 DESIGN §6 + IMPL T6/T7）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | `correlation_distance`：`d=sqrt(0.5*(1-ρ))`；零方差资产 corr 行/列=0、对角=1；`clip(-1,1)`；返回与 `cov` 同 index/columns 的 DataFrame；非方阵抛 `ValueError` | T6 落码 | 读码 + HRP #1 | ✅ d=√(0.5(1−ρ))、零方差 corr=0/对角 1、clip、同索引；HRP #1 atol=1e-4 |
| C2 | `quasi_diagonal_order`：`pdist(d)` → `linkage(method="single")` → `leaves_list`；**N<2 不调用 scipy**（N=1 → `[0]`，N=0 → `[]`，F-4-6） | C1 落码 | 读码 + HRP #2/#4 | ✅ pdist→linkage(single)→leaves_list；N<2 守卫；HRP #2/#4（叶序 [2,0,1]；N=1 [0]） |
| C3 | `recursive_bisection`：保序二分（`mid=lo+(hi-lo)//2`）、逆方差簇权重、`α=1−V₁/(V₁+V₂)`、`w[lo:mid]*=α` / `w[mid:hi]*=1−α`；返回原始顺序 Series；`Σw=1` | C2 落码 | 读码 + HRP #3 | ✅ 保序二分 + 逆方差簇权重 + α 公式；测试内独立复算 1e-12；Σw=1（HRP #3） |
| C4 | `_cluster_var` 退化：`np.divide(1.0, diag, out=zeros, where=diag>0)`（F-4-5，无 RuntimeWarning）；簇内全零 → 等权；`v<=0`/非有限 → 0.0；两簇和 `≤0` → `α=0.5` | C3 落码 | 读码 + HRP #3/#5 | ✅ `np.divide(where=diag>0)` 无警告；簇内全零等权；v≤0→0；两簇和≤0→α=0.5（HRP #3/#5） |
| C5 | `HRPOptimizer(BaseOptimizer)` 正常路径：`correlation_distance` → `quasi_diagonal_order` → `recursive_bisection` → `_apply_constraints` 后投影；结果 `method=="hrp"` | C1-C4 落码 | 读码 + HRP #8 | ✅ distance→order→bisection→`_apply_constraints`；method="hrp"（HRP #8） |
| C6 | **F-4-1 全零特判**：`diag` 全零/非有限 → **等权 1/N**（跳过聚类）+ `message="zero_vol"` + `warning_kind="zero_vol"`；部分零方差 → 零方差资产权重 0、无 NaN、Σw=1 | C5 落码 | HRP #5 | ✅ 全零→1/3 等权 + message/warning_kind="zero_vol"；部分零→先过滤子域再 HRP、回填 0（F-S9-P046b-1）：实测 [0,0.64,0.36]、A=0、Σw=1、无 NaN、warning_kind=None（HRP #5） |
| C7 | **F-4-2 三分支**：`empty` → `_empty_result("hrp")`；`upper` → `infeasible_kind="upper"` + `cash_residual` + message；`lower` → `InfeasibleConstraintError` 原样上抛 | C5 落码 | 读码 + HRP #7 | ✅ empty→`_empty_result`；upper→infeasible_kind="upper"/cash_residual=0.4/message；lower→`InfeasibleConstraintError`（HRP #7） |
| C8 | `max_assets` 守卫：`n > cfg.hrp.max_assets` → 抛 `InfeasibleConstraintError`（`ValueError` 子类，引擎归 `config`）；**在距离矩阵之前触发**（F-5-2） | C5 落码 | 读码 + HRP #6 | ✅ n>max_assets → `InfeasibleConstraintError`（ValueError 子类）且在距离矩阵前触发（HRP #6） |
| C9 | 退化边界：N=1 → 权重 `[1.0]`；N=0 → empty；`HRPConfig.linkage!="single"` 在配置期抛 `ValueError`；与 RiskParity 零方差语义不混淆 | A2/C6 落码 | 读码 + HRP #4 | ✅ N=1→[1.0]；N=0→empty；linkage≠single 配置期 ValueError；RiskParity zero_vol 独立（D4/HRP #4） |
| C10 | `tests/test_p046b_hrp.py` 落盘 **9 例**（名称见 IMPL §6.2）；论文 `d`/`d̃` 逐位（`atol=1e-4`）、`Z` 合并距离与叶序 `[2,0,1]`、测试内独立复算 α（不硬编码权重） | C1-C9 落码 | `pytest --collect-only -q tests/test_p046b_hrp.py` = 9 + HRP #1-#3 | ✅ test_p046b_hrp.py collect **9**；论文 d/d̃ atol=1e-4；Z 合并距离与叶序 [2,0,1]；α 测试内复算 |
| C11 | **对拍边界（F-5-3）**：与 pypfopt 仅对 BL 后验 / 第一级 `d` / 给定叶序 α；**无任何用例断言叶序或权重与 `squareform(d)` 实现逐位相等**（随机 6×6 实测 max\|Δw\|=0.0152） | C10 落码 | 读码用例 + IMPL §4.2/§4.3 | ✅ 用例无叶序/权重与 squareform(d) 逐位断言；IMPL §4.2 maxΔw=0.0152；pypfopt 仅手工对拍 |

## 4. D 组：工厂、引擎与遗留四项（9 项，锚 DESIGN §7/§8 + IMPL T8-T10）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | `build_optimizer` map 新增 `black_litterman` / `bl` / `hrp` 三键；既有 `equal_weight`/`min_variance`/`mean_variance`/`mvo`/`risk_parity` 行为不变；未知 method `ValueError` 消息仍含 `"合法值"` | T8 落码 | 读码 + `test_p025_day_error_diagnostics` | ✅ map 新增 3 键；既有 5 方法不变；未知 method 消息含「合法值」（BL #11/HRP #9 + test_p025） |
| D2 | 引擎唯一改动：`error_type = "ZeroVariance" if result.warning_kind == "zero_vol" else "InfeasibleConstraints"`；触发条件（`infeasible_kind is not None or message`）、`category`、`retryable=False` 均不变 | D1/T9 落码 | 读码 + engine 新用例 | ✅ 引擎唯一改动 error_type 三元分流；触发条件/category/retryable 不变；test_zero_vol_records_zero_variance 通过 |
| D3 | `_optimize_with_diagnostics` 签名与回退包装（2 参自定义优化器）不变；`category` 仍为 `"config" if kind=="lower" else "optimizer"` | T9 落码 | 读码 + `git diff core/engine_v2.py` 仅 1 处 | ✅ 签名与 2 参回退不变；category 表达式不变；git diff 仅 error_type 块（1 处） |
| D4 | **F-S10-P046-1**：`RiskParityOptimizer` 零方差分支置 `message="zero_vol"` + `warning_kind="zero_vol"`；`risk_contrib<=0` 的 break **不置**；upper 分支保留约束 message、`zero_vol` 仅由 `warning_kind` 承载（F-6-4） | T2 落码 | 读码 + `test_zero_variance_window` 零回归 | ✅ RiskParity zero_vol 分支 message/warning_kind 双置；upper 保留约束 message；test_zero_variance_window 零回归 |
| D5 | **F-S10-P046-2**：`estimate_cov` 有效行 `<2` → `logger.warning`（含 `n_valid` 与 method）；输出数值不变（仍走选定 method + `psd_fix`）；`test_p046_cov.py` 新增 `caplog` 用例 | T10 落码 | 读码 + cov 新用例 | ✅ 有效行<2 warning（含 n_valid/method）；数值不变；test_estimate_cov_degenerate_warns 通过 |
| D6 | **F-S10-P046-3**：`codes` 缺失列 → warning 后丢弃（交集）；返回列 == 交集；docstring 同步为「交集 + warning」（不再写 reindex 补 0） | T10 落码 | 读码 + cov 新用例 | ✅ 缺失列 warning「缺失列已丢弃」+ 交集；返回列==交集；test_estimate_cov_codes_missing_warns 通过 |
| D7 | **F-S9-P046-2**：AST P-029 口径（5 目录 + `cli.py`）基线 **22**、core **30**；本批新增代码**无裸 `except Exception`**、无 `type: ignore` | T9/T10 落码 | AST 命令 + 读码 | ✅ P-029 口径（5 目录 + cli.py）实测 **22**、core **30**；新增代码无裸 except Exception、无 type ignore |
| D8 | `_apply_constraints_legacy` 保留且仅 AC-C-01a 对拍使用；本批零修改、零新调用点 | T4 落码 | 读码 + grep 调用点 | ✅ `_apply_constraints_legacy` 保留；本批零修改；调用点仅 AC-C-01a |
| D9 | 零新运行时依赖：`pypfopt`/`skfolio`/`riskfolio-lib` **不安装、不进 CI**；`pyproject.toml` / `uv.lock` 零 diff；`uv lock --check` exit 0 | T11 落码 | `git status` + `uv lock --check` | ✅ pyproject.toml/uv.lock git status 空；uv lock --check exit 0；无 import pypfopt |

## 5. E 组：不变式（12 项，DESIGN §3.1 I1-I12）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| E1 | **I1** BL 无观点时后验 = 先验（逐位，`1e-12`） | B3 落码 | BL #1 | ✅ BL #1：K=0 后验==先验（atol=1e-12） |
| E2 | **I2** 单绝对观点隐含权重仅观点资产变化；后验经协方差传导（F-R2 口径） | B9 落码 | BL #3 | ✅ BL #3：随机 5×5 隐含权重非观点位移 <1e-10、观点资产 >1e-8 |
| E3 | **I3** 默认 `Ω=τPΣPᵀ` 时 τ 消去（0.05 vs 0.5 逐位一致） | B8 落码 | BL #4 | ✅ BL #4：τ=0.05 vs 0.5 逐位一致 |
| E4 | **I4** `Ω→0` 观点资产→Q；`Ω→∞`→先验 | B8 落码 | BL #5 | ✅ BL #5：Ω=1e-14→观点资产≈Q；Ω=1e14→先验（atol=1e-8） |
| E5 | **I5** 后验有限无 NaN；零观点方差 fail-loud；K=0 不进入矩阵求解 | B3/B4 落码 | BL #1/#6 + 读码 | ✅ BL #1/#6 + 读码：后验有限；零观点方差 ValueError；K=0 不进入 solve |
| E6 | **I6** HRP `d`/`d̃` 与论文 Example 1-2 逐位（`atol=1e-4`）；`linkage(single)` Z 与叶序一致 | C1/C2 落码 | HRP #1/#2 | ✅ HRP #1/#2：d/d̃ atol=1e-4；single linkage Z 与叶序 [2,0,1] 一致 |
| E7 | **I7** HRP 权重非负、`Σw=1`（可行域）、在 `[min_weight, max_weight]` 内 | C5/C6 落码 | HRP #3/#7 | ✅ HRP #3/#7：权重非负、Σw=1、max_weight 箱体生效 |
| E8 | **I8** HRP N=1 → 1.0；全零 → 等权 1/N + `zero_vol`；部分零方差 → 零权重、无 NaN | C6/C9 落码 | HRP #4/#5 | ✅ HRP #4/#5：N=1→1.0；全零→1/N+zero_vol；部分零→A=0、无 NaN、Σw=1（F-S9-P046b-1） |
| E9 | **I9** 默认 `equal_weight` 路径与 golden 22 **零漂移**（零重录） | D1 落码 | `-k golden` + `git status tests/golden/` | ✅ `-k golden` 22 passed；`git status --short tests/golden/` 空 |
| E10 | **I10** `build_optimizer` 未知 method 行为不变；`IOptimizer` 2 参 Protocol 不变 | D1/A6 落码 | 读码 + `test_p025` | ✅ 未知 method 行为不变（「合法值」）；IOptimizer 2 参 Protocol 零 diff |
| E11 | **I11** BL/HRP 均 opt-in；引擎 3 参调用签名不变；默认配置不构建新优化器 | A6/D2 落码 | 读码 + `test_cov_computed_once` 等 | ✅ BL/HRP opt-in；引擎 3 参调用不变；默认 equal_weight 不构建新优化器 |
| E12 | **I12** mypy / black / AST / `lint-imports` / `uv lock --check` 不劣化（G 组复述，不重复计数） | G1-G9 通过 | G 组 | ✅ G 组全过：mypy 160·0 / black 322 / AST 22·30 / lint 3 kept / uv lock 0 |

## 6. F 组：测试交付与 TDD 双要素（6 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| F1 | `tests/test_p046b_bl.py` collect **11**，用例名与 IMPL §6.2 逐项一致 | T12 落盘 | `--collect-only -q` | ✅ `--collect-only -q` = **11**；名称与 IMPL §6.2 逐项一致 |
| F2 | `tests/test_p046b_hrp.py` collect **9**，用例名与 IMPL §6.2 逐项一致 | T12 落盘 | `--collect-only -q` | ✅ `--collect-only -q` = **9**；名称与 IMPL §6.2 逐项一致 |
| F3 | 既有测试增例 **3**：`test_estimate_cov_degenerate_warns` / `test_estimate_cov_codes_missing_warns`（`test_p046_cov.py`）、`test_zero_vol_records_zero_variance`（`test_p046_engine.py`，假优化器注入）；`_make_engine` 增可选 `optimizer_instance` 透传 | T12 落盘 | `--collect-only -q -k p046` | ✅ cov 2 例 + engine 1 例；`_make_engine` 增 `optimizer_instance`；`-k p046` collect 78 |
| F4 | **红→绿记录**：先写 23 例并记录红态读数（`ImportError`/`AttributeError`，收集失败或全红）；实现后记录绿态读数（1463 passed / 1 skipped）；两读数均落 Step 9 报告 | F1-F3 编写 | Step 9 报告（红/绿两读数） | ✅ 红态 2 收集错误 ImportError → 绿态定向 40 / 全量 1463+1；两读数落 §13 |
| F5 | 既有断言零改动：`test_p046_constraints.py` 的 `METHODS` 不加入 BL/HRP；golden 22 零重录；无新增 skip/xfail；`test_p046_cov.py` / `test_p046_engine.py` 既有用例断言零修改 | F1-F3 落盘 | `git diff tests/` + `-k golden` | ✅ METHODS 未加 BL/HRP；golden 22 零重录；无新增 skip/xfail；git diff 既有测试仅 import/helper 签名/透传、断言零改动 |
| F6 | **TDD 双要素**：每条新用例含「目标形态 + 反例/边界形态」（正例与边界各 ≥1），非仅提示词；边界用例覆盖：零方差、N=1、upper/lower、缺资产、Ω 极限 | F4 | 读用例 + Step 9 报告 | ✅ 正例+边界：BL #1/#5/#6/#7/#10；HRP #4/#5/#6/#7；见 §13 |

## 7. G 组：门禁（9 项，Step 7 冻结）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| G1 | pytest 全量** collect 1464 / 1463 passed / 1 skipped**（`MPLBACKEND=Agg` + `.venv\Scripts\python.exe`；偏移须登记 `F-S9-P046b-*`） | A-G 落码 | 全量末行 | ✅ `MPLBACKEND=Agg pytest -q` → **1463 passed, 1 skipped**（collect 1464） |
| G2 | `-k p046` **78**（55 + 23） | F1-F3 落盘 | 命令末行 | ✅ `-k p046` → **78 passed** |
| G3 | `-k golden` **22 passed 零重录**；`git status --short tests/golden/` 空 | 全量落码 | 命令 + `git status` | ✅ `-k golden` → **22 passed**；`git status --short tests/golden/` 空 |
| G4 | `-k p054` **120**（零回归） | 全量落码 | 命令末行 | ✅ `-k p054` → **120 passed** |
| G5 | mypy **CI 同款命令**（`tests.yml` L46，含 `scripts`）→ **160 source files · 0** | T11/T12 落盘 | 逐字命令末行 | ✅ mypy CI 同款 → **160 source files, 0 error** |
| G6 | `black --check .` → **322 unchanged**（+2 测试 +1 脚本），0 reformatted | T11/T12 落盘 | 命令末行 | ✅ `black --check .` → **322 unchanged**（4 个本批文件格式化后复跑，exit 0） |
| G7 | 文件计数：`tests/*.py` **158** / `core/*.py` **51** / `live/**/*.py` **19** / `services/*.py` **13** | 全量落码 | `Get-ChildItem` 计数 | ✅ tests **158** / core **51** / live **19**（递归）/ services **13** |
| G8 | AST `except Exception` core 外 **22**、core **30**；`lint-imports` **3 kept** | D7 落码 | AST 命令 + `lint-imports` | ✅ AST **22·30**；`lint-imports` **3 kept, 0 broken** |
| G9 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | D9 落码 | 命令 + `git diff` | ✅ `uv lock --check` exit **0**；pyproject.toml/uv.lock git status 空 |

## 8. H 组：文档、改动面与提交（5 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| H1 | **三文档对齐**（Step 8）：DESIGN 模块 D1-D20 ↔ IMPL 任务 T1-T12 ↔ 本 CHECKLIST A-H 组无悬空；IMPL 功能点在 CHECKLIST 有验收项；机械校验读数贴出 | 本文件落盘 | Step 8 一致性报告 | ✅ **Step 8 PASS**（§12）：机械校验器 **78/78**；D1-D20=20 / T1-T12=12（CHECKLIST 全引用）/ I1-I12↔E1-E12 双射 / U1-U17=17；组项 8/10/11/9/12/6/9/5=70 连续；门禁 12 数字 D/I/C 三文档命中；A20-A26+5 版本号 I/R 双登记；F 链 PROGRESS+IMPL 齐备；四文档状态链均指向 Step 8；详见 §12 |
| H2 | **改动面白名单**：改 3 源（`portfolio.py` / `config.py` / `engine_v2.py`）+ 新建 1 脚本 + 新建 2 测试 + 改 2 测试；**零 diff 面**：`config_v2.py` / `interfaces.py` / `diagnostics.py` / `risk_overlay.py` / `target_positions.py` / `tests/golden/` / `pyproject.toml` / `uv.lock` | G 组通过 | `git diff --stat` + `git status` | ✅ git status：3 源 + 2 测试 + 2 台账改动；1 脚本 + 2 测试 + 7 文档新增；零 diff 面实测空 |
| H3 | **台账回写**：PROGRESS 主行 + 新增 `§3.9x`；RESEARCH §15 / DESIGN §14 / IMPL §9 状态链；CHECKLIST 实测列回填（RULE-1） | G 组通过 | 读回 diff | ✅ PROGRESS 主行 + §3.95；RESEARCH §15 / DESIGN §14 / IMPL §9；CHECKLIST 70 项实测列回填 |
| H4 | **基准脚本**：`scripts/p046b_bench_optimizers.py` 存在、可运行（N=50/200/500，无断言、不写文件、不进 CI）；mypy/black 合规（F-4-7） | T11 落码 | 实跑 + 命令 | ✅ 脚本可直跑（补 sys.path 引导）；N=50/200/500 实跑（N=500 hrp 0.056-0.064s、bl 0.0014-0.0019s）；无断言/不写文件/不进 CI；mypy/black 合规 |
| H5 | **提交与 CI**：提交原子（3 源 + 1 脚本 + 2 新测试 + 2 测试改 + 7 新文档：DESIGN/RESEARCH/IMPL/CHECKLIST + 3 REVIEW + 2 台账修改：PROGRESS / CHECKLIST_p055）；CI 四 job 全绿（lock-check / 3.10 / 3.11 / 3.12）；**须用户明确授权后方可 commit/push** | H1-H4 通过 | `git show --stat` + `gh run view` | ✅ `f272638`（17 files +3698/−52，用户 2026-11-23 明确授权）已推送；CI run `45163412591` 四 job 全绿（lock-check 8s / test 3.11 4m47s / test 3.12 3m48s / arch-check） |

---

## 9. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **70**（A 8 + B 10 + C 11 + D 9 + E 12 + F 6 + G 9 + H 5 = 70，逐表行数机械计数） |
| 实测列初始状态（Step 7） | `[待 Step 9]` **68**（A1-A8 / B1-B10 / C1-C11 / D1-D9 / E1-E12 / F1-F6 / G1-G9 / H2-H4）+ `[待 Step 8]` **1**（H1）+ `[待 Step 10]` **1**（H5）；**✅ 出现即为违规** |
| 实测列终态（Step 10） | 目标 **70 × ✅**；`[待 ...]` **0** |
| 实测列状态（Step 9 后） | **69 × ✅ + 1 × `[待 Step 10]`（H5）**；`[待 Step 9]` **0** |
| 实测列状态（Step 10 后） | **70 × ✅**（H5 回填 commit `f272638` + CI run `45163412591`）；`[待 ...]` **0** |
| 新用例数（计划） | **23 收集** = BL 11 + HRP 9 + 既有 3 |
| 新用例数（实测） | **23** = BL 11 + HRP 9 + 既有 3（`--collect-only` 实读）；collect **1464** 精确，**无偏移** |
| pytest collect 计划 | 1441 + 23 = **1464**（1463 passed + 1 skipped） |
| Step 9 门禁目标 | **1463 passed / 1 skipped**、`-k p046` **78**、`-k golden` **22**、`-k p054` **120**、mypy **160·0**、black **322**、`tests/*.py` **158**、`core` **51**、`live` **19**、`services` **13**、AST **22·30**、`lint-imports` **3 kept**、`uv lock` **0** |
| Step 9 实测 | **1463 passed + 1 skipped**（collect 1464）/ `-k p046` **78** / `-k golden` **22** / `-k p054` **120** / mypy **160·0** / black **322** / `tests/*.py` **158** / `core` **51** / `live` **19** / `services` **13** / AST **22·30** / `lint-imports` **3 kept** / `uv lock` **0**；红态 2 收集错误；F-S9-P046b-1 登记 |

> RULE-2：上述统计仅来自本文件 A-H 组逐项行数机械计数；不得从设计目标或推断值转抄。

---

## 10. 范围守卫（N1-N10，不计入验收项）

| # | 不做项（DESIGN §2.2） | 机械检查 |
|---|---|---|
| N1 | D3 行业/换手/跟踪误差约束 | `grep -n "tracking_error\|turnover"` 新代码 0 命中 |
| N2 | 矩阵式凯利 / 非等风险预算（P-046c） | 无 `kelly` / `risk_budget` 新符号 |
| N3 | max_sharpe / robust BL / Idzorek 置信度 | `BLConfig` 无 `view_confidences` / `sharpe` 字段 |
| N4 | 因子分数派生观点 | views 仅来自 `cfg.bl.views`，无 factor→views 映射 |
| N5 | 市值先验 / `OptimizationContext` | 无 `market_caps` / `mktcap` / `OptimizationContext` 新代码 |
| N6 | 多阶段 DP / `PortfolioPolicy` | 无 `policy` / `dp` 新符号 |
| N7 | Registry 统一重构 | `core/registry.py` / `engine_plugins.py` 零 diff |
| N8 | 新运行时依赖 / pypfopt 入 CI | `pyproject.toml` / `uv.lock` 零 diff；无 `import pypfopt` |
| N9 | 删除 `_apply_constraints_legacy` | 符号仍存在且调用点仅 AC-C-01a |
| N10 | 修改 `config_v2.py`（FROZEN/TD-2） | `git status --short core/config_v2.py` 空 |

---

## 11. 状态链

- **2026-11-23**：Step 5 IMPL（[IMPL_p046b](IMPL_p046b_bl_hrp.md)）+ Step 6 复审 PASS（[REVIEW_p046b_step5_impl](REVIEW_p046b_step5_impl.md)，4 P3 全修）。
- **2026-11-23**：**Step 7 CHECKLIST 落盘（本文）**——70 项验收（A 8 / B 10 / C 11 / D 9 / E 12 / F 6 / G 9 / H 5）；每项 DoR/DoD/证据出口；门禁目标冻结（1464 collect / 1463 passed / 78 / 22 / 120 / 160 / 322 / 158 / 51 / 19 / 13 / 22·30 / 3 kept / 0）；实测列 0 ✅（RULE-1）。**零代码变更 / 未提交**。
- **2026-11-23**：**Step 8 一致性复审 PASS（§12，reviewer GLM-5.3-Flash ≠ Step 7 作者）**——机械校验器 **78/78**（初跑 76/78，2 项为校验器自身正则过严的非文档误报，修正后全过，诚实披露）；H1 回填 ✅。
- **2026-11-23**：**Step 9 TDD PASS（§13）**——红态 2 收集错误（`ImportError: BLConfig/HRPConfig`）→ 绿态全量 **1463 passed + 1 skipped**（collect 1464）；`-k p046` 78 / golden 22 / p054 120 / mypy 160·0 / black 322 / AST 22·30 / lint 3 kept / uv lock 0 / 文件计数 158·51·19·13；bench N=50/200/500 通过；**F-S9-P046b-1**（HRP 部分零方差先过滤子域）回写 DESIGN/IMPL；实测列 **69 ✅ + H5 `[待 Step 10]`**。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS（§14，审计基座 GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash）**——Phase 0-4 全过；门禁独立复跑全绿（1463+1 / 78 / 22 / 120 / 160·0 / 322 / 22·30 / 3 kept / 0 / 158·51·19·13）；数值探针 6/6；**0 P0 / 0 P1 / 0 P2 代码缺陷 + 1 观察 O-R5-P046b-1**；H5 提交待授权。
- **2026-11-23**：**H5 执行并批次关闭**——用户明确授权后原子提交 `f272638`（17 files +3698/−52）推送；CI run `45163412591` 四 job 全绿（lock-check 8s / test 3.11 4m47s / test 3.12 3m48s / arch-check）；H5 回填 ✅ → **实测列 70/70**，**P-046b 批次关闭**。
- **批次状态**：**已关闭（Step 1-10 全通过）**。

## 12. Step 8 一致性复审（2026-11-23，reviewer GLM-5.3-Flash ≠ Step 7 作者 DeepSeek-V4.1-Flash）

> **规范依据**: SPEC_PROCESS Step 8 九项检查清单；**机械校验器 78/78 PASS**（脚本可重放：`consistency_check_step8.py`，四文档全文 regex 断言）；初跑 76/78，2 项 FAIL 经定位均为**校验器自身正则过严**（DESIGN §3.1 的 I 行为普通 `\| I1 \|` 格式非加粗；四文档对 pypfopt 的「不进 CI / 不装依赖 / 不得加入 / 未安装」为同义异形），修正校验器后复跑全过——**非文档缺陷**，诚实披露。

### 12.1 规范九项检查

| # | 检查项 | 结论 | 机械读数 |
|---|---|---|---|
| 1 | 四文档完稿后执行（禁止预填） | ✅ | Step 5/6/7 产物齐备（4 文件 exists）；CHECKLIST 实测列 `✅` 行数 = **1**（H1，即本项 Step 8 产物本身）+ 0 预填违规 |
| 2 | 派生需求登记 | ✅ | F-5-1..F-5-4 于 IMPL §9（Step 6 补登 F-5-4）；PROGRESS 主行 + §3.91/§3.92 登记 |
| 3 | RESEARCH 结论在 DESIGN 中被使用 | ✅ | DESIGN §1 U-P046b-1..17 依据列引 U/G；D1-D20 依据列引 A1-A26 与 F-R/F-4；§12 门禁与 RESEARCH §14 性能实测同源 |
| 4 | DESIGN 模块在 IMPL 有对应实施 | ✅ | D1-D20 表 **20/20**；IMPL `**T1**..**T12**` **12/12**；映射见 §12.2 |
| 5 | IMPL 功能点在 CHECKLIST 有验收项 | ✅ | T1-T12 在 CHECKLIST DoR 列 **12/12 引用**；0 悬空 |
| 6 | 无文档间矛盾 | ✅ | §12.3 抽查 7 组语义（对拍边界/zero_vol/ZeroVariance/MinVariance 零改动/`_upper_result` 消费方/pypfopt 边界/全零特判）跨文档一致 |
| 7 | 术语一致 | ✅ | `warning_kind`/`zero_vol`/`ZeroVariance`/`pdist`/`squareform`/`infeasible_kind` 三文档同拼写同语义 |
| 8 | 双向引用完整（ADR-0008 D6） | ✅ | 正向：CHECKLIST→DESIGN/IMPL/REVIEW×2、IMPL→DESIGN、DESIGN→RESEARCH/REVIEW(4)；本批无 ADR 依赖（grep 0 引用 → 反向无义务） |
| 9 | B 类断言延续 | ✅ | RESEARCH B 类锚 A6/A8/A11/A12：DESIGN/IMPL **均未引用其正文实质**（Walters 在 DESIGN 0 命中，仅 RESEARCH 书目级）；无需 STEP_GAP 标注 |

### 12.2 DESIGN D1-D20 → IMPL T1-T12 → CHECKLIST 映射

| D | 任务 | CHECKLIST 锚 | D | 任务 | CHECKLIST 锚 |
|---|---|---|---|---|---|
| D1 | T1 范围（题干） | A 组全域 | D11 | T6/T7 | C3/C4/C6 |
| D2/D6 | T3（Woodbury） | B3/B4/B8 | D12 | T7 | C5/C7 |
| D3 | T4/T5 | A7/B5 | D13 | T1 | A1-A3 |
| D4 | T3（先验） | B1/B2 | D14 | T8 | D1/B10/C10 |
| D5 | T5（观点过滤） | B6 | D15 | T2/T9 | A4/D2/D4 |
| D7 | T5（原 Σ） | B5 | D16 | T10 | D5/D6 |
| D8 | T3（fail-loud） | B4/E5 | D17 | 不实施 | A6/E10/E11 |
| D9/D10 | T6 | C1-C3/C10 | D18 | T7/T11 | C8/H4 |
| D19 | 不实施 | D8 | D20 | 不实施 | D9/N8 |

### 12.3 门禁数字三文档命中（D=DESIGN / I=IMPL / C=CHECKLIST）

| 数字 | D | I | C | 数字 | D | I | C |
|---|---|---|---|---|---|---|---|
| 1463 | 1 | 3 | 6 | 322 | 1 | 3 | 4 |
| 1464 | 1 | 3 | 4 | 158 | 1 | 2 | 4 |
| 78 | 1 | 4 | 4 | 51 | 3 | 2 | 5 |
| 22 | 13 | 21 | 18 | 19 | 7 | 10 | 6 |
| 120 | 3 | 4 | 5 | 13 | 7 | 12 | 5 |
| 160 | 1 | 3 | 4 | 30 | 2 | 10 | 6 |

（均为全文出现计数，含语境引用；三文档非零即口径并存，数值语义经 §12.1-6 抽查无矛盾。）

### 12.4 其他机械读数

- CHECKLIST 组项计数 **A8/B10/C11/D9/E12/F6/G9/H5 = 70**，序号 1..N 连续（正则逐行机械计数）。
- RULE-1 预填：**0 行预填 ✅**（初始 68×`[待 Step 9]` + 1×`[待 Step 8]` + 1×`[待 Step 10]`；Step 8 后 H1 → ✅，68/0/1）。
- I1-I12（DESIGN §3.1）↔ E1-E12（CHECKLIST）**双射 12/12**；U-P046b-1..17 关闭表 **17/17**。
- F 编号链：F-4-1..8 / F-5-1..4 / F-6-1..4 / F-R1..7 / F-S10-P046-1..3 在 PROGRESS 全部登记（0 missing）；F-5-x / F-6-x 在 IMPL 全部落字。
- A20-A26 与 5 个版本号（1.5.5 / 1.14.4 / 7.4.1 / 3.0.3 / 1.17.1）在 IMPL §4 与 RESEARCH §5 **双登记一致**。
- 四文档状态链「下一步」全部指向 **Step 8**（本节完成前）；PROGRESS §3.89-§3.93 五分节齐备。

## 13. Step 9 TDD 红→绿报告（2026-11-23，DeepSeek-V4.1-Flash）

### 13.1 红态（实现前）

- 新增 `tests/test_p046b_bl.py`（11 例）与 `tests/test_p046b_hrp.py`（9 例）先落盘。
- `pytest tests/test_p046b_bl.py tests/test_p046b_hrp.py -q` → **2 errors**（collection）：
  - `ImportError: cannot import name 'BLConfig' from 'core.config'`
  - `ImportError: cannot import name 'HRPConfig' from 'core.config'`
- 既有 `test_p046_cov.py` / `test_p046_engine.py` 保持绿；红态仅由新契约缺失触发。

### 13.2 绿态（实现后）

| 命令 | 读数 |
|---|---|
| `pytest tests/test_p046b_bl.py tests/test_p046b_hrp.py tests/test_p046_cov.py tests/test_p046_engine.py -q` | **40 passed**（8.21s） |
| `MPLBACKEND=Agg pytest -q` | **1463 passed, 1 skipped**（collect **1464**） |
| `pytest -q -k p046` | **78 passed** |
| `pytest -q -k golden` | **22 passed** |
| `pytest -q -k p054` | **120 passed** |
| mypy CI 同款命令 | **160 source files, 0 error** |
| `black --check .` | **322 unchanged**（初检 4 files would be reformatted，均为本批文件；格式化后复跑 exit 0） |
| AST P-029（5 目录 + `cli.py` / core） | **22 / 30** |
| `lint-imports` | **3 kept, 0 broken** |
| `uv lock --check` | exit **0** |
| 文件计数 | tests **158** / core **51** / live **19**（递归）/ services **13** |
| bench `scripts/p046b_bench_optimizers.py` | N=50/200/500 通过（N=500：hrp 0.056-0.064s / bl 0.0014-0.0019s） |

### 13.3 用例清单（20 例新增 + 3 例既有增例）

- `test_p046b_bl.py`（11）：`test_bl_no_views_equals_prior` / `test_bl_single_view_closed_form` / `test_bl_single_view_implied_weights_only_view_asset` / `test_bl_tau_cancels_with_default_omega` / `test_bl_omega_limits` / `test_bl_zero_view_variance_raises` / `test_bl_explicit_prior_missing_asset_raises` / `test_bl_views_missing_asset_filtered` / `test_bl_optimizer_not_mean_variance_subclass` / `test_bl_upper_infeasible_passthrough` / `test_build_optimizer_bl_aliases`。
- `test_p046b_hrp.py`（9）：`test_hrp_distance_matches_paper_example` / `test_hrp_single_linkage_leaves_order` / `test_hrp_recursive_bisection_closed_form` / `test_hrp_single_asset` / `test_hrp_zero_variance_no_nan` / `test_hrp_max_assets_guard` / `test_hrp_box_constraints` / `test_hrp_method_name` / `test_build_optimizer_hrp`。
- 既有增例（3）：`test_estimate_cov_degenerate_warns` / `test_estimate_cov_codes_missing_warns` / `test_zero_vol_records_zero_variance`。

### 13.4 实施期登记

- **F-S9-P046b-1（P3，实现细化）**：HRP 部分零方差改为「先过滤 `diag>0` 且有限 → 有效子域 HRP → 回填 0」。直接 α 链会让零方差资产得满权重（`diag(0,.09,.16)` → `[0.64,0,0.36]`），与 DESIGN D11「零权重视为 0」不符；细化后 `[0,0.64,0.36]`、Σw=1、无 NaN、`warning_kind=None`。已回写 DESIGN D11/§6.4、IMPL §3.7/§6.2#5、PROGRESS §3.95。
- **bench 脚本**：按仓库惯例（`p055_bench_e2e.py`）补 `sys.path` 引导，使 docstring 用法可直接运行；仍无断言、不写文件、不进 CI。
- **collect 偏移**：**无**（1441 + 23 = 1464）。

## 14. Step 10 ADD 审计 + RULE-5 异构终审（2026-11-23，审计基座 GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash）

> **异构条件（RULE-5）**：审计基座 **GLM-5.3-Flash** ≠ RESEARCH / DESIGN / IMPL / CHECKLIST 四文档作者 **DeepSeek-V4.1-Flash** → 异构天然成立，ADD 审计与异构终审**合并一轮**（P-029 / P-050 先例）。
> **方法**：Phase 0 spec 质量门 → Phase 1 完整性盘点 → Phase 2 保真度比对（IMPL §3 独立读码）→ Phase 3 必要性（diff 逐 hunk 归因）→ Phase 4 语义/生命周期 → 门禁独立复跑 + 数值探针独立复现 + 盲区扫描 + N1-N10 机械复核。**不采信任何未经本基座复现的读数**（Step 9 记录值全部独立重放）。

### 14.1 Phase 0-4 审计

| Phase | 核对内容 | 结论 |
|---|---|---|
| 0 质量门 | 四文档 + 11 关联文档相对链接机械扫描 → **0 broken**；CHECKLIST 70 项实测列 69 ✅ + H5 `[待 Step 10]`（无预填违规） | PASS |
| 1 完整性 | D1-D20 ↔ T1-T12 ↔ A-H 组无悬空（Step 8 校验器 78/78 存续）；E1-E12 不变式均有测试或探针出口 | PASS |
| 2 保真度 | T1-T12 逐项独立读码：`BLConfig`/`HRPConfig` 校验（config.py L272-L308）、`black_litterman_posterior` Woodbury + K×K `solve`（`np.linalg.inv` 全文件 **0 命中**）、`_bl_prior` 三态、`_upper_result`/`_solve_mean_variance` 抽取 + MVO 等价重构、`MinVarianceOptimizer` 零改动、BL upper 早退 lazy、HRP 三纯函数（N<2 守卫 / `np.divide` where / 保序回填）、HRP 子域过滤（F-S9-P046b-1）、`max_assets` 守卫在距离矩阵前、工厂 3 键 + 消息含「合法值」、引擎唯一改动 error_type 三元、`estimate_cov` 双 warning、`_apply_constraints_legacy` 全仓仅 1 处定义（生产零调用） | PASS |
| 3 必要性 | `core/portfolio.py` **13 hunks 全部归因** T1-T10（imports / warning_kind / estimate_cov×2 / 纯函数块 / 求解器抽取 / MVO 重构+BL 插入 / RP zero_vol×3 / HRP 插入 / 工厂）；`config.py` diff 逐行 = `import math` + BLConfig + HRPConfig + bl/hrp 字段；`engine_v2.py` diff = 仅 error_type 块；`CHECKLIST_p055` 1 行 = P-055 收口（H5 白名单）；范围外符号（tracking_error/turnover/kelly/risk_budget/market_caps/OptimizationContext/view_confidences/policy/dp/Idzorek）diff 内 **0 命中** | PASS |
| 4 语义/生命周期 | BL/HRP opt-in（默认 `equal_weight` 路径与 golden 22 零漂移）；`OptimizationResult` 仍 frozen 且新字段末位带默认（既有位置构造零破坏）；`InfeasibleConstraintError` 仍 `ValueError` 子类；纯函数无模块级可变状态；`config_v2.py`/`interfaces.py`/`diagnostics.py`/`risk_overlay.py`/`target_positions.py`/`registry.py`/`engine_plugins.py`/`pyproject.toml`/`uv.lock`/`tests/golden/` 全部 **零 diff** | PASS |

### 14.2 门禁独立复跑（本基座实测，E1-E5 / G1-G9）

| # | 门禁 | 命令（本基座重放） | 实测 | 判定 |
|---|---|---|---|---|
| E1/G1 | 全量 | `MPLBACKEND=Agg pytest -q` | **1463 passed, 1 skipped**（collect 1464，184.33s） | ✅ |
| E1/G2 | p046 子集 | `pytest -q -k p046` | **78 passed**（1386 deselected） | ✅ |
| E1/G3 | golden | `pytest -q -k golden` + `git status tests/golden/` | **22 passed** + 目录**零改动**（零重录） | ✅ |
| E1/G4 | p054 | `pytest -q -k p054` | **120 passed** | ✅ |
| E2/G5 | mypy | CI 同款逐字命令 | **160 source files, 0 error** | ✅ |
| E2/G6 | black | `black --check .` | **322 unchanged**（exit 0） | ✅ |
| E3/G8 | AST | P-029 口径（5 目录 + `cli.py` / core） | **22 / 30**（均与基线一致） | ✅ |
| E3/G8 | lint | `lint-imports` | **3 kept, 0 broken** | ✅ |
| E4/G9 | lock | `uv lock --check` | exit **0** | ✅ |
| E5/G7 | 计数 | `Get-ChildItem` | tests **158** / core **51** / live **19** / services **13** | ✅ |

### 14.3 数值探针独立复现（6/6 PASS，审计侧独立公式复算）

| # | 探针 | 读数 |
|---|---|---|
| P1 | BL Woodbury ≡ 显式逆矩阵公式（随机 5×5 SPD seed=2026，2 观点，Ω=diag(τPΣPᵀ)） | max\|diff\| = **2.78e-17** |
| P2 | τ 消去（0.05 vs 0.9，随机 Σ） | 逐位一致（<1e-12） |
| P3 | HRP 部分零方差 `diag(0,.09,.16)` → `[0, 0.64, 0.36]`、Σw=1、无 NaN、`warning_kind=None`；全零 → 1/3 等权 + `message/warning_kind="zero_vol"` | 复现 F-S9-P046b-1 |
| P4 | 工厂 `black_litterman`/`bl`/`hrp` 别名类型 + 未知 method 消息含「合法值」且列全 3 新键 | PASS |
| P5 | `estimate_cov` 退化行 warning + 输出无 NaN；codes 缺失列 warning + 交集 | PASS |
| P6 | `_bl_prior` equal（δΣw_eq 逐位）/ zero（全零）/ explicit（多余资产 warning 后丢弃） | PASS |

### 14.4 盲区扫描 + N1-N10 复核

- 新增代码（3 源 diff + 2 新测试 + 1 脚本）：裸 `except Exception` **0** / `type: ignore` **0** / `print(` **0** / TODO/FIXME/XXX/HACK **0** / `breakpoint`/pdb **0** / `unittest.mock` **0** / 新增 skip/xfail **0**。
- `core/engine_v2.py` 存量 3 处 `except Exception`（L692/L741/L1391）为**既有代码**（本批 diff 仅 error_type 块），计入基线 core **30**，非本批引入。
- N1-N10 逐项：N1-N6 范围外符号 diff **0 命中**；N7 registry/engine_plugins 零 diff；N8 无 `import pypfopt` + pyproject/uv.lock 零 diff + lock exit 0；N9 `_apply_constraints_legacy` 保留且生产零调用；N10 `config_v2.py` 零 diff（FROZEN/TD-2）。**10/10 PASS**。

### 14.5 发现与处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| O-R5-P046b-1 | P3（观察，无需修复） | 「upper 约束 + cov 全零」组合语义差异：`RiskParityOptimizer`（upper 在末尾判定）报 `ZeroVariance` 优先（F-6-4），`HRP`/`BL`（upper 早退 lazy，不计算 Σ）报 `InfeasibleConstraints` | 与设计一致——F-6-4 明确仅限 RiskParity，HRP/BL upper 早退为 IMPL §3.5 显式设计（保持 lazy 语义）；登记供后续批次知悉，不改码 |

**代码缺陷：0 P0 / 0 P1 / 0 P2 / 0 P3**。

### 14.6 终审结论

- **ADD 审计 PASS + RULE-5 异构终审 PASS**：Phase 0-4 全过；门禁 10 项独立重放全绿且与冻结目标逐项一致；探针 6/6；盲区干净；范围守卫 10/10。
- **H5 已执行**：用户明确授权后原子提交 `f272638`（17 files +3698/−52）推送；CI run `45163412591` **四 job 全绿**（lock-check 8s / test 3.11 4m47s / test 3.12 3m48s / arch-check）；H5 回填 ✅ → 实测列 **70/70**，**P-046b 批次关闭**。
