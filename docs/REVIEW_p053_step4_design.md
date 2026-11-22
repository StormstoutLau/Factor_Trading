# REVIEW：P-053 Step 4 — DESIGN 异构复审回执

> **批次**: P-053 · **Step 4 设计复审** · 日期 2026-11-21
> **复审对象**: [DESIGN_p053_trading_gateway.md](DESIGN_p053_trading_gateway.md)（Step 3 产物，580 行，14 节）
> **复审基座**: GLM-5.3-Flash（≠ Step 3 作者 DeepSeek-V4.1-Flash，异构成立）
> **方法**: ①集成点契约重放（逐行号）→ ②全文一致性审查（契约自洽 / 与 P-052 对齐 / 门禁算术）→ ③分级发现（P1 阻断 / P2 需修 / P3 建议）→ ④全部修复回写 DESIGN
> **结果**: **3 P1 + 5 P2 + 6 P3 = 14 项，14/14 修复回写**；复审后 **PASS**，可进 Step 5 IMPL

---

## 1. 结论速览

| 级别 | 数量 | 编号 | 状态 |
|---|---|---|---|
| P1（契约缺陷，Step 5 无法落码） | 3 | F-D1 / F-D2 / F-D3 | ✅ 全修 |
| P2（语义缺口 / 不变式错误） | 5 | F-D4 / F-D5 / F-D6 / F-D7 / F-D14 | ✅ 全修 |
| P3（精度 / 完整性） | 6 | F-D8 / F-D9 / F-D10 / F-D11 / F-D12 / F-D13 | ✅ 全修 |

**判定**：Step 3 的裁决结构（§0）、模块拓扑（§2）、与 P-052 的衔接面（`pre_trade_check`/`on_order_result`/`cancel_all`/8 审计常量）**零契约冲突**；缺陷集中在**契约完整性**（四个回报 dataclass 未定义、submit 入参缺 intent）与**账本语义边界**（预留结算 / 空头层级 / I4 公式）。全部修复为文档级回写，零代码变更。

## 2. 集成点与代码锚点重放（全部命中）

