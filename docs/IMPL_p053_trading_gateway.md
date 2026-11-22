# IMPL：P-053 交易通道网关（channel / orders / ledger / ledger_store / reconcile / session_calendar / corporate_actions / gateway + 四适配器）

> **批次**: P-053 · **Step 5 实施文档** · 日期 2026-11-21 · **判档 P2**
> **上游**: [DESIGN_p053](DESIGN_p053_trading_gateway.md)（D1-D16 / I1-I12 / 86 例）；[REVIEW_p053_step4](REVIEW_p053_step4_design.md)（3 P1 + 5 P2 + 6 P3 全修复）
> **零代码**：本文件是 Step 5 的实施方案；**Step 9 才落码**
> **口径**: 13 新文件、9 测试文件 86 例、门禁 pytest 1300 / golden 22 / mypy 141 / black 283 / tests 141 / core 51 / live 16

---

## 1. 变更总览

| # | 文件 | 类型 | 内容 | 对应 DESIGN |
|---|---|---|---|---|
| 1 | `live/channel.py` | 新建 | `ChannelState` / `ChannelCapability`(15) / 3 异常 / `require_capability` / `resolve_limits` / `ChannelLimits` / 4 回报 dataclass / `ChannelAdapter` ABC(7) | §3.1、D2/D9 |
| 2 | `live/orders.py` | 新建 | `OrderState`(9) / `TERMINAL_STATES` / `LEGAL` / `OrderRequest` / `make_client_order_id` / `OrderRecord` / `FillRecord` / `transition` / `from_request` | §3.2、D3/D4 |
| 3 | `live/ledger.py` | 新建 | `PositionLot` / `LedgerEntry` / `LedgerSnapshot` / `LedgerError` / `Ledger`（reserve/release/settle_reserve/apply_fill/apply_corporate_action/snapshot/replay） | §3.3、D5 |
| 4 | `live/ledger_store.py` | 新建 | `LedgerStore` Protocol + `SqliteLedgerStore`（WAL / `BEGIN IMMEDIATE` / `.lock` / 三表） | §3.4、D6 |
| 5 | `live/reconcile.py` | 新建 | `BreakLevel` / `ReconcileConfig` / `ParityConfig` / `Break` / 2 Report / 7 函数 | §3.5、D7 |
| 6 | `live/session_calendar.py` | 新建 | `SessionPhase`(6) / `DaySession` / `Calendar` / 5 函数 | §3.6、G11 |
| 7 | `live/corporate_actions.py` | 新建 | `ActionType`(4) / `CorporateAction` / `load_actions` / `actions_for` / `adjust_position` / `attribute_break` | §3.7、G11 |
| 8 | `live/gateway.py` | 新建 | `SubmitResult` / `TradingGateway`（start/submit/poll/cancel/cancel_all/reconcile/pending_unconfirmed/confirm/ingest_fills/shutdown；内部 `_throttle_query`） | §3.8、D10 |
| 9 | `live/adapters/__init__.py` | 新建 | docstring only | §3.9 |
| 10 | `live/adapters/mock.py` | 新建 | `Frame` / `FakeTransport` / `MockChannelAdapter`（挂 `MockLiveBridge`） | §3.9、D1 |
| 11 | `live/adapters/ctp.py` | 新建 | `CtpTransport` Protocol / `CtpChannelAdapter`（48-55 映射；未注入即 `ChannelUnavailable`） | §3.9、D8 |
| 12 | `live/adapters/broker_api.py` | 新建 | `BrokerApiChannelAdapter`（语义占位） | §3.9 |
| 13 | `live/adapters/terminal.py` | 新建 | `TerminalChannelAdapter`（CSV 清单 + `import_fills`） | §3.9、D13 |
| 14 | `tests/test_p053_*.py` | 新建 9 | 86 例（§4 映射） | §7 |
| — | **零修改清单** | 不改 | `core/*`（含 `safety_gate.py`/`event_log.py`/`compliance.py`/`live_bridge.py`/`execution_policy.py`）、`live/safety_store.py`、`pyproject.toml`（**零新依赖**） | D14 / U-P053-8 |

依赖边（I7 守卫；Step 6 F-I2/F-I4 修复后的真实运行期 DAG）：`live.channel → stdlib`（`OrderRequest`/`OrderState` 经 TYPE_CHECKING 引自 live.orders，C-1）；`live.orders → stdlib`（`OrderRequest` 本文件定义，无 channel 依赖）；`live.ledger → live.orders + live.corporate_actions`；`live.corporate_actions → live.reconcile`（`BreakLevel` 运行期；`PositionLot`/`Break` 仅 TYPE_CHECKING）；`live.reconcile → 零内部运行期依赖`（`LedgerSnapshot` 仅注解）；`live.ledger_store → live.orders + live.ledger`；`live.gateway → 上述 + live.safety_gate + core.{event_log,execution_policy,compliance}`；`live.adapters.* → live.channel + live.orders`。

---

## 2. IMPL 澄清（伪码 → 可执行语义，Step 6 逐条复核）

### C-1 `OrderState` 归属与 `channel.py` 的类型引用方向
DESIGN §3.1 要求 `channel.py` 的回报 dataclass 使用 `OrderState`，而 §2 禁止 `orders → channel` 之外的写法。落地：`channel.py` 里 `if TYPE_CHECKING: from live.orders import OrderRequest, OrderState`，**运行期无 import**（`from __future__ import annotations` 保证注解惰性求值）。因此 `live.orders → live.channel` 仍成立，无环。

### C-2 账本内部表示与「有符号量」约定
`Ledger` 内部：`_cash`（已扣预留后的可用现金）、`_reserves: dict[ref, float]`（冻结额）、`_positions`、`_entries`、`_seen`（幂等集）。
**有符号约定（D5/I4 的唯一口径；Step 6 F-I3 统一）**：`LedgerEntry.quantity` 买正卖负；fill 的 `amount = quantity * price`（有符号：买 + / 卖 −）；`corporate_action`/`cash_adjust` 的 `amount = −现金变动`（分红流入 → amount<0）；`fee` 恒正且**单列一条 entry**（`entry_id=f"fee:{fill_key}"`）。**任一 entry 的现金变动恒为 `−amount`，fee 贡献恒为 `−fee`**。现金守恒统一为：

```
cash + reserved == initial_cash − Σ entry.amount − Σ entry.fee   （误差 <1e-6，全 kind 通用）
```

> 原 C-2 草案「`−Σentry.amount + Σca_cash`」对 ca **双算**、对 `cash_adjust` **漏计**，与 DESIGN I4 分组式并**不**等价（Step 6 F-I3 否决）。统一式与 I4 分组式可互相推导：买入 `−(amount+fee)`、卖出 `−amount−fee = +(q*p−fee)`（sell.amount=−q*p）、ca `−amount` 承载原 `Σca_cash`——等价推导见 [REVIEW_p053_step6](REVIEW_p053_step6_impl.md) §4-3。Step 9 门禁以统一式核对。

### C-3 `release()` 幂等，`settle_reserve()` fail-closed
- `release(ref)`：`ref` 不存在 → **no-op**（撤单/拒单回报可能重复投递，重放不得破坏现金）。
- `settle_reserve(ref, actual)`：`ref` 不存在 → `LedgerError`（成交必须有对应预留；回填场景由调用方走「无预留分支」显式扣减，见 C-4）。
- `apply_fill` 买入分支：`ref=fill.client_order_id` 在 `_reserves` 中 → `settle_reserve(ref, actual=q*p+fee)`；否则（人工回填/Terminal）直接 `cash -= q*p+fee`，现金不足即 `LedgerError`（fail-closed）。

### C-4 `reserve()` 的两条边界
`reserve(amount > cash)` → `LedgerError`；`amount < 0` → `ValueError`。同一 `ref` 重复 `reserve` **累加**（金字塔加仓复用同一 `client_order_id` 时正确），`release` 一次性全额退还。

### C-5 流控三桶映射到 P-052 `RateLedger`
`core.compliance.RateLedger` 的 `per_second` 是**整型秒桶**，故每桶各持一个实例 + 一份 `RateLimitConfig`（`max_per_second=int(max(1, limits.*_per_sec))`、`max_per_day`）：
- submit 桶：`check_rate` → `record(is_cancel=False)`；
- cancel 桶：`check_rate` → `record(is_cancel=True)`；
- query 桶：**独立** `RateLedger` + `check_rate` + `record(is_cancel=False)`（Step 6 F-I8 改写：只 check 不 record 的账本恒放行，流控死设——`record` 才推进 `per_second`/`daily_*` 计数）；该桶 `daily_orders` 语义 = 当日查询数，因账本隔离不污染委托桶（P-052 `_refresh_ctx` 只读 submit 桶）。
调用序恒为 **先 check 后 record**（compliance.py L123-137 注释的硬约束）。**Step 10 F-R5-4**：submit/cancel 桶的 `RateLimitConfig` 同样由 `resolve_limits` 三方最小装配（原仅 query 桶接线 → 通道声明的 submit/cancel 上限本地不生效）；cancel 桶秒上限取 `min(内部秒, limits.cancel_per_sec)`，日上限沿用内部（无通道/监管撤单日上限证据）。

### C-6 市价单的预留金额
`OrderRequest.price` 对市价单为 `None` 时，预留基准价取 `ctx.price`（`GuardContext.price` 必填，guard_pipeline.py L36）；即 `reserve = (request.price or ctx.price) * quantity * (1 + cost_buffer)`。市价单在 `can_submit(CLOSE_AUCTION)` 已被拒（F-D9），连续竞价正常通过。

### C-7 cash 层级双检
`start()` 首行校验 `capability.account_level == "cash"`（D15）；`submit()` 步③再对 `SELL_SHORT`/`BUY_TO_COVER` 直接拒（`CapabilityError`），防 `start()` 后能力漂移。

### C-8 `transition()` 的校验次序
① 源状态终态 → `OrderTransitionError`；② `state not in LEGAL[src]` → 同左；③ `filled_quantity` 低于原值或超 `quantity` → 同左；④ `UNKNOWN` 只能由 `query_orders`/`confirm()` 迁出（I9）：`_apply_order_report(from_query=False)` 对 `state==UNKNOWN` 的记录一律 `ignored_transition`（保守收敛，Step 6 F-I16）；`start()` 的查询回放传 `from_query=True`。
同步语义（同 `state`、`filled_quantity is None`）→ 幂等：不带新 `broker_order_id` 返回原对象；携带（ack 回填场景）只补 broker_order_id 与 updated_ts（Step 6 F-I5——否则 PENDING_NEW ack 必触发 `A→A` 非法迁移）。同态带量增长（多次部成 / CTP 52 复合态重报）经 `LEGAL` 自环合法推进，fq 单调由校验③保证。

### C-9 `audit.*` payload 统一经 `build_audit_payload`
`core.compliance.build_audit_payload(*, operator, time_source, **fields)`（compliance.py L160）已带操作人与时钟口径；网关所有审计写 `payload = build_audit_payload(operator=self._operator, time_source="local", ...)`，避免各点各写字段（I12 只用 8 个 `AUDIT_*` 常量）。

