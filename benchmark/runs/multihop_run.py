"""R0 to R3 on public-v2 (P06-T20): run, reload-validate and report, development role only.

The run reads the pilot role (and its NOISY_V1 renderings) only. Every query is answered through
the same published-input boundary as public-v1; the arms receive ``search_budget`` as their
candidate pool while the output limit stays 10. A run is citable only with an external
attestation (``benchmark.runs.seal``); without it the report is labelled development-only.
"""

import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark.adapters.common import validate_result
from benchmark.adapters.contracts import ArmSpec, PublicInput, Result
from benchmark.fixtures.multihop import FAMILIES, PRIMARY, MultiHopCase, multihop_cases
from benchmark.fixtures.noisy_render import STRATUM, label_of, noisy_case, require_labelled
from benchmark.fixtures.partitions import authorize_partition
from benchmark.fixtures.publication import publish, validate_public
from benchmark.fixtures.scenarios import gold_payload
from benchmark.metrics.abstention import abstention_score
from benchmark.metrics.retrieval import retrieval_scores
from benchmark.runs.baselines import quantiles, validate_diagnostics
from benchmark.runs.manifest import code_digest, file_digest, hardware, load, write_once
from benchmark.runs.runner import arm_spec
from benchmark.runs.validate import gold_from, require_attestation, result_from
from benchmark.statistics.paired import PairedValue, adjust_family, paired_difference
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.embedding.assets import METHODS, MODELS
from norn.retrieval.rerank import EvidenceTokenizer

RUN_KIND = "MULTIHOP_CONVENTIONAL_DEVELOPMENT"
ARMS = ("R0", "R1", "R2", "R3")
STRATA = ("TEMPLATE", "NOISY_V1:en", "NOISY_V1:id", "NOISY_V1:mixed")
MARKER = "__GOLD_CANARY__"
CEILING, FLOOR = 0.95, 0.05


def cases_for(
    seed: int, role: str, strata: tuple[str, ...], limit_per_family: int | None
) -> list[tuple[str, MultiHopCase]]:
    """(stratum, case) in a fixed order; the noisy twins are derived from the template cases."""
    require(set(strata) <= set(STRATA) and bool(strata), "UNSUPPORTED_STRATUM")
    templates = multihop_cases(seed, role)
    if limit_per_family is not None:
        taken: dict[str, int] = {}
        kept = []
        for case in templates:
            family = case.case.gold.family
            if taken.get(family, 0) < limit_per_family:
                kept.append(case)
                taken[family] = taken.get(family, 0) + 1
        templates = tuple(kept)
    result: list[tuple[str, MultiHopCase]] = []
    for stratum in strata:
        for template in templates:
            if stratum == "TEMPLATE":
                result.append((stratum, template))
            else:
                result.append((stratum, noisy_case(template, seed, stratum.split(":")[1])))
    return result


def _check_cap(started: int, cap_seconds: float, root: Path, done: int, planned: int) -> None:
    elapsed = (time.perf_counter_ns() - started) / 1e9
    if elapsed > cap_seconds:
        write_once(
            root / "aborted.json",
            {
                "reason": "WALL_CAP_EXCEEDED",
                "elapsed_s": elapsed,
                "pairs_done": done,
                "planned": planned,
            },
        )
        raise NornError("WALL_CAP_EXCEEDED")


