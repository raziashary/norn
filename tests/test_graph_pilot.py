"""P06-T21: the graph pilot runner's guards, statistics and wiring.

The real G0 to G4 observations come from ``norn-benchmark run-graph-pilot`` over the attested
T20 pilot stores and are reloaded by ``graph-pilot-report`` (EVIDENCE_LOG E-P06-014). This file
proves, with exact hand-computed values, the pieces around that run: the merge rule, the false
association definition, the paired contrasts, the variance and power arithmetic, the refusals
and the pilot-only boundary. One small real run (template stratum, one case per family) is
included when the T20 stores and the pinned local models exist on this machine.
"""

import json
import math
import shutil
import statistics
import time
from pathlib import Path

import pytest
from test_multihop_fixtures import first

from benchmark.fixtures.multihop import MultiHopCase
from benchmark.runs import graph_pilot
from benchmark.runs.graph_pilot import (
    ALPHA,
    ARMS,
    CLUSTERS,
    MARGINS,
    NO_TOPOLOGY,
    POWER,
    TOPOLOGIES,
    cluster_sd,
    contrast,
    false_association_sources,
    graph_hits,
    merge,
    minimum_detectable,
    power_table,
    preregistration_digest,
    required_clusters,
    run_graph_pilot,
    source_run_facts,
    validate_graph_pilot,
    verdict,
    walk_config,
    wilson,
)
from norn.contracts.errors import NornError
from norn.retrieval.contracts import EligibleCorpus, Hit, Record

TEXT = TOPOLOGIES[0][0]
ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / ".norn" / "p06-t20-run-001"
ATTESTATION = ROOT / "docs" / "development" / "evidence" / "run_attestation_p06-t20-run-001.json"
MODELS = ROOT / ".norn" / "models"


def record(name: str, source: str | None = None) -> Record:
    return Record(
        "ns", "event-" + name, "atom-" + name, "entity-" + name, (), "p", "{}", "{}", None, "a",
        "ok", "applicable", "2026-10-20T09:00:00+00:00", source or "source-" + name, "v1", 0, 1,
        "00", "text-" + name, 1,
    )  # fmt: skip


def hit(name: str, source: str | None = None) -> Hit:
    return Hit(record(name, source), 0.0, "test")


# --- the merge rule ----------------------------------------------------------------------------


def test_merge_is_the_conventional_rrf_rule_and_a_graph_channel_can_move_a_record_up():
    pool = tuple(hit(n) for n in "abcd")  # G0 order
    only_pool = merge(pool, (), 60)
    assert [h.record.atom_id for h in only_pool] == ["atom-" + n for n in "abcd"]  # G0 unchanged
    graph = (hit("d"), hit("x"))
    merged = merge(pool, graph, 60)
    # d: 1/64 + 1/61, a: 1/61, x: 1/62 (graph rank 2 only), b: 1/62 ... hand-computed order
    scores = {
        "d": 1 / 64 + 1 / 61,
        "a": 1 / 61,
        "b": 1 / 62,
        "x": 1 / 62,
        "c": 1 / 63,
    }
    expected = sorted(scores, key=lambda k: (-scores[k], "atom-" + k))
    assert [h.record.atom_id for h in merged] == ["atom-" + k for k in expected]
    assert merged[0].record.atom_id == "atom-d"  # positive control: the graph moved d to rank one
    assert len(merge(pool, graph, 3)) == 3  # the pool limit still bounds the fused list


def test_graph_hits_keep_proposal_order_once_and_drop_what_the_corpus_does_not_hold():
    corpus = EligibleCorpus(tuple(record(n) for n in "abc"), 1, 1, True, None)
    hits = graph_hits(corpus, ["source-c", "source-zzz", "source-a", "source-c"])
    assert [h.record.atom_id for h in hits] == ["atom-c", "atom-a"]  # no duplicate, no invented one
    assert hits[0].channel == "graph"
    assert graph_hits(corpus, []) == ()
    shared = EligibleCorpus((record("a", "s"), record("b", "s")), 1, 1, True, None)
    assert len(graph_hits(shared, ["s"])) == 2  # every readable record of a source


