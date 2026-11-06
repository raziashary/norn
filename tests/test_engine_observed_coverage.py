"""E12 measures the engine's own coverage answer, never a flag carried by the public query."""

from types import SimpleNamespace

from conftest import clock, request

from benchmark.adapters.common import CommonControl
from benchmark.adapters.contracts import Query
from benchmark.adapters.r7 import BindingAdapter
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.metrics.abstention import abstention_score
from benchmark.metrics.retrieval import retrieval_scores
from benchmark.runs.runner import arm_spec
from norn.retrieval.contracts import RecallRequest


def e12(variant):
    cases = scenarios(build_world(47, partition(47, "smoke")))
    return next(c for c in cases if c.gold.family == "E12" and c.gold.variant == variant)


def test_public_query_has_no_coverage_flag_and_gold_declares_the_injected_outage():
    assert "coverage_state" not in Query.__dataclass_fields__
    case = e12("ambiguous")
    assert "coverage" not in str(publish(case).payload()["query"]).lower()
    assert case.gold.projection_state == "UNAVAILABLE"
    assert case.gold.reason == "PROJECTION_NOT_READY"
    assert e12("positive").gold.projection_state == "CANONICAL_FALLBACK"


def test_engine_reports_the_outage_itself_and_recovers_when_the_projection_exists(engine):
    engine.write(request("e12"))
    query = RecallRequest("Alex parking", clock(), subject="Alex", requested_fields=("parked_in",))
    outage = engine.recall(query).serialize()
    assert outage["status"] == "VERIFICATION_UNAVAILABLE"
    assert outage["reason"] == "PROJECTION_NOT_READY" and outage["evidence"] == []
    engine.project()
    ready = engine.recall(query).serialize()
    assert ready["status"] == "SUPPORTED" and ready["evidence"]


def test_a_source_reading_control_gets_no_credit_for_an_outage_it_cannot_observe():
    case = e12("ambiguous")
    public = publish(case)
    result = CommonControl("extractive").query(public)
    # Before the repair every arm short-circuited to the expected answer on the public flag.
    assert result.evidence_status != "VERIFICATION_UNAVAILABLE"
    retrieval = retrieval_scores(public, result, arm_spec("extractive"), case.gold)
    score = abstention_score(
        result, case.gold, retrieval["complete_set"], retrieval["partial_set"], None
    )
    assert score["status_correct"] is False


def test_binding_adapter_scores_an_engine_reported_outage_but_not_other_failures():
    public = publish(e12("ambiguous"))

    def packet(reason):
        return {
            "status": "VERIFICATION_UNAVAILABLE",
            "evidence": [],
            "reason": reason,
            "coverage": "UNAVAILABLE",
            "missing_fields": [],
            "binding_ranking": [],
        }

    def run(reason):
        engine = SimpleNamespace(
            recall_binding=lambda *a: SimpleNamespace(serialize=lambda: packet(reason))
        )
        return BindingAdapter(engine, public, {}).query("B0")[0]

    outage = run("BINDING_PROJECTION_NOT_READY")
    assert outage.disposition == "OK" and outage.evidence_status == "VERIFICATION_UNAVAILABLE"
    assert outage.reason == "PROJECTION_NOT_READY"
    broken = run("BINDING_READBACK")
    assert broken.disposition == "ERROR" and broken.evidence_status is None
