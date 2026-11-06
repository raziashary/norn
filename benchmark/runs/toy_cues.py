"""P05-T06: reproduce the blueprint weak-cue versus correlated-competitor toy stress test.

A dense cosine choice is compared with a binary top-k support-overlap choice. The two keep
different information (magnitudes and directions versus positions only), so this is a geometric
stress test, not a trained-retrieval result and not evidence about real embeddings. Ties are never
credited. Procedure and tolerances were pinned in the MDP card before this code existed.
"""

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from benchmark.runs.manifest import code_digest, write_once
from benchmark.runs.toy_support import KS, declared, top_k_mask
from norn.contracts.errors import require

SEED, DIMENSION, TRIALS = 73319, 2048, 3000
COMPETITOR_RHO = 0.9
CUE_RHOS = (0.20, 0.35, 0.60)
VARIANTS = ("V1", "V2")
SCOPE = (
    "GEOMETRIC_STRESS_TEST; INFORMATION_RETENTION_MISMATCH_DENSE_MAGNITUDES_VS_SPARSE_POSITIONS; "
    "NOT_A_TRAINED_MODEL; NOT_REAL_EMBEDDINGS"
)


def classify(target: NDArray[Any], competitor: NDArray[Any]) -> dict[str, int]:
    """Strict outcome counts of target overlap versus competitor overlap; equality is a tie."""
    require(target.shape == competitor.shape and target.ndim == 1, "TOY_OVERLAP_SHAPE")
    return {
        "correct": int((target > competitor).sum()),
        "ties": int((target == competitor).sum()),
        "errors": int((target < competitor).sum()),
    }


def cosine(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    result = (a * b).sum(axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
    return np.asarray(result, dtype=np.float64)


def simulate(variant: str, *, seed: int = SEED, trials: int = TRIALS) -> dict[float, Any]:
    require(variant in VARIANTS, "TOY_VARIANT_UNKNOWN")
    rng = np.random.default_rng(seed)

    def gaussian() -> NDArray[np.float64]:
        return rng.standard_normal((trials, DIMENSION))

    target = gaussian()
    noise = {}
    if variant == "V2":  # the three cue noises come before the competitor noise
        noise = {rho: gaussian() for rho in CUE_RHOS}
    competitor = COMPETITOR_RHO * target + np.sqrt(1.0 - COMPETITOR_RHO**2) * gaussian()
    masks = {k: (top_k_mask(target, k), top_k_mask(competitor, k)) for k in KS}
    rows: dict[float, Any] = {}
    for rho in CUE_RHOS:
        drawn = noise[rho] if variant == "V2" else gaussian()
        query = rho * target + np.sqrt(1.0 - rho**2) * drawn
        dense = classify(cosine(query, target), cosine(query, competitor))
        row: dict[str, Any] = {"dense": dense}
        for k in KS:
            q = top_k_mask(query, k)
            t_mask, c_mask = masks[k]
            row[f"k{k}"] = classify((q & t_mask).sum(axis=1), (q & c_mask).sum(axis=1))
        rows[rho] = row
    return rows


def proportions(rows: dict[float, Any], trials: int = TRIALS) -> dict[float, dict[str, float]]:
    result = {}
    for rho, row in rows.items():
        result[rho] = {
            "dense_correct": row["dense"]["correct"] / trials,
            **{f"k{k}_strict": row[f"k{k}"]["correct"] / trials for k in KS},
            **{f"k{k}_ties": row[f"k{k}"]["ties"] / trials for k in KS},
        }
    return result


def compare(
    rows: dict[float, Any], expected: dict[str, Any] | None = None, trials: int = TRIALS
) -> dict[str, Any]:
    study = (expected or declared())["study_2"]
    tolerance = study["exact_reproduction_tolerance"]
    measured = proportions(rows, trials)
    cells = []
    for rho in CUE_RHOS:
        for name, target in study["rows"][f"{rho:.2f}"].items():
            value = measured[rho][name]
            standard_error = float(np.sqrt(max(value * (1 - value), 1e-12) / trials))
            cells.append(
                {
                    "cue_rho": rho,
                    "metric": name,
                    "declared": target,
                    "measured": value,
                    "deviation": value - target,
                    "exact": abs(value - target) <= tolerance,
                    "within_3_se": abs(value - target) <= 3 * standard_error,
                }
            )
    exact = all(c["exact"] for c in cells)
    return {
        "cells": cells,
        "exact_reproduction": exact,
        "all_within_3_se": all(c["within_3_se"] for c in cells),
        "verdict": "EXACT_REPRODUCTION" if exact else "NOT_EXACT_REPRODUCTION",
    }


def run(output: Path) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for name in VARIANTS:
        rows = simulate(name)
        variants[name] = {
            "counts": {f"{rho:.2f}": row for rho, row in rows.items()},
            "comparison": compare(rows),
        }
        print(
            {
                "stage": "variant",
                "variant": name,
                "verdict": variants[name]["comparison"]["verdict"],
            },
            flush=True,
        )
    exact = [n for n, v in variants.items() if v["comparison"]["exact_reproduction"]]
    result = {
        "scope": SCOPE,
        "seed": SEED,
        "numpy": np.__version__,
        "code_digest": code_digest(),
        "tie_rule": declared()["study_2"]["tie_rule"],
        "variants": variants,
        "exact_variants": exact,
        "verdict": "EXACT_REPRODUCTION" if exact else "NOT_EXACT_REPRODUCTION",
        "ordering_note": "two declared orderings; no further ordering was tried",
    }
    return {"digest": write_once(output, result), "verdict": result["verdict"], "exact": exact}
