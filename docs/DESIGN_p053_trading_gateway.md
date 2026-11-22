# DESIGN：P-053 交易通道网关（能力门 + 订单语义 + 账本 + 对账 + 日历/公司行为 + 四适配器骨架）

> **批次**: P-053 · **Step 3 设计** · 日期 2026-11-21 · **判档 P2**
> **上游**: [RESEARCH_p053](RESEARCH_p053_trading_gateway.md)（§6 推荐方案 A / §12 三项补充调研 / G1-G11 / U-P053-1..11）；[REVIEW_p053_step2](REVIEW_p053_step2_research.md)（0 P1 / 3 P2 / 3 P3 全修复）
> **总纲**: F6 L212-221（L270 行）；L244 parity 校准；L419 F-R9-P2 时段状态机；L421 Q12 两模块；O-R2 L487 xtquant 取证
> **口径**: 用户 2026-11-21「按照建议口径执行 Step 3」→ U-P053-1/2/4 采纳 §12 建议；其余 U 项本文件定案（§0.2）
> **零代码/零门禁变更**：本批交付设计文档；Step 5 才落码

---

## 0. 裁决记录（Step 3 定案）

### 0.1 用户已裁决（2026-11-21，「按建议口径」）

| 项 | 定案 | 依据 |
|----|------|------|
| **U-P053-1** | **语义层先行**；首个真实协议连通 = **CTP（SimNow 第二套环境，零审批）**；券商机构 API（XTP/OES）列第二目标（前置=专业投资者资质 + 测试账号审核）；**本批不接真实网络** | §12.1 + §0.5 |
| **U-P053-2** | 账本流水 **SQLite**（stdlib `sqlite3`，WAL，单写者进程，与 outbox 同库）；JSON 原子写只保留 P-052 安全状态（`live/safety_store.py` 不改） | §12.2 + D6 |
| **U-P053-4** | 「已报未确认」= **只查询 + 宽限期 + 人工确认**，不自动重发；自动重发需四条件（柜台确认 `client_order_id` 不存在 + 超宽限期 + 显式开关 + 审计），**不进本批** | §12.3 + D8 |

### 0.2 Step 3 工程口径定案（本文件新增）

| 项 | 定案 | 落点 |
|----|------|------|
| U-P053-3 | 状态机值域 = **FIX 9 值**（A/0/1/2/4/8/C/6/?）：`PENDING_NEW`/`NEW`/`PARTIALLY_FILLED`/`FILLED`/`CANCELED`/`REJECTED`/`EXPIRED`/`PENDING_CANCEL`/`UNKNOWN`；**终态不可逆**、`filled_quantity` 单调不减 | D4 / §3.2 |
| U-P053-5 | parity/对账阈值**配置化**；默认取 Q10 数值；**立项期按账户规模校准并写入验收**（总纲 L244 + Q10 L374）→ `ParityConfig` 全字段默认 + 验收用例引用 | D7 / §5 |
| U-P053-6 | 单写者 = **进程内单例 + SQLite 单连接 + 账本目录 `.lock` 文件**（`O_CREAT|O_EXCL`；已存在则拒绝启动） | D6 / §3.4 |
| U-P053-7 | Terminal 半自动留痕 = **CSV 订单清单**（稳定列序）+ **每单 `audit.order` 双写**；回填 CSV 用 `import_fills()` 入账并记 `audit.fill` | D13 / §3.9 |
| U-P053-8 | **零新依赖**：仅 stdlib（`sqlite3`/`hashlib`/`csv`/`zoneinfo`/`enum`/`dataclasses`）；不引入 pandas/numpy 到 `live/` | D14 / I7 |
| U-P053-9 | `TerminalChannelAdapter` **本批实现最小可用**（清单生成 + 回填导入 + 能力声明），不做 GUI/轮询 | §3.9 |
| U-P053-10 | 与 P-056 边界：本批只做**通道语义**（委托/成交/撤单/查询/对账），不碰期货月差与保证金算法 | I7 |
| U-P053-11 | `corporate_actions` / `session_calendar` **synthetic 先行**（Q12 推荐 7）：本批用注入的交易日历与事件表；真实数据源（AKShare 兜底 / 柜台源）**后置**，接口不变 | D12 / §3.6 |

### 0.3 未改动的既有契约（只引用，不改写）

- P-052：`SafetyGate.pre_trade_check(intent, ctx, *, account_id, strategy_id, ts, time_source="local")` → `SafetyDecision`；`on_order_result(*, rejected, ts)`；`cancel_all(bridge: LiveTradingBridge, *, ts) -> int`（D-G7）；`EventType` 8 个 `audit.*` 常量。
- `core/live_bridge.py`：`LiveTradingBridge` ABC 四方法；`LiveOrder` 五值 `status` 字符串。
- `OrderIntent`：字段仍 `asset/asset_type/target_quantity/current_quantity/urgency`（**不新增字段**；通道侧用新 `OrderRequest`）。

---

## 1. 目标与非目标

**做**（本批验收面）：

1. **通道能力门**：`ChannelCapability` 声明式契约 + `require_capability()` + 生效限额取三方最小；
2. **订单语义层**：`client_order_id` 确定性生成、FIX 对齐状态机与非法迁移拒绝、订单/成交记录契约；
3. **账本**：双分录流水 + 加权成本 + 幂等入账（`entry_id` 唯一）+ SQLite 持久化 + outbox 同库同事务；
4. **对账**：持仓/现金/成交三类比对 + dust/missed/unresolved 三级 + parity（Q10）评估与连续降级判定；
5. **交易日历与时段状态机**（G11）+ **公司行为事件表与先归因**（G11）；
6. **四适配器骨架**：`mock`（FakeTransport 可注入帧）/ `ctp`（协议映射，无真实网络）/ `broker_api`（语义占位）/ `terminal`（半自动清单 + 回填）；
7. **与 P-052 衔接**：`submit()` 除 `channel_halted`/`session_closed` 前置快败外必经 `pre_trade_check`（I5）、回报回写 `on_order_result`、kill 激活零调用、`cancel_all` 复用 bridge 语义；
8. 四文档 + 台账。

**不做**（外置）：

- 真实通道连通/联调（Semantics-first；CTP 连通演练单列，需提前注册 SimNow —— N-2）；
- 券商机构 API 准入申请（外部审核，N-3）；
- 行情通道（N-6）、期货月差/保证金（P-056）、margin/short 账本层级（P-056；本批 `start()` 强制 cash，D15）、REST/WS 服务层与密钥管理（P-054）、微服务化（P-055）；
- 自动重发（U-P053-4 四条件，本批不实现）；
- 新的 `EventType`（复用 P-052 的 8 个审计常量，I12）。

