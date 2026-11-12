"""Identity ranking metrics: the single owner of episode top-1, margin, ties and collisions.

Used by the P05 separation sweep (T07) and the partial-cue/transfer checks (T08). The P04 readers in
``benchmark/runs/binding_report.py`` keep their own ledger-row fields and are not duplicated here.
A tie at the top is never credited: a code that cannot separate two events has not identified one.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from statistics import mean, median
from typing import Any

import numpy as np

from norn.contracts.errors import require

TIE = 1e-12


def ranking_outcome(scores: Sequence[float], gold: Sequence[bool]) -> dict[str, Any]:
    """Score one query: strict top-1, tie-inclusive top-1 (an upper bound), ties and the margin.

    ``margin`` is the best gold score minus the best non-gold score (None without a non-gold event);
    negative means a wrong event ranks ahead.
    """
    require(len(scores) == len(gold) > 0 and any(gold), "IDENTITY_RANKING_INPUT")
    values = np.asarray(scores, dtype=np.float64)
    require(bool(np.isfinite(values).all()), "IDENTITY_RANKING_INPUT")
    flags = np.asarray(gold, dtype=bool)
    top = float(values.max())
    leaders = values >= top - TIE
    others = values[~flags]
    return {
        "top1_strict": bool(leaders.sum() == 1 and flags[leaders][0]),
        "top1_tie_inclusive": bool(flags[leaders].any()),
        "tied_at_top": bool(leaders.sum() > 1),
        "margin": float(values[flags].max() - others.max()) if others.size else None,
        "pool": int(len(values)),
        "gold": int(flags.sum()),
        "contested": bool(others.size),
    }


def summarize(outcomes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Rates over applicable queries; an empty set reports counts with ``None`` rates."""
    n = len(outcomes)
    contested = [o for o in outcomes if o["contested"]]
    margins = [o["margin"] for o in outcomes if o["margin"] is not None]
    rate: Callable[[str], float | None] = lambda key: (  # noqa: E731
        sum(1 for o in outcomes if o[key]) / n if n else None
    )
    return {
        "queries": n,
        "top1_strict": rate("top1_strict"),
        "top1_tie_inclusive": rate("top1_tie_inclusive"),
        "tied_at_top": rate("tied_at_top"),
        # Queries whose pool holds a non-gold episode: the only ones where ranking can fail.
        "contested": len(contested),
        "top1_strict_contested": (
            sum(1 for o in contested if o["top1_strict"]) / len(contested) if contested else None
        ),
        "margin_defined": len(margins),
        "margin_mean": mean(margins) if margins else None,
        "margin_median": median(margins) if margins else None,
        "wrong_event_ahead": (sum(1 for m in margins if m < 0) / len(margins)) if margins else None,
    }


def stratified(
    rows: Sequence[dict[str, Any]], outcomes: Sequence[dict[str, Any]], key: str
) -> dict[str, dict[str, Any]]:
    """Summaries per value of a row field (for example ``cue_missing_fraction``)."""
    require(len(rows) == len(outcomes), "IDENTITY_STRATA_INPUT")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row, outcome in zip(rows, outcomes, strict=True):
        groups.setdefault(str(row[key]), []).append(outcome)
    return {name: summarize(items) for name, items in sorted(groups.items())}


def collision_pairs(codes: np.ndarray) -> dict[str, Any]:
    """Distinct-event pairs whose codes are identical (exact row equality)."""
    require(codes.ndim == 2, "IDENTITY_COLLISION_INPUT")
    n = len(codes)
    groups = Counter(map(bytes, np.ascontiguousarray(codes).view(np.uint8).reshape(n, -1)))
    colliding = sum(c * (c - 1) // 2 for c in groups.values())
    total = n * (n - 1) // 2
    return {
        "events": n,
        "pairs": total,
        "colliding_pairs": colliding,
        "rate": colliding / total if total else None,
    }


def chance_top1(pools: Sequence[int], golds: Sequence[int]) -> float | None:
    """Expected strict top-1 of a uniformly random ranker: the mean of gold count over pool size."""
    require(len(pools) == len(golds) and all(0 < g <= p for p, g in zip(pools, golds, strict=True)))
    return mean(g / p for p, g in zip(pools, golds, strict=True)) if pools else None
