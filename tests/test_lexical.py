import math
from dataclasses import replace

import pytest
from conftest import clock, request

from norn.contracts.errors import NornError
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.exact import eligible
from norn.retrieval.lexical import search, tokenize


def test_bm25_hand_calculated_rare_term_and_reopened_original_source(engine):
    rare = engine.write(request("rare", place="E503-Alpha"))
    engine.write(request("common", place="ZoneA"))
    corpus = eligible(engine, RecallRequest("E503-Alpha", clock()))
    hits = search(corpus, "E503-Alpha", 10)
    assert len(hits) == 1 and hits[0].record.event_id == rare["event_id"]
    # Both source documents have four tokens; one occurrence in one of two documents.
    assert hits[0].score == pytest.approx(math.log(2))
    assert "E503-Alpha" in hits[0].record.text
    assert search(corpus, "...", 10) == ()
    assert search(corpus, "不存在", 10) == ()
    assert tokenize("PARKIR Café E503-Alpha") == ("parkir", "café", "e503-alpha")


def test_unextracted_source_prevents_false_ready_but_current_denial_does_not_leak(engine):
    engine.write(request("allowed"))
    raw = engine.write(replace(request("unparsed", place="UNINDEXED-CANARY"), atoms=()))
    query = RecallRequest("Alex parking", clock(), subject="Alex", requested_fields=("parked_in",))
    corpus = eligible(engine, query)
    assert not corpus.complete and corpus.reason == "UNINDEXED_SOURCE"
    with pytest.raises(NornError, match="UNINDEXED_SOURCE"):
        engine.project()
    assert engine.db.connection.execute("SELECT count(*) FROM ready_snapshots").fetchone()[0] == 0
    result = engine.recall(query).serialize()
    assert result["status"] == "VERIFICATION_UNAVAILABLE" and "UNINDEXED-CANARY" not in str(result)
    engine.deny(raw["event_id"], "deny-unparsed", "test")
    assert eligible(engine, query).complete
    engine.project()
    result = engine.recall(query).serialize()
    assert result["status"] == "SUPPORTED" and "UNINDEXED-CANARY" not in str(result)
