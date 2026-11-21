"""P-052 B 组：账户熔断（B1-B9）。"""

from __future__ import annotations

from core.circuit_breaker import (
    CircuitConfig,
    CircuitSnapshot,
    CircuitState,
    allows_close,
    allows_open,
    evaluate_circuit,
)


def test_b1_normal():
    """B1：无触发 → NORMAL。"""
    decision = evaluate_circuit(
        CircuitConfig(),
        CircuitSnapshot(day_start_equity=1000.0, peak_equity=1100.0, equity=1050.0),
    )
    assert decision.state is CircuitState.NORMAL
    assert decision.reason == ""


def test_b2_daily_loss_triggers_derisk():
    """B2：日亏损达 3% → DERISK_ONLY(daily_loss)。"""
    decision = evaluate_circuit(
        CircuitConfig(),
        CircuitSnapshot(day_start_equity=1000.0, peak_equity=1000.0, equity=960.0),
    )
    assert decision.state is CircuitState.DERISK_ONLY
    assert decision.reason == "daily_loss"


def test_b3_drawdown_triggers_derisk():
    """B3：回撤达 10% → DERISK_ONLY(max_drawdown)。"""
    decision = evaluate_circuit(
        CircuitConfig(),
        CircuitSnapshot(day_start_equity=800.0, peak_equity=1000.0, equity=890.0),
    )
    assert decision.state is CircuitState.DERISK_ONLY
    assert decision.reason == "max_drawdown"


def test_b4_consecutive_rejects_halted():
    """B4：连续拒单达 5 次 → HALTED。"""
    decision = evaluate_circuit(
        CircuitConfig(),
        CircuitSnapshot(day_start_equity=1000.0, equity=1000.0, consecutive_rejects=5),
    )
    assert decision.state is CircuitState.HALTED
    assert decision.reason == "consecutive_rejects"


def test_b5_severity_priority_halted_wins():
    """B5（D-1）：拒单 HALTED 优先于日亏损 DERISK_ONLY。"""
    decision = evaluate_circuit(
        CircuitConfig(),
        CircuitSnapshot(
            day_start_equity=1000.0,
            peak_equity=1000.0,
            equity=900.0,
            consecutive_rejects=6,
        ),
    )
    assert decision.state is CircuitState.HALTED
    assert decision.reason == "consecutive_rejects"


def test_b6_zero_baseline_not_triggered():
    """B6（F-D9）：基准权益 <=0 视为未触发。"""
    decision = evaluate_circuit(
        CircuitConfig(), CircuitSnapshot(day_start_equity=0.0, peak_equity=0.0, equity=0.0)
    )
    assert decision.state is CircuitState.NORMAL


def test_b7_equality_boundary_triggers():
    """B7：等号边界视为触发（>=）。"""
    cfg = CircuitConfig(daily_loss_pct=0.03, max_drawdown_pct=0.10)
    daily = evaluate_circuit(
        cfg, CircuitSnapshot(day_start_equity=1000.0, peak_equity=1000.0, equity=970.0)
    )
    assert daily.state is CircuitState.DERISK_ONLY
    drawdown = evaluate_circuit(
        cfg, CircuitSnapshot(day_start_equity=900.0, peak_equity=1000.0, equity=900.0)
    )
    assert drawdown.reason == "max_drawdown"


def test_b8_allows_open_only_normal():
    """B8：allows_open 仅 NORMAL 放行。"""
    cfg = CircuitConfig()
    normal = evaluate_circuit(cfg, CircuitSnapshot(day_start_equity=1000.0, equity=1000.0))
    derisk = evaluate_circuit(cfg, CircuitSnapshot(day_start_equity=1000.0, equity=900.0))
    assert allows_open(normal) is True
    assert allows_open(derisk) is False


def test_b9_allows_close_until_halted():
    """B9：DERISK_ONLY 允许平仓，HALTED 连平仓也停。"""
    cfg = CircuitConfig()
    derisk = evaluate_circuit(cfg, CircuitSnapshot(day_start_equity=1000.0, equity=900.0))
    halted = evaluate_circuit(cfg, CircuitSnapshot(consecutive_rejects=5))
    assert allows_close(derisk) is True
    assert allows_close(halted) is False
