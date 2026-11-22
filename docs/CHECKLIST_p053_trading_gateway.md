# CHECKLIST：P-053 交易通道网关（channel / orders / ledger / store / reconcile / calendar / corporate_actions / gateway / 4 适配器）

> **批次**: P-053 · **Step 9 + Step 10** · 日期 2026-11-22 · **判档 P2**
> **上游**: [IMPL_p053](IMPL_p053_trading_gateway.md)（13 文件逐处代码 / C-1..C-12 / 86 例映射 / D-1..D-13）；[DESIGN_p053](DESIGN_p053_trading_gateway.md)（D1-D16 + I1-I12 + §5 阈值表）；[REVIEW_p053_step6](REVIEW_p053_step6_impl.md)（5 P1 + 8 P2 + 4 P3 → 17/17 修复，0 P1 残留）；[REVIEW_p053_step10](REVIEW_p053_step10_acceptance.md)（异构复审 22 发现 → 7 修复 + 4 订正 / 6 登记）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **状态**: Step 9 + Step 10 完成（2026-11-22），75/75 ✅ + 异构复审回执（§10）
> **基线读数（@`e9e945f`，P-052 关闭态）**: pytest **1214** / `-k golden` **22** / mypy **128 files 0** / black `--check .` **261** / `tests/*.py` **132** / `core/*.py` **51** / `live/*.py` **3**
> **目标读数**: pytest **1300**（+86）/ `-k golden` **22**（零重录）/ mypy **141 files 0**（+13）/ black **283 unchanged**（+22）/ `tests/*.py` **141**（+9）/ `core/*.py` **51 不变** / `live/*.py` **16**（+13）

---

