"""SQLite 仓储 v2：组合写 / outbox seq / inbox / meta / 只读 preflight（P-054 B1）。

写者：WAL + ``synchronous=FULL`` + ``BEGIN IMMEDIATE`` + ``.lock`` 单写者。
读者：``mode=ro`` + ``query_only=ON`` + 跳过 ``.lock`` + 进程内 ``RLock``（D20）。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, Sequence

from live.events import OutboxEvent
from live.ledger import LedgerEntry
from live.orders import OrderRecord, OrderState

_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS ledger_entry (
  entry_id TEXT PRIMARY KEY, kind TEXT NOT NULL, ts REAL NOT NULL, asset TEXT NOT NULL,
  quantity REAL NOT NULL, price REAL NOT NULL, amount REAL NOT NULL, fee REAL NOT NULL,
  ref TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_entry_ref ON ledger_entry(ref);
CREATE TABLE IF NOT EXISTS order_record (
  client_order_id TEXT PRIMARY KEY, broker_order_id TEXT NOT NULL, state TEXT NOT NULL,
  payload TEXT NOT NULL, updated_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (
  seq            INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id       TEXT NOT NULL UNIQUE,
  aggregate_type TEXT NOT NULL,
  aggregate_id   TEXT NOT NULL,
  event_type     TEXT NOT NULL,
  payload        TEXT NOT NULL,
  created_ts     REAL NOT NULL,
  sent           INTEGER NOT NULL DEFAULT 0,
  sent_ts        REAL
);
CREATE INDEX IF NOT EXISTS ix_outbox_unsent ON outbox(sent, seq);
CREATE TABLE IF NOT EXISTS inbox (
  event_id     TEXT PRIMARY KEY,
  processed_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_SCHEMA_AUX = """
