# CHECKLIST：P-050 期货账目 / 逐日结算 / 强平 / 换月 + 股票负持仓研究模式

> **批次**: P-050 · **T1**（改 `tracker`/`execution`/`engine_v2`/`config`/`invariants`/`target_positions`/`execution_policy`/`risk_manager`/`engine_v3_vector`，波及 V2/V3/golden）
> **上游**: [RESEARCH_p050](RESEARCH_p050_futures_short_accounting.md)（§4.4 E2 / §7 I-P050 / §10.0 裁决 / §10.5 N-1..N-9 / §14.1 复审）· [DESIGN_p050](DESIGN_p050_futures_short_accounting.md)（§2 D1-D12 / §3 签名 / §4 时序 / §7 不变量 / §8 测试 / §12 RD-1..RD-5）· [IMPL_p050](IMPL_p050_futures_short_accounting.md)（§3-§10 T1-T9 / §12 排除表 / §15 RI-1..RI-9）
> **状态**: Step 7 产出（2026-11-20，DeepSeek-V4.1-Flash）；Step 8 一致性**通过**（SC-1..SC-6 已回写，见 §7）；**Step 9 验收完成**（53/53 实测已填，门禁全绿，见 §8 偏差登记）；Step 10 终审待执行
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**本文件提交时 100% 为待填，禁止预填**
> **基线读数（2026-11-20 实测，代码零 diff，`MPLBACKEND=Agg`）**: pytest **987 passed**（1:54）· `-k golden` **18 passed** · 全量 collect **987** · mypy CI 等价 **111 files 0 issue** · black `core tests` **152 unchanged**
> **环境注意（本批登记）**: 未设 `MPLBACKEND=Agg` 时全量出现 **1 failed**（`test_trace_completeness.py`，报 "tk wasn't installed"），单独复跑 pass → 属环境噪声，基线口径固定为 `MPLBACKEND=Agg`
> **目标读数**: pytest **1004**（987 + 17）· `-k golden` **22**（18 + 4，既有 18 零重录）· collect **1004** · mypy **112**（111 + 1 源）· black **155**（152 + 1 源 + 2 测试）· `tests/*.py` **+2**
> **Step 9 实测读数（2026-11-20，`MPLBACKEND=Agg`）**: pytest **1024 passed**（1:46）· `-k golden` **22 passed**（1002 deselected）· collect **1024** · mypy **112 files 0 issue** · black `155 unchanged` · `tests/*.py` **111（109+2）** · `tests/golden/` 仅 `?? p050/`

---

