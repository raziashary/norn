import math

import numpy as np
import pytest

from norn.contracts.errors import NornError
from norn.embedding.binding import BindingModel
from norn.embedding.losses import (
    ARM_FLAGS,
    Decoder,
    ObjectiveWeights,
    Term,
    arm_weights,
    combine,
    facet_scales,
    reconstruction_term,
    retrieval_term,
    separation_term,
    sparsity_term,
)
from norn.embedding.numerics import normalize
from norn.embedding.training import TrainingBatch, objective


def numeric_gradient(function, point, step=1e-6):
    grad = np.zeros_like(point)
    for index in np.ndindex(point.shape):
        up, down = point.copy(), point.copy()
        up[index] += step
        down[index] -= step
        grad[index] = (function(up) - function(down)) / (2 * step)
    return grad


def test_retrieval_hand_value_and_direction_with_alternative_positive():
    q = np.array([[1.0, 0.0]])
    m = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]])
    allowed = np.ones((1, 3), dtype=bool)
    one = retrieval_term(q, m, np.array([[True, False, False]]), allowed, temperature=1.0)
    # logsumexp(1, 0, 0.6) - 1 with temperature 1
    expected = math.log(math.exp(1) + 1 + math.exp(0.6)) - 1
    assert one.value == pytest.approx(expected)
    # A second acceptable memory is a positive, not a negative: the loss falls.
    both = retrieval_term(q, m, np.array([[True, False, True]]), allowed, temperature=1.0)
    assert both.value == pytest.approx(
        math.log(math.exp(1) + 1 + math.exp(0.6)) - math.log(math.exp(1) + math.exp(0.6))
    )
    assert both.value < one.value
    # Direction: moving the query along -gradient lowers the loss.
    step = q - 0.05 * one.gradients["query_codes"]
    step = step / np.linalg.norm(step)
    assert retrieval_term(step, m, np.array([[True, False, False]]), allowed, 1.0).value < one.value
    # A memory outside the allowed set is neither positive nor negative.
    held_out = np.array([[True, True, False]])
    excluded = retrieval_term(q, m, np.array([[True, False, False]]), held_out, 1.0)
    assert excluded.value == pytest.approx(math.log(math.exp(1) + 1) - 1)


def test_retrieval_rejects_bad_temperature_unit_violations_and_missing_positive():
    q = np.array([[1.0, 0.0]])
    m = np.array([[1.0, 0.0], [0.0, 1.0]])
    allowed = np.ones((1, 2), dtype=bool)
    positive = np.array([[True, False]])
    for bad in (0.0, -0.1, 1.5, float("nan")):
        with pytest.raises(NornError, match="LOSS_TEMPERATURE_INVALID"):
            retrieval_term(q, m, positive, allowed, bad)
    with pytest.raises(NornError, match="LOSS_CODES_NOT_UNIT"):
        retrieval_term(2 * q, m, positive, allowed, 1.0)
    with pytest.raises(NornError, match="BINDING_POSITIVE_MISSING"):
        retrieval_term(q, m, np.array([[False, False]]), allowed, 1.0)
    with pytest.raises(NornError, match="BINDING_INELIGIBLE_POSITIVE"):
        retrieval_term(q, m, positive, np.array([[False, True]]), 1.0)


def decoder(weights, bias=None):
    weights = np.asarray(weights, dtype=np.float64)
    return Decoder(weights, np.zeros(weights.shape[::2]) if bias is None else bias)


def test_reconstruction_hand_value_scale_mask_and_direction():
    codes = np.array([[1.0, 0.0]])
    targets = np.array([[[0.5, 0.0], [9.0, 9.0]]])  # the second facet is masked: garbage
    mask = np.array([[1.0, 0.0]])
    identity = decoder([np.eye(2), np.eye(2)])
    # Facet 0: mean squared norm 0.25 -> scale 4; error (0.5, 0) -> 4 * 0.25 = 1.0 over 1 entry.
    assert facet_scales(targets, mask).tolist() == [4.0, 0.0]
    term = reconstruction_term(codes, targets, mask, identity)
    assert term.value == pytest.approx(1.0)
    assert term.gradients["memory_codes"] == pytest.approx(np.array([[4.0, 0.0]]))
    # Direction: moving the code toward the target lowers the loss.
    assert (
        reconstruction_term(
            codes - 0.05 * term.gradients["memory_codes"], targets, mask, identity
        ).value
        < term.value
    )
    # The masked facet changes nothing, neither value nor any gradient.
    changed = targets.copy()
    changed[0, 1] = [-100.0, 55.0]
    other = reconstruction_term(codes, changed, mask, identity)
    assert other.value == term.value
    assert not other.gradients["decoder"][1].any() and not other.gradients["decoder_bias"][1].any()


