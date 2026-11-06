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


def test_paired_difference_weights_clusters_equally_and_resamples_clusters_not_rows():
    # One cluster of ten wins; five single-query clusters tie. Hand value: (1+0*5)/6.
    a = [PairedValue(f"big{i}", "big", 7, 1) for i in range(10)]
    a += [PairedValue(f"small{c}", f"small{c}", 7, 0) for c in range(5)]
    b = [PairedValue(v.query_id, v.cluster_id, 7, 0) for v in a]
    report = paired_difference(tuple(a), tuple(b), seed=47, samples=400)
    assert report["difference"] == pytest.approx(1 / 6)
    low, high = report["confidence_interval"]
    # Cluster resampling can draw samples without the winning cluster; row resampling could not.
    assert low == 0 and 0 < high <= 1


def test_report_family_is_holm_adjusted_and_descriptive_rows_are_excluded():
    from benchmark.statistics.paired import adjust_family

    def contrast(left, right):
        a = tuple(
            PairedValue(f"q{c}-{i}", f"cluster{c}", None, left[c % len(left)])
            for c in range(8)
            for i in range(2)
        )
        b = tuple(
            PairedValue(v.query_id, v.cluster_id, None, right[int(v.cluster_id[7:]) % len(right)])
            for v in a
        )
        return paired_difference(a, b, seed=47, samples=200)

    strong, null = contrast([1], [0]), contrast([1, 0], [0, 1])
    descriptive = paired_difference(
        (PairedValue("q", "c", None, 1),), (PairedValue("q", "c", None, 0),), seed=47
    )
    assert 0 < strong["bootstrap_p_two_sided"] < 0.05
    assert null["bootstrap_p_two_sided"] > 0.5 and "bootstrap_p_two_sided" not in descriptive
    family = adjust_family({"strong": strong, "null": null, "small": descriptive})
    assert family["strong"]["multiplicity"]["family_size"] == 2
    # Two tests: the strongest p is doubled, never reported unadjusted as the headline.
    expected = min(1.0, 2 * strong["bootstrap_p_two_sided"])
    assert family["strong"]["multiplicity"]["holm_adjusted_p"] == pytest.approx(expected)
    assert family["small"]["multiplicity"] == {
        "method": "HOLM",
        "family_size": 2,
        "holm_adjusted_p": None,
        "excluded": True,
    }


def test_privacy_bound_is_reported_only_for_zero_observed_incidents_over_real_exposures():
    from dataclasses import replace

    from benchmark.adapters.contracts import Result
    from benchmark.fixtures.partitions import partition
    from benchmark.fixtures.scenarios import scenarios
    from benchmark.fixtures.world import build_world
    from benchmark.metrics.abstention import abstention_score, aggregate

    cases = scenarios(build_world(47, partition(47, "smoke")))
    private = next(c for c in cases if c.gold.family == "E10")
    plain = next(c for c in cases if c.gold.forbidden_canaries == () and c.gold.family == "E1")
    clean = abstention_score(Result("OK", "NOT_ESTABLISHED", ()), private.gold, None)
    unexposed = abstention_score(Result("OK", "NOT_ESTABLISHED", ()), plain.gold, None)
    report = aggregate([clean, clean, unexposed])
    assert report["privacy_exposure_denominator"] == 2
    assert report["privacy_incident_upper_bound_95"] == pytest.approx(zero_incident_bound(2))
    leaked = replace(Result("OK", "NOT_ESTABLISHED", ()), reason=private.gold.forbidden_canaries[0])
    dirty = aggregate([abstention_score(leaked, private.gold, None), clean])
    assert dirty["privacy_incidents"] == 1 and dirty["privacy_incident_upper_bound_95"] is None
    assert aggregate([unexposed])["privacy_incident_upper_bound_95"] is None
