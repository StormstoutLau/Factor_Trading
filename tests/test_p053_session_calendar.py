"""P-053 T 组：交易日历与时段（T7，8 例）。"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from live.session_calendar import (
    Calendar,
    SessionPhase,
    can_submit,
    local_day,
    next_trading_day,
    session_phase,
)

TZ = "Asia/Shanghai"
CAL = Calendar(trading_days=frozenset({"2026-01-05", "2026-01-06"}), tz=TZ)


def _ts(day: str = "2026-01-05", hour: int = 10, minute: int = 0) -> float:
    year, month, dom = (int(part) for part in day.split("-"))
    return datetime(year, month, dom, hour, minute, tzinfo=ZoneInfo(TZ)).timestamp()


def test_t7_holiday():
    assert session_phase(_ts("2026-01-03", 10, 0), calendar=CAL) is SessionPhase.HOLIDAY


def test_t7_pre_open():
    assert session_phase(_ts(hour=9, minute=20), calendar=CAL) is SessionPhase.PRE_OPEN


def test_t7_continuous_morning():
    assert session_phase(_ts(hour=10, minute=0), calendar=CAL) is SessionPhase.CONTINUOUS


def test_t7_lunch():
    assert session_phase(_ts(hour=12, minute=0), calendar=CAL) is SessionPhase.LUNCH


def test_t7_close_auction():
    assert session_phase(_ts(hour=14, minute=58), calendar=CAL) is SessionPhase.CLOSE_AUCTION


def test_t7_closed_after_close():
    assert session_phase(_ts(hour=15, minute=30), calendar=CAL) is SessionPhase.CLOSED


def test_t7_can_submit_combinations():
    assert can_submit(SessionPhase.CONTINUOUS, order_type="market") is True
    assert can_submit(SessionPhase.CLOSE_AUCTION, order_type="limit") is True
    assert can_submit(SessionPhase.CLOSE_AUCTION, order_type="market") is False
    assert can_submit(SessionPhase.PRE_OPEN) is False


def test_t7_next_trading_day_and_timezone_boundary():
    assert next_trading_day("2026-01-02", calendar=CAL) == "2026-01-05"
    # UTC 2026-01-04 16:30 = Asia/Shanghai 2026-01-05 00:30
    boundary = datetime(2026, 1, 4, 16, 30, tzinfo=timezone.utc).timestamp()
    assert local_day(boundary, tz=TZ) == "2026-01-05"
