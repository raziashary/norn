import json

import numpy as np
import pytest
from conftest import REPO

from benchmark.metrics import identity
from benchmark.runs import separation as sweep
from benchmark.runs.manifest import file_digest
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical
from norn.embedding import separation as sep

HELDOUT = REPO / ".norn" / "p05-t03-heldout-002"


def vector(**entries):
    """A 384-coordinate row that is zero except for the named coordinates (c<index>=value)."""
    row = np.zeros(384)
    for name, value in entries.items():
        row[int(name[1:])] = value
    return row


def test_sparse_width_is_the_percentage_of_384_with_a_floor_of_one():
    assert [sep.sparse_width(p) for p in sep.SPARSITY_PERCENT] == [4, 8, 19, 38, 384]
    with pytest.raises(NornError, match="SEPARATION_SPARSITY"):
        sep.sparse_width(3)


def test_support_keeps_largest_magnitudes_with_signs_ignored_and_low_index_on_ties():
    row = vector(c10=-0.9, c20=0.5, c30=0.5, c40=0.1)
    # |-0.9| first; the 0.5 tie keeps the lower index 20, not 30.
    assert np.flatnonzero(sep.support(row[None], 2)[0]).tolist() == [10, 20]
    assert np.flatnonzero(sep.support(row[None], 3)[0]).tolist() == [10, 20, 30]
    with pytest.raises(NornError, match="SEPARATION_WIDTH"):
        sep.support(row[None], 0)


def test_binary_similarity_is_the_hand_counted_overlap_and_weighted_is_the_hand_cosine():
    a = vector(c1=3.0, c2=-4.0, c3=0.1)
    b = vector(c1=1.0, c2=1.0, c4=9.0)
    q, m = a[None], b[None]
    # k=2: a keeps {1, 2}; b keeps {4, 1}; overlap is the single coordinate 1.
    assert (
        float(sep.similarity(sep.sparsify(q, 2, "binary")[0], sep.sparsify(m, 2, "binary"))[0])
        == 1.0
    )
    # Weighted: a -> (3, -4)/5 at {1, 2}; b -> (1, 9)/sqrt(82) at {1, 4}; dot = 3/5 * 1/sqrt(82).
    expected = (3 / 5) * (1 / np.sqrt(82))
    got = float(
        sep.similarity(sep.sparsify(q, 2, "weighted")[0], sep.sparsify(m, 2, "weighted"))[0]
    )
    assert got == pytest.approx(expected)
    # Full width weighted is the exact dense cosine (the exhaustive control).
    dense = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    full = float(
        sep.similarity(sep.sparsify(q, 384, "weighted")[0], sep.sparsify(m, 384, "weighted"))[0]
    )
    assert full == pytest.approx(dense)


def test_full_width_binary_code_is_a_total_tie_and_is_never_credited():
    rng = np.random.default_rng(3)
    codes = rng.normal(size=(5, 384))
    ones = sep.sparsify(codes, 384, "binary")
    scores = sep.similarity(ones[0], ones)
    outcome = identity.ranking_outcome(scores.tolist(), [True, False, False, False, False])
    assert outcome["tied_at_top"] and not outcome["top1_strict"] and outcome["top1_tie_inclusive"]


def test_rotation_is_orthogonal_deterministic_and_preserves_dense_cosines():
    basis = sep.orthogonal_basis(11)
    assert np.allclose(basis.T @ basis, np.eye(384), atol=1e-9)
    assert np.array_equal(basis, sep.orthogonal_basis(11))
    assert not np.allclose(basis, sep.orthogonal_basis(29))
    x = np.random.default_rng(5).normal(size=(4, 384))
    assert np.allclose(x @ x.T, (x @ basis) @ (x @ basis).T, atol=1e-9)
    # Sparsifying in a rotated basis is not the same code as sparsifying natively.
    assert not np.array_equal(sep.support(x, 8), sep.support(x @ basis, 8))


