# CHECKLIST：P-047 仓位管理（position sizing）

> **批次**: P-047 · **T1**（新建 `core/sizing.py` + `engine_v2` 最小 BUY 现金闸门 + 测试模块 + 3 golden case）
> **上游**: [DESIGN_p047](DESIGN_p047_position_sizing.md)（§2 裁决 D1-D7 / §3 精确签名 / §4 边界 / §5 V1-V12 / §6 I1-I10 / §7 R1-R5 / §10 Step 4 pass：1 P2 + 5 P3 / **§11 Step 6 pass：4 P3 + 2 INFO** / **§12 Step 8 pass：1 P2 + 5 P3 + 3 INFO**）；[RESEARCH_p047](RESEARCH_p047_position_sizing.md)（§7 S1-S11 / §8 I1-I10 / §13 Step 2 有条件通过）；[PROGRESS §3.52.1-§3.52.10](PROGRESS.md)
> **状态**: Step 7 产出（2026-11-18，DeepSeek-V4.1-Flash）；**Step 9 验收回填完成（2026-11-18）**：**43/45 `✅` + 2 `[待 Step 10]`（D8/D9）**，`❌` **0**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；禁止预填
> **行号口径（F-S10-P045-2 教训）**: 本文件行号均 @未提交工作区（HEAD `531795e` + diff）；提交后随 commit hash 稳定，Step 9 已按当时文件逐条复核
> **基线读数（@`531795e`，P-046 关闭）**: pytest **821** / `-k golden` **15** / mypy **108 files 0** / AST `except Exception` **22** / `tests/*.py` **94** / black `core tests` **135**、全仓 **203** / `uv lock --check` exit **0**
> **目标读数**: pytest **846**（+25）/ `-k golden` **18**（+3，既有 15 零重录）/ mypy **109 files 0**（+1 源）/ AST **22（不变）** / `tests/*.py` **95**（+1）/ black `core tests` **基线+2**（+1 源 +1 测试）、全仓 **基线+2** / `uv lock --check` exit **0**

---