## 1. A 组：契约与账目（19 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `BacktestConfig` 新增 4 字段且**全部带默认值**：`allow_negative_stock_positions=False` / `settlement_file=None` / `futures_symbols=[]` / `liquidation_price_type=OPEN`；`allows_short(asset_type)` 为唯一入口（STOCK→开关，非 STOCK→True） | 无 | 读码 + `::test_config_defaults_preserved` | ✅ `test_config_defaults_preserved` + `test_f9_disabled_identical` |
| A2 | `AssetInfo` 新增 `roll_days_before_expiry: Optional[int]=None` / `roll_target: Optional[str]=None`；既有构造调用零破坏 | A1 | 读码 + 现有 config 测试 | ✅ 读码 `core/config.py`；全量 1024 passed（既有构造零破坏） |
| A3 | `Position` 新增 5 字段（`asset_type/multiplier/notional_value/mtm_pnl/settle_base`）全默认；既有 6 字段与构造位置不变 | A1 | 读码 + `::test_position_defaults` | ✅ `test_position_defaults` |
| A4 | `Trade` 新增 3 字段（`asset_type/multiplier/settlement_price`）全默认；既有 8 字段不变 | A1 | 读码 + `test_phase2*` | ✅ `test_trade_defaults` + `test_phase2*` |
| A5 | `core/futures_accounting.py` 落盘：5 个 `@dataclass(frozen=True)`（`ContractSpec`/`LiquidationRequest`/`RollInstruction`/`SettlementResult` + 类型齐全）；`MarginModel` 为 `@runtime_checkable Protocol`；**不 import** tracker/engine/pending | A1 | 读码 + import 白名单 | ✅ 实际 **4 个** frozen dataclass + `MarginModel` Protocol（计数笔误，§8 D-2）；仅 import `core.config`/pandas/numpy |
| A6 | `compute_settlement`：`pnl = q×(S_t − settle_base)×m`（q 有符号，空头自动负号）；缺结算价 → 跳过且 `proxy_used=False`；保证金按 `S_t` 重算 | A5 | `::test_settlement_long/short` | ✅ `test_f2_settle` / `test_f4_short` / `test_settlement_missing_price_skips` |
| A7 | `apply_settlement`：`cash += total_pnl − margin_delta`；返回 `(cash_after, margin_after)`；纯函数不改入参 | A6 | 读码 + F2 | ✅ `test_apply_settlement_pure` + `test_f2_settle` |
| A8 | `liquidation_requests`：`cash>=0 → []`；否则按 `abs(notional)` **降序**生成，且生成时即完成最小集合裁剪（非执行期中途停） | A5 | `::test_liquidation_order_and_trim` | ✅ `test_f5_liquidation`（降序 + 裁剪） |
| A9 | `roll_orders`：`expiry − roll_days ≤ date` 触发；`roll_target` 缺失 → `ValueError`；同合约不重复生成 | A5 | `::test_roll_due_and_missing_target` | ✅ `test_roll_due_and_missing_target` + `test_f7_roll` |
| A10 | `split_reversal`：同号单笔差额；异号返回**两笔** `[平仓侧, 开仓侧]`，返回**字符串侧别**（不依赖 `core.pending`） | A5 | `::test_split_reversal` | ✅ `test_f11_reversal`（6 组映射） |
| A11 | `PositionTracker.settle(...)` 签名含 `fallback_prices`（RI-1）；`specs` 空 → 立即 `None`（股票零开销）；**不产生快照** | A3/A6 | 读码 + `::test_settle_noop_for_stocks` | ✅ `test_settle_noop_for_stocks` / `test_settle_proxy_uses_fallback`（快照数不变） |
| A12 | 现金三方法：`get_available_cash`（=cash）/ `get_total_cash`（cash+Σmargin）/ `get_cash` 保留兼容；引擎 BUY 闸门改用 `_avail_cash()` 探测助手 | A11 | 读码 + F1/F9 | ✅ 读码 + `test_f1_open`（10,000 可用）/`test_f9_disabled_identical` |
| A13 | `execute_trade` 四侧分支：股票路径逐位不变；FUTURE 开仓扣保证金、平仓 `cash += released + q×(px−settle_base)×m − cost`；**四向越量 raise**（SELL 用 `max(qty,0)` 判界） | A3/A4 | `::test_trade_four_sides` + F10 | ✅ `test_f10_overfill` + `test_f1_open`/`test_f3_close` |
| A14 | 引擎 setup 构建 `_contract_specs`：`futures_symbols` 显式枚举；缺 `multiplier/margin_ratio/expiry_date` → raise；`last_holdable` 与 expiry 同年月 → raise（不进入交割月） | A1/A2 | `::test_setup_specs_validation` | ✅ `test_setup_specs_validation`（4 参数：multiplier=0 / ratio=None / expiry=None / 06-30 交割月） |
| A15 | 引擎日序：settle 插在 **pending queue 之后、trigger 之前**；强平请求 `[:0]` 整体前插保持降序；`_kind=="liquidation"` 豁免过期、失败转顺延（RD-1/RI-3） | A11/A14 | 读码 + F6 | ✅ `test_f6_liquidation_exec` / `test_f6_liquidation_deferred` |
| A16 | `compute_portfolio_value` 增 `equity_symbols` / `allow_negative_stock` 可选参数（RI-7 签名勘误 + SC-6 口径勘误：**期货走 `market_values` 权益**=margin+mtm，非名义乘数重算）；缺省时股票逐位不变 | A1 | 读码 + F9 | ✅ `test_f9_disabled_identical` + S1-S4 NAV 闭式 |
| A17 | 期货权重与行业敞口用 `notional_value`；`validate_positions` 期货分支校验 `market_value == margin_used + mtm_pnl`，股票原门不动（RD-5/RI-8） | A3 | 读码 + `::test_validate_futures` | ✅ `test_validate_futures` / `test_i7_notional` |
| A18 | 成本接线：`asset_specs` 注入 `ExecutionSimulator`，乘数落 `amount`；`asset_type=FUTURE` 印花税恒 0、`exchange_fee` 生效；`None` 时逐位不变（RI-6） | A4 | `::test_cost_futures` | ✅ `test_f13_cost` + S1 `trade.amount=900,000`（乘数已落 amount） |
| A19 | `risk_manager` 分母改 `notional_value`，动作降为**仅诊断**（不产生 `FORCE_CLOSE` 动作）；默认不注入，生产行为不变（DESIGN D10 / N-1；**S7 补登：IMPL 文件清单漏列，已回写 T7**） | A3 | 读码 + `::test_risk_manager_diagnostic_only` | ✅ `test_risk_manager_diagnostic_only`（仅 logger） |

