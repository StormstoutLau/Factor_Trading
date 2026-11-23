"""uvicorn 入口与 TLS factory（D15/I14；top-level 可 pickle）。"""

from __future__ import annotations

import os
import ssl
import time
from typing import Callable

DEFAULT_CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES"


def build_ssl_context(
    certfile: str | None = None,
    keyfile: str | None = None,
    *,
    ciphers: str = DEFAULT_CIPHERS,
    ca_certs: str | None = None,
    require_client_cert: bool = False,
) -> ssl.SSLContext:
    """显式 ``minimum_version=TLSv1_2`` + AEAD 优先 cipher（Q16/S68-S72）。"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
    context.set_ciphers(ciphers)
    if ca_certs:
        context.load_verify_locations(cafile=ca_certs)
    if require_client_cert:
        context.verify_mode = ssl.CERT_REQUIRED
    if certfile and keyfile:
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def tls_context_factory(config=None, default_factory=None) -> ssl.SSLContext:
    """uvicorn 协议 ``Callable[[Config, Callable[[], SSLContext]], SSLContext]``；顶层可 pickle。

    A1/A2：factory 在每个 worker 进程内运行，忽略入参、只读 env。
    """
    del config, default_factory
    return build_ssl_context(
        os.environ.get("P054_TLS_CERTFILE"),
        os.environ.get("P054_TLS_KEYFILE"),
        ciphers=os.environ.get("P054_TLS_CIPHERS", DEFAULT_CIPHERS),
        ca_certs=os.environ.get("P054_TLS_CA_CERTS"),
        require_client_cert=os.environ.get("P054_TLS_REQUIRE_CLIENT_CERT") == "1",
    )


def build_heartbeat_reader(settings) -> Callable[[], dict[str, bool]]:
    """sync Redis 心跳读取器（D10/C-12）：``def`` 端点在线程池执行，可安全阻塞。"""
    from services.bus import SyncRedisBus

    bus = SyncRedisBus(settings.redis_url)

    def _fresh(raw: str | None) -> bool:
        if raw is None:
            return False
        head = raw.split(":", 1)[0]
        try:
            ts = float(head)
        except ValueError:
            return True  # 非时间戳负载（旧 ``"ok"``）→ 以 TTL 存在为准
        staleness = float(settings.ready_staleness_seconds)
        return (time.time() - ts) <= staleness

    def read() -> dict[str, bool]:
        return {
            "trading": _fresh(bus.get_key("p054:trading:heartbeat")),
            "consumer": _fresh(bus.get_key("p054:consumer:heartbeat")),
        }

    return read


def main() -> None:  # pragma: no cover - 进程入口
    import redis
    import uvicorn

    from live.ledger_store import SqliteLedgerStore
    from services.api import create_app
    from services.auth import RedisTicketStore
    from services.bus import AsyncRedisBus, SyncRedisBus
    from services.config import ServiceSettings
    from services.ws_hub import ConnectionHub

    workers = int(os.environ.get("P054_WORKERS", "1"))
    if workers != 1:
        raise SystemExit("P054_WORKERS must be 1; scale containers instead")
    settings = ServiceSettings.from_env()
    store = SqliteLedgerStore(settings.sqlite_path, read_only=True)
    publisher = SyncRedisBus(settings.redis_url)
    tickets = RedisTicketStore(redis.Redis.from_url(settings.redis_url, decode_responses=True))
    heartbeat_reader = build_heartbeat_reader(settings)
    orders_hub = ConnectionHub(
        orders_max=settings.ws_orders_queue_max,
        market_max=settings.ws_market_queue_max,
        slow_seconds=settings.ws_slow_consumer_seconds,
    )
    market_hub = ConnectionHub(
        orders_max=settings.ws_orders_queue_max,
        market_max=settings.ws_market_queue_max,
        slow_seconds=settings.ws_slow_consumer_seconds,
    )
    bus = AsyncRedisBus(settings.redis_url)
    app = create_app(
        settings=settings,
        store=store,
        ticket_store=tickets,
        publisher=publisher,
        heartbeat_reader=heartbeat_reader,
        orders_hub=orders_hub,
        market_hub=market_hub,
        bus=bus,
    )
    kwargs: dict = {
        "host": settings.api_host,
        "port": settings.api_port,
        "workers": 1,
    }
    if settings.tls_certfile is not None and settings.tls_keyfile is not None:
        kwargs["ssl_context_factory"] = tls_context_factory
    elif not settings.allow_plaintext_loopback:
        raise SystemExit("TLS required: set P054_TLS_CERTFILE/P054_TLS_KEYFILE")
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":  # pragma: no cover
    main()
