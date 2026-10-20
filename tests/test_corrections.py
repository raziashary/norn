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
