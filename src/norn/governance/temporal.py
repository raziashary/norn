"""Read-only temporal interpretation using the request clock."""

from datetime import datetime, time, timedelta

from norn.contracts.errors import require
from norn.contracts.time import QueryClock, TimeKind, TimeValue, local_instant, zone


def yesterday(clock: QueryClock) -> TimeValue:
    day = clock.evaluation_time.astimezone(zone(clock.timezone)).date() - timedelta(days=1)
    start = local_instant(datetime.combine(day, time()), clock.timezone)
    end = local_instant(datetime.combine(day + timedelta(days=1), time()), clock.timezone)
    return TimeValue(TimeKind.INTERVAL, start, end, clock.timezone, "day")


def valid_interval(start: datetime, end: datetime | None) -> None:
    from norn.contracts.time import aware

    require(end is None or aware(start) < aware(end), "INVALID_INTERVAL")


def contains(start: str, end: str | None, point: str) -> bool:
    return start <= point and (end is None or point < end)