## 2. B 组：测试交付（15 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | `tests/test_p050_futures_accounting.py` 落盘，覆盖 F1-F5/F8-F11/F13，函数清单无空缺 | A5-A13 | `--collect-only -q` | ✅ 25 项收集（含 F1-F5/F8-F13 + I6/I7/I8） |
| B2 | **F1 开仓闭式**：IH `m=300, r=0.1, P0=3500` → margin=105,000、cash=895,000、notional=1,050,000（禁录制） | A13 | `::test_f1_open` | ✅ `test_f1_open` |
| B3 | **F2 结算闭式**：S=3480 → pnl=−6,000、margin=104,400、Δ=−600、cash=889,600、NAV=994,000 | A6/A7 | `::test_f2_settle` | ✅ `test_f2_settle` |
| B4 | **F3 平仓**：保证金全额释放、累计盈亏=两日 pnl 之和、`margin_used=0` | A13 | `::test_f3_close` | ✅ `test_f3_close`（平仓日 realized 仅记结算后价差 +3,000，累计由 NAV 体现；§8 D-3） |
| B5 | **F4 空头**：`q<0` 时 pnl/保证金/notional 符号正确 | A6 | `::test_f4_short` | ✅ `test_f4_short` |
| B6 | **F5 强平生成**：`cash<0` → 非空且降序；`cash>=0` → `[]` | A8 | `::test_f5_liquidation` | ✅ `test_f5_liquidation` |
| B7 | **F6 强平执行**：次日开盘平仓 → 持仓 0 且 `cash>=0`；无法成交 → `deferred_days+1` 且不丢弃 | A15 | `::test_f6_liquidation_exec` | ✅ `test_f6_liquidation_exec` + `test_f6_liquidation_deferred` |
| B8 | **F7 换月**（== 研究 I-P050-6 换月守恒）：新旧 notional 相等；`roll_target` 缺失 raise；到期前不触发 | A9 | `::test_f7_roll` | ✅ `test_f7_roll`（新旧 notional 均 900,000） |
| B9 | **F8 股票空头**：`NAV = C + q(P0−P)`（q=开空股数，正）；`exposure>0` | A13 | `::test_f8_stock_short` | ✅ `test_f8_stock_short` |
| B10 | **F9 开关关闭逐位一致**：3 个股票场景与改动前读数完全相同 | A1/A16 | `::test_f9_disabled_identical` | ✅ `test_f9_disabled_identical` |
| B11 | **F10 越量四向 raise**：SELL / BUY_TO_COVER / SELL_SHORT / BUY 各 1 例，文案含持仓与成交量 | A13 | `::test_f10_overfill` | ✅ `test_f10_overfill`（四向） |
| B12 | **F11 反手两笔**：顺序、数量、分笔费用、中间 cash 断言 | A10/A13 | `::test_f11_reversal` | ✅ `test_f11_reversal` |
| B13 | **F12 V3 拒绝**（== 研究 I-P050-8）：`futures_symbols` 非空或开关开 → `ValueError` | A1 | `::test_f12_v3_reject` | ✅ `test_f12_v3_reject` |
| B14 | **F13 成本接线**：FUTURE 印花税 0、`exchange_fee` 生效；STOCK 三费与改动前一致 | A18 | `::test_f13_cost` | ✅ `test_f13_cost` |
| B15 | **golden 4 例**（`tests/golden/p050/`）：S1 多头三日 / S2 空头三日 / S3 强平 / S4 roll；期望值闭式手算入档；断言面沿用 `_nav_block`+`_metrics_block_v2`+`trades.count` | A14-A16 | `pytest -k golden` + 手算表 | ✅ S1-S4 全绿：`[1e6,1e6,1.015e6,1.003e6]` / `[1e6,1e6,0.985e6,0.997e6]` / `[1e6,0.88e6,0.88e6,0.88e6]` / `[1e6,1e6,1e6,1.003e6]`；trades 1/1/2/3 |