CREATE TABLE IF NOT EXISTS inbox (
  event_id     TEXT PRIMARY KEY,
  processed_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_V2_TABLE_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS ledger_entry (
  entry_id TEXT PRIMARY KEY, kind TEXT NOT NULL, ts REAL NOT NULL, asset TEXT NOT NULL,
  quantity REAL NOT NULL, price REAL NOT NULL, amount REAL NOT NULL, fee REAL NOT NULL,
  ref TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS ix_entry_ref ON ledger_entry(ref)",
    """CREATE TABLE IF NOT EXISTS order_record (
  client_order_id TEXT PRIMARY KEY, broker_order_id TEXT NOT NULL, state TEXT NOT NULL,
  payload TEXT NOT NULL, updated_ts REAL NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS outbox (
  seq            INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id       TEXT NOT NULL UNIQUE,
  aggregate_type TEXT NOT NULL,
  aggregate_id   TEXT NOT NULL,
  event_type     TEXT NOT NULL,
  payload        TEXT NOT NULL,
  created_ts     REAL NOT NULL,
  sent           INTEGER NOT NULL DEFAULT 0,
  sent_ts        REAL
)""",
    "CREATE TABLE IF NOT EXISTS inbox (event_id TEXT PRIMARY KEY, processed_ts REAL NOT NULL)",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


class OutboxEventConflict(RuntimeError):
    """同 ``event_id`` 不同 ``event_type`` / payload（I5）。"""


class StoreReadOnlyError(RuntimeError):
    """只读 store 不可用；``reason`` ∈ permission/uninitialized/not_wal/internal_api_required。"""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class OutboxRecord:
    seq: int
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: str
    created_ts: float
    sent_ts: float | None = None


@dataclass(frozen=True)
class StoreSnapshot:
    seq: int
    orders: tuple[OrderRecord, ...]
    entries: tuple[LedgerEntry, ...]


class LedgerStore(Protocol):
    def append_entry(self, entry: LedgerEntry) -> bool: ...
    def append_entries(self, entries: Sequence[LedgerEntry]) -> int: ...
    def append_entries_with_events(
        self, entries: Sequence[LedgerEntry], events: Sequence[OutboxEvent]
    ) -> int: ...
    def entries(self) -> list[LedgerEntry]: ...
    def upsert_order(self, record: OrderRecord) -> None: ...
    def upsert_order_with_events(
        self, record: OrderRecord, events: Sequence[OutboxEvent]
    ) -> None: ...
    def load_orders(self) -> list[OrderRecord]: ...
    def append_outbox(self, events: Sequence[OutboxEvent]) -> None: ...
    def pending_outbox(self, limit: int = 100) -> list[OutboxRecord]: ...
    def mark_sent(self, seq: int, ts: float) -> None: ...
    def outbox_after(self, after_seq: int, limit: int) -> list[OutboxRecord]: ...
    def max_outbox_seq(self) -> int: ...
    def purge_outbox(self, before_ts: float) -> int: ...
    def inbox_has(self, event_id: str) -> bool: ...
    def mark_inbox(self, event_id: str, ts: float) -> None: ...
    def get_meta(self, key: str) -> str | None: ...
    def set_meta(self, key: str, value: str) -> None: ...
    def snapshot(self) -> StoreSnapshot: ...
    def transaction(self): ...
    def close(self) -> None: ...


def _order_payload(record: OrderRecord) -> str:
    return json.dumps(asdict(record) | {"state": record.state.value}, sort_keys=True)


def _order_from_payload(payload: str) -> OrderRecord:
    data = json.loads(payload)
    data["state"] = OrderState(data["state"])
    return OrderRecord(**data)


class SqliteLedgerStore:
    """写者单实例（``.lock``）；读者 ``read_only=True`` 不建表、不拿锁（I1/I2）。"""

    def __init__(
        self, path: str | Path, *, read_only: bool = False, internal_api: bool = False
    ) -> None:
        self._path = Path(path)
        self._read_only = read_only
        self._closed = False
        self._write_lock = threading.RLock()
        self._read_lock = threading.RLock()
        self._lock_fd: int | None = None
        self._lock_path = self._path.with_name(self._path.name + ".lock")

        if read_only:
            if internal_api:
                raise StoreReadOnlyError("internal_api_required", "configure internal API fallback")
            self._conn = self._open_read_only()
            self._preflight()
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        self._conn = sqlite3.connect(
            str(self._path), isolation_level=None, check_same_thread=False, timeout=5.0
        )
        with self._write_lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._migrate()

    # ---------- 只读 ----------

    def _open_read_only(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                f"file:{self._path.as_posix()}?mode=ro",
                uri=True,
                isolation_level=None,
                check_same_thread=False,
                timeout=5.0,
            )
            conn.execute("PRAGMA query_only=ON")
            return conn
        except (sqlite3.OperationalError, PermissionError) as exc:
            raise StoreReadOnlyError("permission", str(exc)) from exc

    def _preflight(self) -> None:
        with self._read_lock:
            try:
                row = self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='outbox'"
                ).fetchone()
            except (sqlite3.OperationalError, PermissionError) as exc:
                raise StoreReadOnlyError("permission", str(exc)) from exc
            if row is None:
                raise StoreReadOnlyError(
                    "uninitialized", "outbox table missing; start trading_worker first"
                )
            mode = self._conn.execute("PRAGMA journal_mode").fetchone()
            if not mode or str(mode[0]).lower() != "wal":
                raise StoreReadOnlyError(
                    "not_wal", "journal_mode != wal; initialize via trading_worker"
                )
            self._conn.execute("SELECT COALESCE(MAX(seq),0) FROM outbox").fetchone()

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    # ---------- 迁移 ----------

    def _table_names(self) -> set[str]:
        return {
            str(row[0])
            for row in self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    def _get_meta_raw(self, key: str) -> str | None:
        if "meta" not in self._table_names():
            return None
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def _migrate(self) -> None:
        """三分支：无 outbox 表 → 建 v2；v1（无 seq）→ 迁移；v2 → 跳过（F-I5）。"""
        tables = self._table_names()
        if "outbox" not in tables:
            self._conn.executescript(_SCHEMA_V2)
            self._set_meta_locked("schema_version", "2")
            return
        cols = {str(row[1]) for row in self._conn.execute("PRAGMA table_info(outbox)")}
        if "seq" in cols:
            self._conn.executescript(_SCHEMA_AUX)
            self._conn.execute("CREATE INDEX IF NOT EXISTS ix_outbox_unsent ON outbox(sent, seq)")
            if self._get_meta_raw("schema_version") is None:
                self._set_meta_locked("schema_version", "2")
            return
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute("ALTER TABLE outbox RENAME TO outbox_v1")
            for statement in _V2_TABLE_STATEMENTS:  # 逐条执行：executescript 会隐式 COMMIT
                self._conn.execute(statement)
            self._conn.execute(
                "INSERT INTO outbox(event_id,aggregate_type,aggregate_id,event_type,payload,"
                "created_ts,sent,sent_ts) "
                "SELECT event_id,'legacy',event_id,event_type,payload,created_ts,sent,NULL "
                "FROM outbox_v1 ORDER BY rowid"
            )
            self._conn.execute("DROP TABLE outbox_v1")
            self._conn.execute("CREATE INDEX IF NOT EXISTS ix_outbox_unsent ON outbox(sent, seq)")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")
        self._set_meta_locked("schema_version", "2")

    # ---------- 分录 ----------

    def append_entry(self, entry: LedgerEntry) -> bool:
        return self.append_entries([entry]) == 1

    def append_entries(self, entries: Sequence[LedgerEntry]) -> int:
        return self.append_entries_with_events(entries, ())

    def append_entries_with_events(
        self, entries: Sequence[LedgerEntry], events: Sequence[OutboxEvent]
    ) -> int:
        inserted = 0
        with self._write_lock, self.transaction():
            for entry in entries:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO ledger_entry VALUES (?,?,?,?,?,?,?,?,?)",
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
                inserted += cur.rowcount
            for event in events:
                self._append_event_locked(event)
        return inserted

    def entries(self) -> list[LedgerEntry]:
        with self._read_guard():
            rows = self._conn.execute(
                "SELECT entry_id,kind,ts,asset,quantity,price,amount,fee,ref "
                "FROM ledger_entry ORDER BY rowid"
            ).fetchall()
        return [LedgerEntry(*row) for row in rows]

    # ---------- 订单 ----------

    def upsert_order(self, record: OrderRecord) -> None:
        with self._write_lock, self.transaction():
            self._upsert_order_locked(record)

    def upsert_order_with_events(self, record: OrderRecord, events: Sequence[OutboxEvent]) -> None:
        with self._write_lock, self.transaction():
            self._upsert_order_locked(record)
            for event in events:
                self._append_event_locked(event)

    def _upsert_order_locked(self, record: OrderRecord) -> None:
        self._conn.execute(
            "INSERT INTO order_record VALUES (?,?,?,?,?) "
            "ON CONFLICT(client_order_id) DO UPDATE SET "
            "broker_order_id=excluded.broker_order_id, state=excluded.state, "
            "payload=excluded.payload, updated_ts=excluded.updated_ts",
            (
                record.client_order_id,
                record.broker_order_id,
                record.state.value,
                _order_payload(record),
                record.updated_ts,
            ),
        )

    def load_orders(self) -> list[OrderRecord]:
        with self._read_guard():
            rows = self._conn.execute(
                "SELECT payload FROM order_record ORDER BY updated_ts"
            ).fetchall()
        return [_order_from_payload(payload) for (payload,) in rows]

    # ---------- outbox ----------

    def append_outbox(self, events: Sequence[OutboxEvent]) -> None:
        with self._write_lock, self.transaction():
            for event in events:
                self._append_event_locked(event)

    def _append_event_locked(self, event: OutboxEvent) -> None:
        self._conn.execute(
            "INSERT INTO outbox(event_id,aggregate_type,aggregate_id,event_type,payload,created_ts,sent) "
            "VALUES (?,?,?,?,?,?,0) ON CONFLICT(event_id) DO NOTHING",
            (
                event.event_id,
                event.aggregate_type,
                event.aggregate_id,
                event.event_type,
                event.payload,
                event.created_ts,
            ),
        )
        row = self._conn.execute(
            "SELECT event_type,payload FROM outbox WHERE event_id=?", (event.event_id,)
        ).fetchone()
        if row is not None and (row[0] != event.event_type or row[1] != event.payload):
            raise OutboxEventConflict(f"event_id conflict: {event.event_id}")

    def pending_outbox(self, limit: int = 100) -> list[OutboxRecord]:
        with self._read_guard():
            rows = self._conn.execute(
                "SELECT seq,event_id,aggregate_type,aggregate_id,event_type,payload,created_ts,sent_ts "
                "FROM outbox WHERE sent=0 ORDER BY seq LIMIT ?",
                (limit,),
            ).fetchall()
        return [OutboxRecord(*row) for row in rows]

    def mark_sent(self, seq: int, ts: float) -> None:
        with self._write_lock, self.transaction():
            self._conn.execute(
                "UPDATE outbox SET sent=1, sent_ts=? WHERE seq=? AND sent=0", (ts, seq)
            )

    def outbox_after(self, after_seq: int, limit: int) -> list[OutboxRecord]:
        with self._read_guard():
            rows = self._conn.execute(
                "SELECT seq,event_id,aggregate_type,aggregate_id,event_type,payload,created_ts,sent_ts "
                "FROM outbox WHERE seq>? ORDER BY seq LIMIT ?",
                (after_seq, limit),
            ).fetchall()
        return [OutboxRecord(*row) for row in rows]

    def max_outbox_seq(self) -> int:
        with self._read_guard():
            row = self._conn.execute("SELECT COALESCE(MAX(seq),0) FROM outbox").fetchone()
        return int(row[0]) if row else 0

    def purge_outbox(self, before_ts: float) -> int:
        with self._write_lock, self.transaction():
            cur = self._conn.execute(
                "DELETE FROM outbox WHERE sent=1 AND created_ts<? "
                "AND seq < (SELECT COALESCE(MAX(seq),0) FROM outbox)",
                (before_ts,),
            )
        return int(cur.rowcount)

    # ---------- inbox / meta ----------

    def inbox_has(self, event_id: str) -> bool:
        with self._read_guard():
            row = self._conn.execute("SELECT 1 FROM inbox WHERE event_id=?", (event_id,)).fetchone()
        return row is not None

    def mark_inbox(self, event_id: str, ts: float) -> None:
        with self._write_lock, self.transaction():
            self._conn.execute(
                "INSERT OR IGNORE INTO inbox(event_id,processed_ts) VALUES (?,?)",
                (event_id, ts),
            )

    def get_meta(self, key: str) -> str | None:
        with self._read_guard():
            return self._get_meta_raw(key)

    def set_meta(self, key: str, value: str) -> None:
        with self._write_lock, self.transaction():
            self._set_meta_locked(key, value)

    def _set_meta_locked(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # ---------- 快照 ----------

    def snapshot(self) -> StoreSnapshot:
        with self._read_guard():
            self._conn.execute("BEGIN")
            try:
                row = self._conn.execute("SELECT COALESCE(MAX(seq),0) FROM outbox").fetchone()
                seq = int(row[0]) if row else 0
                orders = self._conn.execute(
                    "SELECT payload FROM order_record ORDER BY updated_ts"
                ).fetchall()
                entries = self._conn.execute(
                    "SELECT entry_id,kind,ts,asset,quantity,price,amount,fee,ref "
                    "FROM ledger_entry ORDER BY rowid"
                ).fetchall()
            finally:
                self._conn.execute("COMMIT")
        return StoreSnapshot(
            seq=seq,
            orders=tuple(_order_from_payload(payload) for (payload,) in orders),
            entries=tuple(LedgerEntry(*row) for row in entries),
        )

    # ---------- 事务与生命周期 ----------

    @contextmanager
    def transaction(self):
        if self._read_only:
            raise StoreReadOnlyError("permission", "read-only store cannot open write transaction")
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def _read_guard(self):
        return self._read_lock if self._read_only else self._write_lock

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._conn.close()
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            try:
                os.unlink(self._lock_path)  # 先关连接再删锁（P-053 C-12）
            except FileNotFoundError:
                pass
