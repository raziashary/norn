"""Reopen actual artifacts; missing pairs, changed bytes, code drift or stage fraud fail."""

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from benchmark.adapters.common import validate_result
from benchmark.adapters.contracts import ArmSpec, Candidate, Result
from benchmark.fixtures.audit import audit_summary, load_judgments, stratified_sample
from benchmark.fixtures.partitions import authorize_partition, partition
from benchmark.fixtures.publication import validate_public
from benchmark.fixtures.scenarios import Case, Gold, gold_payload, scenarios
from benchmark.fixtures.world import build_world
from benchmark.metrics.abstention import abstention_score, aggregate
from benchmark.metrics.retrieval import retrieval_scores
from benchmark.runs.manifest import code_digest, file_digest, load
from benchmark.runs.runner import arm_spec
from benchmark.statistics.paired import PairedValue, paired_difference
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest


def result_from(raw: dict[str, Any]) -> Result:
    require(set(raw) == {field.name for field in fields(Result)}, "RESULT_SCHEMA")
    data = dict(raw)
    data["candidates"] = tuple(Candidate(**c) for c in data["candidates"])
    data["missing_fields"] = tuple(data["missing_fields"])
    return Result(**data)


def gold_from(raw: dict[str, Any]) -> Gold:
    data = dict(raw)
    for key in ("acceptable_sets", "slots"):
        data[key] = tuple(tuple(s) for s in data[key])
    data["partial_sets"] = tuple(tuple(s) for s in data.get("partial_sets", ()))
    data["missing_fields"] = tuple(data.get("missing_fields", ()))
    for key in ("relevant_events", "forbidden_sources", "forbidden_canaries"):
        data[key] = tuple(data[key])
    return Gold(**data)


