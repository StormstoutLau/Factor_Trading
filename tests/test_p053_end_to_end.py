"""P-053 T 组：端到端闭环（T9，6 例）。"""

from __future__ import annotations

import csv

import pytest

from core.circuit_breaker import CircuitConfig
from core.compliance import RateLimitConfig
from core.event_log import EventLog, EventType
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.safety import default_fault_policy
from live.adapters.mock import FakeTransport, Frame, MockChannelAdapter
from live.adapters.terminal import TerminalChannelAdapter
from live.channel import ChannelState, FillReport, PositionReport
from live.gateway import TradingGateway
from live.ledger import Ledger
from live.ledger_store import SqliteLedgerStore
from live.orders import FillRecord, OrderRequest
from live.reconcile import BreakLevel
from live.safety_gate import SafetyGate
from live.safety_store import SafetyStateStore

DAY = 1_700_000_000.0


def _make_gate(log: EventLog, tmp_path, name: str = "state.json") -> SafetyGate:
    return SafetyGate(
        event_log=log,
        store=SafetyStateStore(tmp_path / name),
        rate_config=RateLimitConfig(max_per_second=0, max_per_day=0),
        circuit_config=CircuitConfig(),
        fault_policy=default_fault_policy(),
        pipeline=GuardPipeline([]),
    )


def _make_gateway(tmp_path, *, adapter=None, log=None, ledger=None, name="ledger.db"):
    event_log = log or EventLog(log_path=tmp_path / "events.jsonl")
    gate = _make_gate(event_log, tmp_path)
    ledger = ledger or Ledger(initial_cash=100_000.0)
    store = SqliteLedgerStore(tmp_path / name)
    gateway = TradingGateway(
        adapter=adapter or MockChannelAdapter(),
        gate=gate,
        ledger=ledger,
        store=store,
        event_log=event_log,
        clock=lambda: DAY,
    )
    return gateway, gate, ledger, store, event_log


def _intent() -> OrderIntent:
    return OrderIntent(asset="AAA", asset_type="stock", target_quantity=100, current_quantity=0)


def _request() -> OrderRequest:
    return OrderRequest(
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


def _submit(gateway, *, ts: float = DAY):
    return gateway.submit(_intent(), _request(), _ctx(), account_id="ACC", strategy_id="S1", ts=ts)


def test_t9_submit_full_chain(tmp_path):
    gateway, _gate, ledger, store, log = _make_gateway(tmp_path)
    result = _submit(gateway)
    assert result.accepted is True
    assert ledger.cash == pytest.approx(100_000.0 - 1005.0)
    assert ledger.reserved == pytest.approx(1005.0)
    assert len(store.pending_outbox()) == 1
    assert EventType.AUDIT_ORDER in [entry.type for entry in log.read()]
    store.close()


def test_t9_reject_chain_releases_and_audits(tmp_path):
    transport = FakeTransport([Frame("reject", {"code": "E1", "reason": "bad"})])
    adapter = MockChannelAdapter(transport)
    gateway, gate, ledger, store, log = _make_gateway(tmp_path, adapter=adapter)
    calls: list[bool] = []
    original = gate.on_order_result

    def spy(*, rejected: bool, ts: float):
        calls.append(rejected)
        return original(rejected=rejected, ts=ts)

    gate.on_order_result = spy
    result = _submit(gateway)
    assert result.accepted is False
    assert ledger.cash == pytest.approx(100_000.0)
    assert ledger.reserved == pytest.approx(0.0)
    assert calls == [True]
    actions = [entry.payload.get("action") for entry in log.read(event_type=EventType.AUDIT_ORDER)]
    assert "rejected" in actions
    store.close()


def test_t9_terminal_listing_and_import_fills(tmp_path):
    log = EventLog(log_path=tmp_path / "events.jsonl")
    order_csv = tmp_path / "orders.csv"
    adapter = TerminalChannelAdapter(order_csv, event_log=log, ts_provider=lambda: DAY)
    gateway, _gate, ledger, store, _log = _make_gateway(tmp_path, adapter=adapter, log=log)
    result = _submit(gateway)
    assert result.accepted is True

    with order_csv.open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.reader(fp))
    assert rows[0][0] == "ts"
    assert rows[0][1] == "client_order_id"
    assert rows[1][1] == result.client_order_id

    fills_csv = tmp_path / "fills.csv"
    fills_csv.write_text(
        "fill_key,client_order_id,asset,side,quantity,price,fee,ts\n"
        f"f1,{result.client_order_id},AAA,BUY,100,10,0,{DAY}\n",
        encoding="utf-8",
    )
    reports = adapter.import_fills(fills_csv)
    applied = gateway.ingest_fills(reports)
    assert len(applied) == 1
    position = {p.asset: p for p in ledger.snapshot().positions}["AAA"]
    assert position.quantity == pytest.approx(100.0)
    store.close()