## 3. C 组：不变式（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1 不变**（== 研究 I-P050-1 NAV 恒等）：`total_value == cash + Σ market_value`（期货 `market_value=margin+mtm`），公式本体零改动 | A11 | 读码 + 全量 | ✅ `check_all` 公式零改动；1024 passed 无 NAV 恒等报错 |
| C2 | **I6 保证金恒等**（== 研究 I-P050-3）：`margin_used == Σ abs(qty)×settle×m×ratio`（1e-6）；仅 `specs` 非空执行 | A11 | `::test_i6_margin` | ✅ `test_i6_margin`（代码串 **P050-I6**，§8 D-1） |
| C3 | **I7 名义恒等**（== 研究 I-P050-10 模块级固化）：`notional_value == abs(qty)×price×m`，未盯市时也非 0 | A3 | `::test_i7_notional` | ✅ `test_i7_notional`（代码串 **P050-I7**；需显式传 `prices`，§8 D-1） |
| C4 | **I8 现金恒等**（== 研究 I-P050-2）：`cash_t − cash_{t−1} == Σpnl − fee − Δmargin`（单测级） | A7/A13 | `::test_i8_cash_identity` | ✅ `test_i8_cash_identity` |
| C5 | **I-P050-9**：四向越量 raise（与 B11 同源，独立断言消息不含价格） | A13 | `::test_f10_overfill` | ✅ `test_f10_overfill`（消息仅含持仓与成交量） |
| C6 | **I-P050-10**：`exposure == notional_value`，股票未盯市（买入后未 update）也非 0 | A3 | `::test_f1_open` | ✅ `test_f1_open` |
| C7 | **期货 NAV 闭式**：任意三日路径 `NAV_t = 初始 + Σpnl`，误差 ≤1e-6 | A6 | S1 + `::test_f2_settle` | ✅ S1 `[1e6,1e6,1_015_000,1_003_000]`；`test_f2_settle` 994,000 |
| C8 | **空头 NAV 闭式**（== 研究 I-P050-4 多空对称）：`NAV = C + q(P0−P)`，与 `cash + mv` 双路径一致 | A13 | S2 + F8 | ✅ S2 `[1e6,1e6,985_000,997_000]`；`test_f8_stock_short` |
| C9 | **强平终态**（== 研究 I-P050-5 强平单调）：强平后 `cash>=0` 或全部持仓为 0；不存在"请求丢失" | A15 | S3 | ✅ S3 强平后 cash=880,000、持仓 0；顺延用例不丢单 |
| C10 | **零重录**（== 研究 I-P050-7 逐位一致）：既有 12 个 golden 字节不变，`pytest -k golden` 22 passed | A14-A16 | `git status --short tests/golden/` | ✅ 仅 `?? tests/golden/p050/`；22 passed |

