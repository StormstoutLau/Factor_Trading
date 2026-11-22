"""P-054 B 组：outbox v2 迁移 / seq / 冲突 / inbox / meta / purge（12 例）。"""

from __future__ import annotations

import sqlite3

import pytest

from live.events import OutboxEvent
from live.ledger_store import OutboxEventConflict, SqliteLedgerStore


def _event(eid: str = "ev1", payload: str = "p1") -> OutboxEvent:
    return OutboxEvent(
        event_id=eid,
        aggregate_type="order",
        aggregate_id="co1",
        event_type="order.accepted",
        payload=payload,
        created_ts=1.0,
    )


def _make_v1(path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        "CREATE TABLE ledger_entry (entry_id TEXT PRIMARY KEY, kind TEXT NOT NULL, ts REAL NOT NULL,"
        " asset TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL, amount REAL NOT NULL,"
        " fee REAL NOT NULL, ref TEXT NOT NULL);"
        "CREATE TABLE order_record (client_order_id TEXT PRIMARY KEY, broker_order_id TEXT NOT NULL,"
        " state TEXT NOT NULL, payload TEXT NOT NULL, updated_ts REAL NOT NULL);"
        "CREATE TABLE outbox (event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_ts REAL NOT NULL, sent INTEGER NOT NULL DEFAULT 0);"
    )
    conn.execute("INSERT INTO outbox VALUES ('ev3','order.status','p3',3.0,0)")
    conn.execute("INSERT INTO outbox VALUES ('ev1','order.accepted','p1',1.0,0)")
    conn.execute("INSERT INTO outbox VALUES ('ev2','fill.applied','p2',2.0,1)")
    conn.commit()
    conn.close()


def test_b1_fresh_db_creates_v2_schema(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    cols = {row[1] for row in store._conn.execute("PRAGMA table_info(outbox)")}
    assert "seq" in cols and "sent_ts" in cols and "aggregate_type" in cols
    assert store.get_meta("schema_version") == "2"
    store.close()


def test_b2_v1_to_v2_preserves_rowid_order(tmp_path):
    path = tmp_path / "ledger.db"
    _make_v1(path)
    store = SqliteLedgerStore(path)
    records = store.pending_outbox()
    assert [r.event_id for r in records] == ["ev3", "ev1"]
    assert [r.seq for r in records] == [1, 2]
    assert all(r.aggregate_type == "legacy" for r in records)
    assert store.get_meta("schema_version") == "2"
    store.close()


def test_b3_v2_reopen_skips_migration(tmp_path):
    path = tmp_path / "ledger.db"
    first = SqliteLedgerStore(path)
    first.append_outbox([_event()])
    first.close()
    second = SqliteLedgerStore(path)
    assert second.max_outbox_seq() == 1
    assert len(second.pending_outbox()) == 1
    second.close()


def test_b4_seq_never_reused_after_purge(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1")])
    seq = store.pending_outbox()[0].seq
    store.mark_sent(seq, 1.0)
    store.append_outbox([_event("ev2")])
    assert store.max_outbox_seq() == 2
    store.purge_outbox(10.0)
    store.append_outbox([_event("ev3")])
    assert [r.event_id for r in store.pending_outbox()] == ["ev2", "ev3"]
    assert store.max_outbox_seq() == 3
    store.close()


def test_b5_unsent_index_used(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    plan = " ".join(
        str(row)
        for row in store._conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM outbox WHERE sent=0 ORDER BY seq"
        )
    )
    assert "ix_outbox_unsent" in plan
    store.close()


def test_b6_event_conflict_raises(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1", "p1")])
    with pytest.raises(OutboxEventConflict):
        store.append_outbox([_event("ev1", "p2")])
    store.close()


def test_b7_same_payload_silent(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1", "p1"), _event("ev1", "p1")])
    assert len(store.pending_outbox()) == 1
    store.close()


def test_b8_inbox_dedup(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    assert store.inbox_has("ev1") is False
    store.mark_inbox("ev1", 1.0)
    store.mark_inbox("ev1", 2.0)
    assert store.inbox_has("ev1") is True
    rows = store._conn.execute("SELECT COUNT(*) FROM inbox").fetchone()[0]
    assert rows == 1
    store.close()


def test_b9_meta_read_write(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.set_meta("recovery_state", "complete")
    assert store.get_meta("recovery_state") == "complete"
    store.set_meta("recovery_state", "degraded_positions")
    assert store.get_meta("recovery_state") == "degraded_positions"
    store.close()


def test_b10_purge_only_sent_and_old(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1"), _event("ev2")])
    seq1 = store.pending_outbox()[0].seq
    store.mark_sent(seq1, 1.0)
    assert store.purge_outbox(0.0) == 0
    assert store.purge_outbox(2.0) == 1
    assert [r.event_id for r in store.pending_outbox()] == ["ev2"]
    store.close()


def test_b11_purge_never_deletes_max_seq(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1")])
    seq = store.pending_outbox()[0].seq
    store.mark_sent(seq, 1.0)
    assert store.purge_outbox(10_000.0) == 0
    assert store.max_outbox_seq() == seq
    store.close()


def test_b12_mark_sent_by_seq_and_idempotent(tmp_path):
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.append_outbox([_event("ev1")])
    seq = store.pending_outbox()[0].seq
    store.mark_sent(seq, 5.0)
    assert store.pending_outbox() == []
    row = store._conn.execute("SELECT sent, sent_ts FROM outbox WHERE seq=?", (seq,)).fetchone()
    assert row == (1, 5.0)
    store.mark_sent(seq, 9.0)
    assert (
        store._conn.execute("SELECT sent_ts FROM outbox WHERE seq=?", (seq,)).fetchone()[0] == 5.0
    )
    store.close()
