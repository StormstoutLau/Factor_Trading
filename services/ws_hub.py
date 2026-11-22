"""WS 连接管理：snapshot + delta / seq 去重 / 背压 / 心跳（D12/D13/C-15）。"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from services.contracts import ErrorCode, ServiceError, orders_to_dicts


@dataclass
class ConnectionState:
    orders_q: deque[dict] = field(default_factory=deque)
    market_q: deque[dict] = field(default_factory=deque)
    last_seq: int = 0
    slow_since: float | None = None
    closed: bool = False
    close_code: int = 0
    last_pong: float = 0.0

    def next_frame(self) -> dict | None:
        if self.orders_q:
            return self.orders_q.popleft()
        if self.market_q:
            return self.market_q.popleft()
        if self.closed and self.close_code:
            code, self.close_code = self.close_code, 0
            return {"type": "close", "code": code}
        return None


class ConnectionHub:
    def __init__(
        self,
        *,
        orders_max: int = 1000,
        market_max: int = 200,
        slow_seconds: float = 5.0,
        clock=time.monotonic,
    ) -> None:
        self.orders_max = orders_max
        self.market_max = market_max
        self.slow_seconds = slow_seconds
        self.paused = False  # p054:admin 同步（F-I9）；只影响行情，不触订单
        self._clock = clock
        self._connections: list[ConnectionState] = []

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    @property
    def connections(self) -> list[ConnectionState]:
        return list(self._connections)

    def register(self) -> ConnectionState:
        conn = ConnectionState(last_pong=self._clock())
        self._connections.append(conn)
        return conn

    def unregister(self, conn: ConnectionState) -> None:
        if conn in self._connections:
            self._connections.remove(conn)

    # ---------- 订单（不可丢） ----------

    def broadcast_orders(self, seq: int, event: dict, *, now: float | None = None) -> int:
        current = self._clock() if now is None else now
        delivered = 0
        for conn in self._connections:
            if conn.closed:
                continue
            if seq <= conn.last_seq:
                continue  # 连接内去重（I11）
            if len(conn.orders_q) >= self.orders_max:
                conn.slow_since = conn.slow_since if conn.slow_since is not None else current
                if current - conn.slow_since >= self.slow_seconds:
                    conn.closed = True
                    conn.close_code = 1013
                    conn.orders_q.append(
                        {
                            "type": "error",
                            "code": ErrorCode.SLOW_CONSUMER,
                            "message": "order consumer too slow",
                        }
                    )
                continue  # 未超时前不丢队列内既有帧
            conn.last_seq = seq
            conn.orders_q.append({"type": "delta", "seq": seq, "events": [event]})
            delivered += 1
        return delivered

    # ---------- 行情（可丢/可合并） ----------

    def broadcast_market(self, tick: dict, *, now: float | None = None) -> int:
        del now
        if self.paused:  # broadcast-pause：只停行情推送（D19）
            return 0
        delivered = 0
        symbol = tick.get("symbol")
        for conn in self._connections:
            if conn.closed:
                continue
            if len(conn.market_q) >= self.market_max:
                merged = False
                for item in conn.market_q:
                    if item.get("symbol") == symbol:
                        item.update(tick)
                        merged = True
                        break
                if not merged:
                    conn.market_q.popleft()
            conn.market_q.append(dict(tick))
            delivered += 1
        return delivered

    # ---------- 快照 ----------

    def snapshot(self, store, *, limit: int = 200, recovery_state: str | None = None) -> dict:
        if store is None:
            raise ServiceError(ErrorCode.NOT_READY, "store missing")
        snap = store.snapshot()
        orders = list(orders_to_dicts(snap.orders[-limit:]))
        initial = float(store.get_meta("initial_cash") or 0.0)  # F-A1：writer 落 meta 基准
        cash = initial
        as_of = 0.0
        lots: dict[str, float] = {}
        for entry in snap.entries:
            cash -= entry.amount + entry.fee
            as_of = max(as_of, entry.ts)
            if entry.kind == "fill":
                lots[entry.asset] = lots.get(entry.asset, 0.0) + entry.quantity
        positions = [
            {"asset": asset, "quantity": qty}
            for asset, qty in sorted(lots.items())
            if abs(qty) > 1e-12
        ]
        state = recovery_state or store.get_meta("recovery_state") or "incomplete"
        return {
            "type": "snapshot",
            "seq": snap.seq,
            "recovery_state": state,
            "degraded": state == "degraded_positions",
            "orders": orders,
            "positions": positions,
            "account": {
                "cash": cash,
                "reserved_cash": 0.0,
                "equity_estimate": cash,
                "as_of": as_of,
            },
            "market": {},
        }

    def snapshot_and_stream(
        self, store, conn: ConnectionState, *, limit: int = 200, resume_last_seq: int = 0
    ) -> tuple[dict, list[dict]]:
        """先注册（已发生）→ 读快照 → 过滤队列中 seq > snapshot.seq（C-15）。"""
        snapshot = self.snapshot(store, limit=limit)
        snapshot["resumed_from"] = resume_last_seq
        if resume_last_seq > snapshot["seq"]:
            return snapshot, [{"type": "error", "code": "stale_snapshot", "message": ""}]
        pending = [f for f in conn.orders_q if f.get("seq", 0) > snapshot["seq"]]
        conn.orders_q = deque(f for f in conn.orders_q if f.get("seq", 0) <= snapshot["seq"])
        pending.sort(key=lambda f: f.get("seq", 0))
        return snapshot, pending

    # ---------- 心跳 ----------

    def heartbeat(self, conn: ConnectionState, *, now: float | None = None) -> str:
        current = self._clock() if now is None else now
        if current - conn.last_pong > 30.0:
            conn.closed = True
            conn.close_code = 1011
            return "close"
        if current - conn.last_pong > 15.0:
            return "ping"
        return "idle"

    def pong(self, conn: ConnectionState, *, now: float | None = None) -> None:
        conn.last_pong = self._clock() if now is None else now

    def ensure_ready(self, store) -> None:
        if store is None:
            raise ServiceError(ErrorCode.NOT_READY, "store missing")
        if store.get_meta("recovery_state") not in ("complete", "degraded_positions"):
            raise ServiceError(ErrorCode.NOT_READY, "recovery incomplete")
