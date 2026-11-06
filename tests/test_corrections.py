from dataclasses import replace
from datetime import timedelta

import pytest
from conftest import TUESDAY, clock, request

from norn.canonical.corrections import CorrectionRequest, append_relation, retract
from norn.canonical.outbox import allocate
from norn.contracts.errors import NornError


def correction(prior, classification="SUPERSEDES", scope="parking", start=TUESDAY, end=None):
    return CorrectionRequest(prior, classification, scope, start, end, "source-correction")


def test_scoped_correction_late_arrival_and_knowledge_snapshot(engine):
    first = engine.write(request())
    changed = engine.write(
        request("correction", place="ZoneB"), correction=correction(first["atom_ids"][0])
    )
    assert (
        engine.read(first["event_id"], clock()).serialize()["atoms"][0]["applicability"]
        == "SUPERSEDED"
    )
    assert (
        engine.read(changed["event_id"], clock()).serialize()["atoms"][0]["applicability"]
        == "CURRENT"
    )
    historical = engine.read(first["event_id"], clock(first["commit_seq"])).serialize()
    assert historical["atoms"][0]["applicability"] == "CURRENT"
    from norn.contracts.time import parse_instant

    cutoff = parse_instant(first["durable_at"])
    assert (
        engine.read(first["event_id"], clock(knowledge=cutoff)).serialize()["atoms"][0][
            "applicability"
        ]
        == "CURRENT"
    )
    with pytest.raises(NornError, match="NOT_ESTABLISHED"):
        engine.read(changed["event_id"], clock(first["commit_seq"]))
    earlier_valid = clock(valid=TUESDAY - timedelta(days=1))
    assert (
        engine.read(first["event_id"], earlier_valid).serialize()["atoms"][0]["applicability"]
        == "CURRENT"
    )
    assert (
        engine.read(changed["event_id"], earlier_valid).serialize()["atoms"][0]["applicability"]
        == "FUTURE"
    )


def test_wrong_scope_and_cycle_reject_atomically(engine):
    first = engine.write(request())
    with pytest.raises(NornError, match="CORRECTION_SCOPE_MISMATCH"):
        engine.write(
            request("wrong", place="ZoneB"),
            correction=correction(first["atom_ids"][0], scope="other"),
        )
    assert engine.db.connection.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    changed = engine.write(
        request("correction", place="ZoneB"), correction=correction(first["atom_ids"][0])
    )
    with pytest.raises(NornError, match="SUPERSESSION_CYCLE"), engine.db.transaction():
        append_relation(
            engine.registry,
            correction(changed["atom_ids"][0]),
            first["atom_ids"][0],
            allocate(engine.db.connection, engine.access.ns),
            engine.db.now(),
        )
    assert engine.db.connection.execute("SELECT count(*) FROM corrections").fetchone()[0] == 1


def test_contradiction_no_winner_and_additional_evidence_retains_sources(engine):
    first = engine.write(request())
    other = engine.write(
        request("contradiction", place="ZoneB"),
        correction=correction(first["atom_ids"][0], "CONTRADICTS"),
    )
    for receipt in (first, other):
        assert engine.read(receipt["event_id"], clock()).serialize()["outcome"] == "CONFLICT"
    # Separate assertion with identical value but independent bytes.
    extra = request("extra")
    text = b"Alex parked in ZoneA. Additional report."
    extra = replace(extra, content=text, atoms=(replace(extra.atoms[0], end=len(text)),))
    engine.write(extra, correction=correction(first["atom_ids"][0], "ADDITIONAL_EVIDENCE"))
    citations = engine.read(first["event_id"], clock()).serialize()["atoms"][0]["citations"]
    assert len(citations) == 2 and len({c["source_version"] for c in citations}) == 2
    historical = engine.read(first["event_id"], clock(first["commit_seq"])).serialize()
    assert len(historical["atoms"][0]["citations"]) == 1


def test_retraction_preserves_origin_and_history(engine):
    receipt = engine.write(request())
    retract(engine.registry, receipt["atom_ids"][0], TUESDAY, None, "withdrawn")
    atom = engine.read(receipt["event_id"], clock()).serialize()["atoms"][0]
    assert atom["origin"] == "USER_REPORTED" and atom["epistemic"] == "RETRACTED"
    assert atom["assertion_status"] == "RETRACTED"
    earlier = engine.read(receipt["event_id"], clock(receipt["commit_seq"])).serialize()["atoms"][0]
    assert earlier["epistemic"] == "USER_REPORTED" and earlier["assertion_status"] == "ACTIVE"