---

## 2. 模块拓扑与依赖

```
live/
  __init__.py                    （既有，仅 docstring）
  safety_store.py                （既有，P-052：JSON 原子写，不改）
  safety_gate.py                 （既有，P-052：闸门）
  channel.py            新增    能力门 / 通道状态 / 适配器 ABC / 限额合成
  orders.py             新增    订单号 / 状态机 / OrderRecord / FillRecord / 迁移
  ledger.py             新增    双分录账本 / 加权成本 / 幂等入账 / 快照与重放
  ledger_store.py       新增    LedgerStore Protocol + SqliteLedgerStore（WAL/单写者/outbox）
  reconcile.py          新增    三级对账 / ParityConfig + evaluate_parity / 降级判定
  session_calendar.py   新增    交易日历 / 时段状态机 / 可提交判定
  corporate_actions.py  新增    公司行为事件表 / 仓位调整 / 对账先归因
  gateway.py            新增    TradingGateway：submit/poll/cancel/cancel_all/reconcile/start/shutdown
  adapters/
    __init__.py         新增    docstring only
    mock.py             新增    FakeTransport + MockChannelAdapter（注入帧、可编排拒单/断线）
    ctp.py              新增    CtpChannelAdapter（48-55 → OrderState；OrderRef 映射；查询流控）
    broker_api.py       新增    BrokerApiChannelAdapter（能力声明 + 未配置即 ChannelUnavailable）
    terminal.py         新增    TerminalChannelAdapter（CSV 清单 + import_fills 回填）

依赖方向（硬约束，I7）：
  live.channel      → （stdlib + core.execution_policy.OrderIntent 仅类型；OrderRequest/OrderState
                      经 TYPE_CHECKING 引自 live.orders——运行期零反向依赖，C-1/F-I4）
  live.orders       → stdlib（OrderRequest/OrderState 本文件定义；Step 6 F-I2 删除 channel 运行期 import）
  live.ledger       → live.orders, live.corporate_actions
  live.ledger_store → live.orders, live.ledger（Protocol 先于实现）
  live.corporate_actions → live.reconcile（BreakLevel 运行期；PositionLot/Break 仅 TYPE_CHECKING）
  live.reconcile    → 零内部运行期依赖（LedgerSnapshot 仅 TYPE_CHECKING——Step 6 F-I4 解环）
  live.gateway      → live.channel, orders, ledger, ledger_store, reconcile, session_calendar,
                      corporate_actions, safety_gate（P-052）, core.event_log, core.execution_policy,
                      core.compliance（RateLimitConfig）
  live.adapters.*   → live.channel, live.orders（ledger 仅 mock 可选）
禁止：live/* 不得 import filter/*、services/*（不存在）、pandas/numpy；不得 import core.engine*。
```

**新文件计数**：13（8 核心 + 5 adapters）→ `live/*.py` **3 → 16**。

---

## 3. 数据契约

### 3.1 `live/channel.py` — 能力门与适配器 ABC

```python
class ChannelState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"     # 可撤单/可查询，禁止新开
    HALTED = "halted"         # 全停（对账 unresolved / 人工）

@dataclass(frozen=True)
class ChannelCapability:
    channel_id: str
    venue: str                      # "ctp" | "broker_api" | "terminal" | "mock"
    account_level: str              # "cash" | "margin" | "short"
    products: tuple[str, ...]       # ("future","option") / ("stock",)
    supports_client_order_id: bool
    supports_cancel: bool
    supports_query_orders: bool
    supports_query_trades: bool
    supports_query_positions: bool
    autonomous: bool                # False = 半自动（terminal）
    report_registered: bool         # 程序化交易报备状态（capability 门的一项）
    max_submit_per_sec: float
    max_submit_per_day: int
    max_cancel_per_sec: float
    max_query_per_sec: float
    notes: str = ""

class CapabilityError(RuntimeError): ...        # 能力不满足（含缺失项清单）
class ChannelUnavailable(RuntimeError): ...     # 未配置/未连通
class ChannelRejected(RuntimeError):            # 柜台明确拒单
    def __init__(self, code: str, reason: str) -> None: ...

def require_capability(cap: ChannelCapability, *, need: frozenset[str]) -> None
def resolve_limits(cap, *, internal_per_sec: float, internal_per_day: int,
                   regulator_per_sec: float = 300.0,
                   regulator_per_day: int = 20000) -> ChannelLimits   # 取三方最小

@dataclass(frozen=True)
class ChannelLimits:
    submit_per_sec: float; submit_per_day: int; cancel_per_sec: float; query_per_sec: float

@dataclass(frozen=True)
class SubmitAck:                     # adapter.submit() 同步回执（F-D1）
    client_order_id: str
    broker_order_id: str
    state: OrderState                # 接受即 PENDING_NEW（FIX Pending-New 对齐）
    ts: float

@dataclass(frozen=True)
class OrderReport:                   # query_orders / drain_reports 的委托回报
    client_order_id: str; broker_order_id: str; state: OrderState
    filled_quantity: float; avg_price: float; ts: float
    code: str = ""; reason: str = ""     # 柜台错误码/文案（REJECTED 时必填）

@dataclass(frozen=True)
class FillReport:                    # query_trades / drain_reports 的成交回报（入账前转 FillRecord）
    fill_key: str; client_order_id: str; asset: str; side: str
    quantity: float; price: float; fee: float; ts: float

@dataclass(frozen=True)
class PositionReport:                # query_positions 的持仓回报
    asset: str; quantity: float
    available: float | None = None   # 可用数量（期货仓差）；None = 柜台不下发

class ChannelAdapter(ABC):
    capability: ChannelCapability
    state: ChannelState
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def submit(self, request: OrderRequest) -> SubmitAck: ...        # 同步回执，见上 SubmitAck（F-D1）
    def cancel(self, client_order_id: str) -> None: ...
    def query_orders(self, *, day: str) -> list[OrderReport]: ...
    def query_trades(self, *, day: str) -> list[FillReport]: ...
    def query_positions(self) -> list[PositionReport]: ...
    def drain_reports(self) -> list[OrderReport | FillReport]: ...   # 非阻塞，清空队列
```

