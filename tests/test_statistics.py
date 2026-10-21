import math

import pytest

from benchmark.statistics.calibration import fit, proper_scores, zero_incident_bound
from benchmark.statistics.paired import PairedValue, holm, paired_difference
from norn.contracts.errors import NornError


def test_paired_cluster_weight_seed_hierarchy_and_small_sample_controls():
    a = tuple(
        PairedValue(f"q{c}-{i}", f"cluster{c}", seed, 1)
        for c in range(6)
        for i in range(1 if c else 10)
        for seed in (7, 11)
    )
    b = tuple(PairedValue(v.query_id, v.cluster_id, v.training_seed, 0) for v in a)
    report = paired_difference(a, b, seed=47, samples=100)
    assert report == paired_difference(a, b, seed=47, samples=100)
    assert report["difference"] == 1 and report["confidence_interval"] == [1, 1]
    assert report["clusters"] == 6 and report["training_seeds"] == [7, 11]
    small = paired_difference(a[:2], b[:2], seed=47)
    assert small["confidence_interval"] is None and small["state"] == "DESCRIPTIVE_SMALL_SAMPLE"
    with pytest.raises(NornError, match="UNPAIRED_OR_DUPLICATE_CASES"):
        paired_difference(a, b[:-1], seed=47)
    with pytest.raises(NornError, match="UNBALANCED_TRAINING_SEEDS"):
        paired_difference(a[1:], b[1:], seed=47)
    assert holm({"a": 0.01, "b": 0.03, "c": 0.2}) == {"a": 0.03, "b": 0.06, "c": 0.2}


def test_proper_scores_ties_calibration_custody_and_zero_incident_limits():
    perfect = proper_scores(((1, True), (0, False)))
    assert perfect["brier"] == perfect["log_loss"] == perfect["ece"] == 0
    # Confidence predicts correctness: accepting the p=0 wrong answer at full coverage adds risk.
    assert perfect["aurc"] == 0.25
    assert proper_scores(((1, True), (1, True)))["aurc"] == 0
    tied = proper_scores(((0.5, False), (0.5, True)))
    assert tied["brier"] == 0.25 and tied["log_loss"] == pytest.approx(math.log(2))
    assert tied["aurc"] == 0.5 and len(tied["risk_coverage"]) == 1
    assert proper_scores(((1, False),))["log_loss_state"] == "INFINITE"
    calibrated = fit(((0.2, True), (0.2, False)), "calibration", "fixture-digest")
    assert calibrated.predict(0.2) == 0.5 and calibrated.source_digest == "fixture-digest"
    with pytest.raises(NornError, match="UNSUPPORTED_CALIBRATION_BIN"):
        calibrated.predict(0.9)
    for tier in ("smoke", "development", "locked"):
        with pytest.raises(NornError, match="CALIBRATION_PARTITION_REQUIRED"):
            fit(((0.2, True),), tier, "fixture-digest")
    assert zero_incident_bound(0) is None
    assert zero_incident_bound(1) == 0.95
    assert 0 < zero_incident_bound(100) < 0.03
