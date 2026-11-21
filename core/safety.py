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


def decide_fault(policy: FaultPolicy, fault: FaultType, attempts: int) -> tuple[FaultAction, ...]:
    """确定性决策；``attempts`` = 同类故障连续发生次数（C-14）。"""
    actions = policy.actions.get(fault, ())
    if not actions:
        return ()
    limit = policy.max_retries.get(fault, 0)
    if actions[0] is FaultAction.RETRY and attempts < limit:
        return (FaultAction.RETRY,)
    return tuple(a for a in actions if a is not FaultAction.RETRY)
