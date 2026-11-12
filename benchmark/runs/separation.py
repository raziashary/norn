"""P05-T07 development sweep of dense, sparse, rotated, matched-dense and fused 384-d codes.

Offline and credential-free: it reads only the tune-role captures, public sources, evaluator labels
and the 21 frozen T1-T7 checkpoints of a held-out run, every one verified against that run's
manifest digests. The evaluation role is never opened. Two scopes are reported for every cell:

- ``eligible``: the events the engine's scope and time filters left for that query (the pool in its
  capture), the same candidates the real reader ranks.
- ``pooled``: every captured tune-role event ranked for every query, a geometry stress that ignores
  per-query eligibility and is not a retrieval claim.

An event is one captured memory. The same public episode is captured many times, often with
identical and sometimes slightly different features, so identity is scored per episode: an
episode's score is its best event score, a tie counts only between distinct episodes, and the
episode id decides which are gold. (A first run scored events and let copies of one episode tie
with themselves; it is kept as a superseded record.)

Every cell is reported; nothing is selected and no threshold applies (R09 left T07 margins
unapproved, so the sweep is descriptive).
"""

import json
import time
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, cast

import numpy as np

from benchmark.metrics import identity
from benchmark.runs.loss_heldout import TRAINED, checkpoint_name
from benchmark.runs.manifest import code_digest, file_digest, load, write_once
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.embedding import checkpoint, separation
from norn.embedding.numerics import Array, array

ROLE = "tune"
SEEDS = (11, 29, 47)
FUSION_WEIGHTS = (0.25, 0.5, 0.75)
SCOPES = ("eligible", "pooled")
CONFIG: dict[str, Any] = {
    "revision": "separation-sweep-v3-episode-level-hubness",
    "status": "DEVELOPMENT_DESCRIPTIVE_NO_THRESHOLD_NO_SELECTION",
    "role": ROLE,
    "dimension": separation.DIMENSION,
    "sparsity_percent": list(separation.SPARSITY_PERCENT),
    "modes": list(separation.MODES),
    "geometries": ["native"] + [f"rotated-{s}" for s in SEEDS],
    "matched_dense_seeds": list(SEEDS),
    "fusion_weights": list(FUSION_WEIGHTS),
    "sources": ["T0"] + [f"{arm}-{seed}" for arm in TRAINED for seed in SEEDS],
    "scopes": list(SCOPES),
    "exhaustive_control": "native weighted 100 percent: exact dense cosine over the whole pool",
    "bytes": "dense float32 4 per coordinate; weighted 2-byte index + float16 value; binary index",
    "shuffled_control": {"seeds": list(SEEDS), "cell": "T0 native weighted 100 percent, pooled"},
}


@dataclass(frozen=True)
class Query:
    query_id: str
    stratum: str
    family: str
    cluster: str
    vector: Array
    pool: tuple[int, ...]
    relevant: frozenset[str]
    status: str = "SUPPORTED"
    variant: str = "positive"
    language: str = "en"
    missing_fraction: float = 0.0


@dataclass(frozen=True)
class Inputs:
    queries: tuple[Query, ...]
    events: tuple[str, ...]
    episodes: tuple[str, ...]  # parallel to events: the public episode each event renders
    single: Array
    facets: Array
    mask: Array
    manifest_digest: str
    models: dict[str, Any]
    checkpoint_digests: dict[str, str]


def _verified(root: Path) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    require(manifest.get("kind") == "P05_LOSS_HELDOUT", "SEPARATION_RUN_KIND")
    prefixes = tuple(f"{folder}/{ROLE}/" for folder in ("captures", "evaluator", "published"))
    names = [n for n in manifest["artifacts"] if n.startswith(prefixes)]
    require(
        {n.split("/")[0] for n in names} == {"captures", "evaluator", "published"},
        "SEPARATION_TUNE_ARTIFACTS_MISSING",
    )
    for name in names:
        require(not Path(name).anchor and ".." not in Path(name).parts, "UNSAFE_ARTIFACT_PATH")
        require(
            file_digest(root / name) == manifest["artifacts"][name], "SEPARATION_ARTIFACT_CHANGED"
        )
    return cast(dict[str, Any], manifest)


