"""Bounded float64 adapter training math; inference codes are normalized float32."""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from norn.contracts.errors import require

Array = NDArray[np.float64]
MAX_ARRAY_BYTES = 512 * 1024 * 1024


def array(value: Any, shape: tuple[int, ...] | None = None) -> Array:
    result = np.asarray(value, dtype=np.float64)
    require(
        result.nbytes <= MAX_ARRAY_BYTES and bool(np.isfinite(result).all()),
        "BINDING_ARRAY_BUDGET_OR_NONFINITE",
    )
    require(shape is None or result.shape == shape, "BINDING_SHAPE_MISMATCH")
    return result


def normalize(value: Array) -> tuple[Array, Array]:
    norms = np.linalg.norm(value, axis=-1, keepdims=True)
    require(bool((norms > 1e-12).all()), "BINDING_ZERO_CODE")
    return value / norms, norms


def norm_gradient(gradient: Array, code: Array, norms: Array) -> Array:
    return (gradient - code * np.sum(gradient * code, axis=-1, keepdims=True)) / norms


def softmax(value: Array) -> Array:
    exp = np.exp(value - value.max(axis=-1, keepdims=True))
    return exp / exp.sum(axis=-1, keepdims=True)


def contrastive(
    q: Array,
    m: Array,
    positive: NDArray[np.bool_],
    allowed: NDArray[np.bool_],
    temperature: float = 0.1,
) -> tuple[float, Array, Array]:
    require(q.ndim == m.ndim == 2 and q.shape[1] == m.shape[1], "BINDING_SHAPE_MISMATCH")
    require(positive.shape == allowed.shape == (len(q), len(m)), "BINDING_LABEL_SHAPE")
    require(0 < temperature <= 1 and bool(positive.any(axis=1).all()), "BINDING_POSITIVE_MISSING")
    require(not bool((positive & ~allowed).any()), "BINDING_INELIGIBLE_POSITIVE")
    score = q @ m.T / temperature
    all_score = np.where(allowed, score, -1e30)
    pos_score = np.where(positive, score, -1e30)
    all_max, pos_max = all_score.max(axis=1), pos_score.max(axis=1)
    loss = np.mean(
        all_max
        + np.log(np.exp(all_score - all_max[:, None]).sum(axis=1))
        - pos_max
        - np.log(np.exp(pos_score - pos_max[:, None]).sum(axis=1))
    )
    derivative = (softmax(all_score) - softmax(pos_score)) / (len(q) * temperature)
    return float(loss), derivative @ m, derivative.T @ q
