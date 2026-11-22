"""P-054 HM 组：health/ready / 心跳 / recovery / metrics 鉴权与字段（8 例）。"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from pydantic import SecretStr

from live.ledger_store import SqliteLedgerStore
from services.api import create_app, evaluate_readiness, json_log
from services.config import ServiceSettings
from services.metrics import get_metrics

READER = "reader-key-1234567890"


def _store(tmp_path, state: str = "complete") -> SqliteLedgerStore:
    store = SqliteLedgerStore(tmp_path / "ledger.db")
    store.set_meta("recovery_state", state)
    return store


def _app(store):
    settings = ServiceSettings(
        sqlite_path=store._path, api_key=SecretStr(READER), metrics_require_auth=True
    )
    return create_app(settings=settings, store=store)


def test_hm1_live_always_200(tmp_path):
    store = _store(tmp_path)
    with TestClient(_app(store)) as client:
        assert client.get("/health/live").status_code == 200
    store.close()


def test_hm2_stale_trading_heartbeat_503(tmp_path):
    store = _store(tmp_path)
    status, body = evaluate_readiness(store, heartbeats={"trading": False})
    assert status == 503 and "stale_trading" in body["reasons"]
    store.close()


def test_hm3_stale_consumer_heartbeat_503(tmp_path):
    store = _store(tmp_path)
    status, body = evaluate_readiness(store, heartbeats={"trading": True, "consumer": False})
    assert status == 503 and "stale_consumer" in body["reasons"]
    store.close()


def test_hm4_degraded_positions_ready_with_flag(tmp_path):
    store = _store(tmp_path, "degraded_positions")
    status, body = evaluate_readiness(store)
    assert status == 200 and body["degraded"] is True
    store.close()


def test_hm5_four_signal_metrics_present(tmp_path):
    store = _store(tmp_path)
    with TestClient(_app(store)) as client:
        text = client.get("/metrics", headers={"X-API-Key": READER}).text
    for name in (
        "p054_http_requests_total",
        "p054_ws_connections",
        "p054_order_events_total",
        "p054_outbox_pending",
        "p054_quote_latency_seconds",
    ):
        assert name in text
    store.close()


def test_hm6_domain_metrics_present(tmp_path):
    store = _store(tmp_path)
    with TestClient(_app(store)) as client:
        text = client.get("/metrics", headers={"X-API-Key": READER}).text
    for name in ("p054_fills_total", "p054_rate_denied_total", "p054_market_dropped_total"):
        assert name in text
    store.close()


def test_hm7_metrics_requires_auth(tmp_path):
    store = _store(tmp_path)
    with TestClient(_app(store)) as client:
        assert client.get("/metrics").status_code == 401
    store.close()


def test_hm8_json_log_fields():
    line = json_log("order.accepted", coid="co1", seq=3)
    data = json.loads(line)
    assert data["level"] == "info" and data["event"] == "order.accepted"
    assert data["coid"] == "co1" and "ts" in data
    assert get_metrics().ready is not None
