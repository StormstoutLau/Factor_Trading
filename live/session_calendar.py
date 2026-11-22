"""交易日历与时段状态机（P-053 D12 / G11；synthetic 注入）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class SessionPhase(str, Enum):
    PRE_OPEN = "pre_open"
    CONTINUOUS = "continuous"
    LUNCH = "lunch"
    CLOSE_AUCTION = "close_auction"
    CLOSED = "closed"
    HOLIDAY = "holiday"


@dataclass(frozen=True)
class DaySession:
    morning: tuple[int, int] = (9 * 3600 + 30 * 60, 11 * 3600 + 30 * 60)
    afternoon: tuple[int, int] = (13 * 3600, 15 * 3600)
    close_auction: tuple[int, int] | None = (14 * 3600 + 57 * 60, 15 * 3600)
    pre_open: tuple[int, int] = (9 * 3600 + 15 * 60, 9 * 3600 + 30 * 60)


@dataclass(frozen=True)
class Calendar:
    trading_days: frozenset[str]
    session: DaySession = DaySession()
    tz: str = "Asia/Shanghai"


def local_day(ts: float, *, tz: str) -> str:
    return datetime.fromtimestamp(ts, tz=ZoneInfo(tz)).date().isoformat()


def is_trading_day(day: str, *, calendar: Calendar) -> bool:
    return day in calendar.trading_days


def session_phase(ts: float, *, calendar: Calendar) -> SessionPhase:
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo(calendar.tz))
    if dt.date().isoformat() not in calendar.trading_days:
        return SessionPhase.HOLIDAY
    sec = dt.hour * 3600 + dt.minute * 60 + dt.second
    s = calendar.session
    if s.pre_open[0] <= sec < s.pre_open[1]:
        return SessionPhase.PRE_OPEN
    if s.morning[0] <= sec < s.morning[1]:
        return SessionPhase.CONTINUOUS
    if s.morning[1] <= sec < s.afternoon[0]:
        return SessionPhase.LUNCH
    if s.close_auction is not None and s.close_auction[0] <= sec < s.close_auction[1]:
        return SessionPhase.CLOSE_AUCTION
    if s.afternoon[0] <= sec < (s.close_auction[0] if s.close_auction else s.afternoon[1]):
        return SessionPhase.CONTINUOUS
    return SessionPhase.CLOSED


def next_trading_day(day: str, *, calendar: Calendar) -> str | None:
    cursor = datetime.fromisoformat(day).date()
    for _ in range(31):
        cursor = cursor + timedelta(days=1)
        key = cursor.isoformat()
        if key in calendar.trading_days:
            return key
    return None


def can_submit(phase: SessionPhase, *, order_type: str = "limit") -> bool:
    """固定规则（F-D9）：无预埋（F-D10）；收盘竞价仅限价。"""
    if phase is SessionPhase.CONTINUOUS:
        return True
    if phase is SessionPhase.CLOSE_AUCTION:
        return order_type == "limit"
    return False
