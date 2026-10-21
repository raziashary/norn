"""Typed recall contracts; query prerequisites are host/query inputs, never evaluator gold."""

from dataclasses import dataclass
from datetime import datetime

from norn.contracts.errors import require
from norn.contracts.identity import label
from norn.contracts.time import QueryClock, aware


@dataclass(frozen=True)
class RecallRequest:
    text: str
    clock: QueryClock
    arm: str = "R0"
    event_id: str | None = None
    atom_id: str | None = None
    entity_id: str | None = None
    subject: str | None = None
    predicates: tuple[str, ...] = ()
    event_start: datetime | None = None
    event_end: datetime | None = None
    requested_fields: tuple[str, ...] = ()
    candidate_limit: int = 20
    final_limit: int = 10
    max_evidence_tokens: int = 2000
    max_scan_records: int = 10_000
    deadline_ms: int = 30_000

    def __post_init__(self) -> None:
        require(type(self.text) is str and 0 < len(self.text) <= 16_384)
        require(self.arm in {"R0", "R1", "R2", "R3"}, "UNSUPPORTED_ARM")
        require(isinstance(self.clock, QueryClock))
        for value in (self.event_id, self.atom_id, self.entity_id, self.subject):
            if value is not None:
                label(value)
        require(type(self.predicates) is tuple and len(self.predicates) <= 32)
        require(type(self.requested_fields) is tuple and len(self.requested_fields) <= 32)
        for value in (*self.predicates, *self.requested_fields):
            label(value)
        for name in ("event_start", "event_end"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, aware(getattr(self, name)))
        require(
            self.event_end is None
            or (self.event_start is not None and self.event_start < self.event_end),
            "INVALID_EVENT_WINDOW",
        )
        require(type(self.candidate_limit) is int and 1 <= self.candidate_limit <= 1000)
        require(type(self.final_limit) is int and 1 <= self.final_limit <= self.candidate_limit)
        require(type(self.max_evidence_tokens) is int and 1 <= self.max_evidence_tokens <= 100_000)
        require(type(self.max_scan_records) is int and 1 <= self.max_scan_records <= 100_000)
        require(type(self.deadline_ms) is int and 1 <= self.deadline_ms <= 600_000)


@dataclass(frozen=True)
class Record:
    namespace: str
    event_id: str
    atom_id: str
    subject_id: str
    aliases: tuple[str, ...]
    predicate: str
    value_json: str
    qualifiers_json: str
    origin: str | None
    authority: str
    status: str
    applicability: str
    event_time: str
    source_id: str
    source_version: str
    start_byte: int
    end_byte: int
    sha256: str
    text: str
    snapshot: int

    @property
    def key(self) -> str:
        return self.atom_id + ":" + self.source_version + ":" + str(self.start_byte)


@dataclass(frozen=True)
class Hit:
    record: Record
    score: float
    channel: str


@dataclass(frozen=True)
class EligibleCorpus:
    records: tuple[Record, ...]
    snapshot: int
    security_epoch: int
    complete: bool
    reason: str | None
