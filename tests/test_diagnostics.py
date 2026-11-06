import numpy as np
import pytest

from norn.contracts.errors import NornError
from norn.embedding import diagnostics as dg
from norn.embedding.binding import BindingModel
from norn.embedding.losses import Decoder, ObjectiveWeights, arm_weights
from norn.embedding.numerics import normalize
from norn.embedding.training import (
    FactorialBatch,
    Schedule,
    factorial_objective,
    reference_scales,
    train_arm,
)


def make_batch(seed: int, triples: bool = True) -> FactorialBatch:
    rng = np.random.default_rng(seed)
    m, q = 12, 3
    facets = normalize(rng.normal(size=(m, 3, 384)))[0]
    positive = np.zeros((q, m), dtype=bool)
    positive[np.arange(q), np.arange(q)] = True
    rows = (
        np.array([[0, 3, 5], [1, 4, 6]], dtype=np.int64) if triples else np.zeros((0, 3), np.int64)
    )
    return FactorialBatch(
        normalize(rng.normal(size=(q, 384)))[0],
        facets,
        facets[:, 0, :].copy(),
        np.ones((m, 3)),
        positive,
        np.ones((q, m), dtype=bool),
        rows,
    )


def vector(*values):
    return np.array(values, dtype=float)


def test_antagonistic_gradients_are_flagged_and_agreement_is_not():
    # Hand-built gradients: exactly opposed, orthogonal and identical on the shared parameter.
    opposed = dg.conflict(
        {"retrieval": {"out": vector(1, 0)}, "separation": {"out": vector(-2, 0)}}
    )
    pair = opposed["pairs"]["retrieval|separation"]
    assert pair["cosine"] == pytest.approx(-1.0) and pair["conflicting"] is True
    assert pair["norm_ratio"] == pytest.approx(2.0)
    right = dg.conflict({"retrieval": {"out": vector(1, 0)}, "separation": {"out": vector(0, 3)}})
    assert right["pairs"]["retrieval|separation"]["cosine"] == pytest.approx(0.0)
    assert right["pairs"]["retrieval|separation"]["conflicting"] is False
    same = dg.conflict({"retrieval": {"out": vector(1, 1)}, "separation": {"out": vector(2, 2)}})
    assert same["pairs"]["retrieval|separation"]["cosine"] == pytest.approx(1.0)
    assert same["norms"]["retrieval"] == pytest.approx(2**0.5)


def test_a_missing_or_unshared_gradient_is_unknown_never_no_conflict():
    zero = dg.conflict({"retrieval": {"out": vector(1, 0)}, "separation": {"out": vector(0, 0)}})
    pair = zero["pairs"]["retrieval|separation"]
    assert pair["cosine"] is None and pair["conflicting"] is None
    apart = dg.conflict({"retrieval": {"query": vector(1, 0)}, "separation": {"out": vector(1, 0)}})
    assert apart["pairs"]["retrieval|separation"]["conflicting"] is None
    assert apart["pairs"]["retrieval|separation"]["reason"] == "NO_SHARED_NONZERO_PARAMETERS"
    with pytest.raises(NornError, match="DIAGNOSTIC_EMPTY"):
        dg.conflict({})
    rows = [
        zero,
        dg.conflict({"retrieval": {"out": vector(1, 0)}, "separation": {"out": vector(-1, 0)}}),
    ]
    summary = dg.summarize(rows)["retrieval|separation"]
    assert summary["batches"] == 2 and summary["defined"] == 1  # the undefined batch is counted
    assert summary["negative_fraction"] == 1.0


def test_collapsed_codes_are_flagged_and_orthogonal_codes_are_not():
    collapsed = dg.code_stats(np.tile(vector(1, 0, 0, 0), (6, 1)), np.ones(6))
    assert collapsed["effective_rank"] == pytest.approx(1.0)
    assert collapsed["mean_pairwise_cosine"] == pytest.approx(1.0) and collapsed["collapsed"]
    spread = dg.code_stats(np.eye(6, 8), np.array([0.5, 1, 1, 1, 1, 2.0]))
    assert spread["effective_rank"] == pytest.approx(6.0)
    assert spread["mean_pairwise_cosine"] == pytest.approx(0.0) and not spread["collapsed"]
    assert spread["rank_fraction"] == pytest.approx(1.0)
    assert (spread["raw_norm_min"], spread["raw_norm_median"], spread["raw_norm_max"]) == (
        0.5,
        1.0,
        2.0,
    )
    with pytest.raises(NornError, match="CODES_INVALID"):
        dg.code_stats(np.ones((1, 4)), np.ones(1))


