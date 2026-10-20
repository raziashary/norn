import pytest
from conftest import HOST, clock, request

from norn.contracts.errors import NornError
from norn.contracts.evidence import Epistemic, EpistemicState
from norn.integration.engine import Engine


def test_current_denial_propagates_lineage_purge_pending_and_restore(engine, tmp_path):
    first = engine.write(request())
    derived = engine.write(
        request("derived", place="ZoneB", origin=EpistemicState(Epistemic.DERIVED_AGGREGATE))
    )
    lineage = engine.lineage(derived["atom_ids"][0], (first["atom_ids"][0],), "test-aggregate-v1")
    source = engine.registry.source_for_atom(first["atom_ids"][0])["source_id"]
    held = engine.read(first["event_id"], clock(first["commit_seq"]))
    denied = engine.deny(source, "erase-1", "synthetic-expiry")
    assert denied["serving_denied"] is True and denied["physical_purge_complete"] is False
    assert denied["obligations"] and all(o["status"] == "PENDING" for o in denied["obligations"])
    assert lineage in {
        o["selector"] for o in denied["obligations"] if o["artifact"] == "canonical_sql"
    }
    assert engine.deny(source, "erase-1", "synthetic-expiry") == denied
    assert engine.sources.read(first["source_version"])  # Tombstone is not physical purge.
    with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        held.serialize()
    for receipt in (first, derived):
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            engine.read(receipt["event_id"], clock(receipt["commit_seq"]))
    backup = tmp_path / "denied-backup"
    assert engine.backup(backup)["verified"] is True
    with Engine(backup, HOST) as restored:
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            restored.read(first["event_id"], clock())


def test_lineage_cycle_and_physical_completion_not_fabricated(engine):
    a = engine.write(request("a", origin=EpistemicState(Epistemic.HYPOTHESIS)))
    b = engine.write(request("b", place="ZoneB", origin=EpistemicState(Epistemic.HYPOTHESIS)))
    engine.lineage(b["atom_ids"][0], (a["atom_ids"][0],), "revision1")
    with pytest.raises(NornError, match="LINEAGE_CYCLE"):
        engine.lineage(a["atom_ids"][0], (b["atom_ids"][0],), "revision1")


def test_entity_selector_enumerates_contained_evidence_and_real_blob_selector(engine):
    receipt = engine.write(request())
    unrelated = engine.write(request("separate"))
    subject = engine.read(receipt["event_id"], clock()).serialize()["atoms"][0]["subject_ref"]
    result = engine.deny(subject, "erase-entity", "synthetic-expiry")
    sql_selectors = {
        o["selector"] for o in result["obligations"] if o["artifact"] == "canonical_sql"
    }
    blob_selectors = {
        o["selector"] for o in result["obligations"] if o["artifact"] == "source_blobs"
    }
    assert {subject, receipt["event_id"], *receipt["atom_ids"]} <= sql_selectors
    assert receipt["source_version"] in blob_selectors
    assert result["physical_purge_complete"] is False
    with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        engine.read(receipt["event_id"], clock())
    assert engine.read(unrelated["event_id"], clock()).serialize()["outcome"] == "SUPPORTED"


def test_derivation_selector_denies_and_enumerates_output(engine):
    first = engine.write(request("input"))
    output = engine.write(
        request("output", place="ZoneB", origin=EpistemicState(Epistemic.HYPOTHESIS))
    )
    lineage = engine.lineage(output["atom_ids"][0], (first["atom_ids"][0],), "fixture-v1")
    result = engine.deny(lineage, "deny-lineage", "synthetic-expiry")
    selectors = {o["selector"] for o in result["obligations"] if o["artifact"] == "canonical_sql"}
    assert {lineage, output["event_id"], *output["atom_ids"]} <= selectors
    with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        engine.read(output["event_id"], clock())
    assert engine.read(first["event_id"], clock()).serialize()["outcome"] == "SUPPORTED"