- `need` 合法键：`client_order_id` / `cancel` / `query_orders` / `query_trades` / `query_positions` / `autonomous` / `report_registered` / 品种名。
- 缺项时抛 `CapabilityError("missing: cancel, report_registered")`——**门在 `Gateway.start()` 与每次 `submit()` 各校验一次**（防运行期能力漂移）。
- 回报类型（`SubmitAck`/`OrderReport`/`FillReport`/`PositionReport`）定义在本文件（F-D1）；`OrderState` 从 `live.orders` 经 `TYPE_CHECKING` 引用——仅类型注解，运行期不产生反向依赖（§2 依赖边不变）。

### 3.2 `live/orders.py` — 订单号、状态机、记录

```python
class OrderState(str, Enum):
    PENDING_NEW = "A"; NEW = "0"; PARTIALLY_FILLED = "1"; FILLED = "2"
    CANCELED = "4"; REJECTED = "8"; EXPIRED = "C"; PENDING_CANCEL = "6"; UNKNOWN = "?"

TERMINAL_STATES = frozenset({FILLED, CANCELED, REJECTED, EXPIRED})
LEGAL: dict[OrderState, frozenset[OrderState]]   # 见下表

@dataclass(frozen=True)
class OrderRequest:
    client_order_id: str; asset: str; asset_type: str
    side: str                       # BUY/SELL/SELL_SHORT/BUY_TO_COVER
    quantity: float; price: float | None; order_type: str   # limit|market
    account_id: str; strategy_id: str; signal_ts: float; remark: str = ""

def make_client_order_id(*, strategy_id: str, account_id: str, asset: str, side: str,
                         quantity: float, price: float | None, signal_ts: float) -> str
    # "co_" + sha1(f"{strategy}|{account}|{asset}|{side}|{qty:.6f}|{price or 0:.6f}|{ts:.6f}")[:16]
    # 纯函数、同输入同输出；网关只在首次 submit 生成一次（D3）

@dataclass(frozen=True)
class OrderRecord:
    client_order_id: str; broker_order_id: str; asset: str; side: str
    quantity: float; filled_quantity: float; avg_price: float
    state: OrderState; created_ts: float; updated_ts: float
    reject_code: str = ""; reject_reason: str = ""
    @property
    def remaining_quantity(self) -> float: ...
    @property
    def is_terminal(self) -> bool: ...

@dataclass(frozen=True)
class FillRecord:
    fill_key: str          # 柜台 trade_id，无则 f"{client_order_id}:{seq}"
    client_order_id: str; asset: str; side: str
    quantity: float; price: float; fee: float; ts: float

class OrderTransitionError(RuntimeError): ...
def transition(record: OrderRecord, *, state: OrderState, ts: float,
               broker_order_id: str | None = None,
               filled_quantity: float | None = None,
               avg_price: float | None = None,
               reject_code: str = "", reject_reason: str = "") -> OrderRecord
def from_request(request: OrderRequest, *, ts: float) -> OrderRecord   # PENDING_NEW（F-D2：以 request 构造，不再冗余依赖 intent）
```

**合法迁移表（D4）**

| from \ to | NEW | PARTIALLY_FILLED | FILLED | PENDING_CANCEL | CANCELED | REJECTED | EXPIRED | UNKNOWN |
|---|---|---|---|---|---|---|---|---|
| PENDING_NEW(A) | ✅ | ✅ | ✅ | ⛔ | ⛔ | ✅ | ✅ | ✅ |
| NEW(0) | — | ✅ | ✅ | ✅ | ✅(未成交撤销直接终态) | ⛔ | ✅ | ✅ |
| PARTIALLY_FILLED(1) | ⛔ | ✅* | ✅ | ✅ | ✅ | ⛔ | ✅ | ✅ |
| PENDING_CANCEL(6) | ⛔ | ✅ | ✅ | ✅* | ✅ | ⛔ | ✅ | ✅ |
| UNKNOWN(?) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| 终态(2/4/8/C) | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |

附加约束：`filled_quantity` 单调不减、`≤ quantity`；终态后任何迁移 → `OrderTransitionError`；`UNKNOWN` **只能由查询回报**迁移出去（I9）。`✅*` = 同态带量自环（多次部成回报 / CTP 52 复合态重报，Step 6 F-I5：fq 递增合法推进；fq 相同则幂等——同态且 `filled_quantity is None` 返回原对象，携带新 `broker_order_id`（ack 回填）只补该字段）。

注（Step 4 F-D3）：`A→1/A→2` 允许 = **秒级成交路径**——FIX 单笔 ExecutionReport 可直达 `OrdStatus=Filled`（无已报帧）、CTP「全部成交」直返终态、迅投 48-55 部成可不出现已报态；真实柜台不保证经过 `NEW`。I9 不受影响：`UNKNOWN` 收敛仍只走查询/人工。

### 3.3 `live/ledger.py` — 双分录账本

```python
@dataclass(frozen=True)
class PositionLot:
    asset: str; quantity: float; avg_cost: float; realized_pnl: float = 0.0

@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str        # 幂等键：f"fill:{fill_key}" / f"fee:{fill_key}" / f"ca:{action_id}:{asset}"
    kind: str            # "fill" | "fee" | "corporate_action" | "cash_adjust"
    ts: float; asset: str; quantity: float; price: float; amount: float; fee: float; ref: str
    # amount = 有符号不含费成交额（fill：±q*p）；ca/cash_adjust：−现金变动（Step 6 F-I3 统一口径：
    # 任一 entry 的现金变动恒为 −amount）；fee 恒正单列 entry——I4 口径（F-D6 修订）

@dataclass(frozen=True)
class LedgerSnapshot:
    cash: float; reserved_cash: float
    positions: tuple[PositionLot, ...]; as_of: float
    @property
    def equity(self) -> float: ...   # cash + reserved + Σ(qty*avg_cost)（估值由调用方另算）

class LedgerError(RuntimeError): ...   # fail-closed：预留超现金 / 结算无预留（F-D4）

class Ledger:
    def __init__(self, store: LedgerStore | None = None, *, initial_cash: float = 0.0) -> None
    def reserve(self, *, ref: str, amount: float, ts: float) -> None
        # amount 超过可用现金 → LedgerError（fail-closed，F-D4）；成功则 cash → reserved
    def release(self, *, ref: str, ts: float) -> None
        # 撤单/拒单路径：该 ref 预留全额退还 cash（F-D4）
    def settle_reserve(self, *, ref: str, actual: float, ts: float) -> float
        # 买入成交结算（F-D4）：消耗该 ref 预留，cash -= actual，差额（预留−actual）
        # 退还 cash 并返回；无预留 → LedgerError
    def apply_fill(self, fill: FillRecord, *, ts: float | None = None) -> bool   # True=新增
    def apply_corporate_action(self, action: CorporateAction, *, ts: float) -> list[LedgerEntry]
    def cash_adjust(self, *, asset: str, delta: float, ref: str, ts: float) -> LedgerEntry
        # delta=现金变动（入金/费退/配股缴款），entry.amount=−delta（D-2/F-I3）；幂等键 cash_adjust:{ref}
    def snapshot(self) -> LedgerSnapshot
    def entries(self) -> list[LedgerEntry]
    @property
    def initial_cash(self) -> float
    def attach_store(self, store: LedgerStore) -> None            # F-I10：网关接线
    @classmethod
    def resume(cls, entries: Iterable[LedgerEntry], *, initial_cash: float) -> "Ledger"
        # D-7 崩溃恢复：replay 结果回填 _cash/_positions/_entries/_seen（防已持久化 fill 重放）
    @staticmethod
    def replay(entries: Iterable[LedgerEntry], *, initial_cash: float) -> LedgerSnapshot
        # avg_cost 反推对 STOCK_DIVIDEND/SPLIT 等价；RIGHTS_ISSUE 不在 replay 等价范围（F-I17④）
```

