"""Instrument controls plus an actual full-run reader when invoked as a script."""

import argparse
import json
from pathlib import Path

import numpy as np
import pytest

from benchmark.fixtures.binding_cases import cases
from benchmark.fixtures.publication import check_import_barrier, publish
from benchmark.runs.binding import training_targets
from benchmark.runs.binding_report import conditional, validate_packet
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical, digest


def test_binding_roles_are_disjoint_before_wording_and_keep_all_categories():
    datasets = {role: cases(role) for role in ("train", "tune", "evaluation")}
    identities = {}
    for role, values in datasets.items():
        assert {c.gold.family for c in values} == {f"E{i}" for i in range(1, 15)}
        identities[role] = {c.gold.cluster for c in values}
        assert any(c.gold.variant == "action-ambiguous" for c in values)
        for case in values:
            public = publish(case)
            assert "__GOLD_CANARY__" not in canonical(public.payload())
    assert not identities["train"] & identities["tune"]
    assert not identities["train"] & identities["evaluation"]
    assert not identities["tune"] & identities["evaluation"]
    assert digest(canonical([c.query.query_id for c in cases("evaluation")]).encode()) == digest(
        canonical([c.query.query_id for c in datasets["evaluation"]]).encode()
    )
    check_import_barrier(Path("src/norn"), Path("benchmark/adapters"))


def test_identical_facets_do_not_create_conditional_information():
    from types import SimpleNamespace

    vector = (np.ones(384) / np.sqrt(384)).tolist()
    captured = {
        "query": vector,
        "memories": [
            {
                "event_id": "a",
                "source_ids": ["a"],
                "facets": [vector] * 3,
                "single": vector,
                "mask": [True] * 3,
            },
            {
                "event_id": "b",
                "source_ids": ["b"],
                "facets": [vector] * 3,
                "single": vector,
                "mask": [True] * 3,
            },
        ],
    }
    gold = SimpleNamespace(acceptable_sets=(("a",),))
    for variant in ("B1", "B2"):
        controls = conditional(captured, gold, variant, None)
        assert controls["none"] == controls["duplicate_semantic"]
        # Equal geometry ties are broken by identity before B1's RRF ranks;
        # its resulting rank-score gap is not a semantic distance or benefit.
        expected = 1 / 61 - 1 / 62 if variant == "B1" else 0
        assert controls["none"]["target_margin"] == pytest.approx(expected)


def test_real_ambiguous_case_never_makes_a_compatible_episode_negative():
    from dataclasses import asdict

    case = next(c for c in cases("train") if c.gold.family == "E1" and c.gold.reason == "AMBIGUOUS")
    captured = {"memories": [{"source_ids": [s.source_id]} for s in publish(case).sources]}
    targets = training_targets(asdict(case.gold), captured)
    assert len(targets) > 1 and all(targets)
    positive = next(
        c for c in cases("train") if c.gold.family == "E1" and c.gold.expected_status == "SUPPORTED"
    )
    captured = {"memories": [{"source_ids": [s.source_id]} for s in publish(positive).sources]}
    targets = training_targets(asdict(positive.gold), captured)
    assert any(targets) and not all(targets)


def test_result_packet_boundary_rejects_rehashed_claims_before_source_setup(tmp_path):
    from copy import deepcopy
    from dataclasses import asdict
    from types import SimpleNamespace

    from benchmark.adapters.contracts import Result

    public = SimpleNamespace(query=SimpleNamespace(coverage_state="CANONICAL_FALLBACK"))
    result = asdict(Result("UNSUPPORTED", None, (), reason="FEATURE_NOT_SUPPORTED"))
    row = {
        "result": result,
        "diagnostic": {"early": True, "first_result": deepcopy(result)},
        "failure_stage": "NONE",
    }
    validate_packet(tmp_path, row, public, {}, None, None)
    row["result"]["reason"] = "CHANGED_REHASHED_CLAIM"
    with pytest.raises(NornError, match="BINDING_RESULT_PACKET_CHANGED"):
        validate_packet(tmp_path, row, public, {}, None, None)


@pytest.mark.parametrize(
    "reason,disposition", (("QUERY_DEADLINE", "TIMEOUT"), ("MODEL_WORKER_EXITED", "ERROR"))
)
def test_adapter_failure_envelopes_are_results_not_answer_accuracy(reason, disposition):
    from types import SimpleNamespace

    from benchmark.adapters.r7 import BindingAdapter

    public = publish(cases("train", smoke=True)[0])
    packet = {
        "status": "VERIFICATION_UNAVAILABLE",
        "evidence": [],
        "reason": reason,
        "coverage": "UNAVAILABLE",
        "missing_fields": [],
        "binding_ranking": [],
    }
    engine = SimpleNamespace(recall_binding=lambda *args: SimpleNamespace(serialize=lambda: packet))
    result, diagnostic = BindingAdapter(engine, public, {}).query("B0")
    assert result.disposition == disposition and result.evidence_status is None
    assert not result.candidates and diagnostic["packet"]["reason"] == reason


if __name__ == "__main__":
    from benchmark.runs.binding_report import report

    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--model-root", type=Path, required=True)
    args = parser.parse_args()
    observed = report(args.run, args.model_root)
    assert set(observed["strata"]["family"]) == {f"E{i}" for i in range(1, 15)}
    assert len(observed["training"]["jobs"]) == 12
    assert observed["pairs"] == (450 if observed["arms"]["B0"]["unique_queries"] == 15 else 4140)
    print(
        json.dumps(
            {
                "pairs": observed["pairs"],
                "all_categories": True,
                "source_geometry_packet_readback": True,
                "outcome": observed["scientific_outcome"],
            }
        )
    )
