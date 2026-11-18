"""Relation extraction quality against the hidden gold graph (P06-T02).

Relation precision and recall only; identity precision stays in ``benchmark/metrics/identity.py``.
An edge is the triple (tail key, head key, relation) with both endpoints named by governed keys,
so a derived edge is matched on what it says and never on a hidden id. The cited source is
compared separately: an edge can be right while its citation is not. Denominators are explicit and
an empty one reports ``None`` instead of a favourable zero or one.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from norn.contracts.errors import require

ORACLE_REVISION = "gold-diagnostic-v1"
LIST_LIMIT = 20


@dataclass(frozen=True)
class EdgeObs:
    """An edge observed in a derived graph or stated by the gold graph."""

    tail: str | None  # governed key of the requirer; None when the endpoint carries no key
    head: str | None
    relation: str
    source: str  # published id of the citing source
    revision: str = ""


def _triples(edges: Sequence[EdgeObs]) -> dict[tuple[str | None, str | None, str], set[str]]:
    result: dict[tuple[str | None, str | None, str], set[str]] = {}
    for edge in edges:
        result.setdefault((edge.tail, edge.head, edge.relation), set()).add(edge.source)
    return result


def score_edges(
    derived: Sequence[EdgeObs], gold: Sequence[EdgeObs], *, oracle_track: bool = False
) -> dict[str, Any]:
    """Precision, recall, F1 and the exact misses, with support agreement kept separate.

    A derived track must contain no oracle edge; the labelled oracle diagnostic must contain
    nothing but oracle edges. Either mix is refused, never silently scored.
    """
    if oracle_track:
        require(all(e.revision == ORACLE_REVISION for e in derived), "DIAGNOSTIC_TRACK_MISLABELLED")
    else:
        require(
            all(e.revision != ORACLE_REVISION for e in derived), "ORACLE_EDGES_IN_DERIVED_TRACK"
        )
    found, truth = _triples(derived), _triples(gold)
    # An edge with an unkeyed endpoint cannot be matched to a keyed gold edge: always wrong.
    matched = {t for t in found if t in truth and None not in t[:2]}
    spurious = sorted(str(t) for t in found if t not in matched)
    missed = sorted(str(t) for t in truth if t not in matched)
    cited_right = sum(1 for t in matched if found[t] & truth[t])
    precision = len(matched) / len(found) if found else None
    recall = len(matched) / len(truth) if truth else None
    if precision is None or recall is None:
        f1 = None
    else:
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "derived": len(found),
        "gold": len(truth),
        "true_positive": len(matched),
        "false_positive": len(found) - len(matched),
        "false_negative": len(truth) - len(matched),
        "unkeyed": sum(1 for t in found if None in t[:2]),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "citation_agreement": cited_right / len(matched) if matched else None,
        "citation_denominator": len(matched),
        "spurious": spurious[:LIST_LIMIT],
        "missed": missed[:LIST_LIMIT],
    }


def shuffled_gold(gold: Sequence[EdgeObs], seed: int) -> list[EdgeObs]:
    """A control: the same gold edges with heads permuted, so no edge is expected to match."""
    heads = [g.head for g in gold]
    order = list(range(len(heads)))
    random.Random(seed).shuffle(order)
    return [
        EdgeObs(g.tail, heads[order[i]], g.relation, g.source, g.revision)
        for i, g in enumerate(gold)
    ]


def pool(scores: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Micro-average over many cases: counts add, rates come from the summed counts."""
    tp = sum(s["true_positive"] for s in scores)
    derived = sum(s["derived"] for s in scores)
    gold = sum(s["gold"] for s in scores)
    cited = sum(
        round(s["citation_agreement"] * s["citation_denominator"])
        for s in scores
        if s["citation_agreement"] is not None
    )
    matched = sum(s["citation_denominator"] for s in scores)
    precision = tp / derived if derived else None
    recall = tp / gold if gold else None
    return {
        "cases": len(scores),
        "derived": derived,
        "gold": gold,
        "true_positive": tp,
        "false_positive": derived - tp,
        "false_negative": gold - tp,
        "unkeyed": sum(s["unkeyed"] for s in scores),
        "precision": precision,
        "recall": recall,
        "citation_agreement": cited / matched if matched else None,
        "citation_denominator": matched,
    }
