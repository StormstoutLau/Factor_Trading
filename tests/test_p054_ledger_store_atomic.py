"""P-054 A 组：store v2 组合写 / 迁移外原子性 / store-first / 只读 preflight（16 例）。"""

from __future__ import annotations

import sqlite3

import pytest

from live.events import OutboxEvent
from live.ledger import Ledger, LedgerEntry
from live.ledger_store import (
    OutboxEventConflict,
    SqliteLedgerStore,
    StoreReadOnlyError,
)
from live.orders import FillRecord, from_request, OrderRequest


def _entry(eid: str = "e1") -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid,
        kind="fill",
        ts=1.0,
        asset="AAA",
        quantity=10.0,
        price=10.0,
        amount=100.0,
        fee=0.0,
        ref="co1",
    )


def _event(eid: str = "ev1", payload: str = "p1") -> OutboxEvent:
    return OutboxEvent(
        event_id=eid,
        aggregate_type="order",
        aggregate_id="co1",
        event_type="order.accepted",
        payload=payload,
        created_ts=1.0,
    )


def _fill(key: str = "f1", *, fee: float = 0.0) -> FillRecord:
    return FillRecord(
        fill_key=key,
        client_order_id="co1",
        asset="AAA",
        side="BUY",
        quantity=10.0,
        price=10.0,
        fee=fee,
        ts=1.0,
    )


def _request() -> OrderRequest:
    return OrderRequest(
        asset="AAA",
        side="BUY",
        quantity=10.0,
        price=10.0,
        client_order_id="co1",
        account_id="ACC",
        strategy_id="S1",
        signal_ts=1.0,
    )


def test_a1_combo_write_inserts_entries_and_events(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    assert store.append_entries_with_events([_entry()], [_event()]) == 1
    assert len(store.entries()) == 1
    assert len(store.pending_outbox()) == 1
    store.close()


def test_a2_crash_probe_business_and_outbox_same_life(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    with pytest.raises(RuntimeError):
        with store.transaction():
            store._conn.execute(
                "INSERT INTO ledger_entry VALUES (?,?,?,?,?,?,?,?,?)",
                ("e1", "fill", 1.0, "AAA", 10.0, 10.0, 100.0, 0.0, "co1"),
            )
            store._conn.execute(
                "INSERT INTO outbox(event_id,aggregate_type,aggregate_id,event_type,payload,created_ts) "
                "VALUES (?,?,?,?,?,?)",
                ("ev1", "order", "co1", "order.accepted", "p1", 1.0),
            )
            raise RuntimeError("crash after business write")
    assert store.entries() == []
    assert store.pending_outbox() == []
    store.close()


def test_a3_fill_and_fee_entries_same_transaction(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger = Ledger(store=store, initial_cash=1000.0)
    assert ledger.apply_fill(_fill(fee=1.5)) is True
    entries = store.entries()
    assert len(entries) == 2
    assert {e.kind for e in entries} == {"fill", "fee"}
    store.close()


def test_a4_batch_append_idempotent(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    assert store.append_entries([_entry(), _entry("e2")]) == 2
    assert store.append_entries([_entry(), _entry("e2")]) == 0
    assert len(store.entries()) == 2
    store.close()


def test_a5_store_first_failure_leaves_memory_unchanged(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    ledger = Ledger(store=store, initial_cash=1000.0)

    def boom(*args, **kwargs):
        raise RuntimeError("store down")

    store.append_entries_with_events = boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        ledger.apply_fill(_fill())
    assert ledger.cash == pytest.approx(1000.0)
    assert ledger.entries() == []
    assert ledger.snapshot().positions == ()
    store.close()


def test_a6_batch_inserted_count_skips_duplicates(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    assert store.append_entries([_entry(), _entry(), _entry("e2")]) == 2
    store.close()


def test_a7_resume_replay_same_fill_key_no_double_count(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    first = Ledger(store=store, initial_cash=1000.0)
    assert first.apply_fill(_fill()) is True
    resumed = Ledger.resume(store.entries(), initial_cash=1000.0)
    resumed.attach_store(store)
    snapshot_before = resumed.snapshot()
    assert resumed.apply_fill(_fill()) is False
    assert resumed.cash == pytest.approx(snapshot_before.cash)
    assert resumed.snapshot().positions == snapshot_before.positions
    assert len(store.entries()) == 1
    store.close()


def test_a8_read_only_uninitialized(tmp_path):
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(path)
    conn.close()
    with pytest.raises(StoreReadOnlyError) as exc:
        SqliteLedgerStore(path, read_only=True)
    assert exc.value.reason == "uninitialized"


def test_a9_read_only_permission(tmp_path):
    with pytest.raises(StoreReadOnlyError) as exc:
        SqliteLedgerStore(tmp_path / "missing.db", read_only=True)
    assert exc.value.reason == "permission"


def test_a10_read_only_not_wal(tmp_path):
    path = tmp_path / "plain.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE outbox (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE);"
    )
    conn.close()
    with pytest.raises(StoreReadOnlyError) as exc:
        SqliteLedgerStore(path, read_only=True)
    assert exc.value.reason == "not_wal"


def test_a11_read_only_preflight_ok_and_reads(tmp_path):
    path = tmp_path / "ledger.db"
    writer = SqliteLedgerStore(path)
    writer.append_entries_with_events([_entry()], [_event()])
    writer.close()
    reader = SqliteLedgerStore(path, read_only=True)
    assert reader.is_read_only is True
    assert len(reader.entries()) == 1
    assert reader.max_outbox_seq() == 1
    reader.close()


def test_a12_read_only_rejects_write_transaction(tmp_path):
    path = tmp_path / "ledger.db"
    writer = SqliteLedgerStore(path)
    writer.close()
    reader = SqliteLedgerStore(path, read_only=True)
    with pytest.raises(StoreReadOnlyError):
        with reader.transaction():
            pass
    reader.close()


def test_a13_snapshot_contains_seq_orders_entries(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    record = from_request(_request(), ts=1.0)
    store.upsert_order_with_events(record, [_event()])
    store.append_entries([_entry()])
    snap = store.snapshot()
    assert snap.seq == 1
    assert [o.client_order_id for o in snap.orders] == ["co1"]
    assert [e.entry_id for e in snap.entries] == ["e1"]
    store.close()


def test_a14_snapshot_watermark_equals_max_seq(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1", "p1"), _event("ev2", "p2")])
    assert store.snapshot().seq == store.max_outbox_seq() == 2
    store.close()


def test_a15_event_conflict_rolls_back_business_write(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1", "p1")])
    other = from_request(_request(), ts=2.0)
    with pytest.raises(OutboxEventConflict):
        store.upsert_order_with_events(other, [_event("ev1", "different")])
    assert store.load_orders() == []
    store.close()


def test_a16_same_payload_idempotent_silent(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1", "p1")])
    store.append_outbox([_event("ev1", "p1")])
    assert len(store.pending_outbox()) == 1
    store.close()
