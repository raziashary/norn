"""Bounded development-only binding study; labels remain in trusted training/scoring owners."""

import hashlib
import json
import os
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import numpy as np

from benchmark.adapters.baseline import host
from benchmark.adapters.binding_arms import capability
from benchmark.adapters.r7 import BindingAdapter, capture, ingest
from benchmark.fixtures.binding_cases import ROLE_INDICES, cases
from benchmark.fixtures.publication import check_import_barrier, publish, validate_public
from benchmark.runs.manifest import code_digest, file_digest, hardware, load, write_once
from norn.canonical.sources import safe_path
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.embedding.assets import METHODS, MODELS
from norn.embedding.binding import LEARNED, BindingModel
from norn.embedding.checkpoint import save as save_checkpoint
from norn.embedding.numerics import array
from norn.embedding.training import TrainingBatch, train
from norn.integration.engine import Engine

CONFIG: dict[str, Any] = {
    "revision": "binding-development-v2",
    "split": ROLE_INDICES,
    "seeds": [11, 29, 47],
    "updates": 200,
    "batch_queries": 8,
    "optimizer": "Adam-clipped1-lr0.003-v1",
    "temperature": 0.1,
    "backbone_tokens_per_input": 512,
    "numeric_index_bytes_per_event": 1536,
    "max_training_seconds": 7200,
    "job_seconds": 1200,
    "max_array_bytes": 536870912,
    "b5": capability("B5"),
    "primary_stage": "FINAL_EVIDENCE",
    "identity_stage": "BINDING_CANDIDATES",
    "promotion_margins": "UNSET_EXPLORATORY_ONLY",
    "model_selection": "NONE_FIXED_CONFIG",
}


def environment() -> dict[str, Any]:
    return {
        "libraries": {name: version(name) for name in ("numpy", "tokenizers", "onnxruntime")},
        "head_threads": {
            name: os.environ.get(name)
            for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        },
        "provider": "CPUExecutionProvider",
        "native_threads": 2,
    }


def checked(root: Path) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    require(
        manifest.get("schema") == 1
        and manifest.get("kind") == "P04_BINDING_DEVELOPMENT"
        and manifest.get("sealed") is False
        and type(manifest.get("smoke")) is bool,
        "BINDING_MANIFEST_PROFILE",
    )
    require(
        manifest["models"] == json.loads(canonical(MODELS))
        and manifest["methods"] == json.loads(canonical(METHODS))
        and manifest["environment"] == environment(),
        "BINDING_ENVIRONMENT_CHANGED",
    )
    require(manifest["code_digest"] == code_digest(), "BINDING_RUN_CODE_MISMATCH")
    require(manifest["config"] == json.loads(canonical(CONFIG)), "BINDING_CONFIG_CHANGED")
    for name, sha in manifest["artifacts"].items():
        require(not Path(name).anchor and ".." not in Path(name).parts, "UNSAFE_ARTIFACT_PATH")
        require(file_digest(root / name) == sha, "BINDING_ARTIFACT_CHANGED")
    return cast(dict[str, Any], manifest)


def ledger_digest(path: Path) -> str:
    """Stream the bounded P04 ledger; individual artifacts keep the shared64MB limit."""
    safe_path(path)
    require(path.is_file() and path.stat().st_size <= 512_000_000, "BINDING_LEDGER_BUDGET")
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1_048_576):
            checksum.update(chunk)
    return checksum.hexdigest()


def prepare(root: Path, model_root: Path, *, enabled: bool, smoke: bool = False) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    require(not root.exists(), "RUN_DIRECTORY_EXISTS")
    import benchmark.adapters
    import norn

    check_import_barrier(
        Path(str(norn.__file__)).parent, Path(str(benchmark.adapters.__file__)).parent
    )
    source = code_digest()
    root.mkdir(parents=True)
    artifacts: dict[str, str] = {}
    planned: dict[str, list[str]] = {}
    cluster_sets: dict[str, set[str]] = {}
    for role in ROLE_INDICES:
        values = cases(role, smoke=smoke)
        planned[role] = [c.query.query_id for c in values]
        cluster_sets[role] = {c.gold.cluster for c in values}
        for case in values:
            qid = case.query.query_id
            public = publish(case)
            for relative, value in (
                (f"published/{role}/{qid}.json", public.payload()),
                (f"evaluator/{role}/{qid}.json", asdict(case.gold)),
            ):
                artifacts[relative] = write_once(root / relative, value)
            started = time.perf_counter_ns()
            with Engine(
                root / "stores" / role / qid,
                host(public),
                create=True,
                model_root=model_root,
                enable_models=True,
            ) as engine:
                engine.access.bootstrap()
                mapping = ingest(engine, public)
                captured = capture(engine, public, mapping)
            captured.update(mapping=mapping, offline_ns=time.perf_counter_ns() - started)
            relative = f"captures/{role}/{qid}.json"
            artifacts[relative] = write_once(root / relative, captured)
            require(code_digest() == source, "BINDING_SOURCE_CHANGED_DURING_PREPARE")
            print(canonical({"stage": "capture", "role": role, "query": qid}), flush=True)
    names = tuple(ROLE_INDICES)
    require(
        all(
            not cluster_sets[a] & cluster_sets[b]
            for i, a in enumerate(names)
            for b in names[i + 1 :]
        ),
        "BINDING_PARTITION_OVERLAP",
    )
    manifest = {
        "schema": 1,
        "kind": "P04_BINDING_DEVELOPMENT",
        "sealed": False,
        "smoke": smoke,
        "code_digest": source,
        "config": CONFIG,
        "planned": planned,
        "cluster_sets": {k: sorted(v) for k, v in cluster_sets.items()},
        "artifacts": artifacts,
        "models": MODELS,
        "methods": METHODS,
        "hardware": hardware(),
        "environment": environment(),
        "labels": "CONSTRUCTED_UNAUDITED",
        "visibility": "PUBLIC_SOURCES_ONLY; SUPERVISION_TRAIN_ONLY",
    }
    write_once(root / "manifest.json", manifest)
    return {"prepared": {k: len(v) for k, v in planned.items()}, "code_digest": source}


