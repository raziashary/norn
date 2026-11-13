import ast
import inspect
import json
from pathlib import Path

import pytest

from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import Case, scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs import e3_mechanism
from benchmark.runs.e3_mechanism import classify, records_from, replay, replay_run
from norn.contracts.errors import NornError

_CASES = scenarios(build_world(47, partition(47, "smoke")))
RUN = Path(".norn/p05-pre-r-002")


def _chain(slots: int = 4) -> Case:
    return next(
        c
        for c in _CASES
        if c.gold.family == "E3" and c.gold.variant == "positive" and len(c.gold.slots) == slots
    )


def _evidence(case: Case, keep: tuple[int, ...]) -> list[dict]:
    """Exposed records for the chosen chain links, shaped like a stored packet."""
    out = []
    for index in keep:
        s = case.sources[index]
        out.append(
            {
                "namespace": s.namespace,
                "event_id": s.event_id,
                "atom_id": "atom_" + str(index),
                "subject_id": "entity_" + s.observation.actor,
                "aliases": [s.observation.actor],
                "predicate": s.observation.predicate,
                "value_json": json.dumps(s.observation.value),
                "qualifiers_json": "[]",
                "origin": s.observation.origin,
                "authority": "UNVERIFIED",
                "status": "ACTIVE",
                "applicability": "CURRENT",
                "event_time": s.observation.event_time,
                "source_id": "engine_internal_" + str(index),
                "source_version": "v",
                "start_byte": 0,
                "end_byte": 1,
                "sha256": "0" * 64,
                "text": "x",
                "snapshot": 1,
            }
        )
    return out


def _observe(case: Case, keep: tuple[int, ...], status: str, reason: str):
    published = publish(case)
    packet = {
        "status": status,
        "reason": reason,
        "missing_fields": [],
        "evidence": _evidence(case, keep),
    }
    result = {
        "disposition": "OK",
        "candidates": [{"source_id": case.sources[i].source_id} for i in keep],
    }
    return published, replay(published, "R0", packet, result)


def test_chain_query_withholds_fields_and_the_gate_rule_would_also_abstain():
    case = _chain()
    published, row = _observe(case, (0, 1, 2, 3), "NOT_ESTABLISHED", "MISSING_CASE_INPUT")
    assert row["adapter_fields"] == []
    assert row["reproduced"] is True and row["replayed_reason"] == "MISSING_CASE_INPUT"
    assert row["counterfactual_fields"] == ["requires"]
    assert row["counterfactual_reason"] == "AMBIGUOUS"
    # Negative control: every slot retrieved. This must not be filed as a retrieval failure.
    out = classify(row, case.gold, published)
    assert out["complete_set"] is True and out["slot_coverage"] == 1.0
    assert out["false_abstention"] is True and out["mechanism"] == "ADAPTER_AND_GATE_RULE"


def test_incomplete_evidence_is_reported_as_recall_not_as_a_gate_effect_alone():
    case = _chain()
    published, row = _observe(case, (0, 3), "NOT_ESTABLISHED", "MISSING_CASE_INPUT")
    out = classify(row, case.gold, published)
    assert out["complete_set"] is False and out["slot_coverage"] == 0.5
    assert out["mechanism"] == "RECALL_ADAPTER_AND_GATE_RULE"


def test_a_single_link_passes_the_field_only_gate_so_it_cannot_tell_chain_completeness():
    case = _chain()
    _, row = _observe(case, (0,), "NOT_ESTABLISHED", "MISSING_CASE_INPUT")
    assert row["counterfactual_status"] == "SUPPORTED"
    assert row["counterfactual_reason"] == "SUFFICIENT"


def test_a_non_chain_query_keeps_its_fields_and_is_not_filed_as_adapter_suppression():
    case = next(c for c in _CASES if c.gold.family == "E1" and c.gold.variant == "positive")
    published = publish(case)
    packet = {"status": "SUPPORTED", "reason": "SUFFICIENT", "missing_fields": [], "evidence": []}
    row = replay(published, "R0", packet, {"disposition": "OK", "candidates": []})
    assert row["adapter_fields"] != []


def test_failed_rows_are_retained_with_a_reason_not_dropped():
    case = _chain()
    published = publish(case)
    row = replay(published, "R0", {}, {"disposition": "UNSUPPORTED", "candidates": []})
    assert row["replayable"] is False and row["replay_reason"] == "UNSUPPORTED"
    out = classify(row, case.gold, published)
    assert out["false_abstention"] is None and out["mechanism"] is None


def test_the_replay_takes_no_gold_input():
    tree = ast.parse(inspect.getsource(replay))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        a.arg for a in ast.walk(tree) if isinstance(a, ast.arg)
    }
    assert not {n for n in names if "gold" in n.lower()}
    case = _chain()
    _, row = _observe(case, (0, 1), "NOT_ESTABLISHED", "MISSING_CASE_INPUT")
    other = next(c for c in _CASES if c.gold.family == "E1")
    # Labels from an unrelated case change only the evaluator join, never the gate side.
    assert (
        classify(row, other.gold, publish(case))["counterfactual_reason"]
        == row["counterfactual_reason"]
    )


def test_a_record_with_an_unknown_key_is_a_schema_failure():
    item = _evidence(_chain(), (0,))[0]
    assert len(records_from([item])) == 1
    with pytest.raises(NornError) as caught:
        records_from([{**item, "surprise": 1}])
    assert caught.value.code == "EVIDENCE_RECORD_SCHEMA"


def test_a_changed_ledger_is_rejected_before_any_replay(tmp_path: Path):
    for name, body in (("ledger.jsonl", "{}\n"), ("manifest.json", "{}")):
        (tmp_path / name).write_text(body, encoding="utf-8")
    (tmp_path / "completion.json").write_text(
        json.dumps({"ledger_digest": "0" * 64, "manifest_digest": "0" * 64}), encoding="utf-8"
    )
    with pytest.raises(NornError) as caught:
        replay_run(tmp_path)
    assert caught.value.code == "LEDGER_CHANGED"


@pytest.mark.skipif(not RUN.is_dir(), reason="stored p05-pre-r-002 run is local and untracked")
def test_the_stored_baseline_run_reproduces_its_reported_numbers():
    result = replay_run(RUN)
    summary = result["summary"]
    assert summary["unreproduced"] == 0 and summary["not_replayable"] == 0
    assert summary["observed_reasons"] == {"MISSING_CASE_INPUT": 24}
    assert summary["counterfactual_rules"] == {"AMBIGUOUS": 24}
    assert summary["mechanisms"] == {
        "ADAPTER_AND_GATE_RULE": 5,
        "RECALL_ADAPTER_AND_GATE_RULE": 19,
    }
    report = json.loads((Path(".norn") / "p05-pre-r-002-baseline-report.json").read_text("utf-8"))
    for arm, counts in summary["by_arm"].items():
        stored = report["strata"]["family"][e3_mechanism.FAMILY][arm]
        assert counts["complete_sets"] == stored["complete_set_itt_numerator"]
        assert counts["false_abstentions"] == stored["false_abstentions"]
