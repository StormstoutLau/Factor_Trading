"""outbox relay 与单消费者：XADD → mark_sent / inbox 去重 → Pub/Sub 扇出（D7/I4/I6）。"""

from __future__ import annotations

import json
import time

from services.contracts import StreamMessage


class PublisherFailure(RuntimeError):
    pass


class RelayLoop:
    def __init__(
        self,
        store,
        publisher,
        *,
        batch: int = 100,
        poll_interval: float = 0.2,
        clock=time.time,
        sleep=time.sleep,
        metrics=None,
        backoff: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0),
    ) -> None:
        self._store = store
        self._publisher = publisher
        self._batch = batch
        self._poll_interval = poll_interval
        self._clock = clock
        self._sleep = sleep
        self._metrics = metrics
        self._backoff = backoff
        self._failures = 0
        self.last_unsent = 0  # 最近一轮未发送条数（0..batch），供心跳 `<ts>:<int>`（F-D5）
        self.stop = False

    def run_once(self) -> int:
        rows = self._store.pending_outbox(self._batch)
        sent = 0
        for row in rows:
            message = StreamMessage(
                seq=row.seq,
                event_id=row.event_id,
                event_type=row.event_type,
                payload=row.payload,
            )
            try:
                self._publisher.add(message)
            except Exception as exc:  # 保留 sent=0，下轮重试（D7）
                self._failures += 1
                delay = self._backoff[min(self._failures - 1, len(self._backoff) - 1)]
                self._sleep(delay)
                raise PublisherFailure(str(exc)) from exc
            self._store.mark_sent(row.seq, self._clock())
            sent += 1
        self._failures = 0
        self.last_unsent = len(rows)
        if self._metrics is not None:
            self._metrics.outbox_pending.set(len(self._store.pending_outbox(1)))
        return sent

    def purge_once(self, *, retention_days: int = 7) -> int:
        cutoff = self._clock() - retention_days * 86_400
        return int(self._store.purge_outbox(cutoff))

    def run(self, stop_event=None) -> None:
        while not (stop_event.is_set() if stop_event is not None else self.stop):
            try:
                sent = self.run_once()
            except PublisherFailure as exc:
                _log("relay_publisher_failure", error=str(exc))  # Step 10 实跑修正：不再静默
                continue
            if sent == 0:
                self._sleep(self._poll_interval)


class ConsumerLoop:
    """单消费者：inbox 去重 → Pub/Sub 扇出 → XACK（at-least-once，I6）。"""

    def __init__(
        self,
        store,
        bus,
        *,
        channel: str = "p054:orders:events",
        consumer: str = "trading-1",
        stream: str = "p054:orders",
        metrics=None,
        clock=time.time,
    ) -> None:
        self._store = store
        self._bus = bus
        self._channel = channel
        self._consumer = consumer
        self._stream = stream
        self._metrics = metrics
        self._clock = clock
        self.stop = False

    def run_once(self, *, count: int = 10, autoclaim: bool = False) -> int:
        if autoclaim:
            messages = self._bus.autoclaim(consumer=self._consumer, idle_ms=60_000, count=count)
        else:
            messages = self._bus.read(consumer=self._consumer, count=count)
        published = 0
        for message in messages:
            if self._store.inbox_has(message.event_id):
                self._bus.ack(message.message_id)
                continue
            self._bus.publish(
                self._channel,
                {"seq": message.seq, "event": json.loads(message.payload)},
            )
            if self._metrics is not None:
                self._metrics.order_events.labels(type=message.event_type).inc()
            self._store.mark_inbox(message.event_id, self._clock())
            self._bus.ack(message.message_id)
            published += 1
        if self._metrics is not None:
            pending = getattr(self._bus, "stream_pending", lambda _c: 0)
            self._metrics.consumer_pending.set(pending(self._consumer))
        return published

    def run(
        self,
        stop_event=None,
        *,
        count: int = 100,
        autoclaim_every: float = 30.0,
        heartbeat_key: str = "p054:consumer:heartbeat",
        heartbeat_ttl: int = 10,
        poll_interval: float = 0.2,
        sleep=time.sleep,
    ) -> None:
        """常驻消费：存活即扇出（G1）；异常不退出（消费者死掉 = 永久不扇出）。"""
        last_autoclaim = time.monotonic()
        while not (stop_event.is_set() if stop_event is not None else self.stop):
            due = (time.monotonic() - last_autoclaim) >= autoclaim_every
            try:
                published = self.run_once(count=count, autoclaim=due)
            except Exception as exc:  # 不退出：记录后短暂退避重试
                _log("consumer_loop_error", error=repr(exc))
                sleep(1.0)
                continue
            if due:
                last_autoclaim = time.monotonic()
            if self._bus is not None:
                pending = self._bus.stream_pending(self._consumer)
                self._bus.set_key(heartbeat_key, f"{int(time.time())}:{pending}", heartbeat_ttl)
            if published == 0:
                (stop_event.wait(poll_interval) if stop_event is not None else sleep(poll_interval))


def _log(event: str, **fields) -> None:
    import sys

    print(
        json.dumps({"event": event, **fields}, ensure_ascii=False, sort_keys=True), file=sys.stderr
    )
