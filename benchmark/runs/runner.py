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
from norn.embedding.assets import METHODS, MODELS
from norn.retrieval.rerank import EvidenceTokenizer

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
    if name in {"R0", "R1", "R2", "R3"}:
        from benchmark.adapters.baseline import spec

        return spec(name)
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
    model_root: Path | None = None,
    enable_models: bool = False,
) -> dict[str, Any]:
    authorize_partition(role, tier)
    require(not destination.exists(), "RUN_DIRECTORY_EXISTS")
    require(
        bool(names) and len(names) <= 20 and len(set(names)) == len(names),
        "ARM_BUDGET_OR_DUPLICATE",
    )
    specs = {name: arm_spec(name) for name in names}
    source_revision = code_digest()
    baselines = any(name in {"R0", "R1", "R2", "R3"} for name in names)
    require(
        not baselines
        or (set(names) <= {"R0", "R1", "R2", "R3"} and model_root is not None and enable_models),
        "BASELINE_ENABLEMENT_REQUIRED",
    )
    token_counter = EvidenceTokenizer(model_root) if baselines and model_root is not None else None
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
    preparations = {}
    if baselines:
        from benchmark.adapters.baseline import prepare

        assert model_root is not None
        for query_id, public in inputs.items():
            preparations[query_id] = prepare(
                public, destination / "stores" / query_id, model_root, enable_models
            )
        artifacts["preparations.json"] = write_once(destination / "preparations.json", preparations)
    manifest: dict[str, Any] = {
        "schema": 1,
        "run_kind": "CONVENTIONAL_RETRIEVAL_DEVELOPMENT"
        if baselines
        else "SYNTHETIC_HARNESS_CONTROLS",
        "sealed": False,
        "partition": tier,
        "partition_role": role,
        "seed": seed,
        "world_digest": world.sha256,
        "partition_digest": world.partition.sha256,
        "code_digest": source_revision,
        "arms": {name: asdict(spec) for name, spec in specs.items()},
        "planned_pairs": [[c.query.query_id, name] for c in cases for name in names],
        "artifacts": artifacts,
        "hardware": hardware(),
        "evaluation_time": "2026-10-23T00:00:00+00:00",
        "model": {name: spec.model for name, spec in specs.items()} if baselines else "NONE",
        "config": {
            "sample_only": sample_only,
            "baseline_profile": "PUBLIC_SOURCE_RECORDS_E5_PACKET_V1" if baselines else None,
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
    if baselines:
        from importlib.metadata import version

        manifest["retrieval_models"] = MODELS
        manifest["retrieval_methods"] = METHODS
        manifest["retrieval_packages"] = {
            name: version(name) for name in ("numpy", "tokenizers", "onnxruntime", "faiss-cpu")
        }
        manifest["hardware"].update(
            {
                "cache": "COLD_ENGINE_THEN_SECOND_QUERY; ONE_RESIDENT_MODEL",
                "tokenizer": "e5-small-pinned-tokenizer-v1",
                "native_provider": "CPUExecutionProvider",
                "ort_threads": 2,
            }
        )
    require(code_digest() == source_revision, "RUN_CODE_CHANGED_DURING_PREPARATION")
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
                diagnostics: dict[str, Any] | None = None
                try:
                    if name == "perfect":
                        raw = oracle(arm_input, case)
                    elif baselines:
                        from benchmark.adapters.baseline import Baseline

                        assert model_root is not None
                        baseline = Baseline(
                            name,
                            destination / "stores" / case.query.query_id,
                            model_root,
                            enable_models,
                            preparations[case.query.query_id],
                        )
                        raw = baseline.query(arm_input)
                        diagnostics = baseline.diagnostics
                    else:
                        adapter: Adapter = (
                            NativeUnavailable(name)
                            if name.startswith("native:")
                            else CommonControl(name)
                        )
                        raw = adapter.query(arm_input)
                    tokens = validate_result(arm_input, raw, specs[name], token_counter)
                    normalized = raw
                except NornError as error:
                    reason = error.code
                    tokens = 0
                    normalized = Result(
                        "INVALID" if raw is not None else "ERROR",
                        None,
                        (),
                        reason=reason,
                        coverage="UNAVAILABLE",
                    )
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
                if baselines:
                    record["baseline_diagnostics"] = diagnostics
                chain = digest(canonical(record).encode())
                stream.write((canonical({**record, "record_digest": chain}) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
                counts[normalized.disposition] = counts.get(normalized.disposition, 0) + 1
    require(code_digest() == source_revision, "RUN_CODE_CHANGED_DURING_EXECUTION")
    completion = {
        "manifest_digest": manifest_hash,
        "ledger_digest": file_digest(ledger_path),
        "final_chain_digest": chain,
        "observations": sum(counts.values()),
        "dispositions": counts,
    }
    write_once(destination / "completion.json", completion)
    return completion