**记账规则（D5）**

| 事件 | 持仓 | 现金 | 备注 |
|---|---|---|---|
| 买入成交 q@p, fee f | `qty += q`；`avg_cost = (qty_old*avg+q*p)/(qty_old+q)` | 经 `settle_reserve(ref=coid, actual=q*p+f)`：`cash -= actual`、预留差额退还；无预留（回填/人工）→ `cash -= q*p + f`；现金不足 → `LedgerError`（F-D4） | `entry_id=fill:{fill_key}`；fee 单独 entry |
| 卖出成交 q@p, fee f | `qty -= q`；`realized_pnl += (p-avg_cost)*q`；qty→0 时 `avg_cost=0` | `cash += q*p - f` | 同上 |
| 现金分红 d/股 | 不变 | `cash += d*qty` | `ca:{action_id}`；entry.amount=−d*qty（统一口径） |
| 显式现金调整（入金/费退/配股缴款） | 不变 | `cash += delta` | `cash_adjust:{ref}`；entry.amount=−delta（D-2/F-I3） |
| 送转/拆股 r | `qty *= (1+r)`；`avg_cost /= (1+r)` | 不变 | 幂等键同上 |
| 配股（先登记后缴款） | 本批只做「数量与成本调整」记录 | 现金变动仅由显式 `cash_adjust` 触发 | 不为配股自动扣款（U-P053-12） |

**不变式（F-D6 修订 → Step 6 F-I3 统一口径）**：`cash + reserved == initial_cash − Σ entry.amount − Σ entry.fee`（I4，误差 <1e-6，全 kind 通用：fill.amount=有符号 q*p、ca/cash_adjust.amount=−现金变动、fee 恒正单列 entry——任一 entry 的现金变动恒为 −amount；与原买/卖分组式代数等价，推导见 [REVIEW_p053_step6](REVIEW_p053_step6_impl.md) §4-3）；重复 `entry_id` 直接丢弃不改状态（I3）。

### 3.4 `live/ledger_store.py` — SQLite 仓储

```python
class LedgerStore(Protocol):
    def append_entry(self, entry: LedgerEntry) -> bool: ...          # False = entry_id 已存在
    def entries(self) -> list[LedgerEntry]: ...
    def upsert_order(self, record: OrderRecord) -> None: ...
    def load_orders(self) -> list[OrderRecord]: ...
    def append_outbox(self, event_id: str, event_type: str, payload: str, ts: float) -> None: ...
    def pending_outbox(self) -> list[tuple[str, str, str, float]]: ...
    def mark_sent(self, event_id: str) -> None: ...
    def transaction(self): ...        # contextmanager：BEGIN IMMEDIATE
    def close(self) -> None: ...

class SqliteLedgerStore:
    def __init__(self, path: str | Path) -> None   # 目录不存在则建；启动即抢 .lock
```

**建表（`_SCHEMA`，`executescript` 幂等）**

```sql
CREATE TABLE IF NOT EXISTS ledger_entry (
  entry_id TEXT PRIMARY KEY, kind TEXT NOT NULL, ts REAL NOT NULL, asset TEXT NOT NULL,
  quantity REAL NOT NULL, price REAL NOT NULL, amount REAL NOT NULL, fee REAL NOT NULL,
  ref TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_entry_ref ON ledger_entry(ref);
CREATE TABLE IF NOT EXISTS order_record (
  client_order_id TEXT PRIMARY KEY, broker_order_id TEXT NOT NULL, state TEXT NOT NULL,
  payload TEXT NOT NULL, updated_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (
  event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, payload TEXT NOT NULL,
  created_ts REAL NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
```

**连接参数（D6）**：`journal_mode=WAL`、`synchronous=FULL`、`foreign_keys=ON`、`isolation_level=None`（显式 `BEGIN IMMEDIATE`）、`check_same_thread=True`（单写者）、`timeout=5.0`。**`.lock`**：`os.open(lock_path, O_CREAT|O_EXCL)` 成功后保留 fd；已存在 → `RuntimeError("ledger already open")`。
**JSON 列**：`order_record.payload` 为 `dataclasses.asdict(record)` 的 `json.dumps(..., sort_keys=True)`；state 单列冗余便于查询与不变量检查。
**账本与 outbox 同库同事务**：`apply_fill` 写 entry + 写 outbox 在一个 `transaction()` 内（N-4）。
**outbox 消费端（F-D7/D16）**：本批**只写不读**——`pending_outbox()`/`mark_sent()` 供 P-054 服务层（送达/编排）消费，Step 5 不实现投递循环；PRE_OPEN 预埋不进本批（见 §3.6）。

### 3.5 `live/reconcile.py` — 三级对账 + parity

