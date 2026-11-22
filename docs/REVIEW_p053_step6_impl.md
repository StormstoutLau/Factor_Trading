# REVIEW：P-053 Step 6 实施文档异构复审（IMPL）

> **批次**: P-053 · **Step 6 复审** · 日期 2026-11-21 · **判档 P2**
> **对象**: [IMPL_p053](IMPL_p053_trading_gateway.md)（13 文件逐处代码 / C-1..C-12 / 86 例映射）
> **异构性**: IMPL 作者 DeepSeek-V4.1-Flash ≠ 复审基座 GLM-5.3-Flash（对齐 P-051c / P-052 Step 6 先例）
> **方法**: ①IMPL §7 六项复审输入逐条作答（§4）；②P-052 契约与 RESEARCH 官方字典锚点重放（E3，§2）；③对 13 文件码面做可执行性审查——import 闭合、名字冲突、符号口径、状态机、能力门、流控、恢复序、循环依赖
> **结论**: **PASS（修复后）**——17 项发现 = **5 P1 + 8 P2 + 4 P3**，17/17 修复并回写（§5 回执）；DESIGN 四处同步回写；零代码变更（Step 9 按修订后 IMPL 落码）

---

## 1. 结论速览

| 级别 | 数量 | 编号 |
|---|---|---|
| P1（运行必崩 / 守恒破坏 / 循环依赖） | 5 | F-I1 record 名字冲突 · F-I2 OrderRequest 缺失 · F-I3 现金符号不自洽 · F-I4 循环 import · F-I5 transition 同态回报三缺陷 |
| P2（功能阻塞 / 契约违背） | 8 | F-I6 Terminal 被能力门阻塞 · F-I7 CTP 字典映射与错误码 · F-I8 查询流控未实现 · F-I9 成功回报不重置拒单计数 · F-I10 ledger↔store 未接线 · F-I11 gateway import 缺漏 · F-I12 Terminal 回填无入口 · F-I13 explained 过宽 |
| P3（口径 / 注记 / 整洁） | 4 | F-I14 asdict 与 import 尾注 · F-I15 死赋值与 ts 参数 · F-I16 UNKNOWN drain 口径 · F-I17 注记组 |
| 合计 | **17** | 17/17 修复（IMPL ≈20 处编辑 + DESIGN 4 处回写 + PROGRESS/RESEARCH 状态同步） |

P1 一句话摘要：

- **F-I1**：gateway `from core.compliance import record`（函数）与 submit()/cancel() 局部变量 `record`（OrderRecord）同名遮蔽 → `record(self._submit_ledger, ts, False)` 触发 `TypeError: 'OrderRecord' object is not callable`，**成功提交路径必崩**；局部一律改名 `rec`。
- **F-I2**：orders.py 首行 `from live.channel import OrderRequest`，但 `OrderRequest` 既不在 channel.py 运行期命名空间（仅 TYPE_CHECKING 引入），也没有任何文件定义 → **ImportError**；`OrderRequest` 数据类落 orders.py 本文件并删该行（与 C-1「channel 仅 TYPE_CHECKING 反向引用」自洽）。
- **F-I3**：`corporate_action`/`cash_adjust` 的 `entry.amount = +现金流入`，而 fill 的 `entry.amount = −现金流出`——同字段两义；C-2 公式 `−Σentry.amount + Σca_cash` 对 ca **双算**、对 `cash_adjust` **漏计**；`replay` 的 `cash -= e.amount` 对 ca/adjust 方向相反。统一口径「**任一 entry 的现金变动恒为 −amount，fee 恒为 −fee**」→ 守恒式 `cash + reserved == initial_cash − Σentry.amount − Σentry.fee` 全 kind 通用。
- **F-I4**：`ledger → corporate_actions → ledger` 与 `corporate_actions → reconcile → ledger` 双重循环 import；改 corporate_actions 运行期仅依赖 `reconcile.BreakLevel`（attribute_break 判级需要），`PositionLot`/`Break`/`LedgerSnapshot` 全部 TYPE_CHECKING，reconcile 删除未用的 `FillRecord` import → 运行期为无环 DAG。
- **F-I5**（复审新发现，IMPL §7 未列）：①mock/CTP 默认 ack `state=PENDING_NEW`，submit 步⑧ `transition(record, state=PENDING_NEW, broker_order_id=ack...)` 因同态短路要求 `broker_order_id is None` 落入 `A→A` 非法迁移 → **默认成功路径必崩**；②`LEGAL` 缺 `PARTIALLY_FILLED→PARTIALLY_FILLED` / `PENDING_CANCEL→PENDING_CANCEL` 自环 → 第二次部成回报 / CTP 52 复合态重报被判非法丢弃（filled_quantity 滞后）；③C-8「同态同步幂等返回原对象」与 ack 回填 broker_order_id 冲突。修复：同态短路允许 broker 回填 + LEGAL 增两条自环（fq 单调由既有校验③保证）。

