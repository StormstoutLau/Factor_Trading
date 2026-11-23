"""行情源：``MarketDataSource`` 端口 + synthetic 随机游走（D2/C-22）。"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Tick:
    symbol: str
    last: float
    ts: float
    tick_seq: int


class MarketDataSource(Protocol):
    def poll(self) -> list[Tick]: ...


class SyntheticSource:
    """确定性几何随机游走（seed 固定）；``tick_seq`` 单调。"""

    def __init__(
        self, symbols: tuple[str, ...] = ("600000.SH",), *, hz: float = 2.0, seed: int = 7
    ) -> None:
        self._symbols = symbols or ("600000.SH",)
        self._prices = {s: 10.0 for s in self._symbols}
        self._hz = hz
        self._rng = random.Random(seed)
        self._seq = 0

    def poll(self) -> list[Tick]:
        self._seq += 1
        ticks: list[Tick] = []
        for symbol in self._symbols:
            shock = self._rng.gauss(0.0, 0.001)
            self._prices[symbol] = max(0.01, self._prices[symbol] * (1.0 + shock))
            ticks.append(
                Tick(
                    symbol=symbol,
                    last=round(self._prices[symbol], 4),
                    ts=self._seq / self._hz if self._hz else float(self._seq),
                    tick_seq=self._seq,
                )
            )
        return ticks


class MarketGateway:
    def __init__(self, source: MarketDataSource, publisher, *, channel: str = "p054:market"):
        self._source = source
        self._publisher = publisher
        self._channel = channel

    def run_once(self) -> int:
        ticks = self._source.poll()
        if ticks:
            self._publisher.publish(
                self._channel,
                {
                    "type": "market",
                    "tick_seq": ticks[0].tick_seq,
                    "ticks": [{"symbol": t.symbol, "last": t.last, "ts": t.ts} for t in ticks],
                },
            )
        return len(ticks)


def serve(
    stop_event,
    *,
    gateway: MarketGateway,
    hz: float,
    bus=None,
    heartbeat_key: str = "p054:market:heartbeat",
    heartbeat_ttl: int = 10,
) -> None:
    """hz 循环 + 每帧心跳（G3/D12）；``stop_event.wait`` 可被信号立即唤醒。"""
    import time

    interval = 1.0 / hz if hz > 0 else 1.0
    while not stop_event.is_set():
        gateway.run_once()
        if bus is not None:
            bus.set_key(heartbeat_key, f"{time.time():.3f}", heartbeat_ttl)
        stop_event.wait(interval)


def _build_from_env(channel: str | None = None):
    """从 env 构造（gateway, hz, bus）；CLI 覆盖由 main 处理。"""
    from services.bus import SyncRedisBus

    redis_url = os.environ.get("P054_REDIS_URL", "redis://127.0.0.1:6379/0")
    symbols = tuple(
        s.strip()
        for s in os.environ.get("P054_MARKET_SYMBOLS", "600000.SH").split(",")
        if s.strip()
    )
    hz = float(os.environ.get("P054_MARKET_TICK_HZ", "2.0"))
    resolved_channel = channel or os.environ.get("P054_MARKET_CHANNEL", "p054:market")
    bus = SyncRedisBus(redis_url)
    gateway = MarketGateway(SyntheticSource(symbols, hz=hz), bus, channel=resolved_channel)
    return gateway, hz, bus


def _parse_args(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="market_gateway")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--embedded", action="store_true")
    parser.add_argument("--hz", type=float, default=None)
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--redis-url", default=None, dest="redis_url")
    return parser.parse_args(argv)


def main(argv=None) -> None:  # pragma: no cover - 进程入口
    """独立进程默认 = 信号 + serve；``--once`` 单帧；``--embedded`` 交给 run_embedded。"""
    import threading

    args = _parse_args(argv)
    if args.redis_url:
        os.environ["P054_REDIS_URL"] = args.redis_url
    if args.symbols:
        os.environ["P054_MARKET_SYMBOLS"] = args.symbols
    if args.hz is not None:
        os.environ["P054_MARKET_TICK_HZ"] = str(args.hz)
    if args.embedded:
        run_embedded(None)
        return
    gateway, hz, bus = _build_from_env()
    if args.once:
        gateway.run_once()
        return
    from services.trading_worker import install_stop_handlers

    stop_event = threading.Event()
    install_stop_handlers(stop_event)
    serve(
        stop_event,
        gateway=gateway,
        hz=hz,
        bus=bus,
        heartbeat_ttl=int(os.environ.get("P054_MARKET_HEARTBEAT_TTL_SECONDS", "10")),
    )


def run_embedded(stop_event=None) -> None:  # pragma: no cover - 单机内嵌（trading --with-market）
    """外部给 event 则直接 serve；否则自建 event + 安装信号（改写自 P-054 stub）。"""
    import threading

    if stop_event is not None:
        gateway, hz, bus = _build_from_env()
        serve(
            stop_event,
            gateway=gateway,
            hz=hz,
            bus=bus,
            heartbeat_ttl=int(os.environ.get("P054_MARKET_HEARTBEAT_TTL_SECONDS", "10")),
        )
        return
    from services.trading_worker import install_stop_handlers

    event = threading.Event()
    install_stop_handlers(event)
    gateway, hz, bus = _build_from_env()
    serve(
        event,
        gateway=gateway,
        hz=hz,
        bus=bus,
        heartbeat_ttl=int(os.environ.get("P054_MARKET_HEARTBEAT_TTL_SECONDS", "10")),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
