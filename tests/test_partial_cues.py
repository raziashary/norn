import json

import numpy as np
import pytest
from conftest import REPO

from benchmark.metrics import identity
from benchmark.runs import partial_cues as pc
from benchmark.runs import separation as sweep
from norn.contracts.errors import NornError

HELDOUT = REPO / ".norn" / "p05-t03-heldout-002"


def test_set_recall_needs_every_gold_episode_strictly_above_every_distractor():
    assert identity.set_recall([0.9, 0.5, 0.1], [True, False, False]) is True
    assert identity.set_recall([0.9, 0.2, 0.5], [True, True, False]) is False  # one gold below
    assert identity.set_recall([0.5, 0.5, 0.1], [True, False, False]) is False  # a tie is no win
    assert identity.set_recall([0.5, 0.4], [True, True]) is None  # nothing to beat
    with pytest.raises(NornError, match="IDENTITY_RANKING_INPUT"):
        identity.set_recall([0.5, 0.4], [False, False])


def test_top_gap_and_auroc_hand_values_with_perfect_reversed_tied_and_empty_controls():
    assert identity.top_gap([0.2, 0.9, 0.5]) == pytest.approx(0.4)
    assert identity.top_gap([0.2]) is None and identity.top_gap([]) is None
    assert identity.auroc([0.4, 0.5], [0.05]) == 1.0  # perfect
    assert identity.auroc([0.05], [0.4, 0.5]) == 0.0  # reversed
    assert identity.auroc([0.3, 0.3], [0.3]) == 0.5  # all tied
    assert identity.auroc([0.9, 0.1], [0.5]) == 0.5  # one win, one loss
    assert identity.auroc([], [0.5]) is None and identity.auroc([0.5], []) is None


def test_auroc_of_a_gap_that_carries_no_information_is_near_one_half():
    rng = np.random.default_rng(11)
    a, b = rng.random(400).tolist(), rng.random(400).tolist()
    assert abs(identity.auroc(a, b) - 0.5) < 0.05  # type: ignore[operator]
    shifted = [x + 1.0 for x in a]
    assert identity.auroc(shifted, b) == 1.0  # a perfectly informative gap


def test_same_target_groups_count_only_groups_of_two_or_more():
    result = identity.all_correct_rate([[True, True], [True, False], [True]])
    assert result == {"groups": 2, "all_correct": 0.5}
    assert identity.all_correct_rate([[True]]) == {"groups": 0, "all_correct": None}


def _inputs():
    def query(qid, variant, relevant, pool, cluster="c1", status="SUPPORTED", missing=0.0):
        return sweep.Query(
            qid,
            "COMPLETE_CUE" if missing == 0 else "PARTIAL_CUE",
            "f",
            cluster,
            np.zeros(384),
            pool,
            frozenset(relevant),
            status,
            variant,
            "en",
            missing,
        )

    queries = (
        query("suf1", "positive", {"A"}, (0, 1, 2)),
        query("suf2", "positive", {"A"}, (3, 4)),
        query("ins1", "ambiguous", set(), (1, 2), status="NOT_ESTABLISHED"),
        query("ins2", "missing", set(), (0,), status="NOT_ESTABLISHED"),
        query("other", "positive", set(), (0, 1), status="PARTIALLY_SUPPORTED"),
    )
    return sweep.Inputs(
        queries,
        ("e0", "e1", "e2", "e3", "e4"),
        ("A", "B", "C", "A", "B"),
        np.zeros((5, 384)),
        np.zeros((5, 3, 384)),
        np.ones((5, 3)),
        "m" * 8,
        {},
        {},
    )


SCORES = np.array(
    [
        [0.9, 0.5, 0.1, 0.3, 0.4],
        [0.1, 0.3, 0.2, 0.2, 0.7],
        [0.6, 0.55, 0.5, 0.2, 0.3],
        [0.5, 0.5, 0.1, 0.5, 0.5],
        [0.0, 0.0, 0.0, 0.0, 0.0],
    ]
)


