import pytest
from conftest import clock, request

from norn.canonical.identity import inspect_entity, register_entity, review_identity
from norn.contracts.errors import NornError


def test_occurrences_delivery_and_reviewed_name_identity(engine):
    first = engine.write(request("monday"))
    second = engine.write(request("tuesday"))
    assert first["event_id"] != second["event_id"]
    first_subject = engine.read(first["event_id"], clock()).serialize()["atoms"][0]["subject_ref"]
    second_subject = engine.read(second["event_id"], clock()).serialize()["atoms"][0]["subject_ref"]
    assert first_subject != second_subject
    assert first["source_version"] == second["source_version"]
    assert engine.write(request("tuesday")) == second
    with pytest.raises(NornError, match="IDEMPOTENCY_CONFLICT"):
        engine.write(request("tuesday", place="ZoneB"))
    with pytest.raises(NornError, match="OCCURRENCE_EXISTS"):
        engine.write(request("tuesday", delivery="other"))
    # Same label at distinct spans is provisional, never a name-based merge.
    other = engine.write(request("third", place="ZoneB"))
    a = register_entity(engine.registry, first["atom_ids"][0], "Alex")
    identical = register_entity(engine.registry, second["atom_ids"][0], "Alex")
    assert a != identical
    assert a == first_subject and identical == second_subject
    b = register_entity(engine.registry, other["atom_ids"][0], "Alex")
    assert a != b
    assert inspect_entity(engine.registry, a)["review_history"] == []
    review_identity(engine.registry, a, b, "DIFFERENT", first["atom_ids"][0])
    assert inspect_entity(engine.registry, a)["review_history"][0]["decision"] == "DIFFERENT"