### C-10 Terminal CSV 列序与回填解析
列序固定：`ts,client_order_id,asset,side,quantity,price,order_type,strategy_id,account_id,remark`，`encoding="utf-8-sig"`、`newline=""`、表头只在文件为空时写。`import_fills(path)` 读回填表，列序：`fill_key,client_order_id,asset,side,quantity,price,fee,ts`；缺列 → `ValueError`（不猜）。

### C-11 `poll()` 的 FillReport → FillRecord
`FillReport` 与 `FillRecord` 字段同名同序，直接 `FillRecord(**asdict(report))` 转换后 `ledger.apply_fill()`；`False`（重复）不再写 `audit.fill`。

### C-12 `.lock` 生命周期
`SqliteLedgerStore.__init__` 抢锁成功即保留 fd；`close()` 关连接后 `os.close(fd)` + `os.unlink(lock_path)`（**先关连接再删锁**，防第二实例在连接仍活时抢到锁）。`__del__` 不兜底（显式 `close()`；进程崩溃由 `O_CREAT|O_EXCL` 残留文件阻断，属预期 fail-closed，运维手工删锁）。

---

## 3. 逐处代码

### 3.1 `live/channel.py`（新建）

```python
"""通道能力门、通道状态、限额合成与适配器 ABC（P-053 D2/D9）。

本模块零 I/O、零系统时钟（I1/I11）；`live.orders` 仅 TYPE_CHECKING 引用。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型：运行期不产生 orders ↔ channel 循环依赖（C-1）
    from live.orders import OrderRequest, OrderState


class ChannelState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"      # 可撤单/可查询，禁止新开
    HALTED = "halted"          # 全停（对账 unresolved / 人工）


@dataclass(frozen=True)
class ChannelCapability:
    channel_id: str
    venue: str                      # "ctp" | "broker_api" | "terminal" | "mock"
    account_level: str              # 本批仅 "cash"（D15）；margin/short 归 P-056
    products: tuple[str, ...]       # ("stock",) / ("future","option")
    supports_client_order_id: bool
    supports_cancel: bool
    supports_query_orders: bool
    supports_query_trades: bool
    supports_query_positions: bool
    autonomous: bool
    report_registered: bool
    max_submit_per_sec: float
    max_submit_per_day: int
    max_cancel_per_sec: float
    max_query_per_sec: float
    notes: str = ""


class CapabilityError(RuntimeError):
    """能力不满足（消息含缺失项清单）。"""


class ChannelUnavailable(RuntimeError):
    """未配置 / 未连通 / 未注入 transport。"""


class ChannelRejected(RuntimeError):
    """柜台明确拒单（code/reason 原样落 audit.order）。"""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class ChannelLimits:
    submit_per_sec: float
    submit_per_day: int
    cancel_per_sec: float
    query_per_sec: float


@dataclass(frozen=True)
class SubmitAck:
    client_order_id: str
    broker_order_id: str
    state: OrderState
    ts: float


@dataclass(frozen=True)
class OrderReport:
    client_order_id: str
    broker_order_id: str
    state: OrderState
    filled_quantity: float
    avg_price: float
    ts: float
    code: str = ""
    reason: str = ""


@dataclass(frozen=True)
class FillReport:
    fill_key: str
    client_order_id: str
    asset: str
    side: str
    quantity: float
    price: float
    fee: float
    ts: float


@dataclass(frozen=True)
class PositionReport:
    asset: str
    quantity: float
    available: float | None = None


_SWITCHES = {
    "client_order_id": "supports_client_order_id",
    "cancel": "supports_cancel",
    "query_orders": "supports_query_orders",
    "query_trades": "supports_query_trades",
    "query_positions": "supports_query_positions",
    "autonomous": "autonomous",
    "report_registered": "report_registered",
}


def require_capability(cap: ChannelCapability, *, need: frozenset[str]) -> None:
    """缺项即 ``CapabilityError("missing: a, b")``；未知键按品种名处理（D2）。"""
    missing: list[str] = []
    for key in sorted(need):
        attr = _SWITCHES.get(key)
        if attr is not None:
            if not getattr(cap, attr):
                missing.append(key)
        elif key not in cap.products:
            missing.append(key)
    if missing:
        raise CapabilityError("missing: " + ", ".join(missing))


def resolve_limits(
    cap: ChannelCapability,
    *,
    internal_per_sec: float,
    internal_per_day: int,
    regulator_per_sec: float = 300.0,
    regulator_per_day: int = 20000,
) -> ChannelLimits:
    """三方最小（内部 / 通道 / 监管，D2）：任一维取 min，监管优先。"""
    return ChannelLimits(
        submit_per_sec=min(internal_per_sec, cap.max_submit_per_sec, regulator_per_sec),
        submit_per_day=min(internal_per_day, cap.max_submit_per_day, regulator_per_day),
        cancel_per_sec=min(cap.max_cancel_per_sec, cap.max_submit_per_sec),
        query_per_sec=min(cap.max_query_per_sec, cap.max_submit_per_sec),
    )


class ChannelAdapter(ABC):
    """四通道统一语义（D9）：7 方法 + 2 属性。"""

    capability: ChannelCapability
    state: ChannelState

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def submit(self, request: OrderRequest) -> SubmitAck: ...

    @abstractmethod
    def cancel(self, client_order_id: str) -> None: ...

    @abstractmethod
    def query_orders(self, *, day: str) -> list[OrderReport]: ...

    @abstractmethod
    def query_trades(self, *, day: str) -> list[FillReport]: ...

    @abstractmethod
    def query_positions(self) -> list[PositionReport]: ...

    def drain_reports(self) -> list[OrderReport | FillReport]:
        """非阻塞清空回报队列；无队列通道（poll 型）返回 []。"""
        return []


def _ceil_positive(value: float) -> float:
    return float(math.ceil(value)) if value > 0 else 0.0
```

### 3.2 `live/orders.py`（新建）

```python
"""订单号、FIX 对齐状态机与订单/成交记录（P-053 D3/D4）。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import Enum


@dataclass(frozen=True)
class OrderRequest:
    """统一订单请求（D3/D9；channel 与适配器经 TYPE_CHECKING 引用——Step 6 F-I2 落本文件）。"""

    asset: str
    side: str                      # 与 OrderIntent.action 同域（BUY/SELL/SELL_SHORT/BUY_TO_COVER）
    quantity: float
    asset_type: str = "stock"
    price: float | None = None     # 市价单 None（预留基准价取 ctx.price，C-6）
    order_type: str = "limit"
    client_order_id: str = ""      # 空则由网关步⑤生成一次（D3）
    account_id: str = ""
    strategy_id: str = ""
    signal_ts: float = 0.0
    remark: str = ""


class OrderState(str, Enum):
    PENDING_NEW = "A"
    NEW = "0"
    PARTIALLY_FILLED = "1"
    FILLED = "2"
    CANCELED = "4"
    REJECTED = "8"
    EXPIRED = "C"
    PENDING_CANCEL = "6"
    UNKNOWN = "?"


TERMINAL_STATES = frozenset(
    {OrderState.FILLED, OrderState.CANCELED, OrderState.REJECTED, OrderState.EXPIRED}
)

LEGAL: dict[OrderState, frozenset[OrderState]] = {
    OrderState.PENDING_NEW: frozenset(
        {OrderState.NEW, OrderState.PARTIALLY_FILLED, OrderState.FILLED,
         OrderState.REJECTED, OrderState.EXPIRED, OrderState.UNKNOWN}
    ),
    OrderState.NEW: frozenset(
        {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.PENDING_CANCEL,
         OrderState.CANCELED, OrderState.EXPIRED, OrderState.UNKNOWN}
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {OrderState.PARTIALLY_FILLED,   # 自环：多次部成回报，filled_quantity 递增（F-I5；校验③保单调）
         OrderState.FILLED, OrderState.PENDING_CANCEL, OrderState.CANCELED,
         OrderState.EXPIRED, OrderState.UNKNOWN}
    ),
    OrderState.PENDING_CANCEL: frozenset(
        {OrderState.PENDING_CANCEL,     # 自环：复合态重报（CTP 52 部成待撤多次推送，F-I5）
         OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELED,
         OrderState.EXPIRED, OrderState.UNKNOWN}
    ),
    OrderState.UNKNOWN: frozenset(
        {s for s in OrderState if s is not OrderState.UNKNOWN}
    ),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}

_SOURCE = "live.orders"


def make_client_order_id(
    *,
    strategy_id: str,
    account_id: str,
    asset: str,
    side: str,
    quantity: float,
    price: float | None,
    signal_ts: float,
) -> str:
    """确定性 16 hex（D3）：同输入同输出；网关只在首次 submit 调用一次。"""
    raw = "|".join(
        [
            strategy_id,
            account_id,
            asset,
            side,
            f"{quantity:.6f}",
            f"{(price if price is not None else 0.0):.6f}",
            f"{signal_ts:.6f}",
        ]
    )
    return "co_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class OrderRecord:
    client_order_id: str
    broker_order_id: str
    asset: str
    side: str
    quantity: float
    filled_quantity: float
    avg_price: float
    state: OrderState
    created_ts: float
    updated_ts: float
    reject_code: str = ""
    reject_reason: str = ""

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.filled_quantity)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


@dataclass(frozen=True)
class FillRecord:
    fill_key: str
    client_order_id: str
    asset: str
    side: str
    quantity: float
    price: float
    fee: float
    ts: float


class OrderTransitionError(RuntimeError):
    """非法迁移 / 终态回退 / 成交量回退。"""


def transition(
    record: OrderRecord,
    *,
    state: OrderState,
    ts: float,
    broker_order_id: str | None = None,
    filled_quantity: float | None = None,
    avg_price: float | None = None,
    reject_code: str = "",
    reject_reason: str = "",
) -> OrderRecord:
    """按 §3.2 迁移表推进；同态同步回报幂等返回原对象（C-8）。"""
    if record.state is state and filled_quantity is None:
        # 同态回报（F-I5）：纯重放幂等返回原对象；携带新 broker_order_id（ack 回填）只补该字段
        if broker_order_id and not record.broker_order_id:
            return replace(record, broker_order_id=broker_order_id, updated_ts=ts)
        return record
    if record.is_terminal:
        raise OrderTransitionError(f"{record.client_order_id}: terminal {record.state} is irreversible")
    if state not in LEGAL[record.state]:
        raise OrderTransitionError(
            f"{record.client_order_id}: illegal {record.state} -> {state}"
        )
    fq = record.filled_quantity if filled_quantity is None else filled_quantity
    if fq < record.filled_quantity - 1e-12:
        raise OrderTransitionError(f"{record.client_order_id}: filled_quantity regressed")
    if fq > record.quantity + 1e-12:
        raise OrderTransitionError(f"{record.client_order_id}: filled_quantity > quantity")
    return replace(
        record,
        state=state,
        updated_ts=ts,
        broker_order_id=broker_order_id or record.broker_order_id,
        filled_quantity=fq,
        avg_price=record.avg_price if avg_price is None else avg_price,
        reject_code=reject_code or record.reject_code,
        reject_reason=reject_reason or record.reject_reason,
    )


def from_request(request: OrderRequest, *, ts: float) -> OrderRecord:
    """首次提交的 PENDING_NEW 记录（F-D2：以 request 构造）。"""
    return OrderRecord(
        client_order_id=request.client_order_id,
        broker_order_id="",
        asset=request.asset,
        side=request.side,
        quantity=request.quantity,
        filled_quantity=0.0,
        avg_price=0.0,
        state=OrderState.PENDING_NEW,
        created_ts=ts,
        updated_ts=ts,
    )
```

