"""Reopened conventional baseline report; evaluator alone receives hidden labels."""

import math
from pathlib import Path
from typing import Any

from benchmark.adapters.baseline import host, interpret
from benchmark.adapters.contracts import PublicInput, Result
from benchmark.runs.manifest import load
from benchmark.statistics.paired import PairedValue, paired_difference
from norn.contracts.errors import require
from norn.contracts.identity import canonical
from norn.integration.engine import Engine
from norn.projection.local import readback
from norn.retrieval.assembly import TokenCounter
from norn.retrieval.contracts import Hit, Record
from norn.retrieval.resolve import resolve


def validate_diagnostics(
    root: Path,
    published: PublicInput,
    result: Result,
    diagnostic: dict[str, Any] | None,
    tokenizer: TokenCounter | None,
) -> None:
    if not diagnostic:
        require(
            result.disposition != "OK"
            or (
                published.query.coverage_state == "UNAVAILABLE"
                and result.evidence_status == "VERIFICATION_UNAVAILABLE"
            ),
            "MISSING_BASELINE_DIAGNOSTIC",
        )
        return
    require(tokenizer is not None, "TOKENIZER_UNAVAILABLE")
    assert tokenizer is not None
    packet = diagnostic["packet"]
    warm_packet = diagnostic["warm_packet"]
    require(
        diagnostic["repeat_unchanged"]
        == (
            packet["status"] == warm_packet["status"]
            and packet["evidence"] == warm_packet["evidence"]
        ),
        "REPEATED_RESULT_CHANGED",
    )
    require(
        warm_packet["status"] == diagnostic["warm_status"]
        and warm_packet["reason"] == diagnostic["warm_reason"],
        "REPEATED_RESULT_CHANGED",
    )
    require(
        tokenizer.count(canonical(warm_packet)) <= published.query.max_evidence_tokens,
        "BASELINE_PACKET_BUDGET_CHANGED",
    )
    if result.disposition == "OK":
        require(
            packet["status"] == result.evidence_status
            and tuple(packet["missing_fields"]) == result.missing_fields,
            "BASELINE_STATUS_CHANGED",
        )
    require(
        type(diagnostic["cold_ns"]) is int
        and diagnostic["cold_ns"] >= 0
        and type(diagnostic["warm_ns"]) is int
        and diagnostic["warm_ns"] >= 0,
        "BASELINE_COST_CHANGED",
    )
    if diagnostic["tokenizer"] is not None:
        require(
            diagnostic["tokenizer"] == tokenizer.version
            and tokenizer.count(canonical(packet))
            == diagnostic["packet_tokens"]
            <= published.query.max_evidence_tokens,
            "BASELINE_PACKET_BUDGET_CHANGED",
        )
    trace = diagnostic["trace"]
    require(diagnostic["warm_trace"]["snapshot"] == trace["snapshot"], "REPEATED_SNAPSHOT_CHANGED")
    require(trace["provider_calls"] == 0 and trace["retry_count"] == 0, "HIDDEN_PROVIDER_FALLBACK")
    for key in ("model_calls", "model_tokens", "records", "elapsed_ms"):
        require(
            type(trace["usage"][key]) is int and trace["usage"][key] >= 0, "BASELINE_USAGE_CHANGED"
        )
    require(
        trace["usage"]["model_calls"] <= 256 and trace["usage"]["model_tokens"] <= 200_000,
        "BASELINE_MODEL_BUDGET_CHANGED",
    )
    preparations = load(root / "preparations.json")
    prepared = preparations[published.query.query_id]
    require(prepared["input_digest"] == published.sha256, "ARM_INPUT_CHANGED")
    request = interpret(published, trace["arm"])
    sources = {s.source_id: s for s in published.sources}
    mapped_variants: list[list[str]] = []
    with Engine(root / "stores" / published.query.query_id, host(published)) as engine:
        for manifest_id in prepared["projection"]["manifests"].values():
            readback(engine, manifest_id)
        for variant in (packet, warm_packet):
            mapped: list[str] = []
            for raw in variant["evidence"]:
                data = dict(raw)
                data["aliases"] = tuple(data["aliases"])
                record = Record(**data)
                resolve(
                    engine,
                    Hit(record, 0, "validation"),
                    request,
                    trace["snapshot"],
                    prepared["projection"]["security_epoch"],
                )
                source = sources[prepared["mapping"][record.atom_id]]
                require(
                    record.text == source.text and record.sha256 == source.sha256,
                    "SOURCE_MAPPING_MISMATCH",
                )
                mapped.append(source.source_id)
            mapped_variants.append(mapped)
    mapped = mapped_variants[0]
    require(mapped == [c.source_id for c in result.candidates], "BASELINE_FINAL_STAGE_CHANGED")
    if packet["evidence"]:
        require(
            trace["stage_counts"]["final_evidence"] == len(mapped), "BASELINE_STAGE_COUNT_CHANGED"
        )


