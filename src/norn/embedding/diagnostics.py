"""Training diagnostics (blueprint 9.4): objective gradients, their conflict, code collapse.

Every quantity here is an observation about training, never a selection criterion. A gradient
that cannot be computed or compared is reported as missing with its reason; absence of a
measurement is not evidence of agreement between objectives.
"""

from typing import Any

import numpy as np

from norn.contracts.errors import NornError, require
from norn.embedding.binding import BindingModel
from norn.embedding.losses import ObjectiveWeights
from norn.embedding.numerics import Array, effective_rank
from norn.embedding.training import FactorialBatch, factorial_objective

OBJECTIVES = ("retrieval", "reconstruction", "separation")
# Diagnostic flags, not performance margins (R09 margins stay with the owner).
COLLAPSE_COSINE = 0.95
COLLAPSE_RANK = 1.5
DECODER_KEYS = ("decoder.weights", "decoder.bias")


def term_gradients(
    model: BindingModel,
    decoder: Any,
    batch: FactorialBatch,
    reference: dict[str, float] | None = None,
    *,
    temperature: float = 0.1,
    margin: float = 0.2,
) -> tuple[dict[str, dict[str, Array]], dict[str, str]]:
    """Each objective's model-parameter gradient on one batch, plus the ones that are missing."""
    found: dict[str, dict[str, Array]] = {}
    missing: dict[str, str] = {}
    for name in OBJECTIVES:
        weights = ObjectiveWeights(**{name: 1.0})
        require(reference is None or name in reference, "DIAGNOSTIC_REFERENCE_MISSING")
        scale = None if reference is None else {name: reference[name]}
        try:
            _, grads = factorial_objective(
                model, decoder, batch, weights, scale, temperature=temperature, margin=margin
            )
        except NornError as error:
            missing[name] = error.code
            continue
        found[name] = {k: g for k, g in grads.items() if k not in DECODER_KEYS}
    return found, missing


def _norm(grads: dict[str, Array], keys: list[str]) -> float:
    return float(np.sqrt(sum(float(np.sum(grads[k] ** 2)) for k in keys)))


def conflict(
    gradients: dict[str, dict[str, Array]], missing: dict[str, str] | None = None
) -> dict[str, Any]:
    """Norms and pairwise cosines over the parameters both objectives actually reach.

    ``conflicting`` is True for a negative cosine, False for a non-negative one and None when
    the cosine is undefined (no shared parameter or a zero gradient): never False by default.
    """
    require(bool(gradients) or bool(missing), "DIAGNOSTIC_EMPTY")
    norms = {
        name: _norm(grads, [k for k in grads if np.any(grads[k])])
        for name, grads in gradients.items()
    }
    pairs: dict[str, Any] = {}
    names = sorted(gradients)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            shared = [
                k
                for k in gradients[left]
                if k in gradients[right]
                and np.any(gradients[left][k])
                and np.any(gradients[right][k])
            ]
            a = _norm(gradients[left], shared)
            b = _norm(gradients[right], shared)
            if not shared or a < 1e-12 or b < 1e-12:
                pairs[f"{left}|{right}"] = {
                    "cosine": None,
                    "conflicting": None,
                    "shared": sorted(shared),
                    "reason": "NO_SHARED_NONZERO_PARAMETERS",
                }
                continue
            dot = sum(float(np.sum(gradients[left][k] * gradients[right][k])) for k in shared)
            cosine = dot / (a * b)
            pairs[f"{left}|{right}"] = {
                "cosine": cosine,
                "conflicting": cosine < 0,
                "shared": sorted(shared),
                "norm_ratio": max(a, b) / min(a, b),
            }
    return {"norms": norms, "pairs": pairs, "missing": dict(missing or {})}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-batch conflicts with explicit denominators (undefined batches are counted)."""
    result: dict[str, Any] = {}
    keys = sorted({k for row in rows for k in row["pairs"]})
    for key in keys:
        values = [row["pairs"][key]["cosine"] for row in rows if key in row["pairs"]]
        defined = [v for v in values if v is not None]
        result[key] = {
            "batches": len(values),
            "defined": len(defined),
            "mean_cosine": float(np.mean(defined)) if defined else None,
            "min_cosine": float(np.min(defined)) if defined else None,
            "negative_fraction": float(np.mean([v < 0 for v in defined])) if defined else None,
        }
    missing: dict[str, int] = {}
    for row in rows:
        for name in row["missing"]:
            missing[name] = missing.get(name, 0) + 1
    result["missing_objective_batches"] = missing
    return result


def code_stats(codes: Array, raw_norms: Array) -> dict[str, Any]:
    """Effective rank, mean off-diagonal cosine and pre-normalisation norm distribution."""
    require(codes.ndim == 2 and len(codes) >= 2 and bool(np.isfinite(codes).all()), "CODES_INVALID")
    n = len(codes)
    unit = codes / np.maximum(np.linalg.norm(codes, axis=1, keepdims=True), 1e-12)
    gram = unit @ unit.T
    mean_cosine = float((gram.sum() - np.trace(gram)) / (n * (n - 1)))
    rank = effective_rank(codes)
    flat = np.asarray(raw_norms, dtype=float).reshape(-1)
    return {
        "count": n,
        "effective_rank": rank,
        "rank_fraction": rank / min(n, codes.shape[1]),
        "mean_pairwise_cosine": mean_cosine,
        "raw_norm_min": float(flat.min()),
        "raw_norm_median": float(np.median(flat)),
        "raw_norm_max": float(flat.max()),
        "collapsed": mean_cosine > COLLAPSE_COSINE or rank < COLLAPSE_RANK,
    }


def model_code_stats(model: BindingModel, batch: FactorialBatch) -> dict[str, Any]:
    inputs = batch.single if model.variant.startswith("S") else batch.facets
    codes, cache = model.forward(inputs, batch.mask)
    return code_stats(codes, cache["norms"])


class Trace:
    """Training observer: conflict and code statistics every ``every`` updates, read-only."""

    def __init__(self, every: int, *, temperature: float = 0.1, margin: float = 0.2) -> None:
        require(type(every) is int and every >= 1, "TRACE_INTERVAL")
        self.every, self.temperature, self.margin = every, temperature, margin
        self.rows: list[dict[str, Any]] = []

    def __call__(
        self,
        update: int,
        model: BindingModel,
        decoder: Any,
        batch: FactorialBatch,
        reference: dict[str, float],
    ) -> None:
        if (update - 1) % self.every:
            return
        found, missing = term_gradients(
            model, decoder, batch, reference, temperature=self.temperature, margin=self.margin
        )
        row = conflict(found, missing) if (found or missing) else {}
        row.update(update=update, codes=model_code_stats(model, batch))
        self.rows.append(row)