def test_term_gradients_add_up_to_the_combined_gradient_and_report_missing_terms():
    batch = make_batch(3)
    model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    reference = reference_scales(model, decoder, (batch,), arm_weights("T7"))
    found, missing = dg.term_gradients(model, decoder, batch, reference)
    assert set(found) == set(dg.OBJECTIVES) and missing == {}
    _, combined = factorial_objective(model, decoder, batch, arm_weights("T7"), reference)
    for key in model.parameters:
        total = sum(found[name][key] for name in found)
        assert np.allclose(total, combined[key], atol=1e-10), key
    # Without any triple the separation gradient is missing, with the reason, not zero.
    found, missing = dg.term_gradients(model, decoder, make_batch(3, triples=False), reference)
    assert "separation" not in found and missing == {"separation": "SEPARATION_TARGET_MISSING"}
    with pytest.raises(NornError, match="DIAGNOSTIC_REFERENCE_MISSING"):
        dg.term_gradients(model, decoder, batch, {"retrieval": 1.0})


def test_a_real_retrieval_gradient_conflicts_with_separation_somewhere():
    # Measured, not assumed: the cosine is computed on shared memory-tower parameters.
    batch = make_batch(4)
    model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    found, missing = dg.term_gradients(model, decoder, batch)
    row = dg.conflict(found, missing)
    pair = row["pairs"]["retrieval|separation"]
    assert pair["cosine"] is not None and -1.0 <= pair["cosine"] <= 1.0
    assert set(pair["shared"]) >= {"out", "heads"}  # the query head is not shared with separation


def test_schedule_exposure_is_hand_counted_and_visible_in_the_receipt():
    batches = (make_batch(21), make_batch(22))
    warm = Schedule(((1, arm_weights("T1")), (6, arm_weights("T7"))))
    model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    receipt = train_arm(model, decoder, batches, warm, seed=11, updates=10)
    assert receipt["exposure"] == {"retrieval": 10, "reconstruction": 5, "separation": 5}
    assert receipt["schedule"][0]["from_update"] == 1 and receipt["schedule"][1]["from_update"] == 6
    assert all(set(t) == {"retrieval"} for t in receipt["terms"][:5])
    assert all(
        set(t) == {"retrieval", "reconstruction", "separation"} for t in receipt["terms"][5:]
    )
    fixed = train_arm(
        BindingModel("B3", 11),
        Decoder.create(3, 384, 384, seed=5),
        batches,
        arm_weights("T7"),
        seed=11,
        updates=10,
    )
    assert fixed["exposure"] == {"retrieval": 10, "reconstruction": 10, "separation": 10}
    assert fixed["losses"] != receipt["losses"]  # a different schedule is a different treatment
    for bad in (
        ((2, arm_weights("T1")),),
        ((1, arm_weights("T1")), (1, arm_weights("T7"))),
        ((1, ObjectiveWeights()),),
        (),
    ):
        with pytest.raises(NornError, match="SCHEDULE_INVALID"):
            Schedule(bad)
    with pytest.raises(NornError, match="SCHEDULE_INVALID"):  # a phase that never starts
        train_arm(
            BindingModel("B3", 11),
            Decoder.create(3, 384, 384, seed=5),
            batches,
            Schedule(((1, arm_weights("T1")), (11, arm_weights("T7")))),
            seed=11,
            updates=10,
        )


def test_the_observer_records_a_trace_without_changing_training():
    batches = (make_batch(31), make_batch(32))
    plain_model, plain_decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    plain = train_arm(plain_model, plain_decoder, batches, arm_weights("T7"), seed=11, updates=9)
    model, decoder = BindingModel("B3", 11), Decoder.create(3, 384, 384, seed=5)
    trace = dg.Trace(4)
    watched = train_arm(
        model, decoder, batches, arm_weights("T7"), seed=11, updates=9, observer=trace
    )
    assert watched["losses"] == plain["losses"]  # exact: the observer is read-only
    assert all(
        np.array_equal(model.parameters[k], plain_model.parameters[k]) for k in model.parameters
    )
    assert np.array_equal(decoder.weights, plain_decoder.weights)
    assert [row["update"] for row in trace.rows] == [1, 5, 9]
    assert all(
        "retrieval|separation" in row["pairs"] and row["codes"]["count"] == 12 for row in trace.rows
    )
    with pytest.raises(NornError, match="TRACE_INTERVAL"):
        dg.Trace(0)
