"""Graph arms G0 to G4 on the public-v2 pilot role (P06-T21, development only).

G0 is the conventional control (exact, BM25 and pinned dense, fused by RRF over a candidate pool
of ``search_budget``). G1 to G4 add a graph channel (bounded BFS, damped best paths, seeded PPR,
heat kernel) walked from the same fixed seed and fused with G0's ranked pool by the same RRF rule,
keeping the same 10-source output limit, token budget and evidence packaging as G0. Every graph
arm sees the same topology; the topology tracks are the text reader on every stratum (primary),
and, on the template stratum only, the read-back control and the oracle diagnostic (unequal).

The run reads the pilot role only, uses the attested T20 pilot stores (copied, never opened in
place), and makes no network or provider call. Its output is a measurement for the margin proposal
(``p06_margin_proposal.md``); no number here is a benefit claim and no parameter is tuned on it.
"""

import json
import math
import os
import shutil
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any

from benchmark.adapters.baseline import host, interpret
from benchmark.adapters.common import candidate, validate_result
from benchmark.adapters.contracts import PublicInput, Result
from benchmark.fixtures.multihop import FAMILIES, PRIMARY, MultiHopCase
from benchmark.fixtures.noisy_render import STRATUM, label_of, require_labelled
from benchmark.fixtures.partitions import authorize_partition
from benchmark.fixtures.publication import publish, validate_public
from benchmark.fixtures.scenarios import gold_payload
from benchmark.metrics.abstention import abstention_score
from benchmark.metrics.evidence_sets import evidence_scores
from benchmark.metrics.normalize import normalized_sources
from benchmark.metrics.retrieval import retrieval_scores
from benchmark.runs.graph_extraction import TRACK_GOLD, gold_edges, write_gold_diagnostic
from benchmark.runs.manifest import code_digest, file_digest, hardware, load, write_once
from benchmark.runs.multihop_run import STRATA, cases_for
from benchmark.runs.runner import arm_spec
from benchmark.runs.validate import gold_from, require_attestation, result_from
from benchmark.statistics.calibration import zero_incident_bound
from benchmark.statistics.paired import PairedValue, adjust_family, paired_difference
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.embedding.assets import METHODS, MODELS
from norn.extraction.relations import REVISIONS, TRACK_READBACK, TRACK_TEXT, extract_relations
from norn.graph.adjacency import build_graph
from norn.graph.bfs import Limits, bfs, path_candidates
from norn.graph.heat import HeatLimits, heat
from norn.graph.paths import damped_paths
from norn.graph.ppr import PprLimits, activation_candidates, ppr
from norn.graph.seeds import CONVENTIONAL, Seed
from norn.integration.engine import Engine
from norn.projection import local
from norn.retrieval import dense, exact, fusion, lexical
from norn.retrieval.contracts import EligibleCorpus, Hit, RecallRequest
from norn.retrieval.rerank import EvidenceTokenizer
from norn.retrieval.seed_channels import build_seed
from norn.retrieval.service import RecallView, assemble_hits

RUN_KIND = "GRAPH_PILOT_DEVELOPMENT"
ARMS = ("G0", "G1", "G2", "G3", "G4")
GRAPH_ARMS = ARMS[1:]
NO_TOPOLOGY = "NONE"
MARKER = "__GOLD_CANARY__"
TOPOLOGIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (TRACK_TEXT, STRATA),
    (TRACK_READBACK, ("TEMPLATE",)),
    (TRACK_GOLD, ("TEMPLATE",)),
)
MERGE_RULE = "RRF_K60_G0_POOL_PLUS_GRAPH_CHANNEL_TOP_FINAL_LIMIT"
LABEL = "DEVELOPMENT_PILOT_ROLE; NOT_A_CONFIRMATORY_RESULT; NOT_A_BENEFIT_CLAIM"
SEED_BASE = 47
BOOTSTRAP_SAMPLES = 1000
CONFIDENCE = 0.95
ALPHA, POWER = 0.05, 0.80
DELTAS = (0.05, 0.10, 0.15)
SIGMAS = (0.15, 0.25, 0.35)
ROLE_PRIMARY_CLUSTERS = {"pilot": 20, "tune": 40, "evaluation": 200}
REPO = Path(__file__).resolve().parents[2]
PREREGISTRATION = "docs/development/evidence/p06_margin_proposal.md"
PREREGISTRATION_HEADING = "## 2. Preregistered analysis"


