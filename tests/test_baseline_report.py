"""Hand controls plus an explicit reopened real-ledger proof, without rerunning inference."""

import argparse
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from benchmark.adapters.baseline import interpret, spec
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs.baselines import quantiles, report
from norn.canonical.registry import WriteRequest
from norn.contracts.errors import NornError
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
from norn.contracts.time import TimeKind, TimeValue, parse_instant
from norn.extraction.atoms import FixtureAtom


def test_baseline_profile_and_public_question_constraints():
    world = build_world(47, partition(47, "development"))
    published = publish(scenarios(world)[0], (world.gold_canary,))
    query = interpret(published, "R3")
    assert query.requested_fields == ("parked_in",) and query.subject in published.query.text
    assert query.event_start.isoformat().startswith("2026-10-20")
    assert query.event_end - query.event_start == timedelta(days=1)
    assert spec("R0").tokenizer == spec("R3").tokenizer
    assert spec("R0").model == "NONE" and spec("R1").model != "NONE"
    with pytest.raises(NornError, match="UNSUPPORTED_ARM"):
        spec("invented")


def test_latency_control_uses_explicit_nearest_rank_and_empty_denominators():
    assert quantiles([]) == {"p50_ms": None, "p95_ms": None, "p99_ms": None}
    assert quantiles([1_000_000, 2_000_000, 3_000_000, 4_000_000]) == {
        "p50_ms": 2.0,
        "p95_ms": 4.0,
        "p99_ms": 4.0,
    }


def test_chain_root_is_a_cue_and_unsupported_path_goal_is_not_one_field():
    world = build_world(47, partition(47, "development"))
    case = next(case for case in scenarios(world) if case.gold.family == "E3")
    public = publish(case, (world.gold_canary,))
    query = interpret(public, "R3")
    assert query.subject is None and query.requested_fields == ()
    assert len({s.observation.actor for s in public.sources}) > 1


def test_missing_source_field_cannot_remove_an_explicit_question_prerequisite(engine):
    world = build_world(47, partition(47, "development"))
    public = next(
        published
        for case in scenarios(world)
        if "release and rollback" in case.query.text
        for published in (publish(case, (world.gold_canary,)),)
        if {s.observation.predicate for s in published.sources} == {"release"}
    )
    assert interpret(public, "R0").requested_fields == ("release", "rollback")
    # An unavailable source changes evidence, not the meaning of the same question.
    assert interpret(replace(public, sources=()), "R3").requested_fields == ("release", "rollback")
    source = public.sources[0]
    observation = source.observation
    translated = replace(
        public,
        query=replace(public.query, text=f"Pasangan rilis dan rollback untuk {observation.actor}?"),
    )
    assert interpret(translated, "R0").requested_fields == ("release", "rollback")
    content = source.text.encode()
    event = parse_instant(observation.event_time)
    engine.write(
        WriteRequest(
            "partial-pair",
            "operator",
            "partial-pair",
            "partial-pair",
            content,
            TimeValue(TimeKind.EXACT, event),
            event,
            (
                FixtureAtom(
                    observation.actor,
                    "release",
                    TaggedValue("TEXT", observation.value),
                    0,
                    len(content),
                    EpistemicState(Epistemic(observation.origin)),
                ),
            ),
        )
    )
    engine.project()
    for question in (public, translated):
        result = engine.recall(interpret(question, "R0")).serialize()
        assert result["status"] == "PARTIALLY_SUPPORTED", result
        assert result["missing_fields"] == ["rollback"]
        assert [r["text"] for r in result["evidence"]] == [source.text]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--model-root", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.run, args.model_root)
    ledger = [json.loads(line) for line in (args.run / "ledger.jsonl").read_text().splitlines()]
    assert result["pairs"] == len(ledger) and set(result["arms"]) == {"R0", "R1", "R2", "R3"}
    assert set(result["strata"]["family"]) == {f"E{i}" for i in range(1, 15)}
    for arm in result["arms"]:
        assert result["arms"][arm]["planned"] == sum(row["arm_id"] == arm for row in ledger)
        diagnostics = [
            row["baseline_diagnostics"]
            for row in ledger
            if row["arm_id"] == arm and row["baseline_diagnostics"]
        ]
        assert result["costs"][arm]["model_attempts_cold"] == sum(
            d["trace"]["usage"]["model_calls"] for d in diagnostics
        )
    print(
        json.dumps({"pairs": result["pairs"], "families": 14, "reopened_evidence_and_costs": True})
    )