### 3.3 `live/ledger.py`（新建）

```python
"""双分录账本：加权成本 + `entry_id` 幂等 + 预留结算（P-053 D5）。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from live.corporate_actions import CorporateAction, adjust_position
from live.orders import FillRecord

_EPS = 1e-9


class LedgerError(RuntimeError):
    """fail-closed：预留超现金 / 结算无预留 / 回填现金不足。"""


@dataclass(frozen=True)
class PositionLot:
    asset: str
    quantity: float
    avg_cost: float
    realized_pnl: float = 0.0


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    kind: str                      # fill | fee | corporate_action | cash_adjust
    ts: float
    asset: str
    quantity: float                # 买正卖负（C-2）
    price: float
    amount: float                  # = quantity * price（有符号，不含费）
    fee: float
    ref: str


@dataclass(frozen=True)
class LedgerSnapshot:
    cash: float
    reserved_cash: float
    positions: tuple[PositionLot, ...]
    as_of: float

    @property
    def equity(self) -> float:
        return self.cash + self.reserved_cash + sum(p.quantity * p.avg_cost for p in self.positions)


class Ledger:
    def __init__(self, store=None, *, initial_cash: float = 0.0) -> None:
        self._store = store
        self._initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._reserves: dict[str, float] = {}
        self._positions: dict[str, PositionLot] = {}
        self._entries: list[LedgerEntry] = []
        self._seen: set[str] = set()

    # ---------- 预留 ----------

    def reserve(self, *, ref: str, amount: float, ts: float) -> None:
        if amount < 0:
            raise ValueError(f"reserve amount must be >= 0: {amount}")
        if amount > self._cash + _EPS:
            raise LedgerError(f"insufficient cash for reserve {ref}: need {amount:.2f}")
        self._cash -= amount
        self._reserves[ref] = self._reserves.get(ref, 0.0) + amount

    def release(self, *, ref: str, ts: float) -> None:
        amount = self._reserves.pop(ref, 0.0)          # 缺失即 no-op（C-3）
        if amount:
            self._cash += amount

    def settle_reserve(self, *, ref: str, actual: float, ts: float) -> float:
        reserved = self._reserves.pop(ref, None)
        if reserved is None:
            raise LedgerError(f"no reserve for {ref}")
        returned = reserved - actual
        self._cash += returned
        if self._cash < -_EPS:
            raise LedgerError(f"cash negative after settle {ref}: {self._cash:.4f}")
        return returned

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def reserved(self) -> float:
        return sum(self._reserves.values())

    # ---------- 入账 ----------

    def apply_fill(self, fill: FillRecord, *, ts: float | None = None) -> bool:
        if fill.fill_key in self._seen:
            return False
        t = fill.ts if ts is None else ts
        signed = fill.quantity if fill.side == "BUY" else -fill.quantity
        if fill.side not in ("BUY", "SELL"):
            raise ValueError(f"unsupported side for cash ledger: {fill.side}")   # D15
        amount = signed * fill.price
        if fill.side == "BUY":
            actual = fill.quantity * fill.price + fill.fee
            if fill.client_order_id in self._reserves:
                self.settle_reserve(ref=fill.client_order_id, actual=actual, ts=t)
            else:
                if actual > self._cash + _EPS:
                    raise LedgerError(f"insufficient cash for fill {fill.fill_key}")
                self._cash -= actual
        else:
            self._cash += fill.quantity * fill.price   # 现金变动 = −amount（卖出 amount<0，F-I3）
            self._cash -= fill.fee                     # fee 单列 entry，replay 逐项对应

        self._seen.add(fill.fill_key)
        self._append(
            LedgerEntry(
                entry_id=f"fill:{fill.fill_key}", kind="fill", ts=t, asset=fill.asset,
                quantity=signed, price=fill.price, amount=amount, fee=0.0,
                ref=fill.client_order_id,
            )
        )
        if fill.fee:
            self._append(
                LedgerEntry(
                    entry_id=f"fee:{fill.fill_key}", kind="fee", ts=t, asset=fill.asset,
                    quantity=0.0, price=0.0, amount=0.0, fee=fill.fee,
                    ref=fill.client_order_id,
                )
            )
        self._update_position(fill.asset, signed, fill.price)
        return True

    def apply_corporate_action(self, action: CorporateAction, *, ts: float) -> list[LedgerEntry]:
        lot = self._positions.get(action.asset, PositionLot(action.asset, 0.0, 0.0))
        new_lot, cash_delta = adjust_position(lot, action)
        key = f"ca:{action.action_id}:{action.asset}"
        if key in self._seen:
            return []
        entries = [
            LedgerEntry(
                entry_id=key, kind="corporate_action", ts=ts, asset=action.asset,
                quantity=new_lot.quantity - lot.quantity, price=0.0,
                amount=-cash_delta,          # 统一口径：现金变动 = −amount（F-I3；分红流入 → amount<0）
                fee=0.0, ref=action.action_id,
            )
        ]
        self._cash += cash_delta
        self._positions[action.asset] = new_lot
        for entry in entries:
            self._append(entry)
        return entries

    def cash_adjust(self, *, asset: str, delta: float, ref: str, ts: float) -> LedgerEntry:
        """显式现金调整（入金/费退/配股缴款）：``delta`` = 现金变动；entry.amount = −delta（F-I3）。"""
        key = f"cash_adjust:{ref}"
        if key in self._seen:
            raise LedgerError(f"duplicate cash_adjust: {ref}")
        entry = LedgerEntry(
            entry_id=key, kind="cash_adjust", ts=ts, asset=asset, quantity=0.0,
            price=0.0, amount=-delta, fee=0.0, ref=ref,
        )
        self._cash += delta
        self._append(entry)
        return entry

    # ---------- 读 ----------

    def snapshot(self) -> LedgerSnapshot:
        return LedgerSnapshot(
            cash=self._cash,
            reserved_cash=self.reserved,
            positions=tuple(sorted(self._positions.values(), key=lambda p: p.asset)),
            as_of=self._entries[-1].ts if self._entries else 0.0,
        )

    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    @property
    def initial_cash(self) -> float:
        return self._initial_cash

    def attach_store(self, store) -> None:      # store: LedgerStore；F-I10 网关接线
        self._store = store

    @classmethod
    def resume(cls, entries: Iterable[LedgerEntry], *, initial_cash: float) -> "Ledger":
        """从已持久化分录重建运行账本（崩溃恢复 E⑤ / F-I10；开放预留不参与，I10）。"""
        snap = cls.replay(entries, initial_cash=initial_cash)
        ledger = cls(initial_cash=initial_cash)
        ledger._cash = snap.cash
        ledger._positions = {p.asset: p for p in snap.positions}
        ledger._entries = list(entries)
        ledger._seen = {e.entry_id for e in entries}
        return ledger

    @staticmethod
    def replay(entries: Iterable[LedgerEntry], *, initial_cash: float) -> LedgerSnapshot:
        """只重建 cash/positions（开放中的预留不参与，I10 测试限定为已结算账本，C-2）。

        ``corporate_action`` 的 avg_cost 反推 ratio=(q+Δq)/q 对 STOCK_DIVIDEND/SPLIT 与
        ``adjust_position`` 等价（Step 6 §4-5）；RIGHTS_ISSUE（apply 不摊薄）不在 replay
        等价范围（F-I17④，test_ledger ⑭ 范围确认）。
        """
        cash = float(initial_cash)
        lots: dict[str, PositionLot] = {}
        last_ts = 0.0
        for e in entries:
            last_ts = e.ts
            if e.kind in ("fill", "corporate_action", "cash_adjust"):
                cash -= e.amount
                if e.kind == "fill":
                    lot = lots.get(e.asset, PositionLot(e.asset, 0.0, 0.0))
                    lots[e.asset] = _apply_lot(lot, e.quantity, e.price, None)
                elif e.kind == "corporate_action" and e.quantity:
                    lot = lots.get(e.asset, PositionLot(e.asset, 0.0, 0.0))
                    ratio = (lot.quantity + e.quantity) / lot.quantity if lot.quantity else 1.0
                    lots[e.asset] = replace(lot, quantity=lot.quantity + e.quantity,
                                            avg_cost=lot.avg_cost / ratio if ratio else 0.0)
            if e.kind == "fee":
                cash -= e.fee
        return LedgerSnapshot(
            cash=cash, reserved_cash=0.0,
            positions=tuple(sorted(lots.values(), key=lambda p: p.asset)), as_of=last_ts,
        )

    # ---------- 内部 ----------

    def _append(self, entry: LedgerEntry) -> None:
        if self._store is not None:
            self._store.append_entry(entry)
        self._entries.append(entry)

    def _update_position(self, asset: str, signed_qty: float, price: float) -> None:
        lot = self._positions.get(asset, PositionLot(asset, 0.0, 0.0))
        self._positions[asset] = _apply_lot(lot, signed_qty, price, None)


def _apply_lot(lot: PositionLot, signed_qty: float, price: float, _unused) -> PositionLot:
    """买加仓改加权成本；卖减仓结算 realized_pnl；清零时 avg_cost=0（D5）。"""
    if signed_qty > 0:
        new_qty = lot.quantity + signed_qty
        avg = (lot.quantity * lot.avg_cost + signed_qty * price) / new_qty if new_qty else 0.0
        return PositionLot(lot.asset, new_qty, avg, lot.realized_pnl)
    qty = lot.quantity + signed_qty
    realized = lot.realized_pnl + (price - lot.avg_cost) * (-signed_qty)
    if abs(qty) <= _EPS:
        return PositionLot(lot.asset, 0.0, 0.0, realized)
    return PositionLot(lot.asset, qty, lot.avg_cost, realized)
```

### 3.4 `live/ledger_store.py`（新建）