# --- the false-association definition ---------------------------------------------------------


def test_false_association_sources_are_decoys_for_m3_and_the_twin_chain_for_m5():
    m3 = first("M3")
    assert false_association_sources(m3) == frozenset(m3.graph.decoy_sources)
    assert len(m3.graph.decoy_sources) >= 12
    m5 = first("M5")
    twins = false_association_sources(m5)
    chain = {s for slot in m5.case.gold.slots for s in slot}
    assert len(twins) == 2 and twins.isdisjoint(chain)  # the two distractor links, none gold
    assert twins <= {s for _t, _h, _r, s in m5.graph.edges}
    for family in ("M1", "M2", "M4", "M6"):
        assert false_association_sources(first(family)) == frozenset()


# --- paired contrasts, variance and power (hand-computed) --------------------------------------


def observation(query, cluster, arm, topology, recall, *, family="M1", stratum="TEMPLATE"):
    return {
        "query_id": query,
        "cluster": cluster,
        "arm_id": arm,
        "topology": topology,
        "family": family,
        "stratum": stratum,
        "retrieval": {"complete_set": recall},
        "answer": {
            "full_answerable": True,
            "insufficient_for_full": False,
            "observed": True,
            "false_answer": False,
            "false_abstention": not recall,
        },
        "false_association": None,
    }


def paired_rows(values):
    """values: {cluster: [(g0, g3), ...]} one query per tuple, template stratum, family M1."""
    rows = []
    for cluster, pairs in values.items():
        for index, (zero, three) in enumerate(pairs):
            query = f"{cluster}-{index}"
            rows.append(observation(query, cluster, "G0", NO_TOPOLOGY, zero))
            rows.append(observation(query, cluster, "G3", TEXT, three))
    return rows


def test_a_contrast_is_the_equal_cluster_mean_difference_with_its_cluster_sd():
    # Cluster a: (0,1),(0,1) -> +1; cluster b: (1,1) -> 0; cluster c: (0,0),(1,0) -> -0.5.
    rows = paired_rows(
        {
            "a": [(False, True), (False, True)],
            "b": [(True, True)],
            "c": [(False, False), (True, False)],
            "d": [(False, False)],
            "e": [(True, True)],
        }
    )
    result = contrast(rows, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY))
    means = [1.0, 0.0, -0.5, 0.0, 0.0]  # per-cluster mean differences
    assert result["pairs"] == 7 and result["clusters"] == 5
    assert result["difference"] == pytest.approx(statistics.mean(means))  # 0.1, not 3/7
    spread = result["cluster_spread"]
    assert spread["sd"] == pytest.approx(statistics.stdev(means))
    assert spread["clusters"] == 5 and spread["nonzero_clusters"] == 2
    assert spread["sd_upper_95"] >= spread["sd"] * 0.5
    low, high = result["confidence_interval"]
    assert low <= result["difference"] <= high
    # An unobserved right side pairs with nothing: the query leaves the denominator visibly.
    fewer = [r for r in rows if r["query_id"] != "a-0" or r["arm_id"] == "G0"]
    assert contrast(fewer, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY))["pairs"] == 6
    # Another family or stratum is outside this contrast's declared scope.
    other = contrast(rows, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY), families=("M5",))
    assert other["pairs"] == 0 and other["state"] == "NO_APPLICABLE_PAIRS"
    none = contrast(rows, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY), strata={"NOISY_V1:en"})
    assert none["pairs"] == 0


def test_a_contrast_selects_by_arm_and_topology_and_by_the_endpoints_own_denominator():
    rows = paired_rows({c: [(False, True)] for c in "abcde"})
    # Another topology's G3 rows and a query outside the supported denominator must not enter.
    for r in list(rows):
        if r["arm_id"] == "G3":
            rows.append(
                {**r, "topology": "TEMPLATE_READBACK", "retrieval": {"complete_set": False}}
            )
    rows.append(
        {
            **observation("z-0", "z", "G0", NO_TOPOLOGY, False),
            "answer": {**observation("z-0", "z", "G0", NO_TOPOLOGY, False)["answer"],
                       "full_answerable": False, "insufficient_for_full": True},
        }
    )  # fmt: skip
    rows.append({**rows[-1], "arm_id": "G3", "topology": TEXT})
    result = contrast(rows, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY))
    assert result["pairs"] == 5 and result["difference"] == 1.0  # text rows only, supported only
    harm = contrast(rows, "false_answer", ("G3", TEXT), ("G0", NO_TOPOLOGY))
    assert harm["pairs"] == 1  # the insufficient query is this endpoint's only denominator


