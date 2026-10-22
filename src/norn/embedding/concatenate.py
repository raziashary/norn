"""B2: fixed metric, masked normalized facets and prespecified weights/order."""

import numpy as np

from norn.contracts.errors import require
from norn.embedding.numerics import Array, normalize

REVISION = "three-facet-orthogonal128-weighted-concat-v1"
WEIGHTS = (1 / 3, 1 / 3, 1 / 3)
PROJECTION_SEED = 20261021
INPUT_DIMENSION, FACET_DIMENSION = 384, 128


def projection() -> Array:
    # Fixed, shared across facets/arms; this is not learned alignment.
    return np.linalg.qr(
        np.random.default_rng(PROJECTION_SEED).normal(size=(INPUT_DIMENSION, FACET_DIMENSION))
    )[0]


def facets(inputs: Array, mask: Array) -> Array:
    require(inputs.ndim == 3 and inputs.shape[1:] == (3, 384), "BINDING_SHAPE_MISMATCH")
    require(
        mask.shape == inputs.shape[:2] and bool(((mask == 0) | (mask == 1)).all()),
        "BINDING_MASK_SHAPE",
    )
    require(bool((mask.sum(1) > 0).all()), "BINDING_ALL_MISSING_OR_INVALID_MASK")
    projected = inputs @ projection()
    norms = np.linalg.norm(projected, axis=-1, keepdims=True)
    require(bool((norms[mask > 0] > 1e-12).all()), "BINDING_ZERO_CODE")
    return projected / np.maximum(norms, 1e-12) * mask[:, :, None]


def encode(inputs: Array, mask: Array) -> Array:
    value = facets(inputs, mask)
    weights = np.asarray(WEIGHTS)[None, :] * mask
    weights /= weights.sum(1, keepdims=True)
    return normalize((value * np.sqrt(weights[:, :, None])).reshape(len(inputs), 384))[0]