def test_applicability_precedence_is_fixed_not_relationship_id_order(engine):
    first = engine.write(request())
    engine.write(request("replace", place="ZoneB"), correction=correction(first["atom_ids"][0]))
    engine.write(
        request("dispute", place="ZoneC"),
        correction=correction(first["atom_ids"][0], "CONTRADICTS"),
    )
    atom = engine.read(first["event_id"], clock()).serialize()["atoms"][0]
    # Replaced evidence is superseded; a later dispute must not turn it back into a live conflict.
    assert atom["applicability"] == "SUPERSEDED"


def test_retracted_atom_is_not_reported_as_a_live_conflict(engine):
    first = engine.write(request())
    retract(engine.registry, first["atom_ids"][0], TUESDAY, None, "withdrawn")
    engine.write(
        request("dispute", place="ZoneC"),
        correction=correction(first["atom_ids"][0], "CONTRADICTS"),
    )
    atom = engine.read(first["event_id"], clock()).serialize()["atoms"][0]
    assert atom["applicability"] == "UNKNOWN"


def test_writes_cannot_push_an_atom_past_the_limit_that_makes_it_unreadable(engine):
    first = engine.write(request())
    atom = first["atom_ids"][0]
    for minute in range(256):
        retract(engine.registry, atom, TUESDAY + timedelta(minutes=minute), None, "withdrawn")
    with pytest.raises(NornError, match="ATOM_APPEND_BUDGET"):
        retract(engine.registry, atom, TUESDAY + timedelta(minutes=999), None, "withdrawn")
    # The refusal leaves the event readable; the old behaviour made it fail permanently.
    assert engine.read(first["event_id"], clock()).serialize()["atoms"]


def test_a_hypothesis_cannot_put_an_observation_into_conflict(engine):
    from norn.contracts.evidence import Epistemic, EpistemicState

    first = engine.write(request())
    engine.write(
        request("guess", place="ZoneC", origin=EpistemicState(Epistemic.HYPOTHESIS)),
        correction=correction(first["atom_ids"][0], "CONTRADICTS"),
    )
    atom = engine.read(first["event_id"], clock()).serialize()["atoms"][0]
    assert atom["applicability"] == "CURRENT"
    # Positive control: the same dispute from an observation does create the conflict.
    engine.write(
        request("report", place="ZoneD"),
        correction=correction(first["atom_ids"][0], "CONTRADICTS"),
    )
    atom = engine.read(first["event_id"], clock()).serialize()["atoms"][0]
    assert atom["applicability"] == "CONFLICT"


def test_only_the_producer_or_an_admin_can_retract(engine, tmp_path):
    from conftest import HOST

    from norn.governance.access import HostIdentity
    from norn.integration.engine import Engine

    receipt = engine.write(request())
    other = HostIdentity(HOST.namespace, "writer")
    engine.access.grant("writer", "WRITE")
    engine.access.grant("writer", "READ")
    with Engine(engine.root, other) as peer:
        with pytest.raises(NornError, match="NOT_AUTHORIZED"):
            retract(peer.registry, receipt["atom_ids"][0], TUESDAY, None, "withdrawn")
    engine.access.grant("writer", "ADMIN")
    with Engine(engine.root, other) as peer:
        retract(peer.registry, receipt["atom_ids"][0], TUESDAY, None, "withdrawn")
    # The producer itself needs no extra grant.
    mine = engine.write(request("mine", place="ZoneB"))
    retract(engine.registry, mine["atom_ids"][0], TUESDAY, None, "withdrawn")


def test_additional_evidence_is_not_known_before_the_link_was_recorded(tmp_path):
    from datetime import UTC, datetime

    from conftest import HOST

    from norn.contracts.time import QueryClock
    from norn.integration.engine import Engine

    now = [datetime(2026, 10, 20, 10, tzinfo=UTC)]
    with Engine(tmp_path / "store", HOST, create=True, clock=lambda: now[0]) as engine:
        engine.access.bootstrap()
        first = engine.write(request())
        now[0] = datetime(2026, 10, 25, 10, tzinfo=UTC)
        # Identical bytes: the same source version, recorded on the 20th, is cited again.
        engine.write(
            request("extra"), correction=correction(first["atom_ids"][0], "ADDITIONAL_EVIDENCE")
        )

        def known(day):
            cut = datetime(2026, 10, day, 12, tzinfo=UTC)
            return QueryClock(cut, "UTC", "VALID_TIME", TUESDAY, cut, None)

        before = engine.read(first["event_id"], known(22)).serialize()["atoms"][0]["citations"]
        after = engine.read(first["event_id"], known(26)).serialize()["atoms"][0]["citations"]
        # Before the link existed only the primary support is knowable (the old source-version
        # time would have shown both on the 22nd).
        assert len(before) == 1 and len(after) == 2