## 1. M 组：模块与代码（13 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| M1 | `live/channel.py` 新建：`ChannelState`(5 值) + `ChannelCapability`(**16 字段**，Step 10 订正：含 `notes`，DESIGN/IMPL/代码三方一致) + 3 异常（`CapabilityError`/`ChannelRejected`/`ChannelUnavailable`）+ `require_capability`（**7 开关键 + 品种名 fallback** = 8 类合法键）+ `resolve_limits`（内部/通道/监管三方 `min`）+ `ChannelLimits` + 4 回报 dataclass（`SubmitAck`/`OrderReport`/`FillReport`/`PositionReport`）+ `ChannelAdapter` ABC(7 方法)；**运行期零内部 import**（`OrderRequest`/`OrderState` 仅 `TYPE_CHECKING`，C-1） | 无 | 读码 + T1 | ✅ 读码：`live/channel.py` 五状态/**16 字段**/3 异常/**7 开关 `_SWITCHES`**/三方 `min`/4 dataclass/ABC 齐备，`orders` 仅 `TYPE_CHECKING`；T1 10/10 绿（Step 10 订正计数口径） |
| M2 | `live/orders.py` 新建：`OrderState`(9 值) + `TERMINAL_STATES` + `LEGAL` 全表（含 `A→1`/`A→2` 秒成交，F-D3；含 `PARTIALLY_FILLED→PARTIALLY_FILLED`/`PENDING_CANCEL→PENDING_CANCEL` 自环，F-I5）+ `OrderRequest`（**本文件定义**，F-I2）+ `make_client_order_id`（sha1-16，`co_` 前缀）+ `OrderRecord` + `FillRecord` + `transition`（四步校验序 C-8；同态带量自环；同态 + 新 `broker_order_id` 仅回填，F-I5）+ `from_request`；**无 `from live.channel import ...`** | 无 | 读码 + T2 | ✅ 读码：9 状态 + `LEGAL` 含 `A→1/A→2` 与 PF/PC 自环；`OrderRequest` 本文件定义；`grep "from live.channel" live/orders.py` = 0；T2 14/14 绿（含 ack 回填 / PF→PF / PC→PC） |
| M3 | `live/ledger.py` 新建：`PositionLot`/`LedgerEntry`/`LedgerSnapshot`/`LedgerError` + `Ledger`（`reserve`/`release`/`settle_reserve`/`apply_fill`/`apply_corporate_action(*, ts)`/`cash_adjust(*, delta)`/`snapshot`/`entries`/`initial_cash`/`attach_store`/`resume`/`replay`）；**符号统一**（任一 entry 现金变动 = −amount，fee 单列，F-I3）；运行期内部 import 为 `live.corporate_actions` 与 `live.orders.FillRecord`（Step 10 订正口径） | 无 | 读码 + T3 | ✅ 读码：12 个方法齐备；`cash_adjust(*, asset, delta, ref, ts)` 且 `amount=-delta`；买入/卖出/fee 三路现金符号统一；运行期 import `corporate_actions` + `orders.FillRecord`（与 IMPL §3.3 一致）；T3 14/14 绿 |
| M4 | `live/ledger_store.py` 新建：`LedgerStore` Protocol + `SqliteLedgerStore`（`journal_mode=WAL`、`synchronous=FULL`、`BEGIN IMMEDIATE`、`.lock` 单写者、三表 entries/orders/outbox；`append_entry`/`upsert_order`/`load_orders`/`append_outbox`/`entries`；C-12 先关连接再删锁） | 无 | 读码 + T4 | ✅ 读码：WAL/FULL/BEGIN IMMEDIATE/三表齐备；`close()` 先 `_conn.close()` 再 `os.unlink(lock)`；T4 6/6 绿（含第二实例 `OSError`、outbox 回滚） |
| M5 | `live/reconcile.py` 新建：`BreakLevel`/`ReconcileConfig`/`ParityConfig`/`Break`/`ReconcileReport`/`ParityReport` + **8 函数**（Step 10 订正：`classify_quantity` 等 8 个；含 `evaluate_parity`/`should_degrade` 日期维度）；**运行期零内部依赖**（`LedgerSnapshot` 仅 `TYPE_CHECKING`、未用 `FillRecord` import 已删，F-I4） | 无 | 读码 + T5 | ✅ 读码：6 dataclass/Enum + **8 函数**（`classify_quantity`/`reconcile_positions`/`reconcile_cash`/`reconcile_fills`/`overall_level`/`overall_level_breaks`/`evaluate_parity`/`should_degrade`）；运行期零内部 import；T5 12/12 绿 |
| M6 | `live/session_calendar.py` 新建：`SessionPhase`(6 值) + `DaySession`（含 `pre_open` 字段，D-6）+ `Calendar` + 5 函数；`can_submit` 固定规则（不依赖 capability）、收盘集合竞价 14:57-15:00 | 无 | 读码 + T7 | ✅ 读码：6 相位 + `pre_open` + **5 函数**（`local_day`/`is_trading_day`/`session_phase`/`next_trading_day`/`can_submit`，Step 10 订正计数）；收盘竞价区间 14:57-15:00；T7 8/8 绿 |
| M7 | `live/corporate_actions.py` 新建：`ActionType`(4 值) + `CorporateAction` + `load_actions`/`actions_for`/`adjust_position`/`attribute_break`；**运行期仅依赖 `live.reconcile.BreakLevel`**，`PositionLot`/`Break` 仅 `TYPE_CHECKING`（F-I4；`replace` 鸭子类型） | 无 | 读码 + T8 | ✅ 读码：4 类型 + 4 函数；运行期唯一内部 import 为 `BreakLevel`；T8 8/8 绿 |
| M8 | `live/gateway.py` 新建：`SubmitResult` + `TradingGateway`（start/submit/poll/cancel/cancel_all/reconcile/pending_unconfirmed/confirm/ingest_fills/shutdown + 内部 `_throttle_query`）；八步固定序；**局部变量无 `record` 遮蔽**（F-I1）；import 块含 `CapabilityError`/`ChannelUnavailable`/`replace`/`asdict`/`Iterable`/`LedgerEntry`/`BreakLevel`（F-I11）；autonomous 条件化（F-I6）；`_throttle_query` 独立桶 check+record（F-I8）；`on_order_result` 双向调用（F-I9）；`attach_store` + 空账本 `Ledger.resume` 先于查询恢复（F-I10）；`explained=frozenset()`（F-I13）；`from_query` 参数（F-I16）；无 `_reconciled_at_start` 死赋值（F-I15） | M1-M7 | 读码 + T6/T9 | ✅ 读码：11 个公开方法 + `_throttle_query`；submit 八步序 ①-⑧；`rec =` 五处、`record =` 0 处；import 块齐 7 符号；T6 8/8 + T9 6/6 绿 |
| M9 | `live/adapters/__init__.py`（docstring only）+ `mock.py` 新建：`Frame`/`FakeTransport`（`scripts` 帧序列）/`MockChannelAdapter`（挂 `MockLiveBridge` 复用 `gate.cancel_all`）；确定性（不 sleep、无随机）；`SubmitAck ts=0.0` 注记（F-I17②） | M1/M2 | 读码 + T6/T9 | ✅ 读码：`Frame`/`FakeTransport`/`MockChannelAdapter` 齐备，挂 `MockLiveBridge`，无 sleep/random，ack `ts=0.0` 注记在；T6 ②⑦ + T9 ①④ 绿 |
| M10 | `live/adapters/ctp.py` 新建：`CtpTransport` Protocol + `CtpChannelAdapter`；`_CTP_STATUS` 按官方字典（**52 部成待撤 → `PENDING_CANCEL`**，F-I7）；submit/cancel `error_id` 非 0 → `ChannelRejected`，**`-2`/`-3` → `ChannelUnavailable`**（请求级流控不计拒单，F-I7）；**`supports_client_order_id=True` + `_refs` coid↔(FrontID,SessionID,OrderRef) 映射**（Step 10 F-R5-1/F-R5-5，D-9/D-10） | M1/M2 | 读码 + T6 | ✅ 读码：`"52": OrderState.PENDING_CANCEL`；`-2`/`-3` → `ChannelUnavailable`，其余非 0 → `ChannelRejected`；capability `True` + submit 登记 `_refs` + `query_orders` 按 order_ref 反查回 coid；T6 查询桶/恢复序绿 |
| M11 | `live/adapters/broker_api.py` 新建：`BrokerApiChannelAdapter` 语义占位（`capability(venue="broker_api", autonomous=True, supports_client_order_id=True)`；未注入 transport → 全部动作 `ChannelUnavailable`） | M1 | 读码 | ✅ 读码：capability 三字段符合；submit/cancel/query_* 无条件抛 `ChannelUnavailable`（transport 已注入亦不可用——语义占位，Step 10 订正措辞；`_require` 为死占位） |
| M12 | `live/adapters/terminal.py` 新建：`TerminalChannelAdapter`（`autonomous=False`）；`submit` 追加 CSV 固定 10 列（UTF-8-SIG）+ `audit.order`；`import_fills` → `list[FillReport]`；`cancel`/`query_*` → `CapabilityError` | M1/M2/M8 | 读码 + T9 | ✅ 读码：`autonomous=False`；`_ORDER_COLUMNS` 10 列 + `utf-8-sig` + `AUDIT_ORDER`；`import_fills` 返回 `list[FillReport]`；T9 ③ 绿 |
| M13 | **零改动**：`core/safety_gate.py`、`core/event_log.py`、`core/compliance.py`、`core/live_bridge.py`、`core/execution_policy.py`、`live/safety_store.py`、`pyproject.toml`（D14/U-P053-8：P-052 契约零改写、零新依赖） | 无 | `git diff --stat` | ✅ `git status --porcelain` 对上述 7 文件输出为空（零改动、零新依赖） |

