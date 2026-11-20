# CHECKLIST：P-046a 组合优化语义修复（约束不变量 + 协方差统一入口）

> **批次**: P-046a · **T1**（`core/portfolio.py` 语义面 + 3 个新测试模块 + `core/config.py` / `core/engine_v2.py` / `core/diagnostics.py` 接线；golden 18 零重录）
> **上游**: [DESIGN_p046](DESIGN_p046_portfolio_optimization.md)（§2 三决策 D-R1/R2/R3 / §4 分支矩阵 / §5 协方差入口 / §6 engine 接线 / §7 I1-I8 / §8 AC 映射）；[IMPL_p046](IMPL_p046_portfolio_optimization.md)（§2-§7 代码骨架 T1-T6 / §8 测试 T7 / §9 验收命令 / §10 回退点 / §11 偏差 F-D-8..F-E-9 / §12 低效排除表 / §13 执行记录）；[RESEARCH_p046](RESEARCH_p046_portfolio_optimization.md)（§10.1 三项裁决 / §15 AC-C/B1/B2 / §16-§18 三轮异构复审与回填 / §20 Step 9 报告）
> **状态**: Step 7 产出（2026-11-20，DeepSeek-V4.1-Flash）；Step 8 一致性复审 **PASS**（§19）；Step 9 实测回填完成（§8）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；禁止预填
> **行号口径**: 本文件锚 `b5f69a7`（未提交工作区）；Step 9 落码后行号失效，实测证据改用「文件 + 符号名 + 用例名」
> **基线读数（@`b5f69a7`，P-048 关闭）**: pytest **932** / `-k golden` **18** / mypy **111 files 0** / black `core tests` **149**、全仓 **218** / `tests/*.py` **106** / AST `except Exception` core 外 **22**、core 内 **29** / `uv lock --check` exit **0**
> **目标读数**: pytest **973**（932 + 41，Step 9 若 collect 偏移须登记 `F-S9-P046-*`）/ `-k golden` **18（零重录）** / mypy **111 files 0（不变，无新源文件）** / black `core tests` **152**、全仓 **221**（+3 测试模块）/ `tests/*.py` **109** / AST core 外 **22 不变**、core **30**（`record_detail` 零抛错包裹 +1）/ `uv lock --check` exit **0**
> **Step 9 实测（2026-11-20）**: pytest **987 passed**（collect **55**）/ `-k golden` **18** / mypy **111·0** / black **152·221** / `tests/*.py` **109** / AST core 外 **26**、core **30** / `uv lock --check` **0**（偏移见 F-S9-P046-1/2）

---

