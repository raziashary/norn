"""Bounded published-input controls, not retrieval algorithm implementations."""

import json
import random
from dataclasses import replace

from benchmark.adapters.contracts import ArmSpec, Candidate, PublicInput, PublishedSource, Result
from benchmark.fixtures.observations import Observation
from norn.contracts.errors import NornError, require
from norn.contracts.identity import digest


def parse_source(source: PublishedSource) -> Observation:
    require(digest(source.text.encode()) == source.sha256, "PUBLISHED_SOURCE_DIGEST")
    data = json.loads(source.text)
    require(type(data) is dict and set(data) == {"capture", "message"}, "PUBLISHED_SOURCE_SCHEMA")
    require(set(data["capture"]) == set(Observation.__dataclass_fields__), "CAPTURE_SCHEMA")
    capture = Observation(**data["capture"])
    require(capture == source.observation, "OBSERVATION_MISMATCH")
    return capture


def candidate(source: PublishedSource, *, unit_kind: str = "source") -> Candidate:
    ids = {"source": source.source_id, "event": source.event_id, "atom": source.atom_id}
    require(unit_kind in ids, "UNSUPPORTED_CANONICAL_UNIT")
    return Candidate(
        unit_kind, ids[unit_kind], source.source_id, 0, len(source.text.encode()), source.sha256
    )


def validate_result(published: PublicInput, result: Result, spec: ArmSpec) -> int:
    require(
        result.disposition in {"OK", "ERROR", "TIMEOUT", "UNSUPPORTED", "INVALID", "NOT_RUN"},
        "INVALID_DISPOSITION",
    )
    require(result.stage == "FINAL_EVIDENCE", "UNOBSERVED_METRIC_STAGE")
    require(
        type(result.provider_calls) is int and result.provider_calls == 0, "PROVIDER_NOT_ENABLED"
    )
    require(
        result.evidence_status
        in {
            None,
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "CONFLICT",
            "NOT_ESTABLISHED",
            "VERIFICATION_UNAVAILABLE",
        }
    )
    require(
        result.confidence is None
        or (type(result.confidence) in (int, float) and 0 <= result.confidence <= 1),
        "INVALID_CONFIDENCE",
    )
    require(
        type(result.missing_fields) is tuple
        and len(result.missing_fields) <= 100
        and all(type(f) is str and 0 < len(f) <= 128 for f in result.missing_fields),
        "INVALID_MISSING_FIELDS",
    )
    require(
        (result.evidence_status == "PARTIALLY_SUPPORTED") == bool(result.missing_fields),
        "PARTIAL_REQUIRES_EXPLICIT_UNKNOWNS",
    )
    if result.disposition != "OK":
        require(not result.candidates and result.evidence_status is None, "SUCCESS_SHAPED_FAILURE")
        return 0
    require(
        set(published.query.required_capabilities) <= set(spec.capabilities),
        "UNSUPPORTED_CAPABILITY_FALLBACK",
    )
    require(len(result.candidates) <= published.query.max_candidates, "CANDIDATE_BUDGET")
    sources = {s.source_id: s for s in published.sources}
    tokens = 0
    for item in result.candidates:
        require(item.source_id in sources, "OUTSIDE_PUBLISHED_SCOPE")
        source = sources[item.source_id]
        require(
            item.unit_id
            == {"source": source.source_id, "atom": source.atom_id, "event": source.event_id}.get(
                item.unit_kind
            ),
            "FORGED_IDENTITY",
        )
        require(
            type(item.start_byte) is int
            and type(item.end_byte) is int
            and 0 <= item.start_byte < item.end_byte <= len(source.text.encode()),
            "INVALID_LOCATOR",
        )
        raw = source.text.encode()
        try:
            raw[: item.start_byte].decode()
            text = raw[item.start_byte : item.end_byte].decode()
        except UnicodeDecodeError:
            raise NornError("INVALID_UTF8_LOCATOR") from None
        require(digest(text.encode()) == item.span_digest, "CITATION_DIGEST")
        # P02 publishes complete structured captures as its canonical evidence unit.
        # An unrelated substring of a correctly named source cannot earn support.
        require(item.start_byte == 0 and item.end_byte == len(raw), "INCOMPLETE_CAPTURE_LOCATOR")
        tokens += len(text.split())
    require(tokens <= published.query.max_evidence_tokens, "EVIDENCE_TOKEN_BUDGET")
    return tokens


class CommonControl:
    def __init__(self, name: str):
        require(
            name
            in {
                "empty",
                "shuffled",
                "extractive",
                "error",
                "timeout",
                "unsupported",
                "invalid",
                "not_run",
                "confidence",
            }
        )
        self.name = name
        self.spec = ArmSpec(name, "COMMON_INPUT", ("source_read",), "NONE", "PUBLISHED_ONLY")

    def query(self, published: PublicInput) -> Result:
        if not set(published.query.required_capabilities) <= set(self.spec.capabilities):
            return Result(
                "UNSUPPORTED", None, (), reason="FEATURE_NOT_SUPPORTED", coverage="UNAVAILABLE"
            )
        if published.query.coverage_state == "UNAVAILABLE":
            return Result(
                "OK",
                "VERIFICATION_UNAVAILABLE",
                (),
                coverage="UNAVAILABLE",
                reason="CAPTURE_VERIFICATION_UNAVAILABLE",
            )
        if self.name in {"error", "timeout", "unsupported", "not_run"}:
            return Result(
                self.name.upper(), None, (), coverage="UNAVAILABLE", reason="INJECTED_CONTROL"
            )
        if self.name == "empty" or not published.sources:
            return Result("OK", "NOT_ESTABLISHED", ())
        ordered = list(published.sources)
        if self.name == "shuffled":
            random.Random(published.query.query_id).shuffle(ordered)
        else:
            terms = set(published.query.text.lower().split())
            ordered.sort(
                key=lambda s: (-len(terms.intersection(s.text.lower().split())), s.source_id)
            )
        selected = ordered[:1]
        if self.name == "invalid":
            return Result("OK", "SUPPORTED", (replace(candidate(selected[0]), unit_id="forged"),))
        return Result(
            "OK",
            "SUPPORTED",
            tuple(candidate(s) for s in selected),
            confidence=0.5 if self.name == "confidence" else None,
        )


class NativeUnavailable:
    """Truthful native capability row; never a substitute implementation or fake score."""

    def __init__(self, name: str):
        self.spec = ArmSpec(name, "NATIVE", (), "NONE", "NOT_INSTALLED; NO_NATIVE_INGESTION")

    def query(self, published: PublicInput) -> Result:
        return Result(
            "UNSUPPORTED",
            None,
            (),
            coverage="UNAVAILABLE",
            reason="NATIVE_INTEGRATION_NOT_IMPLEMENTED",
        )