def test_an_unobserved_answer_counts_as_a_false_abstention_not_a_silent_drop():
    rows = paired_rows({c: [(True, True)] for c in "abcde"})
    for r in rows:
        if r["arm_id"] == "G3" and r["cluster"] == "a":
            r["answer"] = {**r["answer"], "observed": False, "false_abstention": None}
    result = contrast(rows, "false_abstention", ("G3", TEXT), ("G0", NO_TOPOLOGY))
    assert result["pairs"] == 5 and result["difference"] == pytest.approx(1 / 5)  # cluster a: +1


def test_a_perfect_graph_and_an_identical_graph_are_the_two_controls_of_the_estimator():
    same = paired_rows({c: [(False, False), (True, True)] for c in "abcde"})
    flat = contrast(same, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY))
    assert flat["difference"] == 0.0 and flat["cluster_spread"]["sd"] == 0.0
    assert flat["power"]["observed"]["clusters_needed"]["0.05"] == 0  # no variance, no cost
    gain = paired_rows({c: [(False, True)] for c in "abcde"})
    top = contrast(gain, "slot_recall", ("G3", TEXT), ("G0", NO_TOPOLOGY))
    assert top["difference"] == 1.0 and top["confidence_interval"] == [1.0, 1.0]


def test_cluster_sd_matches_the_hand_value_and_names_what_it_cannot_estimate():
    spread = cluster_sd({"a": [1.0, 1.0], "b": [0.0], "c": [0.0]})
    assert spread["sd"] == pytest.approx(math.sqrt(1 / 3))  # means 1, 0, 0
    assert spread["mean"] == pytest.approx(1 / 3) and spread["nonzero_clusters"] == 1
    assert spread["sd_upper_95"] >= 0.0
    assert cluster_sd({"a": [1.0]}) == {"clusters": 1, "sd": None, "sd_upper_95": None}
    assert cluster_sd({}) == {"clusters": 0, "sd": None, "sd_upper_95": None}


def test_power_arithmetic_matches_the_normal_approximation_by_hand():
    z = statistics.NormalDist()
    total = z.inv_cdf(0.975) + z.inv_cdf(0.80)
    assert (ALPHA, POWER) == (0.05, 0.80) and total == pytest.approx(2.8016, abs=1e-4)
    assert required_clusters(0.25, 0.05) == math.ceil((total * 5) ** 2) == 197
    assert required_clusters(0.25, 0.10) == 50 and required_clusters(0.0, 0.05) == 0
    assert minimum_detectable(0.25, 200) == pytest.approx(total * 0.25 / math.sqrt(200))
    assert minimum_detectable(0.25, 40) == pytest.approx(0.1107, abs=1e-4)
    table = power_table(0.2, 0.3)
    assert set(table) == {"observed", "upper_95", "assumed_0.15", "assumed_0.25", "assumed_0.35"}
    assert table["upper_95"]["clusters_needed"]["0.1"] == required_clusters(0.3, 0.1)
    assert set(table["observed"]["minimum_detectable"]) == {"pilot", "tune", "evaluation"}
    assert "observed" not in power_table(None, None)  # nothing observed: only the assumed rows
    for bad in ((-1, 0.1), (0.2, 0.0)):
        with pytest.raises(NornError, match="INVALID_POWER_INPUT"):
            required_clusters(*bad)


