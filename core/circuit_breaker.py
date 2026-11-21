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
    - 日亏损 ``>= daily_loss_pct`` → DERISK_ONLY ``reason=daily_loss``；
    - 回撤 ``>= max_drawdown_pct`` → DERISK_ONLY ``reason=max_drawdown``。
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