## 1. A 组：模块契约（12 项，锚 DESIGN §2/§4/§5/§6 + IMPL §2-§7）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `InfeasibleConstraintError(ValueError)` 定义于 `core/portfolio.py`；`OptimizationResult`（`frozen=True`，字段 `weights`/`method`/`n_selected`/`max_weight`/`min_weight`/`infeasible_kind`/`cash_residual`/`message`）与 `_Feasibility`（`kind`/`budget` + `is_upper`）齐备 | 无（新建类型） | 读码 | ✅ [portfolio.py](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py) 三类型齐备；3 模块 55 passed |
| A2 | `_precheck(n, cfg, method)` 签名**含 method**（AC-B1-01）；U1-C（`n=0`）→ `empty`、U1-B（`sum_min > 1+1e-12`）→ 抛、U1-A（`sum_max < 1-1e-12`）→ `upper`、否则可行；**4 处调用点**分别传 `"equal_weight"` / `"risk_parity"` / `"min_variance"` / `"mean_variance"` | A1 落码 | 读码 + 参数化用例 | ✅ 读码 `_precheck(` 4 调用点实名齐全；`test_ac_b1_02_u1b_raises[4]` + `test_ac_c_07_*` passed |
| A3 | `_scale_to_budget(w, lo, hi, budget=1.0, tol=1e-12, max_iter=60)`：**短路**（`\|Σclip−budget\|≤tol` 原样返回）、doubling 求上界、二分、终态 `clip` 并断言 `\|Σw−budget\|≤1e-9`；非正分量固定 `lo` | A1 落码 | 读码 + 闭式两点 | ✅ 读码；`test_ac_c_03_box_bounds[3]` + `test_ac_c_02_total_weight_le_one[3]` + `test_ac_c_05_idempotent` passed |
| A4 | `_apply_constraints(weights, feas=None)`：`feas.is_upper` → **只 clip 不归一**；否则走 `_scale_to_budget`；**`_apply_constraints_legacy` 保留**（旧 clip→clip→归一，仅供 AC-C-01a 对照） | A2/A3 落码 | 读码 + B2 | ✅ 读码；`test_ac_c_01a_*[4]` + `test_ac_b2_02/03` passed |
| A5 | `estimate_cov(returns, method="ledoit_wolf", codes=None, psd_fix=True)` 为**唯一入口**：`ledoit_wolf` 走 `sklearn.LedoitWolf`；NaN 走 `dropna(how="any")`、有效行 `<2` → `fillna(0.0)` 后 sample；`_psd_project` 对称化 + 特征值截断；未知 method 抛 `ValueError`（含合法值集）；**自研 `_ledoit_wolf_shrinkage` 已删除** | A1 落码 | 读码 + B11 | ✅ 读码；`test_ac_c_01c_matches_sklearn_ledoitwolf` max diff `<1e-15`；grep 无 `_ledoit_wolf_shrinkage` |
| A6 | 四优化器均实现 `optimize_with_diagnostics(...) -> OptimizationResult`；`BaseOptimizer.optimize` 为**薄包装**（返回 `.weights`）且**签名不变**（3 参含默认，兼容 `IOptimizer` Protocol 与 `strategy.py` 两处 2 参调用） | A1-A5 落码 | 读码 + `mypy` | ✅ 读码；`test_strategy_path_u1b_propagates` passed；mypy 111 files 0 |
| A7 | U1-A 分流：`equal_weight` → 各 `m`（`Σ=n·m`）；`risk_parity` → 保留相对比例仅截断；`min_variance`/`mean_variance` → **直接各 `m`、跳过 cvxpy**（DESIGN §4.3 单点解） | A2/A4 落码 | 读码 + B9/B10 | ✅ 读码；`test_ac_b2_08_minvar_degenerates[4]`（min/mvo × m=0.1/0.2）passed |
| A8 | **F-D-8 修复**：`MeanVarianceOptimizer` 不再在 `returns is not None` 时覆盖注入 `cov_matrix`；注入分支 `cov.loc[selected, selected]`、`expected_returns` 独立取自 `returns[selected].mean()`；`status not in (OPTIMAL, OPTIMAL_INACCURATE)` → `raise RuntimeError`（**已删等权回退**） | A5 落码 | 读码 + B12 | ✅ 读码；`test_cov_entry_used_by_optimizer` passed |
| A9 | `OptimizerConfig.__post_init__` 四条：`0<max_weight≤1` / `min_weight≥0` / `min_weight<max_weight` / `target_count≥1`，违规抛 `ValueError`；**`config_v2` 零改动**（FROZEN / TD-2），`cov_shrinkage` 标 deprecated 但保留 | 无 | 读码 + B8 | ✅ `test_ac_c_08_config_validation[4]` passed；`git status` 无 `core/config_v2.py` |
| A10 | `core/diagnostics.py` 三件套：`DayErrorRecord.detail: Optional[dict]=None`（去重键不含它）、`record_detail(date, stage, *, category, error_type, message, retryable=False, **detail)`（off 早返 + 零抛错 + 截断 + 类别计数）、`classify_day_error` 在 `rebalance` 分支**最前**返回 `("config", False)` for `InfeasibleConstraintError` | A1 落码 | 读码 + B12 | ✅ 读码三件套；`test_engine_u1b_config_category` + `test_p026_record_compat`（`detail is None`）passed |
| A11 | `engine_v2`：L1082-1083 **只算一次** `cov = estimate_cov(returns_data, method=cfg.optimizer.cov_method)` 并注入；`except InfeasibleConstraintError` → 记录 + `emit(ERROR)` + `return`；L1104-1109 overlay 复用同一 `cov`（**L1106 裸 `np.cov` 已删**），传 `cov.to_numpy()` + codes | A5/A6 落码 | 读码 + B12 | ✅ 读码；`test_cov_computed_once` 计数 == 3（3 个可调仓日）；grep 无裸 `np.cov` |
| A12 | 死面零改动：`round_lot_optimize`、`build_optimizer`、`COV_ESTIMATORS` 公开键集、`config_v2.py`、`interfaces.py` 均无 diff；`cov_shrinkage` / `round_lot` / `industry_max_weight` 字段保留并标注（D-3） | A5 落码 | `git diff` + 读码 | ✅ `git status --short` 零 diff 上述文件；`COV_ESTIMATORS` 键集仍 sample/ledoit_wolf/ewma |

