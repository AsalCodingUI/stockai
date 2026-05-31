"""IDX (Indonesia Stock Exchange) market calendar.

Provides trading day checks, market hours, and session status
for the Indonesia Stock Exchange (WIB / Asia/Jakarta timezone).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Union

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

# ---------------------------------------------------------------------------
# IDX Public Holidays 2024–2026
# ---------------------------------------------------------------------------

_IDX_HOLIDAYS: set[date] = {
    # 2024
    date(2024, 1, 1),   # New Year's Day
    date(2024, 2, 8),   # Imlek (Chinese New Year)
    date(2024, 3, 11),  # Isra Mi'raj
    date(2024, 3, 29),  # Good Friday
    date(2024, 4, 10),  # Eid Fitr eve (cuti bersama)
    date(2024, 4, 11),  # Eid Fitr day 1
    date(2024, 4, 12),  # Eid Fitr day 2
    date(2024, 5, 1),   # Labor Day
    date(2024, 5, 9),   # Ascension of Christ
    date(2024, 5, 23),  # Waisak
    date(2024, 6, 1),   # Pancasila Day
    date(2024, 6, 17),  # Eid Adha day 1
    date(2024, 6, 18),  # Eid Adha day 2
    date(2024, 7, 7),   # Islamic New Year (Muharram)
    date(2024, 8, 17),  # Independence Day
    date(2024, 9, 16),  # Maulid Nabi
    date(2024, 12, 25), # Christmas Day
    date(2024, 12, 26), # Christmas Holiday

    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 29),  # Imlek (Chinese New Year)
    date(2025, 3, 28),  # Isra Mi'raj
    date(2025, 3, 29),  # Nyepi (Balinese New Year)
    date(2025, 3, 31),  # Eid Fitr eve (cuti bersama)
    date(2025, 4, 1),   # Eid Fitr day 1
    date(2025, 4, 2),   # Eid Fitr day 2
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 1),   # Labor Day
    date(2025, 5, 12),  # Waisak
    date(2025, 5, 29),  # Ascension of Christ
    date(2025, 6, 1),   # Pancasila Day
    date(2025, 6, 6),   # Eid Adha
    date(2025, 6, 27),  # Islamic New Year (Muharram)
    date(2025, 8, 17),  # Independence Day
    date(2025, 9, 5),   # Maulid Nabi
    date(2025, 12, 25), # Christmas Day
    date(2025, 12, 26), # Christmas Holiday

    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 2, 17),  # Imlek (Chinese New Year)
    date(2026, 2, 18),  # Nyepi
    date(2026, 3, 19),  # Isra Mi'raj
    date(2026, 4, 2),   # Good Friday
    date(2026, 4, 20),  # Eid Fitr day 1
    date(2026, 4, 21),  # Eid Fitr day 2
    date(2026, 5, 1),   # Labor Day
    date(2026, 5, 14),  # Ascension of Christ
    date(2026, 5, 26),  # Waisak
    date(2026, 6, 1),   # Pancasila Day
    date(2026, 6, 4),   # Nyepi Saka 1948
    date(2026, 8, 17),  # Independence Day
    date(2026, 12, 25), # Christmas Day
}

# ---------------------------------------------------------------------------
# Trading session boundaries (WIB, as (hour, minute) tuples)
# ---------------------------------------------------------------------------

_PRE_OPEN_START  = (8, 45)
_SESSION1_START  = (9, 0)
_SESSION1_END    = (12, 0)
_BREAK_END       = (13, 30)   # session 2 start
_SESSION2_END    = (15, 50)
_POST_CLOSE_END  = (16, 0)


def _to_date(d: Union[date, datetime, None]) -> date:
    """Normalise any date/datetime/None to a :class:`date`."""
    if d is None:
        return datetime.now(JAKARTA_TZ).date()
    if isinstance(d, datetime):
        # Make sure we interpret it in Jakarta local time
        if d.tzinfo is None:
            d = JAKARTA_TZ.localize(d)
        return d.astimezone(JAKARTA_TZ).date()
    return d


def _to_datetime(dt: Union[datetime, None]) -> datetime:
    """Return a timezone-aware datetime in WIB, defaulting to now."""
    if dt is None:
        return datetime.now(JAKARTA_TZ)
    if dt.tzinfo is None:
        return JAKARTA_TZ.localize(dt)
    return dt.astimezone(JAKARTA_TZ)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_trading_day(d: Union[date, datetime, None] = None) -> bool:
    """Return True if *d* is a weekday that is not an IDX public holiday.

    Defaults to today (Jakarta time) when *d* is None.
    """
    day = _to_date(d)
    if day.weekday() >= 5:   # 5 = Saturday, 6 = Sunday
        return False
    return day not in _IDX_HOLIDAYS


def is_market_open(dt: Union[datetime, None] = None) -> bool:
    """Return True if the IDX market is currently open.

    The market is considered *open* during Session 1 (09:00–12:00) and
    Session 2 (13:30–15:50) on trading days.  Pre-open and post-close
    periods do **not** count as open.
    """
    now = _to_datetime(dt)
    if not is_trading_day(now):
        return False
    hm = (now.hour, now.minute)
    in_session1 = _SESSION1_START <= hm < _SESSION1_END
    in_session2 = _BREAK_END <= hm < _SESSION2_END
    return in_session1 or in_session2


def next_trading_day(d: Union[date, None] = None) -> date:
    """Return the first trading day that comes *after* *d*.

    Defaults to today (Jakarta time).
    """
    day = _to_date(d)
    candidate = day + timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def prev_trading_day(d: Union[date, None] = None) -> date:
    """Return the most recent trading day that comes *before* *d*.

    Defaults to today (Jakarta time).
    """
    day = _to_date(d)
    candidate = day - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def get_trading_days_between(start: date, end: date) -> list[date]:
    """Return every trading day in the closed interval [*start*, *end*]."""
    days: list[date] = []
    current = start
    while current <= end:
        if is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


def market_status() -> dict:
    """Return a snapshot of current IDX market status.

    Keys
    ----
    is_open : bool
        True when trading is actively happening.
    status : str
        Human-readable status string.
    session : str
        One of ``"pre_open"``, ``"session_1"``, ``"break"``,
        ``"session_2"``, ``"post_close"``, ``"closed"``.
    next_open : str | None
        ISO-8601 datetime string (WIB) for the next session open,
        or None if the next open cannot be determined within the
        look-ahead window.
    """
    now = _to_datetime(None)
    today = now.date()
    hm = (now.hour, now.minute)

    if not is_trading_day(today):
        next_day = next_trading_day(today)
        next_open_dt = JAKARTA_TZ.localize(
            datetime(next_day.year, next_day.month, next_day.day,
                     _SESSION1_START[0], _SESSION1_START[1])
        )
        return {
            "is_open": False,
            "status": "Market closed (non-trading day)",
            "session": "closed",
            "next_open": next_open_dt.isoformat(),
        }

    # Determine session
    if hm < _PRE_OPEN_START:
        session = "closed"
        status = "Market not yet open"
        next_open_dt = JAKARTA_TZ.localize(
            datetime(today.year, today.month, today.day,
                     _SESSION1_START[0], _SESSION1_START[1])
        )
    elif _PRE_OPEN_START <= hm < _SESSION1_START:
        session = "pre_open"
        status = "Pre-open (08:45–09:00 WIB)"
        next_open_dt = JAKARTA_TZ.localize(
            datetime(today.year, today.month, today.day,
                     _SESSION1_START[0], _SESSION1_START[1])
        )
    elif _SESSION1_START <= hm < _SESSION1_END:
        session = "session_1"
        status = "Session 1 open (09:00–12:00 WIB)"
        next_open_dt = None
    elif _SESSION1_END <= hm < _BREAK_END:
        session = "break"
        status = "Lunch break (12:00–13:30 WIB)"
        next_open_dt = JAKARTA_TZ.localize(
            datetime(today.year, today.month, today.day,
                     _BREAK_END[0], _BREAK_END[1])
        )
    elif _BREAK_END <= hm < _SESSION2_END:
        session = "session_2"
        status = "Session 2 open (13:30–15:50 WIB)"
        next_open_dt = None
    elif _SESSION2_END <= hm < _POST_CLOSE_END:
        session = "post_close"
        status = "Post-close (15:50–16:00 WIB)"
        next_day = next_trading_day(today)
        next_open_dt = JAKARTA_TZ.localize(
            datetime(next_day.year, next_day.month, next_day.day,
                     _SESSION1_START[0], _SESSION1_START[1])
        )
    else:
        session = "closed"
        status = "Market closed for today"
        next_day = next_trading_day(today)
        next_open_dt = JAKARTA_TZ.localize(
            datetime(next_day.year, next_day.month, next_day.day,
                     _SESSION1_START[0], _SESSION1_START[1])
        )

    is_open = session in ("session_1", "session_2")

    return {
        "is_open": is_open,
        "status": status,
        "session": session,
        "next_open": next_open_dt.isoformat() if next_open_dt else None,
    }
