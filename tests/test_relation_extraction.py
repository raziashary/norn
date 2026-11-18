"""P06-T02: derived graph tracks, relation quality against the hidden gold, and speculation guards.

The full pilot measurement is ``norn-benchmark graph-extraction-report`` (EVIDENCE_LOG E-P06-009);
these tests prove the reader's grammar and limits, the guards, the scorer and the isolation of the
oracle diagnostic from the derived tracks, on a handful of real and constructed cases.
"""

import ast
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_multihop_fixtures import first

from benchmark.fixtures.noisy_render import CLAUSES, noisy_case
from benchmark.metrics.graph_quality import (
    ORACLE_REVISION,
    EdgeObs,
    pool,
    score_edges,
    shuffled_gold,
)
from benchmark.runs.graph_extraction import (
    PLAN,
    TRACK_GOLD,
    gold_edges,
    measure_case,
    selected_cases,
)
from norn.canonical.identity import register_entity
from norn.canonical.registry import WriteRequest
from norn.contracts.errors import NornError
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
from norn.contracts.identity import canonical
from norn.contracts.time import TimeKind, TimeValue
from norn.extraction import relations
from norn.extraction.atoms import FixtureAtom
from norn.extraction.relations import (
    REVISIONS,
    TRACK_READBACK,
    TRACK_TEXT,
    extract_relations,
    read_message,
)
from norn.governance.access import HostIdentity
from norn.graph.adjacency import build_graph
from norn.integration.engine import Engine

SEED = 47
WHEN = datetime(2026, 10, 20, 9, tzinfo=UTC)


def clause(message: str):
    return read_message(message)


# --- the text reader: grammar, tolerated noise and documented limits ---------------------------


def test_every_requires_phrasing_of_both_languages_reads_with_the_right_direction():
    actor, value = "Bg-0123456789", "svc.0123456789abcd"
    for options in CLAUSES["requires"].values():
        for template in options:
            text = template.replace("{a}", actor).replace("{v}", value)
            found = clause(text)
            assert [(c.kind, c.subject, c.object, c.hedged) for c in found] == [
                ("REQUIRES", actor, value, False)
            ], text


def test_one_adjacent_swap_in_a_filler_word_and_listed_abbreviations_are_tolerated():
    actor, value = "Bg-0123456789", "svc.0123456789abcd"
    for text in (
        f"{actor} deepnds on {value}.",  # swap
        f"{actor} mebmutuhkan {value}.",  # swap
        f"{value} is reqd by {actor}.",  # abbreviation, passive
        f"{actor} dep. on {value}.",  # abbreviation
        f"{actor} cnanot run wihtout {value}.",  # two swapped words in one phrase
        f"btw, {actor} needs {value} in place.",
    ):
        found = clause(text)
        assert [(c.subject, c.object) for c in found] == [(actor, value)], text


def test_unsupported_phrasing_is_missed_not_guessed():
    """Known limits, stated as tests: out-of-grammar wording yields no clause (a visible miss)."""
    actor, value = "Bg-0123456789", "svc.0123456789abcd"
    assert clause(f"{actor} depends on {value}.")  # positive control: the grammar works
    for text in (
        f"{actor} relies on {value}.",  # synonym outside the vocabulary
        f"{actor} depnds on {value}.",  # a deleted letter is not an adjacent swap
        f"{actor} dpeneds on {value}.",  # two separate edits
        f"{actor} deens {value}.",  # the right letters swapped, but not adjacent
        f"{value} is a prerequisite of {actor}.",
        f"{actor} one two three four five six seven eight depends on {value}.",  # gap too long
    ):
        assert clause(text) == [], text


def test_other_predicates_identity_markers_and_distractors_never_read_as_requirements():
    actor, value = "Bg-0123456789", "svc.0123456789abcd"
    for text in (
        f"{actor} is registered and active. [key:{value}]",
        f"{actor} mentioned {value}.",
        f"Note from {actor}: see {value}.",
        f"{actor} parked in {value}.",
        f"{actor} was observed {value}.",
        f"{actor} depends on nothing here. [alias:{value}] [key:{value}]",
        "Reminder: the maintenance window moved to Friday. The desk closed an unrelated ticket.",
    ):
        assert [c for c in clause(text) if c.kind == "REQUIRES"] == [], text


