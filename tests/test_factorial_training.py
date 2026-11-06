import numpy as np
import pytest

from norn.contracts.errors import NornError
from norn.embedding.binding import BindingModel
from norn.embedding.losses import Decoder, arm_weights
from norn.embedding.numerics import normalize
from norn.embedding.training import (
    FactorialBatch,
    TrainingBatch,
    factorial_objective,
    objective,
    reference_scales,
    train,
    train_arm,
)

M, Q = 12, 3


def make_batch(seed: int, triples: bool = True) -> FactorialBatch:
    rng = np.random.default_rng(seed)
    facets = normalize(rng.normal(size=(M, 3, 384)))[0]
    mask = np.ones((M, 3))
    mask[2, 1] = 0.0  # one unobserved facet: masked rows must not leak into any term
    positive = np.zeros((Q, M), dtype=bool)
    positive[np.arange(Q), np.arange(Q)] = True
    allowed = np.ones((Q, M), dtype=bool)
    chosen = np.array([[0, 3, 5], [1, 4, 6]], dtype=np.int64) if triples else None
    return FactorialBatch(
        normalize(rng.normal(size=(Q, 384)))[0],
        facets,
        facets[:, 0, :].copy(),
        mask,
        positive,
        allowed,
        chosen if chosen is not None else np.zeros((0, 3), dtype=np.int64),
    )


def legacy_train(model, batches, *, seed, updates, learning_rate=0.003):
    """The pre-refactor Adam loop, frozen verbatim as the bit-identity reference."""
    rng = np.random.default_rng(seed)
    first, second = ({k: np.zeros_like(v) for k, v in model.parameters.items()} for _ in range(2))
    losses = []
    for step in range(1, updates + 1):
        batch = batches[int(rng.integers(len(batches)))]
        loss, grads = objective(model, batch)
        size = np.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
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
        losses.append(loss)
    return losses


def plain(batch: FactorialBatch) -> TrainingBatch:
    return TrainingBatch(
        batch.queries, batch.facets, batch.single, batch.mask, batch.positive, batch.allowed
    )


def test_refactored_train_is_bit_identical_to_the_legacy_loop():
    batches = tuple(plain(make_batch(s)) for s in (1, 2, 3))
    expected = legacy_train(BindingModel("B3", 11), batches, seed=11, updates=12)
    model = BindingModel("B3", 11)
    receipt = train(model, batches, seed=11, updates=12)
    assert receipt["losses"] == expected  # exact equality, not a tolerance
    legacy_model = BindingModel("B3", 11)
    legacy_train(legacy_model, batches, seed=11, updates=12)
    assert all(
        np.array_equal(model.parameters[k], legacy_model.parameters[k]) for k in model.parameters
    )
    # Negative control: a different seed picks different batches, so the comparison can fail.
    other = train(BindingModel("B3", 11), batches, seed=12, updates=12)
    assert other["losses"] != expected


def test_retrieval_only_arm_reproduces_the_p04_objective_and_gradients():
    batch = make_batch(7)
    model = BindingModel("B3", 11)
    decoder = Decoder.create(3, 384, 384, seed=5)
    combined, grads = factorial_objective(model, decoder, batch, arm_weights("T1"))
    loss, expected = objective(model, plain(batch))
    assert combined.value == pytest.approx(loss, rel=1e-12)
    for key in model.parameters:
        assert np.allclose(grads[key], expected[key], atol=1e-12)
    assert not grads["decoder.weights"].any() and not grads["decoder.bias"].any()


@pytest.mark.parametrize("arm", ["T4", "T5", "T6", "T7"])
def test_combined_arm_gradients_match_finite_differences(arm):
    batch = make_batch(9)
    model = BindingModel("B3", 11)
    decoder = Decoder.create(3, 384, 384, seed=5)
    weights = arm_weights(arm, lam_rec=0.5, lam_sep=2.0)
    reference = reference_scales(model, decoder, (batch,), weights)
    _, grads = factorial_objective(model, decoder, batch, weights, reference)
    probes = [
        (model.parameters["out"], grads["out"], (3, 5)),
        (model.parameters["heads"], grads["heads"], (1, 7, 2)),
        (decoder.weights, grads["decoder.weights"], (1, 4, 9)),
    ]
    if arm in ("T4", "T5", "T7"):
        probes.append((model.parameters["query"], grads["query"], (6, 3)))
    for array, gradient, index in probes:
        original = array[index]
        step = 1e-6
        array[index] = original + step
        high = factorial_objective(model, decoder, batch, weights, reference)[0].value
        array[index] = original - step
        low = factorial_objective(model, decoder, batch, weights, reference)[0].value
        array[index] = original
        numeric = (high - low) / (2 * step)
        assert gradient[index] == pytest.approx(numeric, rel=1e-4, abs=1e-8), (arm, index)


