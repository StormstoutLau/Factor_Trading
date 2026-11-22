"""P-053 T 组：SQLite 账本仓储（T4，6 例）。"""

from __future__ import annotations

import pytest

from live.ledger import LedgerEntry
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRecord, OrderState


def _entry(entry_id: str = "e1") -> LedgerEntry:
    return LedgerEntry(
        entry_id=entry_id,
        kind="fill",
        ts=1.0,
        asset="AAA",
        quantity=10.0,
        price=10.0,
        amount=100.0,
        fee=0.0,
        ref="co1",
    )


def _order() -> OrderRecord:
    return OrderRecord(
        client_order_id="co1",
        broker_order_id="b1",
        asset="AAA",
        side="BUY",
        quantity=100.0,
        filled_quantity=10.0,
        avg_price=10.0,
        state=OrderState.PARTIALLY_FILLED,
        created_ts=1.0,
        updated_ts=2.0,
    )


def test_t4_schema_creation_idempotent(tmp_path):
    path = tmp_path / "ledger.db"
    first = SqliteLedgerStore(path)
    first.close()
    second = SqliteLedgerStore(path)
    assert second.entries() == []
    second.close()


def test_t4_journal_mode_wal(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    store.close()


def test_t4_duplicate_entry_id_returns_false(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    assert store.append_entry(_entry()) is True
    assert store.append_entry(_entry()) is False
    assert len(store.entries()) == 1
    store.close()


def test_t4_outbox_rollback_same_transaction(tmp_path):
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
                ("ev1", "order", "co1", "audit.order", "co1", 1.0),
            )
            raise RuntimeError("boom")
    assert store.entries() == []
    assert store.pending_outbox() == []
    store.close()


def test_t4_second_instance_lock_fails(tmp_path):
    path = tmp_path / "ledger.db"
    first = SqliteLedgerStore(path)
    with pytest.raises(OSError):
        SqliteLedgerStore(path)
    first.close()


def test_t4_restart_reads_back_entries_and_orders(tmp_path):
    path = tmp_path / "ledger.db"
    entry = _entry()
    order = _order()
    first = SqliteLedgerStore(path)
    first.append_entry(entry)
    first.upsert_order(order)
    first.close()

    second = SqliteLedgerStore(path)
    assert second.entries() == [entry]
    orders = second.load_orders()
    assert len(orders) == 1
    assert orders[0].client_order_id == "co1"
    assert orders[0].state is OrderState.PARTIALLY_FILLED
    second.close()