## 1. A 组：代码变更（12 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `SizingConfig` 为 `@dataclass(frozen=True)` **19 字段**（`method` / `kelly_fraction` / `target_vol` / `vol_lookback` / `atr_period` / `atr_k` / `max_weight` / `min_weight` / `max_size` / `min_size` / `granularity` / `cash_buffer` / `commission_rate` / `commission_min` / `slippage_pct` / `pyramid_enabled` / `pyramid_max_adds` / `pyramid_decay` / `pyramid_step_atr`），默认值与 DESIGN §2.0 U-P047-3 逐项一致；`__post_init__` 校验五条：`0<kelly_fraction<=1` / `target_vol>0` / `granularity>0` / `0<max_weight<=1` / `0<=min_weight<=max_weight`，违规抛 `ValueError`；**`vol_lookback` / `atr_period` / `atr_k` 为预留字段、本批零消费**（B1 波动原语不落本批，DESIGN §12.3 D-R3） | 无（新建模块首个类型） | 读码 + V1/V3 | ✅ [sizing.py L46-80](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L46-L80)：19 字段逐项符合 + `__post_init__` 五条校验（L70-80）；V1/V3 PASS |
| A2 | 五个结果/状态类型齐备且 `frozen=True`：`SizingDiagnostics`（`reasons`/`dropped`/`clipped`）/ `SizingResult`（`weights` + `scale` + `diagnostics`）/ `RiskContribution`（`rc` + `pct`，**无 reason 字段**——F-S6-P047-4 订正后口径）/ `CashBudgetResult`（`weights` + `buy_cost` + `budget` + `scale`）/ `SizingState`（`entry_price` / `last_add_price` / `add_count`） | A1 落码 | 读码 | ✅ [sizing.py L83-125](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L83-L125)：五类型全 `frozen=True`，字段与 DESIGN §D2 逐项一致（本行 Step 7 版误写 `CashBudgetResult` 含 `qty`，DESIGN §D2 无此字段，**已订正**，F-S9-P047-1） |
| A3 | `estimate_buy_cash(amount, *, commission_rate, commission_min=5.0, slippage_pct=0.0)`：**`amount<=0 → 0.0` 守卫**（F-S4-P047-2）；返回 `amount + max(amount·commission_rate, commission_min) + amount·slippage_pct`，与 `ExecutionSimulator._calculate_cost(amount, BUY)` 同源 | A1 落码 | 读码 + V9 | ✅ [sizing.py L133-149](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L133-L149)：守卫 L146-147、精确式 L148-149；V9 三档（1_000 / 5_000 / 100_000）逐位相等 PASS |
| A4 | `kelly_fraction_scale(expected_return, variance, *, fraction=0.5)`：`f*=μ/σ²`、`scale=clip(fraction·f*, 0, 1)`；`variance<=0` → `(0.0, "zero_var")`；负 μ → 0；返回 `(scale, reason)` 二元组 | A1 落码 | 读码 + V2/V3 | ✅ [sizing.py L180-197](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L180-L197)：`fraction` 非法 `ValueError`（L188-189）/ `zero_var`（L190-191）/ `non_positive_edge`（L192-193）/ `clipped_max`（L195-196）；V2 闭式 0.125、V3 边界 PASS |
| A5 | `vol_target_scale(weights, cov, *, codes, target_vol=0.15)`：`σ_p=sqrt(wᵀΣw)`、`scale=min(target_vol/σ_p, 1.0)`（**不加杠杆**）；`σ_p==0` → `(原权重, 1.0, "zero_vol")`；`weights` ⊄ `codes` → `ValueError`（fail-fast，F-S6-P047-3 订正口径） | A1 落码 | 读码 + V4/V5 | ✅ [sizing.py L200-220](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L200-L220)：`scale=min(...)` L219、`zero_vol` L217-218；越界 code `ValueError`（`_as_vector` L163-165）；V4/V5 PASS |
| A6 | `risk_contributions(weights, cov, *, codes)`：`RC_i=w_i(Σw)_i/σ_p`、`pct=RC/σ_p`；`Σpct≈1`；`σ_p==0` → rc/pct **全 0**（无 reason 载体）；只诊断不求解（U-P047-2）；越界 code → `ValueError` | A1 落码 | 读码 + V6 | ✅ [sizing.py L223-235](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L223-L235)：RC L233、pct L234、零波动全 0（L230-231）；V6 两例（含 I10 对拍）PASS |
| A7 | `apply_sizing(weights, *, config, cov=None, codes=None, expected_returns=None, total_value=None, prices=None)` 分派：`none` **不做方法缩放但仍施加约束层**（F-S5-P047-2 处置；默认配置下逐值幂等）/ `kelly` 逐标的 `fraction·μ/σ²` 后整体 `scale=新和/旧和` / `vol_target` 组合层 / `risk_parity` 仅写 `reasons[code]=f"rc_pct={pct:.6f}"` 且权重不变；随后统一 `[min_weight, max_weight]` 裁剪 → `[min_size, max_size]` 过滤（需 `total_value`+`prices`，剔除后余额留现金**不归一**）→ 总权重 `>1` 等比缩放；未知 code 宽容**仅 kelly 分支**（`no_cov`） | A3-A6 落码 | 读码 + V1/V2/V6/V7 | ✅ [sizing.py L243-359](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L243-L359)：四分支 L270-314、约束层 L316-351、`no_cov` L276-278、`risk_parity` 仅诊断 L306-311；V1/V2/V6/V7 PASS |
| A8 | `cash_budget_scale(weights, *, cash, prices, total_value, config)`：`budget=cash·cash_buffer`；最多 **3 次**迭代 `qty=floor(w·scale·total_value·buffer/price/granularity)·granularity`、`cost=Σ estimate_buy_cash(qty·price)`，超预算 `scale *= budget/cost`；3 次仍未收敛 → `scale=0` + 全零；`qty=0` 标的成本计 **0** | A3 落码 | 读码 + V8 | ✅ [sizing.py L362-415](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L362-L415)：`np.floor` 整手 L390、3 次迭代 L407、不收敛 `scale=0` L413-415；`qty=0` 成本 0 经 L146 守卫；V8 三例 PASS |
| A9 | `pyramid_step(state, *, price, atr, config)`：`pyramid_enabled=False` → 0；`add_count>=max_adds` → 0；`price<entry_price` → **0（禁摊亏）**；`atr<=0` → 0；`price<last_add_price+pyramid_step_atr·atr` → 0；否则 `increment=pyramid_decay**add_count` 并推进 `last_add_price`/`add_count+1`；返回 `(新状态, increment)` | A2 落码 | 读码 + V10 | ✅ [sizing.py L418-444](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L418-L444)：五道 0 出口 L426-437、`decay**add_count` L438；V10 两例 PASS |
| A10 | `holding_age(entry_date, current_date, trade_dates)`：`((trade_dates>entry)&(trade_dates<=current)).sum()+1`（建仓日=1、跨周末按交易日）；`current<entry` → `ValueError`；纯函数显式传参 | A1 落码 | 读码 + V11 | ✅ [sizing.py L447-458](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L447-L458)：计数 L457-458、`ValueError` L453-454；V11 PASS |
| A11 | `engine_v2.py` diff **仅 3 处**（D7③）：①L28 `from core.sizing import estimate_buy_cash`；②L905-918 `_process_pending_orders` BUY 现金闸门（`required_cash=estimate_buy_cash(open_price·qty, …)`、严格 `<`、`continue` 整单跳过并保留队列、f-string warning 只读）；③零其他改动。**不触发 `enable_fallback`**（该分支仅在 `execute_order` 返回失败后执行）；不改遍历顺序、不改 SELL 路径、不做部分成交 | A3 落码 | `git diff` + V12 | ✅ `git diff --stat` → `core/engine_v2.py` 行读数 **16 ++++++**（**+16/−0**，唯一已跟踪源码改动）；V12 三例（跳过 / 成交 / `continue` 语义）PASS |
| A12 | `core/sizing.py` 为纯函数模块：零 `try/except`、零 `print` / `open` / `random` / 时间读取、无模块级副作用；import 白名单 ⊆ {`__future__`, `dataclasses`, `typing`, `numpy`, `pandas`}；`engine_v2` 仅新增 1 行 import，无 `TYPE_CHECKING` 外的新依赖 | A1-A11 落码 | AST 静态检查 | ✅ AST：`try/except` **0**、`# type: ignore` **0**；import 实为 `__future__/dataclasses/typing/numpy/pandas`（[L15-21](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L15-L21)），无 logging/I-O/random/时间 |

