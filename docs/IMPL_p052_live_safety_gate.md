# IMPL：P-052 实盘安全闸门（safety / circuit_breaker / compliance / guard 扩展 / live 适配层）

> **批次**: P-052 · **Step 5 实施设计（逐处代码）** · 日期 2026-11-21
> **上游**: [DESIGN_p052](DESIGN_p052_live_safety_gate.md)（D1-D14 / I1-I12 / 70 例映射 / §5 阈值表）；[REVIEW_p052_step4](REVIEW_p052_step4_design.md)（GLM-5.3-Flash 异构 ✅，15/15 修复，0 P1 残留）
> **代码证据时点**: HEAD `1f950c6`（工作区仅 docs 改动）；本文仅新增文档，代码零改动
> **基座**: DeepSeek-V4.1-Flash（Step 6 复审须异构 GLM-5.3-Flash）

---

## 1. 变更总览

| # | 文件 | 变更 | 规模 |
|---|------|------|------|
| 1 | `core/safety.py` | **新建**：`KillLevel/KillAction/KillEntry/KillState/KillCommand/KillDecision` + 6 函数 + `FaultType/FaultAction/FaultPolicy` + `default_fault_policy/decide_fault` | ≈ 250 行 |
| 2 | `core/circuit_breaker.py` | **新建**：`CircuitState/CircuitConfig/CircuitSnapshot/CircuitDecision` + `evaluate_circuit/allows_open/allows_close` | ≈ 80 行 |
| 3 | `core/compliance.py` | **新建**：`AbnormalTradeType` + `ProgrammaticTradingReport` + `RateLimitConfig/RateLedger` + 5 函数 + `build_audit_payload` + 2 保留常量 | ≈ 230 行 |
| 4 | `core/guard_pipeline.py` | **扩展**：`GuardContext` +9 字段（带默认）；+5 Guard 类；+`GuardPipeline.live_safe()` | ≈ +230 行 |
| 5 | `core/engine_plugins.py` | **扩展**：`GuardPlugin.__init__` 增 `on_error: str = "open"`；异常分支按该参数决定放行/阻断 | ≈ +12 行 |
| 6 | `core/event_log.py` | **扩展**：`EventType` +8 审计常量 + 模块级 `AUDIT_EVENT_TYPES`（**不改** `EventLogEntry`/`append`） | ≈ +14 行 |
| 7 | `core/interfaces.py` | **扩展**：`AuthConfig` frozen dataclass（S5 契约，实现归 P-054） | ≈ +16 行 |
| 8 | `live/__init__.py` | **新建**：包声明（无逻辑） | ≈ 6 行 |
| 9 | `live/safety_store.py` | **新建**：`SafetyStateStore`（原子写 / 容错读） | ≈ 60 行 |
| 10 | `live/safety_gate.py` | **新建**：`SafetyDecision` + `SafetyGate`（kill→circuit→rate→guard + 审计 + 落盘） | ≈ 230 行 |
| 11 | `docs/RUNBOOK_p052_fault_handling.md` | **新建**：S7 故障处置与人工接管流程 | ≈ 90 行 |
| 12 | `.github/workflows/tests.yml` | **改 1 行**：mypy 目标增 `live`（[L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46) 现不含 `live`） | 1 行 |
| 13 | `tests/test_p052_*.py`（8 个） | **新建**：70 例（§3.12 映射） | ≈ 1150 行 |

**零改动**（I8）：`core/engine_v2.py`、`core/engine_v3_vector.py`、`core/sizing.py`、`core/stops.py`、`core/live_bridge.py`（只调用不改）、`filter/limit_rules.py`（只被上层消费）、`tests/_golden_cases.py`、22 条 golden、`core/__init__.py`。

**编码约束**：black `line-length=100`（[pyproject.toml L94-L96](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L94-L96)）；mypy `python_version=3.10`（[L109-L110](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L109-L110)）；全部模块 `from __future__ import annotations`。

**读数目标**：pytest **1144 → 1214**；`-k golden` **22 零重录**；mypy **122 → 125 files / 0 error**（+3 core；`live` 新纳入则 128）；black **247 → 261 unchanged**（+14 文件）。

---

## 2. IMPL 澄清（伪码 → 可执行语义，Step 6 须逐条复核）

| ID | 澄清点 | 实施口径 |
|----|--------|----------|
| **C-1** | `KillState` 持久化格式（DESIGN 只写 `to_dict/from_dict`） | `{"entries":[{"level","key","active","reason","operator","ts","blocked_actions":[str]}]}`；枚举存 `.value`，读回时 `KillLevel(raw)`/`KillAction(raw)`，未知值抛 `ValueError` 由 `SafetyGate._restore` 吞掉并回落 `initial_kill_state()` |
| **C-2** | I3「低层 disable 不解除高层」的落码方式 | `apply_command` **照常记录** `active=False` 条目（同 `(level,key)` 覆盖）；`effective_kill` 只取**最高 active 层**。故低层置 False 不会篡改高层条目，天然满足 I3，无需额外锁 |
| **C-3** | `SafetyGate` 落盘 schema | `{"kill":…, "ledger":…, "circuit":{"consecutive_rejects":int, "day_start_equity":float, "peak_equity":float, "equity":float}, "equity_day":"YYYY-MM-DD"}`（Step 6 F-I3：权益基准随快照持久化，防重启后当日亏损被遗忘）；`__init__` 末尾 `_restore()`，损坏/缺键**逐段**容错（不整文件丢弃） |
| **C-4** | `CircuitSnapshot` 谁维护（纯函数不得自带状态） | 纯函数只判定；`SafetyGate` 维护 `_snapshot`：`update_equity()` 按 `equity_day` 切日 → 重置 `day_start_equity=peak_equity=equity`，同日则更新 `equity` 与 `peak_equity=max(…)`。**新增方法见 D-4 偏差** |
| **C-5** | 秒级滑窗与跨日重置的精确定义 | `per_second` 只保留 `epoch_sec ∈ {ts-1, ts}` 两桶（仅作滑除）；`record()` 发现 `day_key(ts) != ledger.date` → `daily_orders/daily_cancels` 归零；`check_rate` 秒级判定**只查当前秒桶** `per_second.get(sec,0) >= max_per_second`（Step 6 F-I2 修订：原 `{sec-1, sec}` 求和使相邻秒互斥 = 1 笔/2 秒，与「≤1 笔/秒」不符） |
| **C-6** | `check_rate` 与 `record` 的调用顺序 | **先 check（基于已发生）后 record（本次计入）**；否则本次委托会把自己算进窗口，`max_per_second=1` 时首笔即被拒（自阻） |
| **C-7** | `GuardContext` 由谁填新字段 | 不新增工厂函数、不改 `create_guard_context_from_engine`（[L368-418](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L368-L418) 保持零改动）；调用方用 `dataclasses.replace(ctx, industry=…, limit_up=…)` 填充；`SafetyGate` 只刷新日计数（`_refresh_ctx`） |
| **C-8** | 8 审计常量 + `AUDIT_EVENT_TYPES` 落位 | **全部落 `core/event_log.py`**（`EventType` 类常量 + 模块级 frozenset）；`compliance.py` 不 import 任何项目内模块（**保 §2「三新 core 模块零项目内依赖」**）。见 D-2 偏差 |
| **C-9** | `build_audit_payload` 遇重复键 | `**fields` 含 `operator`/`time_source` → 抛 `ValueError`（禁止覆盖），不静默 |
| **C-10** | `pre_trade_check` 对 `HOLD` 的处理 | `intent.action == "HOLD"` → 立即 `allowed=True, reasons=("hold",)`，**不进入** kill/circuit/rate/guard、不写 rate ledger（HOLD 不产生委托），但仍写 `audit.risk_decision`（审计完整性） |
| **C-11** | 日累计上限计什么 | `max_per_day` 只计**新委托**（`daily_orders`）；撤单由 `cancel_ratio` 单独约束（避免双重计数）。`per_second` 计入所有委托申报 |
| **C-12** | `live_safe()` 各 Guard 参数默认 | `MaxPositionGuard(0.10)`、`MaxOrderValueGuard(1e6)`、`IndustryExposureGuard(0.30)`、`OrderRateGuard(1000)`、`MinCashGuard(0.05)`、`DrawdownGuard(0.10)`，`PriceBandGuard()`/`SelfTradeGuard()` 无参；与 §5 阈值表一致，可由调用方叠加覆盖 |
| **C-13** | 连续拒单计数口径 | `on_order_result(rejected=True)` → `+1`；`rejected=False` → 归零；判定用 `consecutive_rejects >= cfg.max_consecutive_rejects` |
| **C-14** | `decide_fault` 的 RETRY 前缀判定 | `actions[fault][0] is FaultAction.RETRY` 且 `attempts < max_retries[fault]` → 返回 `(RETRY,)`；否则返回 `actions[fault]` 去掉 RETRY 后的全量（确定性，无隐藏阈值） |
| **C-15** | `SafetyDecision.action` 取值 | 透传 `intent.action`（`BUY/SELL/SELL_SHORT/BUY_TO_COVER/HOLD`）；被阻断时仍保留原动作，仅 `allowed=False`，便于审计定位 |

