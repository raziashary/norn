import json

import pytest
from conftest import REPO

from benchmark.runs import loss_heldout as lh
from norn.contracts.errors import NornError

RUNS = REPO / ".norn"
FACTORIAL, SOURCE, MODELS = RUNS / "p05-t03-001", RUNS / "p05-pre-b-001", RUNS / "models"


def row(arm, query, cluster, seed=None, **fields):
    answer = {
        "full_answerable": True,
        "answerable": True,
        "insufficient_for_full": False,
        "observed": True,
        "false_answer": False,
        "false_abstention": False,
        "privacy_incidents": 0,
    }
    answer.update(fields.pop("answer", {}))
    base = {
        "arm": arm,
        "query": query,
        "cluster": cluster,
        "seed": seed,
        "identity_applicable": True,
        "episode_top1": True,
        "complete_set": True,
        "cue_missing_fraction": 0,
        "cue_variant": "positive",
        "disposition": "OK",
        "answer": answer,
    }
    base.update(fields)
    return base


def test_metric_definitions_have_arm_independent_denominators_and_declared_failures():
    base = row("T1", "q", "c", 11)
    assert lh.identity(base) == 1.0 and lh.complete(base) == 1.0
    # A non-OK result on an identity-applicable query counts 0, never dropped.
    failed = row("T1", "q", "c", 11, episode_top1=None, disposition="ERROR")
    assert lh.identity(failed) == 0.0
    assert lh.identity(row("T1", "q", "c", 11, identity_applicable=False)) is None
    # complete applies only to full-answerable, no-missing-cue, positive-variant queries.
    for changed in (
        {"cue_missing_fraction": 0.5},
        {"cue_variant": "missing"},
        {"answer": {"full_answerable": False}},
    ):
        assert lh.complete(row("T1", "q", "c", 11, **changed)) is None
    assert lh.complete(row("T1", "q", "c", 11, complete_set=False)) == 0.0
    # false answer: evaluator-defined denominator; unobserved accepts nothing.
    insufficient = {"insufficient_for_full": True, "answerable": False}
    assert lh.false_answer(row("T1", "q", "c", 11)) is None
    assert (
        lh.false_answer(row("T1", "q", "c", 11, answer={**insufficient, "false_answer": True}))
        == 1.0
    )
    unobserved = {**insufficient, "observed": False, "false_answer": None}
    assert lh.false_answer(row("T1", "q", "c", 11, answer=unobserved)) == 0.0
    # false abstention: unobserved answerable counts 1 (intent to treat).
    assert lh.false_abstention(row("T1", "q", "c", 11)) == 0.0
    miss = {"observed": False, "false_abstention": None}
    assert lh.false_abstention(row("T1", "q", "c", 11, answer=miss)) == 1.0
    assert lh.false_abstention(row("T1", "q", "c", 11, answer={"answerable": False})) is None


def population(selected_wins=True, clusters=6, per_cluster=2):
    """T0 always wrong, T1 right on half, the selected arm right on every query."""
    rows = []
    for c in range(clusters):
        for q in range(per_cluster):
            name = f"q{c}-{q}"
            rows.append(row("T0", name, f"c{c}", None, episode_top1=False))
            for seed in (11, 29, 47):
                rows.append(row("T1", name, f"c{c}", seed, episode_top1=q == 0))
                rows.append(row("T5", name, f"c{c}", seed, episode_top1=selected_wins))
    return rows


def test_paired_contrast_expands_the_untrained_baseline_and_matches_hand_values():
    rows = population()
    c1 = lh.contrast(rows, "T5", "T0", "identity", [11, 29, 47])
    assert c1["difference"] == pytest.approx(1.0) and c1["clusters"] == 6
    assert c1["pairs"] == 6 * 2 * 3  # T0 repeated once per seed
    c2 = lh.contrast(rows, "T5", "T1", "identity", [11, 29, 47])
    assert c2["difference"] == pytest.approx(0.5)  # T1 right on 1 of 2 queries per cluster
    zero = lh.contrast(rows, "T1", "T1", "identity", [11, 29, 47])
    assert zero["difference"] == 0.0 and zero["confidence_interval"] == [0.0, 0.0]
    with pytest.raises(NornError, match="HELDOUT_CONTRAST_EMPTY"):
        lh.contrast(rows, "T5", "T9", "identity", [11, 29, 47])


