import json
import re

import pytest
from conftest import REPO

from benchmark.runs import loss_heldout as lh

DEVELOPMENT = REPO / "docs" / "development"
REPORT = DEVELOPMENT / "evidence" / "losses_and_separation.md"
PROPOSAL = DEVELOPMENT / "evidence" / "p05_r09_margin_proposal.md"
ADR = DEVELOPMENT / "ADR_LOG.md"
RISKS = DEVELOPMENT / "RISKS_AND_OPEN_QUESTIONS.md"
HELDOUT_REPORT = REPO / ".norn" / "p05-t03-heldout-002-report.json"
TRAINING = REPO / ".norn" / "p05-t03-001" / "training.json"
TEXT = REPORT.read_text(encoding="utf-8")
LABELS = {
    "T0_RETAINED_NO_ARM_CLEARS_C1",
    "T1_RETAINED_SELECTED_DOES_NOT_CLEAR_C2",
    "MARGINS_MET_DEVELOPMENT_EXPLORATORY",
    "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED",
    "T1_SELECTED_C1_ONLY",
}
SEED_ROW = re.compile(
    r"^\| (T[1-7]) \| (\d+) \| ([\d,]+) \| (\d+) \| (\d+) \| ([\d.]+) \| ([\d,]+) \| "
    r"`([0-9a-f]{12})` \|$",
    re.M,
)


def contrast(difference, low, high):
    return {"difference": difference, "confidence_interval": [low, high]}


def test_report_states_the_decision_the_frozen_verdict_function_produces():
    assert {label for label in LABELS if f"`{label}`" in TEXT} == {"T0_RETAINED_NO_ARM_CLEARS_C1"}
    # The recorded C1 contrast (point +0.0952, interval [0.000, 0.2619]) reproduces that label...
    recorded = {"C1": contrast(0.09523809523809523, 0.0, 0.2619047619047619)}
    assert lh.verdict("T1", recorded)["outcome"] == "T0_RETAINED_NO_ARM_CLEARS_C1"
    # ...and the same point estimate with a lower bound above zero would be a different result.
    cleared = {"C1": contrast(0.09523809523809523, 0.0001, 0.2619047619047619)}
    assert lh.verdict("T1", cleared)["outcome"] == "T1_SELECTED_C1_ONLY"
    assert "Retained code for the P06 graph study: T0" in TEXT
    assert "T1–T7 are not retained" in TEXT


def test_margins_quoted_in_the_report_are_the_frozen_ones():
    margins = lh.CONFIG["margins"]
    assert (margins["minimum_benefit"], margins["maximum_regression"]) == (0.05, 0.02)
    assert "**+0.05**" in TEXT and "**0.02**" in TEXT
    proposal = PROPOSAL.read_text(encoding="utf-8")
    assert "+0.05" in proposal and "0.02" in proposal and "APPROVED AS WRITTEN" in proposal
    # A margin revised after the result would no longer match the code frozen at this commit.
    assert "e47bf6f" in TEXT and "post-result margin revision" in TEXT


def test_every_arm_and_every_seed_is_preserved_with_its_raw_numbers():
    found = sorted((arm, int(seed)) for arm, seed, *_ in SEED_ROW.findall(TEXT))
    assert found == [(f"T{a}", s) for a in range(1, 8) for s in (11, 29, 47)]
    for arm in ("T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7"):
        assert re.search(rf"^\| {arm} \| \d+/\d+ = ", TEXT, re.M)
    assert "UNSUPPORTED rows are results, not drops" in TEXT
    assert "p05-t03-heldout-001" in TEXT  # the interrupted attempt stays visible


def test_limits_the_graph_study_must_read_are_named_and_exist_in_the_risk_register():
    risks = RISKS.read_text(encoding="utf-8")
    for risk in ("R33", "R35", "R37", "R38"):
        assert risk in TEXT and f"| {risk} |" in risks
    assert "no language-transfer claim is made" in TEXT


def test_adr_records_the_decision_with_the_required_fields():
    section = ADR.read_text(encoding="utf-8").split("## ADR-0028", 1)[1].split("\n## ADR-", 1)[0]
    for field in (
        "Status",
        "Question",
        "Why",
        "Options",
        "Recommendation / decision",
        "What affects what",
        "My answer (editable)",
        "Authority",
        "Verification",
    ):
        assert f"**{field}:**" in section
    assert "T0" in section and "losses_and_separation.md" in section


@pytest.mark.skipif(not HELDOUT_REPORT.exists(), reason="needs the local held-out report")
def test_report_numbers_match_the_recorded_held_out_report():
    recorded = json.loads(HELDOUT_REPORT.read_text(encoding="utf-8"))
    assert recorded["verdict"]["outcome"] == "T0_RETAINED_NO_ARM_CLEARS_C1"
    c1 = recorded["contrasts"]["C1"]
    assert f"{c1['difference']:+.4f}" in TEXT
    assert f"{c1['bootstrap_p_two_sided']:.4f}" in TEXT
    assert recorded["config"]["margins"] == lh.CONFIG["margins"]
    for arm, entry in recorded["summaries"].items():
        positive = round(entry["identity"]["rate"] * entry["identity"]["applicable"])
        assert f"| {arm} | {positive}/{entry['identity']['applicable']} = " in TEXT


@pytest.mark.skipif(not TRAINING.exists(), reason="needs the local factorial run")
def test_per_seed_table_matches_the_recorded_training_receipts():
    training = json.loads(TRAINING.read_text(encoding="utf-8"))
    expected = {
        (j["arm"], str(j["seed"])): (
            f"{j['receipt']['parameters']:,}",
            str(j["receipt"]["nonzero_gradient_steps"]),
            j["sha256"][:12],
        )
        for j in training["jobs"]
    }
    found = {(a, s): (p, n, h) for a, s, p, _u, n, _t, _b, h in SEED_ROW.findall(TEXT)}
    assert found == expected
