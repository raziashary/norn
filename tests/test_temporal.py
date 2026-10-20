from datetime import UTC, datetime

import pytest

from norn.contracts.errors import NornError
from norn.contracts.time import QueryClock, TimeKind, TimeValue, local_instant, parse_instant
from norn.governance.temporal import yesterday


def test_no_naive_exact_or_fabricated_day_precision():
    with pytest.raises(NornError, match="NAIVE_TIME"):
        parse_instant("2026-10-20T09:00:00")
    with pytest.raises(NornError, match="FALSE_PRECISION"):
        TimeValue(TimeKind.EXACT, datetime.now(UTC), precision="day")
    unknown = TimeValue(TimeKind.UNKNOWN, precision="unknown", reason="unspecified")
    assert unknown.start is None


def test_dst_ambiguity_nonexistent_and_explicit_fold():
    local = datetime(2026, 11, 1, 1, 30)
    with pytest.raises(NornError, match="AMBIGUOUS_LOCAL_TIME"):
        local_instant(local, "America/New_York")
    assert (
        local_instant(local, "America/New_York", 1) - local_instant(local, "America/New_York", 0)
    ).total_seconds() == 3600
    with pytest.raises(NornError, match="NONEXISTENT_LOCAL_TIME"):
        local_instant(datetime(2026, 3, 8, 2, 30), "America/New_York")


def test_yesterday_uses_request_timezone_and_23_hour_day():
    now = datetime(2026, 3, 9, 16, tzinfo=UTC)
    value = yesterday(QueryClock(now, "America/New_York", "EVENT_TIME", now, now))
    assert (value.end - value.start).total_seconds() == 23 * 3600
    assert value.start.isoformat() == "2026-03-08T05:00:00+00:00"
