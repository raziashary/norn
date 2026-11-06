"""Separate, checked training objectives for the P05 loss factorial (blueprint 9.1-9.3).

Each term returns its own value and gradients so that a trainer can sum them and a diagnostic can
compare them (gradient cosines, scale normalisation). Raw values of different objectives are not
comparable and are never used to choose a variant (blueprint 9.4).

* retrieval L1: multi-positive InfoNCE over an explicitly *allowed* candidate set (the maths is
  ``numerics.contrastive``; this module only adds the checked wrapper);
* reconstruction L2: masked, per-facet scaled squared error of linear decoders onto the frozen
  facet features (the targets are stop-gradient constants);
* separation L3: hinge ``max(0, mu + s(a, n) - s(a, p))`` over (anchor, same-episode positive,
  confusable negative) index triples, a ranking between identity-labelled episodes;
* sparsity (exploratory): mean L1 norm of the codes, allowed only next to a signal that
  prevents trivial collapse.
"""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from norn.contracts.errors import require
from norn.embedding.numerics import Array, contrastive

TERMS = ("retrieval", "reconstruction", "separation", "sparsity")
MAX_TRIPLES = 4096


@dataclass(frozen=True)
class Term:
    """One objective: its value and gradients keyed by ``query_codes``, ``memory_codes``, ..."""

    name: str
    value: float
    gradients: dict[str, Array] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require(self.name in TERMS and bool(np.isfinite(self.value)), "LOSS_TERM_INVALID")
        require(all(bool(np.isfinite(g).all()) for g in self.gradients.values()), "LOSS_NONFINITE")


@dataclass(frozen=True)
class Decoder:
    """Per-facet linear decoders ``D_r(z) = z @ weights[r] + bias[r]`` (training-time only)."""

    weights: Array  # (facets, code dimension, target dimension)
    bias: Array  # (facets, target dimension)

    def __post_init__(self) -> None:
        require(
            self.weights.ndim == 3
            and self.bias.shape == (self.weights.shape[0], self.weights.shape[2])
            and bool(np.isfinite(self.weights).all() and np.isfinite(self.bias).all()),
            "DECODER_INVALID",
        )

    @classmethod
    def create(cls, facets: int, code_dimension: int, target_dimension: int, seed: int) -> Decoder:
        require(
            type(seed) is int
            and 0 <= seed < 2**32
            and all(type(v) is int and 0 < v <= 4096 for v in (facets, code_dimension))
            and type(target_dimension) is int
            and 0 < target_dimension <= 4096,
            "DECODER_INVALID",
        )
        rng = np.random.default_rng(seed)
        scale = code_dimension**-0.5
        return cls(
            rng.normal(0, scale, (facets, code_dimension, target_dimension)),
            np.zeros((facets, target_dimension)),
        )


def retrieval_term(
    queries: Array,
    memories: Array,
    positive: NDArray[np.bool_],
    allowed: NDArray[np.bool_],
    temperature: float = 0.1,
) -> Term:
    """Multi-positive contrastive loss; alternative valid evidence is never a negative."""
    require(0 < temperature <= 1 and bool(np.isfinite(temperature)), "LOSS_TEMPERATURE_INVALID")
    for code in (queries, memories):
        require(code.ndim == 2 and bool(np.isfinite(code).all()), "LOSS_CODES_INVALID")
        require(
            bool(np.allclose(np.linalg.norm(code, axis=1), 1.0, atol=1e-6)),
            "LOSS_CODES_NOT_UNIT",
        )
    value, dq, dm = contrastive(queries, memories, positive, allowed, temperature)
    return Term("retrieval", value, {"query_codes": dq, "memory_codes": dm})


def facet_scales(targets: Array, mask: Array) -> Array:
    """``1 / mean squared norm`` of each facet over its valid rows (0 for an unobserved facet)."""
    require(
        targets.ndim == 3 and mask.shape == targets.shape[:2] and bool(np.isfinite(targets).all()),
        "RECONSTRUCTION_TARGET_INVALID",
    )
    require(bool(((mask == 0) | (mask == 1)).all()), "RECONSTRUCTION_MASK_INVALID")
    require(bool(mask.sum() > 0), "RECONSTRUCTION_TARGET_MISSING")
    square = (targets**2).sum(axis=2) * mask
    count = mask.sum(axis=0)
    mean_square = np.divide(square.sum(axis=0), count, out=np.zeros(len(count)), where=count > 0)
    observed = count > 0
    require(bool((mean_square[observed] > 1e-12).all()), "RECONSTRUCTION_TARGET_ZERO")
    scales = np.zeros(len(count))
    scales[observed] = 1.0 / mean_square[observed]
    return scales


def reconstruction_term(codes: Array, targets: Array, mask: Array, decoder: Decoder) -> Term:
    """Masked scaled reconstruction. A masked facet contributes neither loss nor gradient."""
    require(
        codes.ndim == 2 and bool(np.isfinite(codes).all()) and len(codes) == len(targets),
        "LOSS_CODES_INVALID",
    )
    require(
        decoder.weights.shape[0] == targets.shape[1]
        and decoder.weights.shape[1] == codes.shape[1]
        and decoder.weights.shape[2] == targets.shape[2],
        "DECODER_SHAPE_MISMATCH",
    )
    scales = facet_scales(targets, mask)
    predicted = np.einsum("nd,fdt->nft", codes, decoder.weights) + decoder.bias
    error = (predicted - targets) * mask[:, :, None]
    count = float(mask.sum())
    value = float((scales[None, :] * (error**2).sum(axis=2)).sum() / count)
    d_predicted = 2.0 * error * scales[None, :, None] / count
    return Term(
        "reconstruction",
        value,
        {
            "memory_codes": np.einsum("nft,fdt->nd", d_predicted, decoder.weights),
            "decoder": np.einsum("nd,nft->fdt", codes, d_predicted),
            "decoder_bias": d_predicted.sum(axis=0),
        },
    )


