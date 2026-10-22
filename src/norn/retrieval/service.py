"""Public recall coordinator: one budget, coherent projections, canonical final rechecks."""

import json
from threading import Event
from typing import TYPE_CHECKING, Any

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical
from norn.embedding.assets import fingerprint
from norn.projection import local
from norn.retrieval import assembly, dense, exact, fusion, lexical
from norn.retrieval.contracts import Hit, RecallRequest
from norn.retrieval.rerank import rerank
from norn.retrieval.resolve import resolve
from norn.telemetry.query import trace
from norn.telemetry.resources import memory

if TYPE_CHECKING:
    from norn.integration.engine import Engine


class UnicodeTokenizer:
    version = "unicode-word-v1"

    def count(self, text: str) -> int:
        return len(lexical.tokenize(text))


class RecallView:
    def __init__(
        self,
        engine: Engine,
        request: RecallRequest,
        hits: tuple[Hit, ...],
        snapshot: int,
        epoch: int,
        data: dict[str, Any],
    ):
        self._engine, self._request, self._hits = engine, request, hits
        self._snapshot, self._epoch, self._payload = snapshot, epoch, canonical(data)

    def serialize(self) -> dict[str, Any]:
        require(self._engine.access.check("READ") == self._epoch, "QUERY_SECURITY_CHANGED")
        for hit in self._hits:
            resolve(self._engine, hit, self._request, self._snapshot, self._epoch)
        require(self._engine.access.check("READ") == self._epoch, "QUERY_SECURITY_CHANGED")
        return json.loads(self._payload)  # type: ignore[no-any-return]


def recall(engine: Engine, request: RecallRequest, *, cancelled: Event | None = None) -> RecallView:
    budget = QueryBudget(request.deadline_ms, cancelled if cancelled is not None else Event())
    try:
        with budget.sqlite_guard(engine.db.connection):
            return _run(engine, request, budget)
    except BaseException:
        engine.close_models()
        raise