```python
class BreakLevel(str, Enum): OK = "ok"; DUST = "dust"; MISSED = "missed"; UNRESOLVED = "unresolved"

@dataclass(frozen=True)
class ReconcileConfig:
    dust_pct: float = 0.001              # 0.1%
    dust_abs_quantity: float = 100.0     # 股/手
    cash_dust_pct_nav: float = 0.0001    # 0.01% NAV
    cash_dust_abs: float = 1.0

@dataclass(frozen=True)
class ParityConfig:                      # Q10 默认值 + 立项期校准（总纲 L244）
    cash_pct_nav: float = 0.0001
    weight_l1: float = 1e-4
    slippage_bps_liquid: float = 10.0
    slippage_bps_illiquid: float = 30.0
    fill_rate_min: float = 0.95
    degrade_days: int = 2

@dataclass(frozen=True)
class Break:
    kind: str        # position | cash | missing_fill | extra_fill
    asset: str; local: float; remote: float; delta: float
    level: BreakLevel; note: str = ""

@dataclass(frozen=True)
class ReconcileReport:
    as_of: float; breaks: tuple[Break, ...]; level: BreakLevel; checked: int

@dataclass(frozen=True)
class ParityReport:
    cash_delta_pct_nav: float; weight_l1: float; slippage_bps: float
    fill_rate: float; breaches: tuple[str, ...]

def classify_quantity(delta: float, remote: float, *, config: ReconcileConfig,
                      explained: bool) -> BreakLevel
def reconcile_positions(local: dict[str, float], remote: dict[str, float], *,
                        config: ReconcileConfig, nav: float = 0.0,
                        explained: frozenset[str] = frozenset()) -> ReconcileReport
def reconcile_cash(local: float, remote: float, *, config: ReconcileConfig, nav: float) -> ReconcileReport
def reconcile_fills(local_keys: set[str], remote_keys: set[str]) -> ReconcileReport
def overall_level(reports: Iterable[ReconcileReport]) -> BreakLevel
def evaluate_parity(paper: LedgerSnapshot, live: LedgerSnapshot, *, nav: float,
                    slippage_bps: float, fill_rate: float, liquid: bool,
                    config: ParityConfig) -> ParityReport
def should_degrade(reports: Sequence[tuple[str, ParityReport]], *, config: ParityConfig) -> bool
    # F-D8：(day, report) 按日升序；取尾部连续 breach 天数 ≥ degrade_days → True
```

**判级（D7）**：`delta==0` → OK；`|delta| ≤ max(dust_abs, dust_pct*|remote|)` → DUST；`explained`（该差异可由**已入账成交/公司行为**解释）→ MISSED；否则 **UNRESOLVED** → 网关置 `HALTED` + `audit.reconcile` + 告警（不自动平仓）。`overall_level` 取最严重。
成交对账判级附注（Step 4）：`reconcile_fills` 中 `missing_fill`（柜台有、本地缺）→ `MISSED`（可补录）；`extra_fill`（本地有、柜台无）→ `UNRESOLVED`（入账缺口，需人工）。

### 3.6 `live/session_calendar.py` — 日历与时段状态机（G11）

```python
class SessionPhase(str, Enum):
    PRE_OPEN = "pre_open"; CONTINUOUS = "continuous"; LUNCH = "lunch"
    CLOSE_AUCTION = "close_auction"; CLOSED = "closed"; HOLIDAY = "holiday"

@dataclass(frozen=True)
class DaySession:                      # 秒偏移（本地自然日 0 点起）
    morning: tuple[int, int] = (9*3600+30*60, 11*3600+30*60)
    afternoon: tuple[int, int] = (13*3600, 15*3600)
    close_auction: tuple[int, int] | None = (14*3600+57*60, 15*3600)   # 沪深收盘集合竞价 14:57-15:00（默认启用，F-D9）
    pre_open: tuple[int, int] = (9*3600+15*60, 9*3600+30*60)

@dataclass(frozen=True)
class Calendar:
    trading_days: frozenset[str]        # "YYYY-MM-DD"（synthetic 注入；真实源后置）
    session: DaySession = DaySession()
    tz: str = "Asia/Shanghai"

def local_day(ts: float, *, tz: str) -> str
def session_phase(ts: float, *, calendar: Calendar) -> SessionPhase
def is_trading_day(day: str, *, calendar: Calendar) -> bool
def next_trading_day(day: str, *, calendar: Calendar) -> str | None
def can_submit(phase: SessionPhase, *, order_type: str = "limit") -> bool   # F-D9：固定规则，不依赖 capability
```

**规则（F-D9/F-D10 修订）**：`can_submit` 为**固定规则**（`ChannelCapability` 无竞价字段，不依赖 capability）：`HOLIDAY`/`CLOSED`/`LUNCH`/`PRE_OPEN` → False；`CONTINUOUS` → True；`CLOSE_AUCTION` → 仅 `order_type=="limit"`（禁市价、允许限价）。本批**不实现** PRE_OPEN 预埋（无 `allow_pre_open` 参数；预埋随 P-054 服务层与 outbox 送达一并交付）。撤单在所有非 `HOLIDAY` 阶段允许。时区用 `zoneinfo.ZoneInfo`（stdlib），`ts` 一律外部注入（I11）。

### 3.7 `live/corporate_actions.py` — 公司行为与先归因（G11）

```python
class ActionType(str, Enum):
    CASH_DIVIDEND = "cash_dividend"; STOCK_DIVIDEND = "stock_dividend"
    SPLIT = "split"; RIGHTS_ISSUE = "rights_issue"

@dataclass(frozen=True)
class CorporateAction:
    action_id: str; asset: str; action_type: ActionType; ex_date: str
    cash_per_share: float = 0.0; share_ratio: float = 0.0; price: float = 0.0
    note: str = ""

def load_actions(rows: Iterable[dict[str, str]]) -> tuple[CorporateAction, ...]   # CSV 行 → 事件表
def actions_for(actions, *, asset: str, ex_date: str) -> tuple[CorporateAction, ...]
def adjust_position(lot: PositionLot, action: CorporateAction) -> tuple[PositionLot, float]
    # 返回（新持仓, 现金变动）；ratio 调整 avg_cost
def attribute_break(brk: Break, *, actions: tuple[CorporateAction, ...]) -> Break
    # 若 delta 可由 ex_date 当天事件精确解释 → level=MISSED 且 note 记 action_id
```

**顺序**：`reconcile_positions()` 前先跑 `attribute_break()`（Q12「先归因再判异常」）；事件表 synthetic（U-P053-11），真实源后置。

### 3.8 `live/gateway.py` — 与 P-052 衔接

