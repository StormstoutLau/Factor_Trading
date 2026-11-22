"""总线：Async/Sync Redis 双客户端 + InMemory FakeBus（D2/D18/F-I7）。"""

from __future__ import annotations

import json
import threading
from collections import defaultdict, deque
from typing import Sequence

from services.contracts import StreamMessage


class InMemoryBus:
    """单进程替身：Pub/Sub 扇出 + Stream 消费组（仅测试/单进程开发，D18）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, list[deque]] = defaultdict(list)
        self._streams: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        self._pending: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        self._keys: dict[str, tuple[str, int]] = {}
        self._msg_seq = 0

    # ---------- Pub/Sub ----------

    def subscribe(self, channel: str) -> deque:
        queue: deque = deque()
        with self._lock:
            self._subs[channel].append(queue)
        return queue

    def publish(self, channel: str, message: dict) -> None:
        with self._lock:
            queues = list(self._subs[channel])
        for queue in queues:
            queue.append(message)

    # ---------- Streams ----------

    def stream_add(self, stream: str, fields: dict) -> str:
        with self._lock:
            self._msg_seq += 1
            message_id = f"{self._msg_seq}-0"
            self._streams[stream].append((message_id, dict(fields)))
        return message_id

    def stream_read(
        self, stream: str, *, consumer: str, count: int = 10, block_ms: int = 1000
    ) -> list[StreamMessage]:
        del block_ms
        out: list[StreamMessage] = []
        with self._lock:
            items = self._streams[stream]
            while items and len(out) < count:
                message_id, fields = items.pop(0)
                self._pending[consumer].append((message_id, fields))
                out.append(_to_stream_message(message_id, fields))
        return out

    def stream_ack(self, consumer: str, message_id: str) -> None:
        del consumer
        with self._lock:
            for key in list(self._pending):
                self._pending[key] = [
                    (mid, fields) for mid, fields in self._pending[key] if mid != message_id
                ]

    def stream_autoclaim(self, consumer: str, *, idle_ms: int, count: int) -> list[StreamMessage]:
        del idle_ms
        with self._lock:
            items = self._pending[consumer][:count]
            self._pending[consumer] = self._pending[consumer][count:]
        return [_to_stream_message(mid, fields) for mid, fields in items]

    def stream_pending(self, consumer: str) -> int:
        with self._lock:
            return len(self._pending[consumer])

    def set_key(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._keys[key] = (value, ttl)

    def get_key(self, key: str) -> str | None:
        with self._lock:
            item = self._keys.get(key)
        return None if item is None else item[0]


def _to_stream_message(message_id: str, fields: dict) -> StreamMessage:
    return StreamMessage(
        seq=int(fields.get("seq", 0)),
        event_id=str(fields.get("event_id", "")),
        event_type=str(fields.get("event_type", "")),
        payload=str(fields.get("payload", "")),
        message_id=message_id,
    )


class SyncRedisBus:
    """交易进程三线程专用（F-I7/D-17）：同步 redis 客户端，线程内无事件循环。"""

    def __init__(self, redis_url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def publish(self, channel: str, message: dict) -> None:
        self._client.publish(channel, json.dumps(message, ensure_ascii=False))

    def subscribe(self, channel: str):
        pubsub = self._client.pubsub()
        pubsub.subscribe(channel)
        return pubsub

    def stream_add(self, stream: str, fields: dict) -> str:
        return str(self._client.xadd(stream, fields, maxlen=200_000, approximate=True))

    def stream_read(
        self, stream: str, *, consumer: str, count: int = 10, block_ms: int = 1000
    ) -> list[StreamMessage]:
        rows = self._client.xreadgroup(
            "p054-relay", consumer, {stream: ">"}, count=count, block=block_ms
        )
        return _decode_rows(rows)  # type: ignore[arg-type]

    def stream_ack(self, consumer: str, message_id: str) -> None:
        del consumer
        self._client.xack("p054:orders", "p054-relay", message_id)

    def stream_autoclaim(self, consumer: str, *, idle_ms: int, count: int) -> list[StreamMessage]:
        _next, rows = self._client.xautoclaim(
            "p054:orders", "p054-relay", consumer, min_idle_time=idle_ms, count=count
        )
        return [_to_stream_message(mid, fields) for mid, fields in rows]

    def set_key(self, key: str, value: str, ttl: int) -> None:
        self._client.set(key, value, ex=ttl)

    def get_key(self, key: str) -> str | None:
        value = self._client.get(key)
        return None if value is None else str(value)

    def close(self) -> None:
        self._client.close()


class AsyncRedisBus:
    """API/WS worker 专用：``redis.asyncio``（D2/D18）。"""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, channel: str, message: dict) -> None:
        await self._client.publish(channel, json.dumps(message, ensure_ascii=False))

    async def subscribe(self, channel: str):
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def close(self) -> None:
        await self._client.aclose()


class InMemoryBusAdapter:
    """把 ``InMemoryBus`` 适配成 ``EventPublisher``/``OrderStream`` 形状。"""

    def __init__(self, bus: InMemoryBus, *, stream: str = "p054:orders") -> None:
        self.bus = bus
        self.stream = stream

    def publish(self, channel: str, message: dict) -> None:
        self.bus.publish(channel, message)

    def add(self, message: StreamMessage) -> str:
        return self.bus.stream_add(
            self.stream,
            {
                "seq": message.seq,
                "event_id": message.event_id,
                "event_type": message.event_type,
                "payload": message.payload,
            },
        )

    def read(self, *, consumer: str, count: int = 10, block_ms: int = 1000):
        return self.bus.stream_read(self.stream, consumer=consumer, count=count, block_ms=block_ms)

    def ack(self, message_id: str) -> None:
        self.bus.stream_ack("consumer", message_id)

    def autoclaim(self, *, consumer: str, idle_ms: int, count: int):
        return self.bus.stream_autoclaim(consumer, idle_ms=idle_ms, count=count)

    def stream_pending(self, consumer: str) -> int:
        return self.bus.stream_pending(consumer)

    def set_key(self, key: str, value: str, ttl: int) -> None:
        self.bus.set_key(key, value, ttl)

    def get_key(self, key: str) -> str | None:
        return self.bus.get_key(key)


def _decode_rows(rows: Sequence) -> list[StreamMessage]:
    out: list[StreamMessage] = []
    for _stream, items in rows:
        for message_id, fields in items:
            out.append(_to_stream_message(message_id, dict(fields)))
    return out
