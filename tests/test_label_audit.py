from dataclasses import replace

import pytest
from conftest import REPO

from benchmark.fixtures.audit import (
    Judgment,
    audit_state,
    audit_summary,
    binding,
    load_attestations,
    load_judgments,
    previous_sample,
    stratified_sample,
    write_audit_pack,
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
    named = frozenset({"fixture-A", "fixture-B", "fixture-C"})
    assert audit_state(case, (a,), named) == "HUMAN_REVIEWED"
    assert audit_state(case, (a, b), named) == "DISPUTED"
    assert audit_state(case, (a, b, c), named) == "ADJUDICATED"
    # Declared independence carries no weight until the owner attests the annotator.
    assert audit_state(case, (a,)) == "PENDING_HUMAN_REVIEW"
    assert audit_state(case, (a,), frozenset({"someone-else"})) == "PENDING_HUMAN_REVIEW"
    with pytest.raises(NornError, match="STALE_AUDIT_BINDING"):
        audit_state(case, (replace(a, source_digest="wrong"),), named)


def test_sample_covers_every_family_twin_and_language_and_contains_the_v1_sample():
    cases = scenarios(build_world(47, partition(47, "smoke")))
    sample = stratified_sample(cases)
    assert len(sample) == 126
    assert len({(c.gold.family, c.gold.variant, c.gold.language) for c in sample}) == 126
    for family in {c.gold.family for c in sample}:
        assert {c.gold.language for c in sample if c.gold.family == family} == {"en", "id", "mixed"}
    earlier = previous_sample(cases)
    assert len(earlier) == 42 and {c.query.query_id for c in earlier} <= {
        c.query.query_id for c in sample
    }


def test_actual_owner_records_count_only_when_current_and_attested(tmp_path):
    cases = scenarios(build_world(47, partition(47, "smoke")))
    judgments = load_judgments(REPO / "docs/development/evidence/label_judgments.json")
    attestation = REPO / "docs/development/evidence/label_attestation.json"
    judgments_file = REPO / "docs/development/evidence/label_judgments.json"
    attested = load_attestations(attestation, judgments_file)
    assert attested == {"project-owner"}
    # Negative control: the statement covers one exact judgments file; a changed file (a new or
    # edited judgment) attests no one until the owner renews the statement.
    changed = tmp_path / "judgments.json"
    changed.write_bytes(judgments_file.read_bytes() + b" ")
    assert load_attestations(attestation, changed) == frozenset()
    assert {j.annotator for j in judgments} == {"project-owner"}
    assert all(j.role == "HUMAN" and j.independent for j in judgments)
    summary = audit_summary(cases, judgments, attested)
    # 42 earlier reviews: the E12 ambiguous gold changed (engine-observed outage), so its record
    # is stale and that case returns to review, along with every case the V1 rotation never saw.
    assert summary["stale_judgments"] == 1 and summary["reviewed_sample"] == 41
    assert summary["sample_size"] == 126 and summary["state"] == "PENDING_OR_DISPUTED"
    assert summary["states"] == {"HUMAN_REVIEWED": 41, "PENDING_HUMAN_REVIEW": 85}
    # Negative control: without the attestation record nothing counts as human-reviewed.
    bare = audit_summary(cases, judgments)
    assert bare["reviewed_sample"] == 0 and bare["unattested_annotators"] == ["project-owner"]
    # The pending pack lists only the 85 cases that still need the owner.
    pack = tmp_path / "pending-pack.md"
    write_audit_pack(cases, pack, judgments, attested)
    assert pack.read_text(encoding="utf-8").count("## E") == 85