def load_inputs(root: Path, *, applicable_only: bool = True) -> Inputs:
    """Read only the digest-verified tune-role artifacts and the 21 trained checkpoints.

    ``applicable_only`` keeps the identity-applicable queries (the T07 sweep); T08 asks for every
    tune query so that insufficient-cue queries can be compared with sufficient ones.

    An *event* is one captured memory: the same public episode is rendered with slightly different
    features in different captures (different stores), so events are keyed per capture and the
    public episode id decides which events are gold for a query.
    """
    manifest = _verified(root)
    events: list[str] = []
    episodes: list[str] = []
    rows: list[tuple[Array, Array, Array]] = []
    queries: list[Query] = []
    for capture_path in sorted((root / "captures" / ROLE).glob("query_*.json")):
        capture = load(capture_path)
        label = load(root / "evaluator" / ROLE / capture_path.name)
        public = load(root / "published" / ROLE / capture_path.name)
        source_event = {s["source_id"]: s["event_id"] for s in public["sources"]}
        pool: list[int] = []
        for number, memory in enumerate(capture["memories"]):
            found = {source_event[s] for s in memory["source_ids"]}
            require(len(found) == 1, "SEPARATION_MEMORY_EVENT")
            pool.append(len(events))
            events.append(f"{capture_path.stem}#{number}")
            episodes.append(next(iter(found)))
            rows.append(
                (
                    array(memory["single"], (384,)),
                    array(memory["facets"], (3, 384)),
                    array(memory["mask"], (3,)),
                )
            )
        applicable = label["expected_status"] == "SUPPORTED" and bool(label["relevant_events"])
        if applicable_only and not applicable:
            continue
        relevant = frozenset(label["relevant_events"]) if applicable else frozenset()
        require(
            not applicable or any(episodes[i] in relevant for i in pool),
            "SEPARATION_GOLD_NOT_IN_POOL",
        )
        queries.append(
            Query(
                label["query_id"],
                "COMPLETE_CUE" if label["cue_missing_fraction"] == 0 else "PARTIAL_CUE",
                label["family"],
                label["cluster"],
                array(capture["query"], (384,)),
                tuple(pool),
                relevant,
                label["expected_status"],
                label["variant"],
                label["language"],
                label["cue_missing_fraction"],
            )
        )
    require(bool(queries) and bool(events), "SEPARATION_NO_QUERIES")
    models, digests = {}, {}
    for key, sha in manifest["checkpoints"].items():
        arm, seed = key.split("/")
        path = root / checkpoint_name(arm, int(seed))
        require(file_digest(path) == sha, "CHECKPOINT_CHANGED")
        models[f"{arm}-{seed}"] = checkpoint.load(path).model
        digests[f"{arm}-{seed}"] = sha
    require(set(models) == set(CONFIG["sources"]) - {"T0"}, "SEPARATION_CHECKPOINTS")
    return Inputs(
        tuple(queries),
        tuple(events),
        tuple(episodes),
        np.stack([r[0] for r in rows]),
        np.stack([r[1] for r in rows]),
        np.stack([r[2] for r in rows]),
        file_digest(root / "manifest.json"),
        models,
        digests,
    )


def source_codes(inputs: Inputs, name: str) -> tuple[Array, Array]:
    """Query and event codes (384 coordinates each) for T0 or one trained checkpoint."""
    queries = np.stack([q.vector for q in inputs.queries])
    if name == "T0":
        return queries, inputs.single
    model = inputs.models[name]
    return model.forward(queries, query=True)[0], model.forward(inputs.facets, inputs.mask)[0]


def _episode_scores(inputs: Inputs, row: Array, members: Sequence[int]) -> dict[str, float]:
    """Best event score per public episode: copies of one episode must not tie with themselves."""
    best: dict[str, float] = {}
    for j in members:
        episode = inputs.episodes[j]
        best[episode] = max(best.get(episode, float("-inf")), float(row[j]))
    return best


def _members(inputs: Inputs, query: Query, scope: str) -> Sequence[int]:
    return query.pool if scope == "eligible" else range(len(inputs.events))


def _outcomes(
    inputs: Inputs, scores: Array, scope: str, labels: dict[str, frozenset[str]] | None = None
) -> list[dict[str, Any]]:
    outcomes = []
    for i, query in enumerate(inputs.queries):
        best = _episode_scores(inputs, scores[i], _members(inputs, query, scope))
        gold = labels[query.query_id] if labels is not None else query.relevant
        outcomes.append(identity.ranking_outcome(list(best.values()), [e in gold for e in best]))
    return outcomes


def _episode_top(inputs: Inputs, row: Array) -> str | None:
    """The single best pooled episode, or None when two distinct episodes tie at the top."""
    best = _episode_scores(inputs, row, range(len(inputs.events)))
    top = max(best.values())
    leaders = [e for e, v in best.items() if v >= top - identity.TIE]
    return leaders[0] if len(leaders) == 1 else None


