"""Reopened exact binding sources, geometry, budgets, outcomes and conditional diagnostics."""

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np

from benchmark.adapters.baseline import host, interpret
from benchmark.adapters.common import validate_result
from benchmark.adapters.r7 import SPECS
from benchmark.fixtures.binding_cases import ROLE_INDICES, cases
from benchmark.fixtures.publication import publish, validate_public
from benchmark.metrics.abstention import abstention_score, aggregate
from benchmark.metrics.retrieval import retrieval_scores
from benchmark.runs.baselines import quantiles
from benchmark.runs.binding import CONFIG, checked, ledger_digest
from benchmark.runs.manifest import file_digest, load
from benchmark.runs.validate import gold_from, result_from
from benchmark.statistics.paired import PairedValue, paired_difference
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.embedding import checkpoint, concatenate, late_fusion
from norn.embedding.binding import LEARNED, BindingModel
from norn.embedding.numerics import Array, array
from norn.embedding.query import encode as query_code
from norn.features.views import derive
from norn.integration.engine import Engine
from norn.projection.binding import readback
from norn.retrieval.assembly import assemble
from norn.retrieval.contracts import Hit
from norn.retrieval.exact import eligible
from norn.retrieval.rerank import EvidenceTokenizer
from norn.retrieval.resolve import resolve


def memory_code(
    captured: dict[str, Any], variant: str, model: BindingModel | None, ablation: str = "none"
) -> Array:
    x = array([captured["facets"]], (1, 3, 384))
    mask = array([captured["mask"]], (1, 3))
    if ablation.startswith("drop_"):
        index = ("context", "semantic", "actions").index(ablation[5:])
        mask[0, index] = 0
    elif ablation == "duplicate_semantic":
        x[:] = x[:, 1:2, :]
    require(bool(mask.any()), "BINDING_ALL_MISSING_OR_INVALID_MASK")
    if variant == "B0":
        return array(captured["single"], (384,))
    if variant == "B1":
        return cast(Array, concatenate.facets(x, mask)[0].reshape(384))
    if variant == "B2":
        return cast(Array, concatenate.encode(x, mask)[0])
    require(model is not None, "BINDING_CHECKPOINT_REQUIRED")
    assert model is not None
    inputs = array([captured["single"]]) if variant.startswith("S") else x
    return cast(Array, model.forward(inputs, mask)[0][0])


