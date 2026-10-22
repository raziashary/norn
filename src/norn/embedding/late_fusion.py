"""B1: separate facet ranks, fixed weights/depth and one bounded final pool."""

import numpy as np

from norn.contracts.errors import require
from norn.embedding.concatenate import WEIGHTS
from norn.embedding.numerics import Array

REVISION = "facet-weighted-rrf60-v1"
RRF_K = 60
DEPTH = "REQUEST_CANDIDATE_LIMIT_PER_FACET_AND_FINAL_POOL"


def scores(query: Array, memories: Array, mask: Array, keys: tuple[str, ...], limit: int) -> Array:
    require(
        query.shape == (3, 128) and memories.shape == (len(keys), 3, 128), "BINDING_SHAPE_MISMATCH"
    )
    require(mask.shape == (len(keys), 3) and 1 <= limit <= 1000, "BINDING_MASK_SHAPE")
    require(len(keys) == len(set(keys)), "BINDING_DUPLICATE_ID")
    result = np.zeros(len(keys))
    for f, weight in enumerate(WEIGHTS):
        present = [i for i in range(len(keys)) if mask[i, f] > 0]
        ranked = sorted(present, key=lambda i: (-float(memories[i, f] @ query[f]), keys[i]))[:limit]
        for rank, index in enumerate(ranked, 1):
            result[index] += weight / (RRF_K + rank)
    return result
