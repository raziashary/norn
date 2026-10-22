from dataclasses import replace

import pytest
from conftest import HOST, clock, request

from norn.contracts.errors import NornError
from norn.contracts.identity import canonical
from norn.contracts.time import TimeKind, TimeValue
from norn.features.context import derive
from norn.integration.engine import Engine
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.exact import eligible


def test_context_reopens_exact_occurrence_source_and_precision(tmp_path):
    root = tmp_path / "store"
    original = request()
    annotated = replace(
        original,
        atoms=(replace(original.atoms[0], qualifiers=(("location", "ZoneA"),)),),
    )
    with Engine(root, HOST, create=True) as engine:
        engine.access.bootstrap()
        receipt = engine.write(annotated)
    with Engine(root, HOST) as engine:
        records = eligible(engine, RecallRequest("Alex", clock())).records
        view = derive(records)
        assert view.event_id == receipt["event_id"]
        assert view.locations == ("ZoneA",) and view.actor_labels == ("Alex",)
        assert "microsecond" in view.text
        assert view.subject_ids[0] not in view.text and view.event_id not in view.text
        assert engine.sources.resolve(view.sources[0]) == annotated.content


def test_context_preserves_unknown_and_refuses_cross_occurrence(engine):
    original = request()
    unknown = replace(
        original,
        event_time=TimeValue(TimeKind.UNKNOWN, precision="unknown", reason="not supplied"),
    )
    engine.write(unknown)
    records = eligible(engine, RecallRequest("Alex", clock())).records
    view = derive(records)
    assert '"kind":"UNKNOWN"' in view.text
    assert view.locations == ()
    engine.write(request("other"))
    mixed = eligible(engine, RecallRequest("Alex", clock())).records
    with pytest.raises(NornError, match="FEATURE_OCCURRENCE_MISMATCH"):
        derive(mixed)
    with pytest.raises(NornError, match="FEATURE_RECORD_BUDGET"):
        derive(())
    with pytest.raises(NornError, match="UNANCHORED_CONTEXT"):
        derive((replace(records[0], qualifiers_json=canonical([["location", "Invented"]])),))