def separation_term(codes: Array, triples: NDArray[np.int64], margin: float) -> Term:
    """Mean hinge over (anchor, same-episode positive, confusable negative) rows of ``codes``."""
    require(
        codes.ndim == 2 and bool(np.isfinite(codes).all()) and bool(len(codes) > 0),
        "LOSS_CODES_INVALID",
    )
    require(np.isfinite(margin) and 0 < margin <= 2, "SEPARATION_MARGIN_INVALID")
    require(
        triples.ndim == 2
        and triples.shape[1] == 3
        and 0 < len(triples) <= MAX_TRIPLES
        and bool(((triples >= 0) & (triples < len(codes))).all()),
        "SEPARATION_TARGET_MISSING",
    )
    a, p, n = triples[:, 0], triples[:, 1], triples[:, 2]
    require(not bool(((a == p) | (a == n) | (p == n)).any()), "SEPARATION_TRIPLE_NOT_DISTINCT")
    s_pos = (codes[a] * codes[p]).sum(axis=1)
    s_neg = (codes[a] * codes[n]).sum(axis=1)
    hinge = margin + s_neg - s_pos
    active = (hinge > 0).astype(np.float64)[:, None]
    scale = 1.0 / len(triples)
    gradient = np.zeros_like(codes)
    np.add.at(gradient, a, scale * active * (codes[n] - codes[p]))
    np.add.at(gradient, p, -scale * active * codes[a])
    np.add.at(gradient, n, scale * active * codes[a])
    return Term("separation", float(np.maximum(hinge, 0.0).mean()), {"memory_codes": gradient})


def sparsity_term(codes: Array) -> Term:
    """Mean L1 norm of the codes (subgradient ``sign``). Meaningful only with a collapse guard."""
    require(codes.ndim == 2 and bool(np.isfinite(codes).all()), "LOSS_CODES_INVALID")
    return Term(
        "sparsity",
        float(np.abs(codes).sum(axis=1).mean()),
        {"memory_codes": np.sign(codes) / len(codes)},
    )


@dataclass(frozen=True)
class ObjectiveWeights:
    retrieval: float = 0.0
    reconstruction: float = 0.0
    separation: float = 0.0
    sparsity: float = 0.0

    def __post_init__(self) -> None:
        values = (self.retrieval, self.reconstruction, self.separation, self.sparsity)
        require(
            all(type(v) in (int, float) and np.isfinite(v) and v >= 0 for v in values),
            "OBJECTIVE_WEIGHT_INVALID",
        )
        # A sparsity penalty alone is minimised by a degenerate code, so it needs a signal that
        # keeps information (retrieval or reconstruction), not just another ranking term.
        require(
            self.sparsity == 0 or self.retrieval > 0 or self.reconstruction > 0,
            "COLLAPSE_ONLY_REGULARIZER",
        )

    @property
    def trained(self) -> bool:
        return any(v > 0 for v in (self.retrieval, self.reconstruction, self.separation))

    def active(self) -> tuple[str, ...]:
        return tuple(name for name in TERMS if getattr(self, name) > 0)


# Blueprint 9.2: the factorial arms. T0 is the frozen encoder baseline and trains nothing.
ARM_FLAGS = {
    "T0": (0, 0, 0),
    "T1": (1, 0, 0),
    "T2": (0, 1, 0),
    "T3": (0, 0, 1),
    "T4": (1, 1, 0),
    "T5": (1, 0, 1),
    "T6": (0, 1, 1),
    "T7": (1, 1, 1),
}


def arm_weights(arm: str, *, lam_rec: float = 1.0, lam_sep: float = 1.0) -> ObjectiveWeights:
    require(arm in ARM_FLAGS, "LOSS_ARM_UNKNOWN")
    retrieval, reconstruction, separation = ARM_FLAGS[arm]
    return ObjectiveWeights(float(retrieval), lam_rec * reconstruction, lam_sep * separation)


@dataclass(frozen=True)
class Combined:
    value: float
    gradients: dict[str, Array]
    parts: dict[str, Term]  # each active term unweighted, for diagnostics
    weights: dict[str, float]  # the effective weight (weight / reference scale) per term


def combine(
    terms: dict[str, Term],
    weights: ObjectiveWeights,
    reference: dict[str, float] | None = None,
) -> Combined:
    """Weighted sum of the active terms with their gradients kept separable by ``parts``.

    ``reference`` holds each active term's value at initialisation; dividing by it normalises
    the loss scales before a weight sweep (blueprint 9.2). Without it the raw weights apply.
    """
    require(weights.trained, "OBJECTIVE_EMPTY")
    active = weights.active()
    require(set(terms) == set(active), "OBJECTIVE_TERMS_MISMATCH")
    effective: dict[str, float] = {}
    for name in active:
        scale = 1.0 if reference is None else reference.get(name, 0.0)
        require(bool(np.isfinite(scale)) and scale > 0, "OBJECTIVE_REFERENCE_INVALID")
        effective[name] = getattr(weights, name) / scale
    value = sum(effective[n] * terms[n].value for n in active)
    gradients: dict[str, Array] = {}
    for name in active:
        for key, gradient in terms[name].gradients.items():
            gradients[key] = gradients.get(key, 0.0) + effective[name] * gradient
    return Combined(float(value), gradients, {n: terms[n] for n in active}, effective)