---

## 2. 锚点重放（E3，全部命中）

| # | 锚点 | 重放结果 | 支撑 |
|---|---|---|---|
| R1 | [safety_gate.py](../live/safety_gate.py#L259-L280) `on_order_result(*, rejected, ts)` | `self._consecutive_rejects = self._consecutive_rejects + 1 if rejected else 0`（L264）→ **`rejected=False` 显式重置为 0**；每次调用写 `audit.circuit` | F-I9 |
| R2 | [safety_gate.py](../live/safety_gate.py#L111-L120) `pre_trade_check(intent, ctx, *, account_id, strategy_id, ts)` | 签名与 IMPL 步④一致；`intent.action` property 分流（L87-100） | ✓ 无发现 |
| R3 | [safety_gate.py](../live/safety_gate.py#L284-L298) `cancel_all(bridge, *, ts) -> int` | 调 `bridge.cancel_orders(None)` 并审计，返回计数 | F-I6（Terminal 无 bridge） |
| R4 | [compliance.py](../core/compliance.py#L87-L160) `RateLedger` / `check_rate` / `record` / `day_key` / `build_audit_payload(*, operator, time_source, **fields)` | `record` 才推进 `per_second`/`daily_*` 计数；**只 check 不 record 的账本恒放行**（空账本） | F-I8（C-5「查询只 check 不 record」错误） |
| R5 | [RESEARCH §3.2 L88](RESEARCH_p053_trading_gateway.md) 官方字典 | xtquant：**52 部成待撤 / 53 部撤 / 54 已撤 / 55 部成**；CTP：查询流控默认 1 笔/秒（在途 1 笔）；请求返回 **-2 未处理请求超许可、-3 每秒请求超许可**（请求级，未送达柜台） | F-I7 |
| R6 | [event_log.py](../core/event_log.py#L60-L67) 8 个 `AUDIT_*` 常量 | IMPL 全部使用合法常量；`append(event_type, payload, source=...)` 的 source 在 entry 级 | F-I17（payload 内重复 source） |
| R7 | [execution_policy.py](../core/execution_policy.py#L57-L88) `OrderIntent` | `asset/asset_type/target_quantity/current_quantity/urgency` + `action`/`abs_trade_quantity` property——`_validate_args` 引用合法 | ✓ |
| R8 | [guard_pipeline.py](../core/guard_pipeline.py#L36) `GuardContext.price` 必填 | C-6 市价预留基准价 `ctx.price` 成立 | ✓ |
| R9 | IMPL §3.2 代码面 | orders.py 无 `OrderRequest` 定义 + 错误 import；`LEGAL` 无自环 | F-I2 / F-I5 |
| R10 | IMPL §3.8 代码面 | `record` 遮蔽；`CapabilityError`/`ChannelUnavailable`/`replace`/`asdict` 未 import；`_query_ledger` 死设；`_reconciled_at_start` 死赋值；`explained=frozenset(a.asset ...)` | F-I1/I8/I11/I13/I15 |

---

## 3. 发现明细

### P1（5 项）

**F-I1 `record` 名字冲突（submit/cancel 成功路径必崩）**
证据：gateway import 块 `from core.compliance import record`；submit() L1378 `record = from_request(request, ts=ts)` 后 L1388 `self._submit_ledger = record(self._submit_ledger, ts, False)`；cancel() L1443 同构。
影响：P-052 流控 `record()` 永不执行且抛 TypeError——成功提交必崩，测试①②④⑤全挂。
修复：局部变量一律 `rec`（submit/cancel/cancel_all/confirm/_apply_order_report 五处），模块级 `record` 保留供三桶调用。

**F-I2 `OrderRequest` 缺定义 + 错误 import**
证据：§1 表 row 2 声称 orders.py 含 `OrderRequest`，但 §3.2 码面只有错误 import（首行 `from live.channel import OrderRequest`）；channel.py 仅 TYPE_CHECKING 引入。
影响：import 闭合失败——所有模块（含 4 适配器 `from live.orders import OrderRequest`）ImportError。
修复：`OrderRequest` 冻结数据类落 orders.py（字段：asset/side/quantity/asset_type="stock"/price=None/order_type="limit"/client_order_id=""/account_id/strategy_id/signal_ts/remark——覆盖 `replace(request, client_order_id=coid)`、`_validate_args`、terminal CSV 全部用法）；删 channel import 行。

**F-I3 现金符号三处不自洽（守恒式与 replay 失真）**
证据：(a) apply_fill 买入 amount=+q*p、卖出 amount=−q*p（现金变动=−amount ✓），但 apply_corporate_action/cash_adjust 的 amount=+现金流入（现金变动=+amount ✗）；(b) C-2 公式 `−Σentry.amount + Σca_cash`：ca 条目被 −amount 与 +ca_cash 各计一次（净 0，实际 +流入）→ 双算；cash_adjust 只被 −amount 覆盖 → 漏计；(c) replay `cash -= e.amount` 对 ca/adjust 与 apply 反向。
影响：分红/入金/配股场景守恒断言（test_ledger ⑤⑬⑭）与 parity 现金比较必错。
修复：统一「**任一 entry 现金变动 = −amount（fee 单列恒 −fee）**」——ca/cash_adjust 的 entry.amount = −现金变动（分红流入 → amount<0）；`cash_adjust` 参数改名 `delta`（语义=现金变动）；卖出分支拆两行 `cash += q*p` / `cash -= f`（与 entry 逐项对应）；守恒式改全 kind 通用 `cash + reserved == initial − Σamount − Σfee`；C-2 与 DESIGN I4 同步改写（§4-3 给出与原分组式的等价推导）。

**F-I4 循环 import**
证据：ledger.py L466 `from live.corporate_actions import CorporateAction, adjust_position`（运行期）；corporate_actions.py L1111-1112 `from live.ledger import PositionLot` + `from live.reconcile import Break, BreakLevel`（运行期）；reconcile.py L849 `from live.ledger import LedgerSnapshot`。
影响：任一入口先触发 `ImportError: cannot import name ... (most likely due to a circular import)`。
修复：corporate_actions 运行期仅 `from live.reconcile import BreakLevel`（attribute_break 的 `replace(brk, level=BreakLevel.MISSED)` 需运行期枚举），`PositionLot`/`Break` 转 TYPE_CHECKING（`dataclasses.replace` 鸭子类型，构造点都在 ledger/reconcile 本域）；reconcile 的 `LedgerSnapshot` 转 TYPE_CHECKING（仅注解）+ 删未使用的 `FillRecord` import → 无环：`ledger → corporate_actions → reconcile → ∅`。

**F-I5 transition 同态回报三缺陷（复审新发现）**
证据：(a) 同态短路 L415 `if record.state is state and filled_quantity is None and broker_order_id is None`——mock/CTP ack 默认 `state=PENDING_NEW` 且带 broker_order_id → 落入 `LEGAL[A]` 查不到 `A` → `OrderTransitionError`（submit 步⑧无 try 包裹 → 直接抛）；(b) `LEGAL[PARTIALLY_FILLED]`/`LEGAL[PENDING_CANCEL]` 无自环 → 多次部成回报（volume_traded 递增）与 CTP 52 重报被 ignored_transition 丢弃；(c) C-8 幂等语义与 ack 回填冲突。
影响：默认成功提交必崩（P1 主证据）；修复 (a) 后 (b) 仍致 filled_quantity 滞后、对账误报。
修复：同态短路改为「`state` 相同且 `filled_quantity is None` → 若携带新 broker_order_id 则仅回填该字段（ack 场景），否则原对象返回」；`LEGAL` 增 `PARTIALLY_FILLED→PARTIALLY_FILLED`、`PENDING_CANCEL→PENDING_CANCEL` 自环（fq 单调不减由既有校验③保证）；C-8 ④ 与 DESIGN §3.2 迁移表同步。

### P2（8 项）

**F-I6 Terminal 被能力门三处阻塞**
证据：Terminal capability `supports_cancel/query_orders/query_trades/query_positions=False, autonomous=False`；submit 步③ `need={"client_order_id","cancel","query_orders"}`；start() `need={"query_trades"}` 且无条件调 query_trades/query_orders；reconcile 无条件 query_positions。
影响：Terminal 通道 start/submit/reconcile 全部 CapabilityError——三桥缺一，D1 违约。
修复：autonomous 条件化——start()：`autonomous` 才 require `{query_trades, query_orders}` 并执行查询恢复，否则跳过；submit 步③：autonomous → `{client_order_id, cancel, query_orders}`，半自动 → `{client_order_id}`；reconcile()：非 autonomous → `audit.reconcile(action="manual_channel")` 后返回空报告（人工对账走 runbook，不入网关）。

**F-I7 CTP 状态映射与错误码处理**
证据：(a) `_CTP_STATUS["52"] = PARTIALLY_FILLED`——官方字典 52=部成待撤（复合态：撤单进行中且有部分成交），应映射 `PENDING_CANCEL`（filled_quantity 由回报承载；53 部撤→CANCELED ✓、55 部成→PARTIALLY_FILLED ✓ 复核无误）；(b) submit 仅 `if code in ("-2","-3")` 抛 ChannelRejected——**其余非 0 error_id（柜台真实拒单）被当成功**，返回 SubmitAck；(c) -2/-3 是**请求级流控**（未送达柜台，RESEARCH §3.2），按 ChannelRejected 处理会错误触发 release+`on_order_result(rejected=True)`（污染熔断计数）。
影响：CTP 柜台拒单被静默吞掉（成交永远不来）；流控误计拒单。
修复：52 → `PENDING_CANCEL`（复合态注记）；submit/cancel 对 `error_id` **非 0 一律拒绝**（`not in ("0","")` → ChannelRejected）；-2/-3 单列 `ChannelUnavailable`（请求级可重试），gateway submit/cancel 增 catch——release 预留 + audit，**不调 on_order_result**。DESIGN §3.9 ctp 行「-2/-3 → ChannelRejected」同步改写。

**F-I8 查询流控未实现（C-5 查询桶死设）**
证据：`self._query_ledger = RateLedger()` 从未被 check/record；start() 连续两次查询、reconcile 查询均零限流；C-5 声称「query 桶只 check 不 record」——但 R4 实证不 record 的账本 check 恒放行。
影响：CTP 1 笔/秒硬约束失效（违规返回 -3 反被当拒单）；测试 flow_recovery ④ 无支撑。
修复：新增 `_throttle_query(ts)`：独立 `_query_ledger` + `check_rate` + `record(is_cancel=False)`（先 check 后 record）；`_query_config` 在 start() 由 `resolve_limits().query_per_sec` 构造（`max_per_second=int(max(1, round(query_per_sec)))`，日上限保守沿用 `rate_config.max_per_day`——RESEARCH 无查询日上限证据）；start() 两次查询、reconcile 的 query_positions 前各调一次；超限抛 `ChannelUnavailable`（fail-closed，测试④断言第二次被限）。C-5 改写。

**F-I9 成功回报不重置拒单计数**
证据：R1——`on_order_result(rejected=False)` 将 `consecutive_rejects` 重置 0；gateway 仅 REJECTED 分支调用（rejected=True）。
影响：一次拒单后即使后续全部成功成交，计数永不复位 → 熔断阈值误触发（P-052 `max_consecutive_rejects`）。
修复：_apply_order_report 非 REJECTED 迁移分支调 `on_order_result(rejected=False, ts)`；submit() ack 成功后同样调用。

**F-I10 ledger 与 store 未接线、无恢复重建**
证据：gateway 同时收 `ledger` 与 `store` 但从不关联；`Ledger.__init__(store=None)` → `_append` 跳过 `store.append_entry` → 分录不落库；重启后无内存账本重建路径。
影响：test_ledger_store 全过但端到端 E⑤（崩溃重启恢复）断档；且重复回放已持久化 fill 时（`_seen` 为空）会二次入账。
修复：`Ledger.attach_store(store)` + gateway.start() 首步接线；新增 `Ledger.resume(entries, *, initial_cash)` 类方法（replay 结果回填 `_cash/_positions/_entries/_seen`）与 `initial_cash` property；start() 在查询恢复**之前**：`persisted = store.entries()`，非空且内存账本无分录 → `Ledger.resume(...)`（幂等防重放）。恢复序 = SSE 口径：resume → query_trades（成交先行）→ query_orders → load_orders → reconcile。

**F-I11 gateway import 缺漏**
证据：码面使用 `CapabilityError`（start/submit）、`ChannelUnavailable`（F-I7/F-I8）、`replace`（步⑤/reconcile）、`asdict`（C-11）、`Iterable`（ingest_fills）均未 import；尾注 L1536 承认「正式落码时补 import」。
影响：Step 9 照抄即 NameError ×5。
修复：import 块补齐（`dataclasses: asdict, dataclass, replace`；`typing: Callable, Iterable`；channel 增 `CapabilityError, ChannelUnavailable`；ledger 增 `LedgerEntry`；reconcile 增 `BreakLevel`）；尾注改写为「已入 import 块」。

**F-I12 Terminal 回填无网关路径**
证据：terminal.import_fills 产出 `list[FillReport]`，但 gateway 无任何方法接收（poll 只吃 drain_reports）。
影响：半自动链路（订单清单 → 人工成交 → 回填入账）断在最后一步；E2E 测试③无落点。
修复：新增 `gateway.ingest_fills(reports)`：逐笔 `FillRecord(**asdict(report))` → `apply_fill(ts=report.ts)` → 成功才 `audit.fill`；返回新增 `list[LedgerEntry]`（与 poll D-5 口径一致）。

**F-I13 explained 过宽（历史行为资产恒 MISSED）**
证据：reconcile() `explained = frozenset(a.asset for a in self._actions)`——只要资产**曾经**有过公司行为，其一切持仓差异未归因即判 MISSED（而非 UNRESOLVED）。
影响：D7 判级语义失效（MISSED=「可解释」被放大为「曾有过事件」），UNRESOLVED→HALTED 停机门漏触发。
修复：`explained=frozenset()`；精确归因完全交给 `attribute_break`（命中才升级 MISSED 并记 action_id——「先归因再判级」的本意）。

### P3（4 项）

**F-I14 `__dict__` → `asdict()` 与 import 尾注**
证据：start()/poll() 用 `FillRecord(**report.__dict__)`（C-11 自身写的是 asdict）；尾注与 F-I11 一并处理。
修复：两处改 `asdict(report)`（frozen dataclass 规范路径，消除对 `__dict__` 实现细节的依赖）。

**F-I15 死赋值 / ts 参数 / pre_open 登记**
证据：start() 尾行 `self._reconciled_at_start = self.reconcile(...)` 无人消费；`apply_corporate_action` 无 `ts` 参数而 entry `ts=0.0` 硬编码（I11 零时钟要求由**调用方注入**）；`DaySession.pre_open` IMPL 与 DESIGN §3.6（L409）**一致**，无需回写。
修复：删死赋值（保留 reconcile 调用本身）；`apply_corporate_action(self, action, *, ts: float)`；D-6 登记 pre_open 核对闭合。

**F-I16 UNKNOWN 的 drain 收敛口径**
证据：C-8 ④声称「drain_reports 的乱序帧不驱动 UNKNOWN→X」，但 `_apply_order_report` 对任意 OrderReport 都执行 transition，`LEGAL[UNKNOWN]` 又放行全部非 UNKNOWN → 声明与实现矛盾。
影响：I9「UNKNOWN 只能由 query/confirm 迁出」的保守语义落空。
修复：`_apply_order_report(..., from_query: bool = False)`；`from_query=False` 且 `rec.state is UNKNOWN` → `ignored_transition` 审计后返回；start() 查询回放传 `from_query=True`；C-8 ④ 改写为与实现一致。

**F-I17 注记组（4 小项）**
①`resolve_limits` 的 `query_per_sec=min(query, submit)` 为保守耦合（无监管证据），docstring 注记；②mock `SubmitAck ts=0.0`：ack.ts 不被网关消费（transition 用 submit 的 ts），确定性注记（I1）；③`_audit` 的 payload 经 `build_audit_payload` 嵌 `source` 与 `append(source=_SOURCE)` 双写 → payload 侧删除，source 只写 entry 级（R6）；④replay 的 avg_cost 反推 `ratio=(q+Δq)/q` 对 STOCK_DIVIDEND/SPLIT 与 `adjust_position` **等价**（§4-5 验算），RIGHTS_ISSUE（apply 不摊薄）**不在 replay 等价范围** → docstring 限定 + I10 测试范围确认（test_ledger ⑭ 只断言送转/拆股）。

---

## 4. IMPL §7 六项复审输入作答

| # | 输入 | 作答 |
|---|---|---|
| 1 | C-1..C-12 是否码面可验证 | C-1 ✓（F-I2 修复后成立：orders 定义 OrderRequest，channel 仅 TYPE_CHECKING）；**C-2 改写**（F-I3 统一符号）；C-3 ✓；C-4 ✓；**C-5 改写**（F-I8：查询桶必须 record——独立账本上 record 不污染委托计数）；C-6 ✓；C-7 ✓；**C-8 修订**（F-I5 同态回填 + 自环；F-I16 from_query 参数）；C-9 ✓（source 去重，F-I17③）；C-10 ✓；C-11 ✓（码面 `__dict__` 改 asdict 对齐，F-I14）；C-12 ✓（先关连接再删锁实证） |
| 2 | D-1..D-5 是否回写 DESIGN | D-1 ✓ 已回写 §3.8 签名（cost_buffer）；D-2 ✓ 已回写 §3.3（cash_adjust 纳入统一口径，参数 delta）；D-3 ✓ 采纳不导出；D-4 ✓ 采纳（gateway 侧以 ts 补 as_of）；D-5 ✓ 采纳（poll/ingest_fills 以 entries 切片取新增）；新增 **D-6**（pre_open 核对闭合）、**D-7**（resume/attach_store 恢复口径）、**D-8**（ingest_fills/_throttle_query 新方法）登记 §5 |
| 3 | C-2 统一式与 DESIGN I4 分组式代数等价？ | 原草案**不等价**（F-I3：ca 双算、cash_adjust 漏计）。修复后统一式 `cash+reserved == initial − Σamount − Σfee` 与分组式互相推导：买入分组项 `−(buy.amount+buy.fee)` = −amount−fee ✓；卖出分组项 `+(sell.amount−sell.fee)`，其中 sell.amount=−q*p → −amount−fee = q*p−fee ✓；ca 项：原式 Σca_cash 在统一式下由 `−amount` 承载（amount=−现金变动）✓。**等价成立** |
| 4 | C-5 三桶满足先 check 后 record？查询桶不 record 影响？ | submit/cancel 桶 ✓。查询桶「只 check 不 record」**错误**：R4 实证空账本 check 恒放行 → 流控死设。改独立账本 + record(is_cancel=False)；其 `daily_orders` 语义=当日查询数，因账本隔离不污染 P-052 委托计数（`_refresh_ctx` 只读 submit 桶） |
| 5 | replay ratio 反推与 adjust_position 等价？ | STOCK_DIVIDEND/SPLIT：apply `new_avg=avg/(1+r)`；replay `ratio=(q+q·r)/q=1+r` → `avg/ratio` ✓ 等价。RIGHTS_ISSUE：apply 不摊薄（U-P053-12 只调数量），replay 会摊薄 → **不等价**，登记为 replay 已知限制（F-I17④；test_ledger ⑭ 范围本就不含配股） |
| 6 | 86 例与 DESIGN §7 一一对应？ | ✓ 逐文件对齐（10/14/14/6/12/8/8/8/6=86）；F-I7/I8 修复使 flow_recovery ④ 与 E2E ③⑤ 获得实现支撑；无用例增删 |

---

## 5. 修复回执与结论

| 落点 | 内容 | 状态 |
|---|---|---|
| IMPL §1 | 依赖边改写（F-I2/I4 后的真实 DAG）+ gateway 方法清单增 ingest_fills | ✅ |
| IMPL §2 | C-2/C-5/C-8 改写（统一符号 / 查询桶 record / 同态语义 + from_query） | ✅ |
| IMPL §3.2 | OrderRequest 定义 + 删错误 import + LEGAL 双自环 + transition 同态短路 | ✅ |
| IMPL §3.3 | 卖出/ca/cash_adjust 符号统一 + apply_corporate_action(*, ts) + attach_store/initial_cash/resume + replay 限定注记 | ✅ |
| IMPL §3.5/§3.7 | reconcile TYPE_CHECKING + 删未用 import；corporate_actions BreakLevel 运行期 + TYPE_CHECKING 化 | ✅ |
| IMPL §3.8 | rec 改名 ×5、import 补齐、autonomous 条件化（步③/start/reconcile）、_throttle_query、on_order_result 双向调用、ChannelUnavailable 捕获、attach_store+resume 接线、explained=frozenset()、ingest_fills、asdict、死赋值删除、source 去重 | ✅ |
| IMPL §3.9 | ctp：52→PENDING_CANCEL + 非 0 拒单 + -2/-3→ChannelUnavailable；mock ack ts 注记 | ✅ |
| IMPL §5 | D-1/D-2 处置更新；新增 D-6/D-7/D-8 | ✅ |
| DESIGN | §2 依赖边（4 行改写）；§3.3 统一公式 + cash_adjust/attach_store/resume + 记账表 cash_adjust 行；§3.8 签名 cost_buffer + start 步序 + ingest_fills + 步③/⑦/⑧/poll 口径；§3.9 ctp 行错误码语义 | ✅ 4 处 |
| PROGRESS / RESEARCH | P-053 行 → Step 1-6 完成；§3.60 追加 Step 6 bullet；RESEARCH 头部状态链 | ✅ |

**遗留与移交**：
- 五文档 + 本复审文档**未提交**（待用户授权；提交行更新为六新文档）。
- CTP 真连语义（SimNow 首连、断线重连重认证、MaxOrderRef 重建）按 U-P053-1 保持后置；`_throttle_query` 的 start() 双查询在 CTP 1/s 下需间隔（真实批次以 sleep/重试解决，本批零 sleep 口径不变）。
- **Step 6 关闭，可进 Step 7（CHECKLIST）**。