def test_hedges_and_causes_are_flagged_and_the_causal_direction_follows_the_voice():
    a, k = "Bg-0123456789", "svc.0123456789abcd"
    hedged = clause(f"{a} might depend on {k}.")
    assert [(c.kind, c.hedged) for c in hedged] == [("REQUIRES", True)]
    assert clause(f"mungkin {a} bergantung pada {k}.")[0].hedged
    may = clause(f"{k} may have caused {a}.")
    assert [(c.kind, c.subject, c.object, c.hedged) for c in may] == [("CAUSE", k, a, True)]
    passive = clause(f"{a} was possibly caused by {k}.")
    assert [(c.kind, c.subject, c.object) for c in passive] == [("CAUSE", k, a)]
    plain = clause(f"{k} caused {a}.")
    assert [(c.kind, c.subject, c.object, c.hedged) for c in plain] == [("CAUSE", k, a, False)]


# --- the quality metric: hand-computed, perfect, empty and shuffled controls -------------------


def e(tail, head, source="s", revision="") -> EdgeObs:
    return EdgeObs(tail, head, "REQUIRES", source, revision)


def test_precision_recall_and_citation_agreement_match_hand_computed_values():
    gold = [e("a", "b", "s1"), e("b", "c", "s2"), e("c", "d", "s3"), e("d", "e", "s4")]
    derived = [e("a", "b", "s1"), e("b", "c", "sX"), e("x", "y", "s9")]
    score = score_edges(derived, gold)
    assert (score["true_positive"], score["false_positive"], score["false_negative"]) == (2, 1, 2)
    assert score["precision"] == pytest.approx(2 / 3) and score["recall"] == 0.5
    assert score["f1"] == pytest.approx(2 * (2 / 3) * 0.5 / (2 / 3 + 0.5))
    assert (score["citation_agreement"], score["citation_denominator"]) == (0.5, 2)
    assert "('x', 'y', 'REQUIRES')" in score["spurious"][0]
    assert len(score["missed"]) == 2


def test_perfect_empty_shuffled_and_unkeyed_controls():
    gold = [e(f"n{i}", f"n{i + 1}", f"s{i}") for i in range(8)]
    perfect = score_edges(gold, gold)
    assert (perfect["precision"], perfect["recall"], perfect["f1"]) == (1.0, 1.0, 1.0)
    empty = score_edges([], gold)
    assert (empty["precision"], empty["recall"], empty["f1"]) == (None, 0.0, None)
    assert score_edges(gold, [])["recall"] is None  # no gold edge: no recall to report
    shuffled = score_edges(gold, shuffled_gold(gold, 1))
    assert shuffled["recall"] < 0.5  # a scrambled truth is not matched
    unkeyed = score_edges([e(None, "n1", "s0")], gold)
    assert (unkeyed["true_positive"], unkeyed["unkeyed"], unkeyed["precision"]) == (0, 1, 0.0)
    both_unkeyed = score_edges([e(None, None, "s0")], [e(None, None, "s0")])
    assert (both_unkeyed["true_positive"], both_unkeyed["unkeyed"]) == (0, 1)
    both_wrong = score_edges([e("p", "q")], [e("r", "s")])
    assert both_wrong["f1"] == 0.0
    pooled = pool([perfect, empty])
    assert (pooled["derived"], pooled["gold"], pooled["true_positive"]) == (8, 16, 8)
    assert pooled["precision"] == 1.0 and pooled["recall"] == 0.5


def test_an_oracle_edge_cannot_be_scored_as_derived_and_the_diagnostic_must_be_labelled():
    gold = [e("a", "b", "s1")]
    with pytest.raises(NornError, match="ORACLE_EDGES_IN_DERIVED_TRACK"):
        score_edges([e("a", "b", "s1", ORACLE_REVISION)], gold)
    with pytest.raises(NornError, match="DIAGNOSTIC_TRACK_MISLABELLED"):
        score_edges([e("a", "b", "s1", "relations-text-v1")], gold, oracle_track=True)
    assert score_edges([e("a", "b", "s1", ORACLE_REVISION)], gold, oracle_track=True)["recall"] == 1