---

## 2. T 组：测试（9 文件 / 86 条）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| T1 | `tests/test_p053_channel_capability.py` **10 条**：缺 `cancel` 抛 `CapabilityError` 且消息含键 / `report_registered=False` 拒 / 品种门 / `resolve_limits` 三方取 min（内部低、通道低、监管 300 兜底）/ 查询上限独立 / `ChannelRejected` 保留 code+reason / `SubmitAck` 可构造 / 五状态值固定 | M1 | pytest | ✅ 10 passed（`test_t1_*` 全绿） |
| T2 | `tests/test_p053_order_semantics.py` **14 条**：coid 同输入同值 / 异输入异值 / 前缀与长度 / `from_request` 初始 `PENDING_NEW` / `A→0` / **`A→1`、`A→2` 秒成交** / `A→8` / `0→4` / `1→2` / `6→4` / `UNKNOWN→0` / 终态不可逆（2/4/8/C）/ filled 回退抛错 / filled > quantity 抛错；**另含 PF→PF 带量自环与 PC→PC 重报**（F-I5） | M2 | pytest | ✅ 14 passed；`co_`+16hex=19 字符（IMPL §4「18」为文档笔误，已按代码约定断言）；含 ack 回填 / PF→PF / PC→PC；**含 A→2 直接断言**（Step 10 F-R5-7 补，`transition(_record(), state=FILLED)`） |
| T3 | `tests/test_p053_ledger.py` **14 条**：买入加权成本 / 两次买入摊薄 / 卖出 `realized_pnl` / 卖出清零 `avg_cost=0` / **现金守恒（买+卖+费，统一式 I4）** / fee 独立 entry / `entry_id` 重复返回 False / reserve 后 cash 减少 / release 退还 / settle 退还差额 / reserve 超现金 `LedgerError` / `settle_reserve` 无预留 `LedgerError` / 分红 cash_delta（entry.amount=−delta） / 送转+拆股 + `replay` 等价 | M3 | pytest | ✅ 14 passed |
| T4 | `tests/test_p053_ledger_store.py` **6 条**：建表幂等 / `journal_mode=wal` / `entry_id` 冲突返回 False / outbox 同事务回滚 / **第二实例 `.lock` 抛错（I8）** / 重启后 entries+orders 读回 | M4 | pytest | ✅ 6 passed |
| T5 | `tests/test_p053_reconcile.py` **12 条**：delta=0 → OK / DUST 绝对阈值 / DUST 比例阈值 / `explained` → MISSED / 未解释 → UNRESOLVED / 现金 DUST / 现金 UNRESOLVED / `missing_fill` → MISSED / `extra_fill` → UNRESOLVED / overall 取最严重 / `evaluate_parity` 四项 breach / `should_degrade` 连续 2 日含中断重置 | M5 | pytest | ✅ 12 passed |
| T6 | `tests/test_p053_flow_recovery.py` **8 条**：恢复顺序 trades→orders（桩记录调用序） / 断线重连不重发（`transport.sent` 计数） / 宽限期前后 `pending_unconfirmed` / **查询桶 1/s（第二次 query 被限，F-I8）** / 拒单回写 `on_order_result(rejected=True)` / **kill 激活 `adapter.submit` 零调用（I6）** / `cancel_all` 走 bridge 返计数 / HALTED 拒新开（`channel_halted`） | M8/M9/M10 | pytest | ✅ 8 passed；拒单例补 `pre_trade_check` spy（Step 10 F-R5-8，I5 直接断言 `gate_calls==[1]`） |
| T7 | `tests/test_p053_session_calendar.py` **8 条**：HOLIDAY / PRE_OPEN / CONTINUOUS / LUNCH / CLOSE_AUCTION / CLOSED（15:00 后）/ `can_submit` 组合（竞价限价 True、市价 False）/ `next_trading_day` 跨周末 + 时区边界 | M6 | pytest | ✅ 8 passed |
| T8 | `tests/test_p053_corporate_actions.py` **8 条**：现金分红 / 送股 / 拆股 / 配股（不扣现金） / `load_actions` 缺列 `ValueError` / `actions_for` 日期过滤 / `attribute_break` 现金归因 → MISSED / `attribute_break` 未知资产原样返回 | M7 | pytest | ✅ 8 passed |
| T9 | `tests/test_p053_end_to_end.py` **6 条**：submit 全链（gate→reserve→adapter→audit.order+outbox） / 拒单链（release + `on_order_result` + audit） / **Terminal 清单 + `ingest_fills` 入账（F-I12）** / 完整日循环（submit→poll fill→reconcile OK） / **崩溃重启恢复（新 store 读回 orders + `Ledger.resume`）** / 对账 unresolved → `state=HALTED` | M8/M12 | pytest | ✅ 6 passed（重启恢复断言 `second._ledger`：`start()` 以新 `Ledger.resume` 替换实例） |
| T10 | 用例合计 **86**（10+14+14+6+12+8+8+8+6）；总 pytest = 1214+86 = **1300**；9 新文件无 `skip`/`xfail` | T1-T9 | pytest 计数 | ✅ `-k p053` = **86 passed**；全量 = **1300 passed**；9 文件 `grep skip\|xfail` = 0 |

