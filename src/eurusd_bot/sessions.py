from __future__ import annotations

from datetime import datetime, time


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def in_window(timestamp: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    current = timestamp.time()
    start = parse_hhmm(start_hhmm)
    end = parse_hhmm(end_hhmm)
    return start <= current <= end


def should_analyze(timestamp: datetime, interval_minutes: int) -> bool:
    total = timestamp.hour * 60 + timestamp.minute
    return total % interval_minutes == 0

