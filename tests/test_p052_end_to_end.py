"""P-052 E 组：闸门 + Mock Bridge 端到端（E1-E4）。"""

from __future__ import annotations

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLimitConfig
from core.config import AssetType
from core.event_log import EventLog
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.live_bridge import MockLiveBridge
from core.safety import KillLevel, default_fault_policy
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

TS = 1_700_000_000.0


def _gate(tmp_path) -> SafetyGate:
    return SafetyGate(
        event_log=EventLog(log_path=tmp_path / "events.jsonl"),
        store=SafetyStateStore(tmp_path / "state.json"),
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=GuardPipeline([]),
    )


def _ctx() -> GuardContext:
    return GuardContext(
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


def _buy() -> OrderIntent:
    return OrderIntent(
        asset="AAA", asset_type=AssetType.STOCK, target_quantity=100, current_quantity=0
    )


def _sell() -> OrderIntent:
    return OrderIntent(
        asset="AAA", asset_type=AssetType.STOCK, target_quantity=0, current_quantity=100
    )


def _submit(gate: SafetyGate, intent: OrderIntent, bridge: MockLiveBridge, ts: float) -> bool:
    decision = gate.pre_trade_check(intent, _ctx(), account_id="ACC", strategy_id="S1", ts=ts)
    if decision.allowed:
        bridge.place_intents([intent], date=None)
    return decision.allowed


def test_e1_allowed_intent_reaches_bridge(tmp_path):
    """E1：放行 → Bridge 产生 1 笔订单。"""
    gate = _gate(tmp_path)
    bridge = MockLiveBridge()
    assert _submit(gate, _buy(), bridge, TS) is True
    assert len(bridge.get_placed_orders()) == 1
    assert bridge.get_placed_orders()[0]["action"] == "BUY"


def test_e2_kill_prevents_submission(tmp_path):
    """E2：kill 生效 → 不下单（平仓仍可下）。"""
    gate = _gate(tmp_path)
    bridge = MockLiveBridge()
    gate.gate_kill(KillLevel.GLOBAL, "", True, "manual", ts=TS)
    assert _submit(gate, _buy(), bridge, TS + 1) is False
    assert bridge.get_placed_orders() == []
    assert _submit(gate, _sell(), bridge, TS + 2) is True
    assert len(bridge.get_placed_orders()) == 1


def test_e3_halted_rejects_both_directions(tmp_path):
    """E3：连续拒单 → HALTED → 开平仓均被拒。"""
    gate = _gate(tmp_path)
    bridge = MockLiveBridge()
    for _ in range(5):
        gate.on_order_result(rejected=True, ts=TS)
    assert _submit(gate, _buy(), bridge, TS + 1) is False
    assert _submit(gate, _sell(), bridge, TS + 2) is False
    assert bridge.get_placed_orders() == []


def test_e4_kill_survives_restart(tmp_path):
    """E4：重启后 kill 仍生效。"""
    gate = _gate(tmp_path)
    gate.gate_kill(KillLevel.GLOBAL, "", True, "manual", ts=TS)
    restarted = _gate(tmp_path)
    bridge = MockLiveBridge()
    assert _submit(restarted, _buy(), bridge, TS + 1) is False
    assert bridge.get_placed_orders() == []
