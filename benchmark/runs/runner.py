"""Paired control execution. Only the explicitly labeled oracle diagnostic sees gold."""

import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark.adapters.common import CommonControl, NativeUnavailable, candidate, validate_result
from benchmark.adapters.contracts import Adapter, ArmSpec, PublicInput, Result
from benchmark.fixtures.audit import audit_summary, load_judgments, stratified_sample
from benchmark.fixtures.partitions import authorize_partition, partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import Case, gold_payload, scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs.manifest import code_digest, file_digest, hardware, write_once
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest

CONTROL_NAMES = (
    "perfect",
    "empty",
    "shuffled",
    "extractive",
    "error",
    "timeout",
    "unsupported",
    "invalid",
    "not_run",
    "confidence",
)


def arm_spec(name: str) -> ArmSpec:
    if name == "perfect":
        return ArmSpec(
            name,
            "ORACLE_DIAGNOSTIC",
            ("source_read",),
            "NONE",
            "EVALUATOR_GOLD; NOT_A_CANDIDATE_ARM",
        )
    if name.startswith("native:"):
        return NativeUnavailable(name).spec
    return CommonControl(name).spec


def oracle(published: PublicInput, case: Case) -> Result:
    if not set(published.query.required_capabilities) <= {"source_read"}:
        return Result(
            "UNSUPPORTED", None, (), coverage="UNAVAILABLE", reason="FEATURE_NOT_SUPPORTED"
        )
    sets = case.gold.partial_sets or case.gold.acceptable_sets
    source_ids = sets[0] if sets else ()
    sources = {s.source_id: s for s in published.sources}
    return Result(
        "OK",
        case.gold.expected_status,
        tuple(candidate(sources[k]) for k in source_ids),
        coverage=case.gold.projection_state,
        reason=case.gold.reason,
        missing_fields=case.gold.missing_fields,
    )


def run_controls(
    destination: Path,
    *,
    seed: int = 47,
    tier: str = "smoke",
    role: str = "smoke",
    names: tuple[str, ...] = ("perfect", "empty", "shuffled"),
    sample_only: bool = False,
    judgments_path: Path | None = None,
) -> dict[str, Any]:
    authorize_partition(role, tier)
    require(not destination.exists(), "RUN_DIRECTORY_EXISTS")
    require(
        bool(names) and len(names) <= 20 and len(set(names)) == len(names),
        "ARM_BUDGET_OR_DUPLICATE",
    )
    specs = {name: arm_spec(name) for name in names}
    started = time.perf_counter_ns()
    world = build_world(seed, partition(seed, tier))
    cases = scenarios(world)
    if sample_only:
        cases = stratified_sample(cases)
    require(len(cases) <= 10_000, "RUN_QUERY_BUDGET")
    judgments = load_judgments(judgments_path) if judgments_path else ()
    audit = audit_summary(cases, judgments)
    inputs = {case.query.query_id: publish(case, (world.gold_canary,)) for case in cases}
    artifacts = {
        "evaluator/world.json": write_once(destination / "evaluator/world.json", asdict(world)),
        "evaluator/gold.json": write_once(
            destination / "evaluator/gold.json", [gold_payload(c) for c in cases]
        ),
        "evaluator/audit.json": write_once(
            destination / "evaluator/audit.json", [asdict(j) for j in judgments]
        ),
    }
    for query_id, public in inputs.items():
        path = "published/" + query_id + ".json"
        artifacts[path] = write_once(destination / path, public.payload())
    manifest = {
        "schema": 1,
        "run_kind": "SYNTHETIC_HARNESS_CONTROLS",
        "sealed": False,
        "partition": tier,
        "partition_role": role,
        "seed": seed,
        "world_digest": world.sha256,
        "partition_digest": world.partition.sha256,
        "code_digest": code_digest(),
        "arms": {name: asdict(spec) for name, spec in specs.items()},
        "planned_pairs": [[c.query.query_id, name] for c in cases for name in names],
        "artifacts": artifacts,
        "hardware": hardware(),
        "evaluation_time": "2026-10-23T00:00:00+00:00",
        "model": "NONE",
        "config": {
            "sample_only": sample_only,
            "max_attempts": 1,
            "benefit_estimand": "SUPPORTED_CASE_COMPLETE_SET_ITT_FAILURE_ZERO",
            "safety_estimand": "OBSERVED_RESPONSE_ONLY; UNOBSERVED_IS_UNKNOWN",
        },
        "audit": audit,
        "custody": (
            "TRUSTED_IN_PROCESS_CONTROLS; STRUCTURAL_AND_PUBLICATION_BARRIER; NOT_OS_SANDBOX"
        ),
        "offline_ns": time.perf_counter_ns() - started,
        "created_at": datetime.now(UTC).isoformat(),
    }
    manifest_hash = write_once(destination / "manifest.json", manifest)
    chain = manifest_hash
    ledger_path = destination / "ledger.jsonl"
    counts: dict[str, int] = {}
    with ledger_path.open("xb") as stream:
        for case in cases:
            public = inputs[case.query.query_id]
            # Round-trip the actual input boundary before every arm call.
            from benchmark.fixtures.publication import validate_public

            for name in names:
                arm_input = validate_public(json.loads(canonical(public.payload())))
                tick = time.perf_counter_ns()
                raw: Result | None = None
                reason = None
                try:
                    if name == "perfect":
                        raw = oracle(arm_input, case)
                    else:
                        adapter: Adapter = (
                            NativeUnavailable(name)
                            if name.startswith("native:")
                            else CommonControl(name)
                        )
                        raw = adapter.query(arm_input)
                    tokens = validate_result(arm_input, raw, specs[name])
                    normalized = raw
                except NornError as error:
                    reason = error.code
                    tokens = 0
                    normalized = Result("INVALID", None, (), reason=reason, coverage="UNAVAILABLE")
                except Exception:
                    reason = "ADAPTER_EXCEPTION"
                    tokens = 0
                    normalized = Result("ERROR", None, (), reason=reason, coverage="UNAVAILABLE")
                record = {
                    "query_id": case.query.query_id,
                    "arm_id": name,
                    "attempt": 1,
                    "training_seed": None,
                    "input_digest": arm_input.sha256,
                    "result": asdict(normalized),
                    "raw_response": asdict(raw) if raw else None,
                    "error_origin": "ADAPTER_OR_OUTPUT_CONTRACT" if reason else None,
                    "elapsed_ns": time.perf_counter_ns() - tick,
                    "evidence_tokens": tokens,
                    "provider_calls": 0,
                    "previous_digest": chain,
                }
                chain = digest(canonical(record).encode())
                stream.write((canonical({**record, "record_digest": chain}) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
                counts[normalized.disposition] = counts.get(normalized.disposition, 0) + 1
    completion = {
        "manifest_digest": manifest_hash,
        "ledger_digest": file_digest(ledger_path),
        "final_chain_digest": chain,
        "observations": sum(counts.values()),
        "dispositions": counts,
    }
    write_once(destination / "completion.json", completion)
    return completion
