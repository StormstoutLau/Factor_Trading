"""鉴权：API Key（常数时间）/ 角色 / 一次性 ticket / 认证失败限流（D14）。"""

from __future__ import annotations

import hmac
import threading
import time
from dataclasses import dataclass

from services.contracts import TicketStore


class Role:
    READER = "reader"
    OPERATOR = "operator"
    ADMIN = "admin"


_ROLE_RANK = {Role.READER: 1, Role.OPERATOR: 2, Role.ADMIN: 3}


@dataclass(frozen=True)
class KeySet:
    reader_key: str
    operator_key: str = ""
    admin_key: str = ""

    def role_for(self, provided: str) -> str | None:
        """常数时间比较；返回满足的最高角色。"""
        role: str | None = None
        if self.reader_key and hmac.compare_digest(provided, self.reader_key):
            role = Role.READER
        if self.operator_key and hmac.compare_digest(provided, self.operator_key):
            role = Role.OPERATOR
        if self.admin_key and hmac.compare_digest(provided, self.admin_key):
            role = Role.ADMIN
        return role


def has_role(actual: str | None, required: str) -> bool:
    if actual is None:
        return False
    return _ROLE_RANK.get(actual, 0) >= _ROLE_RANK.get(required, 99)


class AuthRateLimiter:
    """认证失败限流：``max_failures`` / ``window`` 秒 / IP（内存，进程内）。"""

    def __init__(self, *, max_failures: int = 10, window: float = 60.0) -> None:
        self._max = max_failures
        self._window = window
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}

    def _prune(self, ip: str, now: float) -> list[float]:
        stamps = [t for t in self._failures.get(ip, []) if now - t < self._window]
        self._failures[ip] = stamps
        return stamps

    def allow(self, ip: str, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        with self._lock:
            return len(self._prune(ip, current)) < self._max

    def record_failure(self, ip: str, now: float | None = None) -> None:
        current = time.time() if now is None else now
        with self._lock:
            stamps = self._prune(ip, current)
            stamps.append(current)
            self._failures[ip] = stamps

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)


class InMemoryTicketStore:
    """单进程 ticket：``issue`` 覆盖旧值，``consume`` 单次（GETDEL 语义）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens: dict[str, float] = {}

    def issue(self, token: str, ttl: int, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        with self._lock:
            self._tokens[token] = current + ttl
            return True

    def consume(self, token: str, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        with self._lock:
            expires = self._tokens.pop(token, None)
            return expires is not None and expires >= current


class RedisTicketStore:
    """多 worker 共享：``SET NX EX`` + ``GETDEL``（D14）。"""

    def __init__(self, client, *, prefix: str = "p054:ticket:") -> None:
        self._client = client
        self._prefix = prefix

    def issue(self, token: str, ttl: int) -> bool:
        return bool(self._client.set(f"{self._prefix}{token}", "1", nx=True, ex=ttl))

    def consume(self, token: str) -> bool:
        value = self._client.getdel(f"{self._prefix}{token}")
        return value is not None


def issue_ticket(store: TicketStore, token: str, ttl: int = 30) -> bool:
    return store.issue(token, ttl)


def consume_ticket(store: TicketStore, token: str) -> bool:
    return store.consume(token)
