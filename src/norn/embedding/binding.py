"""Actual trainable frozen-backbone adapters and capacity-matched single-event controls."""

from typing import Any

import numpy as np

from norn.contracts.errors import require
from norn.embedding import attention
from norn.embedding.numerics import Array, array, norm_gradient, normalize

VARIANTS = ("B0", "B1", "B2", "B3", "B4", "S3", "S4")
LEARNED = ("B3", "B4", "S3", "S4")
REVISION = "frozen-e5-adapter-analytic-v1"
DIMENSION, HIDDEN, FACETS = 384, 32, 3


def shapes(variant: str) -> dict[str, tuple[int, ...]]:
    require(variant in LEARNED, "UNSUPPORTED_BINDING_VARIANT")
    if variant.startswith("S"):
        width = 80 if variant == "S3" else 86
        return {
            "head": (DIMENSION, width),
            "bias": (width,),
            "out": (width, DIMENSION),
            "out_bias": (DIMENSION,),
        }
    result = {
        "heads": (FACETS, DIMENSION, HIDDEN),
        "bias": (FACETS, HIDDEN),
        "query": (DIMENSION, HIDDEN),
        "query_bias": (HIDDEN,),
        "out": (HIDDEN, DIMENSION),
        "out_bias": (DIMENSION,),
    }
    if variant == "B4":
        result.update({k: (HIDDEN, HIDDEN) for k in ("aq", "ak", "av", "ao")})
        result["types"] = (FACETS, HIDDEN)
    return result


class BindingModel:
    def __init__(self, variant: str, seed: int = 11, parameters: dict[str, Any] | None = None):
        self.variant = variant
        rng = np.random.default_rng(seed)
        self.parameters = {}
        expected = shapes(variant)
        require(parameters is None or set(parameters) == set(expected), "CHECKPOINT_PARAMETERS")
        for key, shape in expected.items():
            if parameters is not None:
                value = array(parameters[key], shape)
            elif "bias" in key:
                value = np.zeros(shape)
            else:
                scale = (shape[-2] if len(shape) >= 2 else shape[-1]) ** -0.5
                value = rng.normal(0, scale, shape)
            self.parameters[key] = value
        require(self.parameter_bytes <= 2_000_000, "BINDING_PARAMETER_BUDGET")

    @property
    def parameter_count(self) -> int:
        return sum(p.size for p in self.parameters.values())

    @property
    def parameter_bytes(self) -> int:
        return sum(p.nbytes for p in self.parameters.values())

    def forward(
        self, inputs: Array, mask: Array | None = None, *, query: bool = False
    ) -> tuple[Array, dict[str, Any]]:
        p = self.parameters
        require(inputs.ndim in (2, 3) and 0 < len(inputs) <= 1024, "BINDING_BATCH_BUDGET")
        if self.variant.startswith("S"):
            require(inputs.shape[1:] == (DIMENSION,), "BINDING_SHAPE_MISMATCH")
            h = np.tanh(inputs @ p["head"] + p["bias"])
            cache: dict[str, Any] = {"x": inputs, "h": h, "single": True}
            pooled = h
        elif query:
            require(inputs.shape[1:] == (DIMENSION,), "BINDING_SHAPE_MISMATCH")
            h = np.tanh(inputs @ p["query"] + p["query_bias"])
            cache = {"x": inputs, "h": h, "query": True}
            pooled = h
        else:
            require(inputs.shape[1:] == (FACETS, DIMENSION), "BINDING_SHAPE_MISMATCH")
            require(mask is not None and mask.shape == inputs.shape[:2], "BINDING_MASK_SHAPE")
            assert mask is not None
            require(
                bool(((mask == 0) | (mask == 1)).all()) and bool((mask.sum(1) > 0).all()),
                "BINDING_ALL_MISSING_OR_INVALID_MASK",
            )
            h = np.einsum("nfd,fdh->nfh", inputs, p["heads"]) + p["bias"]
            if self.variant == "B4":
                h += p["types"]
            h = np.tanh(h) * mask[:, :, None]
            cache = {"x": inputs, "h": h, "mask": mask}
            fused = h
            if self.variant == "B4":
                fused, cache["attention"] = attention.forward(h, mask, p)
            pooled = (fused * mask[:, :, None]).sum(1) / mask.sum(1, keepdims=True)
        raw = pooled @ p["out"] + p["out_bias"]
        code, norms = normalize(raw)
        cache.update(pooled=pooled, code=code, norms=norms)
        return code, cache

    def backward(self, gradient: Array, cache: dict[str, Any]) -> dict[str, Array]:
        p = self.parameters
        grads = {k: np.zeros_like(v) for k, v in p.items()}
        raw = norm_gradient(gradient, cache["code"], cache["norms"])
        grads["out"] = cache["pooled"].T @ raw
        grads["out_bias"] = raw.sum(0)
        gh = raw @ p["out"].T
        h, x = cache["h"], cache["x"]
        if cache.get("single") or cache.get("query"):
            gh *= 1 - h * h
            name, bias = ("head", "bias") if cache.get("single") else ("query", "query_bias")
            grads[name] = x.T @ gh
            grads[bias] = gh.sum(0)
        else:
            mask = cache["mask"]
            gh = gh[:, None, :] * mask[:, :, None] / mask.sum(1)[:, None, None]
            if self.variant == "B4":
                gh, ag = attention.backward(gh, cache["attention"], p)
                grads.update(ag)
            gh *= (1 - h * h) * mask[:, :, None]
            grads["heads"] = np.einsum("nfd,nfh->fdh", x, gh)
            grads["bias"] = gh.sum(0)
            if self.variant == "B4":
                grads["types"] = gh.sum(0)
        return grads
