"""Opt-in binding retrieval through the existing eligibility and final evidence owners."""

from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.embedding import checkpoint, denoising, late_fusion
from norn.embedding.assets import fingerprint
from norn.embedding.binding import LEARNED, VARIANTS
from norn.embedding.feature_encoder import FeatureEncoder
from norn.embedding.numerics import array
from norn.projection import binding as projection
from norn.retrieval import exact
from norn.retrieval.contracts import Hit, RecallRequest, Record
from norn.retrieval.service import RecallView, assemble_hits
from norn.telemetry.query import trace

if TYPE_CHECKING:
    from norn.integration.engine import Engine


def expand_ranked_events(
    records: tuple[Record, ...], scores: dict[str, float], variant: str, limit: int
) -> tuple[Hit, ...]:
    """Rank memories (events) first, keep ``limit`` of them, then expand to their atoms.

    The candidate limit counts events: one event with many atoms cannot fill the list and push
    every other event out. Atoms of an event keep key order; later stages bound the evidence.
    """
    by_event: dict[str, list[Record]] = {}
    for record in records:
        by_event.setdefault(record.event_id, []).append(record)
    order = sorted(
        by_event, key=lambda event: (-scores[event], min(r.key for r in by_event[event]))
    )
    return tuple(
        Hit(record, scores[event], variant)
        for event in order[:limit]
        for record in sorted(by_event[event], key=lambda r: r.key)
    )


def recall(
    engine: Engine,
    request: RecallRequest,
    variant: str,
    checkpoint_path: Path | None = None,
    *,
    cancelled: Event | None = None,
) -> RecallView:
    if variant == "B5":
        denoising.encode()
    require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
    budget = QueryBudget(request.deadline_ms, cancelled if cancelled is not None else Event())
    epoch = engine.access.check("READ")
    snapshot = (
        request.clock.snapshot
        if request.clock.snapshot is not None
        else int(
            engine.db.connection.execute(
                "SELECT commit_seq FROM namespaces WHERE ns=?", (engine.access.ns,)
            ).fetchone()[0]
        )
    )
    stages: dict[str, int] = {}
    verified: tuple[Hit, ...] = ()
    data: dict[str, Any] = {
        "status": "VERIFICATION_UNAVAILABLE",
        "reason": "INCOMPLETE_VERIFICATION",
        "evidence": [],
        "missing_fields": [],
        "coverage": "UNAVAILABLE",
    }
    try:
        with budget.sqlite_guard(engine.db.connection):
            corpus = exact.eligible(engine, request, budget.checkpoint)
            snapshot = corpus.snapshot
            stages["eligible"] = budget.records = len(corpus.records)
            require(len(corpus.records) <= 4096, "BINDING_CORPUS_BUDGET")
            ck = checkpoint.load(checkpoint_path) if checkpoint_path is not None else None
            require((variant in LEARNED) == (ck is not None), "BINDING_CHECKPOINT_REQUIRED")
            require(ck is None or ck.model.variant == variant, "CHECKPOINT_VARIANT_MISMATCH")
            checkpoint_digest = ck.sha256 if ck else "NONE"
            identity, payloads = projection.load(engine, corpus, variant, checkpoint_digest, budget)
            codec = FeatureEncoder(engine, budget)
            q = codec.query(request.text, variant, ck.model if ck else None)
            events = {r.event_id: payloads[r.key] for r in corpus.records}
            event_keys = tuple(sorted(events))
            scores: dict[str, float] = {}
            if event_keys:
                vectors = array([events[k]["vector"] for k in event_keys], (len(event_keys), 384))
                if variant == "B1":
                    masks = array([events[k]["mask"] for k in event_keys], (len(event_keys), 3))
                    values = late_fusion.scores(
                        q.reshape(3, 128),
                        vectors.reshape(-1, 3, 128),
                        masks,
                        event_keys,
                        request.candidate_limit,
                    )
                else:
                    values = vectors @ q
                scores = {key: float(v) for key, v in zip(event_keys, values, strict=True)}
            ranked = expand_ranked_events(corpus.records, scores, variant, request.candidate_limit)
            stages.update(binding_events=len(event_keys), candidates=len(ranked))
            data, verified = assemble_hits(
                engine, request, ranked, snapshot, epoch, budget, stages, complete=corpus.complete
            )
            data.update(
                projection_snapshot=identity,
                binding_checkpoint=checkpoint_digest,
                model_fingerprints={"encoder": fingerprint("encoder")},
                # Candidates before sufficiency and the final evidence limit: not the evidence.
                binding_ranking_stage="CANDIDATES_BEFORE_SUFFICIENCY_AND_FINAL_LIMIT",
                binding_ranked_events=len(event_keys),
                binding_ranking=[h.record.key for h in ranked],
                binding_scores=[h.score for h in ranked],
            )
    except NornError as error:
        engine.close_models()
        if error.code in {"NOT_AUTHORIZED_OR_NOT_FOUND", "QUERY_SECURITY_CHANGED"}:
            raise
        data.update(reason=error.code, evidence=[])
        verified = ()
    except BaseException:
        engine.close_models()
        raise
    data.update(
        namespace=engine.access.ns,
        snapshot=snapshot,
        security_epoch=epoch,
        evaluation_time=request.clock.evaluation_time.isoformat(),
        knowledge_at=request.clock.knowledge_at.isoformat(),
        valid_at=request.clock.valid_at.isoformat(),
        temporal_basis=request.clock.basis,
        arm=variant,
        trace=trace(engine.access.ns, variant, snapshot, stages, budget, str(data["reason"])),
    )
    view = RecallView(engine, request, verified, snapshot, epoch, data)
    view.serialize()
    if data["status"] != "VERIFICATION_UNAVAILABLE":
        budget.checkpoint()
    return view