def test_t9_full_day_loop_submit_poll_reconcile(tmp_path):
    transport = FakeTransport()
    adapter = MockChannelAdapter(transport)
    gateway, _gate, ledger, store, _log = _make_gateway(tmp_path, adapter=adapter)
    gateway.start()
    result = _submit(gateway)
    transport.frames.append(
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
                "ts": DAY + 1.0,
            },
        )
    )
    applied = gateway.poll(ts=DAY + 1.0)
    assert len(applied) == 1
    position = {p.asset: p for p in ledger.snapshot().positions}["AAA"]
    assert position.quantity == pytest.approx(100.0)
    adapter.query_positions = lambda: [PositionReport("AAA", 100.0)]
    report = gateway.reconcile(ts=DAY + 2.0)
    assert report.level is BreakLevel.OK
    store.close()


def test_t9_crash_restart_recovers_orders_and_ledger(tmp_path):
    path = tmp_path / "ledger.db"
    first, _gate, ledger, store, _log = _make_gateway(tmp_path)
    first.start()
    result = _submit(first)
    first.ingest_fills(
        [
            FillReport(
                fill_key="f1",
                client_order_id=result.client_order_id,
                asset="AAA",
                side="BUY",
                quantity=100.0,
                price=10.0,
                fee=0.0,
                ts=DAY + 1.0,
            )
        ]
    )
    first.shutdown()

    restarted_log = EventLog(log_path=tmp_path / "events2.jsonl")
    adapter = MockChannelAdapter()
    adapter.query_positions = lambda: [PositionReport("AAA", 100.0)]
    restored_ledger = Ledger(initial_cash=100_000.0)
    store2 = SqliteLedgerStore(path)
    second = TradingGateway(
        adapter=adapter,
        gate=_make_gate(restarted_log, tmp_path, "state2.json"),
        ledger=restored_ledger,
        store=store2,
        event_log=restarted_log,
        clock=lambda: DAY,
    )
    second.start()
    orders = store2.load_orders()
    assert len(orders) == 1
    assert orders[0].client_order_id == result.client_order_id
    live_lot = {p.asset: p for p in second._ledger.snapshot().positions}["AAA"]
    assert live_lot.quantity == pytest.approx(100.0)
    assert len(second._ledger.entries()) == 1
    store2.close()


def test_t9_reconcile_unresolved_halts(tmp_path):
    transport = FakeTransport()
    adapter = MockChannelAdapter(transport)
    gateway, _gate, ledger, store, _log = _make_gateway(tmp_path, adapter=adapter)
    gateway.start()
    ledger.apply_fill(
        FillRecord(
            fill_key="f1",
            client_order_id="c1",
            asset="AAA",
            side="BUY",
            quantity=1000.0,
            price=10.0,
            fee=0.0,
            ts=DAY,
        )
    )
    report = gateway.reconcile(ts=DAY + 1.0)
    assert report.level is BreakLevel.UNRESOLVED
    assert adapter.state is ChannelState.HALTED
    store.close()
