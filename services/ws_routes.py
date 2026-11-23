"""WS 挂载：``/ws/orders``、``/ws/market`` + Redis Pub/Sub 订阅任务（G17/C-8..C-11）。"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import partial

import anyio.to_thread
from fastapi import FastAPI, Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from services.contracts import ErrorCode, ServiceError

_POLL = 0.02
_log = logging.getLogger(__name__)


def mount_ws(app: FastAPI) -> None:
    """在两个 Hub 与 bus 都已注入时挂载（默认 app 不挂，零回归）。"""

    @app.websocket("/ws/orders")
    async def ws_orders(
        ws: WebSocket,
        ticket: str = Query(default=""),
        resume_last_seq: int = Query(default=0),
    ) -> None:
        hub = app.state.orders_hub
        await ws.accept()
        if not app.state.tickets.consume(ticket):
            await ws.send_json(
                {"type": "error", "code": ErrorCode.AUTH_FAILED, "message": "invalid ticket"}
            )
            await ws.close(code=4401)
            return
        try:
            hub.ensure_ready(app.state.store)
        except ServiceError:
            await ws.send_json(
                {"type": "error", "code": ErrorCode.NOT_READY, "message": "recovery incomplete"}
            )
            await ws.close(code=4503)
            return
        conn = hub.register()
        try:
            settings = app.state.settings
            limit = settings.ws_snapshot_orders_limit if settings is not None else 200
            snapshot, pending = await anyio.to_thread.run_sync(
                partial(
                    hub.snapshot_and_stream,
                    app.state.store,
                    conn,
                    limit=limit,
                    resume_last_seq=resume_last_seq,
                )
            )
            await ws.send_json(snapshot)
            for frame in pending:
                await ws.send_json(frame)
            await _pump(ws, hub, conn, wrap_market=False)
        finally:
            hub.unregister(conn)

    @app.websocket("/ws/market")
    async def ws_market(ws: WebSocket, ticket: str = Query(default="")) -> None:
        hub = app.state.market_hub
        await ws.accept()
        if not app.state.tickets.consume(ticket):
            await ws.send_json(
                {"type": "error", "code": ErrorCode.AUTH_FAILED, "message": "invalid ticket"}
            )
            await ws.close(code=4401)
            return
        try:
            hub.ensure_ready(app.state.store)
        except ServiceError:
            await ws.send_json(
                {"type": "error", "code": ErrorCode.NOT_READY, "message": "recovery incomplete"}
            )
            await ws.close(code=4503)
            return
        conn = hub.register()
        try:
            await _pump(ws, hub, conn, wrap_market=True)
        finally:
            hub.unregister(conn)


async def _pump(ws: WebSocket, hub, conn, *, wrap_market: bool) -> None:
    """单协程帧泵：20 ms 轮询 + 心跳（D9/C-10）。"""
    while True:
        frame = conn.next_frame()
        if frame is not None:
            if frame.get("type") == "close":
                await ws.close(code=int(frame["code"]))
                return
            await ws.send_json(_wrap(frame) if wrap_market else frame)
            continue
        action = hub.heartbeat(conn)
        if action == "close":
            await ws.close(code=1011)
            return
        if action == "ping":
            await ws.send_json({"type": "ping"})
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=_POLL)
        except asyncio.TimeoutError:
            continue
        except WebSocketDisconnect:
            return
        except ValueError:  # 非 JSON 帧
            continue
        if isinstance(msg, dict) and msg.get("type") == "pong":
            hub.pong(conn)


def _wrap(frame: dict) -> dict:
    if frame.get("type") in ("ping", "close", "error", "delta", "snapshot"):
        return frame
    return {"type": "market", "tick": frame}


def start_subscribers(app: FastAPI) -> list[asyncio.Task]:
    """orders / market / admin 三订阅任务（仅 bus 注入时启动）。"""
    bus = app.state.bus
    if bus is None:
        return []
    settings = app.state.settings
    orders_channel = settings.orders_channel if settings is not None else "p054:orders:events"
    market_channel = settings.market_channel if settings is not None else "p054:market"
    admin_channel = settings.admin_channel if settings is not None else "p054:admin"
    return [
        asyncio.create_task(orders_subscriber(app.state.orders_hub, bus, orders_channel)),
        asyncio.create_task(market_subscriber(app.state.market_hub, bus, market_channel)),
        asyncio.create_task(admin_subscriber(app.state.market_hub, bus, admin_channel)),
    ]


async def orders_subscriber(hub, bus, channel: str) -> None:
    async def _handle(payload: dict) -> None:
        hub.broadcast_orders(int(payload.get("seq", 0)), payload.get("event", {}))

    await _subscribe(bus, channel, _handle)


async def market_subscriber(hub, bus, channel: str) -> None:
    async def _handle(payload: dict) -> None:
        for tick in payload.get("ticks", []):
            hub.broadcast_market(tick)

    await _subscribe(bus, channel, _handle)


async def admin_subscriber(hub, bus, channel: str) -> None:
    async def _handle(payload: dict) -> None:
        hub.set_paused(bool(payload.get("paused", False)))

    await _subscribe(bus, channel, _handle)


async def _subscribe(bus, channel: str, handler) -> None:
    """断线重建 pubsub + 指数退避（A6）；取消穿透。"""
    delay = 1.0
    while True:
        pubsub = None
        try:
            pubsub = await bus.subscribe(channel)
            async for message in pubsub.listen():
                data = message.get("data") if isinstance(message, dict) else None
                if not isinstance(data, (str, bytes)):
                    continue
                try:
                    payload = json.loads(data)
                except (TypeError, ValueError):
                    continue
                await handler(payload)
            delay = 1.0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.warning("subscribe_failed channel=%s error=%r", channel, exc)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.aclose()
                except Exception:  # pragma: no cover - 关闭失败不覆盖主异常
                    pass