---

## 3. 逐处代码

### 3.1 `core/safety.py`（新建，S1 + S7）

```python
"""安全闸门核心：三级 kill switch + 故障处置决策。

纯计算：无 I/O、无 ``datetime.now``、无随机（I1）。时间由调用方传入 ``ts``。

S1 三级 kill：GLOBAL > ACCOUNT > STRATEGY；低层 ``active=False`` 不解除高层（I3）。
S7 故障处置：``FaultPolicy`` 以数据承载重试阈值（I10），``decide_fault`` 确定性决策。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class KillLevel(str, Enum):
    """kill switch 层级。"""

    GLOBAL = "global"
    ACCOUNT = "account"
    STRATEGY = "strategy"


class KillAction(str, Enum):
    """被阻断的动作类别。"""

    OPEN = "open"
    CLOSE = "close"
    CANCEL = "cancel"


_LEVEL_ORDER: tuple[KillLevel, ...] = (KillLevel.GLOBAL, KillLevel.ACCOUNT, KillLevel.STRATEGY)


@dataclass(frozen=True)
class KillEntry:
    """单条 kill 记录。"""

    level: KillLevel
    key: str = ""
    active: bool = True
    reason: str = ""
    operator: str = ""
    ts: float = 0.0
    blocked_actions: tuple[KillAction, ...] = (KillAction.OPEN,)


@dataclass(frozen=True)
class KillState:
    """不可变快照。"""

    entries: tuple[KillEntry, ...] = ()


@dataclass(frozen=True)
class KillCommand:
    """外部下发的 kill 指令。"""

    level: KillLevel
    key: str
    active: bool
    reason: str
    operator: str
    ts: float
    blocked_actions: tuple[KillAction, ...] = (KillAction.OPEN,)


@dataclass(frozen=True)
class KillDecision:
    """一次判定的结果。"""

    blocked: bool
    level: KillLevel | None = None
    reason: str = ""
    blocked_actions: tuple[KillAction, ...] = ()


def initial_kill_state() -> KillState:
    """空状态（全部未激活）。"""
    return KillState()


def apply_command(state: KillState, cmd: KillCommand) -> tuple[KillState, KillEntry]:
    """纯函数：同 ``(level, key)`` 覆盖，其余条目保留。

    低层 ``active=False`` 只覆盖低层条目，不改高层——高层仍 active（I3）。
    """
    entry = KillEntry(
        level=cmd.level,
        key=cmd.key,
        active=cmd.active,
        reason=cmd.reason,
        operator=cmd.operator,
        ts=cmd.ts,
        blocked_actions=cmd.blocked_actions,
    )
    kept = [e for e in state.entries if not (e.level == cmd.level and e.key == cmd.key)]
    kept.append(entry)
    return KillState(entries=tuple(kept)), entry


def effective_kill(state: KillState, account_id: str, strategy_id: str) -> KillDecision:
    """返回最高 active 层级的阻断决策（GLOBAL > ACCOUNT > STRATEGY）。"""
    for level in _LEVEL_ORDER:
        key = ""
        if level is KillLevel.ACCOUNT:
            key = account_id
        elif level is KillLevel.STRATEGY:
            key = strategy_id
        for entry in state.entries:
            if entry.level == level and entry.key == key and entry.active:
                return KillDecision(
                    blocked=True,
                    level=level,
                    reason=entry.reason,
                    blocked_actions=entry.blocked_actions,
                )
    return KillDecision(blocked=False)


def allows(kill: KillDecision, action: KillAction) -> bool:
    """该动作是否被放行。"""
    if not kill.blocked:
        return True
    return action not in kill.blocked_actions


def to_dict(state: KillState) -> dict[str, Any]:
    """序列化（枚举存 value）。"""
    return {
        "entries": [
            {
                "level": e.level.value,
                "key": e.key,
                "active": e.active,
                "reason": e.reason,
                "operator": e.operator,
                "ts": e.ts,
                "blocked_actions": [a.value for a in e.blocked_actions],
            }
            for e in state.entries
        ]
    }


def from_dict(data: dict[str, Any]) -> KillState:
    """反序列化；未知枚举值抛 ``ValueError``（调用方负责容错）。"""
    entries: list[KillEntry] = []
    for raw in data.get("entries", []):
        entries.append(
            KillEntry(
                level=KillLevel(raw["level"]),
                key=str(raw.get("key", "")),
                active=bool(raw.get("active", False)),
                reason=str(raw.get("reason", "")),
                operator=str(raw.get("operator", "")),
                ts=float(raw.get("ts", 0.0)),
                blocked_actions=tuple(
                    KillAction(a) for a in raw.get("blocked_actions", [KillAction.OPEN.value])
                ),
            )
        )
    return KillState(entries=tuple(entries))


# ==================== S7 故障处置 ====================


class FaultType(str, Enum):
    """故障类型（总纲 §3.0 S7 四类）。"""

    DISCONNECT = "disconnect"
    REJECT = "reject"
    PARTIAL_FILL = "partial_fill"
    COUNTER_RESTART = "counter_restart"


class FaultAction(str, Enum):
    """处置动作。"""

    RETRY = "retry"
    PAUSE_NEW = "pause_new"
    CANCEL_ALL = "cancel_all"
    RECONCILE = "reconcile"
    HALT = "halt"
    RESUME = "resume"


@dataclass(frozen=True)
class FaultPolicy:
    """故障策略：动作序列 + 重试上限（阈值可配置，I10）。"""

    actions: dict[FaultType, tuple[FaultAction, ...]]
    max_retries: dict[FaultType, int]


def default_fault_policy() -> FaultPolicy:
    """默认策略（D-G4 / C-14）：断线重试 3 次后暂停新单并对账；柜台重启直接全撤+对账+停机。"""
    return FaultPolicy(
        actions={
            FaultType.DISCONNECT: (
                FaultAction.RETRY,
                FaultAction.PAUSE_NEW,
                FaultAction.RECONCILE,
            ),
            FaultType.REJECT: (FaultAction.RETRY, FaultAction.PAUSE_NEW),
            FaultType.PARTIAL_FILL: (FaultAction.RECONCILE,),
            FaultType.COUNTER_RESTART: (
                FaultAction.CANCEL_ALL,
                FaultAction.RECONCILE,
                FaultAction.HALT,
            ),
        },
        max_retries={
            FaultType.DISCONNECT: 3,
            FaultType.REJECT: 1,
            FaultType.PARTIAL_FILL: 0,
            FaultType.COUNTER_RESTART: 0,
        },
    )


def decide_fault(
    policy: FaultPolicy, fault: FaultType, attempts: int
) -> tuple[FaultAction, ...]:
    """确定性决策；``attempts`` = 同类故障连续发生次数（C-14）。"""
    actions = policy.actions.get(fault, ())
    if not actions:
        return ()
    limit = policy.max_retries.get(fault, 0)
    if actions[0] is FaultAction.RETRY and attempts < limit:
        return (FaultAction.RETRY,)
    return tuple(a for a in actions if a is not FaultAction.RETRY)
```