## 2. B 组：测试交付（13 项，锚 IMPL §8 + RESEARCH §15）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | `tests/test_p046_constraints.py` 落盘，collect **27** = AC-C-01a×4 + AC-C-02..07/09×7 + AC-C-08×1 + AC-B1-01×1 + AC-B1-02×4 + AC-B1-03×1 + AC-B1-04×1 + AC-B2-01..08×8（Step 8 修正分解标签：C-08 计入本模块；B1-05 测试物在 engine 模块、计数归 B12） | T1-T4 落码 | `pytest --collect-only -q` | ✅ collect **38**（≠27，+11，F-S9-P046-1）：C-02/C-03 参数化 +4、C-08 展开 +3、B2-08 展开 +3、`test_cov_entry_used_by_optimizer` +1；38 passed |
| B2 | **AC-C-01a**：`sample` 口径、可行域内四 method 输出与 `_apply_constraints_legacy` **双跑逐位相同**（`abs=1e-12`）；对照向量**运行期生成**，不硬编码（A5 禁录制） | A4 落码 | `::test_ac_c_01a_*` 4 例 | ✅ `test_ac_c_01a_sample_identical_to_legacy[4]` passed（m=1.0 可行域双跑；raw 由 optimizer 运行期生成） |
| B3 | **AC-C-01b**：`-k golden` **18 passed**；`git status --short tests/golden/` 空输出（零重录） | 全量落码 | 命令 + `git status` | ✅ `-k golden` 18 passed；`git status --short tests/golden/` 空 |
| B4 | **AC-C-01c**：`ledoit_wolf` 下 `estimate_cov` 与 `sklearn.LedoitWolf().fit(X).covariance_` 逐位相等（`1e-15`）；另附 **2×2 闭式**一例（手推，非录制） | A5 落码 | `::test_ac_c_01c_*` / `::test_lw_2x2_closed_form` | ✅ 两例 passed（对拍 `<1e-15`；2×2 按 LW 2004 Eq.(5) 结构重建，S 取 ddof=0） |
| B5 | **AC-C-02/03**：参数化网格（含 `min_weight>0`、n·m 边界 10/20/7）下恒有 `Σw≤1+1e-12` 与 `-1e-12≤w_i≤m+1e-9` | A2-A4 落码 | `::test_ac_c_02_*` / `::test_ac_c_03_*` | ✅ `test_ac_c_02_total_weight_le_one[3]` + `test_ac_c_03_box_bounds[3]` passed |
| B6 | **AC-C-04/05/06**：零收益退化（`Σw_raw=0`）无 `NaN`/`inf`；连续两次调用逐位相等；同输入多次运行哈希一致（无随机/时钟） | A3/A4 落码 | `::test_ac_c_04/05/06_*` | ✅ `test_ac_c_04_no_nan_on_zero_raw` / `05_idempotent` / `06_deterministic` passed |
| B7 | **AC-C-07/09**：不可行时 `OptimizationResult.infeasible_kind` 与 `cash_residual` 齐备；`equal_weight` 选股仍为 `min(target_count, len(valid))` + 零值过滤（选择结果快照不变） | A1/A7 落码 | `::test_ac_c_07_*` / `::test_ac_c_09_*` | ✅ `test_ac_c_07_diagnostics_on_infeasible` / `test_ac_c_09_selection_snapshot` passed |
| B8 | **AC-B1-01..06**：消息含 `method`/`n`/`max_weight`/`min_weight`/`required_max_weight=1/n`/`sum_max`/`sum_min` 七要素；U1-B 四 method 均抛（无副作用）；`n·m=1-1e-13` 不抛；U1-A 与 U1-B 消息标识可区分；`__post_init__` 非法配置逐条抛；**5 个 `target_count=2` 构造点**显式 `max_weight`（B13） | A2/A9 落码 | `::test_ac_b1_*` | ✅ B1-01/02[4]/03/04 + C-08[4] passed；5 构造点处置见 B13 |
| B9 | **AC-B2-01..06**：`Σw=Σmin(w_i,m)` 且`cash_residual=1−Σw`（`atol=1e-12`）；等权特例 `n=3,m=0.1→0.3/0.7`；ERC 仅截断不缩放；U1-B 不走 B2；诊断字段齐备；`cash_residual` 与 `OverlayResult.cash_residual` 同义 | A4/A7 落码 | `::test_ac_b2_01..06_*` | ✅ 六例 passed（ERC 用例 m=0.2 → n·m=0.8<1 才进 upper） |
| B10 | **AC-B2-07/08**：端到端（optimizer → `target_positions`）未投资金 `=(1−Σw)·total_value` 且无二次归一化；U1-A 下 min_var/mvo 输出恒为各 `m`（含 `m` 与 `n` 双参数化） | A7/A11 落码 | `::test_ac_b2_07_*` / `::test_ac_b2_08_*` | ✅ `test_ac_b2_07_target_positions_cash` + `test_ac_b2_08_minvar_degenerates[4]` passed |
| B11 | `tests/test_p046_cov.py` 落盘，collect **7**：C-01c 对拍 + 2×2 闭式 + PSD（非 PSD 输入投影后最小特征值 ≥ `-1e-15`）+ NaN listwise + EWMA 对称 PSD + 未知 method 抛错 + **近奇异 Σ 求解边界**（F-D-2） | A5 落码 | `--collect-only` + `::test_*` | ✅ collect **10**（7 + I8 三 method 参数化 3，F-S9-P046-1）；10 passed |
| B12 | `tests/test_p046_engine.py` 落盘，collect **7**：`estimate_cov` 只调一次（monkeypatch 计数==1，**AC-C-10**）；U1-B 经引擎 → 记录 + ERROR 事件 + 当日跳过且 `category=="config"`（**AC-B1-05** 载体）；**U1-A 经引擎 → `record_detail` 落账**（`category=="optimizer"`，`F-S7-P046-1`）；strategy 两调用点 U1-B 冒泡（F-D-1）；窗口含 NaN 不崩（F-D-5）；`infeasible_kind` 入 `DayErrorRecord.detail`；`test_p026` record 断言不因新字段失败（F-D-7） | A10/A11 落码 | `--collect-only` + `::test_*` | ✅ collect **7**；7 passed（计数==3 个调仓日、U1-B config、U1-A optimizer、ERROR 事件、strategy 冒泡、零方差窗口、p026 兼容） |
| B13 | **AC-B1-06 既有测试处置**：5 个 `target_count=2` 构造点显式 `max_weight=0.5`——`test_p023:128`、`test_p025:178`、`test_p025:259`、`test_p025:300`、`test_p026:229`；若某断言确依赖旧超限行为 → **登记「语义修正」**，不得放宽断言 | B8 落码 | 读码 + 三模块 pytest | ✅ 5 点逐一核对：断言不依赖权重数值 → 零改动；另实际改 **2 处语义修正**（`test_p031` L73 `max_weight=1.0`、`test_p048` vol 腿 sklearn LW 复算），F-S9-P046-3 |