def run_multihop(
    destination: Path,
    *,
    seed: int,
    role: str,
    strata: tuple[str, ...],
    names: tuple[str, ...],
    model_root: Path,
    enable_models: bool,
    wall_cap_seconds: float,
    cap_basis: str,
    limit_per_family: int | None = None,
) -> dict[str, Any]:
    authorize_partition(role, role)
    require(role == "pilot", "ROLE_NOT_AUTHORISED_FOR_T20")
    require(not destination.exists(), "RUN_DIRECTORY_EXISTS")
    require(
        set(names) <= set(ARMS) and bool(names) and enable_models, "BASELINE_ENABLEMENT_REQUIRED"
    )
    require(wall_cap_seconds > 0 and bool(cap_basis), "WALL_CAP_REQUIRED")
    specs = {name: arm_spec(name) for name in names}
    source_revision = code_digest()
    started = time.perf_counter_ns()
    selected = cases_for(seed, role, strata, limit_per_family)
    require(0 < len(selected) <= 2000, "RUN_QUERY_BUDGET")
    token_counter = EvidenceTokenizer(model_root)
    inputs: dict[str, PublicInput] = {}
    stratum_of: dict[str, str] = {}
    for stratum, case in selected:
        public = publish(case.case, (MARKER,))
        if stratum != "TEMPLATE":
            require_labelled(public)
        inputs[case.case.query.query_id] = public
        stratum_of[case.case.query.query_id] = stratum
    artifacts = {
        "evaluator/gold.json": write_once(
            destination / "evaluator/gold.json", [gold_payload(c.case) for _s, c in selected]
        ),
        "evaluator/graph_gold.json": write_once(
            destination / "evaluator/graph_gold.json",
            [
                asdict(c.graph) | {"private_sources": len(c.graph.private_sources)}
                for _s, c in selected
            ],
        ),
        "evaluator/strata.json": write_once(destination / "evaluator/strata.json", stratum_of),
    }
    for query_id, public in inputs.items():
        path = "published/" + query_id + ".json"
        artifacts[path] = write_once(destination / path, public.payload())
    from benchmark.adapters.baseline import Baseline, prepare

    preparations: dict[str, Any] = {}
    for done, (query_id, public) in enumerate(inputs.items()):
        _check_cap(started, wall_cap_seconds, destination, done, len(inputs))
        preparations[query_id] = prepare(
            public, destination / "stores" / query_id, model_root, enable_models
        )
    artifacts["preparations.json"] = write_once(destination / "preparations.json", preparations)
    manifest: dict[str, Any] = {
        "schema": 1,
        "run_kind": RUN_KIND,
        "sealed": False,
        "partition": role,
        "partition_role": role,
        "seed": seed,
        "code_digest": source_revision,
        "arms": {name: asdict(spec) for name, spec in specs.items()},
        "planned_pairs": [[q, name] for q in inputs for name in names],
        "artifacts": artifacts,
        "hardware": hardware(),
        "evaluation_time": "2026-10-23T00:00:00+00:00",
        "model": {name: spec.model for name, spec in specs.items()},
        "retrieval_models": MODELS,
        "retrieval_methods": METHODS,
        "config": {
            "strata": list(strata),
            "limit_per_family": limit_per_family,
            "baseline_profile": "PUBLIC_SOURCE_RECORDS_E5_PACKET_V1; SEARCH_BUDGET_CANDIDATE_POOL",
            "max_attempts": 1,
            "benefit_estimand": "SUPPORTED_CASE_COMPLETE_SET_ITT_FAILURE_ZERO",
            "wall_cap": {"seconds": wall_cap_seconds, "basis": cap_basis},
            "label": "DEVELOPMENT_PILOT_ROLE; NOT_A_CONFIRMATORY_RESULT",
        },
        "custody": "TRUSTED_IN_PROCESS; STRUCTURAL_AND_PUBLICATION_BARRIER; NOT_OS_SANDBOX",
        "offline_ns": time.perf_counter_ns() - started,
        "created_at": datetime.now(UTC).isoformat(),
    }
    require(code_digest() == source_revision, "RUN_CODE_CHANGED_DURING_PREPARATION")
    manifest_hash = write_once(destination / "manifest.json", manifest)
    chain = manifest_hash
    counts: dict[str, int] = {}
    ledger_path = destination / "ledger.jsonl"
    done = 0
    with ledger_path.open("xb") as stream:
        for query_id, public in inputs.items():
            for name in names:
                _check_cap(
                    started, wall_cap_seconds, destination, done, len(manifest["planned_pairs"])
                )
                arm_input = validate_public(json.loads(canonical(public.payload())))
                tick = time.perf_counter_ns()
                raw: Result | None = None
                reason, diagnostics = None, None
                try:
                    baseline = Baseline(
                        name, destination / "stores" / query_id, model_root, enable_models,
                        preparations[query_id],
                    )  # fmt: skip
                    raw = baseline.query(arm_input)
                    diagnostics = baseline.diagnostics
                    tokens = validate_result(arm_input, raw, specs[name], token_counter)
                    normalized = raw
                except NornError as error:
                    reason, tokens = error.code, 0
                    normalized = Result(
                        "INVALID" if raw is not None else "ERROR", None, (), reason=reason,
                        coverage="UNAVAILABLE",
                    )  # fmt: skip
                except Exception:
                    reason, tokens = "ADAPTER_EXCEPTION", 0
                    normalized = Result("ERROR", None, (), reason=reason, coverage="UNAVAILABLE")
                record = {
                    "query_id": query_id,
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
                    "baseline_diagnostics": diagnostics,
                }
                chain = digest(canonical(record).encode())
                stream.write((canonical({**record, "record_digest": chain}) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
                counts[normalized.disposition] = counts.get(normalized.disposition, 0) + 1
                done += 1
    require(code_digest() == source_revision, "RUN_CODE_CHANGED_DURING_EXECUTION")
    completion = {
        "manifest_digest": manifest_hash,
        "ledger_digest": file_digest(ledger_path),
        "final_chain_digest": chain,
        "observations": sum(counts.values()),
        "dispositions": counts,
        "elapsed_s": (time.perf_counter_ns() - started) / 1e9,
    }
    write_once(destination / "completion.json", completion)
    return completion


def validate_multihop(
    root: Path,
    *,
    model_root: Path,
    attestation: Path | None = None,
    development_only: bool = False,
) -> dict[str, Any]:
    """Reload every artifact, regenerate the cases and re-score the ledger under the metrics."""
    status = require_attestation(attestation, development_only)
    if attestation is not None:
        from benchmark.runs.seal import verify

        verify(root, attestation)
    manifest, completion = load(root / "manifest.json"), load(root / "completion.json")
    require(
        manifest["schema"] == 1
        and manifest["run_kind"] == RUN_KIND
        and manifest["sealed"] is False,
        "UNSUPPORTED_OR_FALSE_SEAL",
    )
    require(manifest["code_digest"] == code_digest(), "RUN_CODE_MISMATCH")
    require(manifest["partition_role"] == "pilot", "ROLE_NOT_AUTHORISED_FOR_T20")
    authorize_partition("pilot", manifest["partition"])
    require(manifest["config"]["max_attempts"] == 1, "UNSUPPORTED_RETRY_POLICY")
    require(
        canonical(manifest["retrieval_methods"]) == canonical(METHODS)
        and canonical(manifest["retrieval_models"]) == canonical(MODELS),
        "BASELINE_METHOD_OR_MODEL_CHANGED",
    )
    require(
        file_digest(root / "manifest.json") == completion["manifest_digest"], "MANIFEST_CHANGED"
    )
    require(file_digest(root / "ledger.jsonl") == completion["ledger_digest"], "LEDGER_CHANGED")
    for relative, expected in manifest["artifacts"].items():
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts, "UNSAFE_MANIFEST_PATH")
        require(file_digest(root / path) == expected, "RUN_ARTIFACT_CHANGED")
    config = manifest["config"]
    expected = cases_for(
        manifest["seed"], "pilot", tuple(config["strata"]), config["limit_per_family"]
    )
    gold_rows = load(root / "evaluator/gold.json")
    require(
        canonical(gold_rows) == canonical([gold_payload(c.case) for _s, c in expected]),
        "GOLD_GENERATOR_LINEAGE_CHANGED",
    )
    gold = {row["query_id"]: gold_from(row) for row in gold_rows}
    strata = load(root / "evaluator/strata.json")
    require(strata == {c.case.query.query_id: s for s, c in expected}, "STRATA_LINEAGE_CHANGED")
    public = {q: validate_public(load(root / "published" / (q + ".json"))) for q in gold}
    for stratum, case in expected:
        item = public[case.case.query.query_id]
        require(
            item.sha256 == publish(case.case, (MARKER,)).sha256,
            "PUBLISHED_GENERATOR_LINEAGE_CHANGED",
        )
        require(
            (stratum == "TEMPLATE") == all(label_of(s) is None for s in item.sources),
            "STRATUM_LABEL_MISMATCH",
        )
    require(
        set(manifest["artifacts"])
        == {
            "evaluator/gold.json",
            "evaluator/graph_gold.json",
            "evaluator/strata.json",
            "preparations.json",
            *("published/" + q + ".json" for q in gold),
        },
        "UNDECLARED_OR_HIDDEN_ARTIFACT",
    )
    specs: dict[str, ArmSpec] = {}
    for name, raw in manifest["arms"].items():
        data = dict(raw)
        data["capabilities"] = tuple(data["capabilities"])
        specs[name] = ArmSpec(**data)
        require(specs[name] == arm_spec(name), "ARM_SPEC_OR_FALLBACK_CHANGED")
    pairs = {tuple(p) for p in manifest["planned_pairs"]}
    require(
        pairs == {(q, a) for q in gold for a in specs}
        and len(pairs) == len(manifest["planned_pairs"]),
        "PLANNED_PAIR_ACCOUNTING",
    )
    token_counter = EvidenceTokenizer(model_root)
    previous = completion["manifest_digest"]
    seen: set[tuple[str, str]] = set()
    scores: list[dict[str, Any]] = []
    dispositions: dict[str, int] = {}
    with (root / "ledger.jsonl").open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            checksum = row.pop("record_digest")
            require(
                row["previous_digest"] == previous and digest(canonical(row).encode()) == checksum,
                "LEDGER_CHAIN_CHANGED",
            )
            previous = checksum
            pair = row["query_id"], row["arm_id"]
            require(
                pair in pairs and pair not in seen and row["attempt"] == 1, "LEDGER_PAIR_ACCOUNTING"
            )
            seen.add(pair)
            qid, arm = pair
            require(
                row["input_digest"] == public[qid].sha256 and row["provider_calls"] == 0,
                "ARM_INPUT_OR_PROVIDER_CHANGED",
            )
            result = result_from(row["result"])
            tokens = validate_result(public[qid], result, specs[arm], token_counter)
            if row["raw_response"] is not None:
                response = result_from(row["raw_response"])
                require(response.provider_calls == 0, "HIDDEN_PROVIDER_FALLBACK")
                if result.disposition != "INVALID":
                    require(response == result, "RAW_RESULT_CHANGED")
            else:
                require(result.disposition == "ERROR", "MISSING_RAW_RESPONSE")
            require(tokens == row["evidence_tokens"], "TOKEN_ACCOUNTING_CHANGED")
            validate_diagnostics(
                root, public[qid], result, row.get("baseline_diagnostics"), token_counter
            )
            retrieval = retrieval_scores(public[qid], result, specs[arm], gold[qid], token_counter)
            answer = abstention_score(
                result,
                gold[qid],
                retrieval["complete_set"],
                retrieval["partial_set"],
                retrieval["slot_coverage"],
            )
            raw_text = canonical(row)
            answer["privacy_incidents"] = sum(
                m in raw_text for m in (*gold[qid].forbidden_sources, *gold[qid].forbidden_canaries)
            )
            dispositions[result.disposition] = dispositions.get(result.disposition, 0) + 1
            scores.append(
                {
                    "query_id": qid,
                    "arm_id": arm,
                    "family": gold[qid].family,
                    "cluster": gold[qid].cluster,
                    "variant": gold[qid].variant,
                    "stratum": strata[qid],
                    "elapsed_ns": row["elapsed_ns"],
                    "retrieval": retrieval,
                    "answer": answer,
                    "diagnostics": row.get("baseline_diagnostics"),
                }
            )
    require(seen == pairs and len(seen) == completion["observations"], "MISSING_LEDGER_PAIR")
    require(
        previous == completion["final_chain_digest"] and dispositions == completion["dispositions"],
        "COMPLETION_CHANGED",
    )
    return {
        "evidence_status": status,
        "run_kind": RUN_KIND,
        "manifest": {
            k: manifest[k] for k in ("seed", "partition", "code_digest", "config", "hardware")
        },
        "completion": completion,
        "arms": sorted(specs),
        "observations": scores,
    }


def _cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [r for r in rows if r["answer"]["full_answerable"]]
    insufficient = [r for r in rows if r["answer"]["insufficient_for_full"]]
    observed = [r for r in rows if r["answer"]["observed"]]
    recall = (
        sum(r["retrieval"]["complete_set"] is True for r in applicable) / len(applicable)
        if applicable
        else None
    )
    return {
        "planned": len(rows),
        "observed": len(observed),
        "slot_recall_numerator": sum(r["retrieval"]["complete_set"] is True for r in applicable),
        "slot_recall_denominator": len(applicable),
        "slot_recall": recall,
        "saturation": None
        if recall is None
        else "CEILING"
        if recall >= CEILING
        else "FLOOR"
        if recall <= FLOOR
        else "OPEN",
        "status_correct": sum(r["answer"]["status_correct"] is True for r in observed),
        "status_denominator": len(observed),
        "false_answers": sum(r["answer"]["false_answer"] is True for r in rows),
        "false_answer_denominator": len(insufficient),
        "false_abstentions": sum(r["answer"]["false_abstention"] is True for r in rows),
        "false_abstention_denominator": len(applicable),
        "privacy_incidents": sum(r["answer"]["privacy_incidents"] for r in rows),
    }


def report_multihop(
    root: Path,
    model_root: Path,
    attestation: Path | None = None,
    *,
    development_only: bool = False,
) -> dict[str, Any]:
    result = validate_multihop(
        root, model_root=model_root, attestation=attestation, development_only=development_only
    )
    rows = result["observations"]
    cells: dict[str, Any] = {}
    for family in FAMILIES:
        for stratum in sorted({r["stratum"] for r in rows}):
            key = f"{family}|{stratum}"
            cells[key] = {
                arm: _cell(
                    [
                        r
                        for r in rows
                        if r["family"] == family and r["stratum"] == stratum and r["arm_id"] == arm
                    ]
                )
                for arm in result["arms"]
            }
            recalls = [
                c["slot_recall"] for c in cells[key].values() if c["slot_recall"] is not None
            ]
            cells[key]["non_discriminating"] = (
                None if not recalls else max(recalls) - min(recalls) < 0.05
            )
    pooled = {
        arm: _cell([r for r in rows if r["family"] in PRIMARY and r["arm_id"] == arm])
        for arm in result["arms"]
    }
    contrasts = {}
    for arm in result["arms"]:
        if arm != "R0" and "R0" in result["arms"]:
            paired = [
                tuple(
                    PairedValue(
                        r["query_id"],
                        r["cluster"],
                        None,
                        float(r["retrieval"]["complete_set"] is True),
                    )
                    for r in rows
                    if r["arm_id"] == selected
                    and r["family"] in PRIMARY
                    and r["answer"]["full_answerable"]
                )
                for selected in (arm, "R0")
            ]
            contrasts[arm + "-minus-R0"] = paired_difference(*paired, seed=47, samples=1000)
    costs = {}
    for arm in result["arms"]:
        mine = [r for r in rows if r["arm_id"] == arm]
        costs[arm] = {
            "elapsed": quantiles([r["elapsed_ns"] for r in mine]),
            "cold": quantiles([r["diagnostics"]["cold_ns"] for r in mine if r["diagnostics"]]),
            "observed_queries": sum(bool(r["diagnostics"]) for r in mine),
        }
    preparations = load(root / "preparations.json")
    return {
        **{k: v for k, v in result.items() if k != "observations"},
        "definitions": {
            "slot_recall": (
                "complete evidence set among gold SUPPORTED queries, failures count zero"
            ),
            "sufficiency": "status_correct is reported separately and never combined with recall",
            "saturation": (
                f"CEILING at or above {CEILING}, FLOOR at or below {FLOOR}, else OPEN, "
                "per family, stratum and arm"
            ),
            "non_discriminating": "the spread of slot recall across arms is under 0.05",
            "primary_families": list(PRIMARY),
        },
        "cells": cells,
        "primary_pooled": pooled,
        "contrasts": adjust_family(contrasts),
        "costs": costs,
        "offline_build_ns": sum(p["offline_ns"] for p in preparations.values()),
        "limits": (
            "Pilot role only, synthetic template and NOISY_V1 renderings; "
            "question-schema interpreter; "
            "no tune or evaluation role, no graph arm, no confirmatory claim; CPU serial; "
            "the evidence tokenizer and models are the pinned E5 packet profile."
        ),
        "stratum_label": STRATUM,
    }