### 3.2 `core/circuit_breaker.py`（新建，S3）

```python
"""账户级熔断：日亏损 / 最大回撤 / 连续拒单 → 降级（纯计算，I1）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    """熔断状态。"""

    NORMAL = "normal"
    DERISK_ONLY = "derisk_only"
    HALTED = "halted"


@dataclass(frozen=True)
class CircuitConfig:
    """阈值（全部可配置，I10）。"""

    daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    max_consecutive_rejects: int = 5


@dataclass(frozen=True)
class CircuitSnapshot:
    """账户快照（由 ``SafetyGate`` 维护，C-4）。"""

    day_start_equity: float = 0.0
    peak_equity: float = 0.0
    equity: float = 0.0
    consecutive_rejects: int = 0


@dataclass(frozen=True)
class CircuitDecision:
    """熔断判定。"""

    state: CircuitState
    reason: str = ""
    alerts: tuple[str, ...] = ()


def evaluate_circuit(cfg: CircuitConfig, snap: CircuitSnapshot) -> CircuitDecision:
    """按严重度降序判定：HALTED 优先于 DERISK_ONLY（D-1 偏差，见 §4）。

    - ``consecutive_rejects >= max_consecutive_rejects`` → HALTED；
    - 日亏损 ``>= daily_loss_pct`` → DERISK_ONLY``reason=daily_loss``；
    - 回撤 ``>= max_drawdown_pct`` → DERISK_ONLY``reason=max_drawdown``。
    基准权益 <= 0 视为该项未触发（避免除零，F-D9）。
    """
    if cfg.max_consecutive_rejects > 0 and snap.consecutive_rejects >= cfg.max_consecutive_rejects:
        return CircuitDecision(
            state=CircuitState.HALTED,
            reason="consecutive_rejects",
            alerts=(f"consecutive_rejects:{snap.consecutive_rejects}",),
        )
    if snap.day_start_equity > 0:
        loss = (snap.day_start_equity - snap.equity) / snap.day_start_equity
        if loss >= cfg.daily_loss_pct:
            return CircuitDecision(
                state=CircuitState.DERISK_ONLY,
                reason="daily_loss",
                alerts=(f"daily_loss:{loss:.4f}",),
            )
    if snap.peak_equity > 0:
        drawdown = (snap.peak_equity - snap.equity) / snap.peak_equity
        if drawdown >= cfg.max_drawdown_pct:
            return CircuitDecision(
                state=CircuitState.DERISK_ONLY,
                reason="max_drawdown",
                alerts=(f"max_drawdown:{drawdown:.4f}",),
            )
    return CircuitDecision(state=CircuitState.NORMAL)


def allows_open(decision: CircuitDecision) -> bool:
    """NORMAL 才允许开仓。"""
    return decision.state is CircuitState.NORMAL


def allows_close(decision: CircuitDecision) -> bool:
    """HALTED 连平仓也停（需人工接管）。"""
    return decision.state is not CircuitState.HALTED
```

### 3.3 `core/compliance.py`（新建，S4 + S6 辅助）

