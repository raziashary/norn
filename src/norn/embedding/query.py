"""Explicit cue-to-shared-code reader, using the genuinely trained query path."""

from typing import cast

import numpy as np

from norn.contracts.errors import require
from norn.embedding.binding import VARIANTS, BindingModel
from norn.embedding.concatenate import encode as concatenate
from norn.embedding.concatenate import facets
from norn.embedding.numerics import Array, array


def encode(cues: Array, variant: str, model: BindingModel | None = None) -> Array:
    require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
    cues = array(cues, (1, 384))
    if variant == "B0":
        return cast(Array, cues[0])
    if variant in ("B1", "B2"):
        repeated = np.repeat(cues[:, None, :], 3, axis=1)
        mask = np.ones((1, 3))
        return cast(
            Array,
            facets(repeated, mask)[0].reshape(384)
            if variant == "B1"
            else concatenate(repeated, mask)[0],
        )
    require(model is not None and model.variant == variant, "BINDING_CHECKPOINT_REQUIRED")
    assert model is not None
    return cast(Array, model.forward(cues, query=True)[0][0])
