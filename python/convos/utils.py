"""Utility functions for conversation extraction."""

from datetime import datetime, timedelta

import pytz


def utc(dt: datetime | int) -> datetime:
    """Convert datetime or timestamp to UTC timezone."""
    if isinstance(dt, int):
        dt = datetime.fromtimestamp(dt)
    if dt.tzinfo is None:
        return pytz.UTC.localize(dt)
    return dt.astimezone(pytz.UTC)


def allowed_gap(length: int) -> timedelta:
    """Calculate allowed gap between transcripts based on content length."""
    if length < 500:
        return timedelta(minutes=45)
    elif length < 20000:
        return timedelta(minutes=5)
    else:
        return timedelta(seconds=40)


def get_silence_message(gap: timedelta) -> str:
    """Generate silence message for gaps in conversation."""
    m = gap.total_seconds() / 60
    s = gap.total_seconds() % 60
    return f'silence for {m:.0f}m {s:.0f}s'


def get_timestamp_message(timestamp: datetime) -> str:
    """Generate timestamp message for conversation chunks."""
    return f'time: {utc(timestamp).isoformat()}'