## 4. D 组：门禁、改动面与文档（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest **1004 passed**（`MPLBACKEND=Agg`，venv 解释器） | 全量实现 | 全量末行 | ✅ **1024 passed**（106s）；较目标 +20 例（新增 37 例，非 17；§8 D-4） |
| D2 | `-k golden` **22 passed**；`git status --short tests/golden/` 仅显示新增 `p050/`，既有 12 文件无 M | C10 | 命令 | ✅ 22 passed / 1002 deselected；仅 `?? tests/golden/p050/` |
| D3 | 全量 collect **1004**（987 + 17） | B1-B15 | `--collect-only -q` | ✅ **1024 collected**（987 + 37；§8 D-4） |
| D4 | mypy CI 等价 **112 files 0 issue**（+1 源） | 全量实现 | 逐字命令 | ✅ `Success: no issues found in 112 source files` |
| D5 | black `core tests` **155 unchanged**（152+3），0 reformatted | 新文件 | `black --check` | ✅ `155 files left unchanged`（先对本批 7 文件 `black`，随后 0 reformatted） |
| D6 | `tests/*.py` **+2**（两个新测试模块） | B1 | `Get-ChildItem tests\*.py` | ✅ 111 = 109 + 2 |
| D7 | **改动面白名单**：新建 **3 源/测 + 1 目录（4 json）+ 4 文档**；改 **10 源**（config/**interfaces（SC-2 补登）**/tracker/execution/engine_v2/invariants/target_positions/execution_policy/risk_manager/engine_v3_vector）+ `core/__init__.py`；**零 diff**：`core/data.py`/`core/pending.py`/`core/sizing.py`/`core/guard_pipeline.py`/`core/risk_overlay.py`/`tests/_golden_cases.py`/既有 12 golden | 全量实现 | `git status --short` + `git diff --stat` | ✅ 新建 `core/futures_accounting.py` + 2 测试 + `tests/golden/p050/`；改 11 源（含 interfaces/`__init__`）；零 diff 清单全部为空 |
| D8 | **文档回写**：IMPL §13 执行记录逐任务填实测；DESIGN 若有偏差回写；`docs/PROGRESS.md` 登记 P-050（按既有台账格式） | D1-D7 | 读回 diff | ✅ IMPL §13 执行记录 + 本清单实测列 + PROGRESS 登记（§8 汇总偏差） |
| D9 | **CHANGELOG** 按 `[Unreleased]` 规范补 P-050 条目 | D8 | 读码 | ✅ `CHANGELOG.md` `[Unreleased]` 已补 |
| D10 | **提交与 CI**：原子提交（3 新源/测 + 4 json + 4 文档 + 10 改）；四 job 全绿；**须用户明确授权后方可 commit/push** | D1-D9 | `git show --stat` + `gh run view` | [待 Step 10] |

---

## 5. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **54**（A 19 + B 15 + C 10 + D 10 = 54，逐表行数机械计数） |
| 实测列初始状态 | A/B/C/D1-D9 共 **53 × `[待 Step 9]`**；D10 **1 × `[待 Step 10]`**；`✅` 出现即违规 |
| 新用例数（目标） | **17** = 单测 10（F1-F5/F8-F11/F13）+ 集成 3（F6/F7/F12）+ golden 4 |
| 目标 pytest | **1004** = 987 + 17 |
| 目标 golden | **22** = 18 + 4（既有零重录） |

> **RULE-2 统计溯源**：
> - 54 = 19 + 15 + 10 + 10（逐表行数）
> - 1004 = 987 + 17；17 = 10（`test_p050_futures_accounting.py`：F1/F2/F3/F4/F5/F8/F9/F10/F11/F13）+ 3（`test_p050_engine_integration.py`：F6/F7/F12）+ 4（`p050/` golden 参数化）
> - 22 = 18 + 4；18 为 2026-11-20 实测（非继承值）
> - 112 = 111 + 1（`core/futures_accounting.py`，mypy CI 等价口径）
> - 155 = 152 + 3（1 源 + 2 测试）
> - 基线口径：`MPLBACKEND=Agg`；无该变量时 1 failed（tk 缺失，环境噪声，已单独复跑为 pass）