def test_evaluate_scores_matches_hand_computed_values_in_both_scopes():
    result = pc.evaluate_scores(_inputs(), SCORES)
    eligible, pooled = result["eligible"], result["pooled"]
    # Eligible: suf1 wins (A .9 vs B .5), suf2 loses (A .2 vs B .7); the "other" query is skipped.
    assert eligible["identity"]["queries"] == 2 and eligible["identity"]["top1_strict"] == 0.5
    assert eligible["identity"]["contested"] == 2
    assert eligible["set_recall"] == {"applicable": 2, "rate": 0.5}
    gap = eligible["ambiguity_gap"]
    assert (gap["sufficient_n"], gap["insufficient_n"], gap["auroc"]) == (2, 1, 1.0)
    assert gap["sufficient_median"] == pytest.approx(0.45) and gap[
        "insufficient_median"
    ] == pytest.approx(0.05)
    assert eligible["rewording_consistency"] == {"groups": 1, "all_correct": 0.0}
    assert eligible["per_cluster_top1"] == {"c1": 0.5}
    # Pooled: episodes A (e0,e3), B (e1,e4), C (e2); the missing-cue query ties A and B at 0.5.
    assert pooled["identity"]["top1_strict"] == 0.5
    pooled_gap = pooled["ambiguity_gap"]
    assert (pooled_gap["sufficient_n"], pooled_gap["insufficient_n"]) == (2, 2)
    assert pooled_gap["insufficient_median"] == pytest.approx(0.025)  # gaps 0.05 and 0.0
    assert pooled_gap["auroc"] == 1.0
    assert pooled["set_recall"] == {"applicable": 2, "rate": 0.5}


def test_a_code_that_separates_everything_equally_leaves_the_gap_uninformative():
    flat = np.tile(np.array([0.8, 0.2, 0.1, 0.8, 0.2]), (5, 1))
    result = pc.evaluate_scores(_inputs(), flat)["pooled"]
    # Every query sees the same ranking, so sufficient and insufficient gaps coincide: AUROC 0.5.
    assert result["ambiguity_gap"]["auroc"] == 0.5


def test_unseen_identity_roles_are_entity_disjoint_by_construction():
    assert pc.unseen_identity() == {
        "train_entity_indices": [0, 1],
        "tune_entity_indices": [2],
        "disjoint": True,
    }


@pytest.mark.skipif(
    not (HELDOUT / "manifest.json").exists(), reason="needs the local P05 held-out run"
)
def test_real_tune_captures_report_benefit_and_harm_for_every_arm(tmp_path):
    out = tmp_path / "cues.json"
    result = pc.run(HELDOUT, out, wall_cap_seconds=600)
    with pytest.raises(NornError, match="PARTIAL_CUES_OUTPUT_EXISTS"):
        pc.run(HELDOUT, out, wall_cap_seconds=600)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert result["classes"] == {"sufficient": 51, "insufficient": 86, "other": 1}
    assert len(report["cells"]) == 22 * len(pc.CONFIGS) and report["unseen_identity"]["disjoint"]
    assert set(report["arm_minus_t0"]) == {
        f"T{i}/{mode}-{percent}" for i in range(1, 8) for mode, percent in pc.CONFIGS
    }
    t0 = report["arms"]["T0/weighted-100"]
    # Reader check against the T07 sweep: the same 51 queries, scored the same way (28 of 51).
    assert t0["pooled"]["identity"]["queries"] == 51
    assert t0["pooled"]["identity"]["top1_strict"] == pytest.approx(28 / 51)
    for scope in pc.SCOPES:
        auroc = t0[scope]["ambiguity_gap"]["auroc"]
        assert auroc is not None and 0 <= auroc <= 1
    for deltas in report["arm_minus_t0"].values():
        assert (
            deltas["pooled"]["clusters_worse"]
            + deltas["pooled"]["clusters_equal"]
            + deltas["pooled"]["clusters_better"]
            == report["clusters"]
        )
