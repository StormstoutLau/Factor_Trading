"""P-055 T5：部署资产静态断言（compose 健康/卷/端口 / Dockerfile 非 root，2 例）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compose_services_and_health():
    text = (ROOT / "deploy" / "compose.services.yaml").read_text(encoding="utf-8")
    assert "redis:7" in text
    assert "service_healthy" in text
    assert "p055-data" in text
    assert "127.0.0.1:8054:8054" in text
    assert 'P054_METRICS_REQUIRE_AUTH: "0"' in text


def test_dockerfile_services_non_root():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "AS services" in text
    assert "useradd" in text
    assert "USER appuser" in text
