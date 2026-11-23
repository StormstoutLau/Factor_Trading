"""FastAPI app factory：REST 只读管理面 + 鉴权 + health + ticket + metrics（D19）。"""

from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from services.auth import (
    AuthRateLimiter,
    InMemoryTicketStore,
    KeySet,
    Role,
    has_role,
)
from services.config import ServiceSettings
from services.contracts import SnapshotDTO, orders_to_dicts
from services.metrics import Metrics, get_metrics


def _load_store(settings: ServiceSettings | None):
    if settings is None:
        return None
    from live.ledger_store import SqliteLedgerStore

    return SqliteLedgerStore(settings.sqlite_path, read_only=True)


def evaluate_readiness(store, *, heartbeats: dict[str, bool] | None = None) -> tuple[int, dict]:
    """ready 判定：Redis 心跳 TTL + recovery_state + SQLite 可读（§3.7）。"""
    reasons: list[str] = []
    if heartbeats is not None:
        if not heartbeats.get("trading", True):
            reasons.append("stale_trading")
        if not heartbeats.get("consumer", True):
            reasons.append("stale_consumer")
    if store is None:
        reasons.append("db_uninitialized")
        return 503, {"status": "not_ready", "reasons": reasons}
    state = store.get_meta("recovery_state")
    try:
        store.max_outbox_seq()
    except Exception:  # pragma: no cover - 防御式
        reasons.append("db_unreadable")
    if state not in ("complete", "degraded_positions"):
        reasons.append("recovery_incomplete")
    if state == "failed":
        reasons.append("recovery_failed")
    if reasons:
        return 503, {"status": "not_ready", "reasons": reasons}
    return 200, {"status": "ok", "degraded": state == "degraded_positions"}


def json_log(event: str, **fields) -> str:
    """stdlib 结构化日志行（C-20）：固定 ts/level/event + 业务字段。"""
    import time as _time

    return json.dumps(
        {"ts": _time.time(), "level": "info", "event": event, **fields},
        sort_keys=True,
        ensure_ascii=False,
    )