def test_bytes_and_matched_dense_width_follow_the_declared_storage_model():
    assert sep.event_bytes("dense", 384) == 1536
    assert sep.event_bytes("weighted", 4) == 16 and sep.event_bytes("binary", 4) == 8
    assert sep.matched_width(sep.event_bytes("weighted", 4)) == 4
    assert sep.matched_width(sep.event_bytes("binary", 4)) == 2
    assert sep.matched_width(sep.event_bytes("weighted", 384)) == 384
    assert sep.matched_width(1) == 1
    assert sep.gaussian_projection(11, 8).shape == (384, 8)


def test_fusion_endpoints_are_the_two_scores_and_out_of_range_weight_is_refused():
    a, b = np.array([[1.0, 2.0]]), np.array([[3.0, 6.0]])
    assert np.array_equal(sep.fuse(a, b, 0.0), a) and np.array_equal(sep.fuse(a, b, 1.0), b)
    assert np.allclose(sep.fuse(a, b, 0.25), [[1.5, 3.0]])
    with pytest.raises(NornError, match="SEPARATION_FUSION"):
        sep.fuse(a, b, 1.5)


def test_ranking_outcome_hand_values_perfect_tie_and_wrong_event_ahead():
    perfect = identity.ranking_outcome([0.9, 0.2, 0.1], [True, False, False])
    assert perfect["top1_strict"] and perfect["margin"] == pytest.approx(0.7)
    tie = identity.ranking_outcome([0.5, 0.5, 0.1], [True, False, False])
    assert not tie["top1_strict"] and tie["top1_tie_inclusive"] and tie["tied_at_top"]
    wrong = identity.ranking_outcome([0.2, 0.8, 0.1], [True, False, False])
    assert not wrong["top1_strict"] and wrong["margin"] == pytest.approx(-0.6)
    alone = identity.ranking_outcome([0.3], [True])
    assert alone["top1_strict"] and alone["margin"] is None
    with pytest.raises(NornError, match="IDENTITY_RANKING_INPUT"):
        identity.ranking_outcome([0.3, 0.2], [False, False])  # no gold: not a scorable query
    with pytest.raises(NornError, match="IDENTITY_RANKING_INPUT"):
        identity.ranking_outcome([float("nan"), 0.2], [True, False])


def test_summary_counts_an_empty_set_without_inventing_a_rate():
    empty = identity.summarize([])
    assert empty["queries"] == 0 and empty["top1_strict"] is None and empty["margin_mean"] is None
    outcomes = [
        identity.ranking_outcome([0.9, 0.1], [True, False]),
        identity.ranking_outcome([0.1, 0.9], [True, False]),
        identity.ranking_outcome([0.5, 0.5], [True, False]),
        identity.ranking_outcome([0.4], [True]),
    ]
    s = identity.summarize(outcomes)
    assert (s["queries"], s["top1_strict"], s["top1_tie_inclusive"], s["tied_at_top"]) == (
        4,
        0.5,
        0.75,
        0.25,
    )
    assert s["margin_defined"] == 3 and s["wrong_event_ahead"] == pytest.approx(1 / 3)
    strata = identity.stratified([{"s": "A"}, {"s": "A"}, {"s": "B"}, {"s": "B"}], outcomes, "s")
    assert strata["A"]["top1_strict"] == 0.5 and strata["B"]["top1_strict"] == 0.5
    assert strata["B"]["tied_at_top"] == 0.5


def test_shuffled_scores_land_near_the_hand_computed_chance_rate():
    assert identity.chance_top1([4, 2], [1, 1]) == pytest.approx((0.25 + 0.5) / 2)
    rng = np.random.default_rng(7)
    hits = [
        identity.ranking_outcome(rng.normal(size=4).tolist(), [True, False, False, False])[
            "top1_strict"
        ]
        for _ in range(4000)
    ]
    assert abs(sum(hits) / len(hits) - 0.25) < 0.03
    perfect = [identity.ranking_outcome([1.0, 0.0, 0.0, 0.0], [True, False, False, False])] * 3
    assert identity.summarize(perfect)["top1_strict"] == 1.0


