"""Public-only source-record ingestion and explicit schema-based question interpretation."""

import re
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from benchmark.adapters import r0, r1, r2, r3
from benchmark.adapters.common import candidate, parse_source
from benchmark.adapters.contracts import ArmSpec, PublicInput, Result
from norn.canonical.registry import WriteRequest
from norn.contracts.errors import require
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
from norn.contracts.identity import Namespace
from norn.contracts.time import QueryClock, TimeKind, TimeValue, parse_instant
from norn.extraction.atoms import FixtureAtom
from norn.governance.access import HostIdentity
from norn.integration.engine import Engine
from norn.retrieval.contracts import RecallRequest

INTERPRETER = "public-question-fields-v3-source-independent-prerequisites"
# Frozen pilot vocabulary. It does not receive task category, gold values or required slots.
SCHEMA_CUES = (
    (("correction", "koreksi"), ("parked_in", "corrects_parking")),
    (("approve", "disetujui"), ("approved_zone",)),
    (("invoice", "tagihan"), ("invoice_amount",)),
    (("release and rollback", "rilis dan rollback"), ("release", "rollback")),
    (("exception", "pengecualian"), ("latency_ms", "exception_ended")),
    (("cause", "penyebab"), ("caused",)),
    (("parking", "parkir", "parked"), ("parked_in",)),
    (("requirement", "ketergantungan"), ("requires",)),
)


def spec(arm: str) -> ArmSpec:
    require(arm in {"R0", "R1", "R2", "R3"}, "UNSUPPORTED_ARM")
    return {"R0": r0.SPEC, "R1": r1.SPEC, "R2": r2.SPEC, "R3": r3.SPEC}[arm]


def host(published: PublicInput) -> HostIdentity:
    return HostIdentity(Namespace(*published.query.namespace.split("/")), published.query.principal)


def prepare(published: PublicInput, root: Path, model_root: Path, enabled: bool) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    require(not root.exists(), "BASELINE_STORE_EXISTS")
    start = time.perf_counter_ns()
    with Engine(
        root, host(published), create=True, model_root=model_root, enable_models=True
    ) as engine:
        engine.access.bootstrap()
        mapping = {}
        for source in published.sources:
            observation = parse_source(source)
            content = source.text.encode()
            fixture = FixtureAtom(
                observation.actor,
                observation.predicate,
                TaggedValue("TEXT", observation.value),
                0,
                len(content),
                EpistemicState(Epistemic(observation.origin)),
            )
            receipt = engine.write(
                WriteRequest(
                    source.source_id,
                    host(published).principal,
                    source.source_id,
                    source.source_id,
                    content,
                    TimeValue(TimeKind.EXACT, parse_instant(observation.event_time)),
                    parse_instant(observation.event_time),
                    (fixture,),
                )
            )
            mapping[receipt["atom_ids"][0]] = source.source_id
        projection = engine.project()
    return {
        "offline_ns": time.perf_counter_ns() - start,
        "projection": projection,
        "mapping": mapping,
        "input_digest": published.sha256,
        "profile": "DISTINCT_PUBLISHED_SOURCE_OCCURRENCES",
    }


def interpret(published: PublicInput, arm: str) -> RecallRequest:
    query = published.query
    text = query.text.casefold()
    actors = sorted(
        {
            s.observation.actor
            for s in published.sources
            if re.search(r"(?<!\w)" + re.escape(s.observation.actor.casefold()) + r"(?!\w)", text)
        }
    )
    subject = actors[0] if len(actors) == 1 else None
    fields: tuple[str, ...] = ()
    # A requested field remains a prerequisite when its evidence is absent. Combine
    # the declared pilot schema with observed extensions; never infer requirements
    # solely from the fields that happened to survive publication.
    vocabulary = {field for _cues, required in SCHEMA_CUES for field in required}
    vocabulary.update(s.observation.predicate for s in published.sources)
    predicates = sorted(
        {
            predicate
            for predicate in vocabulary
            if re.search(r"(?<!\w)" + re.escape(predicate) + r"(?!\w)", text)
        }
    )
    prerequisites = set(predicates)
    for cues, required in SCHEMA_CUES:
        if any(cue in text for cue in cues):
            prerequisites.update(required)
            break
    fields = tuple(sorted(prerequisites))
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", query.text)
    if re.search(r"\b(chain|links|rantai|tautan)\b", text):
        # A chain's root is a retrieval cue, not a global subject eligibility filter.
        # Field-only sufficiency cannot adjudicate a complete typed path; retain the
        # retrieved sources without claiming that one 'requires' atom proves it.
        subject, fields = None, ()
    start = parse_instant(dates[0] + "T00:00:00+00:00") if len(set(dates)) == 1 else None
    evaluation, knowledge = parse_instant(query.evaluation_time), parse_instant(query.knowledge_at)
    clock = QueryClock(evaluation, query.timezone, "EVENT_TIME", evaluation, knowledge)
    return RecallRequest(
        query.text,
        clock,
        arm=arm,
        subject=subject,
        requested_fields=fields,
        event_start=start,
        event_end=start + timedelta(days=1) if start else None,
        candidate_limit=query.max_candidates,
        final_limit=query.max_candidates,
        max_evidence_tokens=query.max_evidence_tokens,
        deadline_ms=120_000,
    )


