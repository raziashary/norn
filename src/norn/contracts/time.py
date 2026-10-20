"""Explicit clocks, bounded intervals, precision and ambiguous local times."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from norn.contracts.errors import NornError, require


def aware(value: datetime) -> datetime:
    require(
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None,
        "NAIVE_TIME",
    )
    return value.astimezone(UTC)


def parse_instant(value: str) -> datetime:
    require(type(value) is str and len(value) <= 80, "INVALID_TIME")
    try:
        return aware(datetime.fromisoformat(value))
    except ValueError:
        raise NornError("INVALID_TIME") from None


def stamp(value: datetime) -> str:
    return aware(value).isoformat(timespec="microseconds")


def zone(name: str) -> ZoneInfo:
    require(type(name) is str and 0 < len(name) <= 128, "INVALID_TIMEZONE")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        raise NornError("INVALID_TIMEZONE") from None


def local_instant(value: datetime, timezone: str, fold: int | None = None) -> datetime:
    require(value.tzinfo is None, "EXPECTED_LOCAL_TIME")
    require(fold in (None, 0, 1) and type(fold) is not bool, "INVALID_FOLD")
    tz = zone(timezone)
    candidates = []
    for choice in (0, 1):
        candidate = value.replace(tzinfo=tz, fold=choice)
        if candidate.astimezone(UTC).astimezone(tz).replace(tzinfo=None) == value:
            candidates.append(candidate)
    require(bool(candidates), "NONEXISTENT_LOCAL_TIME")
    ambiguous = len({c.utcoffset() for c in candidates}) > 1
    require(not ambiguous or fold is not None, "AMBIGUOUS_LOCAL_TIME")
    return aware(value.replace(tzinfo=tz, fold=fold or 0))


class TimeKind(StrEnum):
    EXACT = "EXACT"
    INTERVAL = "INTERVAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TimeValue:
    kind: TimeKind
    start: datetime | None = None
    end: datetime | None = None
    source_timezone: str = "UTC"
    precision: str = "microsecond"
    reason: str | None = None

    def __post_init__(self) -> None:
        require(type(self.kind) is TimeKind)
        zone(self.source_timezone)
        require(self.precision in {"microsecond", "second", "minute", "day", "unknown"})
        if self.kind == TimeKind.UNKNOWN:
            require(
                self.start is None
                and self.end is None
                and self.reason is not None
                and 0 < len(self.reason) <= 256
                and self.precision == "unknown"
            )
        else:
            require(self.reason is None and self.precision != "unknown")
            require(self.start is not None, "MISSING_TIME")
            if self.start is not None:
                object.__setattr__(self, "start", aware(self.start))
            if self.kind == TimeKind.EXACT:
                require(self.end is None and self.precision != "day", "FALSE_PRECISION")
            else:
                require(self.end is not None, "MISSING_TIME")
                if self.end is not None:
                    object.__setattr__(self, "end", aware(self.end))
                    require(self.start is not None and self.start < self.end, "INVALID_INTERVAL")

    def payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "start": stamp(self.start) if self.start else None,
            "end": stamp(self.end) if self.end else None,
            "source_timezone": self.source_timezone,
            "precision": self.precision,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class QueryClock:
    evaluation_time: datetime
    timezone: str
    basis: str
    valid_at: datetime
    knowledge_at: datetime
    snapshot: int | None = None

    def __post_init__(self) -> None:
        for name in ("evaluation_time", "valid_at", "knowledge_at"):
            object.__setattr__(self, name, aware(getattr(self, name)))
        zone(self.timezone)
        require(self.basis in {"EVENT_TIME", "VALID_TIME", "KNOWLEDGE_AT"})
        require(self.knowledge_at <= self.evaluation_time, "FUTURE_KNOWLEDGE")
        require(self.snapshot is None or (type(self.snapshot) is int and self.snapshot >= 0))