def test_selection_uses_the_c1_point_estimate_and_breaks_ties_to_the_earlier_arm():
    table = {arm: {"difference": 0.1} for arm in lh.TRAINED}
    assert lh.select_arm(table) == "T1"
    table["T6"] = {"difference": 0.3}
    table["T4"] = {"difference": 0.3}
    assert lh.select_arm(table) == "T4"
    with pytest.raises(NornError, match="HELDOUT_SELECTION_ARMS"):
        lh.select_arm({"T1": {"difference": 1.0}})


def item(difference, low, high):
    return {"difference": difference, "confidence_interval": [low, high]}


def test_benefit_and_regression_bounds_are_the_approved_margins_exactly():
    assert lh.benefit(item(0.05, 0.01, 0.1)) is True
    assert lh.benefit(item(0.0499, 0.01, 0.1)) is False  # below the minimum benefit
    assert lh.benefit(item(0.2, 0.0, 0.4)) is False  # lower bound must be above zero
    assert lh.benefit({"difference": 0.5, "confidence_interval": None}) is False
    assert lh.regression("C3", item(0.0, -0.02, 0.1)) is True
    assert lh.regression("C3", item(0.0, -0.0201, 0.1)) is False
    assert lh.regression("C4", item(0.0, -0.1, 0.02)) is True
    assert lh.regression("C5", item(0.0, -0.1, 0.0201)) is False
    assert lh.regression("C4", {"difference": 0.0, "confidence_interval": None}) is None


def contrasts(c1, c2, c3=(0.0, -0.01, 0.01), c4=(0.0, -0.01, 0.01), c5=(0.0, -0.01, 0.01)):
    return {
        n: item(*v)
        for n, v in zip(("C1", "C2", "C3", "C4", "C5"), (c1, c2, c3, c4, c5), strict=True)
    }


def test_verdict_labels_cover_benefit_null_and_regression_with_a_failing_control():
    good = (0.2, 0.1, 0.3)
    assert (
        lh.verdict("T5", contrasts(good, good))["outcome"] == "MARGINS_MET_DEVELOPMENT_EXPLORATORY"
    )
    assert lh.verdict("T5", contrasts((0.01, -0.1, 0.1), good))["outcome"] == (
        "T0_RETAINED_NO_ARM_CLEARS_C1"
    )
    assert lh.verdict("T5", contrasts(good, (0.01, -0.1, 0.1)))["outcome"] == (
        "T1_RETAINED_SELECTED_DOES_NOT_CLEAR_C2"
    )
    worse = lh.verdict("T5", contrasts(good, good, c4=(0.05, 0.0, 0.1)))
    assert worse["outcome"] == "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED"
    assert worse["regressions"] == {"C3": True, "C4": False, "C5": True}
    only = {"C1": item(*good)}
    assert lh.verdict("T1", only)["outcome"] == "T1_SELECTED_C1_ONLY"
    assert lh.verdict("T1", {"C1": item(0.0, -0.1, 0.1)})["outcome"] == (
        "T0_RETAINED_NO_ARM_CLEARS_C1"
    )


def test_arm_sets_per_role_and_the_evaluation_role_waits_for_the_frozen_selection(tmp_path):
    tune = lh.conditions(tmp_path, "tune")
    assert [c.extra["arm"] for c in tune].count("T0") == 1 and len(tune) == 1 + 7 * 3
    assert tune[0].variant == "B0" and tune[0].checkpoint is None
    assert {c.variant for c in tune[1:]} == {"B3"} and {c.seed for c in tune[1:]} == {11, 29, 47}
    with pytest.raises(NornError, match="ARTIFACT_MISSING_OR_BUDGET"):
        lh.conditions(tmp_path, "evaluation")  # no selection yet: nothing may be scored
    (tmp_path / "selection.json").write_text(json.dumps({"selected": "T7"}), encoding="utf-8")
    arms = {c.extra["arm"] for c in lh.conditions(tmp_path, "evaluation")}
    assert arms == {"T0", "T1", "T7"}
    (tmp_path / "selection.json").write_text(json.dumps({"selected": "T1"}), encoding="utf-8")
    assert {c.extra["arm"] for c in lh.conditions(tmp_path, "evaluation")} == {"T0", "T1"}
    (tmp_path / "selection.json").write_text(json.dumps({"selected": "T0"}), encoding="utf-8")
    with pytest.raises(NornError, match="HELDOUT_SELECTION_INVALID"):
        lh.conditions(tmp_path, "evaluation")
    with pytest.raises(NornError, match="HELDOUT_ROLE"):
        lh.conditions(tmp_path, "calibration")