def preregistration_digest(path: Path) -> str:
    """Digest of the preregistered section alone, so results can be added after it unchanged."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(PREREGISTRATION_HEADING)), -1
    )
    require(start >= 0, "PREREGISTRATION_SECTION_MISSING")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return digest(chr(10).join(lines[start:end]).strip().encode())


# Frozen by the owner's written answer of 20 November 2026 (ADR-0029 P06-Q5, proposal sections 6
# to 8, approved as written): a margin changed after a result invalidates promotion.
MARGINS = {"benefit": 0.10, "regression": 0.02, "privacy_incidents": 0}
CLUSTERS = {"tune": 40, "evaluation": 200}  # primary clusters, option (a) of section 7
HARM_CONTRASTS = (
    "G3_minus_G0_false_answer",
    "G3_minus_G0_false_abstention",
    "G3_minus_G0_false_association",
)
VERDICT_SCOPE = "DEVELOPMENT_EXPLORATORY_P06_M1"


def verdict(
    benefit: dict[str, Any], harms: dict[str, dict[str, Any]], privacy_incidents: int
) -> dict[str, Any]:
    """The frozen margins applied to one set of contrasts; the label carries its scope.

    Benefit needs the lower 95% bound above 0 and the point estimate at least the margin. A harm
    contrast with identical arms (no difference and no spread) is non-discriminating and is not
    cited as a bound; any other harm needs an upper bound within the regression margin, and a
    missing interval is not an exclusion."""
    low = (benefit.get("confidence_interval") or [None, None])[0]
    point = benefit.get("difference")
    cleared = low is not None and point is not None and low > 0 and point >= MARGINS["benefit"]
    harm: dict[str, str] = {}
    for name in HARM_CONTRASTS:
        item = harms[name]
        interval = item.get("confidence_interval")
        spread = (item.get("cluster_spread") or {}).get("sd")
        if item.get("pairs") and item.get("difference") == 0 and spread == 0:
            harm[name] = "NON_DISCRIMINATING"
        elif interval is not None and interval[1] <= MARGINS["regression"]:
            harm[name] = "EXCLUDED"
        else:
            harm[name] = "NOT_EXCLUDED"
    if privacy_incidents > MARGINS["privacy_incidents"]:
        label = "PRIVACY_INCIDENT_FAILS"
    elif not cleared:
        label = "G0_RETAINED_NO_BENEFIT"
    elif "NOT_EXCLUDED" in harm.values():
        label = "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED"
    else:
        label = "MARGINS_MET"
    return {"label": label, "scope": VERDICT_SCOPE, "benefit_cleared": cleared, "harm": harm}


def walk_config() -> dict[str, Any]:
    """The walk settings in force: the owner-set defaults of T04 to T06, untuned."""
    return {
        "G1": {"algorithm": "bfs", **asdict(Limits())},
        "G2": {"algorithm": "damped_paths", **asdict(Limits())},
        "G3": {"algorithm": "ppr", **asdict(PprLimits())},
        "G4": {"algorithm": "heat", **asdict(HeatLimits())},
    }


def graph_hits(corpus: EligibleCorpus, sources: Sequence[str]) -> tuple[Hit, ...]:
    """Records of the corpus that state the proposed stored sources, proposal order, once each.

    A proposed source that no readable record states is dropped here and counted by the caller,
    so a proposal can never add evidence the eligible corpus does not hold."""
    by_source: dict[str, list[Any]] = defaultdict(list)
    for record in corpus.records:
        by_source[record.source_id].append(record)
    hits: list[Hit] = []
    seen: set[str] = set()
    for source in sources:
        for record in by_source.get(source, ()):
            if record.key not in seen:
                seen.add(record.key)
                hits.append(Hit(record, 0.0, "graph"))
    return tuple(hits)


def merge(pool: tuple[Hit, ...], graph: tuple[Hit, ...], limit: int) -> tuple[Hit, ...]:
    """G0's ranked pool and the graph channel fused by the conventional RRF rule (no new rule)."""
    return fusion.fuse((), (pool, graph), limit)


def walk_arms(
    registry: Any, graph: Any, seed: Seed, checkpoint: Callable[[], None]
) -> dict[str, dict[str, Any]]:
    """G1 to G4 on one graph: the proposed stored sources, in rank order, with the walk's cost."""
    arms: dict[str, dict[str, Any]] = {}
    for name in GRAPH_ARMS:
        tick = time.perf_counter_ns()
        if name == "G1":
            run: Any = bfs(graph, seed, checkpoint=checkpoint)
            found: Sequence[Any] = path_candidates(registry, graph, run)
            nodes = len(run.steps)
        elif name == "G2":
            run = damped_paths(graph, seed, checkpoint=checkpoint)
            found = path_candidates(registry, graph, run)
            nodes = len(run.steps)
        elif name == "G3":
            run = ppr(graph, seed, checkpoint=checkpoint)
            found = activation_candidates(registry, graph, run)
            nodes = len(run.entries)
        else:
            run = heat(graph, seed, checkpoint=checkpoint)
            found = activation_candidates(registry, graph, run)
            nodes = len(run.entries)
        arms[name] = {
            "sources": [c.source_id for c in found],
            "cost": {
                "graph_ns": time.perf_counter_ns() - tick,
                "nodes": nodes,
                "edges": len(run.edges),
                "counters": dict(run.counters),
                "flags": list(run.flags),
                "unlinked": len(run.unlinked),
                "walk_digest": run.digest(),
            },
        }
    return arms


def seed_record(seed: Seed) -> dict[str, Any]:
    return {
        "digest": seed.digest(),
        "anchors": len(seed.anchors),
        "flags": list(seed.flags),
        "channels": [list(c) for c in seed.channels],
        "max_weight": max((a.weight for a in seed.anchors), default=0.0),
    }


def _cap(started: int, cap_seconds: float, root: Path, done: int, planned: int) -> None:
    elapsed = (time.perf_counter_ns() - started) / 1e9
    if elapsed > cap_seconds:
        write_once(
            root / "aborted.json",
            {"reason": "WALL_CAP_EXCEEDED", "elapsed_s": elapsed, "queries_done": done,
             "planned": planned},
        )  # fmt: skip
        raise NornError("WALL_CAP_EXCEEDED")


def topology_walks(
    store: Path,
    public: PublicInput,
    case: MultiHopCase,
    track: str,
    atom_of: dict[str, str],
    seed: Seed,
) -> dict[str, Any]:
    """Derive one topology in a throw-away store and walk it with the shared seed.

    Each track has its own copy of the pristine store, so no oracle edge can reach a derived
    topology and no derived edge reaches the base store the evidence is assembled from."""
    tick = time.perf_counter_ns()
    with Engine(store, host(public)) as engine:
        if track == TRACK_GOLD:
            ids = {s.source_id for s in public.sources}
            edges, _unpublished = gold_edges(case, ids)
            extra: dict[str, Any] = write_gold_diagnostic(engine, edges, atom_of)
        else:
            report = extract_relations(engine.registry, track)
            extra = {"requires": report.requires, "hypotheses": report.hypotheses}
        graph = build_graph(engine.registry)
        topology_ns = time.perf_counter_ns() - tick
        budget = QueryBudget(120_000, Event())
        with budget.sqlite_guard(engine.db.connection):
            arms = walk_arms(engine.registry, graph, seed, budget.checkpoint)
    return {
        "track": track,
        "topology_ns": topology_ns,
        "extraction": extra,
        "edges": len(graph.edges),
        "graph_digest": graph.digest(),
        "arms": arms,
    }