```python
@dataclass(frozen=True)
class SubmitResult:
    accepted: bool; client_order_id: str; state: OrderState
    decision: SafetyDecision | None = None; reasons: tuple[str, ...] = ()

class TradingGateway:
    def __init__(self, *, adapter: ChannelAdapter, gate: SafetyGate, ledger: Ledger,
                 store: LedgerStore, event_log: IEventBus, *,
                 calendar: Calendar | None = None,
                 reconcile_config: ReconcileConfig | None = None,
                 parity_config: ParityConfig | None = None,
                 actions: tuple[CorporateAction, ...] = (),
                 rate_config: RateLimitConfig | None = None,
                 grace_seconds: float = 60.0, operator: str = "system",
                 clock: Callable[[], float] = time.time,
                 cost_buffer: float = 0.005) -> None    # D-1：买入预留缓冲（IMPL D-1 采纳）

    def start(self) -> None        # 先校验 capability.account_level=="cash"（D15；否则 CapabilityError，F-D5）
                                   # → connect → attach_store + 空账本时 Ledger.resume 重建（F-I10/D-7）
                                   # → autonomous 才 require {query_trades, query_orders}（F-I6）
                                   # → 查询桶限流后 query_trades → query_orders（from_query=True，F-I8/I16）
                                   # → load_orders → 对账 → unresolved 则 HALTED（半自动通道人工对账，F-I6）
    def submit(self, intent: OrderIntent, request: OrderRequest, ctx: GuardContext, *,
               account_id: str, strategy_id: str, ts: float) -> SubmitResult
               # F-D2：pre_trade_check 第一位置参数即 intent（safety_gate L111）；入参校验
               # fail-closed：request.asset/asset_type == intent.*、request.side == intent.action、
               # request.quantity == intent.abs_trade_quantity、request.account_id/strategy_id
               # 与 kwargs 一致——不符 ValueError，adapter.submit 零调用
    def poll(self, *, ts: float | None = None) -> list[LedgerEntry]
    def cancel(self, client_order_id: str, *, ts: float) -> bool
    def cancel_all(self, *, ts: float) -> int
    def reconcile(self, *, ts: float, nav: float = 0.0) -> ReconcileReport
    def pending_unconfirmed(self) -> list[OrderRecord]     # 供人工确认面板（P-054）
    def confirm(self, client_order_id: str, *, state: OrderState, ts: float) -> OrderRecord
    def ingest_fills(self, reports: Iterable[FillReport]) -> list[LedgerEntry]
                                   # F-I12/D-8：Terminal/人工回填入口（import_fills → apply_fill → audit.fill）
    def shutdown(self) -> None
```

**`submit()` 固定顺序（D10，I5/I6）**

1. `adapter.state is HALTED` → 拒（`channel_halted`），**不调 gate**；
2. `session_phase(ts)` 不满足 `can_submit(phase, order_type=request.order_type)` → 拒（`session_closed`，F-D10：本批无预埋）；
3. `require_capability(need = autonomous ? {client_order_id, cancel, query_orders} : {client_order_id})`（Step 6 F-I6：半自动通道仅要求幂等键）+ 流控桶（`resolve_limits` 三方最小；桶复用 P-052 `RateLedger`——submit/cancel 两桶 + **query 独立桶且必须 record**（F-I8：只 check 不 record 的账本恒放行），均先 check 后 record）；cash 层级拒 `SELL_SHORT`/`BUY_TO_COVER`（D15，F-D5）；
4. `gate.pre_trade_check(intent, ctx, account_id=..., strategy_id=..., ts=ts)`；`allowed is False` → 写 `audit.risk_decision`，**返回拒**，`adapter.submit` 零调用（I6：kill 激活时调用计数必须为 0）；
5. `coid = request.client_order_id or make_client_order_id(...)`（只生成一次，D3）；
6. 买入先 `ledger.reserve(ref=coid, amount=price*qty*(1+cost_buffer))`；
7. `adapter.submit(request)` → `ChannelRejected` 时 `release` + `gate.on_order_result(rejected=True, ts=ts)` + `audit.order`；`ChannelUnavailable`（含 CTP -2/-3 请求级流控，F-I7）时 `release` + `audit.order`、**不计拒单**；
8. 成功：`transition(PENDING_NEW，同态回填 broker_order_id，F-I5)` → `store.upsert_order` → `audit.order` + outbox（同事务）→ `gate.on_order_result(rejected=False)`（F-I9：重置连续拒单）。

**`poll()`**：`drain_reports()` → `OrderReport` 走 `transition()`（非法迁移：保留原状态，`audit.order` 记 `ignored_transition`——F-D13）；`FillReport` → `ledger.apply_fill()`（幂等）→ `audit.fill`；`REJECTED` → `gate.on_order_result(rejected=True)`，**其余迁移 → `on_order_result(rejected=False)`**（Step 6 F-I9：重置连续拒单）；**`UNKNOWN` 不迁出**——drain 帧对 `state==UNKNOWN` 记 `ignored_transition`（`from_query=False`，F-I16/I9），留给 `query_orders`/`confirm()` 收敛。

**`cancel_all()`**：若 `adapter` 暴露 `bridge`（`getattr(adapter,"bridge",None)` 非 None）→ 直接 `gate.cancel_all(bridge, ts=ts)`（复用 P-052 D-G7 语义与计数）；否则对本地非终态订单逐个 `adapter.cancel()` 并记 `audit.cancel`。

**宽限期（U-P053-4）**：`start()` 后仍未确认的订单进入 `pending_unconfirmed()`，超过 `grace_seconds` 只**告警 + 进人工面板**，绝不自动重发。

### 3.9 `live/adapters/*.py`

| 文件 | 内容 | 关键约束 |
|---|---|---|
| `__init__.py` | docstring only | 零 import |
| `mock.py` | `FakeTransport`（`scripts: list[Frame]`，`Frame(kind, payload, delay=0)`）+ `MockChannelAdapter`（可编排 ack/拒单/断线/乱序回报）；初始化时挂 `bridge: MockLiveBridge` 以复用 `gate.cancel_all` | 确定性：不 sleep、不使用随机；帧序列由测试注入 |
| `ctp.py` | `CtpTransport` Protocol（`send_order/cancel_order/req_qry_orders/req_qry_trades/req_qry_positions/subscribe`）+ `CtpChannelAdapter`：`48..55 → OrderState` 映射表（**52 部成待撤 → `PENDING_CANCEL`**，复合态注记，F-I7）、`client_order_id ↔ (FrontID, SessionID, OrderRef)` 双向字典、查询桶 1 笔/秒（网关侧独立 RateLedger record，F-I8）；`error_id` 非 0 → `ChannelRejected`，**`-2/-3`（请求级流控，未送达柜台）→ `ChannelUnavailable` 不计拒单**（Step 6 F-I7 修正） | 真实网络零调用（transport 未注入 → `ChannelUnavailable`）；重连后 `MaxOrderRef` 归零**只用查询重建**（D8） |
| `broker_api.py` | `BrokerApiChannelAdapter`：`capability(venue="broker_api", autonomous=True, supports_client_order_id=True)`；未注入 transport → 所有动作 `ChannelUnavailable("broker_api not configured")` | 语义占位，不做准入 |
| `terminal.py` | `TerminalChannelAdapter`：`capability(autonomous=False)`；`submit()` 追加一行到 CSV 清单（列序固定见下）+ `audit.order`；`import_fills(path)` 读人工回填 → `list[FillReport]`；`cancel/query_*` → `CapabilityError` | CSV 列：`ts,client_order_id,asset,side,quantity,price,order_type,strategy_id,account_id,remark`；UTF-8-SIG 便于 Excel |