def test_a_partially_masked_facet_is_excluded_row_by_row():
    identity = decoder([np.eye(2)])
    codes = np.array([[1.0, 0.0], [0.0, 1.0]])
    targets = np.array([[[0.5, 0.0]], [[-90.0, 70.0]]])  # row 1 is masked: its target is garbage
    mask = np.array([[1.0], [0.0]])
    both = reconstruction_term(codes, targets, mask, identity)
    alone = reconstruction_term(codes[:1], targets[:1], mask[:1], identity)
    assert both.value == pytest.approx(alone.value) == pytest.approx(1.0)
    assert not both.gradients["memory_codes"][1].any()
    assert both.gradients["decoder"] == pytest.approx(alone.gradients["decoder"])
    assert both.gradients["decoder_bias"] == pytest.approx(alone.gradients["decoder_bias"])


def test_reconstruction_gradients_match_finite_differences():
    rng = np.random.default_rng(3)
    codes = normalize(rng.normal(size=(4, 5)))[0]
    targets = rng.normal(size=(4, 3, 6))
    mask = np.array([[1, 1, 0], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=np.float64)
    dec = Decoder.create(3, 5, 6, seed=2)
    dec = Decoder(dec.weights, rng.normal(size=dec.bias.shape))
    term = reconstruction_term(codes, targets, mask, dec)
    assert term.gradients["memory_codes"] == pytest.approx(
        numeric_gradient(lambda c: reconstruction_term(c, targets, mask, dec).value, codes),
        abs=1e-6,
    )
    assert term.gradients["decoder"] == pytest.approx(
        numeric_gradient(
            lambda w: reconstruction_term(codes, targets, mask, Decoder(w, dec.bias)).value,
            dec.weights.copy(),
        ),
        abs=1e-6,
    )
    assert term.gradients["decoder_bias"] == pytest.approx(
        numeric_gradient(
            lambda b: reconstruction_term(codes, targets, mask, Decoder(dec.weights, b)).value,
            dec.bias.copy(),
        ),
        abs=1e-6,
    )


def test_reconstruction_rejects_zero_missing_and_malformed_targets_and_decoders():
    codes = np.array([[1.0, 0.0]])
    dec = decoder([np.eye(2)])
    with pytest.raises(NornError, match="RECONSTRUCTION_TARGET_MISSING"):
        reconstruction_term(codes, np.ones((1, 1, 2)), np.zeros((1, 1)), dec)
    with pytest.raises(NornError, match="RECONSTRUCTION_TARGET_ZERO"):
        reconstruction_term(codes, np.zeros((1, 1, 2)), np.ones((1, 1)), dec)
    with pytest.raises(NornError, match="RECONSTRUCTION_MASK_INVALID"):
        reconstruction_term(codes, np.ones((1, 1, 2)), np.full((1, 1), 0.5), dec)
    with pytest.raises(NornError, match="DECODER_SHAPE_MISMATCH"):
        reconstruction_term(codes, np.ones((1, 2, 2)), np.ones((1, 2)), dec)
    with pytest.raises(NornError, match="RECONSTRUCTION_TARGET_INVALID"):
        reconstruction_term(codes, np.array([[[np.nan, 1.0]]]), np.ones((1, 1)), dec)
    with pytest.raises(NornError, match="DECODER_INVALID"):
        Decoder(np.full((1, 2, 2), np.inf), np.zeros((1, 2)))
    with pytest.raises(NornError, match="DECODER_INVALID"):
        Decoder.create(1, 2, 2, seed=-1)


def test_separation_hand_value_gradient_direction_and_satisfied_triple():
    codes = np.array([[1.0, 0.0], [0.6, 0.8], [0.8, 0.6]])  # anchor, same-episode, confusable
    triples = np.array([[0, 1, 2]])
    term = separation_term(codes, triples, margin=0.1)
    assert term.value == pytest.approx(0.1 + 0.8 - 0.6)  # the confusable one is closer
    assert term.gradients["memory_codes"] == pytest.approx(
        np.array([[0.2, -0.2], [-1.0, 0.0], [1.0, 0.0]])
    )
    moved = codes - 0.05 * term.gradients["memory_codes"]
    assert separation_term(moved, triples, 0.1).value < term.value
    satisfied = separation_term(codes, np.array([[0, 2, 1]]), margin=0.1)
    assert satisfied.value == 0.0 and not satisfied.gradients["memory_codes"].any()


def test_separation_gradients_match_finite_differences_with_shared_rows():
    rng = np.random.default_rng(8)
    codes = normalize(rng.normal(size=(6, 5)))[0]
    triples = np.array([[0, 1, 2], [0, 3, 4], [5, 1, 2]])
    term = separation_term(codes, triples, margin=0.5)
    assert term.value > 0
    assert term.gradients["memory_codes"] == pytest.approx(
        numeric_gradient(lambda c: separation_term(c, triples, 0.5).value, codes), abs=1e-6
    )


def test_separation_rejects_invalid_margin_missing_and_degenerate_triples():
    codes = np.eye(3)
    for bad in (0.0, -1.0, 2.5, float("nan")):
        with pytest.raises(NornError, match="SEPARATION_MARGIN_INVALID"):
            separation_term(codes, np.array([[0, 1, 2]]), bad)
    for triples in (np.zeros((0, 3), dtype=np.int64), np.array([[0, 1, 3]]), np.array([[0, 1]])):
        with pytest.raises(NornError, match="SEPARATION_TARGET_MISSING"):
            separation_term(codes, triples, 0.1)
    with pytest.raises(NornError, match="SEPARATION_TRIPLE_NOT_DISTINCT"):
        separation_term(codes, np.array([[0, 1, 1]]), 0.1)


def test_collapse_only_regularization_and_empty_objectives_fail():
    with pytest.raises(NornError, match="COLLAPSE_ONLY_REGULARIZER"):
        ObjectiveWeights(sparsity=1.0)
    with pytest.raises(NornError, match="COLLAPSE_ONLY_REGULARIZER"):
        ObjectiveWeights(separation=1.0, sparsity=0.1)  # a ranking term is not a collapse guard
    assert ObjectiveWeights(retrieval=1.0, sparsity=0.1).active() == ("retrieval", "sparsity")
    for bad in (-1.0, float("nan"), float("inf"), True, "1"):
        with pytest.raises(NornError, match="OBJECTIVE_WEIGHT_INVALID"):
            ObjectiveWeights(retrieval=bad)  # type: ignore[arg-type]
    codes = np.array([[1.0, 0.0]])
    with pytest.raises(NornError, match="OBJECTIVE_EMPTY"):
        combine({}, ObjectiveWeights())
    with pytest.raises(NornError, match="OBJECTIVE_TERMS_MISMATCH"):
        combine({"sparsity": sparsity_term(codes)}, ObjectiveWeights(retrieval=1.0))
    assert sparsity_term(codes).value == 1.0


def test_factorial_arms_match_the_blueprint_table():
    assert len(ARM_FLAGS) == 8
    assert not arm_weights("T0").trained  # frozen encoder baseline
    expected = {
        "T1": ("retrieval",),
        "T2": ("reconstruction",),
        "T3": ("separation",),
        "T4": ("retrieval", "reconstruction"),
        "T5": ("retrieval", "separation"),
        "T6": ("reconstruction", "separation"),
        "T7": ("retrieval", "reconstruction", "separation"),
    }
    for arm, names in expected.items():
        assert arm_weights(arm).active() == names
    assert arm_weights("T7", lam_rec=0.2, lam_sep=0.05).reconstruction == 0.2
    assert arm_weights("T1", lam_rec=0.2).reconstruction == 0.0  # weights apply to active terms
    with pytest.raises(NornError, match="LOSS_ARM_UNKNOWN"):
        arm_weights("T8")


def test_combine_keeps_terms_separable_and_normalises_scales():
    codes = np.array([[1.0, 0.0], [0.6, 0.8], [0.8, 0.6]])
    sep = separation_term(codes, np.array([[0, 1, 2]]), 0.1)
    ret = retrieval_term(
        codes[:1], codes, np.array([[True, False, False]]), np.ones((1, 3), dtype=bool), 1.0
    )
    weights = ObjectiveWeights(retrieval=1.0, separation=0.5)
    raw = combine({"retrieval": ret, "separation": sep}, weights)
    assert raw.value == pytest.approx(ret.value + 0.5 * sep.value)
    assert raw.gradients["memory_codes"] == pytest.approx(
        ret.gradients["memory_codes"] + 0.5 * sep.gradients["memory_codes"]
    )
    assert raw.parts["separation"] is sep and raw.gradients.keys() == {
        "memory_codes",
        "query_codes",
    }
    normalised = combine(
        {"retrieval": ret, "separation": sep},
        weights,
        {"retrieval": ret.value, "separation": sep.value},
    )
    assert normalised.value == pytest.approx(1.0 + 0.5)  # each term is 1 at its reference
    for reference in ({"retrieval": 1.0}, {"retrieval": 0.0, "separation": 1.0}):
        with pytest.raises(NornError, match="OBJECTIVE_REFERENCE_INVALID"):
            combine({"retrieval": ret, "separation": sep}, weights, reference)
    with pytest.raises(NornError, match="LOSS_TERM_INVALID"):
        Term("unknown", 0.0)
    with pytest.raises(NornError, match="LOSS_NONFINITE"):
        Term("retrieval", 0.0, {"memory_codes": np.array([np.nan])})


def test_trainer_consumes_the_terms_through_the_real_model_and_matches_the_existing_objective():
    rng = np.random.default_rng(1)
    facets = normalize(rng.normal(size=(4, 3, 384)))[0]
    queries = facets[:, 1, :].copy()
    mask = np.ones((4, 3))
    positive, allowed = np.eye(4, dtype=bool), np.ones((4, 4), dtype=bool)
    batch = TrainingBatch(queries, facets, queries, mask, positive, allowed)
    model = BindingModel("B3")
    memory, mc = model.forward(facets, mask)
    query, qc = model.forward(queries, query=True)
    ret = retrieval_term(query, memory, positive, allowed)
    # Parity: the checked retrieval term reproduces the existing trainer objective exactly.
    loss, reference = objective(model, batch)
    grads_m, grads_q = (
        model.backward(ret.gradients["memory_codes"], mc),
        model.backward(ret.gradients["query_codes"], qc),
    )
    assert ret.value == pytest.approx(loss)
    for key in model.parameters:
        assert grads_m[key] + grads_q[key] == pytest.approx(reference[key], abs=1e-12)
    # Reconstruction and separation flow into the same parameters through model.backward.
    dec = Decoder.create(3, 384, 384, seed=4)
    rec = reconstruction_term(memory, facets, mask, dec)
    sep = separation_term(memory, np.array([[0, 1, 2], [1, 2, 3]]), 0.5)
    total = combine(
        {"reconstruction": rec, "separation": sep},
        ObjectiveWeights(reconstruction=1.0, separation=1.0),
    )
    grads = model.backward(total.gradients["memory_codes"], mc)
    assert any(np.abs(g).sum() > 0 for g in grads.values())
    probe, index = "out", (0, 0)

    def total_value(value: float) -> float:
        original = model.parameters[probe][index]
        model.parameters[probe][index] = value
        code = model.forward(facets, mask)[0]
        out = combine(
            {
                "reconstruction": reconstruction_term(code, facets, mask, dec),
                "separation": separation_term(code, np.array([[0, 1, 2], [1, 2, 3]]), 0.5),
            },
            ObjectiveWeights(reconstruction=1.0, separation=1.0),
        ).value
        model.parameters[probe][index] = original
        return out

    base = model.parameters[probe][index]
    numeric = (total_value(base + 1e-6) - total_value(base - 1e-6)) / 2e-6
    assert grads[probe][index] == pytest.approx(numeric, abs=1e-6, rel=1e-4)
