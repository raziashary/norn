import json
from dataclasses import replace

import numpy as np
import pytest

from benchmark.fixtures.binding_cases import cases
from benchmark.fixtures.partitions import authorize_partition
from benchmark.fixtures.render import render
from benchmark.fixtures.training_pairs import (
    ONE_FIELD_NAMES,
    PAIRS_VERSION,
    TrainingPairs,
    _bump_action,
    _bump_value,
    _content,
    _differing,
    assert_disjoint_from_heldout,
    build_pairs,
    dumps,
    labels,
    loads,
    pair_from_case,
)
from norn.contracts.errors import NornError
from norn.embedding.binding import BindingModel
from norn.embedding.numerics import normalize
from norn.embedding.training import TrainingBatch, objective

SEED = 20261021


def train_case(family, variant, language="en", fraction=0.0):
    return next(
        c
        for c in cases("train", seed=SEED)
        if c.gold.family == family
        and c.gold.variant == variant
        and c.gold.language == language
        and c.gold.cue_missing_fraction == fraction
        and c.gold.reason != "MENTION_IS_NOT_REQUIREMENT"
    )


def test_hand_counted_e1_positive_keeps_the_paraphrase_and_builds_four_negatives():
    case = train_case("E1", "positive")
    # Two facts (ZoneA on the 19th, ZoneB on the 20th) plus an Indonesian copy of the chosen one.
    assert len(case.sources) == 3 and len(case.gold.acceptable_sets) == 2
    pair, reason = pair_from_case(case, seed=SEED)
    assert pair is not None and reason == ""
    chosen = case.gold.acceptable_sets[0][0]
    paraphrase = case.gold.acceptable_sets[1][0]
    # Alternative valid evidence is a positive, never a negative.
    assert set(pair.positives) == {chosen, paraphrase} and not pair.ambiguous
    by_kind = {(n.kind, n.field): n for n in pair.negatives}
    assert len(pair.negatives) == 4 and pair.screened == ()
    other_day = next(s.source_id for s in case.sources if s.source_id not in pair.positives)
    assert by_kind[("CORPUS", "MULTI")].source_id == other_day  # ZoneA/19th: two fields differ
    anchor = next(s for s in case.sources if s.source_id == chosen).observation
    for name in ONE_FIELD_NAMES:
        negative = by_kind[("ONE_FIELD", name)]
        assert negative.source is not None and negative.anchor == chosen
        assert _differing(negative.source.observation, anchor) == (name,)
        assert negative.source_id == negative.source.source_id
    assert by_kind[("ONE_FIELD", "value")].source.observation.value == "ZoneC"
    assert by_kind[("ONE_FIELD", "event_time")].source.observation.event_time.startswith(
        "2026-10-21"
    )
    assert by_kind[("ONE_FIELD", "origin")].source.observation.origin == "HYPOTHESIS"


def test_value_perturbation_is_hand_checked():
    assert _bump_value("ZoneA") == "ZoneB" and _bump_value("zone") == "zonf"
    assert _bump_value("Zz") == "Za" and _bump_value("invoice-199") == "invoice-200"
    assert _bump_value("12.5kg") == "12.6kg" and _bump_value("v9") == "v10"
    with pytest.raises(NornError, match="PAIR_VALUE_NOT_PERTURBABLE"):
        _bump_value("--")


def test_structured_action_values_keep_their_timestamp_when_perturbed():
    value = "step=0;tool=restart;result=exit0;at=2026-10-19T09:00:00+00:00"
    bumped = _bump_action(value)
    assert bumped == "step=0;tool=restart;result=exit1;at=2026-10-19T09:00:00+00:00"
    two = "step=0;tool=a;result=ok;at=T0|step=1;tool=b;result=ok;at=T1"
    assert _bump_action(two) == "step=0;tool=a;result=ol;at=T0|step=1;tool=b;result=ok;at=T1"
    # Control: the generic bump would corrupt the timestamp offset, which the engine refuses.
    assert _bump_value(value).endswith("+00:1")
    with pytest.raises(NornError, match="PAIR_VALUE_NOT_PERTURBABLE"):
        _bump_action("tool=restart")
    built = build_pairs(smoke=True)
    for pair in built.pairs:
        for negative in pair.negatives:
            if negative.source and negative.source.observation.predicate == "observed_action":
                assert "+00:00" in negative.source.observation.value