---

## 3. C 组：门禁（7 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `$env:MPLBACKEND='Agg'; .\.venv\Scripts\python.exe -m pytest -q` | **1300 passed** | ✅ `1300 passed, 278 warnings in 138.34s`（Step 10 修复后重跑；Step 9 首跑 140.15s） |
| C2 | golden | `-m pytest -q -k golden` | **22 passed**（零重录） | ✅ `22 passed, 1278 deselected`（零重录） |
| C3 | mypy | `-m mypy --explicit-package-bases --check-untyped-defs core … strategies live` | **141 files 0** | ✅ `Success: no issues found in 141 source files` |
| C4 | black | `-m black .` 后 `-m black --check .` | **283 files unchanged** | ✅ `283 files would be left unchanged`（首次格式化 8 新文件） |
| C5 | 无 golden 改动 | `git status --porcelain tests/golden` | 输出为空 | ✅ 输出为空 |
| C6 | 零新依赖 | `git status --porcelain -- pyproject.toml requirements*.txt` | 输出为空（仅 stdlib） | ✅ 输出为空 |
| C7 | 文件计数 | `(Get-ChildItem tests/*.py).Count` 等 | `tests/*.py` **141** / `core/*.py` **51** / `live/*.py` **16** | ✅ 141 / 51 / 16 |

