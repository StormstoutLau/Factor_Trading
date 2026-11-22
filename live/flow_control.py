"""通道流控前置包：FTD 共享预算 + order-flow 合并预算（P-054 D9/D10）。"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_ms: int = 0
    reason: str = ""  # "ftd" | "order_flow" | "per_second" | "daily" | ""


@dataclass(frozen=True)
class CancelResult:
    accepted: bool
    reason: str = (
        ""  # "" | "not_found" | "terminal" | "rate_order_flow" | "rate_ftd" | "unsupported"
    )
    retry_after_ms: int = 0


def _retry_after_ms(now: float) -> int:
    return max(1, int((1.0 - (now % 1.0)) * 1000))


class FtdBudget:
    """整秒窗共享预算：``max_per_sec`` 总计，``reserve`` 仅 cancel 可用（D9）。"""

    def __init__(self, *, max_per_sec: float = 6.0, reserve: int = 1) -> None:
        self._max = max(0, int(max_per_sec))
        self._reserve = max(0, int(reserve))
        self._lock = threading.Lock()
        self._sec = -1
        self._count = 0

    def _roll(self, now: float) -> None:
        sec = int(now // 1)
        if sec != self._sec:
            self._sec = sec
            self._count = 0

    def _limit(self, *, cancel: bool) -> int:
        return self._max if cancel else max(0, self._max - self._reserve)

    def try_reserve(self, now: float, *, cancel: bool = False) -> Decision:
        with self._lock:
            self._roll(now)
            if self._count >= self._limit(cancel=cancel):
                return Decision(False, _retry_after_ms(now), "ftd")
            self._count += 1
            return Decision(True)

    def release(self, *, cancel: bool = False) -> None:
        with self._lock:
            if self._count > 0:
                self._count -= 1

    def remaining(self, now: float, *, cancel: bool = False) -> int:
        with self._lock:
            self._roll(now)
            return max(0, self._limit(cancel=cancel) - self._count)


class OrderFlowBudget:
    """报单+撤单合并额度：容量 ``2 × internal``，submit 不能用撤单保留槽（D10）。"""

    def __init__(self, *, max_per_sec: float = 2.0, reserve_cancel: int = 1) -> None:
        self._max = max(1, int(max_per_sec))
        self._reserve = max(0, int(reserve_cancel))
        self._per_type = max(1, self._max // 2)
        self._lock = threading.Lock()
        self._sec = -1
        self._counts = {"submit": 0, "cancel": 0}

    def _roll(self, now: float) -> None:
        sec = int(now // 1)
        if sec != self._sec:
            self._sec = sec
            self._counts = {"submit": 0, "cancel": 0}

    def _limit(self, kind: str) -> int:
        if kind == "submit":
            return max(0, self._max - self._reserve)
        return self._max

    def try_reserve(self, now: float, *, kind: str = "submit") -> Decision:
        with self._lock:
            self._roll(now)
            if sum(self._counts.values()) >= self._max:
                return Decision(False, _retry_after_ms(now), "order_flow")
            if self._counts[kind] >= self._limit(kind):
                # submit 的保留槽被撤单占用 → 合并额度型拒绝（D10）
                return Decision(False, _retry_after_ms(now), "order_flow")
            if self._counts[kind] >= self._per_type:
                return Decision(False, _retry_after_ms(now), "per_second")
            self._counts[kind] += 1
            return Decision(True)

    def release(self, *, kind: str = "submit") -> None:
        with self._lock:
            if self._counts.get(kind, 0) > 0:
                self._counts[kind] -= 1

    def remaining(self, now: float, *, kind: str = "submit") -> int:
        with self._lock:
            self._roll(now)
            return max(0, min(self._per_type, self._limit(kind)) - self._counts[kind])
