import numpy as np
import pytest

from norn.contracts.errors import NornError
from norn.embedding.binding import BindingModel
from norn.embedding.numerics import normalize
from norn.embedding.training import TrainingBatch, objective, train


def batch():
    rng = np.random.default_rng(1)
    x = normalize(rng.normal(size=(4, 3, 384)))[0]
    q = x[:, 1, :].copy()
    return TrainingBatch(
        q, x, q, np.ones((4, 3)), np.eye(4, dtype=bool), np.ones((4, 4), dtype=bool)
    )


@pytest.mark.parametrize("variant", ("B3", "B4", "S3", "S4"))
def test_actual_gradients_train_query_and_memory_and_match_capacity(variant):
    model, b = BindingModel(variant), batch()
    if variant == "B4":
        b.mask[0, 2] = 0
    initial, gradient = objective(model, b)
    for key, parameter in model.parameters.items():
        for index in (0, parameter.size // 2):
            value = parameter.flat[index]
            parameter.flat[index] = value + 1e-5
            plus = objective(model, b)[0]
            parameter.flat[index] = value - 1e-5
            minus = objective(model, b)[0]
            parameter.flat[index] = value
            assert gradient[key].flat[index] == pytest.approx(
                (plus - minus) / 2e-5, abs=2e-6, rel=1e-3
            )
    receipt = train(model, (b,), seed=11, updates=30)
    assert objective(model, b)[0] < initial
    assert receipt["updates"] == 30 and receipt["backbone"] == "FROZEN"
    assert receipt["nonzero_gradient_steps"] > 0 and receipt["parameter_delta_l2"] > 0
    assert 1 <= receipt["sample_code_effective_rank"] <= len(b.facets) + 1e-9
    q = model.forward(b.queries, query=True)[0]
    m = model.forward(b.single if variant.startswith("S") else b.facets, b.mask)[0]
    assert np.allclose(np.linalg.norm(q, axis=1), 1)
    assert np.allclose(np.linalg.norm(m, axis=1), 1)
    assert np.array_equal((q @ m.T).argmax(1), np.arange(4))
    target = "B3" if variant in ("B3", "S3") else "B4"
    control = "S3" if target == "B3" else "S4"
    assert (
        abs(BindingModel(control).parameter_count / BindingModel(target).parameter_count - 1)
        <= 0.01
    )


def test_masks_envelopes_and_multi_positive_are_real_controls():
    b = batch()
    b.positive[0, 1] = True
    loss, _ = objective(BindingModel("B3"), b)
    assert np.isfinite(loss)
    b.allowed[0, 1] = False
    with pytest.raises(NornError, match="BINDING_POSITIVE_MISSING"):
        objective(BindingModel("B3"), b)
    b = batch()
    b.mask[0] = 0
    with pytest.raises(NornError, match="BINDING_ALL_MISSING"):
        objective(BindingModel("B4"), b)
    with pytest.raises(NornError, match="TRAINING_ENVELOPE"):
        train(BindingModel("B3"), (batch(),), seed=0)


def test_candidate_limit_counts_events_so_one_large_event_cannot_crowd_out_the_rest():
    from dataclasses import replace

    from norn.retrieval.binding import expand_ranked_events
    from norn.retrieval.contracts import Record

    base = Record(
        "ns",
        "event-a",
        "atom-0",
        "s",
        ("a",),
        "p",
        '"v"',
        "{}",
        "USER_REPORTED",
        "UNVERIFIED",
        "ACTIVE",
        "CURRENT",
        "{}",
        "src",
        "v" * 8,
        0,
        4,
        "d" * 8,
        "text",
        1,
    )
    big = [replace(base, atom_id=f"big-{i}", event_id="big") for i in range(12)]
    small = [replace(base, atom_id=f"small-{i}", event_id=f"small-{i}") for i in range(3)]
    scores = {"big": 0.9, "small-0": 0.8, "small-1": 0.7, "small-2": 0.6}
    ranked = expand_ranked_events(tuple(big + small), scores, "B3", 3)
    events = list(dict.fromkeys(h.record.event_id for h in ranked))
    assert events == ["big", "small-0", "small-1"]
    assert sum(h.record.event_id == "big" for h in ranked) == 12
    # Negative control: the old atom-level cut at the same limit would have kept only "big".
    atom_level = sorted((h for h in ranked), key=lambda h: (-h.score, h.record.key))[:3]
    assert {h.record.event_id for h in atom_level} == {"big"}