def conventional_pool(
    engine: Engine, request: RecallRequest, budget: QueryBudget
) -> tuple[EligibleCorpus, int, int, tuple[Hit, ...]]:
    """G0's ranked candidate pool: the R2 recipe of the recall service (exact union, BM25, dense).

    The recipe is repeated here because the service returns only the packaged evidence; the
    run's control compares G0's evidence with the attested R2 evidence of the same query."""
    epoch = engine.access.check("READ")
    corpus = exact.eligible(engine, request, budget.checkpoint)
    _snapshot_id, index = local.load(engine, corpus, ("lexical", "dense"), budget)
    structured = exact.lookup(corpus, request)
    lex = lexical.search(
        corpus,
        request.text,
        request.candidate_limit,
        {k: v["terms"] for k, v in index["lexical"].items()},
        budget.checkpoint,
    )
    models = engine.local_models
    require(models is not None, "LOCAL_MODELS_NOT_ENABLED")
    assert models is not None
    query = dense.encode((request.text,), models, budget, query=True)[0]
    vectors = {k: tuple(v["vector"]) for k, v in index["dense"].items()}
    nearest = dense.search(corpus, query, vectors, request.candidate_limit, budget.checkpoint)
    pool = fusion.fuse(structured, (lex, nearest), request.candidate_limit)
    return corpus, corpus.snapshot, epoch, pool


def package(
    engine: Engine,
    request: RecallRequest,
    ranked: tuple[Hit, ...],
    corpus: EligibleCorpus,
    snapshot: int,
    epoch: int,
    budget: QueryBudget,
    public: PublicInput,
    mapping: dict[str, str],
) -> Result:
    """Evidence packaging and sufficiency by the recall owner, exactly as every conventional arm."""
    data, hits = assemble_hits(
        engine, request, ranked, snapshot, epoch, budget, {}, complete=corpus.complete
    )
    packet = RecallView(engine, request, hits, snapshot, epoch, data).serialize()
    sources = {s.source_id: s for s in public.sources}
    found = []
    for record in packet["evidence"]:
        require(record["atom_id"] in mapping, "SOURCE_MAPPING_MISSING")
        source = sources[mapping[record["atom_id"]]]
        require(
            record["text"] == source.text and record["sha256"] == source.sha256,
            "SOURCE_MAPPING_MISMATCH",
        )
        found.append(candidate(source))
    return Result(
        "OK",
        packet["status"],
        tuple(found),
        coverage=packet["coverage"],
        reason=packet["reason"],
        missing_fields=tuple(packet["missing_fields"]),
    )


def source_run_facts(source_run: Path) -> dict[str, Any]:
    manifest = load(source_run / "manifest.json")
    completion = load(source_run / "completion.json")
    require(
        manifest["run_kind"] == "MULTIHOP_CONVENTIONAL_DEVELOPMENT"
        and manifest["partition_role"] == "pilot"
        and manifest["config"]["strata"] == list(STRATA)
        and manifest["config"]["limit_per_family"] is None,
        "SOURCE_RUN_NOT_THE_T20_PILOT",
    )
    return {
        "manifest_digest": completion["manifest_digest"],
        "ledger_digest": completion["ledger_digest"],
        "final_chain_digest": completion["final_chain_digest"],
        "code_digest": manifest["code_digest"],
        "seed": manifest["seed"],
    }


def reference_sources(source_run: Path) -> dict[str, list[str]]:
    """Ordered evidence sources of the attested R2 rows, by query (the G0 control)."""
    result: dict[str, list[str]] = {}
    with (source_run / "ledger.jsonl").open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            if row["arm_id"] == "R2" and row["result"]["disposition"] == "OK":
                result[row["query_id"]] = [c["source_id"] for c in row["result"]["candidates"]]
    return result