## 3. C 组：不变式（DESIGN §7 I1-I8，8 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1** `Σw ≤ 1 + 1e-12`（含 `min_weight>0` 与 U1-A 路径；`Σ=n·m<1` 时残差留现金） | A4 落码 | AC-C-02 用例 | ✅ `test_ac_c_02_*[3]` + `test_ac_b2_08_*[4]` passed |
| C2 | **I2** `-1e-12 ≤ w_i ≤ m + 1e-9` | A4 落码 | AC-C-03 用例 | ✅ `test_ac_c_03_box_bounds[3]`（×4 method 断言）passed |
| C3 | **I3** 无 `NaN`/`inf`，含 `w.sum()==0` 与零方差退化 | A3/A4 落码 | AC-C-04 + B11 | ✅ `test_ac_c_04_no_nan_on_zero_raw` + B11 10 passed |
| C4 | **I4** 幂等 + 确定性（双调用逐位相等；无随机/时钟） | A3 落码 | AC-C-05/06 | ✅ `05_idempotent` / `06_deterministic`（tobytes 相等）passed |
| C5 | **I5** 不可行必有结构化诊断：optimizer 层 `OptimizationResult` 字段齐备；engine 层 U1-B 落 `config` 类别、U1-A 落 `optimizer` 类别 | A10/A11 落码 | AC-C-07 + B12 | ✅ `test_ac_c_07_*` + `test_engine_u1b_config_category` / `test_engine_u1a_diag_recorded` passed |
| C6 | **I6** 引擎不把配置错误降级为静默跳过：U1-B 必产生 record + `emit(ERROR)`；**U1-D 在 `__post_init__` 冒泡、不进 engine**（`F-S7-P046-2` 口径界定） | A9/A11 落码 | B8 + B12 | ✅ `test_error_event_emitted_on_u1b`（`EventType.ERROR`）+ C-08[4]（构造即抛）passed |
| C7 | **I7** golden 18 零重录（与 B3 同源，此处不重复计数） | 全量落码 | B3 | ✅ 18 passed、`tests/golden/` 零 diff |
| C8 | **I8** `estimate_cov` 输出对称（`max\|Σ−Σᵀ\|==0`）且半正定（最小特征值 ≥ `-1e-15`），三条 method 各一例 | A5 落码 | B11 | ✅ `test_all_methods_symmetric_psd[3]` + `test_ewma_symmetric_psd` passed |

