"""Per-object ACL (ADR-0029 P06-Q7): labels on sources, deny overrides, fail-closed derivations."""

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from conftest import HOST, TUESDAY, clock, request

from norn.canonical.corrections import CorrectionRequest
from norn.contracts.errors import NornError
from norn.governance.access import DENIED, Access, HostIdentity
from norn.governance.eligibility import Eligibility
from norn.integration.engine import Engine
from norn.retrieval import exact
from norn.retrieval.contracts import Hit, RecallRequest
from norn.retrieval.resolve import resolve

READER = "reader"
LABEL = "secret"


def fixed_clock() -> datetime:
    return datetime(2026, 10, 20, 12, tzinfo=UTC)


def source_of(engine: Engine, event_id: str) -> str:
    return str(
        engine.db.connection.execute(
            "SELECT v.source_id FROM events e JOIN source_versions v ON e.ns=v.ns "
            "AND e.source_version=v.id WHERE e.id=?",
            (event_id,),
        ).fetchone()[0]
    )


def seen(view: dict) -> str:
    """The reader's bytes minus the two documented namespace-wide fields (see the limits)."""

    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k != "elapsed_ms"}  # wall time
        return [strip(v) for v in node] if isinstance(node, list) else node

    masked = strip(json.loads(json.dumps(view)))
    masked.pop("resource_observation", None)  # process memory, differs run to run
    masked.pop("projection_snapshot", None)  # digest of namespace-wide manifests (disclosed)
    return json.dumps(masked, sort_keys=True)


def with_tail(occurrence: str, tail: str, place: str = "ZoneA"):
    """A request whose atom span is fixed but whose source text carries a private tail."""
    base = request(occurrence, place=place)
    return replace(base, content=base.content + (" " + tail).encode())


def seen_equal(texts: list[str]) -> bool:
    return len(texts) == 2 and texts[0] == texts[1]


def reader_of(engine: Engine) -> Engine:
    return Engine(
        engine.root, HostIdentity(engine.access.host.namespace, READER), clock=fixed_clock
    )


def build(engine: Engine, private_place: str = "ZoneB", *, deny: bool = True):
    """One public and one private event; the reader holds a namespace READ grant."""
    public = engine.write(request("public", place="ZoneA"))
    private = engine.write(request("private", place=private_place))
    engine.access.grant(READER, "READ")
    engine.access.set_scope(source_of(engine, private["event_id"]), LABEL)
    if deny:
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
    engine.project()
    return public, private


def test_a_namespace_grant_does_not_open_a_denied_label_and_denied_equals_absent(engine):
    public, private = build(engine, deny=False)
    with reader_of(engine) as reader:
        # Positive control: before the label revocation the reader may read both.
        assert reader.access.eligible("READ", private["event_id"])
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
        assert reader.access.eligible("READ", public["event_id"])
        assert not reader.access.eligible("READ", private["event_id"])
        assert not reader.access.eligible("READ", private["atom_ids"][0])
        assert not reader.access.eligible("READ", source_of(engine, private["event_id"]))
        with pytest.raises(NornError) as denied:
            reader.access.check("READ", private["event_id"])
        with pytest.raises(NornError) as absent:
            reader.access.check("READ", "event_" + "0" * 64)
        assert (denied.value.code, str(denied.value)) == (absent.value.code, str(absent.value))
        assert denied.value.code == DENIED


def test_deny_overrides_a_namespace_grant_and_the_newest_epoch_wins_per_label(engine):
    _public, private = build(engine, deny=False)
    source = source_of(engine, private["event_id"])
    labels = Eligibility(engine.db.connection, engine.access.ns, READER)
    assert labels.source_readable("READ", source)  # '*' GRANT, label has no row yet
    engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
    assert not labels.source_readable("READ", source)  # REVOKE at the label beats '*' GRANT
    engine.access.grant(READER, "READ", scope=LABEL)
    assert labels.source_readable("READ", source)  # a newer GRANT at the label wins again
    engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
    engine.access.grant(READER, "READ", revoke=True)  # '*' revoked: no namespace grant at all
    assert not labels.source_readable("READ", source)
    with reader_of(engine) as reader, pytest.raises(NornError, match=DENIED):
        reader.access.check("READ")