```python
"""合规报告与速率台账（纯计算，I1）。

S4：程序化交易报告 schema（细则第九条 6 类 + 第三十四条 3 项）、异常交易枚举、
速率台账（默认 1 笔/秒、1000 笔/日 = D2 项目内部默认值，非监管要求）。
S6 辅助：``build_audit_payload`` 强制注入 operator/time_source。

本模块**不 import 任何项目内模块**（C-8），审计常量统一在 ``core.event_log``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AbnormalTradeType(str, Enum):
    """异常交易类型（细则第十八条四类 + 科创板补充四类）。"""

    INSTANT_ORDER_RATE = "instant_order_rate"
    FREQUENT_INSTANT_CANCEL = "frequent_instant_cancel"
    FREQUENT_PUSH_PULL = "frequent_push_pull"
    SHORT_TERM_LARGE_TRADE = "short_term_large_trade"
    FALSE_DECLARATION = "false_declaration"
    MAINTAIN_LIMIT_PRICE = "maintain_limit_price"
    SELF_TRADE = "self_trade"
    ABNORMAL_DECLARATION_RATE = "abnormal_declaration_rate"


@dataclass(frozen=True)
class ProgrammaticTradingReport:
    """程序化交易报告（第九条六类 + 第三十四条三项）。"""

    investor_name: str
    account_code: str
    member: str
    product_manager: str = ""
    capital_scale: float = 0.0
    capital_source: str = ""
    leverage_scale: float = 0.0
    leverage_source: str = ""
    leverage_ratio: float = 0.0
    strategy_type: str = ""
    strategy_desc: str = ""
    execution_mode: str = ""
    max_order_rate: int = 0
    max_daily_orders: int = 0
    software_name: str = ""
    software_version: str = ""
    developer: str = ""
    contact: str = ""
    contact_info: str = ""
    server_location: str | None = None
    system_test_report: str | None = None
    emergency_plan: str | None = None

    def missing_required(self) -> tuple[str, ...]:
        """第九条最小必填集为空/纯空白 → 返回字段名（F-D14）。"""
        required = (
            "investor_name",
            "account_code",
            "member",
            "strategy_type",
            "execution_mode",
            "software_name",
        )
        missing: list[str] = []
        for name in required:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                missing.append(name)
        return tuple(missing)


@dataclass(frozen=True)
class RateLimitConfig:
    """速率上限（D2 内部默认值，可配置）。"""

    max_per_second: int = 1
    max_per_day: int = 1000
    max_cancel_ratio: float | None = None
    min_cancel_samples: int = 20


@dataclass(frozen=True)
class RateLedger:
    """速率台账（不可变；由 ``record`` 推进）。"""

    date: str = ""
    per_second: dict[int, int] = field(default_factory=dict)
    daily_orders: int = 0
    daily_cancels: int = 0


def day_key(ts: float) -> str:
    """UTC 日键（不取 now，I1）。"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def record(ledger: RateLedger, ts: float, is_cancel: bool) -> RateLedger:
    """记录一次委托申报；跨日重置日累计（C-5）。"""
    day = day_key(ts)
    base = ledger if ledger.date == day else RateLedger(date=day)
    sec = int(ts)
    per_second = {k: v for k, v in base.per_second.items() if k >= sec - 1}
    per_second[sec] = per_second.get(sec, 0) + 1
    return RateLedger(
        date=day,
        per_second=per_second,
        daily_orders=base.daily_orders + (0 if is_cancel else 1),
        daily_cancels=base.daily_cancels + (1 if is_cancel else 0),
    )


def cancel_ratio(ledger: RateLedger) -> float:
    """撤单率 = 撤单数 / 新委托数；分母 0 → 0.0。"""
    if ledger.daily_orders <= 0:
        return 0.0
    return ledger.daily_cancels / ledger.daily_orders


def check_rate(
    ledger: RateLedger, ts: float, cfg: RateLimitConfig
) -> tuple[bool, str]:
    """返回 ``(allowed, reason)``；reason ∈ {"", "per_second", "per_day", "cancel_ratio"}。

    调用方须先 check 后 record（C-6），否则本次委托自阻。
    """
    if cfg.max_per_second > 0:
        sec = int(ts)
        if ledger.per_second.get(sec, 0) >= cfg.max_per_second:  # F-I2：只查当前秒桶
            return False, "per_second"
    if cfg.max_per_day > 0 and ledger.daily_orders >= cfg.max_per_day:
        return False, "per_day"
    if cfg.max_cancel_ratio is not None and ledger.daily_orders >= cfg.min_cancel_samples:
        if cancel_ratio(ledger) > cfg.max_cancel_ratio:
            return False, "cancel_ratio"
    return True, ""


def ledger_to_dict(ledger: RateLedger) -> dict[str, Any]:
    """序列化（键转字符串，JSON 友好；D-3）。"""
    return {
        "date": ledger.date,
        "per_second": {str(k): v for k, v in ledger.per_second.items()},
        "daily_orders": ledger.daily_orders,
        "daily_cancels": ledger.daily_cancels,
    }


def ledger_from_dict(data: dict[str, Any]) -> RateLedger:
    """反序列化；非法值抛 ``ValueError``/``TypeError`` 由调用方容错。"""
    return RateLedger(
        date=str(data.get("date", "")),
        per_second={int(k): int(v) for k, v in dict(data.get("per_second", {})).items()},
        daily_orders=int(data.get("daily_orders", 0)),
        daily_cancels=int(data.get("daily_cancels", 0)),
    )


def build_audit_payload(*, operator: str, time_source: str, **fields: Any) -> dict[str, Any]:
    """强制注入 operator/time_source；重复传入 → ``ValueError``（C-9）。"""
    if "operator" in fields or "time_source" in fields:
        raise ValueError("operator/time_source 由 build_audit_payload 强制注入，不得重复传入")
    payload: dict[str, Any] = {"operator": operator, "time_source": time_source}
    payload.update(fields)
    return payload


AUDIT_RETENTION_YEARS_DEFAULT = 5
AUDIT_RETENTION_YEARS_MAX = 20
```

### 3.4 `core/guard_pipeline.py`（扩展，S2）

**4.1 `GuardContext` 追加 9 字段**（置于 `config` 之后，全部带默认 → I11）：

```python
    # --- P-052 扩展（全部带默认，既有 6 Guard 行为不变） ---
    industry: str = ""
    industry_exposure: dict[str, float] = field(default_factory=dict)
    industry_limits: dict[str, float] = field(default_factory=dict)
    daily_order_count: int = 0
    daily_cancel_count: int = 0
    order_rate_config: dict[str, Any] = field(default_factory=dict)
    limit_up: Optional[float] = None
    limit_down: Optional[float] = None
    counterparty_open_orders: list[dict[str, Any]] = field(default_factory=list)
```

> `Any`/`field`/`Optional` 已在 [L22-23](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L22-L23) 导入，无需新增 import。

**4.2 五个 Guard**（追加在 `MinCashGuard` 之后、`GuardPipeline` 之前）：

