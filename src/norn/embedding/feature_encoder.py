"""The pinned real E5 reader with a shared512-token per-input treatment ceiling."""

from typing import TYPE_CHECKING, cast

import numpy as np

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.embedding import binding, late_fusion
from norn.embedding import concatenate as concatenation
from norn.embedding.assets import fingerprint
from norn.embedding.binding import LEARNED, VARIANTS, BindingModel
from norn.embedding.concatenate import encode as concatenate
from norn.embedding.concatenate import facets
from norn.embedding.numerics import Array, array
from norn.embedding.query import encode as query_code
from norn.features.views import FACETS, Views

if TYPE_CHECKING:
    from norn.integration.engine import Engine

REVISION = "e5-binding-total512-f32-code384-v1"


class FeatureEncoder:
    def __init__(self, engine: Engine, budget: QueryBudget):
        require(
            engine.local_models is not None and engine.evidence_tokenizer is not None,
            "LOCAL_MODELS_NOT_ENABLED",
        )
        self.engine, self.budget = engine, budget

    def texts(self, texts: tuple[str, ...], *, query: bool = False) -> Array:
        require(0 < len(texts) <= 3, "BINDING_FACET_BUDGET")
        tokenizer = self.engine.evidence_tokenizer
        models = self.engine.local_models
        assert tokenizer is not None and models is not None
        prefix = "query: " if query else "passage: "
        allocation = 512 // len(texts)
        inputs = []
        for text in texts:
            self.budget.checkpoint()
            require(type(text) is str and bool(text), "BINDING_EMPTY_INPUT")
            original = text
            text = text[:16_000]
            if tokenizer.count(prefix + text) > allocation:
                low, high = 0, len(text)
                while low < high:
                    self.budget.checkpoint()
                    middle = (low + high + 1) // 2
                    if tokenizer.count(prefix + text[:middle]) <= allocation:
                        low = middle
                    else:
                        high = middle - 1
                text = text[:low]
            require(
                bool(text) and tokenizer.count(prefix + text) <= allocation, "BINDING_TOKEN_BUDGET"
            )
            self.budget.model_truncated |= text != original
            inputs.append(prefix + text)
        used = sum(tokenizer.count(text) for text in inputs)
        require(used <= 512, "BINDING_TOKEN_BUDGET")
        result = array(models.infer("encoder", tuple(inputs), self.budget), (len(texts), 384))
        require(
            bool(np.allclose(np.linalg.norm(result, axis=1), 1, atol=1e-4)), "INVALID_VECTOR_NORM"
        )
        return result

    def memory(self, views: Views, variant: str, model: BindingModel | None = None) -> Array:
        require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
        if variant == "B0" or variant.startswith("S"):
            inputs = self.texts((views.single_text,))
            return cast(
                Array, inputs[0] if variant == "B0" else self._learned(model, variant, inputs)[0]
            )
        present = tuple(t for t in views.texts if t is not None)
        encoded = self.texts(present)
        inputs = np.zeros((1, len(FACETS), 384))
        inputs[0, np.array(views.mask)] = encoded
        mask = np.asarray([views.mask], dtype=np.float64)
        if variant == "B1":
            return cast(Array, facets(inputs, mask)[0].reshape(384))
        if variant == "B2":
            return cast(Array, concatenate(inputs, mask)[0])
        return cast(Array, self._learned(model, variant, inputs, mask)[0])

    def query(self, text: str, variant: str, model: BindingModel | None = None) -> Array:
        require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
        inputs = self.texts((text,), query=True)
        return query_code(inputs, variant, model)

    @staticmethod
    def _learned(
        model: BindingModel | None,
        variant: str,
        inputs: Array,
        mask: Array | None = None,
    ) -> Array:
        require(model is not None and model.variant == variant, "BINDING_CHECKPOINT_REQUIRED")
        assert model is not None
        return model.forward(inputs, mask)[0]


def method(variant: str, checkpoint_digest: str) -> str:
    from norn.contracts.identity import canonical, digest
    from norn.features.views import REVISION as FEATURES

    require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
    return digest(
        canonical(
            (
                REVISION,
                FEATURES,
                fingerprint("encoder"),
                variant,
                checkpoint_digest,
                FACETS,
                concatenation.REVISION,
                concatenation.PROJECTION_SEED,
                concatenation.INPUT_DIMENSION,
                concatenation.FACET_DIMENSION,
                concatenation.WEIGHTS,
                "SQRT_RENORMALIZED_PRESENT_WEIGHTS;COSINE;F32_STORAGE",
                late_fusion.REVISION,
                late_fusion.RRF_K,
                late_fusion.DEPTH,
                binding.REVISION,
                binding.shapes(variant) if variant in LEARNED else None,
            )
        ).encode()
    )