---

## 4. I 组：不变式（12 项，对应 DESIGN I1-I12）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | `channel`/`orders`/`reconcile`/`session_calendar`/`corporate_actions` 判定函数零 I/O、零 `datetime.now`、零随机 | grep 五文件 + 固定 `ts` 单测（T1-T5/T7/T8） | ✅ 五文件 `grep datetime.now\|time.time\|random.` 零命中；T1-T5/T7/T8 全绿 |
| I2 | 终态（FILLED/CANCELED/REJECTED/EXPIRED）不可迁移；`filled_quantity` 单调不减 | T2 全枚举 | ✅ T2 ⑫ 四终态逐一抛 `terminal`；⑬ 回退抛 `regressed`；⑭ 超量抛 `> quantity` |
| I3 | `entry_id`/`fill_key` 唯一；重复入账返回 False 且状态不变 | T3 ⑦ / T4 ③ | ✅ T3 ⑦ 第二次 False 且 entries=1；T4 ③ 同 entry_id 第二次 False |
| I4 | 现金守恒 `cash + reserved == initial_cash − Σ entry.amount − Σ entry.fee`（<1e-6，全 kind 通用） | T3 ⑤⑬⑭ + 快照复算 | ✅ T3 ⑤ 买+卖+费、⑬ 分红、⑭ 送转+拆股复算均 `pytest.approx(..., abs=1e-6)` 通过 |
| I5 | `submit()` 除 `channel_halted`/`session_closed` 外**必经** `pre_trade_check`（含被拒路径） | 打桩计数（T6/T9） | ✅ T6 ⑤ 拒单前已过 gate：`pre_trade_check` spy `gate_calls==[1]` + `on_order_result(rejected=True)` 被调（Step 10 F-R5-8 补直接断言）；T9 ② 拒单链 audit 落 `rejected` |
| I6 | kill 激活时 `adapter.submit` 调用数 == 0 | T6 ⑥ 打桩计数 | ✅ T6 ⑥ `gate.gate_kill(GLOBAL)` 后 `transport.sent == []` |
| I7 | `live/*` 不 import `filter`/`services`/pandas/numpy | `grep -rn "import pandas\|import numpy\|from filter\|from services" live/` 零命中 | ✅ 零命中 |
| I8 | 账本单写者：第二实例 `SqliteLedgerStore(same path)` 抛错 | T4 ⑤ | ✅ T4 ⑤ 第二实例抛 `OSError`（`O_CREAT\|O_EXCL`） |
| I9 | `UNKNOWN` 不被回报猜测推出；只由 `query_orders`/`confirm` 收敛（drain 帧 `from_query=False` → `ignored_transition`，F-I16） | T2 + T6 | ✅ T2 ⑪ `UNKNOWN→0` 合法；gateway `_apply_order_report` 对 `UNKNOWN` + `from_query=False` 早退（读码） |
| I10 | 账本 append-only；`replay(entries) == snapshot()`（RIGHTS_ISSUE 不在等价范围，F-I17④） | T3 ⑭ | ✅ T3 ⑭ 送转+拆股后 `Ledger.replay` 与 `snapshot` 的 cash/quantity/avg_cost 一致 |
| I11 | 时间一律外部注入（`ts` 参数 / `clock`）；纯模块零系统时钟 | grep + 单测显式传 `ts` | ✅ 纯模块 grep 零命中；gateway 全入口显式 `ts`，`clock` 仅在 `start/pending_unconfirmed` 注入 |
| I12 | 审计只用 P-052 的 8 个 `EventType.AUDIT_*`，不新增常量 | `grep EventType.` 白名单比对 `core/event_log.py` L60-67 | ✅ gateway/terminal 仅用 `AUDIT_ORDER`/`AUDIT_FILL`/`AUDIT_CANCEL`/`AUDIT_RECONCILE`，无新增常量 |

---

## 5. D 组：设计决策 D1-D16（16 项）

