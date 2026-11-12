"""Sparse-support and random-basis geometry over dense 384-coordinate codes (P05-T07).

Pure numerics, no I/O. Every code stays at the 384 development dimension (ADR-0027 Q-A: a larger
dimension needs a new owner answer). Sparsity keeps the k largest-magnitude coordinates; ties keep
the lower index so a sparse code is deterministic. Nothing here claims orthogonalization,
c-to-c^k or Johnson-Lindenstrauss behaviour: it only measures how ranking changes when a code is
sparsified, rotated or randomly projected to a matched byte budget.
"""

from typing import cast

import numpy as np

from norn.contracts.errors import require
from norn.embedding.numerics import Array, array

DIMENSION = 384
MODES = ("binary", "weighted")
SPARSITY_PERCENT = (1, 2, 5, 10, 100)
TIE_TOLERANCE = 1e-12
FLOAT_BYTES, INDEX_BYTES, HALF_BYTES = 4, 2, 2


def sparse_width(percent: int) -> int:
    """Number of kept coordinates: the percentage of 384, at least one."""
    require(percent in SPARSITY_PERCENT, "SEPARATION_SPARSITY")
    return max(1, round(DIMENSION * percent / 100))


def support(codes: Array, k: int) -> Array:
    """Boolean (n, 384) mask of the k largest-magnitude coordinates per row; ties keep low index."""
    codes = array(codes)
    require(codes.ndim == 2 and codes.shape[1] == DIMENSION, "SEPARATION_SHAPE")
    require(1 <= k <= DIMENSION, "SEPARATION_WIDTH")
    order = np.argsort(-np.abs(codes), axis=1, kind="stable")[:, :k]
    mask = np.zeros(codes.shape, dtype=bool)
    np.put_along_axis(mask, order, True, axis=1)
    return cast(Array, mask)


def sparsify(codes: Array, k: int, mode: str) -> Array:
    """Binary support indicator, or the weighted signed top-k renormalized to unit length."""
    require(mode in MODES, "SEPARATION_MODE")
    mask = support(codes, k)
    if mode == "binary":
        return cast(Array, mask.astype(np.float64))
    kept = np.where(mask, codes, 0.0)
    norms = np.linalg.norm(kept, axis=1, keepdims=True)
    require(bool((norms > 1e-12).all()), "SEPARATION_ZERO_CODE")
    return kept / norms


def similarity(query: Array, memories: Array) -> Array:
    """Dot product: the overlap count for binary codes, the cosine for unit weighted codes."""
    query, memories = array(query), array(memories)
    require(
        query.ndim == 1 and memories.ndim == 2 and memories.shape[1] == query.shape[0],
        "SEPARATION_SHAPE",
    )
    return memories @ query


def orthogonal_basis(seed: int) -> Array:
    """Deterministic random rotation of the 384 coordinates (preserves every dense cosine)."""
    gaussian = np.random.default_rng(seed).normal(size=(DIMENSION, DIMENSION))
    q, r = np.linalg.qr(gaussian)
    return q * np.sign(np.diag(r))


def gaussian_projection(seed: int, width: int) -> Array:
    """Dense random projection to ``width`` coordinates for the matched-storage control."""
    require(1 <= width <= DIMENSION, "SEPARATION_WIDTH")
    return np.random.default_rng(seed).normal(0, width**-0.5, (DIMENSION, width))


def project(codes: Array, matrix: Array, *, unit: bool) -> Array:
    out = array(codes) @ matrix
    if not unit:
        return out
    norms = np.linalg.norm(out, axis=-1, keepdims=True)
    require(bool((norms > 1e-12).all()), "SEPARATION_ZERO_CODE")
    return out / norms


def event_bytes(mode: str, k: int) -> int:
    """Stored bytes per event: float32 dense, index plus float16 value (weighted), or index only."""
    require(mode in {"dense", *MODES}, "SEPARATION_MODE")
    if mode == "dense":
        return FLOAT_BYTES * k
    return (INDEX_BYTES + (HALF_BYTES if mode == "weighted" else 0)) * k


def matched_width(bytes_per_event: int) -> int:
    """Dense float32 coordinates that fit the same byte budget (at least one)."""
    return max(1, min(DIMENSION, bytes_per_event // FLOAT_BYTES))


def fuse(semantic: Array, learned: Array, weight: float) -> Array:
    """Fixed convex combination: weight 0 is the semantic score, weight 1 the learned score."""
    require(0.0 <= weight <= 1.0 and semantic.shape == learned.shape, "SEPARATION_FUSION")
    return (1.0 - weight) * semantic + weight * learned