def training_batches(
    root: Path, manifest: dict[str, Any]
) -> tuple[tuple[TrainingBatch, ...], dict[str, Any]]:
    items = []
    skipped = []
    expected = {c.query.query_id: c for c in cases("train", smoke=manifest["smoke"])}
    require(list(expected) == manifest["planned"]["train"], "BINDING_CASES_CHANGED")
    for qid in manifest["planned"]["train"]:
        gold = load(root / "evaluator/train" / (qid + ".json"))
        public = load(root / "published/train" / (qid + ".json"))
        require(
            gold == json.loads(canonical(asdict(expected[qid].gold)))
            and public == json.loads(canonical(publish(expected[qid]).payload())),
            "BINDING_DATA_OR_LABEL_CHANGED",
        )
        captured = load(root / "captures/train" / (qid + ".json"))
        require(
            captured["input_digest"] == publish(expected[qid]).sha256,
            "BINDING_CAPTURE_INPUT_CHANGED",
        )
        target = training_targets(gold, captured)
        if not any(target):
            skipped.append({"query": qid, "reason": "NO_ELIGIBLE_SUPERVISED_POSITIVE"})
            continue
        items.append((captured, target))
    require(bool(items), "TRAINING_POSITIVES_EMPTY")
    batches = []
    for start in range(0, len(items), CONFIG["batch_queries"]):
        group = items[start : start + CONFIG["batch_queries"]]
        memories = [m for captured, _ in group for m in captured["memories"]]
        positive = np.zeros((len(group), len(memories)), dtype=bool)
        allowed = np.zeros_like(positive)
        offset = 0
        for i, (_captured, targets) in enumerate(group):
            positive[i, offset : offset + len(targets)] = targets
            allowed[i, offset : offset + len(targets)] = True
            offset += len(targets)
        batches.append(
            TrainingBatch(
                array([c["query"] for c, _ in group]),
                array([m["facets"] for m in memories]),
                array([m["single"] for m in memories]),
                array([m["mask"] for m in memories]),
                positive,
                allowed,
            )
        )
    return tuple(batches), {
        "supervised_queries": len(items),
        "skipped": skipped,
        "false_negative_policy": (
            "ALL_ACCEPTABLE_SOURCES; AMBIGUOUS_ALL_ELIGIBLE; SAME_PUBLIC_CORPUS_ONLY"
        ),
    }


def training_targets(gold: dict[str, Any], captured: dict[str, Any]) -> list[bool]:
    # An underspecified cue cannot make one compatible occurrence a negative.
    if gold["reason"] == "AMBIGUOUS":
        return [True for _ in captured["memories"]]
    target_sources = set().union(
        *(set(s) for s in (*gold["acceptable_sets"], *gold.get("partial_sets", [])))
    )
    return [bool(set(m["source_ids"]) & target_sources) for m in captured["memories"]]