## 6. 已知遗留（不阻塞本批验收）

| 项 | 说明 | 去向 |
|----|------|------|
| `test_trace_completeness.py` 无 `MPLBACKEND` 时偶发 1 failed | 报 "tk wasn't installed"，单跑 pass；疑与本机 matplotlib 后端有关 | 环境问题，不在本批范围 |
| `T0FuturesPolicy` 仍零生产调用点 | 本批仅接 `allow_short` 开关路径，未启用该 Policy | 后续批次（P-056/P-058） |
| 平今/平昨费用、按手最低佣金 | 研究 §5.6 未裁决 | P-056 |
| 盘中强平（C3） | 无分钟级数据契约 | 后续 |
| 品种级保证金整倍数/额度 | 不入本批 | P-056 |

---

## 7. Step 8 一致性检查记录（复审方 GLM-5.3-Flash，2026-11-20）

**方式**：四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）交叉核对编号、映射、计数链、签名与改动面；补测未验证锚点（`tracker.py` L343/L347 行业敞口、`engine_v2.py` L1176-1186 实参、`interfaces.py` L324/L538、RESEARCH §7 L313-322 逐字）。

**结论**：**通过（6 项不一致全部回写）**。54 项验收与计数链（1004=987+17、22=18+4、112=111+1、155=152+3）复核一致；D1-D12 / RD-1..RD-5 / RI-1..RI-9 三文档引用闭合；研究 I-P050 全系列 10 项经映射修正后均有承载出口。

| ID | 级别 | 不一致 | 处置 |
|----|------|--------|------|
| SC-1 | minor | IMPL §1.2 不变量行仍写 "I5/I6/I7"（§9.1 已改 I6/I7，表未同步） | 已改 I6/I7 |
| SC-2 | minor | DESIGN D11 要求 `AbstractPositionTracker` 非抽象 no-op，但 `core/interfaces.py` 不在 IMPL §1.2 与本清单 D7 白名单 | 两处补登，改动面 9→10 源 |
| SC-3 | **major** | 不变量映射错位：IMPL/DESIGN 写 "I6/I7/I8 == 研究 I-P050-5/6/7"，实际研究 §7 为 5 强平单调 / 6 换月守恒 / 7 零重录；正确映射 **I6==I-P050-3、I7==I-P050-10、I8==I-P050-2** | IMPL §9.1、DESIGN §7、本清单 C1-C4/C8-C10/B8/B13 全部改正 |
| SC-4 | minor | IMPL §6.4 函数清单缺 F9/F13 行（仅在 §4.2/§5.2 验收文本），B1 "无空缺项"不可追溯 | 补两行并标注归属任务 |
| SC-5 | minor | §8.6 行业敞口只改 L347 取值，未提 L343 `quantity>0` 门（空头行业敞口漏计） | 补"门同步接 allow_short" |
| SC-6 | **major** | **方案性勘误**：IMPL §8.5 "期货按 `qty×price×multiplier` 重算"在 A3′ 可用现金口径下错误——漏掉保证金占用（NAV 差 `margin_t`），与 `get_total_value` 不一致；engine L1181-1186 实测传 `tracker.get_cash()`（可用）+ market_values dict 互证 | 改为期货走 `market_values`（margin+mtm，settle 每日刷新、日序先于调仓），股票保持重算；参数 `multipliers` 改 `equity_symbols`；DESIGN §3.4 同步；本清单 A16 改写 |

**复核通过项**：RESEARCH §7 I-P050-1..10 原文逐字核对；`compute_portfolio_value` 真实签名与 engine 实参；`interfaces.py` 两处类存在性；tracker L343/L347；CHECKLIST §5 计数链；F1-F13 / T0-T9 / D1-D12 / RD / RI 引用闭合。