class Baseline:
    def __init__(
        self, arm: str, root: Path, model_root: Path, enabled: bool, prepared: dict[str, Any]
    ):
        self.spec = spec(arm)
        self.root, self.model_root, self.enabled, self.prepared = (
            root,
            model_root,
            enabled,
            prepared,
        )
        self.diagnostics: dict[str, Any] = {}

    def query(self, published: PublicInput) -> Result:
        require(published.sha256 == self.prepared["input_digest"], "ARM_INPUT_CHANGED")
        if not set(published.query.required_capabilities) <= set(self.spec.capabilities):
            return Result(
                "UNSUPPORTED", None, (), coverage="UNAVAILABLE", reason="FEATURE_NOT_SUPPORTED"
            )
        if published.query.coverage_state == "UNAVAILABLE":
            return Result(
                "OK",
                "VERIFICATION_UNAVAILABLE",
                (),
                coverage="UNAVAILABLE",
                reason="CAPTURE_VERIFICATION_UNAVAILABLE",
            )
        query = interpret(published, self.spec.arm_id)
        started = time.perf_counter_ns()
        with Engine(
            self.root, host(published), model_root=self.model_root, enable_models=self.enabled
        ) as engine:
            packet = engine.recall(query).serialize()
            cold_ns = time.perf_counter_ns() - started
            started = time.perf_counter_ns()
            warm = engine.recall(query).serialize()
            warm_ns = time.perf_counter_ns() - started
        mapping = self.prepared["mapping"]
        sources = {s.source_id: s for s in published.sources}
        candidates = []
        for record in packet["evidence"]:
            require(record["atom_id"] in mapping, "SOURCE_MAPPING_MISSING")
            source = sources[mapping[record["atom_id"]]]
            require(
                record["text"] == source.text and record["sha256"] == source.sha256,
                "SOURCE_MAPPING_MISMATCH",
            )
            candidates.append(candidate(source))
        self.diagnostics = {
            "packet": {
                key: packet[key] for key in ("status", "reason", "missing_fields", "evidence")
            },
            "trace": packet["trace"],
            "warm_trace": warm["trace"],
            "warm_packet": {
                key: warm[key] for key in ("status", "reason", "missing_fields", "evidence")
            },
            "warm_status": warm["status"],
            "warm_reason": warm["reason"],
            "repeat_unchanged": packet["status"] == warm["status"]
            and packet["evidence"] == warm["evidence"],
            "cold_ns": cold_ns,
            "warm_ns": warm_ns,
            "packet_tokens": packet.get("evidence_tokens", 0),
            "tokenizer": packet.get("tokenizer"),
            "cache": "SECOND_QUERY_SAME_ENGINE_ONE_RESIDENT_MODEL; R3_SWITCHES_MODELS",
            "interpreter": INTERPRETER,
            "semantic_scope": "FIELD_SUPPORT_ONLY; NO_TYPED_PATH_VERIFICATION",
            "resources": packet.get("resource_observation"),
            "possibly_truncated_model_input": packet.get("possibly_truncated_model_input"),
        }
        if "DEADLINE" in packet["reason"] or packet["reason"] == "QUERY_CANCELLED":
            return Result("TIMEOUT", None, (), coverage="UNAVAILABLE", reason=packet["reason"])
        return Result(
            "OK",
            packet["status"],
            tuple(candidates),
            coverage=packet["coverage"],
            reason=packet["reason"],
            missing_fields=tuple(packet["missing_fields"]),
        )
