"""P05-T05: reproduce the blueprint 10.3 sparse-support toy simulation against its declared output.

This measures support overlap of the top-k coordinates of correlated Gaussian vectors. It is not
cosine similarity, not Recall@K and not evidence about real embeddings. The procedure, the three
generator orderings and the tolerances were fixed in the MDP card before this code existed
(`docs/development/evidence/p05_toy_expected.json` holds the declared numbers).
"""

import json
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
from numpy.typing import NDArray

from benchmark.runs.manifest import code_digest, write_once
from norn.contracts.errors import require

EXPECTED = Path(__file__).resolve().parents[2] / "docs/development/evidence/p05_toy_expected.json"
SEED, DIMENSION, PAIRS = 20261019, 2048, 1200
KS = (41, 205)
RHOS = (0.0, 0.3, 0.7, 0.9)
VARIANTS = ("V1", "V2", "V3")
SCOPE = "SUPPORT_OVERLAP_ONLY; NOT_COSINE; NOT_RECALL_AT_K; NOT_REAL_EMBEDDINGS"


def top_k_mask(values: NDArray[np.float64], k: int) -> NDArray[np.bool_]:
    """Boolean support of the ``k`` largest signed coordinates in each row."""
    require(values.ndim == 2 and 0 < k < values.shape[1], "TOY_K_INVALID")
    mask = np.zeros(values.shape, dtype=bool)
    index = np.argpartition(values, -k, axis=1)[:, -k:]
    np.put_along_axis(mask, index, True, axis=1)
    return mask


def overlaps(x: NDArray[np.float64], y: NDArray[np.float64], k: int) -> NDArray[np.float64]:
    """Per-pair shared top-k indices divided by k."""
    return (top_k_mask(x, k) & top_k_mask(y, k)).sum(axis=1) / k


def correlated(x: NDArray[np.float64], eps: NDArray[np.float64], rho: float) -> NDArray[np.float64]:
    return np.asarray(rho * x + np.sqrt(1.0 - rho**2) * eps, dtype=np.float64)


def simulate(variant: str, *, seed: int = SEED, pairs: int = PAIRS) -> dict[tuple[int, float], Any]:
    """Mean overlap and its standard error per ``(k, rho)`` cell for one declared ordering."""
    require(variant in VARIANTS, "TOY_VARIANT_UNKNOWN")
    rng = np.random.default_rng(seed)
    cells: dict[tuple[int, float], Any] = {}

    def record(k: int, rho: float, x: NDArray[np.float64], eps: NDArray[np.float64]) -> None:
        values = overlaps(x, correlated(x, eps, rho), k)
        cells[(k, rho)] = {
            "mean": float(values.mean()),
            "standard_error": float(values.std(ddof=1) / np.sqrt(len(values))),
        }

    def draw() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        return rng.standard_normal((pairs, DIMENSION)), rng.standard_normal((pairs, DIMENSION))

    if variant == "V1":  # k outer, rho inner, fresh draw per cell
        for k in KS:
            for rho in RHOS:
                record(k, rho, *draw())
    elif variant == "V2":  # rho outer, k inner, fresh draw per cell
        for rho in RHOS:
            for k in KS:
                record(k, rho, *draw())
    else:  # V3: one draw per rho shared by both k
        for rho in RHOS:
            x, eps = draw()
            for k in KS:
                record(k, rho, x, eps)
    return cells


def joint_tail_expectation(k: int, rho: float, dimension: int = DIMENSION) -> float:
    """``P(Y in top tail | X in top tail)`` for correlated standard normals (no simulation)."""
    p = k / dimension
    threshold = NormalDist().inv_cdf(1.0 - p)
    if rho == 0.0:
        return p
    grid = np.linspace(threshold, 12.0, 40001)
    density = np.exp(-0.5 * grid**2) / np.sqrt(2.0 * np.pi)
    z = (threshold - rho * grid) / np.sqrt(1.0 - rho**2)
    joint = float(np.trapezoid(density * _survival(z), grid))
    return joint / p


def _survival(z: NDArray[np.float64]) -> NDArray[np.float64]:
    from math import erfc

    return np.array([0.5 * erfc(float(v) / 2**0.5) for v in z])


def declared() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(EXPECTED.read_text(encoding="utf-8"))
    return value


def compare(
    cells: dict[tuple[int, float], Any], expected: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Per-cell deviation from the declared table, exact and 3-standard-error verdicts."""
    study = (expected or declared())["study_1"]
    tolerance = study["exact_reproduction_tolerance"]
    rows = []
    for (k, rho), cell in sorted(cells.items()):
        target = study["mean_support_overlap"][f"k{k}"][str(rho)]
        deviation = cell["mean"] - target
        rows.append(
            {
                "k": k,
                "rho": rho,
                "declared": target,
                "measured": cell["mean"],
                "deviation": deviation,
                "standard_error": cell["standard_error"],
                "exact": abs(deviation) <= tolerance,
                "within_3_se": abs(deviation) <= 3 * cell["standard_error"],
            }
        )
    exact = all(r["exact"] for r in rows)
    return {
        "cells": rows,
        "exact_reproduction": exact,
        "all_within_3_se": all(r["within_3_se"] for r in rows),
        "verdict": "EXACT_REPRODUCTION" if exact else "NOT_EXACT_REPRODUCTION",
    }


def run(output: Path) -> dict[str, Any]:
    variants = {}
    for name in VARIANTS:
        variants[name] = compare(simulate(name))
        print(
            {"stage": "variant", "variant": name, "verdict": variants[name]["verdict"]}, flush=True
        )
    expectation = {f"k{k}": {str(rho): joint_tail_expectation(k, rho) for rho in RHOS} for k in KS}
    exact = [n for n, v in variants.items() if v["exact_reproduction"]]
    result = {
        "scope": SCOPE,
        "seed": SEED,
        "numpy": np.__version__,
        "code_digest": code_digest(),
        "variants": variants,
        "exact_variants": exact,
        "verdict": "EXACT_REPRODUCTION" if exact else "NOT_EXACT_REPRODUCTION",
        "joint_tail_expectation": expectation,
        "declared_table": declared()["study_1"]["mean_support_overlap"],
        "ordering_note": "three declared orderings; no further ordering was tried",
    }
    return {"digest": write_once(output, result), "verdict": result["verdict"], "exact": exact}