def validate_packet(
    root: Path,
    row: dict[str, Any],
    public: Any,
    captured: dict[str, Any],
    model: BindingModel | None,
    tokenizer: EvidenceTokenizer,
) -> None:
    diagnostic = row["diagnostic"]
    result = result_from(row["result"])
    if diagnostic:
        require("first_result" in diagnostic, "BINDING_RESULT_PACKET_CHANGED")
        require(
            row["result"] == diagnostic["first_result"]
            or (row["failure_stage"] == "REPEATED_RECALL" and result.disposition == "ERROR"),
            "BINDING_RESULT_PACKET_CHANGED",
        )
        if "repeated" in diagnostic:
            require(
                diagnostic["repeat_unchanged"]
                == (diagnostic["first_result"] == diagnostic["repeated"]),
                "BINDING_REPEAT_CHANGED",
            )
            validate_result(
                public, result_from(diagnostic["repeated"]), SPECS[row["variant"]], tokenizer
            )
    if not diagnostic or diagnostic.get("early"):
        require(
            result.disposition != "OK"
            or (
                public.query.coverage_state == "UNAVAILABLE"
                and result.evidence_status == "VERIFICATION_UNAVAILABLE"
            ),
            "MISSING_BINDING_DIAGNOSTIC",
        )
        return
    require(diagnostic["ranking_stage"] == "BINDING_CANDIDATES", "UNOBSERVED_METRIC_STAGE")
    request = interpret(public, "R1")
    variant = row["variant"]
    with Engine(root / "stores" / row["role"] / row["query"], host(public)) as engine:
        corpus = eligible(engine, request)
        records = {r.key: r for r in corpus.records}
        identity = row["projection"]["snapshot_id"]
        manifest, payloads = readback(
            engine, identity, keys=frozenset(records), budget=QueryBudget(600_000)
        )
        require(
            manifest["variant"] == variant
            and manifest["canonical_seq"] == corpus.snapshot
            and manifest["security_epoch"] == corpus.security_epoch,
            "BINDING_SNAPSHOT_CHANGED",
        )
        # The independently persisted real E5 capture supplies numerical inputs;
        # source texts/locators are revalidated against the actual canonical store.
        by_event = {m["event_id"]: m for m in captured["memories"]}
        groups: dict[str, list[Any]] = {}
        for record in corpus.records:
            groups.setdefault(record.event_id, []).append(record)
        require(set(groups) == set(by_event), "BINDING_CAPTURE_IDENTITY_CHANGED")
        q = query_code(array([captured["query"]]), variant, model)
        event_keys = tuple(sorted(groups))
        vectors = []
        for event_id in event_keys:
            feature = derive(tuple(sorted(groups[event_id], key=lambda r: r.key)))
            p = payloads[groups[event_id][0].key]
            require(
                p["texts"] == list(feature.texts) and p["mask"] == list(feature.mask),
                "BINDING_FEATURE_SOURCE_CHANGED",
            )
            require(
                np.allclose(
                    array(p["vector"]),
                    memory_code(by_event[event_id], variant, model),
                    atol=2e-6,
                    rtol=2e-6,
                ),
                "BINDING_GEOMETRY_CHANGED",
            )
            vectors.append(p["vector"])
        values: dict[str, float] = {}
        if vectors:
            matrix = array(vectors)
            if variant == "B1":
                scores = late_fusion.scores(
                    q.reshape(3, 128),
                    matrix.reshape(-1, 3, 128),
                    array([by_event[k]["mask"] for k in event_keys]),
                    event_keys,
                    request.candidate_limit,
                )
            else:
                scores = matrix @ q
            values = {key: float(v) for key, v in zip(event_keys, scores, strict=True)}
        expected = tuple(
            sorted(
                (Hit(r, values[r.event_id], variant) for r in corpus.records),
                key=lambda h: (-h.score, h.record.key),
            )[: request.candidate_limit]
        )
        sources = {s.source_id: s for s in public.sources}
        mapped_rank = list(dict.fromkeys(captured["mapping"][h.record.atom_id] for h in expected))
        if diagnostic["packet"]["status"] != "VERIFICATION_UNAVAILABLE":
            require(mapped_rank == diagnostic["ranking_sources"], "BINDING_RANKING_CHANGED")
        packets = [(result_from(diagnostic["first_result"]), diagnostic["packet"])]
        if "packet" in diagnostic.get("repeated_diagnostic", {}):
            packets.append(
                (result_from(diagnostic["repeated"]), diagnostic["repeated_diagnostic"]["packet"])
            )
        for observed, packet in packets:
            require(
                observed.evidence_status
                == (packet["status"] if observed.disposition == "OK" else None)
                and (observed.disposition == "OK" or packet["status"] == "VERIFICATION_UNAVAILABLE")
                and observed.reason == packet["reason"]
                and observed.missing_fields == tuple(packet["missing_fields"])
                and observed.coverage == packet["coverage"],
                "BINDING_RESULT_PACKET_CHANGED",
            )
            require(
                [c.source_id for c in observed.candidates]
                == [captured["mapping"][r["atom_id"]] for r in packet["evidence"]],
                "BINDING_FINAL_STAGE_CHANGED",
            )
            if packet["status"] == "VERIFICATION_UNAVAILABLE":
                require(
                    not packet["evidence"]
                    and bool(packet["reason"])
                    and packet["trace"]["usage"]["model_calls"] >= 0,
                    "BINDING_FAILURE_PACKET_CHANGED",
                )
                continue
            require(
                packet["binding_ranking"] == [h.record.key for h in expected],
                "BINDING_RANKING_CHANGED",
            )
            require(
                np.allclose(packet["binding_scores"], [h.score for h in expected], atol=1e-6),
                "BINDING_RANKING_CHANGED",
            )
            verified = tuple(
                resolve(engine, h, request, corpus.snapshot, corpus.security_epoch)
                for h in expected
            )
            evidence, tokens, _ = assemble(verified, request, tokenizer, complete=corpus.complete)
            for field in ("status", "reason", "missing_fields", "evidence"):
                require(
                    canonical(packet[field]) == canonical(evidence[field]), "BINDING_PACKET_CHANGED"
                )
            require(
                tokens == packet["evidence_tokens"] <= request.max_evidence_tokens,
                "BINDING_PACKET_BUDGET_CHANGED",
            )
            require(
                packet["security_epoch"] == corpus.security_epoch
                and packet["snapshot"] == corpus.snapshot,
                "BINDING_SNAPSHOT_CHANGED",
            )
            counts = packet["trace"]["stage_counts"]
            require(
                counts["eligible"] == len(records)
                and counts["candidates"] == len(expected)
                and counts["final_evidence"] == len(evidence["evidence"]),
                "BINDING_STAGE_COUNT_CHANGED",
            )
            for record in packet["evidence"]:
                source = sources[captured["mapping"][record["atom_id"]]]
                require(
                    record["text"] == source.text and record["sha256"] == source.sha256,
                    "CANDIDATE_SOURCE_MISMATCH",
                )