```python
class MaxOrderValueGuard(Guard):
    """单笔金额上限（等于上限放行）。"""

    def __init__(self, max_order_value: float = 1_000_000.0, enabled: bool = True):
        super().__init__("MaxOrderValueGuard", enabled, {"max_order_value": max_order_value})
        self.max_order_value = max_order_value

    def check(self, ctx: GuardContext) -> GuardResult:
        if self.max_order_value <= 0:
            return GuardResult(passed=True, guard_name=self.name)
        if ctx.order_value > self.max_order_value:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Order value {ctx.order_value:,.0f} exceeds {self.max_order_value:,.0f}",
                severity="error",
            )
        return GuardResult(passed=True, guard_name=self.name)


class PriceBandGuard(Guard):
    """价格带（只读注入字段，不 import filter；D-G6 / F-D5）。"""

    def __init__(self, enabled: bool = True):
        super().__init__("PriceBandGuard", enabled)

    def check(self, ctx: GuardContext) -> GuardResult:
        if ctx.action == "BUY" and ctx.limit_up is not None and ctx.price > ctx.limit_up:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Buy price {ctx.price} above limit_up {ctx.limit_up}",
                severity="error",
            )
        if ctx.action == "SELL" and ctx.limit_down is not None and ctx.price < ctx.limit_down:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Sell price {ctx.price} below limit_down {ctx.limit_down}",
                severity="error",
            )
        if ctx.limit_up is None or ctx.limit_down is None:
            return GuardResult(
                passed=True,
                guard_name=self.name,
                message="Price band unavailable; passed with warning",
                severity="warning",
            )
        return GuardResult(passed=True, guard_name=self.name)


class IndustryExposureGuard(Guard):
    """行业暴露上限（portfolio_value<=0 → 跳过）。"""

    def __init__(self, default_industry_limit: float = 0.30, enabled: bool = True):
        super().__init__(
            "IndustryExposureGuard", enabled, {"default_industry_limit": default_industry_limit}
        )
        self.default_industry_limit = default_industry_limit

    def check(self, ctx: GuardContext) -> GuardResult:
        if ctx.action != "BUY" or not ctx.industry or ctx.portfolio_value <= 0:
            return GuardResult(passed=True, guard_name=self.name)
        limit = ctx.industry_limits.get(ctx.industry, self.default_industry_limit)
        current = ctx.industry_exposure.get(ctx.industry, 0.0)
        new_weight = current + ctx.order_value / ctx.portfolio_value
        if new_weight > limit:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Industry {ctx.industry} exposure {new_weight:.1%} > {limit:.1%}",
                severity="error",
            )
        return GuardResult(passed=True, guard_name=self.name)


class OrderRateGuard(Guard):
    """日笔数 + 撤单率（F-D6：分母 = daily_order_count，样本不足不判）。"""

    def __init__(
        self,
        max_daily_orders: int = 1000,
        max_cancel_ratio: Optional[float] = None,
        min_cancel_samples: int = 20,
        enabled: bool = True,
    ):
        super().__init__(
            "OrderRateGuard",
            enabled,
            {
                "max_daily_orders": max_daily_orders,
                "max_cancel_ratio": max_cancel_ratio,
                "min_cancel_samples": min_cancel_samples,
            },
        )
        self.max_daily_orders = max_daily_orders
        self.max_cancel_ratio = max_cancel_ratio
        self.min_cancel_samples = min_cancel_samples

    def check(self, ctx: GuardContext) -> GuardResult:
        cfg = ctx.order_rate_config or {}
        max_orders = int(cfg.get("max_daily_orders", self.max_daily_orders))
        if max_orders > 0 and ctx.daily_order_count >= max_orders:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Daily order count {ctx.daily_order_count} >= {max_orders}",
                severity="error",
            )
        ratio_limit = cfg.get("max_cancel_ratio", self.max_cancel_ratio)
        if ratio_limit is not None:
            min_samples = int(cfg.get("min_cancel_samples", self.min_cancel_samples))
            if ctx.daily_order_count >= min_samples and ctx.daily_order_count > 0:
                ratio = ctx.daily_cancel_count / ctx.daily_order_count
                if ratio > float(ratio_limit):
                    return GuardResult(
                        passed=False,
                        guard_name=self.name,
                        message=f"Cancel ratio {ratio:.1%} > {float(ratio_limit):.1%}",
                        severity="error",
                    )
        return GuardResult(passed=True, guard_name=self.name)


class SelfTradeGuard(Guard):
    """自成交（同价/穿价对手挂单；空列表放行）。"""

    def __init__(self, enabled: bool = True):
        super().__init__("SelfTradeGuard", enabled)

    def check(self, ctx: GuardContext) -> GuardResult:
        for order in ctx.counterparty_open_orders:
            side = str(order.get("side", "")).upper()
            raw_price = order.get("price")
            if raw_price is None:
                continue
            price = float(raw_price)
            if ctx.action == "BUY" and side == "SELL" and price <= ctx.price:
                return GuardResult(
                    passed=False,
                    guard_name=self.name,
                    message=f"Self-trade: counterparty sell {price} <= buy {ctx.price}",
                    severity="error",
                )
            if ctx.action == "SELL" and side == "BUY" and price >= ctx.price:
                return GuardResult(
                    passed=False,
                    guard_name=self.name,
                    message=f"Self-trade: counterparty buy {price} >= sell {ctx.price}",
                    severity="error",
                )
        return GuardResult(passed=True, guard_name=self.name)
```

**4.3 `GuardPipeline.live_safe()`**（追加在 `aggressive()` 之后，C-12）：

```python
    @classmethod
    def live_safe(cls) -> "GuardPipeline":
        """实盘安全预设（不含 Cooldown/Whitelist，可由调用方叠加）。"""
        return cls(
            [
                MaxPositionGuard(max_weight=0.10),
                PriceBandGuard(),
                MaxOrderValueGuard(max_order_value=1_000_000.0),
                IndustryExposureGuard(default_industry_limit=0.30),
                OrderRateGuard(max_daily_orders=1000),
                SelfTradeGuard(),
                MinCashGuard(min_cash_ratio=0.05),
                DrawdownGuard(max_drawdown=0.10),
            ]
        )
```

### 3.5 `core/engine_plugins.py`（扩展，D-G2）

```python
    def __init__(
        self,
        engine: Any,
        pipeline: Optional[GuardPipeline] = None,
        mode: str = "block",  # 'block' | 'warn'
        on_error: str = "open",  # 'open'（回测默认，P-026 D2.2）| 'closed'（实盘）
    ):
        ...
        self.on_error = on_error
```

