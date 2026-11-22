"""P-054 F 组：REST 鉴权 / ticket / 路由清单 / CORS / TLS factory（12 例）。"""

from __future__ import annotations

import pickle
import ssl

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

import services.auth as auth_mod
from live.events import OutboxEventType, order_event
from live.ledger_store import SqliteLedgerStore
from live.orders import OrderRequest, from_request
from services.api import create_app
from services.api_worker import build_ssl_context, tls_context_factory
from services.auth import InMemoryTicketStore, KeySet, Role  # noqa: F401
from services.config import ServiceSettings

READER = "reader-key-1234567890"
ADMIN = "admin-key-12345678901"


def _seed(tmp_path):
    path = tmp_path / "ledger.db"
    store = SqliteLedgerStore(path)
    store.set_meta("recovery_state", "complete")
    request = OrderRequest(
        asset="AAA",
        side="BUY",
        quantity=100.0,
        price=10.0,
        client_order_id="co1",
        account_id="ACC",
        strategy_id="S1",
        signal_ts=1.0,
    )
    record = from_request(request, ts=1.0)
    store.upsert_order_with_events(
        record, [order_event(record, OutboxEventType.ORDER_ACCEPTED, version=1, ts=1.0)]
    )
    store.close()
    return path


def _settings(tmp_path, *, cors: tuple[str, ...] = ()) -> ServiceSettings:
    return ServiceSettings(
        sqlite_path=(
            _seed(tmp_path) if not (tmp_path / "ledger.db").exists() else tmp_path / "ledger.db"
        ),
        api_key=SecretStr(READER),
        admin_api_key=SecretStr(ADMIN),
        cors_origins=cors,
    )


def test_f1_missing_key_401(tmp_path):
    app = create_app(settings=_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/snapshot").status_code == 401


def test_f2_invalid_key_401(tmp_path):
    app = create_app(settings=_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/snapshot", headers={"X-API-Key": "bad"}).status_code == 401


def test_f3_role_insufficient_403(tmp_path):
    app = create_app(settings=_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/admin/broadcast-pause",
            json={"paused": True},
            headers={"X-API-Key": READER},
        )
        assert response.status_code == 403


def test_f4_admin_key_can_pause(tmp_path):
    published: list[tuple[str, dict]] = []

    class RecordingPublisher:
        def publish(self, channel: str, message: dict) -> None:
            published.append((channel, message))

    app = create_app(settings=_settings(tmp_path), publisher=RecordingPublisher())
    with TestClient(app) as client:
        response = client.post(
            "/api/admin/broadcast-pause",
            json={"paused": True},
            headers={"X-API-Key": ADMIN},
        )
        assert response.status_code == 200 and response.json()["paused"] is True
    assert published == [("p054:admin", {"paused": True})]  # F-I9：跨 worker 广播落码（F-A2）


def test_f5_compare_digest_used(monkeypatch):
    calls = {"n": 0}
    original = auth_mod.hmac.compare_digest

    def spy(a, b):
        calls["n"] += 1
        return original(a, b)

    monkeypatch.setattr(auth_mod.hmac, "compare_digest", spy)
    keys = KeySet(reader_key=READER, admin_key=ADMIN)
    assert keys.role_for(READER) == Role.READER
    assert calls["n"] >= 1


def test_f6_ticket_single_use_and_expiry():
    store = InMemoryTicketStore()
    assert store.issue("t1", 30, now=100.0) is True
    assert store.consume("t1", now=101.0) is True
    assert store.consume("t1", now=102.0) is False
    store.issue("t2", 1, now=100.0)
    assert store.consume("t2", now=200.0) is False


def test_f7_auth_rate_limit_429(tmp_path):
    app = create_app(settings=_settings(tmp_path))
    with TestClient(app) as client:
        statuses = [
            client.get("/api/snapshot", headers={"X-API-Key": "bad"}).status_code for _ in range(11)
        ]
        assert statuses[-1] == 429
        assert statuses.count(401) == 10


def test_f8_route_list_has_no_trading_writes(tmp_path):
    app = create_app(settings=_settings(tmp_path))
    routes = [(getattr(r, "path", ""), getattr(r, "methods", set())) for r in app.routes]
    assert not any(
        path in ("/orders", "/api/orders") and "POST" in methods for path, methods in routes
    )
    assert not any("cancel" in path and "POST" in methods for path, methods in routes)
    assert not any("kill" in path for path, _ in routes)
    assert any(
        path == "/api/admin/broadcast-pause" and "POST" in methods for path, methods in routes
    )


def test_f9_cors_whitelist(tmp_path):
    settings = _settings(tmp_path, cors=("https://app.example",))
    app = create_app(settings=settings)
    with TestClient(app) as client:
        response = client.options(
            "/api/snapshot",
            headers={
                "Origin": "https://app.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://app.example"


def test_f10_tls_factory_assertions():
    context = build_ssl_context()
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert context.maximum_version == ssl.TLSVersion.MAXIMUM_SUPPORTED
    protocols = {c["protocol"] for c in context.get_ciphers()}
    assert protocols <= {"TLSv1.2", "TLSv1.3"}
    assert pickle.dumps(tls_context_factory)


def test_f11_plaintext_only_loopback():
    with pytest.raises(ValidationError):
        ServiceSettings(
            api_key=SecretStr(READER),
            allow_plaintext_loopback=True,
            api_host="0.0.0.0",
        )


def test_f12_ready_branches(tmp_path):
    path = _seed(tmp_path)
    settings = ServiceSettings(sqlite_path=path, api_key=SecretStr(READER))
    app = create_app(settings=settings)
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
    store = SqliteLedgerStore(path)
    store.set_meta("recovery_state", "failed")
    store.close()
    app2 = create_app(settings=settings)
    with TestClient(app2) as client:
        assert client.get("/health/ready").status_code == 503