## 2. B 组：测试与 golden（14 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | **V1** `none` 幂等：输出权重与输入逐值相等、`scale==1.0`、`reasons` 空 | A7 落码 | `::test_v1_none_is_identity` | ✅ PASS |
| B2 | **V2** 凯利闭式：`μ=0.01, σ²=0.04, f=0.5` → `scale == 0.125`（闭式 `0.5·0.25`）；裁剪上界用例由 V3 覆盖 | A4 落码 | `::test_v2_kelly_closed_form` | ✅ PASS |
| B3 | **V3** 凯利边界：负 μ → 0；`variance=0` → 0 + `zero_var`；`fraction<=0` → `ValueError`；裁剪至 1.0 的用例（`clipped_max`） | A4 落码 | `::test_v3_kelly_boundaries` | ✅ PASS |
| B4 | **V4** vol-target 闭式：2 标的等权、`cov=diag[0.04,0.09]` → `σ_p=sqrt(0.0325)`、`scale=0.15/σ_p<1`、缩放后权重逐值；`scale<=1` 恒成立（不加杠杆） | A5 落码 | `::test_v4_vol_target_closed_form` | ✅ PASS |
| B5 | **V5** `σ_p=0`：`scale==1.0` 且 `reason=="zero_vol"`、权重原样 | A5 落码 | `::test_v5_zero_vol` | ✅ PASS |
| B6 | **V6** 风险贡献：`ΣRC≈σ_p`、`Σpct≈1`；等权等相关 `pct≈1/3`；**I10 对拍**用 `RiskParityOptimizer(OptimizerConfig(max_weight=1.0))`（F-S4-P047-1：默认 `0.10` 会 clip+归一化破坏 ERC） | A6 落码 | `::test_v6_risk_contributions` / `::test_v6_risk_parity_equal_budget_crosscheck` | ✅ 两例 PASS |
| B7 | **V7** 裁剪：`max_weight=0.4` 生效、总权重 ≤1；`min_size=10_000` / `max_size=30_000` 下 `{A:0.05,B:0.25,C:0.6}` → A 剔除(0.0)、B 保留(0.25)、C 裁剪(0.3)且总和 0.55 ≤1（**剔除后不归一**）；`none` 方法亦施加约束层（F-S5-P047-2） | A7 落码 | `::test_v7_weight_clip_and_size_filter` / `::test_v7_total_weight_never_exceeds_one` | ✅ 两例 PASS |
| B8 | **V8** 现金预算：`cash=100_000` 超预算组合 → `buy_cost<=budget+1e-6`、qty 为整手、`buy_cost` 逐值；收缩路径 `scale<1`；`qty=0` 标的计成本 **0**（F-S4-P047-2） | A8 落码 | `::test_v8_cash_budget_floor_and_min_commission` / `::test_v8_cash_budget_shrinks_when_over_budget` / `::test_v8_zero_quantity_costs_nothing` | ✅ 三例 PASS |
| B9 | **V9** 成本同源（净现金式，F-S4-P047-6）：`estimate_buy_cash(a) == a + ExecutionSimulator._calculate_cost(a, BUY)`，参数化 `a ∈ {1_000, 5_000, 100_000}` 三档逐位 | A3 落码 | `::test_v9_cost_same_source`（3 参数实例） | ✅ 3 参数实例 PASS |
| B10 | **V10** 金字塔：浮亏不加（`99 < entry 100`）；满足步长加仓且增量递减（`decay**n`：1.0 → 0.5）；`add_count>=max_adds` 停止；`pyramid_enabled=False` 恒 0 | A9 落码 | `::test_v10_pyramid_adds_only_on_profit_and_decays` / `::test_v10_pyramid_respects_max_adds_and_switch` | ✅ 两例 PASS |
| B11 | **V11** 持仓龄：建仓日=1；跨周末按交易日计（`trade_dates` 过滤）；`current<entry` → `ValueError` | A10 落码 | `::test_v11_holding_age_counts_trading_bars` | ✅ PASS |
| B12 | **V12** 引擎闸门（A2）：现金不足 → 不成交、现金不动、`get_pending_orders()` 长度不变；现金充足 → 成交且 `cash == 初始 − estimate_buy_cash(amount)`；**`continue` 而非 `break`**：大额 BUY 被拒后，后续小额 BUY 仍成交（F-S6-P047-1 补测，双标的场景） | A11 落码 | `::test_v12_gate_skips_buy_when_cash_insufficient` / `::test_v12_gate_allows_buy_when_cash_sufficient` / `::test_v12_gate_continues_to_later_orders_after_skip` | ✅ 三例 PASS |
| B13 | **golden ×3**（D6 规格锁定，非行为录制）：`P047_S1` 凯利 / `P047_S2` vol-target / `P047_S3` 现金预算；JSON 含 `inputs`/`config`/`expected`/`tolerance`；`GOLDEN_DIR=tests/golden/p047`；目录隔离测试断言根目录无同名 case | A4/A5/A8 落码 | `::test_p047_golden_kelly` / `_vol_target` / `_cash_budget` / `::test_p047_case_files_isolated_from_root_baseline` | ✅ 4 例 PASS；`-k golden` **18 passed / 828 deselected**；`git status tests/golden/` 仅 `?? tests/golden/p047/` |
| B14 | **红态口径声明**：本批落码前移至 Step 5（批次流程定义），测试与实现同批产出，**无 TDD 红态读数**；替代取证 = DESIGN §5 规格先于实现（Step 3→4 已通过）且 golden 期望由闭式手推（Step 6 §11.1 E2 独立复算逐位）。P-045 的「红态 10 failed」形态仅适用其 Step 9 TDD 路径，**禁止套用** | Step 5 完成 | 读码 + DESIGN §5/§11 | ✅ 口径成立：本批无红态读数，替代取证 = DESIGN §5 规格（Step 4 pass）+ DESIGN §11.1 E2 闭式复算（S1/S2/S3 逐位一致） |

