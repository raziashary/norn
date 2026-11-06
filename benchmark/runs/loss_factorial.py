"""P05 loss factorial: matched T0-T7 training on the frozen E5 substrate (train role only).

Held-out roles are never read here. Train-fit diagnostics show whether each objective does what
it claims on its own training data; they are not generalisation evidence and never select an arm.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from benchmark.adapters.baseline import host
from benchmark.adapters.common import replay_clock
from benchmark.adapters.contracts import PublicInput
from benchmark.adapters.r7 import SPECS, BindingAdapter, capture, ingest
from benchmark.fixtures.binding_cases import cases
from benchmark.fixtures.publication import check_import_barrier, validate_public
from benchmark.fixtures.training_pairs import (
    ONE_FIELD_NAMES,
    PAIRS_VERSION,
    TrainingPair,
    TrainingPairs,
    _content,
    build_pairs,
    dumps,
    labels,
    loads,
)
from benchmark.runs.binding import environment
from benchmark.runs.manifest import code_digest, file_digest, hardware, load, write_once
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.embedding.assets import METHODS, MODELS
from norn.embedding.binding import BindingModel
from norn.embedding.checkpoint import load as load_checkpoint
from norn.embedding.checkpoint import save as save_checkpoint
from norn.embedding.losses import ARM_FLAGS, Decoder, arm_weights
from norn.embedding.numerics import array, normalize
from norn.embedding.training import FactorialBatch, train_arm
from norn.integration.engine import Engine

ARMS = tuple(ARM_FLAGS)
TRAINED_ARMS = tuple(a for a in ARMS if a != "T0")
CONFIG: dict[str, Any] = {
    "revision": "loss-factorial-v1",
    "pairs_version": PAIRS_VERSION,
    "variant": "B3",
    "arms": list(ARMS),
    "seeds": [11, 29, 47],
    "updates": 200,
    "batch_queries": 8,
    "optimizer": "Adam-clipped1-lr0.003-v1",
    "temperature": 0.1,
    "separation_margin": 0.2,
    "lambda_reconstruction": 1.0,
    "lambda_separation": 1.0,
    "loss_scale": "TERM_VALUE_AT_INITIALISATION_PER_BATCH_MEAN",
    "decoder": {"facets": 3, "code": 384, "target": 384, "seed": "TRAINING_SEED"},
    "max_triples_per_query": 12,
    "reload_sample": 6,
    "weights_tuned": False,
    "model_selection": "NONE_RAW_OBJECTIVES_INCOMPARABLE",
    "held_out": "NOT_READ_MARGINS_UNAPPROVED_ADR_0027_Q_D",
}
COMPARABLE_METRICS = ("fit_top1", "fit_mrr", "fit_margin", "triple_order", "triple_gap")
SCORE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Item:
    pair: TrainingPair
    ids: tuple[str, ...]
    query: NDArray[np.float64]
    facets: NDArray[np.float64]
    single: NDArray[np.float64]
    mask: NDArray[np.float64]
    positive: NDArray[np.bool_]
    allowed: NDArray[np.bool_]
    triples: NDArray[np.int64]


def order_arms(summary: dict[str, dict[str, float]], key: str) -> list[str]:
    """Order arms by a comparable diagnostic. A raw objective value is never a ranking key."""
    require(key in COMPARABLE_METRICS, "LOSS_NOT_COMPARABLE")
    return sorted(summary, key=lambda arm: -summary[arm][key])


def _public(case: Any, pair: TrainingPair) -> PublicInput:
    extra = tuple(n.source for n in pair.negatives if n.source is not None)
    markers = (*case.gold.forbidden_sources, *case.gold.forbidden_canaries)
    candidate = PublicInput(case.query, (*case.sources, *extra))
    return validate_public(json.loads(canonical(candidate.payload())), markers)


def train_only(artifacts: dict[str, Any]) -> None:
    """The factorial run owns train-role artifacts only; a held-out path is a custody breach."""
    require(
        all(
            name.startswith(("published/train/", "captures/train/")) or name == "pairs.json"
            for name in artifacts
        ),
        "FACTORIAL_HELDOUT_ARTIFACT",
    )


def checked(root: Path) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    require(
        manifest.get("schema") == 1
        and manifest.get("kind") == "P05_LOSS_FACTORIAL"
        and manifest.get("sealed") is False
        and type(manifest.get("smoke")) is bool,
        "FACTORIAL_MANIFEST_PROFILE",
    )
    require(
        manifest["models"] == json.loads(canonical(MODELS))
        and manifest["methods"] == json.loads(canonical(METHODS))
        and manifest["environment"] == environment(),
        "FACTORIAL_ENVIRONMENT_CHANGED",
    )
    require(manifest["code_digest"] == code_digest(), "FACTORIAL_RUN_CODE_MISMATCH")
    require(manifest["config"] == json.loads(canonical(CONFIG)), "FACTORIAL_CONFIG_CHANGED")
    train_only(manifest["artifacts"])
    for name, sha in manifest["artifacts"].items():
        require(not Path(name).anchor and ".." not in Path(name).parts, "UNSAFE_ARTIFACT_PATH")
        require(file_digest(root / name) == sha, "FACTORIAL_ARTIFACT_CHANGED")
    return cast(dict[str, Any], manifest)


def prepare(
    root: Path,
    model_root: Path,
    *,
    enabled: bool,
    wall_cap_seconds: float,
    smoke: bool = False,
) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    require(0 < wall_cap_seconds <= 86_400, "FACTORIAL_WALL_CAP")
    require(not root.exists(), "RUN_DIRECTORY_EXISTS")
    import benchmark.adapters
    import norn

    check_import_barrier(
        Path(str(norn.__file__)).parent, Path(str(benchmark.adapters.__file__)).parent
    )
    source = code_digest()
    started = time.monotonic()
    pairs = build_pairs(smoke=smoke)
    by_id = {c.query.query_id: c for c in cases("train", seed=pairs.seed, smoke=smoke)}
    root.mkdir(parents=True)
    artifacts = {"pairs.json": write_once(root / "pairs.json", json.loads(dumps(pairs)))}
    for pair in pairs.pairs:
        qid = pair.query_id
        public = _public(by_id[qid], pair)
        artifacts[f"published/train/{qid}.json"] = write_once(
            root / f"published/train/{qid}.json", public.payload()
        )
        tick = time.perf_counter_ns()
        clock = replay_clock(public)
        with Engine(
            root / "stores" / "train" / qid,
            host(public),
            create=True,
            model_root=model_root,
            enable_models=True,
            clock=clock,
        ) as engine:
            engine.access.bootstrap()
            mapping = ingest(engine, public, clock)
            captured = capture(engine, public, mapping)
        captured.update(mapping=mapping, offline_ns=time.perf_counter_ns() - tick)
        artifacts[f"captures/train/{qid}.json"] = write_once(
            root / f"captures/train/{qid}.json", captured
        )
        require(code_digest() == source, "FACTORIAL_SOURCE_CHANGED_DURING_PREPARE")
        require(time.monotonic() - started < wall_cap_seconds, "FACTORIAL_WALL_CAP_EXCEEDED")
        print(canonical({"stage": "capture", "query": qid}), flush=True)
    manifest = {
        "schema": 1,
        "kind": "P05_LOSS_FACTORIAL",
        "sealed": False,
        "smoke": smoke,
        "code_digest": source,
        "config": CONFIG,
        "pairs_sha256": pairs.sha256,
        "wall_time_cap_seconds": wall_cap_seconds,
        "prepare_seconds": time.monotonic() - started,
        "artifacts": artifacts,
        "models": MODELS,
        "methods": METHODS,
        "hardware": hardware(),
        "environment": environment(),
        "labels": "CONSTRUCTED_UNAUDITED",
        "visibility": "TRAIN_ROLE_ONLY; TUNE_AND_EVALUATION_NOT_READ",
    }
    write_once(root / "manifest.json", manifest)
    return {"prepared": len(pairs.pairs), "code_digest": source}


def _triples(pair: TrainingPair, ids: tuple[str, ...], contents: dict[str, Any]) -> list[Any]:
    """(anchor, same-content positive, confusable negative) rows for one query."""
    where = {source_id: i for i, source_id in enumerate(ids)}
    groups: dict[Any, list[str]] = {}
    for source_id in pair.positives:
        if source_id in where:
            groups.setdefault(contents[source_id], []).append(source_id)
    confusable = [
        n
        for n in pair.negatives
        if n.source_id in where
        and (n.kind == "ONE_FIELD" or n.field in (*ONE_FIELD_NAMES, "MULTI"))
    ]
    rows = []
    for members in groups.values():
        for twin in members[1:]:
            for negative in confusable:
                if negative.anchor in members:
                    rows.append([where[members[0]], where[twin], where[negative.source_id]])
    return rows[: CONFIG["max_triples_per_query"]]


def training_items(
    root: Path, manifest: dict[str, Any]
) -> tuple[tuple[Item, ...], TrainingPairs, dict[str, Any]]:
    pairs = loads((root / "pairs.json").read_text(encoding="utf-8"))
    require(pairs.sha256 == manifest["pairs_sha256"], "FACTORIAL_PAIRS_CHANGED")
    by_id = {c.query.query_id: c for c in cases("train", seed=pairs.seed, smoke=manifest["smoke"])}
    items, dropped = [], []
    requested = captured_negatives = 0
    by_kind: dict[str, list[int]] = {}
    for pair in pairs.pairs:
        case = by_id[pair.query_id]
        public = load(root / "published/train" / (pair.query_id + ".json"))
        expected = _public(case, pair)
        require(public == json.loads(canonical(expected.payload())), "FACTORIAL_DATA_CHANGED")
        cap = load(root / "captures/train" / (pair.query_id + ".json"))
        require(cap["input_digest"] == expected.sha256, "FACTORIAL_CAPTURE_INPUT_CHANGED")
        memories = cap["memories"]
        require(all(len(m["source_ids"]) == 1 for m in memories), "FACTORIAL_MEMORY_NOT_ONE_SOURCE")
        ids = tuple(m["source_ids"][0] for m in memories)
        known = {n.source_id for n in pair.negatives}
        requested += len(known)
        captured_negatives += len(known & set(ids))
        for negative in pair.negatives:
            counts = by_kind.setdefault(f"{negative.kind}/{negative.field}", [0, 0])
            counts[0] += negative.source_id in ids
            counts[1] += 1
        if not set(pair.positives) & set(ids):
            dropped.append({"query": pair.query_id, "reason": "POSITIVE_NOT_CAPTURED"})
            continue
        positive, allowed = labels(pair, ids)
        contents = {s.source_id: _content(s.observation) for s in case.sources}
        contents.update(
            {n.source_id: _content(n.source.observation) for n in pair.negatives if n.source}
        )
        rows = _triples(pair, ids, contents)
        items.append(
            Item(
                pair,
                ids,
                array(cap["query"], (384,)),
                array([m["facets"] for m in memories]),
                array([m["single"] for m in memories]),
                array([m["mask"] for m in memories]),
                positive,
                allowed,
                np.asarray(rows, dtype=np.int64).reshape(-1, 3),
            )
        )
    require(bool(items), "TRAINING_POSITIVES_EMPTY")
    stats = {
        "pairs": len(pairs.pairs),
        "items": len(items),
        "dropped": dropped,
        "negatives_requested": requested,
        "negatives_captured": captured_negatives,
        "negatives_captured_vs_requested_by_kind": dict(sorted(by_kind.items())),
        "negatives_not_captured_reason": "ENGINE_ELIGIBILITY_FILTERED_THE_CANDIDATE_CORPUS",
        "items_with_triples": sum(1 for i in items if len(i.triples)),
        "triples": sum(len(i.triples) for i in items),
    }
    return tuple(items), pairs, stats


def build_batches(items: tuple[Item, ...]) -> tuple[FactorialBatch, ...]:
    """Group queries so every batch holds at least one separation triple (deterministic)."""
    size = CONFIG["batch_queries"]
    count = -(-len(items) // size)
    withs = [i for i in items if len(i.triples)]
    require(len(withs) >= count, "FACTORIAL_TRIPLES_SCARCE")
    groups: list[list[Item]] = [[] for _ in range(count)]
    for index, item in enumerate(withs):
        groups[index % count].append(item)
    for item in (i for i in items if not len(i.triples)):
        open_groups = [g for g in groups if len(g) < size]
        min(open_groups, key=len).append(item)
    batches = []
    for group in groups:
        memories = [(item, row) for item in group for row in range(len(item.ids))]
        positive = np.zeros((len(group), len(memories)), dtype=bool)
        allowed = np.zeros_like(positive)
        triples, offset = [], 0
        for q, item in enumerate(group):
            n = len(item.ids)
            positive[q, offset : offset + n] = item.positive
            allowed[q, offset : offset + n] = item.allowed
            triples.extend((item.triples + offset).tolist())
            offset += n
        batches.append(
            FactorialBatch(
                np.stack([item.query for item in group]),
                np.concatenate([item.facets for item in group]),
                np.concatenate([item.single for item in group]),
                np.concatenate([item.mask for item in group]),
                positive,
                allowed,
                np.asarray(triples, dtype=np.int64).reshape(-1, 3),
            )
        )
    return tuple(batches)


def train_run(root: Path) -> dict[str, Any]:
    manifest = checked(root)
    require(not (root / "training.json").exists(), "TRAINING_ALREADY_RECORDED")
    items, pairs, supervision = training_items(root, manifest)
    batches = build_batches(items)
    training_digest = digest(
        canonical({"pairs": pairs.sha256, "data": manifest["artifacts"]}).encode()
    )
    started = time.monotonic()
    deadline = started + manifest["wall_time_cap_seconds"]
    updates = 16 if manifest["smoke"] else CONFIG["updates"]
    jobs, failures = [], []
    for arm in TRAINED_ARMS:
        for seed in CONFIG["seeds"]:
            model = BindingModel(CONFIG["variant"], seed)
            decoder = Decoder.create(
                CONFIG["decoder"]["facets"],
                CONFIG["decoder"]["code"],
                CONFIG["decoder"]["target"],
                seed,
            )
            weights = arm_weights(
                arm, lam_rec=CONFIG["lambda_reconstruction"], lam_sep=CONFIG["lambda_separation"]
            )
            try:
                receipt = train_arm(
                    model,
                    decoder,
                    batches,
                    weights,
                    seed=seed,
                    updates=updates,
                    aggregate_deadline=deadline,
                    temperature=CONFIG["temperature"],
                    margin=CONFIG["separation_margin"],
                )
            except NornError as error:
                failures.append({"arm": arm, "seed": seed, "code": error.code})
                print(canonical({"stage": "failed", "arm": arm, "seed": seed, "code": error.code}))
                continue
            receipt.update(
                arm=arm,
                pairs_sha256=pairs.sha256,
                config_sha256=digest(canonical(CONFIG).encode()),
                decoder_sha256=digest(
                    decoder.weights.astype("<f4").tobytes() + decoder.bias.astype("<f4").tobytes()
                ),
                decoder_stored="NO_TRAINING_TIME_ONLY",
            )
            relative = f"checkpoints/{arm}-{seed}.json"
            saved = save_checkpoint(root / relative, model, receipt, training_digest)
            jobs.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "path": relative,
                    "sha256": saved.sha256,
                    "receipt": receipt,
                }
            )
            print(
                canonical(
                    {
                        "stage": "trained",
                        "arm": arm,
                        "seed": seed,
                        "seconds": receipt["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
            require(
                code_digest() == manifest["code_digest"], "FACTORIAL_SOURCE_CHANGED_DURING_TRAIN"
            )
    value = {
        "jobs": jobs,
        "failures": failures,
        "supervision": supervision,
        "batches": {
            "count": len(batches),
            "queries": [len(b.queries) for b in batches],
            "memories": [len(b.facets) for b in batches],
            "triples": [len(b.triples) for b in batches],
        },
        "training_digest": training_digest,
        "code_digest": manifest["code_digest"],
        "elapsed_seconds": time.monotonic() - started,
    }
    write_once(root / "training.json", value)
    return {
        "trained_jobs": len(jobs),
        "failures": len(failures),
        "elapsed_seconds": value["elapsed_seconds"],
    }


def _codes_raw(item: Item) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    return normalize(item.query[None])[0][0], normalize(item.single)[0]


def _codes_model(model: BindingModel) -> Any:
    def codes(item: Item) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        return (
            model.forward(item.query[None], query=True)[0][0],
            model.forward(item.facets, item.mask)[0],
        )

    return codes


def fit_metrics(items: tuple[Item, ...], codes_of: Any, margin: float) -> dict[str, Any]:
    """Train-fit diagnostics with explicit denominators (never a held-out claim)."""
    top1: list[bool] = []
    margins: list[float] = []
    reciprocal: list[float] = []
    order: list[bool] = []
    gaps: list[float] = []
    for item in items:
        query, memory = codes_of(item)
        score = memory @ query
        allowed = np.flatnonzero(item.allowed)
        ranked = allowed[np.argsort(-score[allowed], kind="stable")]
        reciprocal.append(1.0 / (1 + int(np.flatnonzero(item.positive[ranked])[0])))
        negative = item.allowed & ~item.positive
        if negative.any():
            top1.append(bool(item.positive[ranked[0]]))
            margins.append(float(score[item.positive].max() - score[negative].max()))
        if len(item.triples):
            a, p, n = item.triples[:, 0], item.triples[:, 1], item.triples[:, 2]
            gap = (memory[a] * memory[p]).sum(1) - (memory[a] * memory[n]).sum(1)
            gaps.extend(gap.tolist())
            order.extend((gap > 0).tolist())

    def mean(values: list[Any]) -> float | None:
        return float(np.mean(values)) if values else None

    return {
        "fit_top1": mean(top1),
        "fit_top1_denominator": len(top1),
        "fit_mrr": mean(reciprocal),
        "fit_mrr_denominator": len(reciprocal),
        "fit_margin": mean(margins),
        "triple_order": mean(order),
        "triple_gap": mean(gaps),
        "triple_margin_met": mean([g >= margin for g in gaps]),
        "triple_denominator": len(gaps),
    }


def _reload(
    root: Path,
    model_root: Path,
    items: tuple[Item, ...],
    jobs: list[dict[str, Any]],
    sample_size: int,
) -> list[dict[str, Any]]:
    supported = set(SPECS[CONFIG["variant"]].capabilities)
    usable = []
    for item in items:
        public = validate_public(load(root / "published/train" / (item.pair.query_id + ".json")))
        if set(public.query.required_capabilities) <= supported:
            usable.append((item, public))
    stride = max(1, len(usable) // sample_size)
    sample = usable[::stride][:sample_size]
    rows = []
    for item, public in sample:
        cap = load(root / "captures/train" / (item.pair.query_id + ".json"))
        with Engine(
            root / "stores" / "train" / item.pair.query_id,
            host(public),
            model_root=model_root,
            enable_models=True,
        ) as engine:
            adapter = BindingAdapter(engine, public, cap["mapping"])
            for job in jobs:
                path = root / job["path"]
                engine.project_binding(CONFIG["variant"], path)
                packet = adapter.query(CONFIG["variant"], path)[1]["packet"]
                model = load_checkpoint(path).model
                offline = dict(
                    zip(
                        item.ids,
                        (
                            model.forward(item.facets, item.mask)[0]
                            @ model.forward(item.query[None], query=True)[0][0]
                        ).tolist(),
                        strict=True,
                    )
                )
                engine_scores: dict[str, float] = {}
                for key, score in zip(
                    packet["binding_ranking"], packet["binding_scores"], strict=True
                ):
                    engine_scores[cap["mapping"][key.split(":", 1)[0]]] = score
                diff = max(
                    (abs(engine_scores[s] - offline[s]) for s in engine_scores), default=None
                )
                rows.append(
                    {
                        "query": item.pair.query_id,
                        "arm": job["arm"],
                        "seed": job["seed"],
                        "compared_sources": len(engine_scores),
                        "max_abs_score_difference": diff,
                        "within_tolerance": diff is not None and diff <= SCORE_TOLERANCE,
                        "checkpoint_sha256": packet["binding_checkpoint"],
                        "checkpoint_matches_job": packet["binding_checkpoint"] == job["sha256"],
                    }
                )
    return rows


def report(
    root: Path, model_root: Path, *, enabled: bool, reload_sample: int | None = None
) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    manifest = checked(root)
    training = load(root / "training.json")
    require(training["code_digest"] == manifest["code_digest"], "FACTORIAL_TRAINING_CODE_MISMATCH")
    for job in training["jobs"]:
        require(
            job["path"] == f"checkpoints/{job['arm']}-{job['seed']}.json", "UNSAFE_CHECKPOINT_PATH"
        )
        require(file_digest(root / job["path"]) == job["sha256"], "CHECKPOINT_SOURCE_CHANGED")
    items = training_items(root, manifest)[0]
    margin = CONFIG["separation_margin"]
    arms: dict[str, Any] = {"T0": {"fit": fit_metrics(items, _codes_raw, margin), "seeds": {}}}
    init: dict[str, Any] = {}
    for seed in CONFIG["seeds"]:
        init[str(seed)] = fit_metrics(
            items, _codes_model(BindingModel(CONFIG["variant"], seed)), margin
        )
    for job in training["jobs"]:
        model = load_checkpoint(root / job["path"]).model
        row = fit_metrics(items, _codes_model(model), margin)
        receipt = job["receipt"]
        row["train"] = {
            "loss_first": receipt["losses"][0],
            "loss_last": receipt["losses"][-1],
            "terms_first": receipt["terms"][0],
            "terms_last": receipt["terms"][-1],
            "reference": receipt["reference"],
            "parameter_delta_l2": receipt["parameter_delta_l2"],
            "nonzero_gradient_steps": receipt["nonzero_gradient_steps"],
            "code_effective_rank": receipt["sample_code_effective_rank"],
            "elapsed_seconds": receipt["elapsed_seconds"],
        }
        arms.setdefault(job["arm"], {"seeds": {}})["seeds"][str(job["seed"])] = row
    summary: dict[str, dict[str, float]] = {}
    for arm, value in arms.items():
        rows = list(value["seeds"].values()) if arm != "T0" else [value["fit"]]
        summary[arm] = {
            key: float(np.mean([r[key] for r in rows if r[key] is not None]))
            for key in COMPARABLE_METRICS
            if any(r[key] is not None for r in rows)
        }
    sample_size = CONFIG["reload_sample"] if reload_sample is None else reload_sample
    require(1 <= sample_size <= 64, "FACTORIAL_RELOAD_SAMPLE")
    reload = _reload(root, model_root, items, training["jobs"], sample_size)
    return {
        "revision": CONFIG["revision"],
        "scope": "TRAIN_FIT_DIAGNOSTICS_AND_RELOAD_PROOF; NOT_HELD_OUT",
        "selection": CONFIG["model_selection"],
        "held_out": CONFIG["held_out"],
        "supervision": training["supervision"],
        "batches": training["batches"],
        "failures": training["failures"],
        "arms": arms,
        "untrained_adapter": init,
        "summary_mean_over_seeds": summary,
        "reload": {
            "rows": reload,
            "tolerance": SCORE_TOLERANCE,
            "sample_queries": sample_size,
            "all_within_tolerance": all(r["within_tolerance"] for r in reload),
            "all_checkpoints_match": all(r["checkpoint_matches_job"] for r in reload),
        },
        "manifest_digest": file_digest(root / "manifest.json"),
        "training_digest": file_digest(root / "training.json"),
        "configuration": json.loads(canonical(CONFIG)),
    }


__all__ = ["CONFIG", "order_arms", "prepare", "report", "train_run", "train_only"]