def test_ambiguous_cue_keeps_every_eligible_source_positive_and_forces_no_negative():
    case = train_case("E11", "ambiguous")
    assert case.gold.reason == "AMBIGUOUS" and len(case.sources) >= 3
    pair, _ = pair_from_case(case, seed=SEED)
    assert pair is not None and pair.ambiguous
    assert set(pair.positives) == {s.source_id for s in case.sources} and pair.negatives == ()
    assert pair.positive_sets == (pair.positives,)


def test_unsupported_missing_cases_are_skipped_not_given_invented_positives():
    case = train_case("E1", "missing")
    pair, reason = pair_from_case(case, seed=SEED)
    assert pair is None and reason == "NO_ELIGIBLE_SUPERVISED_POSITIVE"


def test_no_valid_alternative_is_a_negative_anywhere_in_the_train_role():
    built = build_pairs()
    assert len(built.pairs) == 178 and len(built.skipped) == 98  # same split as P04 training
    by_query = {c.gold.query_id: c for c in cases("train", seed=SEED)}
    for pair in built.pairs:
        case = by_query[pair.query_id]
        accepted = {i for g in (*case.gold.acceptable_sets, *case.gold.partial_sets) for i in g}
        contents = {s.source_id: _content(s.observation) for s in case.sources}
        positive_contents = {contents[i] for i in pair.positives}
        for negative in pair.negatives:
            assert negative.source_id not in accepted | set(pair.positives)
            content = contents.get(negative.source_id) or _content(negative.source.observation)
            assert content not in positive_contents
            assert negative.source_id not in contents or negative.kind == "CORPUS"
            assert negative.source_id in contents or negative.kind == "ONE_FIELD"
        if pair.ambiguous:
            assert pair.negatives == ()


def test_a_one_field_change_that_reproduces_valid_evidence_is_screened_not_negative():
    case = train_case("E1", "positive")
    chosen = case.gold.acceptable_sets[0][0]
    anchor = next(s for s in case.sources if s.source_id == chosen)
    # Valid alternative evidence whose content equals the value-perturbed negative.
    rival = replace(anchor.observation, value="ZoneC", producer=anchor.observation.producer)
    from benchmark.fixtures.world import Fact

    alternative = render(
        Fact(
            "hidden-alt",
            rival.actor,
            rival.predicate,
            rival.value,
            rival.event_time,
            rival.recorded_at,
            rival.origin,
            anchor.independence_group,
        ),
        seed=SEED,
        namespace=anchor.namespace,
    )
    gold = replace(
        case.gold, acceptable_sets=(*case.gold.acceptable_sets, (alternative.source_id,))
    )
    pair, _ = pair_from_case(
        replace(case, sources=(*case.sources, alternative), gold=gold), seed=SEED
    )
    assert pair is not None and alternative.source_id in pair.positives
    assert ("ONE_FIELD", "value") not in {
        (n.kind, n.field) for n in pair.negatives if n.anchor == chosen
    }
    assert dict(pair.screened)["ONE_FIELD_COLLIDES_WITH_CORPUS"] == 1
    # Control: without the alternative the same negative is generated.
    base, _ = pair_from_case(case, seed=SEED)
    assert base is not None and ("ONE_FIELD", "value") in {
        (n.kind, n.field) for n in base.negatives
    }


def test_same_event_sources_are_screened_out_of_the_negatives():
    case = train_case("E1", "positive")
    chosen = next(s for s in case.sources if s.source_id == case.gold.acceptable_sets[0][0])
    last = "0" if chosen.source_id[-1] != "0" else "1"
    # Same event (same actor and instant) but different content: still the same episode, so it
    # is withheld from the negatives instead of being taught as wrong.
    twin = replace(
        chosen,
        source_id=chosen.source_id[:-1] + last,
        observation=replace(chosen.observation, value="ZoneQ"),
    )
    assert twin.event_id == chosen.event_id
    pair, _ = pair_from_case(replace(case, sources=(*case.sources, twin)), seed=SEED)
    assert pair is not None and twin.source_id not in {n.source_id for n in pair.negatives}
    assert dict(pair.screened) == {"SAME_EVENT_AS_POSITIVE": 1}
    # Control: with the event screen the twin would otherwise be an ordinary value negative.
    assert twin.observation.value != chosen.observation.value