def train_run(root: Path) -> dict[str, Any]:
    manifest = checked(root)
    require(not (root / "training.json").exists(), "TRAINING_ALREADY_RECORDED")
    batches, supervision = training_batches(root, manifest)
    training_names = {name: sha for name, sha in manifest["artifacts"].items() if "/train/" in name}
    training_digest = digest(canonical(training_names).encode())
    started = time.monotonic()
    jobs = []
    updates = 16 if manifest["smoke"] else CONFIG["updates"]
    for seed in CONFIG["seeds"]:
        for variant in LEARNED:
            model = BindingModel(variant, seed)
            receipt = train(
                model, batches, seed=seed, updates=updates, aggregate_deadline=started + 7200
            )
            relative = f"checkpoints/{variant}-{seed}.json"
            saved = save_checkpoint(root / relative, model, receipt, training_digest)
            jobs.append(
                {
                    "variant": variant,
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
                        "variant": variant,
                        "seed": seed,
                        "updates": updates,
                        "seconds": receipt["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
            require(code_digest() == manifest["code_digest"], "BINDING_SOURCE_CHANGED_DURING_TRAIN")
    value = {
        "jobs": jobs,
        "supervision": supervision,
        "training_digest": training_digest,
        "code_digest": manifest["code_digest"],
        "elapsed_seconds": time.monotonic() - started,
    }
    write_once(root / "training.json", value)
    return {"trained_jobs": len(jobs), "elapsed_seconds": value["elapsed_seconds"]}


def evaluate(root: Path, model_root: Path, *, enabled: bool) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    manifest = checked(root)
    training = load(root / "training.json")
    require(training["code_digest"] == manifest["code_digest"], "BINDING_TRAINING_CODE_MISMATCH")
    jobs = training["jobs"]
    require(len(jobs) == 12, "BINDING_TRAINING_JOBS_MISSING")
    require(
        {(j["variant"], j["seed"]) for j in jobs}
        == {(v, s) for v in LEARNED for s in CONFIG["seeds"]},
        "BINDING_TRAINING_JOBS_MISSING",
    )
    for job in jobs:
        require(
            job["path"] == f"checkpoints/{job['variant']}-{job['seed']}.json",
            "UNSAFE_CHECKPOINT_PATH",
        )
        require(file_digest(root / job["path"]) == job["sha256"], "CHECKPOINT_SOURCE_CHANGED")
    conditions = [(v, None, None) for v in ("B0", "B1", "B2")]
    conditions.extend((j["variant"], j["seed"], root / j["path"]) for j in jobs)
    ledger = root / "binding-ledger.jsonl"
    require(not ledger.exists(), "BINDING_LEDGER_EXISTS")
    chain = file_digest(root / "manifest.json")
    counts: dict[str, int] = {}
    planned = []
    with ledger.open("xb") as stream:
        for role in ("tune", "evaluation"):
            for qid in manifest["planned"][role]:
                public = validate_public(load(root / "published" / role / (qid + ".json")))
                captured = load(root / "captures" / role / (qid + ".json"))
                with Engine(
                    root / "stores" / role / qid,
                    host(public),
                    model_root=model_root,
                    enable_models=True,
                ) as engine:
                    adapter = BindingAdapter(engine, public, captured["mapping"])
                    # Deterministic rotation balances the first resident-model exposure.
                    shift = int(qid[-8:], 16) % len(conditions)
                    ordered = conditions[shift:] + conditions[:shift]
                    for variant, seed, checkpoint_path in ordered:
                        planned.append([role, qid, variant, seed])
                        tick = time.perf_counter_ns()
                        projection: dict[str, Any] = {}
                        diagnostic: dict[str, Any] = {}
                        project_elapsed_ns = None
                        project_budget = QueryBudget(600_000)
                        failure_stage = "PROJECT"
                        try:
                            projection = engine.project_binding(
                                variant, checkpoint_path, budget=project_budget
                            )
                            project_elapsed_ns = time.perf_counter_ns() - tick
                            failure_stage = "FIRST_RECALL"
                            result, diagnostic = adapter.query(variant, checkpoint_path)
                            diagnostic["first_result"] = asdict(result)
                            failure_stage = "REPEATED_RECALL"
                            repeated, repeated_diagnostic = adapter.query(variant, checkpoint_path)
                            diagnostic.update(
                                repeated=asdict(repeated),
                                repeated_diagnostic=repeated_diagnostic,
                                repeat_unchanged=result == repeated,
                            )
                            failure_stage = "NONE"
                        except NornError as error:
                            from benchmark.adapters.contracts import Result

                            result = Result(
                                "ERROR", None, (), coverage="UNAVAILABLE", reason=error.code
                            )
                        counts[result.disposition] = counts.get(result.disposition, 0) + 1
                        row = {
                            "role": role,
                            "query": qid,
                            "variant": variant,
                            "seed": seed,
                            "result": asdict(result),
                            "projection": projection,
                            "diagnostic": diagnostic,
                            "total_ns": time.perf_counter_ns() - tick,
                            "project_elapsed_ns": project_elapsed_ns,
                            "project_attempt_usage": project_budget.usage(),
                            "failure_stage": failure_stage,
                            "previous_digest": chain,
                        }
                        chain = digest(canonical(row).encode())
                        stream.write((canonical({**row, "row_digest": chain}) + "\n").encode())
                        stream.flush()

                        os.fsync(stream.fileno())
                require(
                    code_digest() == manifest["code_digest"], "BINDING_SOURCE_CHANGED_DURING_EVAL"
                )
                print(canonical({"stage": "evaluated", "role": role, "query": qid}), flush=True)
    completion = {
        "planned": planned,
        "counts": counts,
        "last_digest": chain,
        "ledger_digest": ledger_digest(ledger),
        "training_digest": file_digest(root / "training.json"),
        "manifest_digest": file_digest(root / "manifest.json"),
    }
    write_once(root / "binding-completion.json", completion)
    return {"pairs": len(planned), "counts": counts}