def test_collision_pairs_count_identical_codes_exactly():
    rows = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 0.0]])
    result = identity.collision_pairs(rows)
    assert (result["events"], result["pairs"], result["colliding_pairs"]) == (4, 6, 3)
    assert result["rate"] == 0.5
    assert identity.collision_pairs(np.eye(3))["colliding_pairs"] == 0


def _tiny_inputs():
    zero = np.zeros((4, 384))
    queries = (
        sweep.Query("q1", "COMPLETE_CUE", "f", "c1", np.zeros(384), (0, 1, 2), frozenset({"A"})),
        sweep.Query("q2", "PARTIAL_CUE", "f", "c2", np.zeros(384), (2, 3), frozenset({"B", "C"})),
    )
    return sweep.Inputs(
        queries,
        ("e0", "e1", "e2", "e3"),
        ("A", "A", "B", "C"),
        zero,
        np.zeros((4, 3, 384)),
        np.ones((4, 3)),
        "m" * 8,
        {},
        {},
    )


def test_copies_of_one_episode_do_not_tie_with_themselves_but_distinct_episodes_do():
    inputs = _tiny_inputs()
    # q1: the two renderings of A tie each other at 0.9 and B trails; q2: B and C tie at 0.5.
    scores = np.array([[0.9, 0.9, 0.2, 0.0], [0.0, 0.0, 0.5, 0.5]])
    eligible = sweep._outcomes(inputs, scores, "eligible")
    assert eligible[0]["top1_strict"] and not eligible[0]["tied_at_top"]
    assert eligible[0]["pool"] == 2 and eligible[0]["gold"] == 1 and eligible[0]["contested"]
    # q2's two gold episodes tie each other: not credited as an identification, and not contested.
    assert not eligible[1]["top1_strict"] and eligible[1]["tied_at_top"]
    assert eligible[1]["top1_tie_inclusive"] and not eligible[1]["contested"]
    # Pooled: q1 still sees A as the unique best episode among A, B, C (4 events, 3 episodes).
    pooled = sweep._outcomes(inputs, scores, "pooled")
    assert pooled[0]["pool"] == 3 and pooled[0]["top1_strict"]
    assert sweep._episode_top(inputs, scores[0]) == "A"
    assert sweep._episode_top(inputs, scores[1]) is None  # B and C tie at the top
    # Hubness: one of the two queries has a unique leader, and it is episode A.
    result = sweep._scope_result(inputs, scores, "pooled", None)
    assert result["distinct_top_episodes"] == 1 and result["hub_share"] == 0.5
    hub = np.array([[0.9, 0.9, 0.2, 0.0], [0.9, 0.9, 0.2, 0.0]])
    assert sweep._scope_result(inputs, hub, "pooled", None)["hub_share"] == 1.0


def test_contested_summary_counts_only_queries_with_a_distractor():
    all_gold = identity.ranking_outcome([0.5, 0.4], [True, True])
    won = identity.ranking_outcome([0.9, 0.1], [True, False])
    lost = identity.ranking_outcome([0.1, 0.9], [True, False])
    s = identity.summarize([all_gold, won, lost])
    assert s["contested"] == 2 and s["top1_strict_contested"] == 0.5
    assert s["top1_strict"] == pytest.approx(
        2 / 3
    )  # the uncontested query inflates the overall rate
    assert identity.summarize([all_gold])["top1_strict_contested"] is None