def test_a_denied_source_cannot_change_what_the_reader_receives(tmp_path):
    answers = []
    for index, place in enumerate(("ZoneB", "ZoneC")):
        with Engine(tmp_path / f"world{index}", HOST, create=True, clock=fixed_clock) as engine:
            engine.access.bootstrap()
            build(engine, place)
            with reader_of(engine) as reader:
                query = RecallRequest("parking", clock(), subject="Alex")
                answers.append(reader.recall(query).serialize())
                events = reader.read(
                    engine.db.connection.execute(
                        "SELECT id FROM events WHERE occurrence='public'"
                    ).fetchone()[0],
                    clock(),
                ).serialize()
                answers.append(events)
    # The two worlds differ only in the private source's text, so every byte the reader sees
    # (status, evidence, counts, truncation flags, trace) must be identical, and no text leaks.
    assert seen(answers[0]) == seen(answers[2])
    assert seen(answers[1]) == seen(answers[3])
    text = json.dumps(answers)
    assert "ZoneB" not in text and "ZoneC" not in text and "ZoneA" in text


def test_the_operator_still_sees_the_private_source_so_the_control_can_fail(tmp_path):
    with Engine(tmp_path / "w", HOST, create=True) as engine:
        engine.access.bootstrap()
        build(engine, "ZoneB")
        result = json.dumps(
            engine.recall(RecallRequest("parking", clock(), subject="Alex")).serialize()
        )
        assert "ZoneB" in result and "ZoneA" in result


def test_a_denied_neighbour_is_absent_and_its_citation_is_dropped(tmp_path):
    texts = []
    for index, tail in enumerate(("TailBBB", "TailCCC")):
        with Engine(tmp_path / f"world{index}", HOST, create=True, clock=fixed_clock) as engine:
            engine.access.bootstrap()
            first = engine.write(request("first", place="ZoneA"))
            extra = engine.write(
                with_tail("extra", tail),
                correction=CorrectionRequest(
                    first["atom_ids"][0], "ADDITIONAL_EVIDENCE", "parking", TUESDAY, None, "seen"
                ),
            )
            engine.access.grant(READER, "READ")
            seen_by_operator = engine.read(first["event_id"], clock()).serialize()
            assert len(seen_by_operator["atoms"][0]["citations"]) == 2  # control: two supports
            engine.access.set_scope(source_of(engine, extra["event_id"]), LABEL)
            engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
            with reader_of(engine) as reader:
                view = reader.read(first["event_id"], clock()).serialize()
                atom = view["atoms"][0]
                assert [c["support_kind"] for c in atom["citations"]] == ["PRIMARY"]
                assert atom["applicability"] == "CURRENT"
                texts.append(seen(view))
                with pytest.raises(NornError, match=DENIED):
                    reader.read(extra["event_id"], clock())
    assert seen_equal(texts) and "TailBBB" not in texts[0] and "TailCCC" not in texts[1]


def test_a_label_change_between_candidates_and_resolution_is_a_security_change(engine):
    _public, private = build(engine, deny=False)
    with reader_of(engine) as reader:
        query = RecallRequest("parking", clock(), subject="Alex")
        corpus = exact.eligible(reader, query)
        hit = Hit(next(r for r in corpus.records if r.event_id == private["event_id"]), 0.9, "x")
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
        with pytest.raises(NornError, match="QUERY_SECURITY_CHANGED"):
            resolve(reader, hit, query, corpus.snapshot, corpus.security_epoch)