## 4. D 组：门禁、改动面与文档（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest 全量 **973 passed**（932 + 41 = 27 + 7 + 7，`MPLBACKEND=Agg` + `.venv` 解释器；collect 偏移须登记 `F-S9-P046-*`） | 全量落码 | 全量末行 | ✅ **987 passed**（932 + 55；偏移 +14 → F-S9-P046-1） |
| D2 | `-k golden` **18 passed 零重录**；`git status --short tests/golden/` 空输出 | 全量落码 | 命令 + `git status` | ✅ 18 passed；`git status` 该目录空 |
| D3 | mypy **CI 等价命令**（逐字对齐 [tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46)）**111 files 0 issue**（无新源文件） | 全量落码 | 逐字命令 | ✅ `Success: no issues found in 111 source files` |
| D4 | black `core tests` **152**、全仓 **221**，均 0 reformatted；`tests/*.py` **109**（+3） | 新测试落盘 | `black --check` 双口径 + 计数 | ✅ `152 files would be left unchanged` / `221 files ...`；`tests/*.py` = 109 |
| D5 | AST `except Exception` core 外 **22 不变**；core **30**（+`record_detail` 零抛错包裹）；`portfolio.py` 新增代码 `try/except` **0**、`type: ignore` **0**；`diagnostics.record_detail` 内层捕获为**允许例外**（须在报告中注明） | 全量落码 | AST 扫描 + 读码 | ✅ core **29→30**（`record_detail` 包裹，允许例外）；`portfolio.py` try/except 0、`type: ignore` 0；core 外零 diff，但复用扫描实测 **26** ≠ 基线 22（口径不可复现，F-S9-P046-2） |
| D6 | **改动面白名单**：**新建 4**（3 测试 + CHECKLIST 之外的文档另计）；**改 4**（`core/portfolio.py` / `core/config.py` / `core/engine_v2.py` / `core/diagnostics.py`）+ 5 处既有测试 + 4 文档；**零 diff 面**：`core/config_v2.py` / `core/interfaces.py` / `core/risk_overlay.py` / `core/target_positions.py` / `tests/golden/` / `tests/_scenarios_*.py` | 全量落码 | `git diff --stat` + `git status` | ✅ 改 4 源 + **2** 既有测试（非 5，F-S9-P046-3）+ 新建 3 测试 + 5 文档；零 diff 面逐项空（`git status` 佐证） |
| D7 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff（sklearn 已在依赖内） | 全量落码 | 命令 + `git diff` | ✅ exit 0；两文件未修改 |
| D8 | **文档回写**：IMPL 追加「执行记录」小节（T1-T7 实际落码与偏差）/ DESIGN §8.3 门禁读数 / PROGRESS P-046 登记 / 本文件实测列回填；`_apply_constraints_legacy` 的保留理由与删除条件须在 PROGRESS 登记为后续批次入口 | D1-D7 通过 | 读回 diff | ✅ IMPL §13 / DESIGN §8.3 / PROGRESS §3.55.2 / 本文件 §1-§4 与 §8；legacy 删除条件见 PROGRESS §3.55.2 |
| D9 | **遗留与回退**：`U-P046-12`（HRP 一手原文缺失，仅阻塞 P-046b）与 `G-P046-5..9` 归属登记；IMPL §10 四个回退点逐项可执行（R1 legacy 单点切回 / R2 sample 临时回退 / R3 校验不许删 / 整体分段 revert） | D1-D8 通过 | 读码 + 读 IMPL §10 | ✅ PROGRESS §3.55.2「D9 归属」逐条登记；IMPL §10 R1-R3 + 整体 revert 可执行，本批零触发 |
| D10 | **提交与 CI**：提交原子（4 源 + 3 测试 + 5 测试改 + 4 文档 + PROGRESS）；CI 四 job 全绿（lock-check / 3.10 / 3.11 / 3.12）；**须用户明确授权后方可 commit/push** | D1-D9 通过 | `git show --stat` + `gh run view` | ✅ 原子提交 **`15f608a`**（14 files，+3263/−240，白名单核对 ✅）+ 终审文档 `0c183fe`；已推送 `b5f69a7..0c183fe`（用户授权）；CI run **44692414846** 四 job 全绿（RESEARCH §21.4） |

