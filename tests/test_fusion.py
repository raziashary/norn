from dataclasses import replace

import pytest
from conftest import clock, request

from norn.contracts.errors import NornError
from norn.retrieval import exact, fusion
from norn.retrieval.contracts import Hit, RecallRequest


def test_rrf_hand_values_exact_union_and_duplicate_votes(engine):
    engine.write(request("a"))
    engine.write(request("b"))
    a, b = exact.eligible(engine, RecallRequest("parking", clock())).records
    hits = fusion.fuse((Hit(a, 1, "exact"),), ((Hit(b, 9, "lexical"), Hit(a, 8, "lexical")),), 2)
    assert hits[0].record == a and hits[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert hits[1].record == b and hits[1].score == pytest.approx(1 / 61)
    assert fusion.fuse((Hit(a, 1, "exact"),), ((Hit(b, 9, "lexical"),),), 1)[0].record == a
    with pytest.raises(NornError, match="DUPLICATE_CHANNEL_VOTE"):
        fusion.fuse((), ((Hit(a, 1, "lexical"), Hit(a, 2, "lexical")),), 2)
    with pytest.raises(NornError, match="CANDIDATE_IDENTITY_MISMATCH"):
        fusion.fuse((Hit(a, 1, "exact"),), ((Hit(replace(a, text="poison"), 1, "dense"),),), 2)