# --- real cases through every track ------------------------------------------------------------


def test_all_tracks_score_the_template_and_noisy_pilot_cases_and_the_controls_are_perfect(tmp_path):
    scored = {}
    for family in ("M1", "M2", "M3", "M5"):
        template = first(family)
        for track, stratum in PLAN:
            case = template
            if stratum != "TEMPLATE":
                case = noisy_case(template, SEED, stratum.split(":")[1])
            row = measure_case(track, stratum, case, tmp_path)
            scored[(family, track, stratum)] = row["score"]
            assert row["score"]["gold"] > 10 and row["score"]["derived"] > 10
    for key, score in scored.items():
        assert (score["precision"], score["recall"]) == (1.0, 1.0), key
        assert score["citation_agreement"] == 1.0, key
    assert len(scored) == 4 * len(PLAN)
    assert TRACK_GOLD in {t for _f, t, _s in scored}


def test_the_alias_bridge_resolves_only_through_the_reviewed_identity_link(tmp_path):
    row = measure_case(TRACK_TEXT, "TEMPLATE", first("M2"), tmp_path)
    assert row["identity"]["alias_links"] == row["identity"]["gold_alias_links"] == 1
    assert row["identity"]["unresolved_aliases"] == 0
    assert row["score"]["recall"] == 1.0
    assert row["score"]["unkeyed"] == 0  # the keyless stating entity was keyed through SAME_AS


def test_gold_edges_stated_only_by_unpublished_sources_are_reported_apart(tmp_path):
    case = first("M4")
    published = {s.source_id for s in case.case.sources}
    gold, unpublished = gold_edges(case, published)
    assert unpublished == 2 and len(gold) == len(case.graph.edges) - 2
    row = measure_case(TRACK_TEXT, "TEMPLATE", case, tmp_path)
    assert row["unpublished_gold_edges"] == 2 and row["score"]["recall"] == 1.0
    # Control: counting them in the denominator is exactly what would make recall look worse.
    everything = [e(h, t, s) for h, t, _r, s in case.graph.edges]
    assert len(everything) == len(gold) + 2
    private_key = case.graph.private_sources[0].observation.value
    assert private_key  # the private shortcut exists in the hidden graph only
    assert all(private_key not in str(x) for x in row["score"]["spurious"])


def test_the_same_published_sources_reproduce_the_same_graph_bytes(tmp_path):
    digests = []
    for index in range(2):
        built = tmp_path / f"run{index}"
        built.mkdir()
        digests.append(_graph_digest(built, noisy_case(first("M3"), SEED, "mixed"), TRACK_TEXT))
    assert digests[0] == digests[1]
    other = _graph_digest(
        tmp_path / "other", noisy_case(first("M3"), SEED, "mixed"), TRACK_READBACK
    )
    assert other != digests[0]  # the revision of the producer is part of the edge identity


def _graph_digest(root: Path, case, track: str) -> str:
    from benchmark.adapters.baseline import host, load_sources
    from benchmark.adapters.common import replay_clock
    from benchmark.fixtures.publication import publish

    published = publish(case.case, ("__GOLD_CANARY__",))
    clock = replay_clock(published)
    with Engine(root / "store", host(published), create=True, clock=clock) as engine:
        engine.access.bootstrap()
        load_sources(engine, published, clock)
        extract_relations(engine.registry, track)
        return build_graph(engine.registry).digest()


# --- isolation of the oracle diagnostic --------------------------------------------------------