def test_an_entity_is_visible_through_any_readable_source_and_hidden_when_none_is(engine):
    _public, private = build(engine, deny=True)
    only_private = engine.db.connection.execute(
        "SELECT subject_ref FROM atoms WHERE event_id=?", (private["event_id"],)
    ).fetchone()[0]
    labels = Eligibility(engine.db.connection, engine.access.ns, READER)
    assert not labels.allows("READ", only_private)  # every contributing source is denied
    # An atom in a readable source that names the entity makes it visible (any readable source).
    from conftest import TUESDAY as when

    from norn.canonical.registry import WriteRequest
    from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
    from norn.contracts.identity import ObjectRef
    from norn.contracts.time import TimeKind, TimeValue
    from norn.extraction.atoms import FixtureAtom

    text = "Alex knows Alex."
    mention = FixtureAtom(
        "Alex",
        "knows",
        TaggedValue("ENTITY_REF", ObjectRef(HOST.namespace, "entity", only_private)),
        0,
        len(text.encode()),
        EpistemicState(Epistemic.USER_REPORTED),
        (("scope", "parking"),),
    )
    engine.write(
        WriteRequest(
            "operator",
            "mention",
            "mention",
            text.encode(),
            TimeValue(TimeKind.EXACT, when),
            when,
            (mention,),
        )
    )
    assert labels.allows("READ", only_private)


def test_derived_objects_follow_their_sources_and_unknown_kinds_are_never_granted(engine):
    public, private = build(engine, deny=True)
    labels = Eligibility(engine.db.connection, engine.access.ns, READER)
    # A correction edge needs both endpoint atoms: a denied endpoint hides the edge.
    extra = engine.write(
        request("extra", place="ZoneB"),
        correction=CorrectionRequest(
            private["atom_ids"][0], "ADDITIONAL_EVIDENCE", "parking", TUESDAY, None, "x"
        ),
    )
    edge = engine.db.connection.execute("SELECT id FROM relationships").fetchone()[0]
    assert not labels.allows("READ", edge)
    assert Eligibility(engine.db.connection, engine.access.ns, HOST.principal).allows("READ", edge)
    assert extra["event_id"] != public["event_id"]
    engine.db.connection.execute(
        "INSERT INTO objects VALUES(?,?,'mystery')", (engine.access.ns, "m")
    )
    assert not Eligibility(engine.db.connection, engine.access.ns, HOST.principal).allows(
        "READ", "m"
    )


def test_labelling_needs_admin_and_moves_the_epoch(engine):
    public, _private = build(engine, deny=False)
    engine.access.grant(READER, "WRITE")
    epoch = engine.access.check("READ")
    engine.access.set_scope(source_of(engine, public["event_id"]), "other")
    assert engine.access.check("READ") == epoch + 1
    with reader_of(engine) as reader, pytest.raises(NornError, match=DENIED):
        reader.access.set_scope(source_of(engine, public["event_id"]), "x")
    with pytest.raises(NornError, match=DENIED):
        engine.access.set_scope("source_" + "0" * 64, "x")  # an unknown source is just denied


def test_check_and_eligible_are_one_rule(engine):
    public, private = build(engine, deny=True)
    with reader_of(engine) as reader:
        for operation, object_id in (
            ("READ", None),
            ("READ", public["event_id"]),
            ("READ", private["event_id"]),
            ("WRITE", public["event_id"]),
            ("ADMIN", None),
        ):
            allowed = reader.access.eligible(operation, object_id)
            try:
                reader.access.check(operation, object_id)
                assert allowed
            except NornError:
                assert not allowed
    assert isinstance(engine.access, Access)


def test_a_denied_source_neither_marks_the_corpus_incomplete_nor_spends_scan_budget(engine):
    build(engine, deny=True)
    with reader_of(engine) as reader:
        for limit in (10_000, 1):
            query = RecallRequest("parking", clock(), subject="Alex", max_scan_records=limit)
            corpus = exact.eligible(reader, query)
            assert corpus.complete is True and len(corpus.records) == 1
            assert corpus.records[0].source_id != source_of(engine, build_private_event(engine))


def build_private_event(engine: Engine) -> str:
    return str(
        engine.db.connection.execute("SELECT id FROM events WHERE occurrence='private'").fetchone()[
            0
        ]
    )