def conditional(
    captured: dict[str, Any],
    gold: Any,
    variant: str,
    model: BindingModel | None,
    candidate_limit: int = 10,
) -> dict[str, Any]:
    if variant not in ("B1", "B2", "B3", "B4") or not captured["memories"]:
        return {}
    q = query_code(array([captured["query"]]), variant, model)
    memories = captured["memories"]
    keys = tuple(m["event_id"] for m in memories)
    relevant = set().union(*(set(s) for s in gold.acceptable_sets))
    output = {}
    for ablation in ("none", "drop_context", "drop_semantic", "drop_actions", "duplicate_semantic"):
        matrix = array([memory_code(m, variant, model, ablation) for m in memories])
        if variant == "B1":
            masks = array([m["mask"] for m in memories])
            if ablation.startswith("drop_"):
                masks[:, ("context", "semantic", "actions").index(ablation[5:])] = 0
            scores = late_fusion.scores(
                q.reshape(3, 128), matrix.reshape(-1, 3, 128), masks, keys, candidate_limit
            )
        else:
            scores = matrix @ q
        ranked = sorted(range(len(memories)), key=lambda i: (-float(scores[i]), keys[i]))
        top = memories[ranked[0]]["source_ids"]
        right = [
            float(scores[i]) for i, m in enumerate(memories) if set(m["source_ids"]) & relevant
        ]
        wrong = [
            float(scores[i]) for i, m in enumerate(memories) if not set(m["source_ids"]) & relevant
        ]
        output[ablation] = {
            "top1": bool(set(top) & relevant) if relevant else None,
            "target_margin": max(right) - max(wrong) if right and wrong else None,
            "margin_kind": "RRF_RANK_SCORE" if variant == "B1" else "COSINE_SCORE",
        }
    return output


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [r for r in rows if r["answer"]["full_answerable"]]
    identity = [r for r in rows if r["top1"] is not None]
    episodes = [r for r in rows if r["episode_top1"] is not None]
    returned = [r for r in rows if r["wrong_episode"] is not None]
    conditional_summary = {}
    for ablation in ("none", "drop_context", "drop_semantic", "drop_actions", "duplicate_semantic"):
        values = [r["conditional"][ablation] for r in rows if r["conditional"]]
        tops = [v["top1"] for v in values if v["top1"] is not None]
        margins = [v["target_margin"] for v in values if v["target_margin"] is not None]
        conditional_summary[ablation] = {
            "top1_numerator": sum(tops),
            "top1_denominator": len(tops),
            "target_margin_mean": sum(margins) / len(margins) if margins else None,
            "target_margin_denominator": len(margins),
        }
    return {
        "planned": len(rows),
        "unique_queries": len({r["query"] for r in rows}),
        "dispositions": dict(Counter(r["disposition"] for r in rows)),
        "complete_set_numerator": sum(r["complete_set"] is True for r in applicable),
        "complete_set_denominator": len(applicable),
        "top1_numerator": sum(r["top1"] is True for r in identity),
        "top1_denominator": len(identity),
        "episode_top1_numerator": sum(r["episode_top1"] is True for r in episodes),
        "episode_top1_denominator": len(episodes),
        "wrong_returned_episode_numerator": sum(r["wrong_episode"] is True for r in returned),
        "wrong_returned_episode_observed_denominator": len(returned),
        "identity_applicable_planned": sum(r["identity_applicable"] for r in rows),
        "conditional": conditional_summary,
        "answer": aggregate([r["answer"] for r in rows]),
        "first": quantiles([r["first_ns"] for r in rows if r["first_ns"] is not None]),
        "repeated": quantiles([r["repeated_ns"] for r in rows if r["repeated_ns"] is not None]),
        "projection": quantiles([r["project_ns"] for r in rows if r["project_ns"] is not None]),
        "repeated_model_calls": sum(r["repeated_usage"].get("model_calls", 0) for r in rows),
        "repeated_model_tokens": sum(r["repeated_usage"].get("model_tokens", 0) for r in rows),
        "query_usage_missing": sum(not r["query_usage"] for r in rows),
        "projection_usage_missing": sum(not r["project_usage"] for r in rows),
        "repeated_usage_missing": sum(not r["repeated_usage"] for r in rows),
        "repeat_changed": sum(r["repeat_unchanged"] is False for r in rows),
        "eligible_event_counts": dict(Counter(r["eligible_events"] for r in rows)),
        "candidate_limits": dict(Counter(r["candidate_limit"] for r in rows)),
        "resource_observations": [r["resources"] for r in rows],
        "failure_stages": dict(Counter(r["failure_stage"] for r in rows)),
        "projection_model_calls": sum(r["project_usage"].get("model_calls", 0) for r in rows),
        "query_model_calls": sum(r["query_usage"].get("model_calls", 0) for r in rows),
        "projection_model_tokens": sum(r["project_usage"].get("model_tokens", 0) for r in rows),
        "query_model_tokens": sum(r["query_usage"].get("model_tokens", 0) for r in rows),
    }


