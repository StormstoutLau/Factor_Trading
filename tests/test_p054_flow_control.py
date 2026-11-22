"""P-054 D 组：FTD / order-flow 预算与发送前 reserve（16 例）。"""

from __future__ import annotations

import pytest

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLimitConfig
from core.event_log import EventLog
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.safety import default_fault_policy
from live.adapters.mock import FakeTransport, MockChannelAdapter
from live.channel import ChannelCapability, ChannelUnavailable
from live.flow_control import FtdBudget, OrderFlowBudget
from live.gateway import TradingGateway
from live.ledger import Ledger
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

DAY = 1_700_000_000.0


def test_d1_ftd_cancel_six_then_seventh_denied():
    budget = FtdBudget(max_per_sec=6, reserve=1)
    assert all(budget.try_reserve(DAY, cancel=True).allowed for _ in range(6))
    denied = budget.try_reserve(DAY, cancel=True)
    assert denied.allowed is False and denied.reason == "ftd"


def test_d2_ftd_submit_cannot_use_reserved_slot():
    budget = FtdBudget(max_per_sec=6, reserve=1)
    assert all(budget.try_reserve(DAY).allowed for _ in range(5))
    assert budget.try_reserve(DAY).allowed is False


def test_d3_retry_after_ms_positive():
    budget = FtdBudget(max_per_sec=1, reserve=0)
    assert budget.try_reserve(DAY).allowed is True
    denied = budget.try_reserve(DAY)
    assert 0 < denied.retry_after_ms <= 1000


def test_d4_ftd_window_resets_next_second():
    budget = FtdBudget(max_per_sec=6, reserve=1)
    for _ in range(6):
        budget.try_reserve(DAY, cancel=True)
    assert budget.try_reserve(DAY + 1.0, cancel=True).allowed is True


def test_d5_release_returns_slot():
    budget = FtdBudget(max_per_sec=1, reserve=0)
    assert budget.try_reserve(DAY).allowed
    assert budget.try_reserve(DAY).allowed is False
    budget.release()
    assert budget.try_reserve(DAY).allowed is True


def test_d6_order_flow_one_submit_plus_one_cancel_same_second():
    budget = OrderFlowBudget(max_per_sec=2, reserve_cancel=1)
    assert budget.try_reserve(DAY, kind="submit").allowed
    assert budget.try_reserve(DAY, kind="cancel").allowed


def test_d7_order_flow_third_operation_denied():
    budget = OrderFlowBudget(max_per_sec=2, reserve_cancel=1)
    assert budget.try_reserve(DAY, kind="submit").allowed
    assert budget.try_reserve(DAY, kind="cancel").allowed
    denied = budget.try_reserve(DAY, kind="submit")
    assert denied.allowed is False and denied.reason == "order_flow"


def test_d8_submit_cannot_use_cancel_reserved_slot():
    budget = OrderFlowBudget(max_per_sec=2, reserve_cancel=1)
    assert budget.try_reserve(DAY, kind="submit").allowed
    assert budget.try_reserve(DAY, kind="submit").allowed is False


def test_d9_per_type_bucket_caps_cancel_at_one_per_second():
    budget = OrderFlowBudget(max_per_sec=2, reserve_cancel=1)
    assert budget.try_reserve(DAY, kind="cancel").allowed
    denied = budget.try_reserve(DAY, kind="cancel")
    assert denied.allowed is False and denied.reason == "per_second"


def test_d10_order_flow_window_resets():
    budget = OrderFlowBudget(max_per_sec=2, reserve_cancel=1)
    budget.try_reserve(DAY, kind="submit")
    budget.try_reserve(DAY, kind="cancel")
    assert budget.try_reserve(DAY + 1.0, kind="submit").allowed


def _make_gateway(tmp_path, *, ftd=None, order_flow=None, transport=None):
    log = EventLog(log_path=tmp_path / "events.jsonl")
    gate = SafetyGate(
        event_log=log,
        store=SafetyStateStore(tmp_path / "state.json"),
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=GuardPipeline([]),
    )
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    adapter = MockChannelAdapter(transport or FakeTransport())
    gateway = TradingGateway(
        adapter=adapter,
        gate=gate,
        ledger=Ledger(initial_cash=100_000.0),
        store=store,
        event_log=log,
        clock=lambda: DAY,
        ftd_budget=ftd,
        order_flow_budget=order_flow,
    )
    return gateway, store, log, adapter