| ID | 决策 | 落实点 | 实测 |
|----|------|--------|------|
| D1 | 语义层 8 模块 + 适配器 4 骨架，`live → core` 单向 | M1-M12 + I7 grep | ✅ 8+5 文件落盘；I7 零命中 |
| D2 | 能力门在 `start()` 与每次 `submit()` 双检；限额三方 `min` | M1 `require_capability`/`resolve_limits` + T1 ④⑤⑥ | ✅ `start()` 校验 `query_*`；`submit()` 步③；T1 ④⑤⑥ 绿 |
| D3 | `client_order_id` 确定性 sha1-16，只在首提生成一次 | M2 `make_client_order_id` + M8 步⑤ + T2 ①② | ✅ 网关仅在 `coid == ""` 时生成；T2 ①②③ 绿 |
| D4 | FIX 9 值状态机 + 终态不可逆 + `filled_quantity` 单调 | M2 `LEGAL` + T2 | ✅ T2 ⑤-⑭ 全绿 |
| D5 | 双分录 + 加权成本 + `entry_id` 幂等 | M3 + T3 | ✅ T3 ①②③④⑥⑦ 绿 |
| D6 | SQLite WAL + `synchronous=FULL` + 单连接 + `.lock` + outbox 同库 | M4 + T4 | ✅ T4 ①②④⑤⑥ 绿 |
| D7 | 对账三级 + `explained` 判 MISSED + parity 配置化 | M5 + T5 | ✅ T5 12/12 绿 |
| D8 | 恢复顺序 trades→orders→positions；`UNKNOWN` 只由查询/人工收敛 | M8 `start()` 步序 + T6 ① | ✅ T6 ① 调用序 `query_trades < query_orders < query_positions` |
| D9 | 适配器 ABC 7 方法 + 3 类异常分类 | M1 + M9-M12 | ✅ ABC 7 抽象方法；3 异常类齐备 |
| D10 | `submit()` 必经 `pre_trade_check`；回报回写 `on_order_result`；`cancel_all` 走 bridge | M8 + T6 ⑤⑦ + I5 | ✅ T6 ⑤⑦ + T9 ② 绿 |
| D11 | 流控双层（本地三桶 `RateLedger` + 通道声明），查询桶必须 record | M8 `_throttle_query` + T6 ④ | ✅ T6 ④ 同秒第二次查询抛 `ChannelUnavailable` |
| D12 | 日历/时段注入（synthetic）+ 公司行为先归因 | M6/M7 + T7/T8 | ✅ T7/T8 各 8/8 绿 |
| D13 | Terminal CSV 清单 + `audit.order` 双写 + `import_fills` | M12 + T9 ③ | ✅ T9 ③ CSV 10 列 + `ingest_fills` 入账 |
| D14 | 零新依赖；FakeTransport/录制帧；不接真实网络 | C6 + M9 + M10 未注入即 `ChannelUnavailable` | ✅ C6 空；`CtpChannelAdapter._require()` 未注入抛 `ChannelUnavailable` |
| D15 | 账本仅 cash 层级：`start()` 校验 `account_level=="cash"`，cash 拒 `SELL_SHORT`/`BUY_TO_COVER` | M8 `start()` + 步③ + T9 | ✅ `start()` 校验 + `submit()` 步③ 拒空头（读码）；T9 全链 cash 绿 |
| D16 | outbox 本批只写不读（消费归 P-054） | M4 `append_outbox` + T4 ④（无 relay） | ✅ 仅 `append_outbox`/`pending_outbox`/`mark_sent`，无 relay；T4 ④ 回滚绿 |

---

## 6. F 组：Step 6 复审 17 项回执核对（17 项）

