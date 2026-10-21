from dataclasses import replace

import pytest

from benchmark.adapters.common import CommonControl, NativeUnavailable, candidate, validate_result
from benchmark.adapters.contracts import PublicInput, Result
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs.runner import arm_spec, oracle
from norn.contracts.errors import NornError
from norn.contracts.identity import digest


def case_input():
    case = scenarios(build_world(47, partition(47, "smoke")))[0]
    return case, publish(case)


def test_real_controls_share_scope_clock_and_budget_and_native_discloses_unsupported():
    case, public = case_input()
    for name in ("perfect", "extractive", "empty", "shuffled"):
        result = oracle(public, case) if name == "perfect" else CommonControl(name).query(public)
        assert validate_result(public, result, arm_spec(name)) <= public.query.max_evidence_tokens
    native = NativeUnavailable("native:R4")
    assert native.spec.track == "NATIVE"
    assert native.query(public).disposition == "UNSUPPORTED"
    graph = PublicInput(replace(public.query, required_capabilities=("graph",)), public.sources)
    assert CommonControl("extractive").query(graph).disposition == "UNSUPPORTED"
    with pytest.raises(NornError, match="UNSUPPORTED_CAPABILITY_FALLBACK"):
        validate_result(graph, Result("OK", "SUPPORTED", ()), arm_spec("extractive"))
    tiny = PublicInput(replace(public.query, max_evidence_tokens=1), public.sources)
    with pytest.raises(NornError, match="EVIDENCE_TOKEN_BUDGET"):
        validate_result(tiny, oracle(tiny, case), arm_spec("perfect"))


def test_forged_id_wrong_stage_partial_span_and_success_shaped_failure_rejected():
    _, public = case_input()
    source = public.sources[0]
    good = candidate(source)
    result = Result("OK", "SUPPORTED", (good,))
    for changed, code in (
        (replace(result, candidates=(replace(good, unit_id="similar-text"),)), "FORGED_IDENTITY"),
        (replace(result, stage="RETRIEVED_TOP_K"), "UNOBSERVED_METRIC_STAGE"),
        (replace(result, provider_calls=1), "PROVIDER_NOT_ENABLED"),
        (replace(result, disposition="TIMEOUT"), "SUCCESS_SHAPED_FAILURE"),
        (
            replace(
                result,
                candidates=(
                    replace(good, end_byte=1, span_digest=digest(source.text.encode()[:1])),
                ),
            ),
            "INCOMPLETE_CAPTURE_LOCATOR",
        ),
    ):
        with pytest.raises(NornError, match=code):
            validate_result(public, changed, arm_spec("extractive"))
    for unit in ("source", "atom", "event"):
        assert (
            validate_result(
                public,
                replace(result, candidates=(candidate(source, unit_kind=unit),)),
                arm_spec("extractive"),
            )
            > 0
        )
    with pytest.raises(NornError, match="INVALID_QUERY_ID"):
        replace(public.query, query_id="../gold")
