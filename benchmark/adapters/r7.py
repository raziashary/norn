"""Public-only binding capture/adapter. Gold, partitions and target labels never enter here."""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from benchmark.adapters.baseline import interpret
from benchmark.adapters.common import candidate, parse_source
from benchmark.adapters.contracts import ArmSpec, PublicInput, Result
from benchmark.adapters.r8 import SPECS as LEARNED_SPECS
from norn.canonical.registry import WriteRequest
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
from norn.contracts.time import TimeKind, TimeValue, parse_instant
from norn.embedding.feature_encoder import FeatureEncoder
from norn.extraction.atoms import FixtureAtom
from norn.features import views
from norn.integration.engine import Engine
from norn.retrieval.exact import eligible

SPECS = {
    **{
        variant: ArmSpec(
            variant,
            "COMMON_INPUT",
            ("source_read",),
            LEARNED_SPECS["B3"].model,
            "PUBLIC_SOURCE_RECORDS_ONLY",
            "e5-small-pinned-tokenizer-v1",
        )
        for variant in ("B0", "B1", "B2")
    },
    **LEARNED_SPECS,
}
ACTION = re.compile(r"step=(\d{1,2});tool=([\w-]{1,64});result=([\w-]{1,64});at=([^|]{1,80})")


def ingest(engine: Engine, published: PublicInput) -> dict[str, str]:
    require(engine.access.ns == published.query.namespace, "ARM_NAMESPACE_MISMATCH")
    mapping = {}
    for source in published.sources:
        capture = parse_source(source)
        qualifiers: list[tuple[tuple[str, str], ...]] = [()]
        if capture.predicate == "parked_in":
            qualifiers = [(("location", capture.value),)]
        if capture.predicate == "observed_action":
            qualifiers = []
            for encoded in capture.value.split("|"):
                match = ACTION.fullmatch(encoded)
                require(match is not None, "ACTION_CAPTURE_SCHEMA")
                assert match is not None
                step, tool, result, observed = match.groups()
                parse_instant(observed)
                qualifiers.append(
                    (
                        ("action_step", step),
                        ("attempted_tool", tool),
                        ("observed_result", result),
                        ("observed_at", observed),
                    )
                )
        fixtures = tuple(
            FixtureAtom(
                capture.actor,
                capture.predicate,
                TaggedValue("TEXT", capture.value),
                0,
                len(source.text.encode()),
                EpistemicState(Epistemic(capture.origin)),
                q,
            )
            for q in qualifiers
        )
        receipt = engine.write(
            WriteRequest(
                source.source_id,
                engine.access.host.principal,
                source.source_id,
                source.source_id,
                source.text.encode(),
                TimeValue(TimeKind.EXACT, parse_instant(capture.event_time)),
                parse_instant(capture.event_time),
                fixtures,
            )
        )
        mapping.update({atom: source.source_id for atom in receipt["atom_ids"]})
    return mapping


def capture(engine: Engine, published: PublicInput, mapping: dict[str, str]) -> dict[str, Any]:
    """Real frozen features through current public canonical readback, without target labels."""
    request = interpret(published, "R1")
    budget = QueryBudget(600_000)
    corpus = eligible(engine, request, budget.checkpoint)
    require(corpus.complete, corpus.reason or "CAPTURE_INCOMPLETE")
    codec = FeatureEncoder(engine, budget)
    grouped: dict[str, list[Any]] = {}
    for record in corpus.records:
        grouped.setdefault(record.event_id, []).append(record)
    memories = []
    for event_id, records in sorted(grouped.items()):
        feature = views.derive(tuple(records))
        slots = np.zeros((3, 384))
        slots[np.asarray(feature.mask)] = codec.texts(
            tuple(t for t in feature.texts if t is not None)
        )
        single = codec.texts((feature.single_text,))[0]
        full = views.derive(tuple(records), full_fanout=True)
        memories.append(
            {
                "event_id": event_id,
                "source_ids": sorted({mapping[r.atom_id] for r in records}),
                "mask": feature.mask,
                "facets": slots.tolist(),
                "single": single.tolist(),
                "facet_ns": feature.durations_ns,
                "selective_calls": feature.invocations,
                "full_calls": full.invocations,
                "full_facet_ns": full.durations_ns,
            }
        )
    query = codec.texts((published.query.text,), query=True)[0]
    return {
        "input_digest": published.sha256,
        "memories": memories,
        "query": query.tolist(),
        "usage": budget.usage(),
        "snapshot": corpus.snapshot,
        "security_epoch": corpus.security_epoch,
        "truncated": budget.model_truncated,
    }


@dataclass
class BindingAdapter:
    engine: Engine
    published: PublicInput
    mapping: dict[str, str]

    def query(self, variant: str, checkpoint: Path | None = None) -> tuple[Result, dict[str, Any]]:
        published = self.published
        spec = SPECS[variant]
        if not set(published.query.required_capabilities) <= set(spec.capabilities):
            return Result(
                "UNSUPPORTED", None, (), reason="FEATURE_NOT_SUPPORTED", coverage="UNAVAILABLE"
            ), {"early": True}
        if published.query.coverage_state == "UNAVAILABLE":
            return Result(
                "OK",
                "VERIFICATION_UNAVAILABLE",
                (),
                coverage="UNAVAILABLE",
                reason="CAPTURE_VERIFICATION_UNAVAILABLE",
            ), {"early": True}
        request = interpret(published, "R1")
        start = time.perf_counter_ns()
        packet = self.engine.recall_binding(request, variant, checkpoint).serialize()
        elapsed = time.perf_counter_ns() - start
        by_id = {s.source_id: s for s in published.sources}
        evidence = []
        for record in packet["evidence"]:
            source = by_id[self.mapping[record["atom_id"]]]
            require(
                record["text"] == source.text and record["sha256"] == source.sha256,
                "SOURCE_MAPPING_MISMATCH",
            )
            evidence.append(candidate(source))
        ranking = []
        for key in packet.get("binding_ranking", []):
            atom = key.split(":", 1)[0]
            require(atom in self.mapping, "SOURCE_MAPPING_MISSING")
            ranking.append(self.mapping[atom])
        failed = packet["status"] == "VERIFICATION_UNAVAILABLE"
        result = Result(
            "TIMEOUT" if "DEADLINE" in packet["reason"] else "ERROR" if failed else "OK",
            None if failed else packet["status"],
            () if failed else tuple(evidence),
            coverage=packet["coverage"],
            reason=packet["reason"],
            missing_fields=tuple(packet["missing_fields"]),
        )
        return result, {
            "packet": packet,
            "elapsed_ns": elapsed,
            "ranking_sources": list(dict.fromkeys(ranking)),
            "ranking_stage": "BINDING_CANDIDATES",
            "cache": "RESIDENT_ENCODER_AFTER_PROJECT; NO_QUERY_VECTOR_CACHE",
        }