def _run(engine: Engine, request: RecallRequest, budget: QueryBudget) -> RecallView:
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
    verified_hits: tuple[Hit, ...] = ()
    data: dict[str, Any] = {
        "status": "VERIFICATION_UNAVAILABLE",
        "reason": "INCOMPLETE_VERIFICATION",
        "evidence": [],
        "missing_fields": [],
        "coverage": "UNAVAILABLE",
    }
    try:
        budget.checkpoint()
        corpus = exact.eligible(engine, request, budget.checkpoint)
        snapshot = corpus.snapshot
        budget.records = len(corpus.records)
        stages["eligible"] = len(corpus.records)
        capabilities = (
            ("lexical",)
            if request.arm == "R0"
            else (("dense",) if request.arm == "R1" else ("lexical", "dense"))
        )
        snapshot_id, index = local.load(engine, corpus, capabilities, budget)
        structured = exact.lookup(corpus, request) if request.arm != "R1" else ()
        stages["exact"] = len(structured)
        lex = (
            lexical.search(
                corpus,
                request.text,
                request.candidate_limit,
                {k: v["terms"] for k, v in index["lexical"].items()},
                budget.checkpoint,
            )
            if request.arm != "R1"
            else ()
        )
        stages["lexical"] = len(lex)
        if request.arm == "R0":
            stages["channel_votes"] = len(structured) + len(lex)
            candidates = fusion.fuse(structured, (lex,), request.candidate_limit)
        else:
            models = engine.local_models
            if models is None:
                raise NornError("LOCAL_MODELS_NOT_ENABLED")
            query = dense.encode((request.text,), models, budget, query=True)[0]
            vectors = {k: tuple(v["vector"]) for k, v in index["dense"].items()}
            nearest = dense.search(
                corpus, query, vectors, request.candidate_limit, budget.checkpoint
            )
            stages["dense"] = len(nearest)
            stages["channel_votes"] = (
                len(nearest) if request.arm == "R1" else len(structured) + len(lex) + len(nearest)
            )
            candidates = (
                nearest
                if request.arm == "R1"
                else fusion.fuse(structured, (lex, nearest), request.candidate_limit)
            )
            stages["after_dedup"] = len(candidates)
            stages["before_rerank"] = len(candidates)
            if request.arm == "R3":
                candidates = rerank(candidates, request.text, models, budget)
        if request.arm == "R0":
            stages["after_dedup"] = len(candidates)
            stages["before_rerank"] = len(candidates)
        stages["after_rerank"] = len(candidates)
        stages["candidates"] = len(candidates)
        data, verified_hits = assemble_hits(
            engine, request, candidates, snapshot, epoch, budget, stages, complete=corpus.complete
        )
        data.update(
            projection_snapshot=snapshot_id,
            model_fingerprints=(
                {}
                if request.arm == "R0"
                else {
                    "encoder": fingerprint("encoder"),
                    **({"reranker": fingerprint("reranker")} if request.arm == "R3" else {}),
                }
            ),
        )
    except NornError as error:
        if error.code in {"NOT_AUTHORIZED_OR_NOT_FOUND", "QUERY_SECURITY_CHANGED"}:
            engine.close_models()
            raise
        engine.close_models()
        data["reason"] = error.code
        data["evidence"] = []
        verified_hits = ()
    data.update(
        {
            "namespace": engine.access.ns,
            "snapshot": snapshot,
            "security_epoch": epoch,
            "evaluation_time": request.clock.evaluation_time.isoformat(),
            "knowledge_at": request.clock.knowledge_at.isoformat(),
            "valid_at": request.clock.valid_at.isoformat(),
            "temporal_basis": request.clock.basis,
            "arm": request.arm,
            "trace": trace(
                engine.access.ns, request.arm, snapshot, stages, budget, str(data["reason"])
            ),
        }
    )
    view = RecallView(engine, request, verified_hits, snapshot, epoch, data)
    view.serialize()
    if data["status"] != "VERIFICATION_UNAVAILABLE":
        budget.checkpoint()
    return view


def assemble_hits(
    engine: Engine,
    request: RecallRequest,
    candidates: tuple[Hit, ...],
    snapshot: int,
    epoch: int,
    budget: QueryBudget,
    stages: dict[str, int],
    *,
    complete: bool,
) -> tuple[dict[str, Any], tuple[Hit, ...]]:
    """One canonical verification/evidence owner for conventional and binding hits."""
    records = []
    for hit in candidates:
        budget.checkpoint()
        records.append(resolve(engine, hit, request, snapshot, epoch))
    stages["resolved"] = len(records)
    tokenizer: assembly.TokenCounter = (
        engine.evidence_tokenizer if engine.evidence_tokenizer is not None else UnicodeTokenizer()
    )
    packet, tokens, _decision = assembly.assemble(
        tuple(records),
        request,
        tokenizer,
        complete=complete,
        checkpoint=budget.checkpoint,
    )
    budget.checkpoint()
    require(bool(packet), "EVIDENCE_HEADER_BUDGET")
    selected = {
        r["atom_id"] + ":" + r["source_version"] + ":" + str(r["start_byte"])
        for r in packet["evidence"]
    }
    verified_hits = tuple(h for h in candidates if h.record.key in selected)
    stages["final_evidence"] = len(verified_hits)
    data = {
        **packet,
        "coverage": "CONSISTENT_READY" if complete else "DEGRADED",
        "evidence_tokens": tokens,
        "authorizes_action": False,
        "tokenizer": tokenizer.version,
        "possibly_truncated_model_input": bool(budget.model_truncated),
        "resource_observation": {
            "parent": memory(),
            "max_worker_peak_bytes": engine.local_models.peak_worker_bytes
            if engine.local_models
            else None,
            "scope": "SEPARATE_PROCESS_PEAKS_NOT_SIMULTANEOUS_TOTAL",
        },
    }
    return data, verified_hits