def test_wilson_interval_matches_known_values_and_the_edges():
    low, high = wilson(0, 80)
    z2 = statistics.NormalDist().inv_cdf(0.975) ** 2
    assert low == 0.0 and high == pytest.approx(z2 / (80 + z2))  # zero successes: z^2/(n+z^2)
    assert high == pytest.approx(0.0458, abs=1e-4)  # the T20 floor, 0/80
    low, high = wilson(5, 10)
    assert (low, high) == (pytest.approx(0.2366, abs=1e-4), pytest.approx(0.7634, abs=1e-4))
    assert wilson(10, 10)[1] == 1.0 and wilson(0, 0) is None
    with pytest.raises(NornError, match="INVALID_PROPORTION"):
        wilson(3, 2)


# --- refusals and the pilot-only boundary ------------------------------------------------------


def test_the_wall_cap_stops_a_run_visibly(tmp_path):
    started = time.perf_counter_ns()
    graph_pilot._cap(started, 3600.0, tmp_path / "ok", 0, 10)
    assert not (tmp_path / "ok" / "aborted.json").exists()
    with pytest.raises(NornError, match="WALL_CAP_EXCEEDED"):
        graph_pilot._cap(started - 10_000_000_000, 1.0, tmp_path / "late", 3, 10)
    aborted = json.loads((tmp_path / "late" / "aborted.json").read_text())
    assert aborted["queries_done"] == 3 and aborted["planned"] == 10


def test_a_run_refuses_a_missing_enablement_cap_and_existing_directory(tmp_path):
    base = dict(
        source_run=tmp_path,
        source_attestation=tmp_path / "a.json",
        seed=47,
        model_root=tmp_path,
        enable_models=True,
        wall_cap_seconds=60.0,
        cap_basis="test",
    )
    with pytest.raises(NornError, match="BASELINE_ENABLEMENT_REQUIRED"):
        run_graph_pilot(tmp_path / "a", **{**base, "enable_models": False})
    with pytest.raises(NornError, match="WALL_CAP_REQUIRED"):
        run_graph_pilot(tmp_path / "b", **{**base, "cap_basis": ""})
    existing = tmp_path / "c"
    existing.mkdir()
    with pytest.raises(NornError, match="RUN_DIRECTORY_EXISTS"):
        run_graph_pilot(existing, **base)


def test_only_the_attested_t20_pilot_run_is_accepted_as_the_control_source(tmp_path):
    from benchmark.runs.multihop_run import STRATA

    good = {
        "run_kind": "MULTIHOP_CONVENTIONAL_DEVELOPMENT",
        "partition_role": "pilot",
        "config": {"strata": list(STRATA), "limit_per_family": None},
        "code_digest": "c",
        "seed": 47,
    }
    completion = {"manifest_digest": "m", "ledger_digest": "l", "final_chain_digest": "f"}
    (tmp_path / "completion.json").write_text(json.dumps(completion))

    def facts(manifest):
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        return source_run_facts(tmp_path)

    assert facts(good)["seed"] == 47  # positive control: the matching run is accepted
    for change in (
        {"run_kind": "CONVENTIONAL_RETRIEVAL_DEVELOPMENT"},  # a public-v1 run
        {"partition_role": "tune"},
        {"config": {"strata": ["TEMPLATE"], "limit_per_family": None}},
        {"config": {"strata": list(STRATA), "limit_per_family": 1}},
    ):
        with pytest.raises(NornError, match="SOURCE_RUN_NOT_THE_T20_PILOT"):
            facts({**good, **change})


def test_the_preregistered_section_is_hashed_alone_and_changes_are_visible(tmp_path):
    doc = tmp_path / "proposal.md"
    lines = [
        "# T", "", "## 1. Intro", "text", "", "## 2. Preregistered analysis (x)", "rule a",
        "rule b", "", "## 3. Results", "r",
    ]  # fmt: skip

    def write(replace=None, new=None):
        doc.write_text(
            chr(10).join(new if x == replace else x for x in lines) + chr(10), encoding="utf-8"
        )

    write()
    base = preregistration_digest(doc)
    write("r", "other results")
    assert preregistration_digest(doc) == base  # later sections may grow
    write("text", "intro changed")
    assert preregistration_digest(doc) == base  # earlier sections are outside it too
    write("rule b", "rule c")
    assert preregistration_digest(doc) != base  # a changed rule is a changed digest
    doc.write_text("# T" + chr(10) + chr(10) + "## 3. Results" + chr(10), encoding="utf-8")
    with pytest.raises(NornError, match="PREREGISTRATION_SECTION_MISSING"):
        preregistration_digest(doc)
    committed = graph_pilot.REPO / graph_pilot.PREREGISTRATION
    assert preregistration_digest(committed) == preregistration_digest(committed)  # parses


