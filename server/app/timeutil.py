"""UTC time helpers.

All timestamps are stored as timezone-aware UTC.  We normalise to naive UTC
before writing so SQLite and PostgreSQL behave identically.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current time as a naive UTC datetime (comparable and storable)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc(value: datetime | None) -> datetime | None:
    """Normalise any datetime to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None)


def month_bounds(reference: datetime, reset_day: int = 1) -> tuple[datetime, datetime]:
    """Return (start, end) of the quota period containing ``reference``.

    ``reset_day`` is the day of month the period starts on.  Values > 28 are
    clamped to 28 to avoid short-month ambiguity.  ``end`` is exclusive.
    """
    reset_day = max(1, min(28, reset_day))
    ref = to_utc(reference) or utcnow()
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if ref.day >= reset_day:
        start = start.replace(day=reset_day)
    else:
        # previous month
        prev_month_last = start - _one_day()
        start = prev_month_last.replace(day=reset_day)
    end = _add_month(start, reset_day)
    return start, end


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


def _add_month(dt: datetime, reset_day: int) -> datetime:
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return dt.replace(year=year, month=month, day=reset_day)