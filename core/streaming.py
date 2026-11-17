"""流式数据契约（P-042 B3）。

- ``MarketEvent``：最小事件（symbol / ts / kind / payload / seq）；
- ``IStreamingFeed``：订阅、快照、增量拉取、关闭四方法；
- ``InMemoryStreamingFeed``：内存实现（仅测试与回放，不接实时源）。

**边界**：本批不建 ``live/``、不接行情网关；实时适配器由 P-053 实现。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Protocol

import pandas as pd


@dataclass(frozen=True)
class MarketEvent:
    """不可变市场事件（payload 为浅冻结：内部 dict 仍可变更）。"""

    symbol: str
    ts: pd.Timestamp
    kind: str
    payload: dict[str, Any]
    seq: int


class IStreamingFeed(Protocol):
    """流式数据源端口。"""

    def snapshot(self) -> dict[str, MarketEvent]:
        """返回每个 symbol 的最新事件。"""
        ...

    def poll(self, timeout: Optional[float] = None) -> list[MarketEvent]:
        """返回上次 poll 之后的增量事件（按 seq 升序）。"""
        ...

    def subscribe(self, symbols: Iterable[str]) -> None:
        """设置订阅集合（覆盖式）。"""
        ...

    def close(self) -> None:
        """关闭数据源（幂等）。"""
        ...


class InMemoryStreamingFeed:
    """内存流实现：seq 单调、有界队列、snapshot + 增量。

    ``poll(timeout)`` 不阻塞：内存实现没有生产者线程，参数仅为接口齐备；
    阻塞/背压语义由 P-053 的实时适配器实现。
    """

    _KINDS = ("tick", "bar", "snapshot")

    def __init__(self, maxlen: int = 10_000) -> None:
        if maxlen <= 0:
            raise ValueError(f"maxlen 必须为正整数: {maxlen}")
        self._maxlen = maxlen
        self._seq = 0
        self._cursor = 0
        self._buffer: deque[MarketEvent] = deque(maxlen=maxlen)
        self._latest: dict[str, MarketEvent] = {}
        self._symbols: set[str] = set()
        self._closed = False

    def subscribe(self, symbols: Iterable[str]) -> None:
        """设置订阅集合；空集合表示全部订阅。"""
        self._symbols = {str(symbol) for symbol in symbols}

    def publish(
        self, symbol: str, ts: pd.Timestamp, kind: str, payload: dict[str, Any]
    ) -> Optional[MarketEvent]:
        """发布事件；未订阅返回 None（不消耗 seq）。"""
        if self._closed:
            raise RuntimeError("feed 已关闭，禁止 publish")
        if not symbol:
            raise ValueError("symbol 不能为空")
        if kind not in self._KINDS:
            raise ValueError(f"未知事件类型: {kind}")
        if self._symbols and symbol not in self._symbols:
            return None

        self._seq += 1
        event = MarketEvent(
            symbol=symbol,
            ts=pd.Timestamp(ts),
            kind=kind,
            payload=dict(payload),
            seq=self._seq,
        )
        self._buffer.append(event)
        self._latest[symbol] = event
        return event

    def snapshot(self) -> dict[str, MarketEvent]:
        return {} if self._closed else dict(self._latest)

    def poll(self, timeout: Optional[float] = None) -> list[MarketEvent]:
        if self._closed:
            return []
        events = [event for event in self._buffer if event.seq > self._cursor]
        if events:
            self._cursor = events[-1].seq
        return events

    def close(self) -> None:
        self._closed = True
