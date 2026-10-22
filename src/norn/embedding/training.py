"""Explicit, bounded multi-positive training of small adapters on a frozen backbone."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from norn.contracts.errors import require
from norn.embedding.binding import BindingModel
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
    require(
        seed in (11, 29, 47) and type(updates) is int and 1 <= updates <= 200, "TRAINING_ENVELOPE"
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
    numerical_bound = input_bytes * 16 + model.parameter_bytes * 20
    require(numerical_bound <= MAX_ARRAY_BYTES, "TRAINING_ARRAY_BUDGET")
    started = now()
    deadline = min(started + seconds, aggregate_deadline or started + 7200)
    rng = np.random.default_rng(seed)
    first, second = ({k: np.zeros_like(v) for k, v in model.parameters.items()} for _ in range(2))
    losses = []
    initial = {k: v.copy() for k, v in model.parameters.items()}
    nonzero_steps = 0
    process_before = memory()
    for step in range(1, updates + 1):
        require(now() < deadline, "TRAINING_DEADLINE")
        batch = batches[int(rng.integers(len(batches)))]
        loss, grads = objective(model, batch)
        require(
            np.isfinite(loss) and all(bool(np.isfinite(g).all()) for g in grads.values()),
            "TRAINING_NONFINITE",
        )
        size = np.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
        nonzero_steps += int(size > 1e-12)
        scale = min(1.0, 1.0 / max(size, 1e-12))
        for key, value in model.parameters.items():
            g = grads[key] * scale
            first[key] = 0.9 * first[key] + 0.1 * g
            second[key] = 0.999 * second[key] + 0.001 * g * g
            value -= (
                learning_rate
                * (first[key] / (1 - 0.9**step))
                / (np.sqrt(second[key] / (1 - 0.999**step)) + 1e-8)
            )
        require(now() < deadline, "TRAINING_DEADLINE")
        losses.append(loss)
    sample = batches[0]
    codes = model.forward(
        sample.single if model.variant.startswith("S") else sample.facets, sample.mask
    )[0]
    singular = np.linalg.svd(codes, compute_uv=False)
    probabilities = singular / max(float(singular.sum()), 1e-12)
    effective_rank = float(
        np.exp(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-12))))
    )
    return {
        "seed": seed,
        "updates": updates,
        "losses": losses,
        "elapsed_seconds": now() - started,
        "parameters": model.parameter_count,
        "numerical_array_bound_bytes": numerical_bound,
        "backbone": "FROZEN",
        "nonzero_gradient_steps": nonzero_steps,
        "parameter_delta_l2": float(
            np.sqrt(sum(float(np.sum((v - initial[k]) ** 2)) for k, v in model.parameters.items()))
        ),
        "sample_code_effective_rank": effective_rank,
        "sample_code_count": len(codes),
        "process_memory_before": process_before,
        "process_memory_after": memory(),
        "memory_scope": "PARENT_PROCESS_LIFETIME_PEAK; NOT_ISOLATED_TRAINING_OR_WORKER",
        "optimizer": f"Adam-clipped1-lr{learning_rate:g}-v1",
    }