def validate_run(root: Path) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    completion = load(root / "completion.json")
    require(
        manifest["schema"] == 1
        and manifest["run_kind"] == "SYNTHETIC_HARNESS_CONTROLS"
        and manifest["sealed"] is False,
        "UNSUPPORTED_OR_FALSE_SEAL",
    )
    require(manifest["code_digest"] == code_digest(), "RUN_CODE_MISMATCH")
    authorize_partition(manifest["partition_role"], manifest["partition"])
    require(
        manifest["model"] == "NONE" and manifest["config"]["max_attempts"] == 1,
        "UNSUPPORTED_MODEL_OR_RETRY_POLICY",
    )
    require(
        file_digest(root / "manifest.json") == completion["manifest_digest"], "MANIFEST_CHANGED"
    )
    require(file_digest(root / "ledger.jsonl") == completion["ledger_digest"], "LEDGER_CHANGED")
    for relative, expected in manifest["artifacts"].items():
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts, "UNSAFE_MANIFEST_PATH")
        require(file_digest(root / path) == expected, "RUN_ARTIFACT_CHANGED")
    gold_rows = load(root / "evaluator/gold.json")
    require(type(gold_rows) is list and 1 <= len(gold_rows) <= 10_000, "GOLD_CASE_BUDGET")
    gold = {row["query_id"]: gold_from(row) for row in gold_rows}
    require(len(gold) == len(gold_rows), "DUPLICATE_GOLD_CASE")
    world = build_world(manifest["seed"], partition(manifest["seed"], manifest["partition"]))
    require(
        world.sha256 == manifest["world_digest"]
        and world.partition.sha256 == manifest["partition_digest"]
        and canonical(load(root / "evaluator/world.json")) == canonical(asdict(world)),
        "WORLD_PARTITION_LINEAGE_CHANGED",
    )
    expected_cases = scenarios(world)
    if manifest["config"]["sample_only"]:
        expected_cases = stratified_sample(expected_cases)
    require(
        canonical(gold_rows) == canonical([gold_payload(c) for c in expected_cases]),
        "GOLD_GENERATOR_LINEAGE_CHANGED",
    )
    public = {qid: validate_public(load(root / "published" / (qid + ".json"))) for qid in gold}
    require(all(qid == item.query.query_id for qid, item in public.items()), "QUERY_ID_MISMATCH")
    from benchmark.fixtures.publication import publish

    require(
        all(
            public[c.query.query_id].sha256 == publish(c, (world.gold_canary,)).sha256
            for c in expected_cases
        ),
        "PUBLISHED_GENERATOR_LINEAGE_CHANGED",
    )
    artifact_names = {"evaluator/world.json", "evaluator/gold.json", "evaluator/audit.json"}
    artifact_names.update("published/" + qid + ".json" for qid in gold)
    require(set(manifest["artifacts"]) == artifact_names, "UNDECLARED_OR_HIDDEN_ARTIFACT")
    require(
        {
            p.relative_to(root / "published").as_posix()
            for p in (root / "published").rglob("*")
            if p.is_file()
        }
        == {qid + ".json" for qid in gold},
        "UNDECLARED_PUBLIC_FILE",
    )
    audit = audit_summary(
        tuple(Case(item.query, item.sources, gold[qid]) for qid, item in public.items()),
        load_judgments(root / "evaluator/audit.json"),
    )
    require(audit == manifest["audit"], "AUDIT_SUMMARY_CHANGED")
    specs = {}
    for name, raw in manifest["arms"].items():
        data = dict(raw)
        data["capabilities"] = tuple(data["capabilities"])
        specs[name] = ArmSpec(**data)
        require(specs[name] == arm_spec(name), "ARM_SPEC_OR_FALLBACK_CHANGED")
    expected_pairs = {tuple(pair) for pair in manifest["planned_pairs"]}
    require(
        len(expected_pairs) == len(manifest["planned_pairs"]) == len(gold) * len(specs),
        "PLANNED_PAIR_ACCOUNTING",
    )
    require(expected_pairs == {(q, a) for q in gold for a in specs}, "PLANNED_PAIR_ACCOUNTING")
    previous = completion["manifest_digest"]
    seen = set()
    scores = []
    dispositions: dict[str, int] = {}
    path = root / "ledger.jsonl"
    with path.open("rb") as stream:
        for line in stream:
            require(len(line) <= 1_048_576, "LEDGER_ROW_BUDGET")
            row = json.loads(line)
            checksum = row.pop("record_digest")
            require(
                row["previous_digest"] == previous and digest(canonical(row).encode()) == checksum,
                "LEDGER_CHAIN_CHANGED",
            )
            previous = checksum
            pair = row["query_id"], row["arm_id"]
            require(
                pair in expected_pairs and pair not in seen and row["attempt"] == 1,
                "LEDGER_PAIR_ACCOUNTING",
            )
            seen.add(pair)
            qid, arm = pair
            require(
                row["input_digest"] == public[qid].sha256 and row["provider_calls"] == 0,
                "ARM_INPUT_OR_PROVIDER_CHANGED",
            )
            result = result_from(row["result"])
            tokens = validate_result(public[qid], result, specs[arm])
            require(
                type(row["elapsed_ns"]) is int
                and row["elapsed_ns"] >= 0
                and row["training_seed"] is None,
                "COST_OR_SEED_ACCOUNTING",
            )
            if row["raw_response"] is not None:
                response = result_from(row["raw_response"])
                require(response.provider_calls == 0, "HIDDEN_PROVIDER_FALLBACK")
                if result.disposition == "INVALID":
                    error_code = None
                    try:
                        validate_result(public[qid], response, specs[arm])
                    except NornError as error:
                        error_code = error.code
                    require(
                        error_code == result.reason and error_code is not None,
                        "FALSE_INVALID_NORMALIZATION",
                    )
                else:
                    require(response == result, "RAW_RESULT_CHANGED")
            else:
                require(result.disposition == "ERROR", "MISSING_RAW_RESPONSE")
            require(tokens == row["evidence_tokens"], "TOKEN_ACCOUNTING_CHANGED")
            retrieval = retrieval_scores(public[qid], result, specs[arm], gold[qid])
            abstention = abstention_score(
                result, gold[qid], retrieval["complete_set"], retrieval["partial_set"]
            )
            raw = canonical(row.get("raw_response"))
            abstention["privacy_incidents"] = sum(
                marker in raw
                for marker in (*gold[qid].forbidden_sources, *gold[qid].forbidden_canaries)
            )
            abstention["privacy_observed"] = row["raw_response"] is not None
            dispositions[result.disposition] = dispositions.get(result.disposition, 0) + 1
            scores.append(
                {
                    "query_id": qid,
                    "arm_id": arm,
                    "family": gold[qid].family,
                    "cluster": gold[qid].cluster,
                    "variant": gold[qid].variant,
                    "language": gold[qid].language,
                    "cue_missing_fraction": gold[qid].cue_missing_fraction,
                    "elapsed_ns": row["elapsed_ns"],
                    "confidence": result.confidence,
                    "retrieval": retrieval,
                    "answer": abstention,
                }
            )
    require(
        seen == expected_pairs and len(seen) == completion["observations"], "MISSING_LEDGER_PAIR"
    )
    require(
        previous == completion["final_chain_digest"] and dispositions == completion["dispositions"],
        "COMPLETION_CHANGED",
    )
    arms = {}
    for arm in specs:
        selected = [r for r in scores if r["arm_id"] == arm]
        eligible = [r for r in selected if r["answer"]["full_answerable"]]
        # ITT denominator includes candidate/timeout failures, explicitly preregistered in manifest.
        benefits = [int(r["retrieval"]["complete_set"] is True) for r in eligible]
        arms[arm] = {
            "track": specs[arm].track,
            **aggregate([r["answer"] for r in selected]),
            "complete_set_itt": sum(benefits) / len(benefits) if benefits else None,
            "benefit_denominator": len(benefits),
            "calibration": "NO_CONFIDENCE_EMITTED",
            "latency_quantiles": "NOT_REPORTED_CONTROL_SAMPLE_ONLY",
        }
    contrasts = {}
    if "perfect" in arms:
        for arm in specs:
            if arm == "perfect":
                continue
            vectors = []
            for name in ("perfect", arm):
                vectors.append(
                    tuple(
                        PairedValue(
                            r["query_id"],
                            r["cluster"],
                            None,
                            float(r["retrieval"]["complete_set"] is True),
                        )
                        for r in scores
                        if r["arm_id"] == name and r["answer"]["full_answerable"]
                    )
                )
            contrasts["perfect-minus-" + arm] = paired_difference(
                *vectors, seed=manifest["seed"], samples=200
            )
    return {
        "schema": 1,
        "run_kind": manifest["run_kind"],
        "scope": "HARNESS_MECHANICS_ONLY",
        "audit": manifest["audit"],
        "partition": manifest["partition"],
        "partition_role": manifest["partition_role"],
        "manifest_digest": completion["manifest_digest"],
        "sealed": False,
        "pairs": len(scores),
        "arms": arms,
        "contrasts": contrasts,
        "observations": scores,
        "research_efficacy": "NOT_EVALUATED",
        "unsupported_algorithms": "R0-R10 NOT_RUN",
    }