```python
"""SQLite 仓储：WAL / 单写者 `.lock` / outbox 同库同事务（P-053 D6）。"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from live.ledger import LedgerEntry
from live.orders import OrderRecord, OrderState

_SCHEMA = """
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
"""


class LedgerStore(Protocol):
    def append_entry(self, entry: LedgerEntry) -> bool: ...
    def entries(self) -> list[LedgerEntry]: ...
    def upsert_order(self, record: OrderRecord) -> None: ...
    def load_orders(self) -> list[OrderRecord]: ...
    def append_outbox(self, event_id: str, event_type: str, payload: str, ts: float) -> None: ...
    def pending_outbox(self) -> list[tuple[str, str, str, float]]: ...
    def mark_sent(self, event_id: str) -> None: ...
    def transaction(self): ...
    def close(self) -> None: ...


class SqliteLedgerStore:
    """单写者：同路径第二实例在 `.lock` 处失败（I8）。"""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_name(self._path.name + ".lock")
        self._lock_path = lock_path
        self._lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        self._conn = sqlite3.connect(
            str(self._path), isolation_level=None, check_same_thread=True, timeout=5.0
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._closed = False

    # ---------- ledger ----------

    def append_entry(self, entry: LedgerEntry) -> bool:
        with self.transaction():
            try:
                self._conn.execute(
                    "INSERT INTO ledger_entry VALUES (?,?,?,?,?,?,?,?,?)",
                    (entry.entry_id, entry.kind, entry.ts, entry.asset, entry.quantity,
                     entry.price, entry.amount, entry.fee, entry.ref),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def entries(self) -> list[LedgerEntry]:
        rows = self._conn.execute(
            "SELECT entry_id,kind,ts,asset,quantity,price,amount,fee,ref "
            "FROM ledger_entry ORDER BY rowid"
        ).fetchall()
        return [LedgerEntry(*row) for row in rows]

    # ---------- orders ----------

    def upsert_order(self, record: OrderRecord) -> None:
        payload = json.dumps(asdict(record) | {"state": record.state.value}, sort_keys=True)
        with self.transaction():
            self._conn.execute(
                "INSERT INTO order_record VALUES (?,?,?,?,?) "
                "ON CONFLICT(client_order_id) DO UPDATE SET "
                "broker_order_id=excluded.broker_order_id, state=excluded.state, "
                "payload=excluded.payload, updated_ts=excluded.updated_ts",
                (record.client_order_id, record.broker_order_id, record.state.value,
                 payload, record.updated_ts),
            )

    def load_orders(self) -> list[OrderRecord]:
        rows = self._conn.execute(
            "SELECT payload FROM order_record ORDER BY updated_ts"
        ).fetchall()
        out: list[OrderRecord] = []
        for (payload,) in rows:
            data = json.loads(payload)
            data["state"] = OrderState(data["state"])
            out.append(OrderRecord(**data))
        return out

    # ---------- outbox（本批只写，D16） ----------

    def append_outbox(self, event_id: str, event_type: str, payload: str, ts: float) -> None:
        with self.transaction():
            self._conn.execute(
                "INSERT OR IGNORE INTO outbox VALUES (?,?,?,?,0)",
                (event_id, event_type, payload, ts),
            )

    def pending_outbox(self) -> list[tuple[str, str, str, float]]:
        return self._conn.execute(
            "SELECT event_id,event_type,payload,created_ts FROM outbox "
            "WHERE sent=0 ORDER BY created_ts"
        ).fetchall()

    def mark_sent(self, event_id: str) -> None:
        with self.transaction():
            self._conn.execute("UPDATE outbox SET sent=1 WHERE event_id=?", (event_id,))

    # ---------- 事务与生命周期 ----------

    @contextmanager
    def transaction(self):
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._conn.close()
        os.close(self._lock_fd)
        try:
            os.unlink(self._lock_path)          # 先关连接再删锁（C-12）
        except FileNotFoundError:
            pass
```

### 3.5 `live/reconcile.py`（新建）

```python
"""三级对账 + parity 评估与连续降级（P-053 D7）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:  # F-I4：运行期零内部依赖（LedgerSnapshot 仅注解；未用的 FillRecord import 已删）
    from live.ledger import LedgerSnapshot


class BreakLevel(str, Enum):
    OK = "ok"
    DUST = "dust"
    MISSED = "missed"
    UNRESOLVED = "unresolved"


_SEVERITY = {BreakLevel.OK: 0, BreakLevel.DUST: 1, BreakLevel.MISSED: 2, BreakLevel.UNRESOLVED: 3}


@dataclass(frozen=True)
class ReconcileConfig:
    dust_pct: float = 0.001
    dust_abs_quantity: float = 100.0
    cash_dust_pct_nav: float = 0.0001
    cash_dust_abs: float = 1.0


@dataclass(frozen=True)
class ParityConfig:
    cash_pct_nav: float = 0.0001
    weight_l1: float = 1e-4
    slippage_bps_liquid: float = 10.0
    slippage_bps_illiquid: float = 30.0
    fill_rate_min: float = 0.95
    degrade_days: int = 2


@dataclass(frozen=True)
class Break:
    kind: str            # position | cash | missing_fill | extra_fill
    asset: str
    local: float
    remote: float
    delta: float
    level: BreakLevel
    note: str = ""


@dataclass(frozen=True)
class ReconcileReport:
    as_of: float
    breaks: tuple[Break, ...]
    level: BreakLevel
    checked: int


@dataclass(frozen=True)
class ParityReport:
    cash_delta_pct_nav: float
    weight_l1: float
    slippage_bps: float
    fill_rate: float
    breaches: tuple[str, ...]


def classify_quantity(
    delta: float, remote: float, *, config: ReconcileConfig, explained: bool
) -> BreakLevel:
    if abs(delta) <= 1e-12:
        return BreakLevel.OK
    if abs(delta) <= max(config.dust_abs_quantity, config.dust_pct * abs(remote)):
        return BreakLevel.DUST
    if explained:
        return BreakLevel.MISSED
    return BreakLevel.UNRESOLVED


def reconcile_positions(
    local: dict[str, float],
    remote: dict[str, float],
    *,
    config: ReconcileConfig,
    nav: float = 0.0,
    explained: frozenset[str] = frozenset(),
) -> ReconcileReport:
    breaks: list[Break] = []
    for asset in sorted(set(local) | set(remote)):
        lo, ro = local.get(asset, 0.0), remote.get(asset, 0.0)
        level = classify_quantity(lo - ro, ro, config=config, explained=asset in explained)
        if level is not BreakLevel.OK:
            breaks.append(Break("position", asset, lo, ro, lo - ro, level))
    return ReconcileReport(0.0, tuple(breaks), overall_level_breaks(breaks), len(set(local) | set(remote)))


def reconcile_cash(local: float, remote: float, *, config: ReconcileConfig, nav: float) -> ReconcileReport:
    delta = local - remote
    if abs(delta) <= 1e-12:
        level = BreakLevel.OK
    elif abs(delta) <= max(config.cash_dust_abs, config.cash_dust_pct_nav * abs(nav)):
        level = BreakLevel.DUST
    else:
        level = BreakLevel.UNRESOLVED
    breaks = () if level is BreakLevel.OK else (Break("cash", "CASH", local, remote, delta, level),)
    return ReconcileReport(0.0, breaks, level, 1)


def reconcile_fills(local_keys: set[str], remote_keys: set[str]) -> ReconcileReport:
    breaks: list[Break] = []
    for key in sorted(remote_keys - local_keys):          # 柜台有、本地缺 → 可补录
        breaks.append(Break("missing_fill", key, 0.0, 1.0, -1.0, BreakLevel.MISSED, key))
    for key in sorted(local_keys - remote_keys):          # 本地有、柜台无 → 入账缺口
        breaks.append(Break("extra_fill", key, 1.0, 0.0, 1.0, BreakLevel.UNRESOLVED, key))
    return ReconcileReport(0.0, tuple(breaks), overall_level_breaks(breaks), len(local_keys | remote_keys))


def overall_level(reports: Iterable[ReconcileReport]) -> BreakLevel:
    worst = BreakLevel.OK
    for rep in reports:
        if _SEVERITY[rep.level] > _SEVERITY[worst]:
            worst = rep.level
    return worst


def overall_level_breaks(breaks: Iterable[Break]) -> BreakLevel:
    worst = BreakLevel.OK
    for brk in breaks:
        if _SEVERITY[brk.level] > _SEVERITY[worst]:
            worst = brk.level
    return worst


def evaluate_parity(
    paper: LedgerSnapshot,
    live: LedgerSnapshot,
    *,
    nav: float,
    slippage_bps: float,
    fill_rate: float,
    liquid: bool,
    config: ParityConfig,
) -> ParityReport:
    nav = max(abs(nav), 1e-9)
    cash_pct = abs(paper.cash - live.cash) / nav
    pw = {p.asset: p.quantity * p.avg_cost / nav for p in paper.positions}
    lw = {p.asset: p.quantity * p.avg_cost / nav for p in live.positions}
    l1 = sum(abs(pw.get(a, 0.0) - lw.get(a, 0.0)) for a in set(pw) | set(lw))
    breaches: list[str] = []
    if cash_pct > config.cash_pct_nav:
        breaches.append("cash")
    if l1 > config.weight_l1:
        breaches.append("weight")
    if slippage_bps > (config.slippage_bps_liquid if liquid else config.slippage_bps_illiquid):
        breaches.append("slippage")
    if fill_rate < config.fill_rate_min:
        breaches.append("fill_rate")
    return ParityReport(cash_pct, l1, slippage_bps, fill_rate, tuple(breaches))


def should_degrade(
    reports: Sequence[tuple[str, ParityReport]], *, config: ParityConfig
) -> bool:
    """按日升序取尾部连续 breach 天数(ID)，≥ degrade_days 即降级（F-D8）。"""
    streak = 0
    for _day, rep in sorted(reports, key=lambda item: item[0]):
        if rep.breaches:
            streak += 1
            if streak >= config.degrade_days:
                return True
        else:
            streak = 0
    return False
```

### 3.6 `live/session_calendar.py`（新建）

```python
"""交易日历与时段状态机（P-053 D12 / G11；synthetic 注入）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class SessionPhase(str, Enum):
    PRE_OPEN = "pre_open"
    CONTINUOUS = "continuous"
    LUNCH = "lunch"
    CLOSE_AUCTION = "close_auction"
    CLOSED = "closed"
    HOLIDAY = "holiday"


@dataclass(frozen=True)
class DaySession:
    morning: tuple[int, int] = (9 * 3600 + 30 * 60, 11 * 3600 + 30 * 60)
    afternoon: tuple[int, int] = (13 * 3600, 15 * 3600)
    close_auction: tuple[int, int] | None = (14 * 3600 + 57 * 60, 15 * 3600)
    pre_open: tuple[int, int] = (9 * 3600 + 15 * 60, 9 * 3600 + 30 * 60)


@dataclass(frozen=True)
class Calendar:
    trading_days: frozenset[str]
    session: DaySession = DaySession()
    tz: str = "Asia/Shanghai"


def local_day(ts: float, *, tz: str) -> str:
    return datetime.fromtimestamp(ts, tz=ZoneInfo(tz)).date().isoformat()


def is_trading_day(day: str, *, calendar: Calendar) -> bool:
    return day in calendar.trading_days


def session_phase(ts: float, *, calendar: Calendar) -> SessionPhase:
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo(calendar.tz))
    if dt.date().isoformat() not in calendar.trading_days:
        return SessionPhase.HOLIDAY
    sec = dt.hour * 3600 + dt.minute * 60 + dt.second
    s = calendar.session
    if s.pre_open[0] <= sec < s.pre_open[1]:
        return SessionPhase.PRE_OPEN
    if s.morning[0] <= sec < s.morning[1]:
        return SessionPhase.CONTINUOUS
    if s.morning[1] <= sec < s.afternoon[0]:
        return SessionPhase.LUNCH
    if s.close_auction is not None and s.close_auction[0] <= sec < s.close_auction[1]:
        return SessionPhase.CLOSE_AUCTION
    if s.afternoon[0] <= sec < (s.close_auction[0] if s.close_auction else s.afternoon[1]):
        return SessionPhase.CONTINUOUS
    return SessionPhase.CLOSED


def next_trading_day(day: str, *, calendar: Calendar) -> str | None:
    cursor = datetime.fromisoformat(day).date()
    for _ in range(31):
        cursor = cursor + timedelta(days=1)
        key = cursor.isoformat()
        if key in calendar.trading_days:
            return key
    return None


def can_submit(phase: SessionPhase, *, order_type: str = "limit") -> bool:
    """固定规则（F-D9）：无预埋（F-D10）；收盘竞价仅限价。"""
    if phase is SessionPhase.CONTINUOUS:
        return True
    if phase is SessionPhase.CLOSE_AUCTION:
        return order_type == "limit"
    return False
```