def test_the_derived_reader_cannot_see_gold_or_the_benchmark():
    tree = ast.parse(Path(relations.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not [m for m in imported if m.startswith(("benchmark", "norn.embedding", "random"))]
    assert not [m for m in imported if "socket" in m or "urllib" in m or "http" in m]
    assert {"norn.graph.adjacency", "norn.canonical.registry"} <= imported  # control: parsed
    assert list(inspect.signature(extract_relations).parameters) == ["registry", "track"]
    assert ORACLE_REVISION not in REVISIONS.values()
    assert "gold-diagnostic" not in Path(relations.__file__).read_text(encoding="utf-8")


def test_the_oracle_track_writes_only_the_oracle_revision_and_derived_stores_hold_none(tmp_path):
    case = first("M1")
    cases = selected_cases(SEED, 1)
    assert len(cases["TEMPLATE"]) == 6 and len(cases["NOISY_V1:id"]) == 6
    for track in (TRACK_TEXT, TRACK_READBACK):
        row = measure_case(track, "TEMPLATE", case, tmp_path)
        assert row["extra"]["requires"] == row["score"]["derived"]  # nothing else was written
    oracle = measure_case(TRACK_GOLD, "TEMPLATE", case, tmp_path)
    assert oracle["extra"] == {"written": oracle["score"]["derived"], "unmapped": 0}
    assert not list(tmp_path.iterdir())  # throw-away stores are removed after each case


# --- speculation and unresolved endpoints (constructed sources) --------------------------------


def put(engine, occurrence: str, actor: str, message: str, value: str = "x"):
    """Ingest one constructed source whose only relation text is ``message``."""
    content = canonical({"message": message}).encode()
    fixture = FixtureAtom(
        actor,
        "registered",
        TaggedValue("TEXT", actor),
        0,
        len(content),
        EpistemicState(Epistemic.DOCUMENT_ASSERTION),
    )
    receipt = engine.write(
        WriteRequest(
            "operator",
            occurrence,
            occurrence,
            content,
            TimeValue(TimeKind.EXACT, WHEN),
            WHEN,
            (fixture,),
        )
    )
    return receipt


def built(engine, specs: list[tuple[str, str, str, str | None]]):
    """(occurrence, actor, message, key) per source; keys are registered as ADMIN."""
    receipts = {}
    for occurrence, actor, message, key in specs:
        receipts[occurrence] = put(engine, occurrence, actor, message)
        if key is not None:
            register_entity(engine.registry, receipts[occurrence]["atom_ids"][0], actor, key)
    return receipts


def relation_rows(engine):
    return engine.db.connection.execute(
        "SELECT relation_type,epistemic,from_kind,to_kind,producer_revision FROM graph_edges "
        "ORDER BY id"
    ).fetchall()


def test_speculation_never_becomes_a_requirement_or_a_verified_cause(engine):
    receipts = built(
        engine,
        [
            (
                "define",
                "Svc-cause",
                "Svc-cause is registered and active. [key:svc.cause01]",
                "svc.cause01",
            ),
            (
                "effect",
                "Svc-effect",
                "svc.cause01 may have caused Svc-effect. [key:svc.effect01]",
                "svc.effect01",
            ),
            (
                "plain",
                "Svc-plain",
                "svc.cause01 caused Svc-plain. [key:svc.plain001]",
                "svc.plain001",
            ),
            (
                "hedge",
                "Svc-hedge",
                "Svc-hedge might depend on svc.cause01. [key:svc.hedge001]",
                "svc.hedge001",
            ),
            (
                "real",
                "Svc-real",
                "Svc-real depends on svc.cause01. [key:svc.real0001]",
                "svc.real0001",
            ),
        ],
    )
    report = extract_relations(engine.registry, TRACK_TEXT)
    rows = relation_rows(engine)
    kinds = sorted((r["relation_type"], r["epistemic"], r["from_kind"]) for r in rows)
    assert kinds == [
        ("HYPOTHESIZES_CAUSE", "HYPOTHESIS", "event"),
        ("HYPOTHESIZES_CAUSE", "HYPOTHESIS", "event"),
        ("REQUIRES", "DOCUMENT_ASSERTION", "entity"),
    ]  # the hedged requirement wrote nothing; the unhedged causal clause is still a hypothesis
    assert (report.requires, report.hypotheses, report.skipped) == (
        1,
        2,
        {"HEDGED_REQUIREMENT": 1},
    )
    assert "VERIFIED_CAUSE" not in {r["relation_type"] for r in rows}
    graph = build_graph(engine.registry)
    cause_event = receipts["define"]["event_id"]
    effects = {e.target.id for e in graph.edges if e.relation == "HYPOTHESIZES_CAUSE"}
    assert effects == {receipts["effect"]["event_id"], receipts["plain"]["event_id"]}
    assert {e.source.id for e in graph.edges if e.relation == "HYPOTHESIZES_CAUSE"} == {cause_event}
    # Positive control: the one unhedged dependency is a real REQUIRES edge to the keyed entity.
    requires = [e for e in graph.edges if e.relation == "REQUIRES"]
    assert len(requires) == 1 and requires[0].epistemic == "DOCUMENT_ASSERTION"


def test_unknown_keys_and_bare_names_stay_unresolved_and_equal_names_never_merge(engine):
    built(
        engine,
        [
            (
                "one",
                "Svc-dup",
                "Svc-dup is registered and active. [key:svc.dupkey01]",
                "svc.dupkey01",
            ),
            (
                "two",
                "Svc-dup",
                "Svc-dup is registered and active. [key:svc.dupkey02]",
                "svc.dupkey02",
            ),
            (
                "tail",
                "Svc-tail",
                "Svc-tail depends on svc.unknown99. [key:svc.tailkey1]",
                "svc.tailkey1",
            ),
            ("name", "Svc-name", "Svc-name depends on Svc-dup. [key:svc.namekey1]", "svc.namekey1"),
            ("bare", "Svc-bare", "Svc-bare depends on svc.dupkey02.", None),
        ],
    )
    report = extract_relations(engine.registry, TRACK_TEXT)
    graph = build_graph(engine.registry)
    requires = [e for e in graph.edges if e.relation == "REQUIRES"]
    assert len(requires) == 1  # only the keyless source citing a registered key resolves
    keys = {
        r[0]: r[1] for r in engine.db.connection.execute("SELECT id,external_key FROM entities")
    }
    assert keys[requires[0].target.id] == "svc.dupkey02"
    assert report.skipped == {"UNRESOLVED_ENDPOINT": 2}  # the unknown key and the bare name
    assert not [e for e in graph.edges if e.relation == "IDENTITY_LINK"]  # same name, no merge


def test_a_source_the_principal_cannot_read_yields_no_edge_and_leaks_no_key(engine):
    label = "secret"
    receipts = built(
        engine,
        [
            (
                "open",
                "Svc-open",
                "Svc-open is registered and active. [key:svc.openkey1]",
                "svc.openkey1",
            ),
            (
                "hide",
                "Svc-hide",
                "Svc-hide depends on svc.openkey1. [key:svc.hidekey1]",
                "svc.hidekey1",
            ),
            (
                "show",
                "Svc-show",
                "Svc-show depends on svc.openkey1. [key:svc.showkey1]",
                "svc.showkey1",
            ),
        ],
    )
    owner = engine.registry.source_for_atom(receipts["hide"]["atom_ids"][0])["source_id"]
    engine.access.set_scope(owner, label)
    engine.access.grant("operator", "READ", revoke=True, scope=label)
    report = extract_relations(engine.registry, TRACK_TEXT)
    assert report.atoms_read == 2 and report.requires == 1  # the hidden atom was never read
    hidden_atom = receipts["hide"]["atom_ids"][0]
    span = engine.db.connection.execute(
        "SELECT source_span_id FROM atoms WHERE id=?", (hidden_atom,)
    ).fetchone()[0]
    hidden_entity = engine.db.connection.execute(
        "SELECT id FROM entities WHERE external_key='svc.hidekey1'"
    ).fetchone()[0]
    touching = engine.db.connection.execute(
        "SELECT count(*) FROM graph_edges WHERE source_span_id=? OR from_id=? OR to_id=?",
        (span, hidden_entity, hidden_entity),
    ).fetchone()[0]
    assert touching == 0 and owner not in json.dumps([tuple(r) for r in relation_rows(engine)])


def test_readback_and_text_reader_agree_when_the_text_is_the_stored_fact(engine):
    built(
        engine,
        [("a", "Svc-aaa", "Svc-aaa is registered and active. [key:svc.aaaaaaaa]", "svc.aaaaaaaa")],
    )
    # A requires atom whose stored fact and message state the same dependency.
    content = canonical({"message": "Svc-bee depends on svc.aaaaaaaa. [key:svc.bbbbbbbb]"}).encode()
    fixture = FixtureAtom(
        "Svc-bee",
        "requires",
        TaggedValue("TEXT", "svc.aaaaaaaa"),
        0,
        len(content),
        EpistemicState(Epistemic.DOCUMENT_ASSERTION),
    )
    receipt = engine.write(
        WriteRequest(
            "operator", "b", "b", content, TimeValue(TimeKind.EXACT, WHEN), WHEN, (fixture,)
        )
    )
    register_entity(engine.registry, receipt["atom_ids"][0], "Svc-bee", "svc.bbbbbbbb")
    text = extract_relations(engine.registry, TRACK_TEXT)
    readback = extract_relations(engine.registry, TRACK_READBACK)
    assert (text.requires, readback.requires) == (1, 1)
    revisions = {r["producer_revision"] for r in relation_rows(engine)}
    assert revisions == {REVISIONS[TRACK_TEXT], REVISIONS[TRACK_READBACK]}
    with pytest.raises(NornError, match="UNSUPPORTED_TRACK"):
        extract_relations(engine.registry, "GOLD_DIAGNOSTIC")
    other = Engine(engine.root, HostIdentity(engine.access.host.namespace, "nobody"))
    with other, pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        extract_relations(other.registry, TRACK_TEXT)


def test_readback_reads_only_the_requires_predicate(engine):
    built(
        engine,
        [("a", "Svc-aaa", "Svc-aaa is registered and active. [key:svc.aaaaaaaa]", "svc.aaaaaaaa")],
    )
    content = canonical({"message": "Svc-bee owns svc.aaaaaaaa. [key:svc.bbbbbbbb]"}).encode()
    fixture = FixtureAtom(
        "Svc-bee",
        "owns",  # a TEXT value naming a registered key, but not a requirement
        TaggedValue("TEXT", "svc.aaaaaaaa"),
        0,
        len(content),
        EpistemicState(Epistemic.DOCUMENT_ASSERTION),
    )
    receipt = engine.write(
        WriteRequest(
            "operator", "b", "b", content, TimeValue(TimeKind.EXACT, WHEN), WHEN, (fixture,)
        )
    )
    register_entity(engine.registry, receipt["atom_ids"][0], "Svc-bee", "svc.bbbbbbbb")
    report = extract_relations(engine.registry, TRACK_READBACK)
    assert (report.requires, report.hypotheses, report.skipped) == (0, 0, {})
    assert relation_rows(engine) == []


def test_the_text_reader_never_reads_the_structured_capture():
    source = inspect.getsource(relations._Reader.message_of)
    assert '["message"]' in source and "capture" not in source
    message = "Bg-0123456789 needs svc.0123456789abcd."
    assert [(c.subject, c.object) for c in read_message(message)] == [
        ("Bg-0123456789", "svc.0123456789abcd")
    ]


def test_edges_to_a_key_no_published_source_defines_are_an_identity_limit_not_a_reading_error(
    tmp_path,
):
    row = measure_case(TRACK_TEXT, "TEMPLATE", first("M3", "missing"), tmp_path)
    assert (
        row["unrepresentable_gold_edges"] >= 30
    )  # the hub's key is defined only by a dropped source
    assert row["score"]["recall"] < 0.7  # judged against every published gold edge
    assert (
        row["score_representable"]["recall"] == 1.0
    )  # the relation reader lost nothing it could keep
    assert row["score_representable"]["precision"] == row["score"]["precision"] == 1.0
    assert row["extra"]["skipped"] == {"UNRESOLVED_ENDPOINT": row["unrepresentable_gold_edges"]}
    positive = measure_case(TRACK_TEXT, "TEMPLATE", first("M3"), tmp_path)
    assert positive["unrepresentable_gold_edges"] == 0 and positive["score"]["recall"] == 1.0
