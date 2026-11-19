# CHECKLIST：P-048 风险 overlay（组合级权重缩放）

> **批次**: P-048 · **T1**（新建 `core/risk_overlay.py` 纯函数模块 + `set_signal` 可选校验 + engine 三处 opt-in 接线 + 2 测试模块 + S15 场景）
> **上游**: [DESIGN_p048](DESIGN_p048_risk_overlay.md)（§5 缩放算法 / §6 策略 / §7 接入与门控 / §8 测试与场景 / §9 改动面 / §10 能力边界 / §12 I1-I7 / §15 A1-A9 / **§18.1 Step 4 pass：1 P2 + 5 P3** / **§18.2 Step 6 pass：1 P2 + 4 P3 + 5 正面核验** / **§18.3 Step 8 pass：2 P2 + 7 P3 + 1 INFO**）；[IMPL_p048](IMPL_p048_risk_overlay.md)（§2-§4 代码骨架 / §5 T4 / §6 T5 接线 / §7 T6 测试与 S15 / §8 12 锚点 / §9 门禁 / §10 风险回退 / §11 五项微调 / §13 Step 6 吸收 5/5）；[RESEARCH_p048](RESEARCH_p048_risk_overlay.md)（§15 DoD / §18 Step 2 pass：2 P2 + 5 P3）
> **状态**: Step 7 产出（2026-11-19，DeepSeek-V4.1-Flash）；**Step 8 复审 PASS**（[DESIGN §18.3](DESIGN_p048_risk_overlay.md)：2 P2 + 7 P3 + 1 INFO，修正已 10/10 吸收——计数链 / 基线读数以本文件现行值为准）；**Step 9 验收回填完成（2026-11-19，GLM-5.3-Flash，异构于 Step 5 落码）**：A/B/C/D1-D9 共 **39 项全 `✅`**（门禁对照见 §8）；**Step 10 终审 PASS + D10 关闭（2026-11-19/20，Qwen3.8-Max 终审 / DeepSeek-V4.1-Flash 回填）**：**40 项全 `✅`**，提交 `c12497c`，CI run `44558140801` 四 job 全绿
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；禁止预填
> **行号口径（F-S10-P045-2 教训）**: 本文件行号 @未提交工作区（基线 `73f9807` + diff）；主提交 **`c12497c`** 已落盘，行号对 `c12497c` 有效（提交后复核无位移）
> **基线读数（@`73f9807`，P-059 关闭）**: pytest **906** / `-k golden` **18** / `-k p059` **60**（Step 8 实测订正 F-S8-P048-1：原记 39 系 P-059 B8 `test_p059_scenarios.py` 单模块 collect 误升格）/ 全量 collect **906** / mypy **110 files 0** / black `core tests` **146**、全仓 **215** / `tests/*.py` **104** / AST `except Exception`（core 外生产面）**22** / `uv lock --check` exit **0**
> **目标读数**: pytest **932**（906 + 26，Step 5 实测订正 F-S5-P048-3）/ `-k golden` **18（零重录）** / `-k p059` **63**（60 + 3）/ 全量 collect **932** / mypy **111 files 0**（+1 源）/ black `core tests` **149**、全仓 **218**（+3）/ `tests/*.py` **106**（+2）/ AST **22（不变）** / `uv lock --check` exit **0**

---