| ID | 复审发现（P 级） | 核对动作 | 实测 |
|----|------------------|----------|------|
| F1 | F-I1（P1）`record` 遮蔽 | `grep -n "^ *record = " live/gateway.py` 零命中；`rec =` 五处（submit/cancel/cancel_all/confirm/_apply_order_report） | ✅ `record =` 0 处；`rec =` 5 处 |
| F2 | F-I2（P1）`OrderRequest` 缺定义 / 错误 import | `grep -n "from live.channel import" live/orders.py` 零命中；`class OrderRequest` 在 orders.py | ✅ 0 命中；`OrderRequest` 定义于 `live/orders.py` |
| F3 | F-I3（P1）现金符号统一 | 守恒断言 T3 ⑤⑬⑭ 通过；`cash_adjust` 形参名为 `delta` 且 `amount=-delta` | ✅ T3 ⑤⑬⑭ 绿；`amount=-delta` |
| F4 | F-I4（P1）循环 import | 四文件互相 import 冒烟（`python -c "import live.gateway"`）；corporate_actions 运行期仅 `BreakLevel` | ✅ `import-ok`（gateway/ledger_store/4 adapters）；corporate_actions 仅 `BreakLevel` |
| F5 | F-I5（P1）transition 同态 ack 崩溃 + 缺自环 | T2 含 `A→A` 带 broker 回填、PF→PF、PC→PC 三例 | ✅ T2 ⑥⑨⑩ 覆盖三例 |
| F6 | F-I6（P2）Terminal 被能力门阻塞 | T9 ③ 全链通过；`submit` 步③ need 按 `autonomous` 分支 | ✅ T9 ③ 绿；非 autonomous 仅需 `client_order_id` |
| F7 | F-I7（P2）CTP 52 映射 / 非 0 拒单 / -2·-3 语义 | `_CTP_STATUS["52"] is PENDING_CANCEL`；三条错误码分支单测或读码 | ✅ `"52": PENDING_CANCEL`；`-2/-3` → `ChannelUnavailable`，其余非 0 → `ChannelRejected` |
| F8 | F-I8（P2）查询桶死设 | T6 ④ 第二次查询被限 | ✅ T6 ④ 绿 |
| F9 | F-I9（P2）成功回报不重置拒单计数 | 读码两条 `on_order_result(rejected=False, ...)`（submit ack / 非拒单迁移） | ✅ 两处：submit 成功 ack、非拒单迁移 else 分支 |
| F10 | F-I10（P2）ledger↔store 未接线 | `attach_store` 在 `start()`；T9 ⑤ 重启恢复 | ✅ `start()` 内 `attach_store`；T9 ⑤ 绿 |
| F11 | F-I11（P2）import 缺漏 | `grep` 五个符号在 gateway import 块；`python -c "import live.gateway"` | ✅ `CapabilityError`/`ChannelUnavailable`/`replace`/`asdict`/`Iterable`/`LedgerEntry`/`BreakLevel` 全在；import-ok |
| F12 | F-I12（P2）Terminal 回填无入口 | `ingest_fills` 存在且 T9 ③ 入账 2 条 entry | ✅ `ingest_fills` 存在；T9 ③ 入账 fill entry（fee=0 时 1 条） |
| F13 | F-I13（P2）`explained` 过宽 | `grep "explained = frozenset()" live/gateway.py` 命中 | ✅ `explained: frozenset[str] = frozenset()`（注解形态，语义一致） |
| F14 | F-I14（P3）`__dict__` → `asdict` | `grep "__dict__" live/gateway.py` 零命中 | ✅ 0 命中；使用 `asdict(report)` |
| F15 | F-I15（P3）死赋值 / `ts` 参数 | `grep "_reconciled_at_start"` 零命中；`apply_corporate_action(..., *, ts)` 签名 | ✅ 0 命中；`apply_corporate_action(self, action, *, ts)` |
| F16 | F-I16（P3）UNKNOWN drain 口径 | `from_query` 形参与 UNKNOWN 早退分支；T2/T6 断言 | ✅ `_apply_order_report(..., from_query=False)` + UNKNOWN 早退；T2/T6 绿 |
| F17 | F-I17（P3）注记组四条 | 读码：`resolve_limits` 注记 / mock ack ts 注记 / `_audit` payload 无 `source=` / replay docstring 限 RIGHTS_ISSUE | ✅ 四处注记/口径均在；`_audit` 的 `source` 只在 `event_log.append(..., source=)` |

---

## 7. 出口判定

- **Step 9 判据**：M13 + T10 + C7 + I12 + D16 + F17 = **75 项全部 ✅**（`[待 Step 9]` 清零）；
- **任一 ❌** → 记录证据并回 Step 5/6（禁止补丁式修复）；
- **实测读数**回填 §8，再进 Step 8 一致性检查（四文档交叉核对）。
- **Step 10 判据**：75 项 ✅ 复跑通过 + ADD 异构复审（Phase 0 判档 **Tier A** → 三路 subagent 并行审计 → Phase 3.5 源码级验证）产出 [REVIEW_p053_step10](REVIEW_p053_step10_acceptance.md)：22 发现 → **7 代码/测试修复 + 4 文档订正 + 6 登记**（U-P053-15..20），**0 P1 残留**；修复后门禁全量重放（C1-C7）零回归（§10）。