## 3. C 组：不变式（DESIGN I1-I10 + 既有语义，10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1** 零行为：既有 golden **15 零重录**（`-k golden` 18 = 15 + 3 新）；`engine_v2` diff 限 A11 三处；`agents/` / `core/strategy.py` / `core/risk_manager.py` / `core/target_positions.py` / `core/execution_policy.py` / `filter/` **零 diff** | 全量实现 | `pytest -k golden` + `git status` | ✅ `-k golden` 18 全绿（既有 15 无重录）；`git status --short` 干净面：已跟踪源码改动仅 `core/engine_v2.py`，上述受保护路径 `git diff` 空 |
| C2 | **I2** 现金非负：三条 V12 路径后 `tracker.get_cash() >= 0`；闸门不产生负现金、不预支 | A11 落码 | V12 | ✅ V12 三例断言通过；闸门仅读 `tracker.get_cash()`，无扣款/预支 |
| C3 | **I3** 成本恒等：`estimate_buy_cash` 与 `ExecutionSimulator._calculate_cost(…, BUY)` 三档逐位相等；闸门所需现金与模拟器扣款口径一致 | A3/A11 落码 | V9 | ✅ V9 三档逐位 PASS；引擎闸门复用同一函数（L28 import + L905-918） |
| C4 | **I4** 纯函数：见 A12（零 try/except、零 I/O、import 白名单、无全局态） | A1-A12 落码 | AST 静态检查 | ✅ 同 A12：`try/except` 0、`# type: ignore` 0、import 白名单成立 |
| C5 | **I5** 不加杠杆：vol-target `scale<=1`；`max_weight<=1`；所有路径总权重 ≤1（含裁剪后与预算缩放后） | A5/A7/A8 落码 | V4/V7/V8 | ✅ V4（`scale<=1`）/ V7（总权重 ≤1）/ V8（预算收缩、`buy_cost<=budget`）PASS |
| C6 | **I6** 禁摊亏：`pyramid_step` 在 `price<entry_price` 恒 0；递减加仓 `decay<1` | A9 落码 | V10 | ✅ V10：`price=99 < entry=100` → 0；增量 1.0 → 0.5 |
| C7 | **I7** 预算保守：只用当前现金（`cash·cash_buffer`）、floor 量化、`buy_cost<=budget`；3 次不收敛宁可 `scale=0` 空仓不超支 | A8 落码 | V8 | ✅ V8：`buy_cost<=budget+1e-6`；仅用传入 `cash`；不收敛分支 `scale=0`（L413-415） |
| C8 | **I8** 计数链：`-k golden` **15 → 18**（收集数口径）；`18 = 15 + 3`，新 case 不进根目录 `glob("*.json")==set(CASE_IDS)` 断言 | B13 落码 | `pytest --collect-only -k golden` | ✅ `--collect-only -k golden` → **18/846 tests collected (828 deselected)**；`18 = 15 + 3` |
| C9 | **I9** 无配置扩散：`core/config.py` **零 diff**（`SizingConfig` 独立 dataclass）；`pyproject.toml` / `uv.lock` **零 diff** | 全量实现 | `git diff` | ✅ `git status --short` 不含三文件；`git diff --stat` 仅 `core/engine_v2.py` + `docs/PROGRESS.md` |
| C10 | **I10** 等预算对拍：等权输入下 `pct≈1/n`，且与 `RiskParityOptimizer(OptimizerConfig(max_weight=1.0))` 一致；「默认 `max_weight=0.10` clip 后非 ERC」登记 P-046 不在本批修；另：`build_target_positions` / `core/portfolio.py` / `tests/_golden_cases.py` / `tests/test_golden_baseline.py` / `tests/golden/G*.json` **零 diff** | A6 落码 | V6 + `git status` | ✅ `::test_v6_risk_parity_equal_budget_crosscheck` PASS（`pct≈1/3`）；上述文件 `git diff` 空 |