def test_only_the_train_role_is_readable_and_heldout_labels_cannot_enter():
    with pytest.raises(NornError, match="PAIRS_ROLE_DENIED"):
        build_pairs("tune")
    for role, tier in (
        ("trainer", "calibration"),
        ("trainer", "locked"),
        ("tuner", "calibration"),
        ("calibrator", "development"),
    ):
        with pytest.raises(NornError, match="PARTITION_ACCESS_DENIED"):
            authorize_partition(role, tier)
    built = build_pairs()
    assert assert_disjoint_from_heldout(built)["heldout_cases_checked"] == 276
    # Negative control: a pair built from an evaluation-role case is caught for the right reason.
    held = next(c for c in cases("evaluation", seed=SEED) if c.gold.reason == "SUFFICIENT")
    leaked, _ = pair_from_case(held, seed=SEED)
    assert leaked is not None
    contaminated = TrainingPairs(
        PAIRS_VERSION, "train", SEED, False, (*built.pairs, leaked), built.skipped
    )
    with pytest.raises(NornError, match="HELDOUT_LABEL_IN_TRAINING"):
        assert_disjoint_from_heldout(contaminated)
    with pytest.raises(NornError, match="PAIRS_ROLE_DENIED"):
        assert_disjoint_from_heldout(replace(built, role="tune"))


def test_versioned_roundtrip_is_deterministic_and_tamper_evident():
    first, second = build_pairs(smoke=True), build_pairs(smoke=True)
    assert first.sha256 == second.sha256 and dumps(first) == dumps(second)
    assert loads(dumps(first)) == first and first.version == PAIRS_VERSION
    raw = json.loads(dumps(first))
    raw["pairs"]["pairs"][0]["positives"] = ["source_" + "0" * 64]
    with pytest.raises(NornError, match="PAIRS_DIGEST"):
        loads(json.dumps(raw))
    raw = json.loads(dumps(first))
    raw["pairs"]["role"] = "tune"
    with pytest.raises(NornError, match="PAIRS_VERSION_OR_ROLE"):
        loads(json.dumps(raw))
    raw = json.loads(dumps(first))
    raw["pairs"]["version"] = "training-pairs-v0"
    with pytest.raises(NornError, match="PAIRS_VERSION_OR_ROLE"):
        loads(json.dumps(raw))


def test_trainer_consumes_labels_through_the_real_batch_and_objective():
    case = train_case("E1", "positive")
    pair, _ = pair_from_case(case, seed=SEED)
    assert pair is not None
    memory_ids = (*pair.positives, *(n.source_id for n in pair.negatives), "source_" + "f" * 64)
    positive, allowed = labels(pair, memory_ids)
    # The unknown memory is neither positive nor a screened negative: excluded, not a negative.
    assert positive.sum() == len(pair.positives) and allowed.sum() == len(memory_ids) - 1
    assert not allowed[-1] and not (positive & ~allowed).any()
    rng = np.random.default_rng(5)
    facets = normalize(rng.normal(size=(len(memory_ids), 3, 384)))[0]
    batch = TrainingBatch(
        normalize(rng.normal(size=(1, 384)))[0],
        facets,
        facets[:, 0, :].copy(),
        np.ones((len(memory_ids), 3)),
        positive[None, :],
        allowed[None, :],
    )
    loss, gradient = objective(BindingModel("B3"), batch)
    assert np.isfinite(loss) and any(np.abs(g).sum() > 0 for g in gradient.values())
    with pytest.raises(NornError, match="PAIR_POSITIVE_NOT_IN_MEMORY"):
        labels(pair, tuple(n.source_id for n in pair.negatives))
    with pytest.raises(NornError, match="PAIR_MEMORY_DUPLICATE"):
        labels(pair, (pair.positives[0], pair.positives[0]))
