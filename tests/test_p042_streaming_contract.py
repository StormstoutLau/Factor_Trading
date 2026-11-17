"""P-042 B3 流式契约测试（V8-V12）。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from core.streaming import IStreamingFeed, InMemoryStreamingFeed, MarketEvent

TS = pd.Timestamp("2024-01-02 09:30:00")


def test_v8_seq_monotonic_and_frozen():
    """V8：跨 symbol seq 严格递增；事件不可变；协议四方法齐备。"""
    feed = InMemoryStreamingFeed()
    first = feed.publish("A", TS, "tick", {"px": 1.0})
    second = feed.publish("B", TS, "tick", {"px": 2.0})
    third = feed.publish("A", TS, "bar", {"px": 3.0})

    assert first is not None and second is not None and third is not None
    assert [first.seq, second.seq, third.seq] == [1, 2, 3]
    assert isinstance(first, MarketEvent)

    with pytest.raises(FrozenInstanceError):
        setattr(first, "seq", 99)

    expected = {"snapshot", "poll", "subscribe", "close"}
    assert expected <= {name for name in dir(IStreamingFeed) if not name.startswith("_")}


def test_v9_snapshot_latest_per_symbol():
    """V9：snapshot 返回每 symbol 最新事件。"""
    feed = InMemoryStreamingFeed()
    feed.publish("A", TS, "tick", {"px": 1.0})
    b1 = feed.publish("B", TS, "tick", {"px": 2.0})
    a2 = feed.publish("A", TS, "tick", {"px": 3.0})

    assert feed.snapshot() == {"A": a2, "B": b1}


def test_v10_poll_delta_and_empty():
    """V10：poll 按序返回增量；无新事件返回 []。"""
    feed = InMemoryStreamingFeed()
    events = [
        feed.publish("A", TS, "tick", {"i": 1}),
        feed.publish("B", TS, "tick", {"i": 2}),
        feed.publish("A", TS, "tick", {"i": 3}),
    ]

    assert feed.poll() == events
    assert feed.poll() == []

    extra = feed.publish("B", TS, "bar", {"i": 4})
    assert feed.poll() == [extra]


def test_v11_subscribe_filters_publish():
    """V11：订阅集非空时，未订阅 symbol 不入队且不消耗 seq。"""
    feed = InMemoryStreamingFeed()
    feed.subscribe(["A"])

    assert feed.publish("B", TS, "tick", {"px": 1.0}) is None
    assert feed.snapshot() == {}

    allowed = feed.publish("A", TS, "tick", {"px": 2.0})
    assert allowed is not None and allowed.seq == 1
    assert feed.snapshot() == {"A": allowed}
    assert feed.poll() == [allowed]


def test_v12_close_semantics():
    """V12：close 幂等；关闭后 publish 拒绝、poll []、snapshot {}。"""
    feed = InMemoryStreamingFeed()
    feed.publish("A", TS, "tick", {"px": 1.0})
    feed.close()
    feed.close()

    with pytest.raises(RuntimeError):
        feed.publish("A", TS, "tick", {"px": 2.0})
    assert feed.poll() == []
    assert feed.snapshot() == {}
