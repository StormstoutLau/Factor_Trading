"""Prometheus 指标：四黄金信号 + 领域指标 + 多 worker 聚合（D16/C-19）。"""

from __future__ import annotations

import os

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

_REGISTRY: CollectorRegistry | None = None


def get_registry() -> CollectorRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        registry = CollectorRegistry()
        if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
            from prometheus_client import multiprocess

            multiprocess.MultiProcessCollector(registry)
        _REGISTRY = registry
    return _REGISTRY


class Metrics:
    """单例命名空间：延迟/流量/错误/饱和度 + 订单/outbox/WS 领域指标。"""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        reg = registry or get_registry()
        self.registry = reg
        self.http_requests = Counter(
            "p054_http_requests_total", "HTTP requests", ["path", "status"], registry=reg
        )
        self.ws_connections = Gauge("p054_ws_connections", "Active WS connections", registry=reg)
        self.ws_slow_consumers = Counter(
            "p054_ws_slow_consumers_total", "Slow consumer closes", registry=reg
        )
        self.order_events = Counter(
            "p054_order_events_total", "Published order events", ["type"], registry=reg
        )
        self.fills = Counter("p054_fills_total", "Applied fills", registry=reg)
        self.rate_denied = Counter(
            "p054_rate_denied_total", "Rate denied", ["reason"], registry=reg
        )
        self.outbox_pending = Gauge("p054_outbox_pending", "Unsent outbox rows", registry=reg)
        self.consumer_pending = Gauge("p054_consumer_pending", "PEL pending count", registry=reg)
        self.ready = Gauge("p054_ready", "Readiness (0/1)", registry=reg)
        self.quote_latency = Histogram("p054_quote_latency_seconds", "Quote latency", registry=reg)
        self.order_latency = Histogram(
            "p054_order_latency_seconds", "Order event latency", registry=reg
        )
        self.e2e_latency = Histogram("p054_e2e_latency_seconds", "End-to-end latency", registry=reg)
        self.market_dropped = Counter(
            "p054_market_dropped_total", "Dropped market ticks", registry=reg
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)


_METRICS: Metrics | None = None


def get_metrics() -> Metrics:
    """进程级单例：避免同名指标重复注册（多 worker 走 multiproc collector）。"""
    global _METRICS
    if _METRICS is None:
        _METRICS = Metrics()
    return _METRICS
