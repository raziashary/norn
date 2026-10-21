"""Final-evidence ranking, conditional identity and named safety observations."""

import math
from typing import Any

from benchmark.adapters.contracts import ArmSpec, PublicInput, Result
from benchmark.fixtures.scenarios import Gold
from benchmark.metrics.evidence_sets import evidence_scores
from benchmark.metrics.normalize import normalized_sources


def retrieval_scores(
    published: PublicInput, result: Result, spec: ArmSpec, gold: Gold
) -> dict[str, Any]:
    ids = normalized_sources(published, result, spec)
    if result.disposition != "OK":
        return {
            "observed": False,
            "reason": result.disposition,
            "rank_stage": result.stage,
            "retrieval_recall": None,
            "complete_set": None,
            "slot_coverage": None,
            "identity_correct": None,
            "partial_set": None,
        }
    relevant = set().union(*(set(s) for s in (*gold.acceptable_sets, *gold.partial_sets)))
    alternatives = [set(s) for s in (*gold.acceptable_sets, *gold.partial_sets)]
    recall = max((len(set(ids) & a) / len(a) for a in alternatives if a), default=None)
    precision = sum(i in relevant for i in ids) / len(ids) if ids and relevant else None
    rr = next((1 / rank for rank, item in enumerate(ids, 1) if item in relevant), 0.0)
    covered: set[int] = set()
    dcg = 0.0
    for rank, item in enumerate(ids, 1):
        slots = {
            i for i, alternatives_in_slot in enumerate(gold.slots) if item in alternatives_in_slot
        }
        if slots - covered:
            dcg += 1 / math.log2(rank + 1)
            covered.update(slots)
    ideal = sum(
        1 / math.log2(i + 1)
        for i in range(1, min(len(gold.slots), published.query.max_candidates) + 1)
    )
    available = frozenset(s.source_id for s in published.sources)
    scores = evidence_scores(ids, gold, available)
    source_index = {s.source_id: s for s in published.sources}
    events = {source_index[item].event_id for item in ids}
    identity = None
    if gold.expected_status == "SUPPORTED" and gold.relevant_events:
        identity = bool(events) and events <= set(gold.relevant_events)
    return {
        "observed": True,
        "rank_stage": "FINAL_EVIDENCE",
        "canonical_unit": "source",
        "dedup_policy": "FIRST_SOURCE_ID",
        "raw_candidates": len(result.candidates),
        "unique_sources": len(ids),
        "unique_events": len(events),
        "retrieval_recall": recall,
        "retrieval_precision": precision,
        "mrr": rr if relevant else None,
        "ndcg": dcg / ideal if relevant and ideal else None,
        "success": bool(set(ids) & relevant) if relevant else None,
        "identity_correct": identity,
        "wrong_episode": not identity if identity is not None else None,
        **scores,
    }
