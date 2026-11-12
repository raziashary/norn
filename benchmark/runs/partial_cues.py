"""P05-T08 development check of ambiguity, over-separation and transfer for the T0-T7 codes.

Offline and credential-free, on the same digest-verified tune-role captures and frozen checkpoints
as the T07 sweep, but over *every* tune query so that insufficient-cue queries (ambiguous or
missing cue, where no single episode is the answer) can be compared with sufficient ones. The
evaluation role is never opened. Owner answer ADR-0027 Q-B bounds the claims: this card reports
same-target rewording and unseen-identity transfer only; the rewordings differ in language
(en/id/mixed) and carry no separate paraphrase label, so no language-transfer claim is made.

Everything is descriptive: no margin was approved for T08, nothing is selected and no verdict label
is produced. Benefit (strict episode top-1, set recall) and harm (cross-pool top-1, ambiguity
separation, per-cluster losses against T0) are reported side by side.
"""

import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from benchmark.fixtures.binding_cases import ROLE_INDICES
from benchmark.metrics import identity
from benchmark.runs.manifest import code_digest, write_once
from benchmark.runs.separation import CONFIG as SWEEP_CONFIG
from benchmark.runs.separation import (
    Inputs,
    Query,
    _episode_scores,
    _members,
    load_inputs,
    source_codes,
)
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.embedding import separation

SCOPES = ("eligible", "pooled")
INSUFFICIENT_VARIANTS = ("ambiguous", "missing", "action-ambiguous")
CONFIGS = (("weighted", 100), ("weighted", 10))
CONFIG: dict[str, Any] = {
    "revision": "partial-cues-v1",
    "status": "DEVELOPMENT_DESCRIPTIVE_NO_THRESHOLD_NO_VERDICT",
    "role": SWEEP_CONFIG["role"],
    "sources": SWEEP_CONFIG["sources"],
    "codes": [
        {"mode": mode, "percent": percent, "geometry": "native"} for mode, percent in CONFIGS
    ],
    "scopes": list(SCOPES),
    "classes": {
        "sufficient": "identity-applicable queries (SUPPORTED with relevant events)",
        "insufficient": "queries with no relevant event and variant in "
        + str(list(INSUFFICIENT_VARIANTS)),
        "other": "PARTIALLY_SUPPORTED/action queries without relevant events are not scored here",
    },
    "metrics": {
        "identity": "strict episode top-1 over sufficient queries, overall and by cue stratum",
        "set_recall": "every gold episode strictly above every non-gold one (sufficient queries "
        "with at least one non-gold episode; applicable counts reported)",
        "ambiguity_gap": "AUROC of the top-1 minus top-2 episode gap, sufficient versus "
        "insufficient queries with two or more candidates; 0.5 means the gap cannot separate "
        "them",
        "rewording_consistency": "same-target query groups (identical relevant episodes, 2+ "
        "queries): share of groups where every query is strict top-1 correct",
        "per_cluster_harm": "clusters where an arm's strict top-1 is below / equal to / above T0",
    },
    "unseen_identity": "entity-disjoint roles by construction (binding_cases.ROLE_INDICES)",
}


def _klass(query: Query) -> str:
    if query.relevant:
        return "sufficient"
    return "insufficient" if query.variant in INSUFFICIENT_VARIANTS else "other"