### 3.7 `live/corporate_actions.py`（新建）

```python
"""公司行为事件表与对账先归因（P-053 D12 / G11）。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Iterable

from live.reconcile import BreakLevel    # 运行期唯一内部依赖（attribute_break 判级，F-I4）

if TYPE_CHECKING:  # PositionLot/Break 仅注解：replace 鸭子类型，构造点在 ledger/reconcile 本域
    from live.ledger import PositionLot
    from live.reconcile import Break


class ActionType(str, Enum):
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    SPLIT = "split"
    RIGHTS_ISSUE = "rights_issue"


@dataclass(frozen=True)
class CorporateAction:
    action_id: str
    asset: str
    action_type: ActionType
    ex_date: str
    cash_per_share: float = 0.0
    share_ratio: float = 0.0
    price: float = 0.0
    note: str = ""


_COLUMNS = ("action_id", "asset", "action_type", "ex_date",
            "cash_per_share", "share_ratio", "price", "note")


def load_actions(rows: Iterable[dict[str, str]]) -> tuple[CorporateAction, ...]:
    out: list[CorporateAction] = []
    for row in rows:
        missing = [c for c in _COLUMNS if c not in row]
        if missing:
            raise ValueError(f"corporate action row missing columns: {missing}")
        out.append(
            CorporateAction(
                action_id=row["action_id"], asset=row["asset"],
                action_type=ActionType(row["action_type"]), ex_date=row["ex_date"],
                cash_per_share=float(row["cash_per_share"] or 0.0),
                share_ratio=float(row["share_ratio"] or 0.0),
                price=float(row["price"] or 0.0), note=row["note"],
            )
        )
    return tuple(out)


def actions_for(
    actions: Iterable[CorporateAction], *, asset: str, ex_date: str
) -> tuple[CorporateAction, ...]:
    return tuple(a for a in actions if a.asset == asset and a.ex_date == ex_date)


def adjust_position(lot: PositionLot, action: CorporateAction) -> tuple[PositionLot, float]:
    """返回（新持仓, 现金变动）。配股不自动扣款（U-P053-12）。"""
    if action.action_type is ActionType.CASH_DIVIDEND:
        return lot, action.cash_per_share * lot.quantity
    ratio = action.share_ratio
    if action.action_type is ActionType.RIGHTS_ISSUE:
        return replace(lot, quantity=lot.quantity * (1.0 + ratio)), 0.0
    if ratio <= 0.0:
        return lot, 0.0
    new_qty = lot.quantity * (1.0 + ratio)
    new_avg = lot.avg_cost / (1.0 + ratio) if new_qty else 0.0
    return replace(lot, quantity=new_qty, avg_cost=new_avg), 0.0


def attribute_break(brk: Break, *, actions: tuple[CorporateAction, ...]) -> Break:
    """差异可由同日公司行为精确解释 → MISSED 并记 action_id（先归因再判级）。"""
    for action in actions:
        if action.asset != brk.asset:
            continue
        if brk.kind == "cash" and action.action_type is ActionType.CASH_DIVIDEND:
            expected = action.cash_per_share * brk.local
            if abs(brk.delta - expected) <= max(1.0, abs(expected) * 0.01):
                return replace(brk, level=BreakLevel.MISSED, note=action.action_id)
        if brk.kind == "position" and action.action_type in (
            ActionType.STOCK_DIVIDEND, ActionType.SPLIT, ActionType.RIGHTS_ISSUE,
        ):
            expected = brk.local * action.share_ratio
            if abs(abs(brk.delta) - abs(expected)) <= max(1.0, abs(expected) * 0.01):
                return replace(brk, level=BreakLevel.MISSED, note=action.action_id)
    return brk
```

### 3.8 `live/gateway.py`（新建）

