from dataclasses import replace

import pytest
from conftest import clock, request

from norn.contracts.errors import NornError
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue


def test_uncertain_and_empty_extraction_never_invent_action_cause_or_authority(engine):
    original = request()
    uncertain = replace(
        original.atoms[0], unresolved=True, epistemic=EpistemicState(Epistemic.HYPOTHESIS)
    )
    receipt = engine.write(replace(original, atoms=(uncertain,)))
    result = engine.read(receipt["event_id"], clock()).serialize()
    atom = result["atoms"][0]
    assert atom["origin"] == "HYPOTHESIS" and atom["assertion_status"] == "UNRESOLVED"
    assert atom["authority"] == "UNVERIFIED" and result["outcome"] == "NOT_ESTABLISHED"
    assert "cause" not in str(result).lower()
    empty = engine.write(replace(request("other"), atoms=()))
    assert engine.read(empty["event_id"], clock()).serialize()["atoms"] == []


def test_unanchored_or_invalid_span_rejects_without_canonical_write(engine):
    original = request()
    with pytest.raises(NornError, match="UNANCHORED_VALUE"):
        engine.write(
            replace(
                original,
                atoms=(replace(original.atoms[0], value=TaggedValue("TEXT", "invented-canary")),),
            )
        )
    assert engine.db.connection.execute("SELECT count(*) FROM events").fetchone()[0] == 0