def report(root: Path, model_root: Path) -> dict[str, Any]:
    manifest = checked(root)
    completion = load(root / "binding-completion.json")
    training = load(root / "training.json")
    require(
        completion["manifest_digest"] == file_digest(root / "manifest.json")
        and completion["training_digest"] == file_digest(root / "training.json")
        and completion["ledger_digest"] == ledger_digest(root / "binding-ledger.jsonl"),
        "BINDING_COMPLETION_CHANGED",
    )
    jobs = {(j["variant"], j["seed"]): j for j in training["jobs"]}
    require(
        set(jobs) == {(v, s) for v in LEARNED for s in CONFIG["seeds"]}
        and len(training["jobs"]) == 12,
        "BINDING_TRAINING_JOBS_MISSING",
    )
    models = {}
    for job_key, job in jobs.items():
        require(
            job["path"] == f"checkpoints/{job_key[0]}-{job_key[1]}.json", "UNSAFE_CHECKPOINT_PATH"
        )
        require(file_digest(root / job["path"]) == job["sha256"], "CHECKPOINT_SOURCE_CHANGED")
        ck = checkpoint.load(root / job["path"])
        require(
            (ck.model.variant, ck.payload["training"]["seed"]) == job_key,
            "CHECKPOINT_VARIANT_MISMATCH",
        )
        require(ck.payload["data_digest"] == training["training_digest"], "TRAINING_DATA_CHANGED")
        require(
            ck.payload["training"] == job["receipt"]
            and ck.payload["training"]["updates"]
            == (16 if manifest["smoke"] else CONFIG["updates"])
            and ck.model.parameter_count == job["receipt"]["parameters"],
            "BINDING_TRAINING_RECEIPT_CHANGED",
        )
        models[job_key] = ck.model
    train_artifacts = {
        name: sha for name, sha in manifest["artifacts"].items() if "/train/" in name
    }
    require(
        training["training_digest"] == digest(canonical(train_artifacts).encode()),
        "TRAINING_DATA_CHANGED",
    )
    for target, control in (("B3", "S3"), ("B4", "S4")):
        require(
            abs(models[control, 11].parameter_count / models[target, 11].parameter_count - 1)
            <= 0.01,
            "BINDING_CAPACITY_MISMATCH",
        )
    for role in ROLE_INDICES:
        expected_cases = cases(role, smoke=manifest["smoke"])
        require(
            manifest["planned"][role] == [c.query.query_id for c in expected_cases],
            "BINDING_CASES_CHANGED",
        )
        for case in expected_cases:
            qid = case.query.query_id
            require(
                load(root / "published" / role / (qid + ".json"))
                == json.loads(canonical(publish(case).payload()))
                and load(root / "evaluator" / role / (qid + ".json"))
                == json.loads(canonical(asdict(case.gold))),
                "BINDING_DATA_OR_LABEL_CHANGED",
            )
    conditions = [(v, None) for v in ("B0", "B1", "B2")] + list(jobs)
    expected = {
        (role, qid, variant, seed)
        for role in ("tune", "evaluation")
        for qid in manifest["planned"][role]
        for variant, seed in conditions
    }
    require(
        len(completion["planned"]) == len(expected)
        and {tuple(p) for p in completion["planned"]} == expected,
        "MISSING_BINDING_PAIR",
    )
    tokenizer = EvidenceTokenizer(model_root)
    chain = file_digest(root / "manifest.json")
    seen = set()
    observations = []
    disposition_counts: Counter[str] = Counter()
    with (root / "binding-ledger.jsonl").open("rb") as stream:
        while raw := stream.readline(262_145):
            require(len(raw) <= 262_144, "BINDING_ROW_BUDGET")
            row = json.loads(raw)
            claimed = row.pop("row_digest")
            require(
                row["previous_digest"] == chain and digest(canonical(row).encode()) == claimed,
                "BINDING_LEDGER_CHAIN_CHANGED",
            )
            chain = claimed
            key = (row["role"], row["query"], row["variant"], row["seed"])
            require(key in expected and key not in seen, "UNPLANNED_OR_DUPLICATE_BINDING_PAIR")
            seen.add(key)
            public = validate_public(
                load(root / "published" / row["role"] / (row["query"] + ".json"))
            )
            gold = gold_from(load(root / "evaluator" / row["role"] / (row["query"] + ".json")))
            captured = load(root / "captures" / row["role"] / (row["query"] + ".json"))
            model = models.get((row["variant"], row["seed"]))
            result = result_from(row["result"])
            validate_result(public, result, SPECS[row["variant"]], tokenizer)
            validate_packet(root, row, public, captured, model, tokenizer)
            retrieval = retrieval_scores(public, result, SPECS[row["variant"]], gold, tokenizer)
            answer = abstention_score(
                result, gold, retrieval["complete_set"], retrieval["partial_set"]
            )
            answer["privacy_incidents"] = sum(
                marker in canonical(row)
                for marker in (*gold.forbidden_sources, *gold.forbidden_canaries)
            )
            diagnostic = row["diagnostic"]
            ranks = diagnostic.get("ranking_sources", [])
            positive = set().union(*(set(s) for s in gold.acceptable_sets))
            top1 = (
                (bool(ranks) and ranks[0] in positive)
                if gold.expected_status == "SUPPORTED"
                else None
            )
            source_events = {s.source_id: s.event_id for s in public.sources}
            identity_applicable = gold.expected_status == "SUPPORTED" and bool(gold.relevant_events)
            episode_top1 = (
                bool(ranks) and source_events[ranks[0]] in gold.relevant_events
                if identity_applicable and result.disposition == "OK"
                else None
            )
            observations.append(
                {
                    "role": row["role"],
                    "query": row["query"],
                    "variant": row["variant"],
                    "seed": row["seed"],
                    "family": gold.family,
                    "cluster": gold.cluster,
                    "language": gold.language,
                    "cue_variant": gold.variant,
                    "cue_missing_fraction": gold.cue_missing_fraction,
                    "disposition": result.disposition,
                    "complete_set": retrieval["complete_set"],
                    "answer": answer,
                    "top1": top1,
                    "episode_top1": episode_top1,
                    "identity_applicable": identity_applicable,
                    "wrong_episode": retrieval.get("wrong_episode") if result.candidates else None,
                    "candidate_limit": public.query.max_candidates,
                    "eligible_events": len(captured["memories"]),
                    "repeat_unchanged": diagnostic.get("repeat_unchanged"),
                    "project_ns": row["project_elapsed_ns"],
                    "repeated_usage": diagnostic.get("repeated_diagnostic", {})
                    .get("packet", {})
                    .get("trace", {})
                    .get("usage", {}),
                    "resources": diagnostic.get("packet", {}).get("resource_observation", {}),
                    "conditional": conditional(
                        captured, gold, row["variant"], model, public.query.max_candidates
                    )
                    if row["role"] == "evaluation"
                    else {},
                    "first_ns": diagnostic.get("elapsed_ns"),
                    "repeated_ns": diagnostic.get("repeated_diagnostic", {}).get("elapsed_ns"),
                    "project_usage": row["project_attempt_usage"],
                    "failure_stage": row["failure_stage"],
                    "query_usage": diagnostic.get("packet", {}).get("trace", {}).get("usage", {}),
                }
            )
            disposition_counts[result.disposition] += 1
    require(
        seen == expected
        and chain == completion["last_digest"]
        and dict(disposition_counts) == completion["counts"],
        "MISSING_BINDING_PAIR",
    )
    evaluation = [r for r in observations if r["role"] == "evaluation"]
    arms = {v: summary([r for r in evaluation if r["variant"] == v]) for v in SPECS}
    strata = {
        field: {
            str(value): {
                v: summary([r for r in evaluation if r[field] == value and r["variant"] == v])
                for v in SPECS
            }
            for value in sorted({r[field] for r in evaluation})
        }
        for field in ("family", "language", "cue_variant", "cue_missing_fraction")
    }
    contrasts = {}
    for left, right in (
        ("B3", "B1"),
        ("B4", "B1"),
        ("B3", "S3"),
        ("B4", "S4"),
        ("B1", "B0"),
        ("B2", "B0"),
    ):
        seeds = CONFIG["seeds"] if left in LEARNED else [None]
        pair = []
        for selected in (left, right):
            values = []
            for r in evaluation:
                if r["variant"] != selected or not r["answer"]["full_answerable"]:
                    continue
                for seed in seeds if r["seed"] is None else [r["seed"]]:
                    values.append(
                        PairedValue(
                            r["query"], r["cluster"], seed, float(r["complete_set"] is True)
                        )
                    )
            pair.append(tuple(values))
        contrasts[left + "-minus-" + right] = paired_difference(*pair, seed=47)
    return {
        "schema": 1,
        "scope": "UNAUDITED_FROZEN_BACKBONE_DEVELOPMENT_ONLY",
        "scientific_outcome": "INCONCLUSIVE",
        "pairs": len(seen),
        "arms": arms,
        "strata": strata,
        "contrasts": contrasts,
        "training": training,
        "environment": manifest["environment"],
        "b5": CONFIG["b5"],
        "storage": storage(root, manifest),
        "feature_costs": feature_costs(root, manifest),
        "seedwise": {
            str(seed): {
                v: summary([r for r in evaluation if r["variant"] == v and r["seed"] == seed])
                for v in LEARNED
            }
            for seed in CONFIG["seeds"]
        },
        "model_selection": "NONE",
        "observations": observations,
        "models": manifest["models"],
        "hardware": manifest["hardware"],
        "limits": [
            "No practical promotion margins/power/locked or external study",
            "Template/category transfer not tested; synthetic labels unaudited",
            "Baseline predictions reused across seed-aware contrasts, not new exposures",
            "Conditional arrays are frozen-feature ranking diagnostics, not answer/capacity claims",
            "Resident encoder after projection; first-project exposure rotated by query",
            "No general entailment, normative approval, generated QA or privacy-risk bound",
        ],
    }


