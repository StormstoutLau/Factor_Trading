"""SQLite 仓储：WAL / 单写者 `.lock` / outbox 同库同事务（P-053 D6）。"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from live.ledger import LedgerEntry
from live.orders import OrderRecord, OrderState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_entry (
  entry_id TEXT PRIMARY KEY, kind TEXT NOT NULL, ts REAL NOT NULL, asset TEXT NOT NULL,
  quantity REAL NOT NULL, price REAL NOT NULL, amount REAL NOT NULL, fee REAL NOT NULL,
  ref TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_entry_ref ON ledger_entry(ref);
CREATE TABLE IF NOT EXISTS order_record (
  client_order_id TEXT PRIMARY KEY, broker_order_id TEXT NOT NULL, state TEXT NOT NULL,
  payload TEXT NOT NULL, updated_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (
  event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, payload TEXT NOT NULL,
  created_ts REAL NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
"""


class LedgerStore(Protocol):
    def append_entry(self, entry: LedgerEntry) -> bool: ...
    def entries(self) -> list[LedgerEntry]: ...
    def upsert_order(self, record: OrderRecord) -> None: ...
    def load_orders(self) -> list[OrderRecord]: ...
    def append_outbox(self, event_id: str, event_type: str, payload: str, ts: float) -> None: ...
    def pending_outbox(self) -> list[tuple[str, str, str, float]]: ...
    def mark_sent(self, event_id: str) -> None: ...
    def transaction(self): ...
    def close(self) -> None: ...


class SqliteLedgerStore:
    """单写者：同路径第二实例在 `.lock` 处失败（I8）。"""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_name(self._path.name + ".lock")
        self._lock_path = lock_path
        self._lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        self._conn = sqlite3.connect(
            str(self._path), isolation_level=None, check_same_thread=True, timeout=5.0
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._closed = False

    # ---------- ledger ----------

    def append_entry(self, entry: LedgerEntry) -> bool:
        with self.transaction():
            try:
                self._conn.execute(
                    "INSERT INTO ledger_entry VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        entry.entry_id,
                        entry.kind,
                        entry.ts,
                        entry.asset,
                        entry.quantity,
                        entry.price,
                        entry.amount,
                        entry.fee,
                        entry.ref,
                    ),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def entries(self) -> list[LedgerEntry]:
        rows = self._conn.execute(
            "SELECT entry_id,kind,ts,asset,quantity,price,amount,fee,ref "
            "FROM ledger_entry ORDER BY rowid"
        ).fetchall()
        return [LedgerEntry(*row) for row in rows]

    # ---------- orders ----------

    def upsert_order(self, record: OrderRecord) -> None:
        payload = json.dumps(asdict(record) | {"state": record.state.value}, sort_keys=True)
        with self.transaction():
            self._conn.execute(
                "INSERT INTO order_record VALUES (?,?,?,?,?) "
                "ON CONFLICT(client_order_id) DO UPDATE SET "
                "broker_order_id=excluded.broker_order_id, state=excluded.state, "
                "payload=excluded.payload, updated_ts=excluded.updated_ts",
                (
                    record.client_order_id,
                    record.broker_order_id,
                    record.state.value,
                    payload,
                    record.updated_ts,
                ),
            )

    def load_orders(self) -> list[OrderRecord]:
        rows = self._conn.execute("SELECT payload FROM order_record ORDER BY updated_ts").fetchall()
        out: list[OrderRecord] = []
        for (payload,) in rows:
            data = json.loads(payload)
            data["state"] = OrderState(data["state"])
            out.append(OrderRecord(**data))
        return out

    # ---------- outbox（本批只写，D16） ----------

    def append_outbox(self, event_id: str, event_type: str, payload: str, ts: float) -> None:
        with self.transaction():
            self._conn.execute(
                "INSERT OR IGNORE INTO outbox VALUES (?,?,?,?,0)",
                (event_id, event_type, payload, ts),
            )

    def pending_outbox(self) -> list[tuple[str, str, str, float]]:
        return self._conn.execute(
            "SELECT event_id,event_type,payload,created_ts FROM outbox "
            "WHERE sent=0 ORDER BY created_ts"
        ).fetchall()

    def mark_sent(self, event_id: str) -> None:
        with self.transaction():
            self._conn.execute("UPDATE outbox SET sent=1 WHERE event_id=?", (event_id,))

    # ---------- 事务与生命周期 ----------

    @contextmanager
    def transaction(self):
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._conn.close()
        os.close(self._lock_fd)
        try:
            os.unlink(self._lock_path)  # 先关连接再删锁（C-12）
        except FileNotFoundError:
            pass