def _run_root(tmp_path, names):
    """A manifest with tiny stand-in artifacts for the given relative names."""
    artifacts = {}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": name}), encoding="utf-8")
        artifacts[name] = file_digest(path)
    manifest = {"kind": "P05_LOSS_HELDOUT", "artifacts": artifacts, "checkpoints": {}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_only_digest_verified_tune_artifacts_are_read_and_evaluation_is_never_opened(tmp_path):
    names = [f"{f}/tune/query_{'a' * 64}.json" for f in ("captures", "evaluator", "published")]
    root = _run_root(tmp_path, [*names, f"captures/evaluation/query_{'b' * 64}.json"])
    assert sweep._verified(root)["kind"] == "P05_LOSS_HELDOUT"
    # A corrupted evaluation artifact does not matter: the sweep never reads that role...
    (root / f"captures/evaluation/query_{'b' * 64}.json").write_text("tampered", encoding="utf-8")
    assert sweep._verified(root)
    # ...but a tune artifact that differs from the manifest digest is refused.
    (root / names[0]).write_text("tampered", encoding="utf-8")
    with pytest.raises(NornError, match="SEPARATION_ARTIFACT_CHANGED"):
        sweep._verified(root)


def test_a_run_without_tune_artifacts_or_of_another_kind_is_refused(tmp_path):
    only_eval = _run_root(tmp_path / "a", [f"captures/evaluation/query_{'b' * 64}.json"])
    with pytest.raises(NornError, match="SEPARATION_TUNE_ARTIFACTS_MISSING"):
        sweep._verified(only_eval)
    other = _run_root(
        tmp_path / "b", [f"{f}/tune/q.json" for f in ("captures", "evaluator", "published")]
    )
    manifest = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    manifest["kind"] = "P05_LOSS_FACTORIAL"
    (other / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NornError, match="SEPARATION_RUN_KIND"):
        sweep._verified(other)


@pytest.mark.skipif(
    not (HELDOUT / "manifest.json").exists(), reason="needs the local P05 held-out run"
)
def test_real_tune_captures_sweep_reports_every_declared_cell_and_the_controls(tmp_path):
    out = tmp_path / "sweep.json"
    result = sweep.run(HELDOUT, out, wall_cap_seconds=600)
    with pytest.raises(NornError, match="SEPARATION_OUTPUT_EXISTS"):
        sweep.run(HELDOUT, out, wall_cap_seconds=600)
    report = json.loads(out.read_text(encoding="utf-8"))
    cells = report["cells"]
    sources, percents, modes = 22, len(sep.SPARSITY_PERCENT), len(sep.MODES)
    sparse = sources * 4 * modes * percents
    matched = sources * 3 * modes * percents
    fusion = 21 * percents * len(sweep.FUSION_WEIGHTS)
    assert len(cells) == result["cells"] == sparse + matched + fusion + 3
    assert report["scopes"]["applicable_queries"] == 51 and "evaluation" not in canonical(
        report["config"]
    )

    def find(family, source, geometry, mode, percent):
        return next(
            c
            for c in cells
            if (c["family"], c["source"], c["geometry"], c["mode"], c["percent"])
            == (family, source, geometry, mode, percent)
        )

    exhaustive = find("sparse", "T0", "native", "weighted", 100)
    # The exhaustive control agrees with itself wherever its own top episode is unique.
    assert exhaustive["pooled"]["agreement_with_dense"] == pytest.approx(
        1 - exhaustive["pooled"]["overall"]["tied_at_top"]
    )
    # Negative control: a full-width binary code ties every episode, so nothing is credited.
    ties = find("sparse", "T0", "native", "binary", 100)
    assert ties["pooled"]["overall"]["top1_strict"] == 0
    assert ties["pooled"]["overall"]["tied_at_top"] == 1
    # Shuffled labels sit near the pooled chance rate, far below the real exhaustive rate.
    chance = exhaustive["pooled"]["chance_top1"]
    shuffled = [
        c["pooled"]["overall"]["top1_strict"]
        for c in cells
        if c["family"] == "shuffled_gold_control"
    ]
    real = exhaustive["pooled"]["overall"]["top1_strict"]
    assert len(shuffled) == 3 and max(shuffled) < chance + 0.1 < real
    assert (
        1 <= exhaustive["pooled"]["distinct_top_episodes"] <= report["scopes"]["distinct_episodes"]
    )
    assert 0 < exhaustive["pooled"]["hub_share"] <= 1
