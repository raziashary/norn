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
    # The query yields three terms (compound, "e503", "alpha"), each present once in one of two
    # documents: idf = ln(1 + 1.5/1.5) = ln 2. Document lengths are 6 and 4 (average 5), so
    # each term contributes ln2 * 2.2 / (1 + 1.2 * (0.25 + 0.75 * 6/5)).
    expected = 3 * math.log(2) * 2.2 / (1 + 1.2 * (0.25 + 0.75 * 6 / 5))
    assert hits[0].score == pytest.approx(expected)
    assert "E503-Alpha" in hits[0].record.text
    assert search(corpus, "...", 10) == ()
    assert search(corpus, "不存在", 10) == ()
    assert tokenize("PARKIR Café E503-Alpha") == ("parkir", "café", "e503-alpha", "e503", "alpha")


def test_compound_parts_and_cjk_bigrams_are_searchable_without_losing_identifiers():
    assert tokenize("park_zone") == ("park_zone", "park", "zone")
    assert tokenize("停车位置") == ("停车", "车位", "位置")
    assert tokenize("车") == ("车",)
    assert tokenize("lot 停车场 B2") == ("lot", "停车", "车场", "b2")
    assert tokenize("a-b_c") == ("a-b_c", "a", "b", "c")


def test_compound_parts_find_the_compound_and_the_compound_finds_only_itself(engine):
    compound = engine.write(request("compound", place="park_zone"))
    corpus = eligible(engine, RecallRequest("park", clock()))
    assert [h.record.event_id for h in search(corpus, "park", 10)] == [compound["event_id"]]
    assert [h.record.event_id for h in search(corpus, "park_zone", 10)] == [compound["event_id"]]


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