## 8. 实测读数（Step 9 回填）

| 指标 | 基线 @`e9e945f` | 目标 | 实测 |
|------|------------------|------|------|
| pytest 全量 | 1214 | 1300 | ✅ **1300 passed** |
| `-k golden` | 22 | 22（零重录） | ✅ **22 passed** |
| mypy | 128 files / 0 | 141 files / 0 | ✅ **141 files / 0** |
| black `--check .` | 261 | 283 unchanged | ✅ **283 unchanged** |
| `tests/*.py` | 132 | 141 | ✅ **141** |
| `core/*.py` | 51 | 51 | ✅ **51** |
| `live/*.py` | 3 | 16 | ✅ **16** |

## 9. 备注

- **落地顺序**按 IMPL §6 三组（G1 语义层 32 例 → G2 存储+对账 32 例 → G3 适配器+网关 22 例），每组红绿后再进下一组；R-1 分三次提交。
- **Step 6 残留修正（Step 7 顺手）**：DESIGN §6 I4 行原仍为 F-D6 分组式，已与 §3.3 统一式（`cash+reserved == initial_cash − Σ entry.amount − Σ entry.fee`）对齐；本 CHECKLIST §4 I4 取统一式。
- **本批不做**：真实网络连通（U-P053-1）、outbox 消费（D16 → P-054）、margin/short 账本（D15 → P-056）、对账编排（U-P053-13 → P-054）、首接已有持仓自动导入（U-P053-14，预留 `seed_snapshot`）。
- **F 组与 M/I 组的关系**：F 组是 Step 6 发现的**定点核对**（grep / 单测点），不重复 M 组的整文件 DoD；Step 8 一致性检查时按 F→M→I 的映射交叉核对。
- **Step 9 实施偏差记录**：① `make_client_order_id` 实际长度 `co_`+16hex=**19**，IMPL §4「18」按笔误处理；② `start()` 恢复段第二个循环变量由 `report` 改名 `order_report`（避免 mypy 同作用域类型冲突，语义不变）；③ `MockChannelAdapter.drain_reports` 局部 `out` 显式标注 `list[OrderReport | FillReport]`（mypy）。三处均不改变对外语义。

## 10. Step 10 异构复审记录（RULE-5，详见 [REVIEW_p053_step10](REVIEW_p053_step10_acceptance.md)）

> 复审基座 GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash）· ADD Phase 0 判档 **Tier A**（5/5）→ 三路 subagent 并行审计 → 主线 Phase 3.5 源码级验证 → 修复 + 门禁全量重放。

| 处置 | 发现 | 回执位置 |
|------|------|----------|
| **代码/测试修复（7）** | F-R5-1（P1，CTP capability + coid 映射）· F-R5-2（start() 回放环死路径）· F-R5-4（委托/撤单桶接 resolve_limits）· F-R5-5（CTP `_refs` 登记+反查）· F-R5-7（T2 补 A→2 直接断言）· F-R5-8（T6 补 `pre_trade_check` spy）· F-R5-9（`should_degrade` 尾部连续语义） | M10 / T2 / T6 / I5 实测列已更新；代码落点见 REVIEW §5 |
| **文档订正（4）** | A-3（M1 `ChannelCapability` 16 字段）· A-4（M3 运行期 import 口径）· B-6（M11 语义占位措辞）· B-8（M5 8 函数 + M6 5 函数计数） | M1 / M3 / M5 / M6 / M11 实测列已更新 |
| **登记（6 项，合并 11 项未修）** | U-P053-15 死代码 `_ceil_positive`/`_SOURCE` · U-P053-16 `Ledger.resume` 一次性迭代器 · U-P053-17 outbox 同事务公开 API 缺口（P-054 前置）· U-P053-18 CTP 启动期同秒 3 查询限流（P-054 前置）· U-P053-19 `attribute_break` 现金分支维度错位不可达 · U-P053-20 测试覆盖缺口合并项（A-7 + C-P3-1/2/4/5） | REVIEW §6 四元块 |
| **编号双轨** | F-R5-3 = B-3 → U-P053-18；F-R5-6 = B-7 → U-P053-19（登记项保留 F-R5 映射） | — |

**复审后门禁重放**：pytest **1300 passed（138.34s）** / golden **22** / mypy **141 files 0** / black **283 unchanged** / 计数 141/51/16 全绿；golden、零改动 7 文件、依赖清单 git status 空。**0 P1 残留，Step 10 出口 PASS**。
