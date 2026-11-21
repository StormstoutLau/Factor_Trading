"""P-052 L 组：SafetyGate 组合闸门（L1-L10）。"""

from __future__ import annotations

from core.circuit_breaker import CircuitConfig, CircuitState
from core.compliance import RateLimitConfig
from core.config import AssetType
from core.event_log import EventLog, EventType
from core.execution_policy import OrderIntent
from core.guard_pipeline import Guard, GuardContext, GuardPipeline, MaxOrderValueGuard
from core.live_bridge import MockLiveBridge
from core.safety import KillLevel, default_fault_policy
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

DAY1 = 1_700_000_000.0
DAY2 = DAY1 + 86_400.0


class _BoomGuard(Guard):
    """故意抛异常的 Guard（fail-closed 用例）。"""

    def __init__(self) -> None:
        super().__init__("BoomGuard", True)

    def check(self, ctx: GuardContext):
        raise RuntimeError("boom")


def _gate(tmp_path, *, pipeline=None, rate=None, circuit=None, store="state.json") -> SafetyGate:
    return SafetyGate(
        event_log=EventLog(log_path=tmp_path / "events.jsonl"),
        store=SafetyStateStore(tmp_path / store),
        rate_config=rate or RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=circuit or CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=pipeline if pipeline is not None else GuardPipeline([]),
    )


def _ctx(**overrides) -> GuardContext:
    base = dict(
        action="BUY",
        symbol="AAA",
        quantity=100.0,
        price=10.0,
        order_value=1000.0,
        current_positions={},
        current_weights={},
        portfolio_value=100_000.0,
        cash=100_000.0,
    )
    base.update(overrides)
    return GuardContext(**base)


def _buy() -> OrderIntent:
    return OrderIntent(
        asset="AAA", asset_type=AssetType.STOCK, target_quantity=100, current_quantity=0
    )


def _sell() -> OrderIntent:
    return OrderIntent(
        asset="AAA", asset_type=AssetType.STOCK, target_quantity=0, current_quantity=100
    )


def _hold() -> OrderIntent:
    return OrderIntent(
        asset="AAA", asset_type=AssetType.STOCK, target_quantity=50, current_quantity=50
    )


def _check(gate: SafetyGate, intent: OrderIntent, ts: float, **ctx_over):
    return gate.pre_trade_check(intent, _ctx(**ctx_over), account_id="ACC", strategy_id="S1", ts=ts)


def test_l1_pass_writes_audit(tmp_path):
    """L1：放行并写 audit.risk_decision。"""
    gate = _gate(tmp_path)
    decision = _check(gate, _buy(), ts=1000.0)
    assert decision.allowed is True
    assert decision.decision_id
    entries = gate._event_log.read(event_type=EventType.AUDIT_RISK_DECISION)
    assert len(entries) == 1
    assert entries[0].payload["allowed"] is True
    assert entries[0].payload["operator"] == "system"


def test_l2_kill_blocks_open_allows_close(tmp_path):
    """L2（S1）：kill 阻开仓、放行平仓。"""
    gate = _gate(tmp_path)
    gate.gate_kill(KillLevel.GLOBAL, "", True, "manual", ts=1000.0)
    opened = _check(gate, _buy(), ts=1001.0)
    assert opened.allowed is False
    assert "kill:global" in opened.reasons
    closed = _check(gate, _sell(), ts=1002.0)
    assert closed.allowed is True


def test_l3_derisk_only_blocks_open_halted_blocks_all(tmp_path):
    """L3（F-I1）：DERISK_ONLY 只阻开仓；HALTED 全停。"""
    gate = _gate(tmp_path)
    gate.update_equity(1_000_000.0, ts=DAY1)
    gate.update_equity(960_000.0, ts=DAY1)
    assert gate.circuit_decision.state is CircuitState.DERISK_ONLY
    assert _check(gate, _buy(), ts=DAY1 + 1).allowed is False
    assert _check(gate, _sell(), ts=DAY1 + 2).allowed is True
    for _ in range(5):
        gate.on_order_result(rejected=True, ts=DAY1)
    assert gate.circuit_decision.state is CircuitState.HALTED
    assert _check(gate, _sell(), ts=DAY1 + 3).allowed is False


def test_l4_rate_limit_blocks(tmp_path):
    """L4：速率超限阻断。"""
    gate = _gate(tmp_path, rate=RateLimitConfig(max_per_second=1, max_per_day=0))
    assert _check(gate, _buy(), ts=1000.0).allowed is True
    blocked = _check(gate, _buy(), ts=1000.0)
    assert blocked.allowed is False
    assert "rate:per_second" in blocked.reasons


def test_l5_guard_blocks(tmp_path):
    """L5：Guard 阻断透传原因。"""
    gate = _gate(tmp_path, pipeline=GuardPipeline([MaxOrderValueGuard(max_order_value=10.0)]))
    blocked = _check(gate, _buy(), ts=1000.0, order_value=1000.0)
    assert blocked.allowed is False
    assert any("Order value" in reason for reason in blocked.reasons)


def test_l6_guard_exception_fail_closed(tmp_path):
    """L6（D-G2）：Guard 异常 → fail-closed。"""
    gate = _gate(tmp_path, pipeline=GuardPipeline([_BoomGuard()]))
    blocked = _check(gate, _buy(), ts=1000.0)
    assert blocked.allowed is False
    assert any(reason.startswith("guard_error") for reason in blocked.reasons)


def test_l7_hold_is_allowed_and_not_counted(tmp_path):
    """L7：HOLD 特判放行且不消耗速率。"""
    gate = _gate(tmp_path, rate=RateLimitConfig(max_per_second=1, max_per_day=1))
    decision = _check(gate, _hold(), ts=1000.0)
    assert decision.allowed is True
    assert decision.action == "HOLD"
    assert decision.reasons == ("hold",)
    assert gate._ledger.daily_orders == 0


def test_l8_persist_and_restore(tmp_path):
    """L8（C-3/F-I3）：kill 与权益基准跨实例恢复。"""
    gate = _gate(tmp_path)
    gate.gate_kill(KillLevel.ACCOUNT, "ACC", True, "manual", ts=DAY1)
    gate.update_equity(1_000_000.0, ts=DAY1)
    gate.update_equity(960_000.0, ts=DAY1)
    restored = _gate(tmp_path)
    # ACCOUNT 级需显式账套上下文（pre_trade_check 注入）；GLOBAL 不受影响
    restored_decision = _check(restored, _buy(), ts=DAY1 + 1)
    assert restored_decision.allowed is False
    assert restored_decision.kill_level is KillLevel.ACCOUNT
    assert restored.circuit_decision.state is CircuitState.DERISK_ONLY


def test_l9_cancel_all_returns_count(tmp_path):
    """L9（F-D1）：cancel_all 走 bridge.cancel_orders(None) 返回笔数。"""
    gate = _gate(tmp_path)
    bridge = MockLiveBridge()
    bridge.place_intents([_buy(), _sell()], date=None)
    assert gate.cancel_all(bridge, ts=DAY1) == 2
    assert gate.cancel_all(bridge, ts=DAY1) == 0


def test_l10_equity_day_roll_resets_baseline(tmp_path):
    """L10（D-4）：跨日重置基线。"""
    gate = _gate(tmp_path)
    gate.update_equity(1_000_000.0, ts=DAY1)
    gate.update_equity(900_000.0, ts=DAY1)
    assert gate.circuit_decision.state is CircuitState.DERISK_ONLY
    gate.update_equity(900_000.0, ts=DAY2)
    assert gate.circuit_decision.state is CircuitState.NORMAL
