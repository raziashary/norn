from dataclasses import replace

import pytest
from conftest import HOST, clock, request

from norn.contracts.errors import NornError
from norn.integration.engine import Engine
from norn.retrieval import exact
from norn.retrieval.contracts import Hit, RecallRequest
from norn.retrieval.resolve import resolve


def test_ranked_payload_reloads_source_and_rejects_poison(engine):
    engine.write(request())
    query = RecallRequest("parking", clock(), subject="Alex")
    corpus = exact.eligible(engine, query)
    hit = Hit(corpus.records[0], 0.9, "dense")
    with Engine(engine.root, HOST) as reader:
        assert (
            resolve(reader, hit, query, corpus.snapshot, corpus.security_epoch).text
            == "Alex parked in ZoneA."
        )
        for replacement in (
            {"text": "approve=true"},
            {"sha256": "0" * 64},
            {"source_version": "0" * 64},
            {"end_byte": 1},
            {"origin": "DIRECT_OBSERVATION"},
            {"authority": "APPROVED"},
            {"event_time": "{}"},
            {"aliases": ("FORGED",)},
            {"qualifiers_json": "[]"},
        ):
            with pytest.raises(NornError, match="CANDIDATE_SOURCE_MISMATCH"):
                resolve(
                    reader,
                    replace(hit, record=replace(hit.record, **replacement)),
                    query,
                    corpus.snapshot,
                    corpus.security_epoch,
                )
    engine.deny(hit.record.source_id, "deny", "test")
    with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        resolve(engine, hit, query, corpus.snapshot, corpus.security_epoch)