## 4. D 组：门禁、提交与文档（9 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest 全量 **846 passed**（821 + 25，`MPLBACKEND=Agg` 口径） | 全量实现 | 全量末行 | ✅ **846 passed, 184 warnings, 60.32s**（Python312 + `MPLBACKEND=Agg`） |
| D2 | `-k golden` **18 passed / 828 deselected**；`git status tests/golden/` 仅新增 `p047/` 三文件、既有 15 零改动 | 全量实现 | 命令 + `git status` | ✅ **18 passed, 828 deselected, 18.07s**；`git status` 仅 `?? tests/golden/p047/` |
| D3 | black 变更文件 clean；`core tests` 计数 = 基线 + 2（+`core/sizing.py` +`tests/test_p047_position_sizing.py`）；全仓 = 基线 + 2；`tests/*.py` **95**（94 + 1） | 新文件落盘 | `black --check` 双口径 + 计数 | ✅ black 26.5.0：`core tests` **137 files left unchanged, 0 reformatted**（135+2）；全仓 **205 unchanged, 0 reformatted**（203+2）；`tests/*.py` **95** |
| D4 | mypy **CI 等价口径**（`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples`）**109 files 0 issue**（108 + 1 源） | 全量实现 | 逐字命令 | ✅ **Success: no issues found in 109 source files** |
| D5 | AST `except Exception` **22（不变）**；`core/sizing.py` 新增 `try/except` / `# type: ignore` 均 **0** | A12 落码 | AST 静态检查 + `git diff` | ✅ AST **22**（agents 11 / filter 5 / scripts 2 / batch_backtest 2 / strategy_evaluation 1 / cli 1）；`core/sizing.py` try/except **0**、`# type: ignore` **0** |
| D6 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | 全量实现 | 命令 + `git diff` | ✅ `uv lock --check` → `Resolved 148 packages in 9ms`，exit **0**；两文件零 diff |
| D7 | 全量回归无 P-047 相关失败；Tk/Tcl 环境性异常须以 `MPLBACKEND=Agg` 口径复跑排除（O-S5-P047-1），若仍复现须单独隔离并记录为环境缺陷非本批回归 | D1-D6 通过 | 两次复跑对照 | ✅ 两次全量复跑（前台 60.32s / 后台副本 65.19s）均 **846 passed**，零失败；Agg 口径下无 Tk/Tcl 异常 |
| D8 | 提交原子（**10 文件**）：新源 1（`core/sizing.py`）+ golden 3（`tests/golden/p047/P047_S1/S2/S3.json`）+ 新测试 1（`tests/test_p047_position_sizing.py`）+ 已跟踪源订正 1（`core/engine_v2.py`）+ 新文档 3（RESEARCH / DESIGN / CHECKLIST）+ 已跟踪文档 1（PROGRESS）；CI 四 job 全绿（lock-check / 3.10 / 3.11 / 3.12） | D1-D7 通过 | `git show --stat` + `gh run view` | [待 Step 10] |
| D9 | 文档回填：DESIGN §11（Step 6）/ §12（Step 8）/ PROGRESS §3.52.6-§3.52.10 / 本文件 **45/45** 实测列；CHANGELOG 是否需要条目按仓库惯例判定 | D8 通过 | 读回 | [待 Step 10] |

