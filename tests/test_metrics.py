import math
from dataclasses import replace

import pytest

from benchmark.adapters.common import candidate
from benchmark.adapters.contracts import Result
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.metrics.abstention import abstention_score, aggregate
from benchmark.metrics.retrieval import retrieval_scores
from benchmark.runs.runner import arm_spec, oracle


def fixtures():
    return scenarios(build_world(47, partition(47, "smoke")))


def test_hand_calculated_chain_partial_complete_redundant_and_wrong_episode():
    case = next(c for c in fixtures() if c.gold.family == "E3" and c.gold.variant == "positive")
    public = publish(case)
    spec = arm_spec("extractive")
    selected = candidate(case.sources[0])
    partial = retrieval_scores(
        public, Result("OK", "SUPPORTED", (selected, selected)), spec, case.gold
    )
    assert partial["slot_coverage"] == partial["retrieval_recall"] == 0.25
    assert partial["complete_set"] is False
    assert partial["unique_sources"] == 1 and partial["raw_candidates"] == 2
    assert partial["ndcg"] == pytest.approx(1 / sum(1 / math.log2(i + 1) for i in range(1, 5)))
    full = retrieval_scores(public, oracle(public, case), arm_spec("perfect"), case.gold)
    assert full["complete_set"] is True and full["ndcg"] == 1
    parking = fixtures()[0]
    public = publish(parking)
    wrong = Result("OK", "SUPPORTED", (candidate(parking.sources[0]),))
    scored = retrieval_scores(public, wrong, spec, parking.gold)
    assert scored["wrong_episode"] is True and scored["retrieval_recall"] == 0
    # Any acceptable alternative can complete a slot; copied alternatives add no slots.
    alternate = next(
        s for s in parking.sources if s.source_id == parking.gold.acceptable_sets[1][0]
    )
    alt = retrieval_scores(
        public, Result("OK", "SUPPORTED", (candidate(alternate),)), spec, parking.gold
    )
    assert alt["complete_set"] is True and alt["slot_denominator"] == 1


def test_abstention_two_sides_and_no_denominator_is_unavailable_not_success():
    positive = fixtures()[0]
    missing = next(c for c in fixtures() if c.gold.family == "E1" and c.gold.variant == "missing")
    no_support = retrieval_scores(
        publish(missing), Result("OK", "NOT_ESTABLISHED", ()), arm_spec("empty"), missing.gold
    )
    assert no_support["complete_set"] is None
    assert no_support["slot_coverage"] is None and no_support["unsatisfiable_slots"] == 1
    rows = [
        abstention_score(Result("OK", "NOT_ESTABLISHED", ()), positive.gold, False),
        abstention_score(Result("OK", "SUPPORTED", ()), missing.gold, None),
        abstention_score(Result("TIMEOUT", None, ()), missing.gold, None),
    ]
    report = aggregate(rows)
    assert report["false_answer_rate"] == report["false_abstention_rate"] == 1
    assert report["false_answer_denominator"] == report["false_abstention_denominator"] == 1
    assert report["failure_counts"] == 1 and report["privacy_observation_denominator"] == 2
    assert aggregate([])["selective_risk"] is None
    private = next(c for c in fixtures() if c.gold.family == "E10")
    leaked = replace(Result("OK", "NOT_ESTABLISHED", ()), reason=private.gold.forbidden_canaries[0])
    assert abstention_score(leaked, private.gold, None)["privacy_incidents"] == 1


def test_qualified_partial_returns_supported_subset_and_explicit_unknowns():
    case = next(c for c in fixtures() if c.gold.expected_status == "PARTIALLY_SUPPORTED")
    public = publish(case)
    result = oracle(public, case)
    score = retrieval_scores(public, result, arm_spec("perfect"), case.gold)
    assert score["complete_set"] is None and score["partial_set"] is True
    assert score["slot_coverage"] == 1 and score["unsatisfiable_slots"] == 1
    answer = abstention_score(result, case.gold, score["complete_set"], score["partial_set"])
    assert answer["correct_supported"] is True
    report = aggregate([answer])
    assert report["selective_risk"] == 0 and report["qualified_partial_accuracy"] == 1
    assert report["partial_answer_usefulness"] == 0.5
    overclaim = replace(result, evidence_status="SUPPORTED", missing_fields=())
    wrong = abstention_score(overclaim, case.gold, score["complete_set"], score["partial_set"])
    assert wrong["false_answer"] is True and wrong["correct_supported"] is False
    unknown = replace(result, missing_fields=("release",))
    assert abstention_score(unknown, case.gold, None, True)["correct_supported"] is False