def run_graph_pilot(
    destination: Path,
    *,
    source_run: Path,
    source_attestation: Path,
    seed: int,
    model_root: Path,
    enable_models: bool,
    wall_cap_seconds: float,
    cap_basis: str,
    limit_per_family: int | None = None,
    strata: tuple[str, ...] = STRATA,
    preregistration: Path = REPO / PREREGISTRATION,
) -> dict[str, Any]:
    authorize_partition("pilot", "pilot")
    require(not destination.exists(), "RUN_DIRECTORY_EXISTS")
    require(enable_models, "BASELINE_ENABLEMENT_REQUIRED")
    require(wall_cap_seconds > 0 and bool(cap_basis), "WALL_CAP_REQUIRED")
    require(bool(strata) and set(strata) <= set(STRATA), "UNSUPPORTED_STRATUM")
    from benchmark.runs.seal import verify

    verify(source_run, source_attestation)
    registered = preregistration_digest(preregistration)  # the endpoints are fixed before the run
    source = source_run_facts(source_run)
    require(source["seed"] == seed, "SOURCE_RUN_SEED_MISMATCH")
    source_revision = code_digest()
    started = time.perf_counter_ns()
    selected = cases_for(seed, "pilot", strata, limit_per_family)
    require(0 < len(selected) <= 2000, "RUN_QUERY_BUDGET")
    reference = reference_sources(source_run)
    preparations = load(source_run / "preparations.json")
    inputs: dict[str, PublicInput] = {}
    stratum_of: dict[str, str] = {}
    for stratum, case in selected:
        public = publish(case.case, (MARKER,))
        if stratum != "TEMPLATE":
            require_labelled(public)
        qid = case.case.query.query_id
        original = validate_public(load(source_run / "published" / (qid + ".json")))
        require(original.sha256 == public.sha256, "PUBLISHED_INPUT_DIFFERS_FROM_T20")
        require(preparations[qid]["input_digest"] == public.sha256, "PREPARATION_INPUT_DIFFERS")
        inputs[qid] = public
        stratum_of[qid] = stratum
    artifacts = {
        "evaluator/gold.json": write_once(
            destination / "evaluator/gold.json", [gold_payload(c.case) for _s, c in selected]
        ),
        "evaluator/strata.json": write_once(destination / "evaluator/strata.json", stratum_of),
    }
    plan = [
        [qid, track, arm]
        for qid in inputs
        for track, strata in TOPOLOGIES
        if stratum_of[qid] in strata
        for arm in GRAPH_ARMS
    ] + [[qid, NO_TOPOLOGY, "G0"] for qid in inputs]
    manifest: dict[str, Any] = {
        "schema": 1,
        "run_kind": RUN_KIND,
        "sealed": False,
        "partition": "pilot",
        "partition_role": "pilot",
        "seed": seed,
        "code_digest": source_revision,
        "arms": list(ARMS),
        "planned_rows": plan,
        "artifacts": artifacts,
        "hardware": hardware(),
        "evaluation_time": "2026-10-23T00:00:00+00:00",
        "retrieval_models": MODELS,
        "retrieval_methods": METHODS,
        "config": {
            "strata": list(strata),
            "limit_per_family": limit_per_family,
            "topologies": [[t, list(s)] for t, s in TOPOLOGIES],
            "revisions": REVISIONS | {TRACK_GOLD: "oracle"},
            "merge_rule": MERGE_RULE,
            "seed_channels": list(CONVENTIONAL),
            "walks": walk_config(),
            "output_limit": 10,
            "candidate_pool": 60,
            "g0_recipe": "R2_EXACT_UNION_BM25_DENSE_RRF_K60",
            "source_run": source,
            "preregistration": {"path": PREREGISTRATION, "section_digest": registered},
            "benefit_estimand": "SUPPORTED_CASE_COMPLETE_SET_ITT_FAILURE_ZERO",
            "wall_cap": {"seconds": wall_cap_seconds, "basis": cap_basis},
            "label": LABEL,
            "status_semantics": "SUFFICIENCY_BY_THE_RECALL_OWNER_ON_THE_ARMS_OWN_EVIDENCE",
        },
        "custody": "TRUSTED_IN_PROCESS; STRUCTURAL_AND_PUBLICATION_BARRIER; NOT_OS_SANDBOX",
        "created_at": datetime.now(UTC).isoformat(),
    }
    manifest_hash = write_once(destination / "manifest.json", manifest)
    token_counter = EvidenceTokenizer(model_root)
    spec = arm_spec("R2")
    chain = manifest_hash
    counts: dict[str, int] = {}
    work = destination / "work"
    rows = 0
    mismatches = 0
    with (destination / "ledger.jsonl").open("xb") as stream:

        def write(row: dict[str, Any]) -> None:
            nonlocal chain, rows
            row = {**row, "attempt": 1, "provider_calls": 0, "previous_digest": chain}
            chain = digest(canonical(row).encode())
            stream.write((canonical({**row, "record_digest": chain}) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
            rows += 1
            counts[row["result"]["disposition"]] = counts.get(row["result"]["disposition"], 0) + 1

        for done, (stratum, case) in enumerate(selected):
            _cap(started, wall_cap_seconds, destination, done, len(selected))
            qid = case.case.query.query_id
            public = inputs[qid]
            mapping: dict[str, str] = preparations[qid]["mapping"]
            atom_of = {s: a for a, s in mapping.items()}
            tracks = [t for t, strata in TOPOLOGIES if stratum in strata]
            origin = source_run / "stores" / qid
            copies = {name: work / qid[:24] / name for name in ("base", *tracks)}
            for target in copies.values():
                shutil.copytree(origin, target)
            request = interpret(public, "R2")
            walked: dict[str, dict[str, Any]] = {}
            with Engine(
                copies["base"], host(public), model_root=model_root, enable_models=True
            ) as engine:
                budget = QueryBudget(request.deadline_ms, Event())
                with budget.sqlite_guard(engine.db.connection):
                    tick = time.perf_counter_ns()
                    shared = build_seed(engine, request, CONVENTIONAL)
                    seed_ns = time.perf_counter_ns() - tick
                    tick = time.perf_counter_ns()
                    corpus, snapshot, epoch, pool = conventional_pool(engine, request, budget)
                    g0 = package(
                        engine, request, pool, corpus, snapshot, epoch, budget, public, mapping
                    )
                    g0_ns = time.perf_counter_ns() - tick
                    tokens = validate_result(public, g0, spec, token_counter)
                    control = [c.source_id for c in g0.candidates] == reference.get(qid)
                    mismatches += not control
                    write(
                        {
                            "query_id": qid,
                            "arm_id": "G0",
                            "topology": NO_TOPOLOGY,
                            "input_digest": public.sha256,
                            "result": asdict(g0),
                            "elapsed_ns": g0_ns,
                            "seed_ns": seed_ns,
                            "evidence_tokens": tokens,
                            "seed": seed_record(shared),
                            "graph": None,
                            "g0_matches_t20_r2": control,
                            "pool": len(pool),
                        }
                    )
                    for track in tracks:
                        walked[track] = topology_walks(
                            copies[track], public, case, track, atom_of, shared
                        )
                        for arm in GRAPH_ARMS:
                            proposal = walked[track]["arms"][arm]
                            tick = time.perf_counter_ns()
                            hits = graph_hits(corpus, proposal["sources"])
                            merged = merge(pool, hits, request.candidate_limit)
                            result = package(
                                engine, request, merged, corpus, snapshot, epoch, budget,
                                public, mapping,
                            )  # fmt: skip
                            merge_ns = time.perf_counter_ns() - tick
                            in_pool = {h.record.key for h in pool}
                            write(
                                {
                                    "query_id": qid,
                                    "arm_id": arm,
                                    "topology": track,
                                    "input_digest": public.sha256,
                                    "result": asdict(result),
                                    "elapsed_ns": merge_ns + proposal["cost"]["graph_ns"],
                                    "seed_ns": 0,
                                    "evidence_tokens": validate_result(
                                        public, result, spec, token_counter
                                    ),
                                    "seed": None,
                                    "graph": {
                                        **proposal["cost"],
                                        "track": track,
                                        "topology_ns": walked[track]["topology_ns"],
                                        "topology_edges": walked[track]["edges"],
                                        "topology_digest": walked[track]["graph_digest"],
                                        "proposed": len(proposal["sources"]),
                                        "proposed_published": [
                                            mapping[h.record.atom_id] for h in hits
                                        ],
                                        "mapped": len(hits),
                                        "new_in_pool": sum(
                                            h.record.key not in in_pool for h in hits
                                        ),
                                    },
                                    "g0_matches_t20_r2": None,
                                    "pool": len(pool),
                                }
                            )
            shutil.rmtree(work / qid[:24])
    shutil.rmtree(work, ignore_errors=True)
    require(code_digest() == source_revision, "RUN_CODE_CHANGED_DURING_EXECUTION")
    require(rows == len(plan), "PLANNED_ROW_ACCOUNTING")
    completion = {
        "manifest_digest": manifest_hash,
        "ledger_digest": file_digest(destination / "ledger.jsonl"),
        "final_chain_digest": chain,
        "observations": rows,
        "dispositions": counts,
        "g0_control_mismatches": mismatches,
        "elapsed_s": (time.perf_counter_ns() - started) / 1e9,
    }
    write_once(destination / "completion.json", completion)
    return completion


# --- statistics (pure, hand-checkable) ---------------------------------------------------------


def wilson(successes: int, trials: int, level: float = CONFIDENCE) -> list[float] | None:
    """Wilson score interval of a proportion; None when there is no denominator."""
    require(0 <= successes <= trials and 0 < level < 1, "INVALID_PROPORTION")
    if trials == 0:
        return None
    z = statistics.NormalDist().inv_cdf(0.5 + level / 2)
    p = successes / trials
    centre = (p + z * z / (2 * trials)) / (1 + z * z / trials)
    half = (
        z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / (1 + z * z / trials)
    )
    # The bounds at zero and at all successes are exact, not the rounding of the formula.
    low = 0.0 if successes == 0 else max(0.0, centre - half)
    high = 1.0 if successes == trials else min(1.0, centre + half)
    return [low, high]


def required_clusters(
    sigma: float, delta: float, alpha: float = ALPHA, power: float = POWER
) -> int:
    """Clusters for a two-sided test of a mean paired difference ``delta`` at SD ``sigma``."""
    require(sigma >= 0 and delta > 0 and 0 < alpha < 1 and 0 < power < 1, "INVALID_POWER_INPUT")
    z = statistics.NormalDist()
    return math.ceil(((z.inv_cdf(1 - alpha / 2) + z.inv_cdf(power)) * sigma / delta) ** 2)


def minimum_detectable(
    sigma: float, clusters: int, alpha: float = ALPHA, power: float = POWER
) -> float:
    """The smallest mean paired difference detectable with ``clusters`` at SD ``sigma``."""
    require(sigma >= 0 and clusters >= 1 and 0 < alpha < 1 and 0 < power < 1, "INVALID_POWER_INPUT")
    z = statistics.NormalDist()
    return (z.inv_cdf(1 - alpha / 2) + z.inv_cdf(power)) * sigma / math.sqrt(clusters)


def cluster_sd(differences: dict[str, list[float]]) -> dict[str, Any]:
    """SD of the cluster means of a paired difference, with a bootstrap upper bound for it.

    Clusters are the unit: each cluster's differences are averaged first, so the SD is the one
    the cluster bootstrap and the power formula use. The upper value is the 95th percentile of
    the SD over cluster resamples (fixed seed), a conservative planning value for few clusters."""
    means = {c: statistics.mean(v) for c, v in sorted(differences.items()) if v}
    values = list(means.values())
    if len(values) < 2:
        return {"clusters": len(values), "sd": None, "sd_upper_95": None}
    import random

    rng = random.Random(SEED_BASE)
    draws = sorted(
        statistics.stdev(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_SAMPLES)
    )
    return {
        "clusters": len(values),
        "mean": statistics.mean(values),
        "sd": statistics.stdev(values),
        "sd_upper_95": draws[int((BOOTSTRAP_SAMPLES - 1) * 0.95)],
        "nonzero_clusters": sum(v != 0 for v in values),
    }


def power_table(sd: float | None, sd_upper: float | None) -> dict[str, Any]:
    """Clusters needed per margin and the margin each role can detect, at the pilot SD values."""
    values = {"observed": sd, "upper_95": sd_upper} | {f"assumed_{s}": s for s in SIGMAS}
    table: dict[str, Any] = {}
    for name, sigma in values.items():
        if sigma is None:
            continue
        table[name] = {
            "sigma": sigma,
            "clusters_needed": {str(d): required_clusters(sigma, d) for d in DELTAS},
            "minimum_detectable": {
                role: minimum_detectable(sigma, n) for role, n in ROLE_PRIMARY_CLUSTERS.items()
            },
        }
    return table


def false_association_sources(case: MultiHopCase) -> frozenset[str]:
    """Published sources that state a decoy or same-name-twin association (M3 and M5 only)."""
    graph = case.graph
    if graph.family == "M3":
        return frozenset(graph.decoy_sources)
    if graph.family != "M5":
        return frozenset()
    name = {hidden: display for hidden, display, _key in graph.nodes}
    twins = {h for h, n in name.items() if n == name[graph.seed_node]} - {graph.seed_node}
    reached = set(twins)
    changed = True
    while changed:
        changed = False
        for tail, head, _relation, _source in graph.edges:
            if tail in reached and head not in reached:
                reached.add(head)
                changed = True
    return frozenset(s for tail, _head, _r, s in graph.edges if tail in reached)


# --- reload, validation and scoring ------------------------------------------------------------


def validate_graph_pilot(
    root: Path,
    *,
    model_root: Path,
    attestation: Path | None = None,
    development_only: bool = False,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Reload every artifact, regenerate the cases and re-score every ledger row."""
    status = require_attestation(attestation, development_only)
    if attestation is not None:
        from benchmark.runs.seal import verify

        verify(root, attestation)
    manifest, completion = load(root / "manifest.json"), load(root / "completion.json")
    require(
        manifest["schema"] == 1
        and manifest["run_kind"] == RUN_KIND
        and manifest["sealed"] is False
        and manifest["partition_role"] == "pilot",
        "UNSUPPORTED_RUN",
    )
    authorize_partition("pilot", manifest["partition"])
    require(manifest["code_digest"] == code_digest(), "RUN_CODE_MISMATCH")
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
    require(config["walks"] == walk_config(), "WALK_SETTINGS_CHANGED")
    require(config["merge_rule"] == MERGE_RULE, "MERGE_RULE_CHANGED")
    require(
        config["preregistration"]["section_digest"]
        == preregistration_digest(repo / config["preregistration"]["path"]),
        "PREREGISTRATION_CHANGED",
    )
    expected_cases = cases_for(
        manifest["seed"], "pilot", tuple(config["strata"]), config["limit_per_family"]
    )
    gold_rows = load(root / "evaluator/gold.json")
    require(
        canonical(gold_rows) == canonical([gold_payload(c.case) for _s, c in expected_cases]),
        "GOLD_GENERATOR_LINEAGE_CHANGED",
    )
    gold = {row["query_id"]: gold_from(row) for row in gold_rows}
    strata = load(root / "evaluator/strata.json")
    require(
        strata == {c.case.query.query_id: s for s, c in expected_cases}, "STRATA_LINEAGE_CHANGED"
    )
    cases = {c.case.query.query_id: c for _s, c in expected_cases}
    public: dict[str, PublicInput] = {}
    for stratum, case in expected_cases:
        item = publish(case.case, (MARKER,))
        require(
            (stratum == "TEMPLATE") == all(label_of(s) is None for s in item.sources),
            "STRATUM_LABEL_MISMATCH",
        )
        public[case.case.query.query_id] = item
    planned = {tuple(p) for p in manifest["planned_rows"]}
    require(len(planned) == len(manifest["planned_rows"]), "PLANNED_ROW_ACCOUNTING")
    spec = arm_spec("R2")
    token_counter = EvidenceTokenizer(model_root)
    previous = completion["manifest_digest"]
    seen: set[tuple[str, str, str]] = set()
    scored: list[dict[str, Any]] = []
    with (root / "ledger.jsonl").open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            checksum = row.pop("record_digest")
            require(
                row["previous_digest"] == previous and digest(canonical(row).encode()) == checksum,
                "LEDGER_CHAIN_CHANGED",
            )
            previous = checksum
            key = (row["query_id"], row["topology"], row["arm_id"])
            require(key in planned and key not in seen and row["attempt"] == 1, "LEDGER_ROW_PLAN")
            seen.add(key)
            qid = row["query_id"]
            require(
                row["input_digest"] == public[qid].sha256 and row["provider_calls"] == 0,
                "ARM_INPUT_OR_PROVIDER_CHANGED",
            )
            result = result_from(row["result"])
            tokens = validate_result(public[qid], result, spec, token_counter)
            require(tokens == row["evidence_tokens"], "TOKEN_ACCOUNTING_CHANGED")
            retrieval = retrieval_scores(public[qid], result, spec, gold[qid], token_counter)
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
            returned = normalized_sources(public[qid], result, spec, token_counter)
            twins = false_association_sources(cases[qid])
            actual = set(returned)
            published = frozenset(s.source_id for s in public[qid].sources)
            covered = sum(bool(set(slot) & published & actual) for slot in gold[qid].slots)
            proposed = row["graph"]["proposed_published"] if row["graph"] else None
            proposal = (
                None
                if proposed is None
                else {
                    "complete": evidence_scores(tuple(proposed), gold[qid], published)[
                        "complete_set"
                    ],
                    "top10_complete": evidence_scores(tuple(proposed[:10]), gold[qid], published)[
                        "complete_set"
                    ],
                }
            )
            scored.append(
                {
                    "query_id": qid,
                    "arm_id": row["arm_id"],
                    "topology": row["topology"],
                    "family": gold[qid].family,
                    "cluster": gold[qid].cluster,
                    "variant": gold[qid].variant,
                    "stratum": strata[qid],
                    "elapsed_ns": row["elapsed_ns"],
                    "retrieval": retrieval,
                    "answer": answer,
                    "returned": list(returned),
                    "covered_slots": covered,
                    "false_association": bool(actual & twins) if twins else None,
                    "graph": row["graph"],
                    "proposal": proposal,
                    "seed": row["seed"],
                    "g0_matches_t20_r2": row["g0_matches_t20_r2"],
                }
            )
    require(seen == planned and len(seen) == completion["observations"], "MISSING_LEDGER_ROW")
    require(previous == completion["final_chain_digest"], "COMPLETION_CHANGED")
    return {
        "evidence_status": status,
        "run_kind": RUN_KIND,
        "manifest": {
            k: manifest[k] for k in ("seed", "partition", "code_digest", "config", "hardware")
        },
        "completion": completion,
        "observations": scored,
    }


# --- the report --------------------------------------------------------------------------------


def _cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [r for r in rows if r["answer"]["full_answerable"]]
    insufficient = [r for r in rows if r["answer"]["insufficient_for_full"]]
    hits = sum(r["retrieval"]["complete_set"] is True for r in applicable)
    twins = [r for r in rows if r["false_association"] is not None]
    return {
        "planned": len(rows),
        "observed": sum(r["answer"]["observed"] for r in rows),
        "slot_recall_numerator": hits,
        "slot_recall_denominator": len(applicable),
        "slot_recall": hits / len(applicable) if applicable else None,
        "slot_recall_wilson_95": wilson(hits, len(applicable)),
        "status_correct": sum(r["answer"]["status_correct"] is True for r in rows),
        "status_denominator": sum(r["answer"]["observed"] for r in rows),
        "false_answers": sum(r["answer"]["false_answer"] is True for r in rows),
        "false_answer_denominator": len(insufficient),
        "false_abstentions": sum(_abstained(r) for r in applicable),
        "false_abstention_denominator": len(applicable),
        "false_associations": sum(r["false_association"] is True for r in twins),
        "false_association_denominator": len(twins),
        "privacy_incidents": sum(r["answer"]["privacy_incidents"] for r in rows),
        "mean_covered_slots": statistics.mean(r["covered_slots"] for r in rows) if rows else None,
    }


def _abstained(row: dict[str, Any]) -> bool:
    """False abstention with an unobserved answer counted as one (intent to treat)."""
    return (not row["answer"]["observed"]) or row["answer"]["false_abstention"] is True


ENDPOINTS: dict[str, tuple[Callable[[dict[str, Any]], bool], Callable[[dict[str, Any]], float]]] = {
    "slot_recall": (
        lambda r: bool(r["answer"]["full_answerable"]),
        lambda r: float(r["retrieval"]["complete_set"] is True),
    ),
    "false_answer": (
        lambda r: bool(r["answer"]["insufficient_for_full"]),
        lambda r: float(r["answer"]["false_answer"] is True),
    ),
    "false_abstention": (
        lambda r: bool(r["answer"]["full_answerable"]),
        lambda r: float(_abstained(r)),
    ),
    "false_association": (
        lambda r: r["false_association"] is not None,
        lambda r: float(r["false_association"] is True),
    ),
}


def _select(
    rows: list[dict[str, Any]], arm: str, topology: str, families: tuple[str, ...], strata: set[str]
) -> dict[str, dict[str, Any]]:
    return {
        r["query_id"]: r
        for r in rows
        if r["arm_id"] == arm
        and r["topology"] == topology
        and r["family"] in families
        and r["stratum"] in strata
    }


def contrast(
    rows: list[dict[str, Any]],
    endpoint: str,
    left: tuple[str, str],
    right: tuple[str, str],
    *,
    families: tuple[str, ...] = PRIMARY,
    strata: set[str] | None = None,
) -> dict[str, Any]:
    """Equal-cluster-mean paired difference ``left - right`` with its cluster SD and power table.

    G0 has no topology, so its rows pair with a topology's rows by query id. Only queries both
    sides observed under the endpoint's own denominator enter, and the denominator is reported."""
    applies, value = ENDPOINTS[endpoint]
    chosen = strata if strata is not None else set(STRATA)
    a = _select(rows, left[0], left[1], families, chosen)
    b = _select(rows, right[0], right[1], families, chosen)
    ids = sorted(q for q in a if q in b and applies(a[q]))
    result: dict[str, Any] = {
        "endpoint": endpoint,
        "left": list(left),
        "right": list(right),
        "families": list(families),
        "strata": sorted(chosen),
        "pairs": len(ids),
    }
    if not ids:
        return result | {"difference": None, "state": "NO_APPLICABLE_PAIRS"}
    left_values = tuple(PairedValue(q, a[q]["cluster"], None, value(a[q])) for q in ids)
    right_values = tuple(PairedValue(q, b[q]["cluster"], None, value(b[q])) for q in ids)
    stats = paired_difference(left_values, right_values, seed=SEED_BASE, samples=BOOTSTRAP_SAMPLES)
    per_cluster: dict[str, list[float]] = defaultdict(list)
    for x, y in zip(left_values, right_values, strict=True):
        per_cluster[x.cluster_id].append(x.value - y.value)
    spread = cluster_sd(per_cluster)
    return (
        result
        | stats
        | {
            "cluster_spread": spread,
            "power": power_table(spread["sd"], spread["sd_upper_95"]),
        }
    )


def _qs(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "max": None}
    ordered = sorted(values)

    def pick(q: float) -> float:
        return ordered[max(0, math.ceil(q * len(ordered)) - 1)]

    return {"p50": pick(0.5), "p95": pick(0.95), "max": ordered[-1]}


def _costs(rows: list[dict[str, Any]], arm: str, topology: str) -> dict[str, Any]:
    mine = [r for r in rows if r["arm_id"] == arm and r["topology"] == topology]
    graph = [r["graph"] for r in mine if r["graph"]]
    base = {r["query_id"]: r for r in rows if r["arm_id"] == "G0"}
    gained = lost = 0
    for r in mine:
        if r["answer"]["full_answerable"]:
            delta = r["covered_slots"] - base[r["query_id"]]["covered_slots"]
            gained += max(0, delta)
            lost += max(0, -delta)
    nodes = sum(g["nodes"] for g in graph)
    supported = [r for r in mine if r["answer"]["full_answerable"] and r["proposal"]]
    return {
        "supported_queries": len(supported),
        "proposal_complete": sum(r["proposal"]["complete"] is True for r in supported),
        "proposal_top10_complete": sum(r["proposal"]["top10_complete"] is True for r in supported),
        "queries": len(mine),
        "elapsed_ms": _qs([r["elapsed_ns"] / 1e6 for r in mine]),
        "nodes": _qs([g["nodes"] for g in graph]),
        "edges": _qs([g["edges"] for g in graph]),
        "transitions": _qs([g["counters"].get("transitions", 0) for g in graph]),
        "bound_or_flagged": sum(bool(g["flags"]) for g in graph),
        "walks_with_unlinked_anchors": sum(g["unlinked"] > 0 for g in graph),
        "proposed_sources": _qs([g["proposed"] for g in graph]),
        "new_to_the_pool": sum(g["new_in_pool"] for g in graph),
        "gold_slots_gained_over_g0": gained,
        "gold_slots_lost_against_g0": lost,
        "visited_nodes_total": nodes,
        "useful_extra_per_1000_visited_nodes": gained / nodes * 1000 if nodes else None,
    }


def report_graph_pilot(
    root: Path,
    model_root: Path,
    attestation: Path | None = None,
    *,
    development_only: bool = False,
) -> dict[str, Any]:
    result = validate_graph_pilot(
        root, model_root=model_root, attestation=attestation, development_only=development_only
    )
    rows = result["observations"]
    topologies = [t for t, _s in TOPOLOGIES]
    cells: dict[str, Any] = {}
    for family in FAMILIES:
        for stratum in STRATA:
            for arm, topology in [("G0", NO_TOPOLOGY)] + [
                (a, t) for t in topologies for a in GRAPH_ARMS
            ]:
                chosen = [
                    r
                    for r in rows
                    if (r["family"], r["stratum"], r["arm_id"], r["topology"])
                    == (family, stratum, arm, topology)
                ]
                if chosen:
                    cells[f"{family}|{stratum}|{topology}|{arm}"] = _cell(chosen)
    pooled = {
        f"{topology}|{arm}": _cell(
            [
                r
                for r in rows
                if r["family"] in PRIMARY and r["arm_id"] == arm and r["topology"] == topology
            ]
        )
        for arm, topology in [("G0", NO_TOPOLOGY)] + [(a, TRACK_TEXT) for a in GRAPH_ARMS]
    }
    text = TRACK_TEXT
    template = {"TEMPLATE"}
    primary = {
        "G3_minus_G0": contrast(rows, "slot_recall", ("G3", text), ("G0", NO_TOPOLOGY)),
        "G3_minus_G1": contrast(rows, "slot_recall", ("G3", text), ("G1", text)),
        "G2_minus_G3": contrast(rows, "slot_recall", ("G2", text), ("G3", text)),
        "G4_minus_G3": contrast(rows, "slot_recall", ("G4", text), ("G3", text)),
        "G1_minus_G0": contrast(rows, "slot_recall", ("G1", text), ("G0", NO_TOPOLOGY)),
    }
    controls = {
        f"G3_{track}_minus_G0_TEMPLATE": contrast(
            rows,
            "slot_recall",
            ("G3", track),
            ("G0", NO_TOPOLOGY),
            strata=template,
        )
        for track in (TRACK_READBACK, TRACK_GOLD)
    }
    families_harm = {"false_answer": FAMILIES, "false_abstention": FAMILIES}
    harm = {
        f"G3_minus_G0_{endpoint}": contrast(
            rows,
            endpoint,
            ("G3", text),
            ("G0", NO_TOPOLOGY),
            families=families_harm.get(endpoint, ("M3", "M5")),
        )
        for endpoint in ("false_answer", "false_abstention", "false_association")
    }
    exposures = sum(
        1
        for r in rows
        if r["answer"]["privacy_observed"] and r["answer"]["privacy_canaries_present"]
    )
    seeds = [r for r in rows if r["arm_id"] == "G0"]
    seed_summary = {
        f"{family}|{stratum}": {
            "queries": len(chosen),
            "exact_degraded": sum("EXACT_CHANNEL_DEGRADED" in r["seed"]["flags"] for r in chosen),
            "anchors": _qs([r["seed"]["anchors"] for r in chosen]),
            "max_anchor_weight": _qs([r["seed"]["max_weight"] for r in chosen]),
        }
        for family in FAMILIES
        for stratum in STRATA
        if (chosen := [r for r in seeds if r["family"] == family and r["stratum"] == stratum])
    }
    return {
        **{k: v for k, v in result.items() if k != "observations"},
        "label": LABEL,
        "definitions": {
            "slot_recall": "complete evidence set among gold SUPPORTED queries, "
            "failures count zero",
            "primary_families": list(PRIMARY),
            "estimand": "EQUAL_CLUSTER_MEAN_PAIRED_DIFFERENCE, strata pooled inside a cluster",
            "status": "reported separately; on the chain families the interpreter clears the "
            "requested fields, so status is unchanged by the evidence by construction",
            "false_association": "M3 and M5 queries whose returned evidence includes a decoy "
            "or same-name-twin source",
            "useful_extra": "gold slots a graph arm covers that G0 does not, "
            "per 1,000 visited nodes",
            "power": "two-sided alpha 0.05, power 0.80, normal approximation, cluster SD",
            "unequal_control": "the oracle topology is an upper bound, "
            "never an arm of the contrast family",
        },
        "pooled_primary_text_topology": pooled,
        "cells": cells,
        "contrasts": adjust_family(primary),
        "controls_descriptive": controls,
        "harm": harm,
        "costs": {
            f"{topology}|{arm}": _costs(rows, arm, topology)
            for arm, topology in [(a, t) for t in topologies for a in GRAPH_ARMS]
        },
        "seed": seed_summary,
        "privacy": {
            "incidents": sum(r["answer"]["privacy_incidents"] for r in rows),
            "exposures": exposures,
            "zero_incident_upper_bound_95": zero_incident_bound(exposures),
            "scope": "private M4 sources are never published to the runtime store; the denied-"
            "bridge walk control is tests/test_diffusion_privacy.py",
        },
        "g0_control": {
            "rows": len(seeds),
            "matches_attested_r2": sum(r["g0_matches_t20_r2"] is True for r in seeds),
        },
        "limits": (
            "Pilot role only (24 clusters, 20 primary), synthetic template and NOISY_V1 "
            "renderings, untuned owner-set walk defaults, no tune or evaluation role read, no G5, "
            "G6 or G7, no benefit claim; CPU serial; seeds are the conventional channels."
        ),
        "stratum_label": STRATUM,
    }
