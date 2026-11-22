"""查询调度器：最小间隔 + 单在途 + Full Jitter 退避（P-054 D8/U-P053-18）。"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from live.channel import ChannelUnavailable

T = TypeVar("T")


@dataclass(frozen=True)
class BackoffPolicy:
    initial: float = 1.0
    factor: float = 2.0
    cap: float = 5.0
    max_attempts: int = 5

    def high(self, attempt: int) -> float:
        return min(self.initial * (self.factor ** (attempt - 1)), self.cap)

    def delay(self, attempt: int, rng: random.Random) -> float:
        """Full Jitter：``uniform(0, min(initial×factor^(n-1), cap))``（Q5/§14.4）。"""
        return rng.uniform(0.0, self.high(attempt))


class QueryScheduler:
    """单在途 + 相邻间隔 ≥ ``1/query_per_sec``；``-2/-3`` 退避重试（I10）。"""

    def __init__(
        self,
        *,
        query_per_sec: float = 1.0,
        backoff: BackoffPolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self._min_interval = 1.0 / query_per_sec if query_per_sec > 0 else 0.0
        self._backoff = backoff or BackoffPolicy()
        self._clock = clock
        self._sleep = sleep
        self._rng = rng or random.Random(7)
        self._lock = threading.Lock()
        self._last: float | None = None
        self.attempts = 0
        self.calls = 0

    @property
    def min_interval(self) -> float:
        return self._min_interval

    def _wait_slot(self) -> None:
        if self._last is not None:
            wait = self._last + self._min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def run(self, fn: Callable[[], T], *, retry: bool = True) -> T:
        with self._lock:  # 单在途：并发调用串行化
            self.calls += 1
            self._wait_slot()
            attempt = 0
            while True:
                attempt += 1
                self.attempts = attempt
                try:
                    return fn()
                except ChannelUnavailable as exc:
                    if not retry or attempt >= self._backoff.max_attempts:
                        raise ChannelUnavailable(str(exc)) from exc
                    self._sleep(self._backoff.delay(attempt, self._rng))
                    self._wait_slot()
