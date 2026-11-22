"""行情源：``MarketDataSource`` 端口 + synthetic 随机游走（D2/C-22）。"""

from __future__ import annotations

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


def main() -> None:  # pragma: no cover - 进程入口
    """行情网关独立入口：直读 env（不走 ServiceSettings——无 API key 依赖，F-A3）。"""
    import os

    from services.bus import SyncRedisBus

    redis_url = os.environ.get("P054_REDIS_URL", "redis://127.0.0.1:6379/0")
    symbols = tuple(
        s.strip()
        for s in os.environ.get("P054_MARKET_SYMBOLS", "600000.SH").split(",")
        if s.strip()
    )
    hz = float(os.environ.get("P054_MARKET_TICK_HZ", "2.0"))
    channel = os.environ.get("P054_MARKET_CHANNEL", "p054:market")
    bus = SyncRedisBus(redis_url)
    gateway = MarketGateway(SyntheticSource(symbols, hz=hz), bus, channel=channel)
    gateway.run_once()


def run_embedded(stop_event=None) -> None:  # pragma: no cover - 单机内嵌
    main()