def quantiles(values: list[int]) -> dict[str, float | None]:
    if not values:
        return {"p50_ms": None, "p95_ms": None, "p99_ms": None}
    ordered = sorted(values)
    return {
        f"p{percent}_ms": ordered[max(0, math.ceil(percent / 100 * len(ordered)) - 1)] / 1_000_000
        for percent in (50, 95, 99)
    }


def report(root: Path, model_root: Path) -> dict[str, Any]:
    from benchmark.runs.validate import validate_run

    result = validate_run(root, model_root=model_root)
    require(result["run_kind"] == "CONVENTIONAL_RETRIEVAL_DEVELOPMENT", "BASELINE_RUN_REQUIRED")
    observations = result["observations"]
    strata: dict[str, Any] = {}
    for field in ("family", "variant", "language"):
        strata[field] = {}
        for value in sorted({r[field] for r in observations}):
            strata[field][value] = {}
            for arm in result["arms"]:
                rows = [r for r in observations if r[field] == value and r["arm_id"] == arm]
                applicable = [r for r in rows if r["answer"]["full_answerable"]]
                strata[field][value][arm] = {
                    "planned": len(rows),
                    "observed": sum(r["answer"]["observed"] for r in rows),
                    "complete_set_itt_numerator": sum(
                        r["retrieval"]["complete_set"] is True for r in applicable
                    ),
                    "complete_set_itt_denominator": len(applicable),
                    "false_answers": sum(r["answer"]["false_answer"] is True for r in rows),
                    "false_abstentions": sum(r["answer"]["false_abstention"] is True for r in rows),
                }
    costs = {}
    for arm in result["arms"]:
        diagnostics = [
            r["baseline_diagnostics"]
            for r in observations
            if r["arm_id"] == arm and r["baseline_diagnostics"]
        ]
        costs[arm] = {
            "cold": quantiles([d["cold_ns"] for d in diagnostics]),
            "repeated": quantiles([d["warm_ns"] for d in diagnostics]),
            "observed_queries": len(diagnostics),
            "model_attempts_cold": sum(d["trace"]["usage"]["model_calls"] for d in diagnostics),
            "model_tokens_cold": sum(d["trace"]["usage"]["model_tokens"] for d in diagnostics),
            "model_attempts_repeated": sum(
                d["warm_trace"]["usage"]["model_calls"] for d in diagnostics
            ),
            "model_tokens_repeated": sum(
                d["warm_trace"]["usage"]["model_tokens"] for d in diagnostics
            ),
            "truncated_queries": sum(
                bool(d["possibly_truncated_model_input"]) for d in diagnostics
            ),
            "changed_repeated_results": sum(not d["repeat_unchanged"] for d in diagnostics),
            "unavailable_repeated_queries": sum(
                d["warm_status"] == "VERIFICATION_UNAVAILABLE" for d in diagnostics
            ),
            "failed_rows_without_usage": sum(
                r["arm_id"] == arm and not r["baseline_diagnostics"] and not r["answer"]["observed"]
                for r in observations
            ),
        }
    contrasts = {}
    if "R0" in result["arms"]:
        for arm in result["arms"]:
            if arm != "R0":
                paired = [
                    tuple(
                        PairedValue(
                            r["query_id"],
                            r["cluster"],
                            None,
                            float(r["retrieval"]["complete_set"] is True),
                        )
                        for r in observations
                        if r["arm_id"] == selected and r["answer"]["full_answerable"]
                    )
                    for selected in (arm, "R0")
                ]
                contrasts[arm + "-minus-R0"] = paired_difference(*paired, seed=47, samples=1000)
    preparations = load(root / "preparations.json")
    return {
        **{k: v for k, v in result.items() if k != "observations"},
        "strata": strata,
        "costs": costs,
        "contrasts": contrasts,
        "offline_build_ns": sum(p["offline_ns"] for p in preparations.values()),
        "offline_model_attempts": sum(
            p["projection"]["usage"]["model_calls"] for p in preparations.values()
        ),
        "offline_model_tokens": sum(
            p["projection"]["usage"]["model_tokens"] for p in preparations.values()
        ),
        "metric_stage": "FINAL_EVIDENCE; earlier stages expose counts only",
        "limits": (
            "Synthetic development instances; question schema interpreter; "
            "no generator/training/locked/external validity; "
            "cold includes engine/model setup; repeated R3 switches resident models; "
            "CPU serial; resources are separate process peaks."
        ),
    }