def create_app(
    *,
    settings: ServiceSettings | None = None,
    store=None,
    ticket_store=None,
    metrics: Metrics | None = None,
    publisher=None,
    orders_hub=None,
    market_hub=None,
    bus=None,
    heartbeat_reader=None,
) -> FastAPI:
    if bus is not None:

        @asynccontextmanager
        async def _lifespan(app: FastAPI):
            from services.ws_routes import start_subscribers

            tasks = start_subscribers(app)
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                await bus.close()  # AsyncRedisBus.close() 已实装（bus.py#L163-164）

        app = FastAPI(title="P-054 service layer", lifespan=_lifespan)
    else:
        app = FastAPI(title="P-054 service layer")
    app.state.settings = settings
    app.state.store = store or _load_store(settings)
    app.state.tickets = ticket_store or InMemoryTicketStore()
    app.state.metrics = metrics or get_metrics()
    app.state.publisher = publisher
    app.state.orders_hub = orders_hub
    app.state.market_hub = market_hub
    app.state.bus = bus
    app.state.heartbeat_reader = heartbeat_reader
    app.state.limiter = AuthRateLimiter()
    keys = KeySet(
        reader_key=(
            settings.api_key.get_secret_value() if settings is not None else "reader-key-000000"
        ),
        operator_key=(
            settings.operator_api_key.get_secret_value()
            if settings is not None and settings.operator_api_key is not None
            else ""
        ),
        admin_key=(
            settings.admin_api_key.get_secret_value()
            if settings is not None and settings.admin_api_key is not None
            else "admin-key-0000000"
        ),
    )
    app.state.keys = keys

    if settings is not None and settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key"],
        )

    def _auth(request: Request, x_api_key: str | None, required: str) -> str:
        client = request.client.host if request.client else "unknown"
        limiter: AuthRateLimiter = app.state.limiter
        if not limiter.allow(client):
            raise HTTPException(status_code=429, detail="auth rate limited")
        if not x_api_key:
            limiter.record_failure(client)
            raise HTTPException(status_code=401, detail="missing api key")
        role = keys.role_for(x_api_key)
        if role is None:
            limiter.record_failure(client)
            raise HTTPException(status_code=401, detail="invalid api key")
        if not has_role(role, required):
            raise HTTPException(status_code=403, detail="forbidden")
        limiter.record_success(client)
        return role

    def reader_dep(
        request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")
    ) -> str:
        return _auth(request, x_api_key, Role.READER)

    def admin_dep(
        request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")
    ) -> str:
        return _auth(request, x_api_key, Role.ADMIN)

    def _snapshot() -> SnapshotDTO:
        store = app.state.store
        if store is None:
            return SnapshotDTO(0, (), (), {}, "incomplete")
        snap = store.snapshot()
        positions = []
        initial = float(store.get_meta("initial_cash") or 0.0)  # F-A1：writer 落 meta 基准
        cash = initial
        as_of = 0.0
        for entry in snap.entries:
            cash -= entry.amount + entry.fee
            as_of = max(as_of, entry.ts)
        for asset in sorted({e.asset for e in snap.entries if e.kind == "fill"}):
            qty = sum(e.quantity for e in snap.entries if e.asset == asset and e.kind == "fill")
            if abs(qty) > 1e-12:
                positions.append({"asset": asset, "quantity": qty})
        return SnapshotDTO(
            seq=snap.seq,
            orders=orders_to_dicts(snap.orders),
            positions=tuple(positions),
            account={"cash": cash, "reserved_cash": 0.0, "equity_estimate": cash, "as_of": as_of},
            recovery_state=(store.get_meta("recovery_state") or "incomplete"),
            degraded=(store.get_meta("recovery_state") == "degraded_positions"),
        )

    @app.get("/health/live")
    def health_live() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> Any:
        from fastapi.responses import JSONResponse

        reader = app.state.heartbeat_reader
        status, body = evaluate_readiness(
            app.state.store, heartbeats=reader() if reader is not None else None
        )
        return JSONResponse(status_code=status, content=body)

    @app.get("/api/snapshot", dependencies=[Depends(reader_dep)])
    def api_snapshot() -> dict:
        snap = _snapshot()
        return {
            "seq": snap.seq,
            "orders": list(snap.orders),
            "positions": list(snap.positions),
            "account": snap.account,
            "recovery_state": snap.recovery_state,
            "degraded": snap.degraded,
        }

    @app.get("/api/orders", dependencies=[Depends(reader_dep)])
    def api_orders(
        status: str | None = None,
        limit: int = Query(default=100, le=500),
        offset: int = 0,
    ) -> dict:
        store = app.state.store
        orders = store.load_orders() if store is not None else []
        if status:
            orders = [o for o in orders if o.state.value == status]
        window = orders[offset : offset + limit]
        return {"orders": list(orders_to_dicts(window)), "total": len(orders)}

    @app.get("/api/orders/{coid}", dependencies=[Depends(reader_dep)])
    def api_order(coid: str) -> dict:
        store = app.state.store
        for record in store.load_orders() if store is not None else []:
            if record.client_order_id == coid:
                return dict(orders_to_dicts([record])[0])
        raise HTTPException(status_code=404, detail="order not found")

    @app.get("/api/positions", dependencies=[Depends(reader_dep)])
    def api_positions() -> dict:
        return {"positions": list(_snapshot().positions)}

    @app.get("/api/account", dependencies=[Depends(reader_dep)])
    def api_account() -> dict:
        return _snapshot().account

    @app.get("/api/events", dependencies=[Depends(reader_dep)])
    def api_events(after_seq: int = 0, limit: int = Query(default=100, le=500)) -> dict:
        store = app.state.store
        rows = store.outbox_after(after_seq, limit) if store is not None else []
        return {
            "events": [
                {
                    "seq": r.seq,
                    "event_id": r.event_id,
                    "event_type": r.event_type,
                    "payload": json.loads(r.payload),
                }
                for r in rows
            ]
        }

    @app.post("/api/ws-ticket", dependencies=[Depends(reader_dep)])
    def api_ws_ticket() -> dict:
        ttl = app.state.settings.ws_ticket_ttl_seconds if app.state.settings else 30
        token = secrets.token_urlsafe(24)
        app.state.tickets.issue(token, ttl)
        return {"ticket": token, "expires_in": ttl}

    @app.post("/api/admin/broadcast-pause", dependencies=[Depends(admin_dep)])
    def api_broadcast_pause(payload: dict) -> dict:
        paused = bool(payload.get("paused", True))
        app.state.paused = paused
        if app.state.publisher is not None:  # F-I9：跨 worker 生效（api + ws_hub 同步）
            channel = settings.admin_channel if settings is not None else "p054:admin"
            app.state.publisher.publish(channel, {"paused": paused})
        return {"paused": paused}

    @app.get("/metrics")
    def api_metrics(
        request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")
    ) -> Any:
        require = app.state.settings.metrics_require_auth if app.state.settings else True
        if require:
            _auth(request, x_api_key, Role.READER)
        from fastapi.responses import Response

        return Response(content=app.state.metrics.render(), media_type="text/plain")

    app.state.paused = False
    if orders_hub is not None and market_hub is not None and bus is not None:
        from services.ws_routes import mount_ws

        mount_ws(app)
    return app