def _scope_result(
    inputs: Inputs, scores: Array, scope: str, dense_top: list[str | None] | None
) -> dict[str, Any]:
    outcomes = _outcomes(inputs, scores, scope)
    result: dict[str, Any] = {
        "overall": identity.summarize(outcomes),
        "strata": identity.stratified(
            [{"stratum": q.stratum} for q in inputs.queries], outcomes, "stratum"
        ),
        "chance_top1": identity.chance_top1(
            [o["pool"] for o in outcomes], [o["gold"] for o in outcomes]
        ),
    }
    if scope == "pooled":
        top = [_episode_top(inputs, scores[i]) for i in range(len(inputs.queries))]
        named = Counter(t for t in top if t is not None)
        # Hubness: how many different episodes ever lead, and the share one episode leads.
        result["distinct_top_episodes"] = len(named)
        result["hub_share"] = max(named.values()) / len(top) if named else 0.0
        if dense_top is not None:
            result["agreement_with_dense"] = sum(
                1 for a, b in zip(top, dense_top, strict=True) if a is not None and a == b
            ) / len(top)
    return result


def _cell(
    inputs: Inputs,
    qs: Array,
    es: Array,
    dense_top: list[str | None] | None,
    meta: dict[str, Any],
    index_seconds: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    scores = qs @ es.T
    query_seconds = time.perf_counter() - started
    cell = dict(meta)
    cell["index_bytes_pooled"] = meta["bytes_per_event"] * len(inputs.events)
    cell["index_ms_pooled"] = index_seconds * 1000
    cell["query_ms_pooled_all"] = query_seconds * 1000
    # Collisions are between distinct episodes: one representative event per episode.
    first = list({e: i for i, e in reversed(list(enumerate(inputs.episodes)))}.values())
    cell["collisions_pooled"] = identity.collision_pairs(es[sorted(first)])
    for scope in SCOPES:
        cell[scope] = _scope_result(inputs, scores, scope, dense_top)
    return cell


def sweep(inputs: Inputs, *, wall_cap_seconds: float) -> list[dict[str, Any]]:
    started = time.monotonic()
    cells: list[dict[str, Any]] = []

    def check() -> None:
        require(time.monotonic() - started <= wall_cap_seconds, "SEPARATION_WALL_CAP_EXCEEDED")

    bases = {s: separation.orthogonal_basis(s) for s in SEEDS}
    for name in CONFIG["sources"]:
        q_dense, e_dense = source_codes(inputs, name)
        dense_scores = q_dense @ e_dense.T
        dense_top = [_episode_top(inputs, dense_scores[i]) for i in range(len(inputs.queries))]
        for geometry in CONFIG["geometries"]:
            basis = None if geometry == "native" else bases[int(geometry.split("-")[1])]
            q_geo = q_dense if basis is None else q_dense @ basis
            e_geo = e_dense if basis is None else e_dense @ basis
            for mode in separation.MODES:
                for percent in separation.SPARSITY_PERCENT:
                    check()
                    k = separation.sparse_width(percent)
                    t0 = time.perf_counter()
                    es = separation.sparsify(e_geo, k, mode)
                    seconds = time.perf_counter() - t0
                    qs = separation.sparsify(q_geo, k, mode)
                    meta = {
                        "family": "sparse",
                        "source": name,
                        "geometry": geometry,
                        "mode": mode,
                        "percent": percent,
                        "k": k,
                        "bytes_per_event": separation.event_bytes(mode, k),
                    }
                    cells.append(_cell(inputs, qs, es, dense_top, meta, seconds))
        for mode in separation.MODES:
            for percent in separation.SPARSITY_PERCENT:
                k = separation.sparse_width(percent)
                budget = separation.event_bytes(mode, k)
                width = separation.matched_width(budget)
                for seed in SEEDS:
                    check()
                    matrix = separation.gaussian_projection(seed, width)
                    t0 = time.perf_counter()
                    es = separation.project(e_dense, matrix, unit=True)
                    seconds = time.perf_counter() - t0
                    qs = separation.project(q_dense, matrix, unit=True)
                    meta = {
                        "family": "matched_dense",
                        "source": name,
                        "geometry": f"gaussian-{seed}",
                        "mode": mode,
                        "percent": percent,
                        "k": width,
                        "bytes_per_event": separation.event_bytes("dense", width),
                        "matched_to_bytes": budget,
                    }
                    cells.append(_cell(inputs, qs, es, dense_top, meta, seconds))
        if name == "T0":
            continue
        q_zero, e_zero = source_codes(inputs, "T0")
        for percent in separation.SPARSITY_PERCENT:
            k = separation.sparse_width(percent)
            sem_s = (
                separation.sparsify(q_zero, k, "weighted")
                @ separation.sparsify(e_zero, k, "weighted").T
            )
            lrn_s = (
                separation.sparsify(q_dense, k, "weighted")
                @ separation.sparsify(e_dense, k, "weighted").T
            )
            for weight in FUSION_WEIGHTS:
                check()
                fused = separation.fuse(sem_s, lrn_s, weight)
                cell = {
                    "family": "fusion",
                    "source": name,
                    "geometry": "native",
                    "mode": "weighted",
                    "percent": percent,
                    "k": k,
                    "weight": weight,
                    "bytes_per_event": 2 * separation.event_bytes("weighted", k),
                }
                cell["index_bytes_pooled"] = cell["bytes_per_event"] * len(inputs.events)
                cell["collisions_pooled"] = None
                for scope in SCOPES:
                    cell[scope] = _scope_result(inputs, fused, scope, None)
                cells.append(cell)
    # Shuffled-label control: gold events reassigned at random among the pooled events.
    q_zero, e_zero = source_codes(inputs, "T0")
    full = q_zero @ e_zero.T
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        real = _outcomes(inputs, full, "pooled")
        episodes = sorted(set(inputs.episodes))
        labels = {
            q.query_id: frozenset(rng.choice(episodes, size=o["gold"], replace=False).tolist())
            for q, o in zip(inputs.queries, real, strict=True)
        }
        outcomes = _outcomes(inputs, full, "pooled", labels)
        cells.append(
            {
                "family": "shuffled_gold_control",
                "source": "T0",
                "seed": seed,
                "pooled": {"overall": identity.summarize(outcomes)},
            }
        )
    return cells


def summarize_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (family, arm, geometry, mode, percent, weight, scope) with the seed spread."""
    groups: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for cell in cells:
        if cell["family"] == "shuffled_gold_control":
            continue
        arm = cell["source"].split("-")[0]
        kind = cell["geometry"].split("-")[0]
        for scope in SCOPES:
            rate = cell[scope]["overall"]["top1_strict"]
            groups[
                (
                    cell["family"],
                    arm,
                    kind,
                    cell["mode"],
                    cell["percent"],
                    cell.get("weight"),
                    scope,
                )
            ].append(rate)
    return [
        {
            "family": k[0],
            "arm": k[1],
            "geometry_kind": k[2],
            "mode": k[3],
            "percent": k[4],
            "weight": k[5],
            "scope": k[6],
            "runs": len(v),
            "top1_strict_mean": mean(v),
            "top1_strict_min": min(v),
            "top1_strict_max": max(v),
        }
        for k, v in sorted(
            groups.items(), key=lambda item: (*item[0][:5], item[0][5] or 0.0, item[0][6])
        )
    ]


def run(root: Path, output: Path, *, wall_cap_seconds: float) -> dict[str, Any]:
    require(0 < wall_cap_seconds <= 3600, "SEPARATION_WALL_CAP")
    require(not output.exists(), "SEPARATION_OUTPUT_EXISTS")
    started = time.monotonic()
    inputs = load_inputs(root)
    cells = sweep(inputs, wall_cap_seconds=wall_cap_seconds)
    scopes = {
        "applicable_queries": len(inputs.queries),
        "pooled_events": len(inputs.events),
        "distinct_episodes": len(set(inputs.episodes)),
        "eligible_pool_sizes": sorted({len(q.pool) for q in inputs.queries}),
        "eligible_pool_histogram": dict(Counter(len(q.pool) for q in inputs.queries)),
        "partial_cue_queries": sum(q.stratum == "PARTIAL_CUE" for q in inputs.queries),
        "clusters": len({q.cluster for q in inputs.queries}),
    }
    value = {
        "schema": 1,
        "kind": "P05_SEPARATION_SWEEP",
        "labels": "CONSTRUCTED_UNAUDITED",
        "status": CONFIG["status"],
        "config": json.loads(canonical(CONFIG)),
        "config_digest": digest(canonical(CONFIG).encode()),
        "code_digest": code_digest(),
        "heldout_manifest_digest": inputs.manifest_digest,
        "checkpoint_digests": inputs.checkpoint_digests,
        "scopes": scopes,
        "wall_cap_seconds": wall_cap_seconds,
        "elapsed_seconds": time.monotonic() - started,
        "cells": cells,
        "summary": summarize_cells(cells),
    }
    return {"report_digest": write_once(output, value), "cells": len(cells), **scopes}
