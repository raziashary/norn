"""Explicit, bounded multi-positive training of small adapters on a frozen backbone."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from norn.contracts.errors import require
from norn.embedding.binding import BindingModel
from norn.embedding.losses import (
    MAX_TRIPLES,
    Combined,
    Decoder,
    ObjectiveWeights,
    Term,
    combine,
    reconstruction_term,
    retrieval_term,
    separation_term,
    sparsity_term,
)
from norn.embedding.numerics import MAX_ARRAY_BYTES, Array, contrastive
from norn.telemetry.resources import memory


@dataclass(frozen=True)
class TrainingBatch:
    queries: Array
    facets: Array
    single: Array
    mask: Array
    positive: NDArray[np.bool_]
    allowed: NDArray[np.bool_]

    def validate(self) -> None:
        q, m = len(self.queries), len(self.facets)
        require(0 < q <= 32 and 0 < m <= 512, "TRAINING_BATCH_BUDGET")
        require(
            self.queries.shape == (q, 384)
            and self.facets.shape == (m, 3, 384)
            and self.single.shape == (m, 384)
            and self.mask.shape == (m, 3),
            "BINDING_SHAPE_MISMATCH",
        )
        require(
            self.positive.shape == self.allowed.shape == (q, m)
            and self.positive.dtype == self.allowed.dtype == np.bool_,
            "BINDING_LABEL_SHAPE",
        )
        require(
            all(
                bool(np.isfinite(v).all())
                for v in (self.queries, self.facets, self.single, self.mask)
            ),
            "TRAINING_NONFINITE",
        )
        require(
            bool(((self.mask == 0) | (self.mask == 1)).all())
            and bool((self.mask.sum(1) > 0).all()),
            "BINDING_ALL_MISSING_OR_INVALID_MASK",
        )
        require(
            bool(self.positive.any(1).all()) and not bool((self.positive & ~self.allowed).any()),
            "BINDING_POSITIVE_MISSING",
        )


def objective(model: BindingModel, batch: TrainingBatch) -> tuple[float, dict[str, Array]]:
    batch.validate()
    inputs = batch.single if model.variant.startswith("S") else batch.facets
    memory, mc = model.forward(inputs, batch.mask)
    query, qc = model.forward(batch.queries, query=True)
    loss, dq, dm = contrastive(query, memory, batch.positive, batch.allowed)
    mg, qg = model.backward(dm, mc), model.backward(dq, qc)
    return loss, {k: mg[k] + qg[k] for k in model.parameters}


Step = Callable[[Any], tuple[float, dict[str, Array], dict[str, float]]]


def _envelope(
    batches: tuple[TrainingBatch, ...],
    parameter_bytes: int,
    *,
    seed: int,
    updates: int,
    seconds: float,
    learning_rate: float,
) -> int:
    require(
        type(seed) is int and 0 <= seed < 2**32 and type(updates) is int and 1 <= updates <= 200,
        "TRAINING_ENVELOPE",
    )
    require(
        0 < seconds <= 1200 and 0 < learning_rate <= 0.01 and 0 < len(batches) <= 512,
        "TRAINING_ENVELOPE",
    )
    for batch in batches:
        batch.validate()
    # Deliberate conservative bound includes resident inputs and temporary work,
    # parameters, both Adam states, gradients and forward/reverse caches.
    input_bytes = sum(
        v.nbytes
        for b in batches
        for v in (b.queries, b.facets, b.single, b.mask, b.positive, b.allowed)
    )
    bound = input_bytes * 16 + parameter_bytes * 20
    require(bound <= MAX_ARRAY_BYTES, "TRAINING_ARRAY_BUDGET")
    return bound


def _fit(
    parameters: dict[str, Array],
    batches: tuple[Any, ...],
    step: Step,
    *,
    seed: int,
    updates: int,
    seconds: float,
    aggregate_deadline: float | None,
    learning_rate: float,
    now: Callable[[], float],
) -> dict[str, Any]:
    """The one clipped-Adam loop, shared so every objective is optimised identically."""
    started = now()
    deadline = min(started + seconds, aggregate_deadline or started + 7200)
    rng = np.random.default_rng(seed)
    first, second = ({k: np.zeros_like(v) for k, v in parameters.items()} for _ in range(2))
    losses: list[float] = []
    parts: list[dict[str, float]] = []
    initial = {k: v.copy() for k, v in parameters.items()}
    nonzero_steps = 0
    process_before = memory()
    for index in range(1, updates + 1):
        require(now() < deadline, "TRAINING_DEADLINE")
        batch = batches[int(rng.integers(len(batches)))]
        loss, grads, terms = step(batch)
        require(
            np.isfinite(loss) and all(bool(np.isfinite(g).all()) for g in grads.values()),
            "TRAINING_NONFINITE",
        )
        size = np.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
        nonzero_steps += int(size > 1e-12)
        scale = min(1.0, 1.0 / max(size, 1e-12))
        for key, value in parameters.items():
            g = grads[key] * scale
            first[key] = 0.9 * first[key] + 0.1 * g
            second[key] = 0.999 * second[key] + 0.001 * g * g
            value -= (
                learning_rate
                * (first[key] / (1 - 0.9**index))
                / (np.sqrt(second[key] / (1 - 0.999**index)) + 1e-8)
            )
        require(now() < deadline, "TRAINING_DEADLINE")
        losses.append(loss)
        parts.append(terms)
    return {
        "losses": losses,
        "parts": parts,
        "nonzero_steps": nonzero_steps,
        "elapsed": now() - started,
        "delta": float(
            np.sqrt(sum(float(np.sum((v - initial[k]) ** 2)) for k, v in parameters.items()))
        ),
        "process_before": process_before,
    }


def _code_rank(codes: Array) -> float:
    singular = np.linalg.svd(codes, compute_uv=False)
    probabilities = singular / max(float(singular.sum()), 1e-12)
    return float(np.exp(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-12)))))


def train(
    model: BindingModel,
    batches: tuple[TrainingBatch, ...],
    *,
    seed: int,
    updates: int = 200,
    seconds: float = 1200,
    aggregate_deadline: float | None = None,
    learning_rate: float = 0.003,
    now: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    bound = _envelope(
        batches,
        model.parameter_bytes,
        seed=seed,
        updates=updates,
        seconds=seconds,
        learning_rate=learning_rate,
    )

    def step(batch: Any) -> tuple[float, dict[str, Array], dict[str, float]]:
        loss, grads = objective(model, batch)
        return loss, grads, {}

    fit = _fit(
        model.parameters,
        batches,
        step,
        seed=seed,
        updates=updates,
        seconds=seconds,
        aggregate_deadline=aggregate_deadline,
        learning_rate=learning_rate,
        now=now,
    )
    sample = batches[0]
    codes = model.forward(
        sample.single if model.variant.startswith("S") else sample.facets, sample.mask
    )[0]
    return {
        "seed": seed,
        "updates": updates,
        "losses": fit["losses"],
        "elapsed_seconds": fit["elapsed"],
        "parameters": model.parameter_count,
        "numerical_array_bound_bytes": bound,
        "backbone": "FROZEN",
        "nonzero_gradient_steps": fit["nonzero_steps"],
        "parameter_delta_l2": fit["delta"],
        "sample_code_effective_rank": _code_rank(codes),
        "sample_code_count": len(codes),
        "process_memory_before": fit["process_before"],
        "process_memory_after": memory(),
        "memory_scope": "PARENT_PROCESS_LIFETIME_PEAK; NOT_ISOLATED_TRAINING_OR_WORKER",
        "optimizer": f"Adam-clipped1-lr{learning_rate:g}-v1",
    }


@dataclass(frozen=True)
class FactorialBatch(TrainingBatch):
    """A training batch that also names (anchor, same-episode positive, negative) memory rows."""

    triples: NDArray[np.int64] = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int64))

    def validate(self) -> None:
        super().validate()
        m = len(self.facets)
        require(
            self.triples.ndim == 2
            and self.triples.shape[1] == 3
            and len(self.triples) <= MAX_TRIPLES
            and self.triples.dtype == np.int64
            and bool(((self.triples >= 0) & (self.triples < m)).all()),
            "FACTORIAL_TRIPLES_INVALID",
        )


def _terms(
    model: BindingModel,
    decoder: Decoder,
    batch: FactorialBatch,
    weights: ObjectiveWeights,
    temperature: float,
    margin: float,
) -> tuple[dict[str, Term], dict[str, Any], dict[str, Any]]:
    batch.validate()
    inputs = batch.single if model.variant.startswith("S") else batch.facets
    memory_codes, mc = model.forward(inputs, batch.mask)
    query_codes, qc = model.forward(batch.queries, query=True)
    terms: dict[str, Term] = {}
    if weights.retrieval > 0:
        terms["retrieval"] = retrieval_term(
            query_codes, memory_codes, batch.positive, batch.allowed, temperature
        )
    if weights.reconstruction > 0:
        terms["reconstruction"] = reconstruction_term(
            memory_codes, batch.facets, batch.mask, decoder
        )
    if weights.separation > 0:
        terms["separation"] = separation_term(memory_codes, batch.triples, margin)
    if weights.sparsity > 0:
        terms["sparsity"] = sparsity_term(memory_codes)
    return terms, mc, qc


def factorial_objective(
    model: BindingModel,
    decoder: Decoder,
    batch: FactorialBatch,
    weights: ObjectiveWeights,
    reference: dict[str, float] | None = None,
    *,
    temperature: float = 0.1,
    margin: float = 0.2,
) -> tuple[Combined, dict[str, Array]]:
    """Combined loss and gradients for ``model`` parameters plus ``decoder.weights/bias`` keys.

    The query tower receives gradient only through the retrieval term; the output projection is
    shared by both towers, so without retrieval only the query head stays at initialisation.
    """
    terms, mc, qc = _terms(model, decoder, batch, weights, temperature, margin)
    combined = combine(terms, weights, reference)
    dm = combined.gradients.get("memory_codes")
    dq = combined.gradients.get("query_codes")
    grads = {k: np.zeros_like(v) for k, v in model.parameters.items()}
    if dm is not None:
        for key, g in model.backward(dm, mc).items():
            grads[key] += g
    if dq is not None:
        for key, g in model.backward(dq, qc).items():
            grads[key] += g
    grads["decoder.weights"] = combined.gradients.get("decoder", np.zeros_like(decoder.weights))
    grads["decoder.bias"] = combined.gradients.get("decoder_bias", np.zeros_like(decoder.bias))
    return combined, grads


def reference_scales(
    model: BindingModel,
    decoder: Decoder,
    batches: tuple[FactorialBatch, ...],
    weights: ObjectiveWeights,
    *,
    temperature: float = 0.1,
    margin: float = 0.2,
) -> dict[str, float]:
    """Mean initial value of each active term over every batch (blueprint 9.2 normalisation)."""
    totals = dict.fromkeys(weights.active(), 0.0)
    for batch in batches:
        terms = _terms(model, decoder, batch, weights, temperature, margin)[0]
        for name, term in terms.items():
            totals[name] += term.value / len(batches)
    require(all(v > 1e-9 for v in totals.values()), "OBJECTIVE_REFERENCE_INVALID")
    return totals


def train_arm(
    model: BindingModel,
    decoder: Decoder,
    batches: tuple[FactorialBatch, ...],
    weights: ObjectiveWeights,
    *,
    seed: int,
    updates: int = 200,
    seconds: float = 1200,
    aggregate_deadline: float | None = None,
    learning_rate: float = 0.003,
    temperature: float = 0.1,
    margin: float = 0.2,
    now: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Train one loss-factorial arm with the same optimiser, batches and budget as ``train``."""
    require(weights.trained, "OBJECTIVE_EMPTY")
    bound = _envelope(
        batches,
        model.parameter_bytes + decoder.weights.nbytes + decoder.bias.nbytes,
        seed=seed,
        updates=updates,
        seconds=seconds,
        learning_rate=learning_rate,
    )
    reference = reference_scales(
        model, decoder, batches, weights, temperature=temperature, margin=margin
    )
    parameters = {
        **model.parameters,
        "decoder.weights": decoder.weights,
        "decoder.bias": decoder.bias,
    }

    def step(batch: Any) -> tuple[float, dict[str, Array], dict[str, float]]:
        combined, grads = factorial_objective(
            model, decoder, batch, weights, reference, temperature=temperature, margin=margin
        )
        return combined.value, grads, {n: t.value for n, t in combined.parts.items()}

    fit = _fit(
        parameters,
        batches,
        step,
        seed=seed,
        updates=updates,
        seconds=seconds,
        aggregate_deadline=aggregate_deadline,
        learning_rate=learning_rate,
        now=now,
    )
    sample = batches[0]
    codes = model.forward(
        sample.single if model.variant.startswith("S") else sample.facets, sample.mask
    )[0]
    return {
        "seed": seed,
        "updates": updates,
        "losses": fit["losses"],
        "terms": fit["parts"],
        "reference": reference,
        "weights": dict(weights.__dict__),
        "elapsed_seconds": fit["elapsed"],
        "parameters": model.parameter_count,
        "decoder_parameters": decoder.weights.size + decoder.bias.size,
        "numerical_array_bound_bytes": bound,
        "backbone": "FROZEN",
        "nonzero_gradient_steps": fit["nonzero_steps"],
        "parameter_delta_l2": fit["delta"],
        "sample_code_effective_rank": _code_rank(codes),
        "sample_code_count": len(codes),
        "process_memory_before": fit["process_before"],
        "process_memory_after": memory(),
        "memory_scope": "PARENT_PROCESS_LIFETIME_PEAK; NOT_ISOLATED_TRAINING_OR_WORKER",
        "optimizer": f"Adam-clipped1-lr{learning_rate:g}-v1",
        "temperature": temperature,
        "margin": margin,
    }