def test_towers_receive_gradient_only_from_the_terms_that_reach_them():
    batch = make_batch(11)
    decoder = Decoder.create(3, 384, 384, seed=5)
    model = BindingModel("B3", 11)
    _, grads = factorial_objective(model, decoder, batch, arm_weights("T2"))
    # Reconstruction reaches the memory tower, shared output and decoder, never the query head.
    assert grads["heads"].any() and grads["out"].any() and grads["decoder.weights"].any()
    assert not grads["query"].any() and not grads["query_bias"].any()
    _, grads = factorial_objective(model, decoder, batch, arm_weights("T3"))
    assert grads["heads"].any() and not grads["query"].any() and not grads["decoder.weights"].any()


def test_masked_facet_row_gets_no_reconstruction_gradient_through_its_head():
    batch = make_batch(13)
    decoder = Decoder.create(3, 384, 384, seed=5)
    model = BindingModel("B3", 11)
    base = factorial_objective(model, decoder, batch, arm_weights("T2"))[1]["heads"]
    changed = batch.facets.copy()
    changed[2, 1] = np.random.default_rng(1).normal(size=384)  # a masked, unobserved facet value
    other = FactorialBatch(
        batch.queries,
        changed,
        batch.single,
        batch.mask,
        batch.positive,
        batch.allowed,
        batch.triples,
    )
    moved = factorial_objective(model, decoder, other, arm_weights("T2"))[1]["heads"]
    assert np.array_equal(base, moved)


def test_arm_training_is_deterministic_and_records_each_term():
    batches = (make_batch(21), make_batch(22))
    receipts = []
    for _ in range(2):
        model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
        receipts.append(train_arm(model, decoder, batches, arm_weights("T7"), seed=11, updates=15))
    assert receipts[0]["losses"] == receipts[1]["losses"]
    assert receipts[0]["terms"] == receipts[1]["terms"]
    first = receipts[0]
    assert set(first["reference"]) == {"retrieval", "reconstruction", "separation"}
    assert all(set(t) == set(first["reference"]) for t in first["terms"])
    assert first["losses"][-1] < first["losses"][0] and first["backbone"] == "FROZEN"
    assert (
        first["nonzero_gradient_steps"] == 15
        and first["decoder_parameters"] == 3 * 384 * 384 + 3 * 384
    )


def test_reconstruction_only_arm_leaves_the_query_head_at_initialisation():
    batches = (make_batch(31),)
    model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    before = {k: v.copy() for k, v in model.parameters.items()}
    train_arm(model, decoder, batches, arm_weights("T2"), seed=11, updates=10)
    assert np.array_equal(model.parameters["query"], before["query"])
    assert not np.array_equal(model.parameters["out"], before["out"])  # shared output moved


def test_rejections_fail_visibly():
    model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    with pytest.raises(NornError, match="OBJECTIVE_EMPTY"):
        train_arm(model, decoder, (make_batch(1),), arm_weights("T0"), seed=11, updates=1)
    with pytest.raises(NornError, match="SEPARATION_TARGET_MISSING"):
        train_arm(
            model, decoder, (make_batch(1, triples=False),), arm_weights("T3"), seed=11, updates=1
        )
    bad = make_batch(1)
    broken = FactorialBatch(
        bad.queries,
        bad.facets,
        bad.single,
        bad.mask,
        bad.positive,
        bad.allowed,
        np.array([[0, 1, M]], dtype=np.int64),
    )
    with pytest.raises(NornError, match="FACTORIAL_TRIPLES_INVALID"):
        train_arm(model, decoder, (broken,), arm_weights("T3"), seed=11, updates=1)
    with pytest.raises(NornError, match="TRAINING_ENVELOPE"):
        train_arm(model, decoder, (make_batch(1),), arm_weights("T1"), seed=11, updates=201)