---

## 5. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **43**（A 12 + B 13 + C 8 + D 10 = 43，逐表行数机械计数） |
| AC 覆盖范围 | **仅被裁决分支**（AC-C-01a..10 + AC-B1-01..06 + AC-B2-01..08）；RESEARCH §15.4 的 **AC-B3-01..04 与 AC-B4-01..02 为落选备选（「备选」标注），不在本批 43 项内**（Step 8 显式声明，防误读为遗漏） |
| 实测列初始状态（Step 7） | A/B/C/D1-D9 共 **42 × `[待 Step 9]`**；D10 **1 × `[待 Step 10]`**；`✅` 出现即为违规 |
| 实测列终态（Step 9） | **43 × `✅`**（Step 10 回填 D10 后全绿）；`[待 Step 9]` **0** |
| 新用例数（计划） | **41 收集** = constraints 27 + cov 7 + engine 7 |
| 新用例数（实测） | **55** = constraints **38** + cov **10** + engine **7**（F-S9-P046-1） |
| Step 9 门禁目标 | pytest **973** / `-k golden` **18** / mypy **111** / black **152·221** / `tests/*.py` **109** / AST **22·30** / `uv lock --check` exit **0**（解释器 `.venv\Scripts\python.exe`） |
| Step 9 门禁实测 | pytest **987** / `-k golden` **18** / mypy **111·0** / black **152·221** / `tests/*.py` **109** / AST **26·30** / `uv lock --check` **0** |