def test_the_module_reads_the_pilot_role_only_and_no_network_or_provider_code():
    source = Path(graph_pilot.__file__).read_text(encoding="utf-8")
    assert 'authorize_partition("pilot", "pilot")' in source
    assert 'cases_for(seed, "pilot"' in source and "multihop_cases(" not in source
    for forbidden in ("socket", "urllib", "requests", "groq", "GROQ", ".env", "getenv"):
        assert forbidden not in source
    assert ARMS == ("G0", "G1", "G2", "G3", "G4")  # G5, G6, G7 belong to M2
    assert walk_config()["G3"]["algorithm"] == "ppr" and walk_config()["G4"]["algorithm"] == "heat"


def test_an_unattested_run_is_not_citable_and_a_missing_one_is_refused(tmp_path):
    with pytest.raises(NornError, match="ATTESTATION_REQUIRED"):
        validate_graph_pilot(tmp_path, model_root=tmp_path)
    with pytest.raises(NornError, match="ATTESTATION_OR_DEVELOPMENT_ONLY"):
        validate_graph_pilot(
            tmp_path, model_root=tmp_path, attestation=tmp_path / "a", development_only=True
        )


# --- a small real run over the attested T20 stores (skipped when they are not on this machine) -


def available() -> bool:
    return SOURCE_RUN.is_dir() and MODELS.is_dir() and ATTESTATION.is_file()


@pytest.mark.skipif(not available(), reason="T20 pilot stores or pinned local models absent")
def test_a_real_template_run_reloads_scores_and_detects_tampering(tmp_path):
    destination = tmp_path / "run"
    completion = run_graph_pilot(
        destination,
        source_run=SOURCE_RUN,
        source_attestation=ATTESTATION,
        seed=47,
        model_root=MODELS,
        enable_models=True,
        wall_cap_seconds=3600.0,
        cap_basis="unit test, six template queries",
        limit_per_family=1,
        strata=("TEMPLATE",),
    )
    per_query = 1 + len(TOPOLOGIES) * 4
    assert completion["observations"] == 6 * per_query
    assert completion["g0_control_mismatches"] == 0  # G0 is the attested R2, byte for byte
    assert not (destination / "work").exists()  # throw-away stores are removed
    report = graph_pilot.report_graph_pilot(destination, MODELS, development_only=True)
    assert report["evidence_status"] == "DEVELOPMENT_ONLY_NOT_CITABLE"
    assert report["g0_control"] == {"rows": 6, "matches_attested_r2": 6}
    assert report["privacy"]["incidents"] == 0
    assert report["label"].endswith("NOT_A_BENEFIT_CLAIM")
    assert any("|G3" in key for key in report["costs"])
    rows = [json.loads(x) for x in (destination / "ledger.jsonl").read_text().splitlines()]
    for r in rows:
        assert len(r["result"]["candidates"]) <= 10 and r["provider_calls"] == 0
        if r["graph"]:
            assert r["graph"]["mapped"] <= r["graph"]["proposed"]
            assert r["graph"]["nodes"] > 0 and r["graph"]["counters"]
    # The preregistered section is re-hashed on reload: an unchanged copy passes, an edited one
    # is refused (the repository root is a parameter so the committed proposal is never touched).
    copy = tmp_path / "repo"
    (copy / Path(graph_pilot.PREREGISTRATION).parent).mkdir(parents=True)
    proposal = copy / graph_pilot.PREREGISTRATION
    shutil.copy(graph_pilot.REPO / graph_pilot.PREREGISTRATION, proposal)
    kept = validate_graph_pilot(destination, model_root=MODELS, development_only=True, repo=copy)
    assert kept["observations"]
    proposal.write_text(
        proposal.read_text(encoding="utf-8").replace(
            "G3 minus G0 (primary)", "G3 minus G1 (primary)"
        ),
        encoding="utf-8",
    )
    with pytest.raises(NornError, match="PREREGISTRATION_CHANGED"):
        validate_graph_pilot(destination, model_root=MODELS, development_only=True, repo=copy)
    # Tampering with one scored byte of the ledger is caught by the chain.
    ledger = destination / "ledger.jsonl"
    original = ledger.read_bytes()
    ledger.write_bytes(original.replace(b'"evidence_tokens":', b'"evidence_tokens":1', 1))
    with pytest.raises(NornError, match="LEDGER_CHANGED"):
        validate_graph_pilot(destination, model_root=MODELS, development_only=True)
    ledger.write_bytes(original)
    shutil.rmtree(destination)
    assert MultiHopCase is not None


