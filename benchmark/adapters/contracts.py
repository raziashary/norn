"""Public source/query/result records independent of evaluator construction."""

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from benchmark.fixtures.observations import Observation
from norn.contracts.errors import require
from norn.contracts.identity import Namespace, canonical, digest
from norn.contracts.time import parse_instant, zone


@dataclass(frozen=True)
class PublishedSource:
    source_id: str
    event_id: str
    atom_id: str
    text: str
    sha256: str
    namespace: str
    allowed_principals: tuple[str, ...]
    observation: Observation
    independence_group: str

    def __post_init__(self) -> None:
        for kind in ("source", "event", "atom"):
            require(
                re.fullmatch(kind + r"_[0-9a-f]{64}", getattr(self, kind + "_id")) is not None,
                "INVALID_PUBLIC_ID",
            )
        require(type(self.text) is str and 0 < len(self.text.encode()) <= 1_048_576)
        require(digest(self.text.encode()) == self.sha256, "PUBLISHED_SOURCE_DIGEST")
        require(type(self.allowed_principals) is tuple and bool(self.allowed_principals))
        require(isinstance(self.observation, Observation))

    def public(self) -> dict[str, Any]:
        result = asdict(self)
        result["allowed_principals"] = list(self.allowed_principals)
        return result


@dataclass(frozen=True)
class Query:
    query_id: str
    text: str
    namespace: str
    principal: str
    evaluation_time: str
    knowledge_at: str
    timezone: str
    max_candidates: int
    max_evidence_tokens: int
    required_capabilities: tuple[str, ...] = ("source_read",)
    coverage_state: str = "CANONICAL_FALLBACK"

    def __post_init__(self) -> None:
        require(re.fullmatch(r"query_[0-9a-f]{64}", self.query_id) is not None, "INVALID_QUERY_ID")
        parts = self.namespace.split("/")
        require(len(parts) == 3, "INVALID_NAMESPACE")
        Namespace(*parts)
        zone(self.timezone)
        require(self.coverage_state in {"CANONICAL_FALLBACK", "UNAVAILABLE"})
        require(parse_instant(self.knowledge_at) <= parse_instant(self.evaluation_time))
        require(type(self.text) is str and 0 < len(self.text) <= 16_384)
        require(type(self.max_candidates) is int and 1 <= self.max_candidates <= 1000)
        require(type(self.max_evidence_tokens) is int and 1 <= self.max_evidence_tokens <= 100_000)


@dataclass(frozen=True)
class PublicInput:
    query: Query
    sources: tuple[PublishedSource, ...]

    def __post_init__(self) -> None:
        require(type(self.sources) is tuple and len(self.sources) <= 10_000)
        require(len({s.source_id for s in self.sources}) == len(self.sources), "DUPLICATE_SOURCE")
        for source in self.sources:
            require(
                source.namespace == self.query.namespace
                and self.query.principal in source.allowed_principals,
                "PUBLIC_PERMISSION_LEAK",
            )
            require(
                parse_instant(source.observation.recorded_at)
                <= parse_instant(self.query.knowledge_at),
                "PUBLIC_TEMPORAL_LEAK",
            )

    def payload(self) -> dict[str, Any]:
        return {"query": asdict(self.query), "sources": [s.public() for s in self.sources]}

    @property
    def sha256(self) -> str:
        return digest(canonical(self.payload()).encode())


@dataclass(frozen=True)
class Candidate:
    unit_kind: str
    unit_id: str
    source_id: str
    start_byte: int
    end_byte: int
    span_digest: str


@dataclass(frozen=True)
class Result:
    disposition: str
    evidence_status: str | None
    candidates: tuple[Candidate, ...]
    stage: str = "FINAL_EVIDENCE"
    coverage: str = "CANONICAL_FALLBACK"
    reason: str = "CONTROL_OUTPUT"
    confidence: float | None = None
    provider_calls: int = 0
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArmSpec:
    arm_id: str
    track: str
    capabilities: tuple[str, ...]
    model: str
    source_visibility: str
    tokenizer: str = "whitespace-v1"

    def __post_init__(self) -> None:
        require(self.track in {"COMMON_INPUT", "NATIVE", "ORACLE_DIAGNOSTIC"})
        require(self.model == "NONE", "MODEL_NOT_ENABLED")
        require(self.tokenizer == "whitespace-v1", "UNSUPPORTED_TOKENIZER")


class Adapter(Protocol):
    spec: ArmSpec

    def query(self, published: PublicInput) -> Result: ...