---

## 5. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **45**（A 12 + B 14 + C 10 + D 9 = 45，逐表行数机械计数） |
| 实测列回填（Step 9） | **43/45 `✅`**（A 12 + B 14 + C 10 + D 7）；**2 × `[待 Step 10]`**（D8/D9）；`❌` **0**；累计 `45 = 43 + 2` |
| 新用例数 | **25 收集**（23 函数：V1-V12 共 19 个函数 + golden/隔离 4 个；`v9` 参数化 3 → 净 +2 实例） |
| Step 9 门禁实测 | pytest **846**（60.32s）/ `-k golden` **18**（828 deselected）/ black **137·205**（0 reformatted）/ mypy **109 files 0 issue** / AST **22** / `tests/*.py` **95** / `uv lock --check` exit **0** |

> **RULE-2 统计溯源**：45 = 12 + 14 + 10 + 9（逐表行数）；846 = 821 + 25（B1-B13）；18 = 15 + 3（B13）；109 = 108 + 1（A1-A12 同文件 `core/sizing.py`）；95 = 94 + 1（B1-B14 同文件）；AST 22 不变（A12 零 try/except）；black 增量 +2 = 1 源 + 1 测试。
> **RULE-5 声明**：Step 1-7 文档作者 **DeepSeek-V4.1-Flash**（同一基座）；Step 2 / Step 4 / Step 6 / Step 8 复审**异构成立**（GLM-5.3-Flash：RESEARCH §13 / DESIGN §10 / DESIGN §11 / DESIGN §12）；Step 10 终审**待 GLM-5.3-Flash**。

---

## 6. Step 7 → Step 8 交接

