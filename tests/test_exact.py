from datetime import timedelta

from conftest import TUESDAY, clock, request

from norn.contracts.identity import stable_id
from norn.integration.engine import Engine
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.exact import eligible, lookup


def test_reopened_actor_time_and_exact_id_do_not_substitute_similar_ids(engine):
    good = engine.write(request())
    other = engine.write(request("other", place="ZoneB"))
    query = RecallRequest(
        "Alex parking",
        clock(),
        subject="Alex",
        event_start=TUESDAY,
        event_end=TUESDAY + timedelta(days=1),
    )
    with Engine(engine.root, engine.access.host) as reopened:
        corpus = eligible(reopened, query)
    assert len(corpus.records) == 2 and corpus.complete
    assert {h.record.event_id for h in lookup(corpus, query)} == {
        good["event_id"],
        other["event_id"],
    }
    exact = RecallRequest("Alex", clock(), event_id=good["event_id"])
    assert {r.event_id for r in eligible(engine, exact).records} == {good["event_id"]}
    unknown = RecallRequest("Alex", clock(), event_id=good["event_id"] + "x")
    assert not eligible(engine, unknown).records
    outside = RecallRequest("Alex", clock(), event_start=TUESDAY + timedelta(days=1))
    assert not eligible(engine, outside).records


def test_current_denial_precedes_window_and_historical_snapshot(engine):
    for index in range(8):
        hidden = engine.write(request(f"denied-{index}", place=f"FORBIDDEN-{index}"))
        sid = stable_id("source", engine.access.ns, hidden["source_version"])
        engine.deny(sid, f"erase-{index}", "synthetic-control")
    good = engine.write(request("allowed"))
    corpus = eligible(engine, RecallRequest("Alex", clock(), subject="Alex", max_scan_records=1))
    assert corpus.complete and len(corpus.records) == 1
    assert corpus.records[0].event_id == good["event_id"]
    assert "FORBIDDEN" not in corpus.records[0].text
