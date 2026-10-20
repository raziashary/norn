from decimal import Decimal

import pytest
from conftest import HOST

from norn.cli import parse_write
from norn.contracts.errors import NornError
from norn.contracts.evidence import (
    Applicability,
    AssertionStatus,
    Epistemic,
    EpistemicState,
    Lifecycle,
    Outcome,
    TaggedValue,
)
from norn.contracts.identity import Namespace, ObjectRef


@pytest.mark.parametrize(
    "tag,value",
    [
        ("INTEGER", True),
        ("INTEGER", 2**64),
        ("BOOLEAN", 1),
        ("DECIMAL", float("nan")),
        ("DECIMAL", "NaN"),
        ("DECIMAL", "Infinity"),
        ("DECIMAL", Decimal("1.2")),
        ("TEXT", ""),
        ("JSON_NULL", "null"),
        ("FLOAT", 1.0),
    ],
)
def test_invalid_values(tag, value):
    with pytest.raises(NornError):
        TaggedValue(tag, value)


def test_id_namespace_and_independent_axes():
    with pytest.raises(NornError):
        Namespace("../../tenant", "w", "p")
    with pytest.raises(NornError):
        ObjectRef(HOST.namespace, "atom", "arbitrary")
    assert TaggedValue("DECIMAL", "1.200").value == "1.200"
    assert (
        len(
            {
                Lifecycle.INDEX_PENDING,
                AssertionStatus.ACTIVE,
                Applicability.CURRENT,
                Outcome.SUPPORTED,
            }
        )
        == 4
    )


@pytest.mark.parametrize("external", list(Epistemic))
def test_seven_external_origins(external):
    state = EpistemicState(
        external, Epistemic.USER_REPORTED if external == Epistemic.RETRACTED else None
    )
    assert state.external == external
    assert state.origin != Epistemic.RETRACTED
    assert (state.status == AssertionStatus.RETRACTED) == (external == Epistemic.RETRACTED)


def test_unknown_retraction_quarantines_and_forged_authority_rejected():
    assert EpistemicState(Epistemic.RETRACTED).status == AssertionStatus.UNRESOLVED
    with pytest.raises(NornError, match="INVALID_FIELDS"):
        parse_write({"authority": "APPROVED", "principal": "admin"}, HOST)


@pytest.mark.parametrize("external", list(Epistemic))
def test_all_seven_import_export_through_persisted_reader(engine, external):
    from conftest import clock, request

    state = EpistemicState(
        external, Epistemic.USER_REPORTED if external == Epistemic.RETRACTED else None
    )
    receipt = engine.write(request(origin=state))
    atom = engine.read(receipt["event_id"], clock()).serialize()["atoms"][0]
    assert atom["epistemic"] == external.value
    assert atom["origin"] == state.origin.value


def test_unknown_retracted_origin_survives_quarantined_roundtrip(engine):
    from conftest import clock, request

    receipt = engine.write(request(origin=EpistemicState(Epistemic.RETRACTED)))
    result = engine.read(receipt["event_id"], clock()).serialize()
    assert result["atoms"][0]["epistemic"] == "RETRACTED"
    assert result["atoms"][0]["origin"] is None
    assert result["atoms"][0]["assertion_status"] == "UNRESOLVED"
    assert result["outcome"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize(
    "value,text",
    [
        (TaggedValue("INTEGER", 7), "Alex counted 7."),
        (TaggedValue("DECIMAL", "1.20"), "Alex paid 1.20."),
        (TaggedValue("BOOLEAN", True), "Alex says true."),
        (TaggedValue("JSON_NULL", None), "Alex left it unset."),
    ],
)
def test_tagged_values_survive_canonical_consumer(engine, value, text):
    from dataclasses import replace

    from conftest import clock, request

    original = request()
    atom = replace(original.atoms[0], value=value, end=len(text.encode()))
    receipt = engine.write(replace(original, content=text.encode(), atoms=(atom,)))
    exported = engine.read(receipt["event_id"], clock()).serialize()["atoms"][0]["value"]
    assert exported == {"tag": value.tag, "value": value.value}


def test_time_value_and_current_entity_reference_controls(engine):
    from dataclasses import replace

    from conftest import TUESDAY, clock, request

    from norn.contracts.time import TimeKind, TimeValue

    first = engine.write(request())
    target = engine.read(first["event_id"], clock()).serialize()["atoms"][0]["subject_ref"]
    original = request("reference")
    value = TaggedValue("ENTITY_REF", ObjectRef(HOST.namespace, "entity", target))
    receipt = engine.write(replace(original, atoms=(replace(original.atoms[0], value=value),)))
    assert (
        engine.read(receipt["event_id"], clock()).serialize()["atoms"][0]["value"]["value"][
            "object_id"
        ]
        == target
    )
    time_value = TaggedValue("TIME", TimeValue(TimeKind.EXACT, TUESDAY))
    another = request("time-value")
    timed = engine.write(replace(another, atoms=(replace(another.atoms[0], value=time_value),)))
    assert (
        engine.read(timed["event_id"], clock()).serialize()["atoms"][0]["value"]["value"]["kind"]
        == "EXACT"
    )
    foreign = ObjectRef(Namespace("other", "w", "p"), "entity", target)
    with pytest.raises(NornError, match="CROSS_NAMESPACE_REFERENCE"):
        engine.write(
            replace(
                request("foreign"),
                atoms=(replace(original.atoms[0], value=TaggedValue("ENTITY_REF", foreign)),),
            )
        )
    engine.deny(target, "deny-referenced-entity", "synthetic-expiry")
    with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        engine.read(receipt["event_id"], clock())