| # | 锚点 | 位置 | 重放结果 |
|---|---|---|---|
| 1 | `SafetyGate.pre_trade_check(intent, ctx, *, account_id, strategy_id, ts, time_source="local")` | [safety_gate.py L111-120](file:///f:/Coding/Factor_Trading_v3.0/live/safety_gate.py#L111-L120) | ✅ 第一位置参数 = `intent: OrderIntent` → **F-D2 依据** |
| 2 | `SafetyDecision(allowed/action/reasons/decision_id/kill_level/circuit_state)` | safety_gate.py L58-66 | ✅ §3.8 `SubmitResult.decision` 类型一致 |
| 3 | `on_order_result(*, rejected: bool, ts: float)` | safety_gate.py L259 | ✅ §3.8 步⑦/poll 调用签名一致 |
| 4 | `cancel_all(bridge: LiveTradingBridge, *, ts: float) -> int` | safety_gate.py L284 | ✅ D-G7 语义；`getattr(adapter,"bridge",None)` 路径成立 |
| 5 | `RateLedger` / `record` / `check_rate` / `day_key` | safety_gate.py L18-27（import 自 core.compliance） | ✅ **F-D11 依据**：P-052 已有桶原语，D11「本地令牌桶」未指定实现 |
| 6 | `RateLimitConfig(max_per_second=1, max_per_day=1000)` | [compliance.py L77-83](file:///f:/Coding/Factor_Trading_v3.0/core/compliance.py#L77-L83) | ✅ §5 表指向正确 |
| 7 | 8 个 `EventType.AUDIT_*` | [event_log.py L60-67](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L60-L67)（AUDIT_EVENT_TYPES L70-79） | ✅ I12 白名单成立 |
| 8 | `OrderIntent` 字段 asset/asset_type/target_quantity/current_quantity/urgency | [execution_policy.py L56-75](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L56-L75) | ✅ §0.3「不新增字段」成立 |
| 9 | `OrderIntent.action` property（BUY/SELL/SELL_SHORT/BUY_TO_COVER/HOLD） | execution_policy.py L87-96 | ✅ request.side ↔ intent.action 一致性校验可行（F-D2） |
| 10 | `LiveTradingBridge` ABC 四方法 / `MockLiveBridge` | [live_bridge.py L69-85](file:///f:/Coding/Factor_Trading_v3.0/core/live_bridge.py#L69-L85) / L144 | ✅ mock 适配器挂 bridge 可行 |
| 11 | sqlalchemy/pymysql/psycopg2/redis/celery 声明未用（全仓 .py 零引用） | pyproject.toml L42-46 | ✅ U-P053-8 零新依赖口径成立 |
| 12 | `live/*.py` 现存 = 3 | glob | ✅ 3 → 16 计数成立 |
| 13 | `services/` 不存在 | glob | ✅ I7 禁 import 项真实 |
| 14-17 | 外部锚点抽检：SimNow 第二套环境 / 迅投 48-55 委托状态 / FIX ExecutionReport 单笔直达 Filled / Alpaca client_order_id 拒重复 | RESEARCH §12/§3.2 | ✅ 与 D3/D4/D8 口径一致（F-D3 依据：柜台**可不经过已报直达终态/部成**） |

## 3. 发现与修复明细

### P1（阻断：Step 5 无法按当前契约落码）

**F-D1 · §3.1 四个回报 dataclass 被引用但从未定义**
- 证据：`ChannelAdapter` ABC 签名引用 `SubmitAck`/`OrderReport`/`FillReport`/`PositionReport`（§3.1 L154-159），全文仅此两处出现，无字段定义。
- 影响：适配器 5 文件与 poll/reconcile 全部依赖这四个类型；不定义则 Step 5 首日即卡死。
- **修复**：§3.1 补齐四 dataclass——`SubmitAck{client_order_id, broker_order_id, state, ts}`；`OrderReport{client_order_id, broker_order_id, state, filled_quantity, avg_price, ts, code="", reason=""}`；`FillReport{fill_key, client_order_id, asset, side, quantity, price, fee, ts}`；`PositionReport{asset, quantity, available=None}`；`OrderState` 经 `TYPE_CHECKING` 引用（不产生运行期反向依赖，§2 依赖边不变）。
- 回执：✅ 已回写 §3.1。

**F-D2 · `TradingGateway.submit()` 签名缺 `intent`**
- 证据：§3.8 submit 签名为 `(self, request, ctx, *, account_id, strategy_id, ts)`；但固定序第④步调 `gate.pre_trade_check(intent, ctx, ...)`——**intent 无来源**（safety_gate.py L111 第一位置参数即 intent）。
- 影响：Step 5 无法编译通过；亦缺 request↔intent 一致性校验。
- **修复**：签名改 `submit(intent, request, ctx, *, account_id, strategy_id, ts)`；补一致性校验（asset/asset_type/side==intent.action/quantity==abs_trade_quantity/account_id/strategy_id 与 kwargs 一致，不符 `ValueError` fail-closed，adapter 零调用）；§3.2 `from_intent(intent, *, request, ts)` 冗余 → 改 `from_request(request, *, ts)`。
- 回执：✅ 已回写 §3.2/§3.8。

**F-D3 · 迁移表禁 `A→1/A→2` 与真实柜台「秒成交」冲突**
- 证据：§3.2 迁移表 PENDING_NEW 行 `PARTIALLY_FILLED=⛔、FILLED=⛔`；但 FIX 单笔 ExecutionReport 可直达 `OrdStatus=Filled`（无已报帧）、CTP「全部成交」直返终态、迅投 48-55 部成可不出现已报态；§3.9 mock 的「可编排乱序回报」同样会注入此类帧。
- 影响：真实/模拟回报在 Step 5 首测即被 `OrderTransitionError` 拒收，与 D4「与柜台语义同源」自相矛盾。
- **修复**：A→1/A→2 改 ✅；表下加注（秒级成交路径 + I9 不受影响：UNKNOWN 收敛仍只走查询/人工）。
- 回执：✅ 已回写 §3.2 迁移表。

### P2（语义缺口 / 不变式错误）

**F-D4 · 预留金结算缺口（leftover 永久冻结 + reserve 超现金行为未定义）**
- 证据：D5 买入行 `cash -= q*p + f；reserved -= 冻结额（不足则 0，差额记 cash_adjust）`——预留按 `price*qty*(1+buffer)` 计，成交价差/费用低于预留时**差额无退还规则**（永久冻结在 reserved）；`reserve()` 超现金无行为定义。
- **修复**：§3.3 增 `settle_reserve(*, ref, actual, ts) -> float`（消耗预留、cash 按 actual 扣减、差额退还并返回）；cancel/reject → `release()` 全额退还；`reserve()` 现金不足 → 新增 `LedgerError`（fail-closed）；D5 买入行改写。
- 回执：✅ 已回写 §3.3。

**F-D5 · 账本仅现金多头，但 capability/侧别允许 margin/short**
- 证据：`ChannelCapability.account_level ∈ {cash, margin, short}`（§3.1）、`OrderRequest.side` 含 `SELL_SHORT`/`BUY_TO_COVER`（§3.2）；而账本（§3.3）只有多头加权成本与 realized_pnl，无保证金/空单语义。
- 影响：半支持空单 = 静默错误记账（无保证金占用、无强平）。
- **修复**：新增 **D15**——本批账本仅 cash 层级；`start()` 校验 `account_level=="cash"` 否则 `CapabilityError`；submit 第③步对 cash 层级拒 `SELL_SHORT`/`BUY_TO_COVER`；§1 非目标增 margin/short（P-056）。
- 回执：✅ 已回写 §1/§3.8/§4。

**F-D6 · I4 现金守恒公式双计/漏计 fee**
- 证据：§3.3 不变式为 `initial_cash − Σ买入amount + Σ卖出amount − Σfee + Σ公司行为现金`；而 D5 规则买入流出 = `q*p+f`、卖出流入 = `q*p−f`——fee 方向在买/卖两侧相反，单一 `−Σfee` 项必错（卖出 fee 双扣或买入 fee 漏计，取决于 amount 含费口径）。
- **修复**：定义 `LedgerEntry.amount = 不含费成交额（fill: q*p；fee 单列）`；公式改 `cash + reserved == initial − Σ(buy.amount + buy.fee) + Σ(sell.amount − sell.fee) + Σca_cash`；§3.3 不变式行与 §6 I4 同步改写。
- 回执：✅ 已回写 §3.3/§6。

**F-D7 · outbox 消费端未定义 + PRE_OPEN 预埋自相矛盾**
- 证据：§3.4 Protocol 定义 `pending_outbox/mark_sent`，但 §3.8 仅步⑧写入、全文无读取方；§3.6 又称 PRE_OPEN 预埋「进 outbox，开盘后由 poll() 送达」——poll() 契约（§3.8）不含送达逻辑。
- **修复**：§3.4 明确 outbox 本批**只写不读**（供 P-054 服务层消费），Step 5 不实现投递循环；PRE_OPEN 预埋随 P-054 一并交付（并入 F-D10）；新增 **D16** 决策行。
- 回执：✅ 已回写 §3.4/§3.6/§4。

**F-D14 · I5「submit() 100% 经过 pre_trade_check」与八步固定序矛盾**
- 证据：第①步 `channel_halted`、第②步 `session_closed` 均在 gate 之前返回（§3.8），与「100%」冲突。
- **修复**：I5 改「除 `channel_halted`/`session_closed` 两个前置快败外**必经** `pre_trade_check`（含被拒路径）」；§1 目标第 7 条同步措辞。
- 回执：✅ 已回写 §1/§6。

### P3（精度 / 完整性）

**F-D8 · `should_degrade` 缺日期维度** — `Iterable[ParityReport]` 无法判「连续 2 日降级」。**修复**：签名改 `Sequence[tuple[str, ParityReport]]`（day 升序，取尾部连续 breach 天数 ≥ `degrade_days`）。✅ §3.5。

**F-D9 · `can_submit` 的 CLOSE_AUCTION 规则引用 capability，但契约无对应字段** — `ChannelCapability` 15 字段无一含竞价段。**修复**：改**固定规则** `can_submit(phase, *, order_type="limit")`（CONTINUOUS 允许；CLOSE_AUCTION 禁市价、允许限价）；`DaySession.close_auction` 默认改 `(14:57, 15:00)`（沪深收盘竞价）。✅ §3.6。

**F-D10 · `allow_pre_open` 未列入 Gateway `__init__`** — §3.6 称配置项但 §3.8 无此参数。**修复**：并入 F-D7——本批删除 PRE_OPEN 预埋（`can_submit(PRE_OPEN) == False`），不引入该参数。✅ §3.6/§3.8。

**F-D11 · 流控桶实现未指定** — D11「本地令牌桶」无落点。**修复**：明确复用 P-052 `RateLedger`（`record/check_rate/day_key`，safety_gate.py L18-27 已 import），submit/cancel/query 三桶各一。✅ §3.8/§4 D11。

**F-D12 · 首接已有持仓账户 → UNRESOLVED → HALTED（无 bootstrap）** — start() 对账「空本地账本 vs 非空柜台持仓」必判 unresolved。**修复**：§9 登记 **U-P053-14**：本批不做自动导入（SimNow 空仓不受影响）；预留 `seed_snapshot(remote)` 显式导入（人工触发 + `audit.reconcile`），落点随真实连通批次再定。✅ §9。

**F-D13 · poll()「audit.order 的 warn 字段」为杜撰结构** — audit payload 为字典，无 warn 字段定义。**修复**：改「非法迁移保留原状态，payload 记 `ignored_transition`」。✅ §3.8。

**附注（并入回执）**：`reconcile_fills` 判级补注——`missing_fill`（柜台有、本地缺）→ `MISSED`（可补录）；`extra_fill`（本地有、柜台无）→ `UNRESOLVED`（入账缺口，需人工）。✅ §3.5。

## 4. 门禁算术复核

| 项 | DESIGN §7 声明 | 复算 | 结果 |
|---|---|---|---|
| 测试用例 | 86 = 10+14+14+6+12+8+8+8+6 | 24/38/44/56/64/72/80/**86** | ✅ |
| 新文件 | 13 = 8 核心 + 5 adapters | §2 逐项清点 = 13 | ✅ |
| `live/*.py` | 3 → 16 | 3+13=16 | ✅ |
| mypy | 128 → 141 | 128+13=141 | ✅ |
| black | 261 → 283 | 261+22=283 | ✅ |
| `tests/*.py` | 132 → 141 | 132+9=141 | ✅ |
| pytest | 1214 → 1300 | 1214+86=1300 | ✅ |
| golden | 22 不变 | 不涉及 | ✅ |

## 5. 修复回执汇总与结论

| # | 级别 | 修复落点 | 回执 |
|---|---|---|---|
| F-D1 | P1 | §3.1（四 dataclass + TYPE_CHECKING 注记） | ✅ |
| F-D2 | P1 | §3.2 from_request / §3.8 submit 签名+校验 | ✅ |
| F-D3 | P1 | §3.2 迁移表 A 行 + 秒成交注记 | ✅ |
| F-D4 | P2 | §3.3（LedgerError / settle_reserve / D5 买入行） | ✅ |
| F-D5 | P2 | §1 非目标 / §3.8 start+步③ / §4 D15 | ✅ |
| F-D6 | P2 | §3.3 amount 口径+不变式 / §6 I4 | ✅ |
| F-D7 | P2 | §3.4 outbox 用途 / §3.6 / §4 D16 | ✅ |
| F-D14 | P2 | §1 目标 7 / §6 I5 | ✅ |
| F-D8 | P3 | §3.5 should_degrade 签名 | ✅ |
| F-D9 | P3 | §3.6 can_submit 固定规则 + close_auction 默认 | ✅ |
| F-D10 | P3 | §3.6 删预埋 / §3.8 步② | ✅ |
| F-D11 | P3 | §3.8 步③ RateLedger / §4 D11 | ✅ |
| F-D12 | P3 | §9 U-P053-14 | ✅ |
| F-D13 | P3 | §3.8 poll ignored_transition | ✅ |

**结论**：**PASS（修复后）**。DESIGN 契约自洽、与 P-052 集成面零改写、门禁算术成立、14 项发现全部回写。**可进 Step 5 IMPL**（按 R-1 分三组：语义层 → 存储+对账 → 适配器+端到端）。