def evaluate_scores(inputs: Inputs, scores: Any) -> dict[str, Any]:
    """Every T08 metric for one (n_queries, n_events) score matrix, per scope."""
    result: dict[str, Any] = {}
    for scope in SCOPES:
        outcomes: list[dict[str, Any]] = []
        sufficient: list[Query] = []
        set_hits: list[bool] = []
        gaps: dict[str, list[float]] = {"sufficient": [], "insufficient": []}
        groups: dict[frozenset[str], list[bool]] = defaultdict(list)
        by_cluster: dict[str, list[bool]] = defaultdict(list)
        for i, query in enumerate(inputs.queries):
            klass = _klass(query)
            if klass == "other":
                continue
            best = _episode_scores(inputs, scores[i], _members(inputs, query, scope))
            if not best:
                continue
            gap = identity.top_gap(list(best.values()))
            if gap is not None:
                gaps[klass].append(gap)
            if klass != "sufficient":
                continue
            flags = [e in query.relevant for e in best]
            outcome = identity.ranking_outcome(list(best.values()), flags)
            outcomes.append(outcome)
            sufficient.append(query)
            recall = identity.set_recall(list(best.values()), flags)
            if recall is not None:
                set_hits.append(recall)
            groups[query.relevant].append(outcome["top1_strict"])
            by_cluster[query.cluster].append(outcome["top1_strict"])
        sufficient_rows = [{"stratum": _stratum(q)} for q in sufficient]
        result[scope] = {
            "identity": identity.summarize(outcomes),
            "identity_strata": identity.stratified(sufficient_rows, outcomes, "stratum"),
            "set_recall": {
                "applicable": len(set_hits),
                "rate": sum(set_hits) / len(set_hits) if set_hits else None,
            },
            "ambiguity_gap": {
                "sufficient_n": len(gaps["sufficient"]),
                "insufficient_n": len(gaps["insufficient"]),
                "auroc": identity.auroc(gaps["sufficient"], gaps["insufficient"]),
                "sufficient_median": median(gaps["sufficient"]) if gaps["sufficient"] else None,
                "insufficient_median": median(gaps["insufficient"])
                if gaps["insufficient"]
                else None,
            },
            "rewording_consistency": identity.all_correct_rate(list(groups.values())),
            "per_cluster_top1": {c: mean(map(float, v)) for c, v in sorted(by_cluster.items())},
        }
    return result


def _stratum(query: Query) -> str:
    return "COMPLETE_CUE" if query.missing_fraction == 0 else "PARTIAL_CUE"


def unseen_identity() -> dict[str, Any]:
    train, tune = set(ROLE_INDICES["train"]), set(ROLE_INDICES["tune"])
    return {
        "train_entity_indices": sorted(train),
        "tune_entity_indices": sorted(tune),
        "disjoint": not (train & tune),
    }


def _leaf(cell: dict[str, Any], path: tuple[str, ...]) -> float | None:
    node: Any = cell
    for key in path:
        node = node[key]
    return None if node is None else float(node)


def _delta(arm: dict[str, Any], base: dict[str, Any], scope: str) -> dict[str, Any]:
    """Arm minus T0 for one scope: the separation benefit and the generalization harm together."""

    def diff(*path: str) -> float | None:
        a, b = _leaf(arm[scope], path), _leaf(base[scope], path)
        return None if a is None or b is None else a - b

    mine, theirs = arm[scope]["per_cluster_top1"], base[scope]["per_cluster_top1"]
    return {
        "top1_strict": diff("identity", "top1_strict"),
        "top1_strict_contested": diff("identity", "top1_strict_contested"),
        "set_recall": diff("set_recall", "rate"),
        "gap_auroc": diff("ambiguity_gap", "auroc"),
        "rewording_all_correct": diff("rewording_consistency", "all_correct"),
        "clusters_worse": sum(1 for c in mine if mine[c] < theirs[c] - 1e-12),
        "clusters_equal": sum(1 for c in mine if abs(mine[c] - theirs[c]) <= 1e-12),
        "clusters_better": sum(1 for c in mine if mine[c] > theirs[c] + 1e-12),
    }


