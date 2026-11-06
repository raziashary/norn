"""P05-T04: objective-gradient conflict, collapse and warm-start disclosure on a T03 run.

Reads a completed ``factorial`` run by artifact digest (its code digest is allowed to differ: the
source moved on) and re-trains T7 with a read-only observer. The re-run must reproduce T03's loss
sequence exactly or the result says so. Train role only; nothing here is held-out evidence.
"""

import time
from pathlib import Path
from typing import Any

import numpy as np

from benchmark.runs import loss_factorial as lf
from benchmark.runs.manifest import code_digest, file_digest, load, write_once
from norn.contracts.errors import require
from norn.embedding import diagnostics as dg
from norn.embedding.binding import BindingModel
from norn.embedding.checkpoint import load as load_checkpoint
from norn.embedding.losses import Decoder, ObjectiveWeights, arm_weights
from norn.embedding.training import Schedule, reference_scales, train_arm

WARM_START = {"retrieval_updates": 100}
TRACE_EVERY = 10


def verified_manifest(root: Path) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    require(manifest.get("kind") == "P05_LOSS_FACTORIAL", "FACTORIAL_MANIFEST_PROFILE")
    lf.train_only(manifest["artifacts"])
    for name, sha in manifest["artifacts"].items():
        require(file_digest(root / name) == sha, "FACTORIAL_ARTIFACT_CHANGED")
    return dict(manifest)


def run(root: Path, output: Path, *, wall_cap_seconds: float) -> dict[str, Any]:
    require(0 < wall_cap_seconds <= 3600, "DIAGNOSTICS_WALL_CAP")
    started = time.monotonic()
    manifest = verified_manifest(root)
    training = load(root / "training.json")
    cfg = manifest["config"]
    items, pairs, _ = lf.training_items(root, manifest)
    batches = lf.build_batches(items)
    full = ObjectiveWeights(retrieval=1.0, reconstruction=1.0, separation=1.0)
    updates = 16 if manifest["smoke"] else cfg["updates"]
    seeds: dict[str, Any] = {}
    for seed in cfg["seeds"]:
        model = BindingModel(cfg["variant"], seed)
        decoder = Decoder.create(
            cfg["decoder"]["facets"], cfg["decoder"]["code"], cfg["decoder"]["target"], seed
        )
        reference = reference_scales(
            model,
            decoder,
            batches,
            full,
            temperature=cfg["temperature"],
            margin=cfg["separation_margin"],
        )
        rows = []
        for batch in batches:
            found, missing = dg.term_gradients(
                model,
                decoder,
                batch,
                reference,
                temperature=cfg["temperature"],
                margin=cfg["separation_margin"],
            )
            rows.append(dg.conflict(found, missing))
        initial = {
            "conflict": dg.summarize(rows),
            "norms_mean": {
                name: float(np.mean([r["norms"][name] for r in rows if name in r["norms"]]))
                for name in dg.OBJECTIVES
            },
            "codes": dg.model_code_stats(model, batches[0]),
        }
        trace = dg.Trace(
            TRACE_EVERY, temperature=cfg["temperature"], margin=cfg["separation_margin"]
        )
        t7 = train_arm(
            model,
            decoder,
            batches,
            arm_weights(
                "T7", lam_rec=cfg["lambda_reconstruction"], lam_sep=cfg["lambda_separation"]
            ),
            seed=seed,
            updates=updates,
            temperature=cfg["temperature"],
            margin=cfg["separation_margin"],
            observer=trace,
        )
        recorded = next(j for j in training["jobs"] if j["arm"] == "T7" and j["seed"] == seed)
        trajectory = [
            {
                "update": row["update"],
                "pairs": {k: v["cosine"] for k, v in row["pairs"].items()},
                "norms": row["norms"],
                "missing": row["missing"],
                "collapsed": row["codes"]["collapsed"],
                "effective_rank": row["codes"]["effective_rank"],
                "mean_pairwise_cosine": row["codes"]["mean_pairwise_cosine"],
            }
            for row in trace.rows
        ]
        warm_model = BindingModel(cfg["variant"], seed)
        warm_decoder = Decoder.create(
            cfg["decoder"]["facets"], cfg["decoder"]["code"], cfg["decoder"]["target"], seed
        )
        first = WARM_START["retrieval_updates"] if not manifest["smoke"] else 8
        warm = train_arm(
            warm_model,
            warm_decoder,
            batches,
            Schedule(
                (
                    (1, arm_weights("T1")),
                    (
                        first + 1,
                        arm_weights(
                            "T7",
                            lam_rec=cfg["lambda_reconstruction"],
                            lam_sep=cfg["lambda_separation"],
                        ),
                    ),
                )
            ),
            seed=seed,
            updates=updates,
            temperature=cfg["temperature"],
            margin=cfg["separation_margin"],
        )
        margin = cfg["separation_margin"]
        seeds[str(seed)] = {
            "reference": reference,
            "initial": initial,
            "t7_reproduces_t03_losses": t7["losses"] == recorded["receipt"]["losses"],
            "t7_trajectory": trajectory,
            "t7_final_fit": lf.fit_metrics(items, lf._codes_model(model), margin),
            "warm_start": {
                "schedule": warm["schedule"],
                "exposure": warm["exposure"],
                "final_terms": warm["terms"][-1],
                "fit": lf.fit_metrics(items, lf._codes_model(warm_model), margin),
                "stored": "NO_IN_MEMORY_DIAGNOSTIC_TREATMENT",
            },
            "checkpoint_codes": {
                job["arm"]: dg.model_code_stats(
                    load_checkpoint(root / job["path"]).model, batches[0]
                )
                for job in training["jobs"]
                if job["seed"] == seed
            },
        }
        require(time.monotonic() - started < wall_cap_seconds, "DIAGNOSTICS_WALL_CAP_EXCEEDED")
        print({"stage": "diagnosed", "seed": seed}, flush=True)
    result = {
        "scope": "TRAIN_ROLE_DIAGNOSTICS; NOT_HELD_OUT; NO_SELECTION",
        "source_run": str(root.name),
        "source_manifest_digest": file_digest(root / "manifest.json"),
        "source_training_digest": file_digest(root / "training.json"),
        "pairs_sha256": pairs.sha256,
        "code_digest": code_digest(),
        "source_run_code_digest": manifest["code_digest"],
        "trace_every": TRACE_EVERY,
        "collapse_cutoffs": {
            "cosine": dg.COLLAPSE_COSINE,
            "rank": dg.COLLAPSE_RANK,
            "kind": "DIAGNOSTIC_NOT_MARGIN",
        },
        "seeds": seeds,
        "elapsed_seconds": time.monotonic() - started,
    }
    return {"digest": write_once(output, result), "elapsed_seconds": result["elapsed_seconds"]}