def _submit(gateway, *, ts: float = DAY):
    intent = OrderIntent(asset="AAA", asset_type="stock", target_quantity=100, current_quantity=0)
    request = OrderRequest(
        asset="AAA",
        side="BUY",
        quantity=100.0,
        asset_type="stock",
        price=10.0,
        order_type="limit",
        account_id="ACC",
        strategy_id="S1",
        signal_ts=DAY,
    )
    ctx = GuardContext(
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
    return gateway.submit(intent, request, ctx, account_id="ACC", strategy_id="S1", ts=ts)


def test_d11_gate_denied_budget_does_not_call_adapter(tmp_path):
    gateway, store, log, adapter = _make_gateway(
        tmp_path, order_flow=OrderFlowBudget(max_per_sec=1, reserve_cancel=1)
    )
    result = _submit(gateway)
    assert result.accepted is False
    assert result.reasons == ("rate_order_flow",)
    assert adapter._transport.sent == []
    assert gateway._ledger.cash == pytest.approx(100_000.0)
    actions = [e.payload.get("action") for e in log.read()]
    assert "rate_denied" in actions
    assert store.pending_outbox() == []
    store.close()


def test_d12_ftd_denied_reason(tmp_path):
    gateway, store, _log, _adapter = _make_gateway(
        tmp_path, ftd=FtdBudget(max_per_sec=1, reserve=1)
    )
    result = _submit(gateway)
    assert result.accepted is False
    assert result.reasons == ("rate_ftd",)
    store.close()


def test_d13_send_counts_even_when_counter_rejects(tmp_path):
    from live.adapters.mock import Frame

    transport = FakeTransport([Frame("reject", {"code": "E1", "reason": "bad"})])
    gateway, store, _log, _adapter = _make_gateway(
        tmp_path, ftd=FtdBudget(max_per_sec=2, reserve=1), transport=transport
    )
    assert _submit(gateway, ts=DAY).accepted is False
    assert gateway._ftd.remaining(DAY) == 0  # 拒单也消耗
    second = _submit(gateway, ts=DAY)
    assert second.reasons == ("rate_ftd",)
    store.close()


def test_d14_local_unavailable_releases_slot(tmp_path):
    class UnavailableAdapter(MockChannelAdapter):
        def submit(self, request):
            raise ChannelUnavailable("not sent")

    gateway, store, _log, _adapter = _make_gateway(
        tmp_path, ftd=FtdBudget(max_per_sec=2, reserve=1), transport=FakeTransport()
    )
    gateway._adapter = UnavailableAdapter()
    result = _submit(gateway, ts=DAY)
    assert result.reasons == ("channel_unavailable",)
    assert gateway._ftd.remaining(DAY) == 1
    store.close()


def test_d15_capability_declares_ftd_defaults():
    cap = ChannelCapability(
        channel_id="x",
        venue="ctp",
        account_level="cash",
        products=("future",),
        supports_client_order_id=True,
        supports_cancel=True,
        supports_query_orders=True,
        supports_query_trades=True,
        supports_query_positions=True,
        autonomous=True,
        report_registered=True,
        max_submit_per_sec=10.0,
        max_submit_per_day=1000,
        max_cancel_per_sec=10.0,
        max_query_per_sec=1.0,
    )
    assert cap.max_ftd_per_sec == 6.0
    assert cap.ftd_reserve == 1
    assert cap.startup_ftd_instructions == 2


def test_d16_rate_denied_audit_carries_reason(tmp_path):
    gateway, store, log, _adapter = _make_gateway(
        tmp_path, order_flow=OrderFlowBudget(max_per_sec=1, reserve_cancel=1)
    )
    _submit(gateway)
    entries = [e for e in log.read() if e.payload.get("action") == "rate_denied"]
    assert entries and entries[0].payload.get("reason") == "order_flow"
    store.close()
