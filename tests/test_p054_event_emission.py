"""P-054 C 组：6 类事件 / event_id / event_version / canonical / 对账仅审计（10 例）。"""

from __future__ import annotations

import json

import pytest

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLimitConfig
from core.event_log import EventLog, EventType
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.safety import default_fault_policy
from live.adapters.mock import FakeTransport, Frame, MockChannelAdapter
from live.channel import FillReport, OrderReport
from live.events import OutboxEventType
from live.flow_control import OrderFlowBudget
from live.gateway import TradingGateway
from live.ledger import Ledger
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest, OrderState
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

DAY = 1_700_000_000.0


def _make_gateway(tmp_path, *, transport=None, order_flow=None):
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
    ledger = Ledger(initial_cash=100_000.0)
    ledger.attach_store(store)
    adapter = MockChannelAdapter(transport or FakeTransport())
    gateway = TradingGateway(
        adapter=adapter,
        gate=gate,
        ledger=ledger,
        store=store,
        event_log=log,
        clock=lambda: DAY,
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        order_flow_budget=order_flow,
    )
    return gateway, store, log, adapter


def _submit(gateway, *, ts: float = DAY, coid: str = ""):
    intent = OrderIntent(asset="AAA", asset_type="stock", target_quantity=100, current_quantity=0)
    request = OrderRequest(
        asset="AAA",
        side="BUY",
        quantity=100.0,
        asset_type="stock",
        price=10.0,
        order_type="limit",
        client_order_id=coid,
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


def test_c1_accepted_event_fixed_v1(tmp_path):
    gateway, store, _log, _adapter = _make_gateway(tmp_path)
    result = _submit(gateway)
    events = store.pending_outbox()
    assert len(events) == 1
    assert events[0].event_type == OutboxEventType.ORDER_ACCEPTED
    assert events[0].event_id == f"order:{result.client_order_id}:accepted:v1"
    store.close()


def test_c2_rejected_event_on_counter_reject(tmp_path):
    transport = FakeTransport([Frame("reject", {"code": "E1", "reason": "bad"})])
    gateway, store, _log, _adapter = _make_gateway(tmp_path, transport=transport)
    result = _submit(gateway)
    assert result.accepted is False
    events = store.pending_outbox()
    assert [e.event_type for e in events] == [OutboxEventType.ORDER_REJECTED]
    assert events[0].event_id.endswith("rejected:v1")
    store.close()


def test_c3_cancel_success_emits_status_pending_cancel(tmp_path):
    transport = FakeTransport([Frame("ack", {"state": OrderState.NEW.value})])
    gateway, store, _log, _adapter = _make_gateway(tmp_path, transport=transport)
    result = _submit(gateway)
    assert gateway.cancel(result.client_order_id, ts=DAY + 1) is True
    types = [e.event_type for e in store.pending_outbox()]
    assert OutboxEventType.ORDER_STATUS in types
    status = [e for e in store.pending_outbox() if e.event_type == OutboxEventType.ORDER_STATUS][0]
    assert ":status:6:" in status.event_id
    assert OutboxEventType.ORDER_CANCELED not in types
    store.close()


def test_c4_cancel_rejected_event_on_budget_denial(tmp_path):
    transport = FakeTransport(
        [
            Frame("ack", {"state": OrderState.NEW.value}),
            Frame("ack", {"state": OrderState.NEW.value}),
        ]
    )
    gateway, store, _log, _adapter = _make_gateway(
        tmp_path, transport=transport, order_flow=OrderFlowBudget(max_per_sec=2, reserve_cancel=1)
    )
    first = _submit(gateway, ts=DAY, coid="co_first")
    second = _submit(gateway, ts=DAY + 1, coid="co_second")
    assert gateway.cancel_ex(first.client_order_id, ts=DAY + 2).accepted is True
    denied = gateway.cancel_ex(second.client_order_id, ts=DAY + 2)
    assert denied.accepted is False
    assert denied.reason == "rate_order_flow"
    assert any(
        e.event_type == OutboxEventType.ORDER_CANCEL_REJECTED for e in store.pending_outbox()
    )
    store.close()


def test_c5_fill_emits_only_fill_applied(tmp_path):
    gateway, store, _log, adapter = _make_gateway(tmp_path)
    result = _submit(gateway)
    adapter._transport.frames.append(
        Frame(
            "fill",
            {
                "fill_key": "f1",
                "client_order_id": result.client_order_id,
                "asset": "AAA",
                "side": "BUY",
                "quantity": 100.0,
                "price": 10.0,
                "fee": 0.0,
                "ts": DAY + 1,
            },
        )
    )
    assert len(gateway.poll(ts=DAY + 1)) == 1
    types = [e.event_type for e in store.pending_outbox()]
    assert types.count(OutboxEventType.FILL_APPLIED) == 1
    assert OutboxEventType.ORDER_STATUS not in types
    store.close()


def test_c6_event_version_increments_on_real_transitions(tmp_path):
    gateway, store, _log, adapter = _make_gateway(tmp_path)
    result = _submit(gateway)
    coid = result.client_order_id
    adapter._transport.frames.append(
        Frame(
            "order",
            {
                "client_order_id": coid,
                "broker_order_id": "b1",
                "state": OrderState.NEW,
                "filled_quantity": 0.0,
                "avg_price": 0.0,
                "ts": DAY + 1,
            },
        )
    )
    gateway.poll(ts=DAY + 1)
    adapter._transport.frames.append(
        Frame(
            "order",
            {
                "client_order_id": coid,
                "broker_order_id": "b1",
                "state": OrderState.FILLED,
                "filled_quantity": 100.0,
                "avg_price": 10.0,
                "ts": DAY + 2,
            },
        )
    )
    gateway.poll(ts=DAY + 2)
    ids = [e.event_id for e in store.pending_outbox()]
    assert f"order:{coid}:status:0:v1" in ids
    assert f"order:{coid}:status:2:v2" in ids
    store.close()


def test_c7_payload_is_canonical_json(tmp_path):
    gateway, store, _log, _adapter = _make_gateway(tmp_path)
    _submit(gateway)
    payload = store.pending_outbox()[0].payload
    assert (
        json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        == payload
    )
    assert ": " not in payload
    store.close()


def test_c8_event_catalog_exactly_six(tmp_path):
    types = {
        OutboxEventType.ORDER_ACCEPTED,
        OutboxEventType.ORDER_REJECTED,
        OutboxEventType.ORDER_CANCELED,
        OutboxEventType.ORDER_CANCEL_REJECTED,
        OutboxEventType.ORDER_STATUS,
        OutboxEventType.FILL_APPLIED,
    }
    assert len(types) == 6
    assert not any("reconcile" in t for t in types)


def test_c9_reconcile_writes_audit_only(tmp_path):
    gateway, store, log, _adapter = _make_gateway(tmp_path)
    before = len(store.pending_outbox())
    gateway.reconcile(ts=DAY)
    assert len(store.pending_outbox()) == before
    assert any(e.type == EventType.AUDIT_RECONCILE for e in log.read())
    store.close()


def test_c10_old_payload_without_event_version_defaults_zero(tmp_path):
    gateway, store, _log, _adapter = _make_gateway(tmp_path)
    payload = json.dumps(
        {
            "client_order_id": "co_old",
            "broker_order_id": "b1",
            "asset": "AAA",
            "side": "BUY",
            "quantity": 100.0,
            "filled_quantity": 0.0,
            "avg_price": 0.0,
            "state": OrderState.NEW.value,
            "created_ts": DAY,
            "updated_ts": DAY,
        }
    )
    store._conn.execute(
        "INSERT INTO order_record VALUES (?,?,?,?,?)",
        ("co_old", "b1", OrderState.NEW.value, payload, DAY),
    )
    loaded = store.load_orders()
    assert loaded[0].event_version == 0
    store.close()
