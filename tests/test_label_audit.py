from dataclasses import replace
from pathlib import Path

import pytest

from benchmark.fixtures.audit import (
    Judgment,
    audit_state,
    audit_summary,
    binding,
    load_judgments,
    stratified_sample,
)
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from norn.contracts.errors import NornError


def test_human_audit_states_and_changed_source_binding():
    case = scenarios(build_world(47, partition(47, "smoke")))[0]
    source, gold = binding(case)
    simulation = Judgment(
        case.query.query_id,
        "simulated-author",
        "TEST_FIXTURE",
        False,
        source,
        gold,
        True,
        "Synthetic record for mechanics only",
    )
    assert audit_state(case, (simulation,)) == "PENDING_HUMAN_REVIEW"
    with pytest.raises(NornError, match="FALSE_HUMAN_INDEPENDENCE"):
        replace(simulation, independent=True)
    # Synthetic unit controls of HUMAN schema; these are never production audit records.
    a = replace(simulation, annotator="fixture-A", role="HUMAN", independent=True)
    b = replace(a, annotator="fixture-B", agrees=False)
    c = replace(a, annotator="fixture-C", adjudicates=("fixture-A", "fixture-B"))
    assert audit_state(case, (a,)) == "HUMAN_REVIEWED"
    assert audit_state(case, (a, b)) == "DISPUTED"
    assert audit_state(case, (a, b, c)) == "ADJUDICATED"
    with pytest.raises(NornError, match="STALE_AUDIT_BINDING"):
        audit_state(case, (replace(a, source_digest="wrong"),))


def test_sample_covers_all_families_twins_and_languages():
    sample = stratified_sample(scenarios(build_world(47, partition(47, "smoke"))))
    assert len(sample) == 42
    assert len({(c.gold.family, c.gold.variant) for c in sample}) == 42
    for family in {c.gold.family for c in sample}:
        assert {c.gold.language for c in sample if c.gold.family == family} == {"en", "id", "mixed"}


def test_actual_owner_records_are_bound_to_current_sample():
    cases = scenarios(build_world(47, partition(47, "smoke")))
    judgments = load_judgments(Path("docs/development/evidence/label_judgments.json"))
    summary = audit_summary(cases, judgments)
    assert summary["state"] == "SAMPLE_REVIEWED"
    assert summary["reviewed_sample"] == summary["sample_size"] == 42
    assert {j.annotator for j in judgments} == {"project-owner"}
    assert all(j.role == "HUMAN" and j.independent for j in judgments)