异常分支（替换 [L244-247](file:///f:/Coding/Factor_Trading_v3.0/core/engine_plugins.py#L244-L247)）：

```python
        except Exception as e:
            self._error_count += 1
            if self.on_error == "closed":
                logger.warning(f"Guard 检查异常（已阻断）: {e}")
                return False, [f"guard_error: {e}"]
            logger.warning(f"Guard 检查异常（已放行）: {e}")
            return True, []
```

> 默认 `on_error="open"` → 既有回测与 `tests/test_p026_*` 行为不变（I8/I11）。

### 3.6 `core/event_log.py`（扩展，S6，C-8）

`EventType` 类内追加（[L50-57](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L50-L57)）：

```python
    # --- P-052 S6 审计（唯一来源；compliance 不重复定义） ---
    AUDIT_INTENT = "audit.intent"
    AUDIT_RISK_DECISION = "audit.risk_decision"
    AUDIT_ORDER = "audit.order"
    AUDIT_FILL = "audit.fill"
    AUDIT_CANCEL = "audit.cancel"
    AUDIT_RECONCILE = "audit.reconcile"
    AUDIT_KILL = "audit.kill"
    AUDIT_CIRCUIT = "audit.circuit"
```

类后追加：

```python
AUDIT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventType.AUDIT_INTENT,
        EventType.AUDIT_RISK_DECISION,
        EventType.AUDIT_ORDER,
        EventType.AUDIT_FILL,
        EventType.AUDIT_CANCEL,
        EventType.AUDIT_RECONCILE,
        EventType.AUDIT_KILL,
        EventType.AUDIT_CIRCUIT,
    }
)
```

> `EventLogEntry` 与 `append` 签名零改动（I12）；旧 JSONL 照常可读。

### 3.7 `core/interfaces.py`（扩展，S5 契约）

```python
from dataclasses import dataclass   # 追加于既有 import 段（imports 在 L9-15）


@dataclass(frozen=True)
class AuthConfig:
    """S5 鉴权与传输安全契约（本批只定契约；中间件实现归 P-054）。"""

    mode: str = "local"                 # "local" | "api_key" | "jwt"
    api_key_env: str = "FT_API_KEY"     # 密钥只经环境注入，不落配置文件
    bind_host: str = "127.0.0.1"        # 仅本机/内网
    require_tls: bool = False           # TLS 由 P-054 承载
    allowed_origins: tuple[str, ...] = ()
    enable_401_403: bool = True
```

### 3.8 `live/__init__.py`（新建）

```python
"""实盘适配层（P-052 最小实现）。

仅含 S1/S3 状态持久化与安全闸门；真实交易通道（QMT/券商 API/CTP）归 P-053。
依赖方向：``live → core``（总纲 L114/L286）；不 import ``filter``/``services``。
"""
```

### 3.9 `live/safety_store.py`（新建）

```python
"""安全状态落盘：临时文件 + ``os.replace`` 原子写；读失败返回 ``None``。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class SafetyStateStore:
    """kill/熔断/台账状态的最小持久化（单写者，风险表第 4 行）。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(self, data: dict[str, Any]) -> None:
        """原子写：同目录临时文件 → fsync → ``os.replace``。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".safety-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def load(self) -> dict[str, Any] | None:
        """不存在/损坏/非 dict → ``None``（不抛，交由调用方回落默认）。"""
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None
```

### 3.10 `live/safety_gate.py`（新建，S1/S3/S6 编排）

```python
"""实盘安全闸门：kill → circuit → rate → guard，全程审计与落盘。

fail-closed（D-G2）：任一检查异常 → ``allowed=False``。本类不自动平仓（D-G9/D12）。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace

from core.circuit_breaker import (
    CircuitConfig,
    CircuitDecision,
    CircuitSnapshot,
    CircuitState,
    allows_close,
    allows_open,
    evaluate_circuit,
)
from core.compliance import (
    RateLedger,
    RateLimitConfig,
    build_audit_payload,
    check_rate,
    day_key,
    ledger_from_dict,
    ledger_to_dict,
    record,
)
from core.event_log import EventType, IEventBus
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.live_bridge import LiveTradingBridge
from core.safety import (
    FaultPolicy,
    KillAction,
    KillCommand,
    KillDecision,
    KillEntry,
    KillLevel,
    KillState,
    allows,
    apply_command,
    effective_kill,
    from_dict,
    initial_kill_state,
    to_dict,
)

logger = logging.getLogger(__name__)

_SOURCE = "live.safety_gate"


@dataclass(frozen=True)
class SafetyDecision:
    """一次事前检查的结论。"""

    allowed: bool
    action: str
    reasons: tuple[str, ...] = ()
    decision_id: str = ""
    kill_level: KillLevel | None = None
    circuit_state: CircuitState = CircuitState.NORMAL


class SafetyGate:
    """组合 kill/circuit/rate/guard 的发单前闸门（单实例单写者）。"""

    def __init__(
        self,
        *,
        event_log: IEventBus,
        store: "SafetyStateStore",
        rate_config: RateLimitConfig,
        circuit_config: CircuitConfig,
        fault_policy: FaultPolicy,
        pipeline: GuardPipeline | None = None,
        operator: str = "system",
    ) -> None:
        self._event_log = event_log
        self._store = store
        self._rate_config = rate_config
        self._circuit_config = circuit_config
        self._fault_policy = fault_policy
        self._pipeline = pipeline or GuardPipeline.live_safe()
        self._operator = operator
        self._kill: KillState = initial_kill_state()
        self._ledger = RateLedger()
        self._snapshot = CircuitSnapshot()
        self._consecutive_rejects = 0
        self._equity_day = ""
        self._account_id = ""
        self._strategy_id = ""
        self._restore()

    # ---------- 属性 ----------

    @property
    def kill_decision(self) -> KillDecision:
        return effective_kill(self._kill, self._account_id, self._strategy_id)

    @property
    def circuit_decision(self) -> CircuitDecision:
        return evaluate_circuit(self._circuit_config, self._snapshot)

    # ---------- 核心：事前检查 ----------

    def pre_trade_check(
        self,
        intent: OrderIntent,
        ctx: GuardContext,
        *,
        account_id: str,
        strategy_id: str,
        ts: float,
        time_source: str = "local",
    ) -> SafetyDecision:
        """kill → circuit → rate → guard；任一阻断即返回并写 ``audit.risk_decision``。
        方向由 ``intent.action`` 推导（property，execution_policy.py L87-100）：
        BUY/SELL_SHORT=开、SELL/BUY_TO_COVER=平——kill 按 ``allows(OPEN/CLOSE)``、
        circuit 按 ``allows_open/close`` 分流（Step 6 F-I1：默认 kill 与 DERISK_ONLY
        均不得阻断平仓）。account_id/strategy_id 显式传参（F-D2）；价格/市值类输入
        以 ctx 为准（OrderIntent 无 price 字段，execution_policy.py L71-75）。"""
        decision_id = uuid.uuid4().hex
        action = intent.action
        self._account_id = account_id
        self._strategy_id = strategy_id
        circuit = self.circuit_decision
        if action == "HOLD":
            self._audit_decision(
                decision_id, True, action, account_id, strategy_id, None, circuit, ("hold",), time_source
            )
            return SafetyDecision(
                allowed=True,
                action=action,
                reasons=("hold",),
                decision_id=decision_id,
                circuit_state=circuit.state,
            )

        kill = self.kill_decision
        reasons: list[str] = []
        allowed = True
        # 方向分流（Step 6 F-I1）：由 intent.action 推导（execution_policy.py L87-100 property）
        # BUY/SELL_SHORT = 开仓方向；SELL/BUY_TO_COVER = 平仓方向。
        # 默认 kill（blocked_actions=(OPEN,)）只停开仓；DERISK_ONLY 放行平仓；HALTED 全停。
        is_open_direction = action in ("BUY", "SELL_SHORT")
        kill_action = KillAction.OPEN if is_open_direction else KillAction.CLOSE
        circuit_ok = allows_open(circuit) if is_open_direction else allows_close(circuit)
        if kill.blocked and not allows(kill, kill_action):
            allowed = False
            reasons.append(f"kill:{kill.level.value}" if kill.level else "kill")
        elif not circuit_ok:
            allowed = False
            reasons.append(f"circuit:{circuit.reason}")
        else:
            rate_ok, rate_reason = check_rate(self._ledger, ts, self._rate_config)
            if not rate_ok:
                allowed = False
                reasons.append(f"rate:{rate_reason}")
            else:
                try:
                    guard_reasons = self._pipeline.get_blocking_reasons(self._refresh_ctx(ctx))
                except Exception as exc:  # D-G2：实盘 fail-closed
                    logger.warning(f"Guard 检查异常（已阻断）: {exc}")
                    allowed = False
                    reasons.append(f"guard_error:{exc}")
                else:
                    if guard_reasons:
                        allowed = False
                        reasons.extend(guard_reasons)

        if allowed:
            self._ledger = record(self._ledger, ts, is_cancel=False)
            self._persist()

        self._audit_decision(
            decision_id,
            allowed,
            action,
            account_id,
            strategy_id,
            kill.level,
            circuit,
            tuple(reasons),
            time_source,
        )
        return SafetyDecision(
            allowed=allowed,
            action=action,
            reasons=tuple(reasons),
            decision_id=decision_id,
            kill_level=kill.level,
            circuit_state=circuit.state,
        )

    # ---------- S1 kill ----------

    def gate_kill(
        self, level: KillLevel, key: str, active: bool, reason: str, *, ts: float
    ) -> KillEntry:
        """更新 kill 状态 → 落盘 → ``audit.kill``。"""
        command = KillCommand(
            level=level, key=key, active=active, reason=reason, operator=self._operator, ts=ts
        )
        self._kill, entry = apply_command(self._kill, command)
        self._persist()
        self._event_log.append(
            EventType.AUDIT_KILL,
            build_audit_payload(
                operator=self._operator,
                time_source="local",
                level=level.value,
                key=key,
                active=active,
                reason=reason,
                blocked_actions=[a.value for a in entry.blocked_actions],
            ),
            source=_SOURCE,
        )
        return entry

    # ---------- S3 熔断 ----------

    def update_equity(self, equity: float, *, ts: float) -> CircuitDecision:
        """喂入账户权益并重评熔断（D-4 新增；按日切基准）。"""
        day = day_key(ts)
        snapshot = self._snapshot
        if snapshot.day_start_equity <= 0 or self._equity_day != day:
            snapshot = replace(snapshot, day_start_equity=equity, peak_equity=equity, equity=equity)
            self._equity_day = day
        else:
            snapshot = replace(
                snapshot, equity=equity, peak_equity=max(snapshot.peak_equity, equity)
            )
        self._snapshot = snapshot
        self._persist()
        return self.circuit_decision

    def on_order_result(self, *, rejected: bool, ts: float) -> CircuitDecision:
        """更新连续拒单 → 重评熔断 → ``audit.circuit``。
        ``ts`` 预留（F-I5）：审计事件时间由 ``EventLogEntry.ts`` 承载，payload 不重复携带。"""
        self._consecutive_rejects = self._consecutive_rejects + 1 if rejected else 0
        self._snapshot = replace(self._snapshot, consecutive_rejects=self._consecutive_rejects)
        decision = self.circuit_decision
        self._persist()
        self._event_log.append(
            EventType.AUDIT_CIRCUIT,
            build_audit_payload(
                operator=self._operator,
                time_source="local",
                state=decision.state.value,
                reason=decision.reason,
                alerts=list(decision.alerts),
                consecutive_rejects=self._consecutive_rejects,
            ),
            source=_SOURCE,
        )
        return decision

    # ---------- S1 一键撤单 ----------

    def cancel_all(self, bridge: LiveTradingBridge, *, ts: float) -> int:
        """调 ``cancel_orders(None)`` 撤全部未成交（D-G7；F-D1 按实际 API）。"""
        cancelled = int(bridge.cancel_orders(None))
        self._event_log.append(
            EventType.AUDIT_CANCEL,
            build_audit_payload(
                operator=self._operator,
                time_source="local",
                scope="all",
                cancelled_count=cancelled,
                ts=ts,
            ),
            source=_SOURCE,
        )
        return cancelled

    # ---------- 内部 ----------

    def _refresh_ctx(self, ctx: GuardContext) -> GuardContext:
        """用台账刷新日计数（C-7）。"""
        return replace(
            ctx,
            daily_order_count=max(ctx.daily_order_count, self._ledger.daily_orders),
            daily_cancel_count=max(ctx.daily_cancel_count, self._ledger.daily_cancels),
        )

    def _audit_decision(
        self,
        decision_id: str,
        allowed: bool,
        action: str,
        account_id: str,
        strategy_id: str,
        kill_level: KillLevel | None,
        circuit: CircuitDecision,
        reasons: tuple[str, ...],
        time_source: str,
    ) -> None:
        self._event_log.append(
            EventType.AUDIT_RISK_DECISION,
            build_audit_payload(
                operator=self._operator,
                time_source=time_source,
                decision_id=decision_id,
                allowed=allowed,
                action=action,
                account_id=account_id,
                strategy_id=strategy_id,
                kill_level=kill_level.value if kill_level else None,
                circuit_state=circuit.state.value,
                reasons=list(reasons),
            ),
            source=_SOURCE,
        )

    def _restore(self) -> None:
        """逐段容错恢复（C-3）；损坏段回落默认，不整文件丢弃。"""
        data = self._store.load()
        if not data:
            return
        kill_raw = data.get("kill")
        if isinstance(kill_raw, dict):
            try:
                self._kill = from_dict(kill_raw)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(f"kill 状态恢复失败，回落空状态: {exc}")
        ledger_raw = data.get("ledger")
        if isinstance(ledger_raw, dict):
            try:
                self._ledger = ledger_from_dict(ledger_raw)
            except (ValueError, TypeError) as exc:
                logger.warning(f"速率台账恢复失败，回落空台账: {exc}")
        circuit_raw = data.get("circuit")
        if isinstance(circuit_raw, dict):
            rejects = circuit_raw.get("consecutive_rejects")
            if isinstance(rejects, int) and rejects >= 0:
                self._consecutive_rejects = rejects
            raw_day = circuit_raw.get("day_start_equity", 0.0)
            raw_peak = circuit_raw.get("peak_equity", 0.0)
            raw_eq = circuit_raw.get("equity", 0.0)
            # F-I3：恢复权益基准，跨重启同日不重置（update_equity 按 equity_day 判日切）
            self._snapshot = CircuitSnapshot(
                day_start_equity=float(raw_day) if isinstance(raw_day, (int, float)) else 0.0,
                peak_equity=float(raw_peak) if isinstance(raw_peak, (int, float)) else 0.0,
                equity=float(raw_eq) if isinstance(raw_eq, (int, float)) else 0.0,
                consecutive_rejects=self._consecutive_rejects,
            )
        day = data.get("equity_day")
        if isinstance(day, str):
            self._equity_day = day

    def _persist(self) -> None:
        self._store.save(
            {
                "kill": to_dict(self._kill),
                "ledger": ledger_to_dict(self._ledger),
                "circuit": {
                    "consecutive_rejects": self._consecutive_rejects,
                    "day_start_equity": self._snapshot.day_start_equity,
                    "peak_equity": self._snapshot.peak_equity,
                    "equity": self._snapshot.equity,
                },
                "equity_day": self._equity_day,
            }
        )
```

> `SafetyStateStore` 用字符串注解避免循环导入担忧（实际 `live.safety_store` 不 import safety_gate，无环）；Step 9 可改直接 import 并去掉引号。

### 3.11 `docs/RUNBOOK_p052_fault_handling.md`（新建，S7，**Step 5 已落盘**）

结构（落地内容见 [RUNBOOK_p052](RUNBOOK_p052_fault_handling.md)）：

1. **四类故障处置表**：现象 → `decide_fault` 期望动作 → 人工动作（断线 3 次内自动重试；≥3 次暂停新单+对账；拒单 1 次暂停新增，连续拒单由熔断 `HALTED` 接管；部分成交对账；柜台重启全撤+对账+停机）。
2. **一键停机流程**：`gate_kill(GLOBAL, "", True, reason, ts)` → `cancel_all(bridge, ts=…)` → 核对 `audit.kill`/`audit.cancel` → 通知。
3. **恢复流程**：对账通过 → `gate_kill(GLOBAL, "", False, …)` → `on_order_result(rejected=False)` 清零 → 复核 `circuit_state == NORMAL`。
4. **演练记录模板**：日期/故障注入方式/`decision_id`/实际动作/耗时/结论（总纲 L165 出口）。
5. **升级路径**：`HALTED` 不自动恢复（需人工），`DERISK_ONLY` 允许平仓。

### 3.12 测试映射（70 例）

| 文件 | 用例 ID | 覆盖内容 |
|------|---------|----------|
| `tests/test_p052_safety_kill.py` | K1-K14 | K1 空状态不阻断；K2-K4 三级各自生效；K5-K6 GLOBAL>ACCOUNT>STRATEGY；K7 低层 disable 不解除高层（I3）；K8 同 (level,key) 覆盖；K9 blocked_actions 含 CLOSE 时阻断平仓；K10 `allows` 三类动作；K11-K12 `to_dict/from_dict` 往返 + 未知枚举抛错；K13-K14 `decide_fault` 断线/重启（含 attempts 边界） |
| `tests/test_p052_circuit_breaker.py` | B1-B9 | B1 NORMAL；B2 日亏损触发；B3 回撤触发；B4 连续拒单→HALTED；B5 优先级（拒单优先于亏损，D-1）；B6 基准 0 不触发（F-D9）；B7 等号边界；B8 `allows_open`；B9 `allows_close`（DERISK_ONLY True / HALTED False） |
| `tests/test_p052_compliance.py` | C1-C10 | C1 `missing_required` 全空 → 6 项；C2 必填齐全 → 空；C3 纯空白视为缺失；C4 秒级窗口阻断；C5 窗口过期放行；C6 日累计；C7 跨日重置（F-D10）；C8 撤单率样本不足不判；C9 撤单率超限；C10 保留常量 5/20 |
| `tests/test_p052_guard_extensions.py` | G1-G15 | G1-G2 MaxOrderValue 正/反（G2 等号放行）；G3-G5 PriceBand BUY/SELL/None warning；G6-G8 IndustryExposure 正/反/pv≤0 跳过；G9-G11 OrderRate 日笔数/撤单率/样本不足；G12-G14 SelfTrade 正/反/空列表；G15 `live_safe()` 组件与顺序 |
| `tests/test_p052_eventlog_audit.py` | A1-A6 | A1 8 常量值与 `AUDIT_EVENT_TYPES` 一致；A2 append 不改签名（I12）；A3 `audit.*` 可 replay；A4 seq 单调（I6）；A5 `build_audit_payload` 注入两键；A6 重复键抛 ValueError |
| `tests/test_p052_live_safety_gate.py` | L1-L10 | L1 放行写 risk_decision；L2 kill 阻断开仓 + **放行平仓**（默认 blocked_actions=(OPEN,)，F-I1）；L3 DERISK_ONLY 阻断 BUY 放行 SELL、HALTED 全停；L4 rate 阻断；L5 guard 阻断；L6 异常 fail-closed；L7 HOLD 特判；L8 落盘往返恢复（I4，**含权益基准** F-I3）；L9 `cancel_all` 返回笔数；L10 `update_equity` 切日重置 |
| `tests/test_p052_end_to_end.py` | E1-E4 | E1 BUY 意图→gate→MockLiveBridge 下单；E2 kill 后不下单；E3 连续拒单→HALTED 后拒单；E4 重启后 kill 仍生效 |
| `tests/test_p052_auth_contract.py` | S1-S2 | S1 `AuthConfig` 默认值；S2 `api_key_env` 注入约定 |
| **合计** | **70** | 与 DESIGN §7 一致 |

---

## 4. 与 DESIGN 的偏差与补齐（Step 6 复核清单）

| ID | 项 | DESIGN | IMPL | 理由 |
|----|----|--------|------|------|
| **D-1** | 熔断判定优先级 | `daily_loss > max_drawdown > consecutive_rejects`（§3.2） | **严重度优先**：`consecutive_rejects(HALTED)` 先判，再 `daily_loss`/`max_drawdown` | 按 DESIGN 原序，日亏损会**覆盖**已 HALTED 的状态，把「全停」降级为「只平不开」——安全倒挂。Step 6 须确认采用严重度优先并回写 DESIGN §3.2/§4 D4 |
| **D-2** | `AUDIT_EVENT_TYPES` 落位 | §3.3 放 `compliance.py` | 落 `core/event_log.py`（与 8 常量同文件） | 同时满足 F-D3「单一来源」与 DESIGN §2「三新 core 模块零项目内依赖」——否则 compliance 必须 import event_log，与依赖表冲突 |
| **D-3** | 台账序列化函数名 | §3.3 写 `to_dict / from_dict` | `ledger_to_dict / ledger_from_dict` | 避免与 `core/safety.py` 的同名函数在 `safety_gate` 内冲突（同模块 import 两个 `to_dict` 需别名，可读性差） |
| **D-4** | `SafetyGate` 方法集 | §3.6 只列 `pre_trade_check/gate_kill/on_order_result/cancel_all` + 2 属性 | **新增 `update_equity(equity, *, ts)`** | 熔断需要账户权益输入；`CircuitSnapshot` 由纯函数外维护（C-4）。缺此方法则 `DERISK_ONLY/HALTED` 永不触发 |
| **D-5** | 拒单故障升级动作 | §3.1「拒单→PAUSE_NEW(+HALT if 连续)」 | `REJECT` 只到 `PAUSE_NEW`，**不追加 HALT** | 连续拒单的 HALT 已由账户熔断（`consecutive_rejects`）承担；双轨会在同一事实上下发两个 HALT，审计重复且状态源不唯一 |
| **D-6** | mypy 覆盖 | 未提 | `.github/workflows/tests.yml` L46 增 `live` | 否则新增 `live/` 三文件不在类型门禁内 |

**DESIGN 已覆盖、无需补齐**：C-1..C-3/C-5..C-15 均为 DESIGN 留有空间或直接规定的实施细节，未改语义。

**Step 6 复审裁定（GLM-5.3-Flash，2026-11-21，异构 ✅）**：D-1..D-6 **全部采纳**——D-1 严重度优先正确并已回写 DESIGN §3.2/§4 D4；D-2 连带 F-I4 同步 DESIGN §3.3；D-5 单轨 HALT 与 RUNBOOK §1 一致；D-6 tests.yml 行经核验必要。另按复审修复 F-I1（方向分流）/ F-I2（秒桶判定）/ F-I3（权益基准持久化）回写本文 §2/§3/§5；详见 [REVIEW_p052_step6](REVIEW_p052_step6_impl.md)。

---

## 5. 实施顺序（Step 5 执行序）

1. `core/safety.py`（零依赖）→ 跑 K 组 14 例；
2. `core/circuit_breaker.py`（零依赖）→ 跑 B 组 9 例；
3. `core/compliance.py`（零依赖）→ 跑 C 组 10 例；
4. `core/event_log.py` 常量 + `core/interfaces.py` `AuthConfig` → 跑 A 组 6 例 + S 组 2 例；
5. `core/guard_pipeline.py` 扩展 → 跑 G 组 15 例 + **既有 guard 测试全绿**（I11）；
6. `core/engine_plugins.py` `on_error` → 跑 P-026 既有插件测试（默认 open 不变）；
7. `live/{__init__,safety_store,safety_gate}.py` → 跑 L 组 10 例；
8. `tests/test_p052_end_to_end.py` → 跑 E 组 4 例；
9. `docs/RUNBOOK_p052_fault_handling.md` 落盘；
10. 门禁：`pytest`（目标 1214）/ `-k golden`（22 零重录）/ `mypy`（125 files 0，含 `live` 则 128）/ `black`（**先格式化再 `--check`**，261 unchanged——F-I7：IMPL 代码含超 100 列行，以 black 输出为准）。

**风险预案**：
- 若 `core/event_log.py` 加常量引发 `EventLog` 既有测试失败 → 只可能是 `AUDIT_EVENT_TYPES` 命名冲突，改名或移入类内，不回退常量本身；
- 若 `live/` 触发 import-linter 依赖告警 → 检查是否误 import `filter`（D-G6/F-D5 明确禁止），退路是上层注入；
- 若 E 组 `MockLiveBridge` 下单断言不稳 → 以 `get_placed_orders()` 断言而非内部计数，不改 `live_bridge.py`（I8）。
