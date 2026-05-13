"""
Event Log — Append-only persistent event log with in-memory ring buffer.

借鉴 OpenAlice 设计:
- Dual-write: every append goes to disk (JSONL) AND an in-memory buffer
- The memory buffer holds the most recent N entries for fast queries
- Disk is the source of truth for crash recovery and full history

Storage: one JSON object per line (`events.jsonl`), append-only.
Recovery: on startup, loads the tail of the file into the memory buffer
and restores the seq counter.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class EventLogEntry:
    """事件日志条目"""

    seq: int
    ts: float
    type: str
    payload: dict[str, Any]
    source: str = ""  # 事件来源模块


EventListener = Callable[[EventLogEntry], None]


class EventLog:
    """
    持久化事件日志

    双写策略：磁盘(JSONL) + 内存(ring buffer)
    支持实时订阅、分页查询、类型过滤
    """

    def __init__(
        self,
        log_path: str | Path = "data/events.jsonl",
        buffer_size: int = 500,
        auto_flush: bool = True,
    ):
        self.log_path = Path(log_path)
        self.buffer_size = buffer_size
        self.auto_flush = auto_flush

        # Thread safety
        self._lock = threading.RLock()

        # In-memory ring buffer
        self._buffer: list[EventLogEntry] = []

        # Seq counter
        self._seq = 0

        # Listeners
        self._listeners: list[EventListener] = []
        self._type_listeners: dict[str, list[EventListener]] = {}

        # Ensure directory exists and recover state
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._recover_state()

        logger.info(
            f"EventLog initialized: path={self.log_path}, "
            f"buffer={len(self._buffer)}/{buffer_size}, seq={self._seq}"
        )

    # ==================== Core Operations ====================

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        source: str = "",
    ) -> EventLogEntry:
        """
        追加事件

        Args:
            event_type: 事件类型，如 "factor.calc", "trade.execute", "agent.decision"
            payload: 事件载荷数据
            source: 事件来源模块名

        Returns:
            持久化后的事件条目（含 seq/ts）
        """
        with self._lock:
            self._seq += 1
            entry = EventLogEntry(
                seq=self._seq,
                ts=__import__("time").time(),
                type=event_type,
                payload=payload,
                source=source,
            )

            # Dual write: disk first
            self._append_to_disk(entry)

            # Then memory
            self._buffer.append(entry)
            if len(self._buffer) > self.buffer_size:
                self._buffer = self._buffer[-self.buffer_size :]

            # Fan-out to subscribers
            self._notify_listeners(entry)

            return entry

    def read(
        self,
        after_seq: int = 0,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> list[EventLogEntry]:
        """
        从磁盘读取事件

        Args:
            after_seq: 只返回 seq > after_seq 的事件
            limit: 最大返回数量
            event_type: 只返回该类型的事件
        """
        results: list[EventLogEntry] = []

        if not self.log_path.exists():
            return results

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = self._parse_entry(json.loads(line))
                        if entry.seq <= after_seq:
                            continue
                        if event_type and entry.type != event_type:
                            continue
                        results.append(entry)
                        if limit and len(results) >= limit:
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.warning(f"EventLog read error: {e}")

        return results

    def query(
        self,
        page: int = 1,
        page_size: int = 100,
        event_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        分页查询（从磁盘，按时间倒序）

        Returns:
            {entries, total, page, page_size, total_pages}
        """
        all_entries = self.read(event_type=event_type)
        total = len(all_entries)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))

        # Newest first
        start = max(0, total - page * page_size)
        end = total - (page - 1) * page_size
        entries = list(reversed(all_entries[start:end]))

        return {
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def recent(
        self,
        after_seq: int = 0,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> list[EventLogEntry]:
        """
        查询内存 buffer（快速，无磁盘 IO）

        只能看到最近的 buffer_size 条事件
        """
        with self._lock:
            results: list[EventLogEntry] = []
            for entry in self._buffer:
                if entry.seq <= after_seq:
                    continue
                if event_type and entry.type != event_type:
                    continue
                results.append(entry)
                if limit and len(results) >= limit:
                    break
            return results

    def last_seq(self) -> int:
        """当前最大 seq 号"""
        with self._lock:
            return self._seq

    # ==================== Subscription ====================

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        """
        订阅所有事件

        Returns:
            取消订阅函数
        """
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe():
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def subscribe_type(
        self, event_type: str, listener: EventListener
    ) -> Callable[[], None]:
        """
        订阅特定类型事件

        Returns:
            取消订阅函数
        """
        with self._lock:
            if event_type not in self._type_listeners:
                self._type_listeners[event_type] = []
            self._type_listeners[event_type].append(listener)

        def unsubscribe():
            with self._lock:
                if event_type in self._type_listeners:
                    if listener in self._type_listeners[event_type]:
                        self._type_listeners[event_type].remove(listener)

        return unsubscribe

    # ==================== Helper Methods ====================

    def _append_to_disk(self, entry: EventLogEntry) -> None:
        """追加到磁盘文件"""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self._entry_to_dict(entry), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write event to disk: {e}")

    def _notify_listeners(self, entry: EventLogEntry) -> None:
        """通知所有订阅者"""
        # General listeners
        for fn in self._listeners:
            try:
                fn(entry)
            except Exception as e:
                logger.warning(f"Event listener error: {e}")

        # Type-specific listeners
        type_listeners = self._type_listeners.get(entry.type, [])
        for fn in type_listeners:
            try:
                fn(entry)
            except Exception as e:
                logger.warning(f"Event type listener error: {e}")

    def _recover_state(self) -> None:
        """从磁盘恢复状态"""
        if not self.log_path.exists():
            return

        try:
            entries: list[EventLogEntry] = []
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entries.append(self._parse_entry(data))
                    except (json.JSONDecodeError, KeyError):
                        continue

            if entries:
                # Load tail into buffer
                tail = entries[-self.buffer_size :]
                self._buffer = tail
                self._seq = entries[-1].seq

        except Exception as e:
            logger.warning(f"EventLog recovery error: {e}")

    def _parse_entry(self, data: dict[str, Any]) -> EventLogEntry:
        """从 dict 解析 EventLogEntry"""
        return EventLogEntry(
            seq=data["seq"],
            ts=data["ts"],
            type=data["type"],
            payload=data.get("payload", {}),
            source=data.get("source", ""),
        )

    def _entry_to_dict(self, entry: EventLogEntry) -> dict[str, Any]:
        """转换为 dict"""
        return {
            "seq": entry.seq,
            "ts": entry.ts,
            "type": entry.type,
            "payload": entry.payload,
            "source": entry.source,
        }

    def close(self) -> None:
        """关闭日志，清理资源"""
        with self._lock:
            self._listeners.clear()
            self._type_listeners.clear()
            self._buffer.clear()

    def reset(self) -> None:
        """重置所有状态并删除日志文件（仅用于测试）"""
        with self._lock:
            self._seq = 0
            self._buffer.clear()
            self._listeners.clear()
            self._type_listeners.clear()
            if self.log_path.exists():
                self.log_path.unlink()


# ==================== Convenience Functions ====================

_event_log_instance: Optional[EventLog] = None


def get_event_log(
    log_path: str | Path = "data/events.jsonl",
    buffer_size: int = 500,
) -> EventLog:
    """获取全局 EventLog 实例（单例模式）"""
    global _event_log_instance
    if _event_log_instance is None:
        _event_log_instance = EventLog(log_path=log_path, buffer_size=buffer_size)
    return _event_log_instance


def log_event(
    event_type: str,
    payload: dict[str, Any],
    source: str = "",
) -> Optional[EventLogEntry]:
    """
    快捷记录事件

    如果 EventLog 未初始化，自动创建默认实例
    """
    try:
        el = get_event_log()
        return el.append(event_type, payload, source)
    except Exception as e:
        logger.warning(f"log_event failed: {e}")
        return None