---

## 4. 关键决策 D1-D16

| ID | 决策 | 理由 | 反例（被否方案） |
|----|------|------|------------------|
| D1 | 语义层 8 模块 + 适配器 4 骨架，`live → core` 单向 | 监管关闭外接后仍可验收；注入式测试 | 直接写 xtquant 网关（已不可用） |
| D2 | 能力门在 `start()` 与每次 `submit()` 双检；限额取内部/通道/监管**三方最小** | 防运行期能力漂移；监管红线优先 | 只启动时检一次 |
| D3 | `client_order_id` 确定性 sha1（16 hex）+ 允许显式覆盖；**只在首提生成一次** | 重试复用即幂等；可离线复算 | UUID 每次重试重生成（Alpaca/FIX 反例） |
| D4 | FIX 9 值状态机 + 终态不可逆 + `filled_quantity` 单调 | 与柜台/STEP 语义同源；防回退 | 自由字符串（现状 G3） |
| D5 | 双分录 + 加权成本 + `entry_id` 幂等 | 现金守恒可测；重放可复算 | 只记成交不记现金 |
| D6 | SQLite WAL + `synchronous=FULL` + 单连接 + `.lock` + outbox 同库 | 崩溃安全、零新依赖、可检索 | JSONL 追加（无唯一约束/事务） |
| D7 | 对账三级 + `explained` 判 MISSED + parity 配置化 | 噪声可分离；Q10 可校准 | 一刀切阈值 |
| D8 | 恢复顺序 trades→orders→positions；`UNKNOWN` 只由查询/人工收敛 | 对齐 IBKR / vnpy / STEP；禁盲目重发 | 宽限期自动重发（U-P053-4 否） |
| D9 | 适配器 ABC 7 方法 + 3 类异常分类 | 四通道同一语义；错误可判 | 每通道各写一套接口 |
| D10 | `submit()` 必经 `pre_trade_check`；回报回写 `on_order_result`；`cancel_all` 走 bridge | 不改 P-052 契约，I5/I6 可断言 | 网关自行放行 |
| D11 | 流控双层（本地 `RateLedger` 桶——`record/check_rate/day_key` 三桶 + 通道声明） | 与 P-052 内部 1/s、1000 笔/日一致；复用既有原语（F-D11） | 只在适配器内限速 |
| D12 | 日历/时段注入（synthetic）+ 公司行为先归因 | Q12/G11 验收；真实源后置不改接口 | 硬编码交易时间 |
| D13 | Terminal CSV 清单 + `audit.order` 双写 + `import_fills` | 半自动留痕可审计 | 只写日志无清单 |
| D14 | 零新依赖；FakeTransport/录制帧；不接真实网络 | U-P053-8；D4 口径 | 引入 pandas / 实连 SimNow |
| D15 | 账本本批仅 cash 层级：`start()` 校验 `account_level=="cash"`，cash 拒 `SELL_SHORT`/`BUY_TO_COVER`（F-D5） | capability 声明超出账本能力 = 静默错误记账（无保证金/强平语义） | 账本静默支持空单（margin/short 归 P-056） |
| D16 | outbox 本批只写不读，送达循环归 P-054（F-D7） | 预留事件外发通道（N-4），避免半实现投递 | 本批实现 REST 送达（P-054 范围） |

---

## 5. 阈值与默认值表