## 1. A 组：模块契约（12 项，锚 DESIGN §4-§10 + IMPL §2-§5）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `RiskOverlayConfig` 为 `@dataclass(frozen=True)`，**8 字段**（`enabled=False` / `target_vol=None` / `defensive_policy="none"` / `dd_soft=0.08` / `dd_hard=0.12` / `b_min=0.0` / `scale_floor=0.0` / `dd_hysteresis=False`）；`__post_init__` 校验四条：`b_min∈[0,1]` / `scale_floor∈[0,1]` / `0≤dd_soft<dd_hard≤1` / `target_vol>0`（非 None 时），违规抛 `ValueError`；**不校验策略键**（留给 `resolve_policy`，避免循环依赖） | 无（新建模块首类型） | 读码 + `::test_config_validation` | `✅` [risk_overlay.py L47-L70](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L47-L70)：`frozen=True` 8 字段默认值逐项一致，`__post_init__` 四校验；`::test_config_validation` pass |
| A2 | `DeRiskContext`（`drawdown`/`peak_nav`/`current_nav`/`weights`）、`DeRiskPlan`（`scale=1.0`/`action="none"`/`weights=None`/`reason=""`/`detail={}`）、`OverlayResult`（`weights`/`scale_vol`/`scale_dd`/`scale_total`/`cash_residual`/`action`/`reason`）三者均 `frozen=True`；`DeRiskPlan.weights` 为**预留通道**，默认 `None` 表示标量缩放路径 | A1 落码 | 读码 + `__all__` 11 符号（F-S8-P048-5） | `✅` [L46-L91](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L46-L91) 三 dataclass 均 `frozen=True`（RiskOverlayConfig L46 / DeRiskContext L72 / DeRiskPlan L79；F-S10-P048-1 订正区间）；`DeRiskPlan.weights=None` 预留通道；`__all__` 11 符号 @L28-L40 |
| A3 | `IDefensivePolicy` 为 `@runtime_checkable` Protocol，仅 `name` + `plan(ctx) -> DeRiskPlan`；docstring 声明「实现必须无状态、不得持有跨 bar 记忆」（F-S6-P048-5）；`apply_overlay` 的 `policy` 注入点仅供单测 | A1 落码 | 读码 + `isinstance(policy, IDefensivePolicy)` | `✅` [L94-L103](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L94-L103)：`@runtime_checkable` Protocol 仅 `name`+`plan`，docstring 声明无状态（F-S6-P048-5）；policy 注入用例 `::test_i4_identity` pass |
| A4 | `CapabilityError(RuntimeError)` 定义于本模块；`SectorRotationPolicy` / `HedgeOverlayPolicy` 的 `plan` 直抛 `CapabilityError`（含具体阻断原因文案），**不静默降级为不变**；二者登记进注册表但不参与默认路径 | A1 落码 | 读码 + `::test_reserved_policies_raise` | `✅` [L43](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L43) `CapabilityError(RuntimeError)`；[L182-L205](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L182-L205) 两预留策略 `plan` 直抛（文案含阻断原因）；`::test_reserved_policies_raise` pass |
| A5 | 4 实现语义与 DESIGN §6.1 逐项一致：`NoDeRiskPolicy` 恒等；`CashScalingPolicy`（默认）`dd≤dd_soft→1`、`dd≥dd_hard→b_min`、中间 `1−t(1−b_min)`、`t=(dd−dd_soft)/(dd_hard−dd_soft)`；`FixedFloorPolicy` 单阈值；`TieredLadderPolicy` 取**最深命中档** | A2 落码 | 读码 + B2-B5 | `✅` [L119-L179](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L119-L179) 四实现语义与 DESIGN §6.1 逐项一致；B2-B5 全 pass |
| A6 | `TieredLadderPolicy.LADDER = ((0.08,0.5),(0.12,0.25),(0.20,0.0))` 为**类常量、不可配置**，docstring 明示本批不开放配置（F-S6-P048-3） | A5 落码 | 读码 | `✅` [L165-L169](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L165-L169) `LADDER` 类常量（非 `__init__` 参数），docstring 明示「本批档位为类常量，不可配置」 |
| A7 | `DEFENSIVE_POLICIES` **6 键**（`none`/`cash_scaling`/`fixed_floor`/`ladder`/`sector_rotation`/`hedge_overlay`）；`resolve_policy(name, config)` 未知键抛 `ValueError`（fail-loud，文案含可选键集）；所有策略统一 `__init__(config)` 无分支（IMPL §11 I-P048-2） | A4/A5 落码 | 读码 + `::test_registry_has_six_keys` + `::test_unknown_policy_raises` | `✅` [L208-L215](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L208-L215) 6 键；[L229-L234](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L229-L234) 未知键 `ValueError`（文案含 `sorted` 键集）；六策略统一 `__init__(config)`；两测试 pass |
| A8 | `OVERLAY_CAPABILITIES` 键集**完全等于** `{defensive_asset_rotation, hedge_overlay}`（各含 `supported=False` + `note`）；**零触碰** P-059 `CAPABILITY_BOUNDARIES` 8 键与 [_scenarios_assert.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_assert.py#L155-L170) 的精确键集断言（DESIGN §10 / A8） | A7 落码 | 读码 + `::test_overlay_capabilities_exact` + `git diff tests/_scenarios_assert.py` | `✅` [L216-L226](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L216-L226) 键集精确等于 2 键（各 `supported=False`+`note`）；`git diff tests/_scenarios_assert.py` 空输出（零触碰）；`::test_overlay_capabilities_exact` pass |
| A9 | `compute_drawdown(nav_history)`：空序列 → `(0.0,0.0,0.0)`；`peak=max(nav_history)`、`current=nav_history[-1]`；`peak<=0 → 0.0`；结果 clip 到 `[0,1]`；**不 import** [guard_pipeline.py](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py)（组合级不拖入订单级组件） | A1 落码 | 读码 + `import` 白名单 + C6 | `✅` [L237-L250](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L237-L250) 空序列→`(0.0,0.0,0.0)`/`peak=max`/`peak≤0→0.0`/clip `[0,1]`；import 区 [L10-L17](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L10-L17) 仅 numpy+core.sizing（不 import guard_pipeline）；`::test_i6_drawdown_bounds` pass |
| A10 | `apply_overlay(...)` 三层：`scale_vol`（`target_vol=None` → 1.0）/ `scale_dd=plan.scale` / `scale_total=max(scale_floor, scale_vol×scale_dd)`；`plan.weights is None` → 逐值乘 `scale_total`；**不重新归一化**；`cash_residual=1−Σw_out`；`reason` 由两腿 reason 以 `+` 拼接；`config.dd_hysteresis=True` → `CapabilityError` | A9 落码 | 读码 + C1-C5 | `✅` [L253-L303](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L253-L303) 三层 scale / [L289-L292](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L289-L292) `plan.weights` 分支 / [L300](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L300) `cash_residual` / [L294-L302](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L294-L302) reason `+` 拼接；[L263-L264](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L263-L264) dd_hysteresis→`CapabilityError`；C1-C5 全 pass |
| A11 | vol 腿**直接调用** `core.sizing.vol_target_scale`，不内联重写公式（F-S4-P048-2）；`cov is None or not codes` 且 `target_vol` 非 None → `scale_vol=1.0` 且 `reason` 含 `zero_vol`，**不抛错**（降级而非失败） | A10 落码 | 读码 + `::test_i5_monotone` | `✅` [L268-L276](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L268-L276) 直接调用 `core.sizing.vol_target_scale`（不内联）；`cov is None or not codes` → `scale_vol=1.0` + `reason="zero_vol"` 不抛错；`::test_i5_monotone` pass |
| A12 | `set_signal(signal, *, mode, external_max_weight=None)`：签名 +1 关键词参数；超限校验**置于 `if mode == "weights":` 块内**（默认 `None` 逐字零行为，含既有 4 个非法用例）；超限抛 `ValueError` 且文案含最坏 code / 日期 / 实测值 / 上限 | A2 落码 | 读码 + B9 + `pytest -q tests/test_p044*` | `✅` engine_v2 [L366-L378](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L366-L378) 签名 +1 kw-only；[L396-L405](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L396-L405) 校验置于 `weights` 块内；`pytest -q tests/test_p044_strategy_interface.py` **8 passed**；B9 三例 pass |

## 2. B 组：测试与场景交付（11 项，锚 IMPL §7）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | `tests/test_p048_risk_overlay.py` 落盘，覆盖 IMPL §7.1 表 **15 项**（ramp 三点 / b_min / fixed_floor / ladder / 预留抛错 / 未知键 / 注册表 6 键 / 能力表 2 键 / I1 / I2 / I3 / I5 / I4 / 滞回 / 配置校验），无空缺项 | T1-T3 落码 | `pytest --collect-only -q tests/test_p048_risk_overlay.py` | `✅` collect **16**（IMPL §7.1 15 项 + I6 专测 = 16；函数清单逐项核对无空缺） |
| B2 | **ramp 三点闭式（A5 禁录制）**：`dd_soft=0.08 / dd_hard=0.12 / b_min=0` 下 `dd=0.05→1.0`、`0.10→0.5`、`0.15→0.0`；期望值须与 DESIGN §6.2 表逐位一致，且可手推 | A5 落码 | `::test_ramp_three_points` | `✅` pass（dd=0.05→1.0 / 0.10→0.5 / 0.15→0.0，与 DESIGN §6.2 表逐位一致，闭式手推） |
| B3 | `b_min=0.2` 两点：`dd=0.10 → 1−0.5×0.8 = 0.6`；`dd=0.15 → 0.2`（硬阈覆盖） | A5 落码 | `::test_ramp_with_b_min` | `✅` pass（dd=0.10→0.6 / 0.15→0.2） |
| B4 | `fixed_floor` 两点：`dd=0.11 → 1.0`；`dd=0.13 → b_min` | A5 落码 | `::test_fixed_floor` | `✅` pass（dd=0.11→1.0 / 0.13→b_min） |
| B5 | `ladder` 最深命中：`dd=0.13 → 0.25`（命中 0.08 与 0.12，取最深）；`dd=0.21 → 0.0`（命中三档） | A5 落码 | `::test_ladder_deepest_hit` | `✅` pass（dd=0.13→0.25 最深命中 / 0.21→0.0 三档全命中） |
| B6 | 抛错三态齐备：2 个预留策略 → `CapabilityError`；`resolve_policy("nope", cfg)` → `ValueError`；`dd_hysteresis=True` 的 `apply_overlay` → `CapabilityError` | A4/A7/A10 落码 | `::test_reserved_policies_raise` / `::test_unknown_policy_raises` / `::test_hysteresis_raises` | `✅` 三测试 pass（2 预留策略 `CapabilityError` / 未知键 `ValueError` / `dd_hysteresis` `CapabilityError`） |
| B7 | 注册表与能力表**精确键集**断言：`set(DEFENSIVE_POLICIES)` == 6 键；`set(OVERLAY_CAPABILITIES)` == 2 键（同型精确相等，防悄悄扩容） | A7/A8 落码 | `::test_registry_has_six_keys` / `::test_overlay_capabilities_exact` | `✅` 两测试 pass（`set(DEFENSIVE_POLICIES)`==6 键 / `set(OVERLAY_CAPABILITIES)`==2 键精确相等） |
| B8 | `tests/test_p048_overlay_engine.py` 落盘，覆盖 IMPL §7.2 **4 项**：`risk_overlay=None` 与基线 NAV 一致；`enabled=False` ≡ `None` 逐值相等；`enabled=True` 权重按 `scale_total` 等比缩小（**夹具须显式设小 `cov_lookback` 并断言 `scale_vol < 1.0`**，F-S6-P048-4 防 `returns_data=None` 假阳性）；未启用时 `_nav_history == []` | T5 落码 | `pytest --collect-only -q tests/test_p048_overlay_engine.py` | `✅` collect **7**（4 接线 + 3 external_max_weight）；`test_enabled_scales_weights` 夹具 `cov_lookback=2` 且断言 `scale_vol<1.0`（F-S6-P048-4）；`test_nav_history_not_accumulated_when_disabled` 断言 `_nav_history==[]`；`test_default_none_keeps_baseline`（F-S5-P048-5 重命名后 `-k golden` 恢复 18） |
| B9 | **T4 补登验收（F-S7-P048-1）**：IMPL §7.1/§7.2 未列 `external_max_weight` 用例，依 DESIGN §9.2 须至少 **3 例**——超限抛 `ValueError`（含最坏 code/日期）、合规通过、`external_max_weight=None` 时既有 weights 合法/非法用例逐字不变 | A12 落码 | 新增 `::test_external_max_weight_*`（3 例）+ 既有 `test_p044_*` 全绿 | `✅` 3 例 pass（rejects_breach 含最坏 code/日期文案 / allows_within_limit / default_none_unchanged）+ `test_p044_strategy_interface.py` **8 passed** |
| B10 | **S15 场景定义合规**：`rebalance={"frequency":"daily"}`（**必须显式**，否则默认 `N_days=5` 只再平衡一次）、`cost=NO_COST`、`optimizer={"cov_lookback":2}`、`target_vol=None`、`defensive_policy="cash_scaling"`、`dd_soft=0.02`、`dd_hard=0.08`、`b_min=0.0`、单标的、显式 open/close 五列；场景注释含**三项时序口径**（创建日收盘价定数量 / 次日 open 成交 / `rebalance(d)` 只见 `nav(0..d-1)`）与**手算八步**（I-P048-5） | T6 落码 | 读码 `_scenarios_cases.py` S15 | `✅` [L647-L721](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_cases.py#L647-L721)：NO_COST / `rebalance daily` 显式（L689）/ `cov_lookback=2` / `target_vol=None` / `cash_scaling` / dd_soft=0.02 / dd_hard=0.08 / b_min=0.0 / 单标的 / OHLC 五列显式；**三项时序口径** L649-L652；**手算八步** L653-L666（含 `value_buffer=0.985`，F-S5-P048-1 订正） |
| B11 | **S15 期望（手算闭式，非录制；6 日路径，F-S5-P048-1/-2 订正）**：fills **全集** `(d1, BUY, 9800, 10.00)` / `(d4, SELL, 4400, 9.20)` / `(d5, SELL, 5400, 9.20)`（`_match_fills` 双向精确匹配，漏声明即红）；nav_days d1=104,900 / d2=100,000 / d3=92,160 / d4=92,160；`final_cash = final_nav = 92,160`；`final_positions == {}`；末日持仓已归零 → 无清仓挂单与强平双写；场景计数 18（含 `test_registry_contract` 第二处硬编码） | B10 落码 | `::test_p059_scenario[S15]` + `::test_registry_contract` | `✅` S15 三实例全 pass（scenario / 第二参数化 / metamorphic，均在 `-k p059` 63 内）；fills 全集 3 条 `_match_fills` 双向精确匹配；nav_days d1=104,900 / d2=100,000 / d3=92,160 / d4=92,160；final_cash=final_nav=92,160；`final_positions=={}`；计数 18 双写：[_scenarios_cases.py L729](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_cases.py#L729) + `test_registry_contract` pass |

## 3. C 组：不变式（DESIGN §12 I1-I7，7 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1** `0 ≤ scale_total ≤ 1`（不加杠杆）：参数网格扫描 `dd_soft/dd_hard/b_min/scale_floor/target_vol` 全组合下恒成立 | A10 落码 | `::test_i1_scale_bounds` | `✅` pass（参数网格全组合 `0≤scale_total≤1` 恒成立，DD 上升→scale 下降；集合断言见 C7） |
| C2 | **I2** 标量乘法**不重新归一**：`Σ w_out ≤ Σ w_in`（`scale_total ≤ 1` 时）；**预留 `plan.weights` 通道除外**（Σ 由策略负责，已在 DESIGN §12 声明） | A10 落码 | `::test_i2_no_renormalize` | `✅` pass（`scale_total≤1` 时 `Σw_out≤Σw_in`，残差留现金不回填） |
| C3 | **I3** `cash_residual = 1 − Σ w_out ≥ 0`，且 `Σw_out + cash_residual == 1`（浮点 1e-12 容差） | A10 落码 | `::test_i3_cash_residual` | `✅` pass（`Σw_out + cash_residual == 1`，浮点 1e-12 容差） |
| C4 | **I4 精确条件**：`not enabled` **或**（`defensive_policy=="none"` **且** `target_vol is None`）⇒ `w_out == w_in` **且** `scale_total == 1.0`；反例须证明 `policy="none"` 非门控——`target_vol` 非 None 时 vol 缩放仍生效 | A10 落码 | `::test_i4_identity`（含反例） + `::test_enabled_false_equals_none` | `✅` 两测试 pass（恒等路径 `scale_total==1.0`；反例 `target_vol` 非 None 时 `policy="none"` 仍缩放，证明非门控；`enabled=False` ≡ `None` 逐值相等） |
| C5 | **I5** `scale_dd` 对 DD 单调不增；`scale_total = max(scale_floor, scale_vol·scale_dd)` 的下界由 `scale_floor` 兜住（含 `scale_floor>0` 用例）；σ 越大 `scale_vol` 越小 | A10/A11 落码 | `::test_i5_monotone` | `✅` pass（σ=0.1→`scale_vol`≈0.5 / σ=0.2→0.25 单调减；`scale_floor>0` 兜底用例含 `max()` 生效路径） |
| C6 | **I6** `drawdown ∈ [0,1]`、`peak = max(nav_history)`：含空序列 / 单点 / 单调上涨（DD=0）/ 深回撤 >100% 需 clip 的边界用例 | A9 落码 | `::compute_drawdown` 直接断言 | `✅` pass（空序列→(0,0,0) / 单点 / 单调上涨 DD=0 / 深回撤 clip 上界 1.0，`::test_i6_drawdown_bounds`） |
| C7 | **I7** 输出权重非负、代码集合 ⊆ 输入集合（`plan.weights` 通道除外）；`apply_overlay` 不改写入参映射 | A10 落码 | `::test_i1_scale_bounds` 附带集合断言 | `✅` pass（输出权重非负 / 代码集合 ⊆ 输入集合 / 入参映射不被改写） |

## 4. D 组：门禁、改动面与文档（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest 全量 **932 passed**（906 + 26 = 16 纯函数 + 4 接线 + 3 external_max_weight + 3 场景族实例，`MPLBACKEND=Agg` 口径，**venv 解释器**见 DESIGN §18.3.3） | 全量实现 | 全量末行 | `✅` `================ 932 passed, 219 warnings in 121.75s (0:02:01) ================`（`collected 932 items`；`MPLBACKEND=Agg` + `.venv` 解释器） |
| D2 | `-k golden` **18 passed 零重录**；`git status --short tests/golden/` **空输出**（A3） | 全量实现 | 命令 + `git status` | `✅` **18 passed, 914 deselected**（零重录）；`git status --short tests/golden/` **空输出** |
| D3 | `-k p059` **63 passed**（基线 **60**，Step 8 实测订正 F-S8-P048-1；S15 参与 3 处参数化 +3）；全量 `--collect-only` **932**（906 + 26）；场景计数断言（`_scenarios_cases.py` L652 与 `test_registry_contract`）均为 `18` | B11 落码 | 两条命令 + 读码 | `✅` `--collect-only -q -k p059` → **63/932 collected（869 deselected）**；`-k p059` 全量跑含 S15 三实例全 pass；计数 18 双写（[_scenarios_cases.py L729](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_cases.py#L729) + `test_registry_contract`）均通过（B11） |
| D4 | mypy **CI 等价命令**（`--explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples`，逐字对齐 [tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46)）**111 files 0 issue**（110 + 1） | 全量实现 | 逐字命令 | `✅` **111 files: no issues found in 31.13s**（逐字对齐 tests.yml L46；含 F-S9-P048-1 修正后复跑） |
| D5 | black `core tests` **149**（146 + 1 源 + 2 测试）、全仓 **218**（215 + 3），均 **0 reformatted**；`tests/*.py` **106**（104 + 2 新测试模块） | 新文件落盘 | `black --check` 双口径 + 计数 | `✅` core tests **149 files would be left unchanged** / 全仓 **218 files would be left unchanged**；`Get-ChildItem tests\*.py` = **106** |
| D6 | AST `except Exception`（core 外生产面）**22 不变**；`core/risk_overlay.py` 内 `try/except` **0** 且 `# type: ignore` **0** | A1-A12 落码 | AST 静态扫描 + 读码 | `✅` core 外 **22**（P-029 命令：agents 11 / filter 5 / scripts 2 / batch_backtest 2 / strategy_evaluation 1 / cli.py 1，构成与 PROGRESS L130 一致）/ core **29**（双口径同源 P-059）；`risk_overlay.py` `ast.Try` = **0** 且 `type: ignore` = **0**；engine_v2 增量行（+47/−1）无 `try`/`except`。**F-S9-P048-1**：初测 Try=1、type-ignore=1（`resolve_policy` EAFP + 裸 `type` 值类型），Step 9 内 LBYL 修正后复测 0，规格达成 |
| D7 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` **零 diff** | 全量实现 | 命令 + `git diff` | `✅` `uv lock --check` → `Resolved 148 packages` exit **0**；`git diff --stat -- pyproject.toml uv.lock` **空输出** |
| D8 | **改动面白名单**：**新建 7**（`core/risk_overlay.py` + `tests/test_p048_risk_overlay.py` + `tests/test_p048_overlay_engine.py` + 四文档）；**改 7**（`core/config.py` +8 / `core/engine_v2.py` +48 / `tests/_scenarios_cases.py` / `tests/_scenarios_builder.py` / `tests/test_p059_scenarios.py`〔第二处计数硬编码，F-S5-P048-4〕/ `scripts/verify_scenario.py`〔docstring 计数〕/ `docs/PROGRESS.md`）；**零 diff 面**：`core/guard_pipeline.py` / `core/sizing.py` / `core/config_v2.py` / `tests/_scenarios_assert.py` / `tests/_scenarios_spec.py` / `tests/golden/`；回退点按 IMPL §10 可执行（删新源 + 撤 6 锚点 + 撤 S15；T4 可单独回退） | 全量实现 | `git diff --stat` + `git status --short` + 读 IMPL §10 | `✅` `git status --short` = **M×7 + ??×7 = 14 文件**，与白名单逐项吻合；numstat：`core/config.py` **7/1**（总 8 行）、`core/engine_v2.py` **47/1**（总 48 行）；零 diff 面 6 项 `git diff --stat` **空输出**；回退清单读回（IMPL §10）可执行 |
| D9 | **文档回写**：DESIGN §16.1 Step 5 执行回写；PROGRESS 登记 P-048；IMPL §12 执行记录表由 `[待执行]` 改为实测；本文件 D8 引用的回退清单与 IMPL §10 逐项一致 | D1-D8 通过 | 读回 diff | `✅` [DESIGN §16.1 @L470](file:///f:/Coding/Factor_Trading_v3.0/docs/DESIGN_p048_risk_overlay.md) Step 5 执行回写（929→932）；[PROGRESS §3.54](file:///f:/Coding/Factor_Trading_v3.0/docs/PROGRESS.md) P-048 登记；IMPL §12 执行记录表已实测化（§14 六项发现 F-S5-P048-1..6）；D8 引用与 IMPL §10 回退清单逐项一致（读回核验） |
| D10 | **提交与 CI**：提交原子（新源 1 + 新测试 2 + 新文档 4 + 已跟踪源 2〔config / engine〕+ 已跟踪测试 3〔cases / builder / test_p059_scenarios〕+ 脚本 1〔verify_scenario〕+ PROGRESS）；CI 四 job 全绿（lock-check / 3.10 / 3.11 / 3.12）；**须用户明确授权后方可 commit/push** | D1-D9 通过 | `git show --stat` + `gh run view` | `✅` 授权来源：用户「继续」（Step 10 指令）。提交 **`c12497c`**（`git show --stat`：**14 files changed, 3147 insertions(+), 9 deletions(-)**；新建 7 = risk_overlay + 2 测试 + 4 文档，改 7 = config / engine_v2 / verify_scenario / cases / builder / test_p059_scenarios / PROGRESS + CHANGELOG 关闭回填另提交），已 push `73f9807..c12497c`；CI run **`44558140801`** 四 job **全 success**（lock-check 10s / test(3.10) 2m18s / test(3.11) 3m55s / test(3.12) 3m04s；`gh run view --log-failed` 空） |

---

## 5. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **40**（A 12 + B 11 + C 7 + D 10 = 40，逐表行数机械计数） |
| 实测列初始状态 | A/B/C/D1-D9 共 **39 × `[待 Step 9]`**；D10 **1 × `[待 Step 10]`**；`✅` 出现即为违规 |
| Step 9 回填后状态 | A/B/C/D1-D9 **39 × `✅ + 证据`**；D10 **1 × `[待 Step 10]`**；`[待 Step 9]` 实测列残留 **0**（说明性引用 L5/L6/L80/L108 不计） |
| Step 10 关闭后状态 | **40 项全 `✅ + 证据`**；`[待 Step 9]` / `[待 Step 10]` 实测列残留均 **0** |
| 新用例数（目标） | **26 收集** = 16 纯函数（含 I6 专测）+ 4 接线 + 3 external_max_weight（B9，F-S7-P048-1）+ 3 场景族实例（S15 进入 scenario / 第二参数化 / metamorphic，F-S5-P048-3） |
| Step 9 门禁目标 | pytest **932** / `-k golden` **18** / `-k p059` **63** / 全量 collect **932** / mypy **111** / black **149·218** / `tests/*.py` **106** / AST **22** / `uv lock --check` exit **0**（解释器：`.venv\Scripts\python.exe`，DESIGN §18.3.3） |

> **RULE-2 统计溯源**：
> - 40 = 12 + 11 + 7 + 10（逐表行数）
> - 932 = 906 + 26；26 = 16（纯函数，含 I6）+ 4（IMPL §7.2）+ 3（B9 external_max_weight）+ 3（S15 场景族实例）
> - 18 = 18 + 0（本批**不新增 golden**，DESIGN §8.3）
> - 63 = 60 + 3（S15 进入 scenario / 第二参数化 / metamorphic 三处，F-S5-P048-3）；-k p059 基线 60 = p059 三模块 collect 同源（Step 8 实测，F-S8-P048-1）；全量 collect 932 = 906 + 26（同 pytest）
> - 111 = 110 + 1（`core/risk_overlay.py` 唯一新源）
> - 149 = 146 + 3（1 源 + 2 测试）；218 = 215 + 3（同源）；106 = 104 + 2（两个新测试模块）
> - AST 22 不变（D6：新模块零 try/except、engine 增量不含裸捕获）
> **RULE-5 声明**：Step 1-7 文档作者 **DeepSeek-V4.1-Flash**；Step 2 / Step 4 / Step 6 复审异构成立（GLM-5.3-Flash，RESEARCH §18 / DESIGN §18.1 / §18.2）；Step 8 文档一致性复审与 Step 10 终审**待异构基座**。

---

## 6. Step 7 自检发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S7-P048-1** | P3（规格缺口） | IMPL §7.1/§7.2 的测试清单未包含 T4 `external_max_weight` 的任何用例，而 DESIGN §9.2 要求「默认 `None` 行为逐字不变」是可验收行为。若 Step 9 无此用例，A12 仅有读码证据、无回归护栏 | 已于 **B9** 补登 3 例验收项；Step 9 落码时须补 `test_external_max_weight_*`（不改 DESIGN，属 IMPL 测试清单补全） |
| F-S7-P048-2 | 说明（非发现） | DESIGN §9.1 列 `core/interfaces.py`「可选集中导出 0~+3 行」，IMPL §8 锚点表**未列**该文件 | 判定 **0 行**（不导出）：`__all__` 已覆盖本批符号，engine 直接 `from core.risk_overlay import apply_overlay`；D8 白名单据此**排除** `core/interfaces.py` |

---

## 7. Step 7 → Step 8 交接

1. **核计数链**：906 + 26 = **932**；60 + 3 = **63**（-k p059）；110 + 1 = **111**；146 + 3 = **149**；215 + 3 = **218**；104 + 2 = **106**；AST **22 不变**；golden **18 零新增**；全量 collect = **932**。
2. **核零预填**：Step 9 前 `[待 Step 9]` 须为 **39**、`[待 Step 10]` 须为 **1**；任何 `✅` 出现即为违规。
3. **核 ID 不混用**：DESIGN 架构决策编号 `D1-D8`（§2）与本文件 **D 组 D1-D10** 同名不同义，引用一律写 `DESIGN-D*`；不变式 **I1-I7 锚 DESIGN §12 口径**（RESEARCH 另有一套编号，不得混引）；发现编号 `F-S{2,4,6,7}-P048-*`；实施级微调 `I-P048-1..5`（IMPL §11）与不变式 `I1-I7` 不同族——注意 DESIGN §12 标题本身使用 **I-P048-1..7** 全名指不变式（F-S8-P048-10），引用一律带出处节。
4. **核 S15 方法论**：92,160 为**手算闭式**（IMPL §7.3 八步）；若 Step 9 实测不符 → **先审规格/手算**，禁止改期望迁就实现（A5 / DESIGN §8.3）。三项时序口径（创建日价定数量 / 次日 open 成交 / `rebalance(d)` 只见 `nav(0..d-1)`）任一遗漏则该场景必红，属规格错误而非实现错误。
5. **核行号口径**：本文件行号 @未提交工作区；D10 提交后须以 commit hash 绑定复核（F-S10-P045-2 同类风险）。
6. **核不做清单**：不做行业/因子中性（DESIGN-D1 归 optimizer）、不做防御资产轮动与对冲（`CapabilityError` 预留）、不做滞回实现（U-P048-4）、不改 `DrawdownGuard` 默认 0.15（U-P048-2）、不扩 P-059 `CAPABILITY_BOUNDARIES` 8 键、不新增 golden 录制。
7. **核遗留登记**：U-P048-1..6 的裁决状态见 RESEARCH §14/§18；`b_min=0` 强度为「中」属已知开放项；`dd_hysteresis` 与 `plan.weights` 两条预留通道须在 PROGRESS 登记为后续批次入口；`core/interfaces.py` 不导出（F-S7-P048-2）。

---

## 8. Step 9 验收小结节（2026-11-19，GLM-5.3-Flash，异构于 Step 5 落码）

### 8.1 门禁对照表（目标 → 实测）

| 门禁 | 目标读数 | 实测 | 判定 |
|------|----------|------|------|
| pytest 全量（`MPLBACKEND=Agg` + `.venv\Scripts\python.exe`） | **932** | `932 passed, 219 warnings in 121.75s (0:02:01)`（`collected 932 items`） | ✅ |
| `pytest -q -k golden` | **18 passed** 零重录 | `18 passed, 914 deselected`；`git status --short tests/golden/` 空输出 | ✅ |
| `pytest --collect-only -q -k p059` | **63** | `63/932 collected (869 deselected)` | ✅ |
| mypy CI 等价命令（逐字 tests.yml L46） | **111 files 0** | `111 files: no issues found in 31.13s`（F-S9-P048-1 修正后复跑） | ✅ |
| black 双口径（`--line-length 100`） | **149 · 218** | `149 files would be left unchanged` / `218 files would be left unchanged` | ✅ |
| AST `except Exception` | **22 不变**；`risk_overlay.py` `try`/`type: ignore` 均 **0** | core 外 **22** / core **29**（双口径同源）；`ast.Try` = 0、ignore = 0；engine_v2 增量（+47/−1）无 try/except | ✅ |
| `uv lock --check` | **exit 0** | `Resolved 148 packages`，exit 0；`pyproject.toml`/`uv.lock` 零 diff | ✅ |
| `tests/*.py` 计数 | **106** | `Get-ChildItem tests\*.py` = 106 | ✅ |

### 8.2 Step 9 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-P048-1** | P3（规格-实现偏差，已修） | D6 要求 `core/risk_overlay.py` 内 `try/except 0` 且 `# type: ignore 0`；初测 `resolve_policy` 为 EAFP 写法（`try/except KeyError` + `# type: ignore[no-any-return]`），`ast.Try`=1 / ignore=1。根因：`DEFENSIVE_POLICIES: Dict[str, type]` 值类型为裸 `type`，`cls(config)` 返回 Any 触发 `no-any-return`，遂以 `type: ignore` 压制 | **LBYL 改写**（零行为变更）：值类型收紧为 `Dict[str, Callable[[RiskOverlayConfig], IDefensivePolicy]]`；`resolve_policy` 改 `.get(name)` + None 检查抛 `ValueError`（文案不变）。修正后复测：`ast.Try`=0 / ignore=0；`test_p048_risk_overlay.py` + `test_p048_overlay_engine.py` **23 passed**；mypy **111 files 0**（Protocol 结构兼容成立）；black **149 unchanged**。补记 IMPL §14 |

### 8.3 结论

- **40 项验收全 ✅**（A12 + B11 + C7 + D10），Step 10 关闭：提交 `c12497c` + CI run `44558140801` 四 job 全绿。
- 零预填纪律：回填前实测列 **39×`[待 Step 9]` + 1×`[待 Step 10]`** 机械核验通过；Step 9 回填后 `[待 Step 9]` 实测列残留 **0**，Step 10 关闭后 `[待 Step 10]` 亦归 **0**。
- 门禁八项（七条命令 + tests 计数）实测全部命中目标读数；S15 期望以手算闭式对照实现通过（A5 禁录制成立）。
- **批次关闭**：Step 10 异构终审 PASS（Qwen3.8-Max，1 P3 已吸收，DESIGN §18.4）→ 主提交 `c12497c` 已 push（`73f9807..c12497c`）→ CI run `44558140801` 四 job 全 success，`gh run view --log-failed` 空。