# --- the frozen margins ------------------------------------------------------------------------


def contrast_stub(difference, low, high, *, sd=0.1, pairs=10):
    return {
        "difference": difference,
        "confidence_interval": None if low is None else [low, high],
        "cluster_spread": {"sd": sd},
        "pairs": pairs,
    }


def harms(**changes):
    base = {name: contrast_stub(0.0, 0.0, 0.0, sd=0.0) for name in graph_pilot.HARM_CONTRASTS}
    return base | changes


def test_the_frozen_margins_are_the_owner_approved_values():
    assert MARGINS == {"benefit": 0.10, "regression": 0.02, "privacy_incidents": 0}
    assert CLUSTERS == {"tune": 40, "evaluation": 200}


def test_the_verdict_applies_the_frozen_margins_with_positive_and_negative_controls():
    win = contrast_stub(0.113, 0.037, 0.212)
    quiet = harms()
    assert verdict(win, quiet, 0)["label"] == "MARGINS_MET"  # positive control
    assert set(verdict(win, quiet, 0)["harm"].values()) == {"NON_DISCRIMINATING"}
    bounded = harms(G3_minus_G0_false_association=contrast_stub(0.0, -0.01, 0.015, sd=0.05))
    assert verdict(win, bounded, 0)["harm"]["G3_minus_G0_false_association"] == "EXCLUDED"
    assert verdict(win, bounded, 0)["label"] == "MARGINS_MET"
    # Benefit below the margin, or an interval touching zero, retains the simpler arm.
    assert verdict(contrast_stub(0.09, 0.02, 0.2), quiet, 0)["label"] == "G0_RETAINED_NO_BENEFIT"
    assert verdict(contrast_stub(0.2, 0.0, 0.4), quiet, 0)["label"] == "G0_RETAINED_NO_BENEFIT"
    assert verdict(contrast_stub(0.2, None, None), quiet, 0)["label"] == "G0_RETAINED_NO_BENEFIT"
    # A harm whose upper bound exceeds +0.02, or has no interval, is not excluded.
    worse = harms(G3_minus_G0_false_association=contrast_stub(0.107, 0.018, 0.214, sd=0.15))
    assert verdict(win, worse, 0)["label"] == "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED"
    unknown = harms(G3_minus_G0_false_answer=contrast_stub(0.0, None, None, sd=0.1))
    assert verdict(win, unknown, 0)["label"] == "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED"
    # One privacy incident fails everything, whatever the benefit.
    assert verdict(win, quiet, 1)["label"] == "PRIVACY_INCIDENT_FAILS"
    assert verdict(win, quiet, 0)["scope"] == "DEVELOPMENT_EXPLORATORY_P06_M1"


def test_the_saved_pilot_report_reproduces_its_label_under_the_frozen_margins():
    path = graph_pilot.REPO / "docs/development/evidence/p06_graph_pilot_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    result = verdict(
        report["contrasts"]["G3_minus_G0"], report["harm"], report["privacy"]["incidents"]
    )
    assert result["label"] == "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED"
    assert result["harm"] == {
        "G3_minus_G0_false_answer": "NON_DISCRIMINATING",
        "G3_minus_G0_false_abstention": "NON_DISCRIMINATING",
        "G3_minus_G0_false_association": "NOT_EXCLUDED",
    }
    assert report["evidence_status"] == "ATTESTED" and report["g0_control"]["rows"] == 192