1. **核计数链**：821 + 25 = **846**；15 + 3 = **18**（deselected = 846 − 18 = 828）；108 + 1 源 = **109**；94 + 1 = **95**；AST **22 不变**；black 增量 **+2**（绝对基线以 Step 9 复跑为准，禁止沿用 P-045 的 135/203 旧读数）。
2. **核零预填**：Step 9 前 `[待 Step 9]` 须为 **43**、`[待 Step 10]` 须为 **2**；任何 `✅` 出现即为违规（Step 9 已按此执行：回填前实测 43 + 2）。
3. **核 ID 不混用**：DESIGN 裁决 `D1-D7`（§2.0）与本文件 **D 组 D1-D9** 同名不同义，引用一律写 `DESIGN-D*`；**RESEARCH §8 I1-I10 与 DESIGN §6 I1-I10 同号不同义**（如 RESEARCH I4=确定性 vs DESIGN I4=纯函数），C 组一律锚定 **DESIGN 口径**（O-S8-P047-1，DESIGN §12.2）；DESIGN **派生需求 D-R1~D-R4**（§12.3）与 RESEARCH 断言编号无冲突；用例 `V1-V12` 与 P-013 golden `G1-G7` 隔离；发现编号 `F-S{2,4,5,6,8,9}-P047-*`。
4. **核 golden 方法论**：S1/S2/S3 为**规格锁定**（闭式手推），若 Step 9 实测与期望不符 → **先审规格**（DESIGN R6），禁止改期望迁就实现；`git status tests/golden/` 只允许出现 `p047/` 三个新文件。
5. **核行号口径**：本文件行号 @未提交工作区；提交后须以 commit hash 绑定重取（F-S10-P045-2 同类风险，Step 9 复跑时逐条核对）。
6. **核不做清单**：不做空/负权重（P-050，`apply_sizing` 已 fail-fast）、不接线 `apply_sizing` 到引擎/多策略（P-051）、不改 `core/config.py`、不改 `build_target_positions`、不做部分成交、不改队列遍历顺序（R2）、不做 `asset_costs` 覆盖下的精确同源（F-S4-P047-5 限定）。
7. **核遗留登记**：P-046（风险预算求解 / clip 破坏 ERC）、P-048（R1/R2 观察与风险动作闭环）、O-S5-P047-1/2（Tk/Tcl 环境缺陷、`verify_p045` 缺 `vectorbt`）、O-S6-P047-1/2（V2 字面数值等价覆盖、kelly 分支顺序冗余）、O-S8-P047-1/2（I 系列同号不同义已注记、`SizingState` JSON round-trip 随 P-051）；**按 DESIGN §12.3 派生需求 D-R1~D-R4 核对实现**（no_price 处置 / atr<=0 防御 / 三预留字段零消费 / golden S3 round 反推）。

---

## 7. Step 9 验收小结（2026-11-18）

| 门禁 | 命令 / 方法 | 实测 | 目标 | 判定 |
|------|-------------|------|------|------|
| pytest 全量 | `MPLBACKEND=Agg` + Python312 `pytest -q` | 846 passed, 184 warnings, 60.32s | 846 | ✅ |
| golden 计数 | `pytest -q -k golden` | 18 passed, 828 deselected, 18.07s | 18 / 828 | ✅ |
| 用例收集 | `pytest --collect-only -q tests/test_p047_position_sizing.py` | **25 tests collected** | 25 | ✅ |
| black（`core tests`） | `black --check core tests` | 137 unchanged, 0 reformatted | 基线+2 | ✅ |
| black（全仓） | `black --check .` | 205 unchanged, 0 reformatted | 基线+2 | ✅ |
| mypy（CI 等价） | 十四目录 `mypy` | Success: no issues found in **109** source files | 109 / 0 | ✅ |
| AST 盲区 | `except Exception` 静态扫描（core 外） | **22**（agents 11 / filter 5 / scripts 2 / batch_backtest 2 / strategy_evaluation 1 / cli 1） | 22 不变 | ✅ |
| 测试文件数 | `tests/*.py` 计数 | **95** | 95 | ✅ |
| lock 一致性 | `uv lock --check` | Resolved 148 packages in 9ms，exit **0** | exit 0 | ✅ |
| diff 范围 | `git diff --stat` | `core/engine_v2.py` **+16/−0**；`docs/PROGRESS.md` +143 | 见 A11/C9 | ✅ |
| 纯函数性 | AST + 读码 | `core/sizing.py` try/except **0**、`# type: ignore` **0** | 0 | ✅ |
| golden 目录 | `git status tests/golden/` | 仅 `?? tests/golden/p047/`（3 JSON） | 3 新 | ✅ |

**发现（当轮处置）**：

- **F-S9-P047-1（P3，文档笔误）**：本文件 A2 的 DoD 在 Step 7 版写作 `CashBudgetResult` 含 `qty`，与 DESIGN §D2 及实现（[sizing.py L109-116](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L109-L116)，4 字段）不符。**处置**：以 DESIGN 为准订正 DoD 文本，`qty` 由 `weights`（已含整手折算后的权重）+ `buy_cost` 表达，无需新增字段；不影响 A8/V8/golden S3 的任何断言。

**结论**：45 项中 **43 项 ✅ / 2 项 `[待 Step 10]` / 0 项 ❌**，全部门禁达标，**准予进入 Step 10 终审**。