```python
"""TradingGateway：submit 八步固定序 + 回报/对账编排（P-053 D10）。"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterable

from core.compliance import (
    RateLedger,
    RateLimitConfig,
    build_audit_payload,
    check_rate,
    record,
)
from core.event_log import EventType, IEventBus
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext
from live.channel import (
    CapabilityError,
    ChannelAdapter,
    ChannelLimits,
    ChannelRejected,
    ChannelState,
    ChannelUnavailable,
    FillReport,
    OrderReport,
    require_capability,
    resolve_limits,
)
from live.corporate_actions import CorporateAction, attribute_break
from live.ledger import Ledger, LedgerEntry
from live.ledger_store import LedgerStore
from live.orders import (
    FillRecord,
    OrderRecord,
    OrderState,
    OrderTransitionError,
    OrderRequest,
    from_request,
    make_client_order_id,
    transition,
)
from live.reconcile import (
    BreakLevel,
    ParityConfig,
    ReconcileConfig,
    ReconcileReport,
    reconcile_positions,
)
from live.safety_gate import SafetyDecision, SafetyGate
from live.session_calendar import Calendar, can_submit, local_day, session_phase

_SOURCE = "live.gateway"


@dataclass(frozen=True)
class SubmitResult:
    accepted: bool
    client_order_id: str
    state: OrderState
    decision: SafetyDecision | None = None
    reasons: tuple[str, ...] = ()


class TradingGateway:
    def __init__(
        self,
        *,
        adapter: ChannelAdapter,
        gate: SafetyGate,
        ledger: Ledger,
        store: LedgerStore,
        event_log: IEventBus,
        calendar: Calendar | None = None,
        reconcile_config: ReconcileConfig | None = None,
        parity_config: ParityConfig | None = None,
        actions: tuple[CorporateAction, ...] = (),
        rate_config: RateLimitConfig | None = None,
        grace_seconds: float = 60.0,
        operator: str = "system",
        clock: Callable[[], float] = time.time,
        cost_buffer: float = 0.005,          # IMPL D-1：§5 表要求可配
    ) -> None:
        self._adapter = adapter
        self._gate = gate
        self._ledger = ledger
        self._store = store
        self._event_log = event_log
        self._calendar = calendar
        self._reconcile_config = reconcile_config or ReconcileConfig()
        self._parity_config = parity_config or ParityConfig()
        self._actions = actions
        self._rate_config = rate_config or RateLimitConfig()
        self._grace_seconds = grace_seconds
        self._operator = operator
        self._clock = clock
        self._cost_buffer = cost_buffer
        self._orders: dict[str, OrderRecord] = {}
        self._limits: ChannelLimits | None = None
        self._submit_ledger = RateLedger()
        self._cancel_ledger = RateLedger()
        self._query_ledger = RateLedger()
        self._query_config: RateLimitConfig | None = None   # start() 按 resolve_limits 填（F-I8）
        self._submit_config: RateLimitConfig | None = None  # start() 按 resolve_limits 填（F-R5-4）
        self._cancel_config: RateLimitConfig | None = None  # 同上：撤单桶亦取三方最小

    # ---------- 生命周期 ----------

    def start(self) -> None:
        if self._adapter.capability.account_level != "cash":
            raise CapabilityError("ledger supports cash accounts only (D15)")
        self._adapter.connect()
        self._limits = resolve_limits(
            self._adapter.capability,
            internal_per_sec=self._rate_config.max_per_second,
            internal_per_day=self._rate_config.max_per_day,
        )
        self._query_config = RateLimitConfig(
            max_per_second=int(max(1, round(self._limits.query_per_sec))),
            max_per_day=self._rate_config.max_per_day,   # 无查询日上限证据，保守沿用（F-I8）
        )
        self._submit_config = RateLimitConfig(           # F-R5-4：委托桶接三方最小（D11 双层）
            max_per_second=max(1, int(round(self._limits.submit_per_sec))),
            max_per_day=min(self._rate_config.max_per_day, self._limits.submit_per_day),
        )
        self._cancel_config = RateLimitConfig(           # F-R5-4：撤单桶取 min(内部, 通道撤单上限)
            max_per_second=max(
                1, min(self._rate_config.max_per_second, int(round(self._limits.cancel_per_sec)))
            ),
            max_per_day=self._rate_config.max_per_day,   # 无通道/监管撤单日上限证据，沿用内部
        )
        cap = self._adapter.capability
        if cap.autonomous:                  # F-I6：半自动通道无查询能力，跳过远程恢复
            require_capability(cap, need=frozenset({"query_trades", "query_orders"}))
        self._ledger.attach_store(self._store)               # F-I10：接线（否则分录不落库）
        persisted = self._store.entries()
        if persisted and not self._ledger.entries():         # 崩溃恢复：重建运行账本（F-I10）
            self._ledger = Ledger.resume(persisted, initial_cash=self._ledger.initial_cash)
        day = local_day(self._clock(), tz=(self._calendar.tz if self._calendar else "Asia/Shanghai"))
        for rec in self._store.load_orders():   # F-R5-2：先装载本地订单，远程回报方可回放
            self._orders.setdefault(rec.client_order_id, rec)
        if cap.autonomous:                  # 恢复序（SSE）：先成交报告 → 再订单状态
            self._throttle_query(self._clock())
            for report in self._adapter.query_trades(day=day):
                self._ledger.apply_fill(FillRecord(**asdict(report)))
            self._throttle_query(self._clock())
            for report in self._adapter.query_orders(day=day):
                self._apply_order_report(report, ts=self._clock(), from_query=True)
        self.reconcile(ts=self._clock())                     # F-I15：不留死赋值

    def shutdown(self) -> None:
        try:
            self._adapter.disconnect()
        finally:
            self._store.close()

    # ---------- 生成 ----------

    def submit(
        self,
        intent: OrderIntent,
        request: OrderRequest,
        ctx: GuardContext,
        *,
        account_id: str,
        strategy_id: str,
        ts: float,
    ) -> SubmitResult:
        self._validate_args(intent, request, ctx, account_id, strategy_id)

        if self._adapter.state is ChannelState.HALTED:                    # ①
            return SubmitResult(False, request.client_order_id, OrderState.REJECTED,
                                reasons=("channel_halted",))
        if self._calendar is not None:                                     # ②
            phase = session_phase(ts, calendar=self._calendar)
            if not can_submit(phase, order_type=request.order_type):
                return SubmitResult(False, request.client_order_id, OrderState.REJECTED,
                                    reasons=("session_closed",))

        if self._adapter.capability.autonomous:                            # ③ F-I6
            need = {"client_order_id", "cancel", "query_orders"}
        else:                        # 半自动：无撤单/查询能力，订单清单 + 人工确认
            need = {"client_order_id"}
        require_capability(self._adapter.capability, need=frozenset(need))
        if request.side in ("SELL_SHORT", "BUY_TO_COVER"):
            raise CapabilityError("cash account cannot short (D15)")
        allowed, reason = check_rate(self._submit_ledger, ts,
                                     self._submit_config or self._rate_config)  # F-R5-4
        if not allowed:
            return SubmitResult(False, request.client_order_id, OrderState.REJECTED,
                                reasons=(f"rate_{reason}",))

        decision = self._gate.pre_trade_check(                    # ④
            intent, ctx, account_id=account_id, strategy_id=strategy_id, ts=ts
        )
        if not decision.allowed:
            return SubmitResult(False, request.client_order_id, OrderState.REJECTED,
                                decision=decision, reasons=decision.reasons)

        coid = request.client_order_id or make_client_order_id(   # ⑤
            strategy_id=strategy_id, account_id=account_id, asset=request.asset,
            side=request.side, quantity=request.quantity, price=request.price,
            signal_ts=request.signal_ts,
        )
        request = replace(request, client_order_id=coid)
        if request.side == "BUY":                                 # ⑥
            base_price = request.price if request.price is not None else ctx.price
            self._ledger.reserve(
                ref=coid,
                amount=base_price * request.quantity * (1.0 + self._cost_buffer),
                ts=ts,
            )
        rec = from_request(request, ts=ts)
        try:                                                      # ⑦
            ack = self._adapter.submit(request)
        except ChannelRejected as exc:
            self._ledger.release(ref=coid, ts=ts)
            self._gate.on_order_result(rejected=True, ts=ts)
            self._audit(EventType.AUDIT_ORDER, coid, "rejected", code=exc.code,
                        reason=exc.reason, ts=ts)
            return SubmitResult(False, coid, OrderState.REJECTED, reasons=(exc.code,))
        except ChannelUnavailable as exc:                         # F-I7：请求级未受理不计拒单
            self._ledger.release(ref=coid, ts=ts)
            self._audit(EventType.AUDIT_ORDER, coid, "unavailable", reason=str(exc), ts=ts)
            return SubmitResult(False, coid, OrderState.PENDING_NEW,
                                reasons=("channel_unavailable",))

        self._submit_ledger = record(self._submit_ledger, ts, False)
        rec = transition(rec, state=ack.state, ts=ts,
                         broker_order_id=ack.broker_order_id)      # ⑧（F-I5：同态回填 broker id）
        self._gate.on_order_result(rejected=False, ts=ts)          # F-I9：成功 ack 重置拒单计数
        self._orders[coid] = rec
        self._store.upsert_order(rec)
        self._audit(EventType.AUDIT_ORDER, coid, "accepted", state=rec.state.value, ts=ts)
        self._store.append_outbox(
            event_id=uuid.uuid4().hex, event_type=EventType.AUDIT_ORDER,
            payload=coid, ts=ts,
        )
        return SubmitResult(True, coid, rec.state, decision=decision)

    # ---------- 回报 ----------

    def poll(self, *, ts: float | None = None) -> list[LedgerEntry]:
        """回报驱动：drain → 入账（FILL）或状态推进（REPORT）；返回本轮新增分录（D-5/F-I14）。"""
        now = self._clock() if ts is None else ts
        applied: list[LedgerEntry] = []
        for report in self._adapter.drain_reports():
            if isinstance(report, FillReport):
                mark = len(self._ledger.entries())
                if self._ledger.apply_fill(FillRecord(**asdict(report)), ts=report.ts):
                    self._audit(EventType.AUDIT_FILL, report.client_order_id,
                                "fill", fill_key=report.fill_key, ts=report.ts)
                    applied.extend(self._ledger.entries()[mark:])
                continue
            self._apply_order_report(report, ts=now)
        return applied

    def _apply_order_report(self, report: OrderReport, *, ts: float,
                            from_query: bool = False) -> None:
        rec = self._orders.get(report.client_order_id)
        if rec is None:
            return
        if rec.state is OrderState.UNKNOWN and not from_query:   # F-I16：drain 帧不迁出 UNKNOWN（I9）
            self._audit(EventType.AUDIT_ORDER, report.client_order_id,
                        "ignored_transition", from_state=rec.state.value,
                        to_state=report.state.value, ts=ts)
            return
        try:
            updated = transition(
                rec, state=report.state, ts=report.ts,
                filled_quantity=report.filled_quantity, avg_price=report.avg_price,
                reject_code=report.code, reject_reason=report.reason,
                broker_order_id=report.broker_order_id or None,
            )
        except OrderTransitionError:
            self._audit(EventType.AUDIT_ORDER, report.client_order_id,
                        "ignored_transition", from_state=rec.state.value,
                        to_state=report.state.value, ts=ts)
            return
        self._orders[report.client_order_id] = updated
        self._store.upsert_order(updated)
        self._audit(EventType.AUDIT_ORDER, report.client_order_id,
                    "transition", state=updated.state.value, ts=ts)
        if updated.state is OrderState.REJECTED:
            self._gate.on_order_result(rejected=True, ts=ts)
            self._ledger.release(ref=report.client_order_id, ts=ts)
        else:
            self._gate.on_order_result(rejected=False, ts=ts)    # F-I9：非拒单迁移重置计数
            if updated.state is OrderState.CANCELED:
                self._ledger.release(ref=report.client_order_id, ts=ts)

    def _throttle_query(self, ts: float) -> None:
        """查询桶独立限流：先 check 后 record（F-I8；daily_orders = 当日查询数）。"""
        cfg = self._query_config or self._rate_config
        allowed, reason = check_rate(self._query_ledger, ts, cfg)
        if not allowed:
            raise ChannelUnavailable(f"query rate limited: {reason}")
        self._query_ledger = record(self._query_ledger, ts, is_cancel=False)

    def ingest_fills(self, reports: Iterable[FillReport]) -> list[LedgerEntry]:
        """Terminal/人工回填入口（F-I12）：import_fills 产出经此入账并审计（E2E ③）。"""
        applied: list[LedgerEntry] = []
        for report in reports:
            mark = len(self._ledger.entries())
            if self._ledger.apply_fill(FillRecord(**asdict(report)), ts=report.ts):
                self._audit(EventType.AUDIT_FILL, report.client_order_id,
                            "fill", fill_key=report.fill_key, ts=report.ts)
                applied.extend(self._ledger.entries()[mark:])
        return applied

    # ---------- 撤单 ----------

    def cancel(self, client_order_id: str, *, ts: float) -> bool:
        rec = self._orders.get(client_order_id)
        if rec is None or rec.is_terminal:
            return False
        allowed, reason = check_rate(self._cancel_ledger, ts,
                                     self._cancel_config or self._rate_config)  # F-R5-4
        if not allowed:
            return False
        try:
            self._adapter.cancel(client_order_id)
        except ChannelRejected:
            return False
        except ChannelUnavailable:                   # F-I7：流控未受理，不迁移状态
            return False
        self._cancel_ledger = record(self._cancel_ledger, ts, True)
        self._orders[client_order_id] = transition(
            rec, state=OrderState.PENDING_CANCEL, ts=ts
        )
        self._store.upsert_order(self._orders[client_order_id])
        self._audit(EventType.AUDIT_CANCEL, client_order_id, "requested", ts=ts)
        return True

    def cancel_all(self, *, ts: float) -> int:
        bridge = getattr(self._adapter, "bridge", None)
        if bridge is not None:
            return self._gate.cancel_all(bridge, ts=ts)
        count = 0
        for coid, rec in list(self._orders.items()):
            if not rec.is_terminal and self.cancel(coid, ts=ts):
                count += 1
        return count

    # ---------- 对账与人工确认 ----------

    def reconcile(self, *, ts: float, nav: float = 0.0) -> ReconcileReport:
        if not self._adapter.capability.autonomous:          # F-I6：半自动通道人工对账不入网关
            self._audit(EventType.AUDIT_RECONCILE, "-", "manual_channel", ts=ts)
            return ReconcileReport(ts, (), BreakLevel.OK, 0)
        self._throttle_query(ts)                             # F-I8/F-I14：query_positions 受查询桶
        snapshot = self._ledger.snapshot()
        local = {p.asset: p.quantity for p in snapshot.positions}
        remote = {r.asset: r.quantity for r in self._adapter.query_positions()}
        explained: frozenset[str] = frozenset()              # F-I13：精确归因交给 attribute_break
        report = reconcile_positions(local, remote, config=self._reconcile_config,
                                     nav=nav, explained=explained)
        report = replace(
            report,
            breaks=tuple(attribute_break(b, actions=self._actions) for b in report.breaks),
        )
        self._audit(EventType.AUDIT_RECONCILE, "-", report.level.value,
                    checked=report.checked, ts=ts)
        if report.level.value == "unresolved":
            self._adapter.state = ChannelState.HALTED
        return report

    def pending_unconfirmed(self) -> list[OrderRecord]:
        return [
            r for r in self._orders.values()
            if r.state in (OrderState.PENDING_NEW, OrderState.UNKNOWN)
            and self._clock() - r.created_ts > self._grace_seconds
        ]

    def confirm(self, client_order_id: str, *, state: OrderState, ts: float) -> OrderRecord:
        rec = self._orders[client_order_id]
        updated = transition(rec, state=state, ts=ts)
        self._orders[client_order_id] = updated
        self._store.upsert_order(updated)
        self._audit(EventType.AUDIT_ORDER, client_order_id, "confirmed",
                    state=updated.state.value, ts=ts)
        return updated

    # ---------- 内部 ----------

    def _audit(self, event_type: str, ref: str, action: str, **fields) -> None:
        payload = build_audit_payload(
            operator=self._operator, time_source="local",
            client_order_id=ref, action=action, **fields,   # source 只写 entry 级（F-I17）
        )
        self._event_log.append(event_type, payload, source=_SOURCE)

    def _validate_args(self, intent, request, ctx, account_id, strategy_id) -> None:
        """request ↔ intent ↔ kwargs 一致性（F-D2：fail-closed，adapter 零调用）。"""
        problems = []
        if request.asset != intent.asset:
            problems.append("asset")
        if str(request.asset_type) != str(intent.asset_type):
            problems.append("asset_type")
        if request.side != intent.action:
            problems.append("side")
        if abs(request.quantity - intent.abs_trade_quantity) > 1e-9:
            problems.append("quantity")
        if request.account_id != account_id:
            problems.append("account_id")
        if request.strategy_id != strategy_id:
            problems.append("strategy_id")
        if request.order_type == "limit" and request.price is None:
            problems.append("price")
        if problems:
            raise ValueError("inconsistent order args: " + ", ".join(problems))
```

> **Step 6 F-I11**：`CapabilityError`/`ChannelUnavailable`/`replace`/`asdict`/`Iterable` 已全部入 §3.8 import 块，尾注作废。
> `poll()` 返回本轮新增 entry（D-5）：以 `len(entries())` 前后差切片取新增（fill+fee 两类），不改 `apply_fill` 签名（test_ledger ⑦ 的 bool 契约保持）。

### 3.9 `live/adapters/*.py`（新建 5 文件）

**`__init__.py`**