def test_summary_reports_every_arm_with_applicable_denominators():
    rows = population(clusters=1, per_cluster=2)
    summary = lh.arm_summary(rows)
    assert set(summary) == {"T0", "T1", "T5"}
    assert summary["T0"]["identity"] == {"applicable": 2, "positive": 0.0, "rate": 0.0}
    assert summary["T1"]["identity"]["applicable"] == 6  # 2 queries x 3 seeds
    assert summary["T1"]["identity"]["rate"] == pytest.approx(0.5)
    assert summary["T5"]["episode_top1_not_observed"] == 0


def _tiny_run(root):
    """A manifest-bound run with one tune and one evaluation artifact and no checkpoints."""
    canonical, file_digest = lh.canonical, lh.file_digest
    artifacts = {}
    for role in lh.ROLES:
        name = f"evaluator/{role}/q.json"
        (root / name).parent.mkdir(parents=True)
        (root / name).write_text(f'{{"role": "{role}"}}', encoding="utf-8")
        artifacts[name] = file_digest(root / name)
    manifest = {
        "schema": 1,
        "kind": "P05_LOSS_HELDOUT",
        "sealed": False,
        "smoke": False,
        "code_digest": lh.code_digest(),
        "config": json.loads(canonical(lh.CONFIG)),
        "environment": lh.environment(),
        "artifacts": artifacts,
        "checkpoints": {},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return artifacts


def test_tune_phase_check_never_opens_the_evaluation_role_files(tmp_path):
    artifacts = _tiny_run(tmp_path)
    assert lh.checked(tmp_path, "tune") and lh.checked(tmp_path)
    # Positive control: changing a tune artifact fails every check.
    tune_file = tmp_path / "evaluator/tune/q.json"
    tune_file.write_text('{"role": "tampered"}', encoding="utf-8")
    for role in ("tune", None):
        with pytest.raises(NornError, match="HELDOUT_ARTIFACT_CHANGED"):
            lh.checked(tmp_path, role)
    tune_file.write_text('{"role": "tune"}', encoding="utf-8")
    assert lh.checked(tmp_path, "tune")
    # Custody control: an evaluation artifact that is missing entirely cannot fail a tune check,
    # so tune-phase work does not read evaluation-role bytes; the full check still refuses it.
    (tmp_path / "evaluator/evaluation/q.json").unlink()
    assert "evaluator/evaluation/q.json" in artifacts
    assert lh.checked(tmp_path, "tune")
    with pytest.raises(NornError):
        lh.checked(tmp_path, "evaluation")
    with pytest.raises(NornError, match="HELDOUT_ROLE"):
        lh.checked(tmp_path, "calibration")


@pytest.mark.skipif(
    not (FACTORIAL / "training.json").exists()
    or not (SOURCE / "manifest.json").exists()
    or not MODELS.exists(),
    reason="needs the local P05 factorial run, the P04 source run and the local models",
)
def test_smoke_scores_tune_then_selects_then_scores_evaluation_once(tmp_path):
    root = tmp_path / "heldout"
    lh.prepare(root, FACTORIAL, SOURCE, wall_cap_seconds=600, smoke=True)
    manifest = lh.checked(root)
    assert {k: len(v) for k, v in manifest["planned"].items()} == {"tune": 2, "evaluation": 2}
    with pytest.raises(NornError, match="HELDOUT_SELECTION_MISSING"):
        lh.score(root, MODELS, "evaluation", enabled=True, wall_cap_seconds=600)
    assert not (root / "ledger-evaluation.jsonl").exists()
    lh.score(root, MODELS, "tune", enabled=True, wall_cap_seconds=900)
    with pytest.raises(NornError, match="HELDOUT_ROLE_ALREADY_SCORED"):
        lh.score(root, MODELS, "tune", enabled=True, wall_cap_seconds=900)
    selection = lh.select(root, MODELS)
    assert selection["selected"] in lh.TRAINED
    lh.score(root, MODELS, "evaluation", enabled=True, wall_cap_seconds=900)
    value = lh.report(root, MODELS)
    assert set(value["summaries"]) == {"T0", "T1", selection["selected"]}
    assert value["scope"] == lh.CONFIG["status"] and value["verdict"]["outcome"]
    rows = lh.observations(root, MODELS, "tune")
    assert len(rows) == 2 * (1 + 7 * 3) and all(
        r["disposition"] in {"OK", "UNSUPPORTED"} for r in rows
    )