> **RULE-2 统计溯源**：
> - 43 = 12 + 13 + 8 + 10（逐表行数）
> - 973 = 932 + 41；41 = 27（constraints：C-01a×4 + C-02..09×7 + B1×8 + B2×8）+ 7（cov）+ 7（engine）
> - **987 = 932 + 55**；55 = 38（constraints：C-01a×4 + C-02×3 + C-03×3 + C-04..07/09×5 + C-08×4 + B1-01×1 + B1-02×4 + B1-03×1 + B1-04×1 + B2-01..07×7 + B2-08×4 + `cov_entry`×1）+ 10（cov：7 + I8×3）+ 7（engine）
> - 18 = 18 + 0（本批**不新增 golden**，DESIGN §8.3）
> - mypy 111 不变（无新源文件，仅改 4 个既有源）
> - 152 = 149 + 3（三个新测试模块）；221 = 218 + 3；109 = 106 + 3
> - AST core 外实测 26、core 30（`record_detail` 一处零抛错包裹）；基线 22 不可复现 → F-S9-P046-2
> - **41 为计划收集数；实测 55**（F-S9-P046-1），本表计划值不回改，实测值单列（RULE-1）
> **RULE-5 声明**：Step 1-9 文档与代码作者 **DeepSeek-V4.1-Flash**；Step 2 / 4 / 6 / 8 复审异构成立（GLM-5.3-Flash，RESEARCH §16/§17/§18/§19）；Step 10 终审**待异构基座**。

---

## 6. Step 7 自检发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S7-P046-1** | P3（覆盖缺口） | AC-C-07 只约束 optimizer 层的 `OptimizationResult`，未要求 engine 侧 U1-A 落账；而 DESIGN §6.3 明确要求 `infeasible_kind` 等写入诊断。若 Step 9 只测 optimizer 层，选项 i 的 engine 接线无回归护栏 | 已于 **B12** 补「U1-A 经引擎 → `record_detail` 落账」用例（`category=="optimizer"`） |
| **F-S7-P046-2** | P3（口径歧义） | AC-B1-05 原文「配置不可行（**冒泡**）vs 数值失败（记录+跳过）」与 DESIGN §6.2「U1-B 运行时 → engine 捕获 → 记录 + 跳过」措辞冲突：U1-B 属运行时不可行，不应冒泡 | 本文件 **C6** 明确界定：**U1-D 冒泡**（`__post_init__`，启动即失败）、**U1-B 记录+跳过**（engine）；不改 DESIGN，按 DESIGN §6.2 为准 |
| **F-S7-P046-3** | P3（AC 映射缺口） | DESIGN §5.1 选项 i 的核心是「Σ 只算一次」，但 §15 AC 清单无对应编号，IMPL §8.1 的 `test_cov_computed_once` 未挂 AC | 挂入 **B12** 首例（monkeypatch 计数==1），并在 C 组不重复计数；Step 8 可裁定是否回填 RESEARCH 为 `AC-C-10` |
| **F-S7-P046-4** | 说明（非发现） | AC-C-09 只约束 `equal_weight` 的 `min()` + 零值过滤；`min_var`/`mvo` 的 `nlargest` 无 `min()` 截断、不过滤 0（§13.1 C-5） | 按 method 分别取证：`equal_weight` 断言选股快照不变（B7），其余三 method 只断言 `n=len(selected_stocks)` 口径（A2/A7），**不强行统一** |