```python
"""P-053 通道适配器骨架（mock / ctp / broker_api / terminal）。"""
```

**`mock.py`**（确定性、无 sleep、无随机）

```python
from __future__ import annotations

from dataclasses import dataclass, field

from core.live_bridge import MockLiveBridge
from live.channel import (
    ChannelAdapter, ChannelCapability, ChannelRejected, ChannelState,
    FillReport, OrderReport, PositionReport, SubmitAck,
)
from live.orders import OrderRequest, OrderState


@dataclass(frozen=True)
class Frame:
    kind: str                 # ack | reject | order | fill | disconnect
    payload: dict
    delay: float = 0.0


class FakeTransport:
    """按脚本出帧；测试注入帧序列（D1）。"""

    def __init__(self, frames: list[Frame] | None = None) -> None:
        self.frames: list[Frame] = list(frames or [])
        self.sent: list[OrderRequest] = []
        self.cancels: list[str] = []

    def next_frame(self, kind: str) -> Frame | None:
        for i, frame in enumerate(self.frames):
            if frame.kind == kind:
                return self.frames.pop(i)
        return None


class MockChannelAdapter(ChannelAdapter):
    def __init__(self, transport: FakeTransport | None = None) -> None:
        self._transport = transport or FakeTransport()
        self.bridge = MockLiveBridge()
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="mock", venue="mock", account_level="cash", products=("stock",),
            supports_client_order_id=True, supports_cancel=True, supports_query_orders=True,
            supports_query_trades=True, supports_query_positions=True, autonomous=True,
            report_registered=True, max_submit_per_sec=50.0, max_submit_per_day=100000,
            max_cancel_per_sec=50.0, max_query_per_sec=10.0,
        )

    def connect(self) -> None:
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        frame = self._transport.next_frame("reject")
        if frame is not None:
            raise ChannelRejected(str(frame.payload.get("code", "mock_reject")),
                                  str(frame.payload.get("reason", "")))
        self._transport.sent.append(request)
        ack = self._transport.next_frame("ack")
        state = OrderState(ack.payload.get("state", OrderState.PENDING_NEW.value)) if ack else OrderState.PENDING_NEW
        return SubmitAck(request.client_order_id, f"mock_{len(self._transport.sent):06d}",
                         state, 0.0)   # ts=0.0：ack.ts 不被网关消费（transition 用 submit 的 ts，I1 确定性）

    def cancel(self, client_order_id: str) -> None:
        self._transport.cancels.append(client_order_id)

    def query_orders(self, *, day: str) -> list[OrderReport]:
        return []

    def query_trades(self, *, day: str) -> list[FillReport]:
        return []

    def query_positions(self) -> list[PositionReport]:
        return []

    def drain_reports(self):
        out = []
        while True:
            frame = self._transport.next_frame("order")
            if frame is None:
                break
            out.append(OrderReport(**frame.payload))
        while True:
            frame = self._transport.next_frame("fill")
            if frame is None:
                break
            out.append(FillReport(**frame.payload))
        return out
```

**`ctp.py`**（协议映射，真实网络零调用）

```python
from __future__ import annotations

from typing import Protocol

from live.channel import (
    ChannelAdapter, ChannelCapability, ChannelRejected, ChannelState,
    ChannelUnavailable, FillReport, OrderReport, PositionReport, SubmitAck,
)
from live.orders import OrderRequest, OrderState

# 迅投/CTP 48-55 → FIX 9 值（RESEARCH §3.2 官方字典；Step 6 F-I7 复核）：
# 51 已报待撤 / 52 部成待撤（复合态：撤单进行中且有部分成交 → PENDING_CANCEL，
# filled_quantity 由回报承载）/ 53 部撤 / 54 已撤 / 55 部成。
_CTP_STATUS = {
    "48": OrderState.PENDING_NEW, "49": OrderState.PENDING_NEW,
    "50": OrderState.NEW, "51": OrderState.PENDING_CANCEL,
    "52": OrderState.PENDING_CANCEL, "53": OrderState.CANCELED,
    "54": OrderState.CANCELED, "55": OrderState.PARTIALLY_FILLED,
}


class CtpTransport(Protocol):
    def send_order(self, request: OrderRequest) -> dict: ...
    def cancel_order(self, client_order_id: str) -> dict: ...
    def req_qry_orders(self, day: str) -> list[dict]: ...
    def req_qry_trades(self, day: str) -> list[dict]: ...
    def req_qry_positions(self) -> list[dict]: ...
    def subscribe(self) -> None: ...


class CtpChannelAdapter(ChannelAdapter):
    def __init__(self, transport: CtpTransport | None = None) -> None:
        self._transport = transport
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="ctp", venue="ctp", account_level="cash", products=("future", "option"),
            supports_client_order_id=True,   # F-R5-1：coid ↔ OrderRef 映射（原 False 与网关能力门互斥）
            supports_cancel=True, supports_query_orders=True,
            supports_query_trades=True, supports_query_positions=True, autonomous=True,
            report_registered=True, max_submit_per_sec=10.0, max_submit_per_day=20000,
            max_cancel_per_sec=10.0, max_query_per_sec=1.0,     # 查询 1 笔/秒
        )
        self._refs: dict[str, tuple[str, str, str]] = {}

    def _require(self) -> CtpTransport:
        if self._transport is None:
            raise ChannelUnavailable("ctp transport not injected")
        return self._transport

    def connect(self) -> None:
        self._require().subscribe()
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        reply = self._require().send_order(request)
        code = str(reply.get("error_id", "0"))
        if code in ("-2", "-3"):
            # -2/-3 = 请求级流控（未送达柜台，RESEARCH §3.2）→ 可重试，不计柜台拒单（F-I7）
            raise ChannelUnavailable(f"ctp flow control {code}: {reply.get('error_msg', '')}")
        if code not in ("0", ""):                 # 非 0 一律柜台拒单（F-I7：原只拦 -2/-3）
            raise ChannelRejected(code, str(reply.get("error_msg", "")))
        ref = str(reply["order_ref"])
        self._refs[request.client_order_id] = (   # F-R5-5：coid ↔ (FrontID, SessionID, OrderRef)
            str(reply.get("front_id", "")), str(reply.get("session_id", "")), ref,
        )
        return SubmitAck(request.client_order_id, ref,
                         OrderState.PENDING_NEW, 0.0)

    def cancel(self, client_order_id: str) -> None:
        reply = self._require().cancel_order(client_order_id)
        code = str(reply.get("error_id", "0"))
        if code in ("-2", "-3"):
            raise ChannelUnavailable(f"ctp flow control {code}: {reply.get('error_msg', '')}")
        if code not in ("0", ""):
            raise ChannelRejected(code, str(reply.get("error_msg", "")))

    def query_orders(self, *, day: str) -> list[OrderReport]:
        by_ref = {ref: coid for coid, (_f, _s, ref) in self._refs.items()}  # F-R5-5 反查
        return [
            OrderReport(
                client_order_id=by_ref.get(str(row["order_ref"]), str(row["client_order_id"])),
                broker_order_id=str(row["order_ref"]),
                state=_CTP_STATUS.get(str(row["order_status"]), OrderState.UNKNOWN),
                filled_quantity=float(row.get("volume_traded", 0.0)),
                avg_price=float(row.get("price_traded", 0.0)), ts=float(row["ts"]),
                code=str(row.get("status_msg", "")), reason="",
            )
            for row in self._require().req_qry_orders(day)
        ]

    def query_trades(self, *, day: str) -> list[FillReport]:
        return [FillReport(**row) for row in self._require().req_qry_trades(day)]

    def query_positions(self) -> list[PositionReport]:
        return [
            PositionReport(asset=row["instrument_id"], quantity=float(row["volume"]))
            for row in self._require().req_qry_positions()
        ]
```

**`broker_api.py`**（语义占位）

```python
from __future__ import annotations

from live.channel import (
    ChannelAdapter, ChannelCapability, ChannelState, ChannelUnavailable,
    FillReport, OrderReport, PositionReport, SubmitAck,
)
from live.orders import OrderRequest


class BrokerApiChannelAdapter(ChannelAdapter):
    def __init__(self, transport=None) -> None:
        self._transport = transport
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="broker_api", venue="broker_api", account_level="cash",
            products=("stock",), supports_client_order_id=True, supports_cancel=True,
            supports_query_orders=True, supports_query_trades=True,
            supports_query_positions=True, autonomous=True, report_registered=False,
            max_submit_per_sec=20.0, max_submit_per_day=20000, max_cancel_per_sec=20.0,
            max_query_per_sec=4.0, notes="语义占位；准入审核归 N-3",
        )

    def _require(self):
        if self._transport is None:
            raise ChannelUnavailable("broker_api not configured")
        return self._transport

    def connect(self) -> None:
        self._require()
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        raise ChannelUnavailable("broker_api not configured")

    def cancel(self, client_order_id: str) -> None:
        raise ChannelUnavailable("broker_api not configured")

    def query_orders(self, *, day: str) -> list[OrderReport]:
        raise ChannelUnavailable("broker_api not configured")

    def query_trades(self, *, day: str) -> list[FillReport]:
        raise ChannelUnavailable("broker_api not configured")

    def query_positions(self) -> list[PositionReport]:
        raise ChannelUnavailable("broker_api not configured")
```

**`terminal.py`**（半自动清单 + 回填）

```python
from __future__ import annotations

import csv
from pathlib import Path

from core.event_log import EventType, IEventBus
from live.channel import (
    ChannelAdapter, CapabilityError, ChannelCapability, ChannelState,
    FillReport, OrderReport, PositionReport, SubmitAck,
)
from live.orders import OrderRequest, OrderState

_ORDER_COLUMNS = ("ts", "client_order_id", "asset", "side", "quantity", "price",
                  "order_type", "strategy_id", "account_id", "remark")
_FILL_COLUMNS = ("fill_key", "client_order_id", "asset", "side", "quantity",
                 "price", "fee", "ts")


class TerminalChannelAdapter(ChannelAdapter):
    def __init__(self, path: str | Path, *, event_log: IEventBus, ts_provider) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._event_log = event_log
        self._ts = ts_provider
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="terminal", venue="terminal", account_level="cash",
            products=("stock",), supports_client_order_id=True, supports_cancel=False,
            supports_query_orders=False, supports_query_trades=False,
            supports_query_positions=False, autonomous=False, report_registered=False,
            max_submit_per_sec=1.0, max_submit_per_day=1000, max_cancel_per_sec=0.0,
            max_query_per_sec=0.0,
        )

    def connect(self) -> None:
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        write_header = not self._path.exists() or self._path.stat().st_size == 0
        with self._path.open("a", newline="", encoding="utf-8-sig") as fp:
            writer = csv.writer(fp)
            if write_header:
                writer.writerow(_ORDER_COLUMNS)
            writer.writerow([
                f"{self._ts():.6f}", request.client_order_id, request.asset, request.side,
                f"{request.quantity:.6f}", "" if request.price is None else f"{request.price:.6f}",
                request.order_type, request.strategy_id, request.account_id, request.remark,
            ])
        self._event_log.append(EventType.AUDIT_ORDER,
                               {"client_order_id": request.client_order_id,
                                "action": "listed", "path": str(self._path)},
                               source="live.adapters.terminal")
        return SubmitAck(request.client_order_id, "", OrderState.PENDING_NEW, self._ts())

    def cancel(self, client_order_id: str) -> None:
        raise CapabilityError("missing: cancel")

    def query_orders(self, *, day: str) -> list[OrderReport]:
        raise CapabilityError("missing: query_orders")

    def query_trades(self, *, day: str) -> list[FillReport]:
        raise CapabilityError("missing: query_trades")

    def query_positions(self) -> list[PositionReport]:
        raise CapabilityError("missing: query_positions")

    def import_fills(self, path: str | Path) -> list[FillReport]:
        with Path(path).open(newline="", encoding="utf-8-sig") as fp:
            rows = list(csv.DictReader(fp))
        missing = [c for c in _FILL_COLUMNS if rows and c not in rows[0]]
        if missing:
            raise ValueError(f"fill csv missing columns: {missing}")
        return [
            FillReport(
                fill_key=row["fill_key"], client_order_id=row["client_order_id"],
                asset=row["asset"], side=row["side"],
                quantity=float(row["quantity"]), price=float(row["price"]),
                fee=float(row["fee"] or 0.0), ts=float(row["ts"]),
            )
            for row in rows
        ]
```