def _mean_cell(cells: list[dict[str, Any]], scope: str) -> dict[str, Any]:
    """Average the per-seed results of one arm (numeric leaves only; counts come from seed 1)."""

    def avg(path: tuple[str, ...]) -> float | None:
        values = []
        for cell in cells:
            node: Any = cell[scope]
            for key in path:
                node = node[key]
            if node is not None:
                values.append(node)
        return mean(values) if values else None

    clusters = sorted(cells[0][scope]["per_cluster_top1"])
    first = cells[0][scope]
    return {
        "identity": {
            "queries": first["identity"]["queries"],
            "contested": first["identity"]["contested"],
            "top1_strict": avg(("identity", "top1_strict")),
            "top1_strict_contested": avg(("identity", "top1_strict_contested")),
        },
        "set_recall": {
            "applicable": first["set_recall"]["applicable"],
            "rate": avg(("set_recall", "rate")),
        },
        "ambiguity_gap": {
            "sufficient_n": first["ambiguity_gap"]["sufficient_n"],
            "insufficient_n": first["ambiguity_gap"]["insufficient_n"],
            "auroc": avg(("ambiguity_gap", "auroc")),
            "sufficient_median": avg(("ambiguity_gap", "sufficient_median")),
            "insufficient_median": avg(("ambiguity_gap", "insufficient_median")),
        },
        "rewording_consistency": {
            "groups": first["rewording_consistency"]["groups"],
            "all_correct": avg(("rewording_consistency", "all_correct")),
        },
        "per_cluster_top1": {
            c: mean(cell[scope]["per_cluster_top1"][c] for cell in cells) for c in clusters
        },
    }


def run(root: Path, output: Path, *, wall_cap_seconds: float) -> dict[str, Any]:
    require(0 < wall_cap_seconds <= 3600, "PARTIAL_CUES_WALL_CAP")
    require(not output.exists(), "PARTIAL_CUES_OUTPUT_EXISTS")
    started = time.monotonic()
    inputs = load_inputs(root, applicable_only=False)
    classes: dict[str, int] = defaultdict(int)
    for query in inputs.queries:
        classes[_klass(query)] += 1
    cells: list[dict[str, Any]] = []
    for name in CONFIG["sources"]:
        q_dense, e_dense = source_codes(inputs, name)
        for mode, percent in CONFIGS:
            require(
                time.monotonic() - started <= wall_cap_seconds, "PARTIAL_CUES_WALL_CAP_EXCEEDED"
            )
            k = separation.sparse_width(percent)
            scores = separation.sparsify(q_dense, k, mode) @ separation.sparsify(e_dense, k, mode).T
            arm, _, seed = name.partition("-")
            cells.append(
                {
                    "source": name,
                    "arm": arm,
                    "seed": int(seed) if seed else None,
                    "mode": mode,
                    "percent": percent,
                    **evaluate_scores(inputs, scores),
                }
            )
    arms: dict[str, dict[str, Any]] = {}
    for mode, percent in CONFIGS:
        for arm in sorted({c["arm"] for c in cells}):
            mine = [
                c for c in cells if c["arm"] == arm and (c["mode"], c["percent"]) == (mode, percent)
            ]
            arms[f"{arm}/{mode}-{percent}"] = {scope: _mean_cell(mine, scope) for scope in SCOPES}
    comparison = {
        key: {scope: _delta(value, arms[f"T0/{key.split('/')[1]}"], scope) for scope in SCOPES}
        for key, value in arms.items()
        if not key.startswith("T0/")
    }
    value = {
        "schema": 1,
        "kind": "P05_PARTIAL_CUES",
        "labels": "CONSTRUCTED_UNAUDITED",
        "status": CONFIG["status"],
        "config": json.loads(canonical(CONFIG)),
        "config_digest": digest(canonical(CONFIG).encode()),
        "code_digest": code_digest(),
        "classes": dict(classes),
        "clusters": len({q.cluster for q in inputs.queries}),
        "heldout_manifest_digest": inputs.manifest_digest,
        "checkpoint_digests": inputs.checkpoint_digests,
        "unseen_identity": unseen_identity(),
        "wall_cap_seconds": wall_cap_seconds,
        "elapsed_seconds": time.monotonic() - started,
        "cells": cells,
        "arms": arms,
        "arm_minus_t0": comparison,
    }
    return {
        "report_digest": write_once(output, value),
        "cells": len(cells),
        "classes": dict(classes),
    }
