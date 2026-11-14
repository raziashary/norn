"""P06-T20: public-v2 baseline run controls that need no local models.

The real R0 to R3 observations are produced by ``norn-benchmark run-multihop-baselines`` and
reloaded by ``multihop-report`` (see EVIDENCE_LOG E-P06-007); a model-free suite cannot rerun
them, so this file proves the guards, scoring and wiring around that run.
"""

import json
from pathlib import Path

import pytest
from test_multihop_fixtures import first

from benchmark.adapters.baseline import interpret
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs import multihop_run
from benchmark.runs.multihop_run import (
    ARMS,
    CEILING,
    FLOOR,
    STRATA,
    _cell,
    _check_cap,
    cases_for,
    report_multihop,
    run_multihop,
    validate_multihop,
)
from norn.contracts.errors import NornError


def row(
    complete: bool | None, *, supported: bool = True, status_ok: bool = True, observed: bool = True
):
    return {
        "retrieval": {"complete_set": complete},
        "answer": {
            "full_answerable": supported,
            "insufficient_for_full": not supported,
            "observed": observed,
            "status_correct": status_ok if observed else None,
            "false_answer": False if observed else None,
            "false_abstention": False if observed else None,
            "privacy_incidents": 0,
        },
    }


def test_slot_recall_saturation_and_status_are_scored_separately():
    perfect = _cell([row(True) for _ in range(10)])
    empty = _cell([row(False) for _ in range(10)])
    middle = _cell([row(True) for _ in range(5)] + [row(False) for _ in range(5)])
    assert (perfect["slot_recall"], perfect["saturation"]) == (1.0, "CEILING")
    assert (empty["slot_recall"], empty["saturation"]) == (0.0, "FLOOR")
    assert (middle["slot_recall"], middle["saturation"]) == (0.5, "OPEN")
    assert CEILING == 0.95 and FLOOR == 0.05
    # Recall counts only supported queries; insufficient ones never enter its denominator.
    mixed = _cell([row(True), row(None, supported=False, status_ok=False)])
    assert mixed["slot_recall_denominator"] == 1 and mixed["status_correct"] == 1
    assert mixed["false_answer_denominator"] == 1
    # A failure counts zero recall (intent to treat) instead of dropping out.
    failed = _cell([row(True), row(None, observed=False)])
    assert failed["slot_recall"] == 0.5 and failed["observed"] == 1
    assert _cell([row(None, supported=False)])["saturation"] is None  # no applicable query


def test_strata_and_case_selection_are_deterministic_and_labelled():
    one = cases_for(47, "pilot", ("TEMPLATE",), 1)
    assert [c.case.gold.family for _s, c in one] == ["M1", "M2", "M3", "M4", "M5", "M6"]
    again = cases_for(47, "pilot", ("TEMPLATE",), 1)
    assert [c.case.query.query_id for _s, c in one] == [c.case.query.query_id for _s, c in again]
    noisy = cases_for(47, "pilot", ("NOISY_V1:id",), 1)
    assert {s for s, _c in noisy} == {"NOISY_V1:id"}
    assert {c.case.gold.language for _s, c in noisy} == {"id"}
    assert {c.case.query.query_id for _s, c in noisy}.isdisjoint(
        c.case.query.query_id for _s, c in one
    )
    assert len(cases_for(47, "pilot", STRATA, None)) == 4 * 48
    with pytest.raises(NornError, match="UNSUPPORTED_STRATUM"):
        cases_for(47, "pilot", ("NOISY_V2",), None)


def test_arms_search_the_budget_pool_but_output_stays_ten():
    v2 = publish(first("M1").case)
    request = interpret(v2, "R0")
    assert (request.candidate_limit, request.final_limit) == (60, 10)
    v1 = publish(scenarios(build_world(47, partition(47, "development")))[0])
    legacy = interpret(v1, "R0")
    assert (legacy.candidate_limit, legacy.final_limit) == (10, 10)  # public-v1 unchanged
    assert request.deadline_ms == legacy.deadline_ms


def test_the_wall_cap_stops_a_run_visibly_and_never_truncates_silently(tmp_path):
    import time

    started = time.perf_counter_ns()
    _check_cap(started, 3600.0, tmp_path / "ok", 0, 10)  # under the cap: nothing happens
    assert not (tmp_path / "ok" / "aborted.json").exists()
    with pytest.raises(NornError, match="WALL_CAP_EXCEEDED"):
        _check_cap(started - 10_000_000_000, 1.0, tmp_path / "late", 3, 10)
    aborted = json.loads((tmp_path / "late" / "aborted.json").read_text())
    assert aborted["reason"] == "WALL_CAP_EXCEEDED" and aborted["pairs_done"] == 3
    assert aborted["planned"] == 10 and not (tmp_path / "late" / "completion.json").exists()


def test_run_refuses_unauthorised_roles_missing_enablement_and_missing_cap(tmp_path):
    base = dict(
        seed=47,
        strata=("TEMPLATE",),
        names=("R0",),
        model_root=tmp_path,
        enable_models=True,
        wall_cap_seconds=60.0,
        cap_basis="test",
    )
    with pytest.raises(NornError, match="PARTITION_ACCESS_DENIED"):
        run_multihop(tmp_path / "a", role="locked", **base)
    with pytest.raises(NornError, match="LOCKED_NOT_SEALED"):
        run_multihop(tmp_path / "b", role="evaluation", **base)
    with pytest.raises(NornError, match="ROLE_NOT_AUTHORISED_FOR_T20"):
        run_multihop(tmp_path / "c", role="tune", **base)  # tune is read only after margins freeze
    with pytest.raises(NornError, match="BASELINE_ENABLEMENT_REQUIRED"):
        run_multihop(tmp_path / "d", role="pilot", **{**base, "enable_models": False})
    with pytest.raises(NornError, match="WALL_CAP_REQUIRED"):
        run_multihop(tmp_path / "e", role="pilot", **{**base, "cap_basis": ""})
    existing = tmp_path / "f"
    existing.mkdir()
    with pytest.raises(NornError, match="RUN_DIRECTORY_EXISTS"):
        run_multihop(existing, role="pilot", **base)
    assert ARMS == ("R0", "R1", "R2", "R3")


def test_a_run_without_attestation_or_the_development_label_is_not_citable(tmp_path):
    with pytest.raises(NornError, match="ATTESTATION_REQUIRED"):
        report_multihop(tmp_path, tmp_path)
    with pytest.raises(NornError, match="ATTESTATION_OR_DEVELOPMENT_ONLY"):
        validate_multihop(
            tmp_path, model_root=tmp_path, attestation=tmp_path / "a", development_only=True
        )


def test_no_public_v1_run_or_number_is_accepted_or_carried_over(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": 1, "run_kind": "CONVENTIONAL_RETRIEVAL_DEVELOPMENT", "sealed": False})
    )
    (tmp_path / "completion.json").write_text("{}")
    with pytest.raises(NornError, match="UNSUPPORTED_OR_FALSE_SEAL"):
        validate_multihop(tmp_path, model_root=tmp_path, development_only=True)
    source = Path(multihop_run.__file__).read_text(encoding="utf-8")
    assert "p03" not in source.lower() and "p05" not in source.lower()