---

## 7. Step 7 → Step 8 交接

1. **核计数链**：932 + 41 = **973**；41 = 27 + 7 + 7；149 + 3 = **152**；218 + 3 = **221**；106 + 3 = **109**；mypy **111 不变**；golden **18 零新增**；AST core 外 **22 不变** / core **30**。
2. **核零预填**：Step 9 前 `[待 Step 9]` 须为 **42**、`[待 Step 10]` 须为 **1**；任何 `✅` 出现即为违规。
3. **核 ID 不混用**：DESIGN 架构决策 `D1-D8`（§2）与本文件 **D 组 D1-D10** 同名不同义，引用一律写 `DESIGN-D*`；不变式 **I1-I8 锚 DESIGN §7**；AC 编号锚 **RESEARCH §15**（`AC-C-*` / `AC-B1-*` / `AC-B2-*`）；复审发现 `F-D-*`（Step 4）/ `F-E-*`（Step 6）/ `F-S7-P046-*`（本节）。
4. **核既有测试处置**：5 个 `target_count=2` 构造点（`test_p023:128` / `test_p025:178,259,300` / `test_p026:229`）必须显式 `max_weight`；若断言依赖旧超限行为 → 登记「语义修正」，**不得**放宽断言。
5. **核零重录纪律**：AC-C-01a 对照向量运行期生成（禁硬编码）；AC-C-01c 2×2 必须手推闭式；U1-A 的 `m` 期望由 `cfg.max_weight` 直接取值（非录制）。
6. **核行号口径**：本文件与 DESIGN/IMPL 行号均锚 `b5f69a7`；Step 9 落码后统一重取，D10 提交后以 commit hash 绑定复核。
7. **核不做清单**：不做 BL/HRP（P-046b）、不做矩阵式凯利/非等风险预算（L3-1/L3-2）、不做行业·换手·跟踪误差约束、不删死配置字段（D-3）、不改 `config_v2`（FROZEN）、不改 `round_lot_optimize`、不改 overlay 三层公式（P-048 已锁）、不引入 `pypfopt` 运行时依赖。

---

## 8. Step 9 实测回填记录（2026-11-20）

| 项 | 结果 |
|---|---|
| 42 项实测列 | **42 ✅ + 1 `[待 Step 10]`**；`[待 Step 9]` 清零 |
| 全量 pytest | **987 passed**（932 + 55；107s） |
| 新增用例 | **55**（constraints 38 / cov 10 / engine 7；计划 41） |
| golden | **18 passed**；`tests/golden/` 零 diff |
| mypy / black | **111·0** / **152·221**（0 reformatted） |
| AST / lock | core **30**、core 外 **26**；`uv lock --check` **0** |
| 既有测试 | 改 **2 处**（F-S9-P046-3），5 构造点零改动 |
| 回退点 | R1/R2/R3 + 整体 revert 零触发 |

**发现登记（本步新增）**：

| ID | 级别 | 内容 | 处置 |
|---|---|---|---|
| **F-S9-P046-1** | P3（计数偏移） | collect 41 → 55（+14）；全量 973 → 987 | 以实测为准；计划值保留、实测单列 |
| **F-S9-P046-2** | P3（基线口径） | AST core 外基线 22 在复算脚本下为 26，口径未固化 | 本批 core 外零 diff；P-046b 前固化扫描脚本 |
| **F-S9-P046-3** | P3（既有测试） | D6 预计 5 处，实际 2 处（`test_p031` / `test_p048`） | 均按「语义修正」登记，无放宽断言 |

> 详细报告见 [RESEARCH §20](RESEARCH_p046_portfolio_optimization.md) 与 [IMPL §13](IMPL_p046_portfolio_optimization.md)。