| 项 | 默认 | 来源 | 可配 |
|---|---|---|---|
| `internal_per_sec` / `internal_per_day` | `RateLimitConfig(max_per_second=1, max_per_day=1000)` | P-052 [compliance.py L77-83](file:///f:/Coding/Factor_Trading_v3.0/core/compliance.py#L77-L83) | ✅ |
| 监管红线 | 300 笔/秒、20000 笔/日 | 沪深细则（2025-07-07 施行） | ❌ 常量 |
| CTP 查询桶 | 1 笔/秒 | 柜台文档 | ✅ |
| 买入预留缓冲 `cost_buffer` | 0.005（0.5%） | 覆盖佣金+滑点 | ✅ |
| 宽限期 `grace_seconds` | 60 | U-P053-4 | ✅ |
| 对账 dust | `max(100 股, 0.1%×|remote|)` | JR/T 0300 实践 | ✅ |
| 现金 dust | `max(1 元, 0.01%×NAV)` | 同上 | ✅ |
| parity（Q10） | cash 0.01% NAV / weight L1 1e-4 / 滑点 10·30bps / 成交率 95% / 连续 2 日降级 | 未决文档 L365 + 总纲 L244 校准 | ✅ `ParityConfig` |
| 重连退避 | 1/2/4/8/16s，上限 30s，最多 5 次 | 工程实践 | ✅ |

---

## 6. 不变式 I1-I12

| ID | 不变式 | 验证方式 |
|----|--------|----------|
| I1 | `orders`/`reconcile`/`session_calendar`/`corporate_actions`/`channel` 的判定函数**零 I/O、零 `datetime.now`、零随机** | grep + 单测直接调用 |
| I2 | 终态（2/4/8/C）不可迁移；`filled_quantity` 单调不减 | 迁移表全枚举单测 |
| I3 | `entry_id`/`fill_key` 唯一致；重复入账返回 False 且状态不变 | 重复 apply 断言 |
| I4 | 现金守恒：`cash+reserved == initial_cash − Σ entry.amount − Σ entry.fee`（误差 <1e-6，全 kind 通用；fill.amount=有符号 q*p、ca/cash_adjust.amount=−现金变动、fee 恒正单列 entry——Step 6 F-I3 统一口径，与 F-D6 分组式代数等价，见 §3.3） | 随机帧回放 + 快照复算 |
| I5 | `submit()` 除 `channel_halted`/`session_closed` 两个前置快败外**必经** `pre_trade_check`（含被拒路径，F-D14） | 打桩计数 |
| I6 | kill 激活时 `adapter.submit` 调用数 == 0 | 打桩计数 |
| I7 | `live/*` 不 import `filter`/`services`/pandas/numpy | grep 守卫 |
| I8 | 账本单写者：第二实例 `SqliteLedgerStore(same path)` 抛错 | 单测 |
| I9 | `UNKNOWN` 不被回报「猜测」推出；只由 `query_orders`/`confirm` 收敛 | 状态机单测 |
| I10 | 账本 append-only；`replay(entries) == snapshot()` | 重放等价单测 |
| I11 | 时间一律外部注入（`ts` 参数 / `clock`）；纯模块零系统时钟 | grep |
| I12 | 审计只用 P-052 的 8 个 `EventType.AUDIT_*`；**不新增**常量 | grep `EventType.` 白名单 |

---

## 7. 测试策略与用例映射（86 例 / 9 文件）

| 文件 | 例数 | 覆盖 |
|---|---|---|
| `tests/test_p053_channel_capability.py` | 10 | 能力缺项拒绝、限额三方最小、状态漂移、`report_registered` 门、品种门 |
| `tests/test_p053_order_semantics.py` | 14 | coid 确定性/唯一性（同输入同值、异输入异值）、迁移表全枚举、终态不可逆、filled 单调、UNKNOWN 收敛 |
| `tests/test_p053_ledger.py` | 14 | 买卖加权成本、realized_pnl、现金守恒、fee 分录、幂等重复入账、reserve/release、分红/送转/拆股、replay 等价 |
| `tests/test_p053_ledger_store.py` | 6 | 建表幂等、WAL 生效、entry 唯一冲突、outbox 事务、单写者锁、重启后 entries 读回 |
| `tests/test_p053_reconcile.py` | 12 | 三类对账、dust/missed/unresolved 判级、explained 归因、overall 取最严重、parity 五项阈值 + 连续 2 日降级 |
| `tests/test_p053_flow_recovery.py` | 8 | 恢复顺序、断线重连不重发、宽限期告警、查询桶 1/s、拒单回写 `on_order_result`、kill 零调用、`cancel_all` 走 bridge、HALTED 拒新开 |
| `tests/test_p053_session_calendar.py` | 8 | 五阶段判定、节假日、午休、收盘集合竞价、跨日、`can_submit` 组合、时区边界、`next_trading_day` |
| `tests/test_p053_corporate_actions.py` | 8 | 四种行为调整、幂等、先归因再判级、事件日期过滤、CSV 载入、未知资产、数量/成本精度、与账本联动 |
| `tests/test_p053_end_to_end.py` | 6 | submit 全链（gate→reserve→adapter→audit）、拒单链、Terminal 清单+回填、完整日循环、崩溃重启恢复、对账 unresolved → HALTED |

**门禁目标**：pytest **1214 → 1300**（+86）/ `-k golden` **22 不变** / mypy **128 → 141**（+13）/ black **261 → 283**（+22）/ `tests/*.py` **132 → 141**（+9）/ `core/*.py` **51 不变** / `live/*.py` **3 → 16**（+13）。

---

## 8. 与总纲 / RESEARCH 的偏差

| # | 偏差 | 说明 | 处理 |
|---|---|---|---|
| 1 | RESEARCH §9 估 6 模块 / 62 例 → DESIGN 13 模块 / 86 例 | 增量来源：G11 两模块（总纲 L419/L421）、SQLite 仓储（U-P053-2）、四适配器骨架（D1）、parity 评估（L244） | 均已在上游有依据；门禁目标按 86 例重算（§7） |
| 2 | RESEARCH §6.1 无 `gateway.py` | 集成点（submit/poll/cancel/reconcile）单列一文件更可测 | 新增，依赖仍为 `live → core` |
| 3 | 新增 `ParityConfig`/`evaluate_parity` | Q10 属 P-053 验收（未决文档 L421），但 RESEARCH 只引阈值未落实现 | 落在 `reconcile.py`，不新增模块 |
| 4 | 新增 `confirm()` / `pending_unconfirmed()` | U-P053-4 的「人工确认」需要落点 | 网关方法；面板 UI 归 P-054 |
| 5 | `LiveTradingBridge` 不变 | D-G7 复用：`cancel_all` 检测 `adapter.bridge` | 无契约变更 |

---

## 9. 风险与未决

| ID | 风险/未决 | 影响 | 处置 |
|---|---|---|---|
| R-1 | 13 模块一次性落地，Step 5 体量偏大 | 交付节奏 | 分 3 组提交（语义层 / 存储+对账 / 适配器+端到端），每组红绿 |
| R-2 | SQLite 在 Windows 上 WAL 与杀进程组合的边界 | 崩溃恢复 | `synchronous=FULL` + 恢复用例（E5）；Step 9 实测 |
| R-3 | synthetic 日历/事件表与真实源差异 | 上线切换 | 接口不变（U-P053-11），真实源作为注入实现 |
| R-4 | `resolve_limits` 默认值若被误配低于通道 | 限流误伤 | 三方 `min` + 单测覆盖 |
| U-P053-12 | 配股缴款是否自动扣现金 | 账本准确性 | 本批**不自动扣款**，只记录数量/成本与显式 `cash_adjust`；真实接入时再定 |
| U-P053-13 | 对账触发编排（收盘后定时、异常停机联动） | 运维 | 本批只提供 API；编排归 P-054 |
| U-P053-14 | 首接**已有持仓**账户：本地空账本 vs 柜台持仓 → UNRESOLVED → HALTED（无 bootstrap 种子，F-D12） | 首连体验 | 本批不做自动导入（SimNow 空仓不受影响）；预留 `seed_snapshot(remote)` 显式导入（人工触发 + `audit.reconcile`），落点随真实连通批次再定 |

---

## 10. 出口条件（Step 5/7/9 对齐）

1. §3 全部契约按签名落地，13 新文件（`live/*.py` 16）；
2. §6 I1-I12 各有对应测试且全绿（86 例）；
3. §7 门禁读数达标（pytest 1300 / mypy 141 / black 283 / tests 141 / golden 22）；
4. §5 全部阈值可配且有默认；
5. `live/*` 零 `filter`/`services`/pandas/numpy import（grep 守卫）；
6. 与 P-052 契约零改写（`pre_trade_check`/`on_order_result`/`cancel_all`/8 审计常量）；
7. CHECKLIST（Step 7）逐项可证、Step 9 实测回填。