---

## 4. 测试映射（86 例 / 9 文件）

| 文件 | 例数 | 用例（断言要点） |
|---|---|---|
| `test_p053_channel_capability.py` | 10 | ①缺 `cancel` 抛 `CapabilityError` 且消息含键 ②`report_registered=False` 被拒 ③品种门（`future` 不在 `products`）④`resolve_limits` 三方取 min（内部低于通道）⑤通道低于内部 ⑥监管 300 兜底 ⑦`max_query_per_sec` 独立与 submit 解耦 ⑧`ChannelRejected` 保留 code/reason ⑨`SubmitAck` 字段可构造 ⑩五状态枚举值固定 |
| `test_p053_order_semantics.py` | 14 | ①coid 同输入同值 ②异输入异值 ③coid 前缀 `co_` + 长度 19（`co_`+sha1[:16]） ④`from_request` 初始 A ⑤A→0 ⑥A→1/A→2 秒成交（F-D3）⑦A→8 ⑧0→4 ⑨1→2 ⑩6→4 ⑪?→0 ⑫终态不可逆（2/4/8/C 各一断言合并）⑬filled 回退抛错 ⑭filled > quantity 抛错；另含 PF→PF 带量自环 / PC→PC 重报 / 同态 ack 回填断言（F-I5，合并断言体例） |
| `test_p053_ledger.py` | 14 | ①买入加权成本 ②两次买入摊薄 ③卖出 realized_pnl ④卖出清零 avg_cost=0 ⑤现金守恒（买+卖+费）⑥fee 独立 entry ⑦`entry_id` 重复返回 False ⑧reserve 后 cash 减少 ⑨release 退还 ⑩settle 退还差额 ⑪reserve 超现金 `LedgerError` ⑫`settle_reserve` 无预留 `LedgerError` ⑬分红 cash_delta ⑭送转/拆股 + replay 等价（合并） |
| `test_p053_ledger_store.py` | 6 | ①建表幂等（两实例前先 close）②`journal_mode=wal` ③`entry_id` 冲突返回 False ④outbox 事务（entry + outbox 同事务回滚）⑤第二实例 `.lock` 抛错（I8）⑥重启后 entries/orders 读回 |
| `test_p053_reconcile.py` | 12 | ①持仓 delta=0 → OK ②DUST 阈值（绝对）③DUST 阈值（比例）④explained → MISSED ⑤未解释 → UNRESOLVED ⑥现金 DUST ⑦现金 UNRESOLVED ⑧missing_fill → MISSED ⑨extra_fill → UNRESOLVED ⑩overall 取最严重 ⑪`evaluate_parity` 四项 breach ⑫`should_degrade` 连续 2 日（含中断重置） |
| `test_p053_flow_recovery.py` | 8 | ①恢复顺序 trades→orders（桩记录调用序）②断线重连不重发（`transport.sent` 计数）③宽限期前 `pending_unconfirmed` 为空 / 后非空 ④查询桶 1/s（第二次 query 被限）⑤拒单回写 `on_order_result(rejected=True)` ⑥kill 激活 `adapter.submit` 零调用（I6）⑦`cancel_all` 走 bridge 且返回计数 ⑧HALTED 拒新开（`channel_halted`） |
| `test_p053_session_calendar.py` | 8 | ①HOLIDAY ②PRE_OPEN ③CONTINUOUS ④LUNCH ⑤CLOSE_AUCTION ⑥CLOSED（15:00 后）⑦`can_submit` 组合（竞价限价 True / 市价 False）⑧`next_trading_day` 跨周末 + 时区边界 |
| `test_p053_corporate_actions.py` | 8 | ①现金分红 ②送股 ③拆股 ④配股（不扣现金）⑤`load_actions` 缺列 `ValueError` ⑥`actions_for` 日期过滤 ⑦`attribute_break` 现金归因 → MISSED ⑧`attribute_break` 未知资产 → 原样返回 |
| `test_p053_end_to_end.py` | 6 | ①submit 全链（gate→reserve→adapter→audit.order+outbox）②拒单链（release + on_order_result + audit）③Terminal 清单 + `import_fills` 入账 ④完整日循环（submit→poll fill→reconcile OK）⑤崩溃重启恢复（新 store 读回 orders + ledger）⑥对账 unresolved → `state=HALTED` |

**合计**：10+14+14+6+12+8+8+8+6 = **86**。

---

## 5. 与 DESIGN 的偏差与补齐（Step 6 复核清单）

| # | 偏差/补齐 | 说明 | 处置 |
|---|---|---|---|
| **D-1** | `TradingGateway.__init__` 增 `cost_buffer: float = 0.005` | DESIGN §5 要求「买入预留缓冲可配」，但 §3.8 签名未列 | 采纳；**已回写 DESIGN §3.8 签名**（Step 6） |
| **D-2** | `Ledger.cash_adjust(...)` 新增 | DESIGN §3.3 记账表提到「显式 `cash_adjust`」但 `Ledger` 无方法 | 采纳（幂等键 `cash_adjust:{ref}`，参数 `delta`=现金变动）；**已回写 DESIGN §3.3**（Step 6 F-I3 统一口径） |
| **D-3** | `_apply_lot` / `overall_level_breaks` 为内部辅助 | pseudocode 未列，属实现细节 | 采纳（不导出） |
| **D-4** | `reconcile_positions` 返回 `as_of=0.0` | 纯函数不持时钟（I1） | 采纳；调用方（gateway）按需替换 `as_of` |
| **D-5** | `poll()` 实现内 `applied` 语义 | DESIGN 声明返回 `list[LedgerEntry]`，实现取本轮新增 entry | 采纳；**Step 6 已定口径**：`len(entries())` 前后差切片（不改 apply_fill 的 bool 契约） |
| **D-6** | `DaySession.pre_open` 与 DESIGN §3.6 一致 | Step 6 核对：DESIGN L409 已含 pre_open | 闭合（无需回写） |
| **D-7** | `Ledger.resume()` / `initial_cash` / `attach_store` 新增 | 崩溃恢复（E2E ⑤）需重建运行账本并防 fill 重放（Step 6 F-I10） | 采纳；已回写 DESIGN §3.3 |
| **D-8** | `gateway.ingest_fills()` / `_throttle_query()` 新增 | Terminal 回填入口与查询桶实现（Step 6 F-I12/F-I8） | 采纳；已回写 DESIGN §3.8 |
| **D-9** | CTP `supports_client_order_id` False→**True** | §3.8 自主通道 need 含 `client_order_id`，False 则 CTP 经网关 submit 必抛 `CapabilityError`（Step 10 F-R5-1，规格自身矛盾） | 采纳；本节 + CHECKLIST M10 已同步 |
| **D-10** | CTP `_refs` 落地 coid↔(FrontID,SessionID,OrderRef) | DESIGN §3.9 声明但原码未实现（Step 10 F-R5-5） | 采纳；submit 登记 + query_orders 反查 |
| **D-11** | start() `load_orders` 提前到远程回报回放环之前 | 原序回放环读空 `_orders`，from_query 回报静默丢弃（Step 10 F-R5-2） | 采纳；本节已同步 |
| **D-12** | submit/cancel 桶接 `resolve_limits` | D11 双层流控原只落 query 桶（Step 10 F-R5-4） | 采纳；C-5 注记 + 本节已同步 |
| **D-13** | `should_degrade` 改尾部连续语义 | 原实现历史 2 连闩锁，与 docstring「尾部连续」不符（Step 10 F-R5-9） | 采纳；T5 既有断言不变（bad-ok-bad→False / 追加→True） |
| **C 组** | C-1..C-12（§2） | 伪码 → 可执行语义的 12 项澄清 | Step 6 逐条复核 |

**零修改确认**：`core/*`、`live/safety_gate.py`、`live/safety_store.py`、`pyproject.toml` 全部不动（`git diff --stat` 应只含 13 新文件 + 9 测试）。

---

## 6. 实施顺序（Step 5 执行序 -- Step 9 落码按此分三组）

| 组 | 文件 | 出口 |
|---|---|---|
| **G1 语义层** | `channel.py` → `orders.py` → `session_calendar.py` → `corporate_actions.py`（`adjust_position` 先行） | `test_p053_channel_capability` + `test_p053_order_semantics` + `test_p053_session_calendar` 32 例全绿 |
| **G2 存储 + 对账** | `ledger.py` → `ledger_store.py` → `reconcile.py` | `test_p053_ledger` + `test_p053_ledger_store` + `test_p053_reconcile` 32 例全绿 |
| **G3 适配器 + 网关 + 端到端** | `adapters/*`（5）→ `gateway.py` | `test_p053_flow_recovery` + `test_p053_corporate_actions` + `test_p053_end_to_end` 22 例全绿 |

**每组完成即跑**：`python -m pytest tests/test_p053_<组>.py -q` → `black .` → `python -m mypy live/` → 全绿再进下一组。
**收口门禁**：pytest **1300** / `-k golden` **22** / mypy **141** / black **283** / `tests/*.py` **141** / `core/*.py` **51** / `live/*.py` **16**；`grep -rn "import pandas\|import numpy\|from filter\|from services" live/` 零命中（I7）。

---

## 7. Step 6 复审输入

1. §2 C-1..C-12 逐条：是否都能在码面上验证（不是「打算这么做」）；
2. §5 D-1..D-5 是否需回写 DESIGN；
3. C-2 的「有符号量」等式与 DESIGN I4 的买/卖分组式**代数等价**（需验算）；
4. C-5 三桶 `RateLedger` 是否满足「先 check 后 record」，查询桶不 `record` 是否影响 `daily_orders`；
5. `ledger.replay` 对 `corporate_action` 的 `ratio` 反推是否与 `adjust_position` 的 `avg_cost/(1+r)` 等价（需反例检查）；
6. 86 例映射是否与 DESIGN §7 逐文件一一对应（10/14/14/6/12/8/8/8/6）。