def storage(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    sizes: Counter[str] = Counter()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).parts
        if relative[0] not in {"stores", "captures", "checkpoints"}:
            continue
        kind = (
            "checkpoint_global"
            if relative[0] == "checkpoints"
            else "private_capture"
            if relative[0] == "captures"
            else "projection_CAS"
            if "projections" in relative
            else "source_CAS"
            if "blobs" in relative
            else "whole_SQLite"
            if path.name.startswith("canonical.sqlite3")
            else "other"
        )
        sizes[kind] += path.stat().st_size
    return {
        "physical_bytes": dict(sizes),
        "numeric_bytes_per_event_per_generation": 1536,
        "scope": (
            "ACTUAL_FILES; CAS_INCLUDES_TEXT_JSON_AND_CHECKPOINT_COPIES; NOT_ALLOCATOR_ISOLATION"
        ),
        "source_visibility": manifest["visibility"],
    }


def feature_costs(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for role, queries in manifest["planned"].items():
        for qid in queries:
            captured = load(root / "captures" / role / (qid + ".json"))
            totals["capture_offline_ns"] += captured["offline_ns"]
            for m in captured["memories"]:
                totals["events"] += 1
                totals["selective_operator_ns"] += sum(m["facet_ns"])
                totals["full_operator_ns"] += sum(m["full_facet_ns"])
                totals["selective_calls"] += sum(m["selective_calls"])
                totals["full_calls"] += sum(m["full_calls"])
    return {
        "observations": dict(totals),
        "scope": "SERIAL_SOURCE_OPERATORS; SAME_EVENT; NO_MODEL_FANOUT_SPEEDUP_CLAIM",
    }