**复审意见**：SC-6 是 Step 6 复审 RD-4 的"修对了签名、修错了口径"——RI-7 只验了参数形态，未按 A3′ 现金语义重推估值恒等式；本次以 engine 实参为证据闭环。映射修正后研究 I-P050-1..10 与 CHECKLIST 出口一一对应（1→C1、2→C4、3→C2、4→C8、5→C9、6→B8、7→C10、8→B13、9→C5、10→C3/C6）。无未决分歧，**可进入 Step 9（TDD 实现）**。

---

## 8. Step 9 实现记录与偏差登记（2026-11-20）

**门禁**：pytest 1024 passed · `-k golden` 22 passed · collect 1024 · mypy 112 files 0 issue · black 155 unchanged · `tests/*.py` 111（109+2）· `tests/golden/` 仅 `?? p050/`。

| ID | 级别 | 偏差 | 处置 |
|----|------|------|------|
| D-1 | minor（代码串） | 不变量代码串：模块内 `I6`/`I7` 已被 `check_v3_static_positions` / `check_v3_cost_identity` 占用，P-050 两项改用 **`P050-I6` / `P050-I7`**（研究 RI-9 原判断有误） | 函数名与测试名不变（`check_margin_identity` / `check_notional_identity`、`test_i6_margin` / `test_i7_notional`），仅 `code=` 串改；C2/C3 实测列已注明 |
| D-2 | minor（文档笔误） | A5 写 "5 个 frozen dataclass"，实际 **4 个**（`ContractSpec/LiquidationRequest/RollInstruction/SettlementResult`）+ `MarginModel` Protocol | 本清单 A5 实测列标注；不影响接口 |
| D-3 | minor（语义） | F3 平仓日 `realized_pnl` 只记"结算后价差"（`+3,000`），建仓至结算日的累计盈亏已通过 NAV/cash 体现，不重复计入 realized | `test_f3_close` 断言按此修正；B4 已注明 |
| D-4 | minor（计数） | 新用例 **37**（单测 25 + 集成 12）而非目标 17 → pytest/collect = **987 + 37 = 1024**（目标 1004） | 拆分为更小断言面：F6 拆执行/顺延、A14 参数化 4 例、F11 6 组映射等；D1/D3 实测列已登记 |
| D-5 | minor（接口实现） | `ContractSpec` 追加 `asset_type: AssetType = AssetType.FUTURE`（`ExecutionSimulator` 通过 `getattr(spec,"asset_type")` 判定期货，否则印花税/乘数路径误走股票） | 新增字段带默认值，零破坏；mypy 由 `Mapping[str, Any]` 承接 |
| D-6 | minor（语义修正） | 引擎权重侧按 D7 细化：**期货天然双向**（`allow_short = allows_short(STOCK) or 有期货`），股票负权重仍按开关截断为 0；否则期货空头需误开股票负持仓开关 | S2/S3 以"股票开关关闭"验证 D7；`_generate_targets` / weights 模式同步 |
| D-7 | minor（健壮性） | 平仓单（`BUY_TO_COVER`）遇"已无持仓"由 raise 改为**自然作废**（强平与调仓同日重复平仓时防越量守卫误伤）；`BUY_TO_COVER` 改走 `buyable_mask`（原误用 `sellable_mask`） | `_execute_next_day_orders` / `_process_pending_orders` 两处；股票 `SELL` 行为不变 |

**既有测试语义更新（3 文件，非本批新增）**：`test_p1_multi_asset_refine.py::test_buy_does_not_cover_short` → `::test_buy_on_short_raises_overfill`（越量改为 raise）；`test_phase2_multi_asset.py` 空头 `market_value` 断言 → 有符号 `-6800.0`；`test_phase3_risk_monitor.py` 3 例保证金动作 → 仅诊断（`assertLogs` + 无动作）。
