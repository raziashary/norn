import math

import pytest
from conftest import clock, request

from norn.contracts.errors import NornError
from norn.embedding.assets import verified
from norn.embedding.baseline import ModelWorker, vector
from norn.retrieval import dense, exact
from norn.retrieval.contracts import RecallRequest


def test_exhaustive_same_vector_control_preserves_distinct_occurrences(engine):
    a, b = engine.write(request("a")), engine.write(request("b"))
    corpus = exact.eligible(engine, RecallRequest("parking", clock()))
    unit = (1.0, *([0.0] * 383))
    vectors = {r.key: unit for r in corpus.records}
    hits = dense.search(corpus, unit, vectors, 10)
    assert {h.record.event_id for h in hits} == {a["event_id"], b["event_id"]}
    assert [h.record.key for h in hits] == sorted(vectors)
    assert all(h.score == 1 for h in hits)
    with pytest.raises(NornError, match="DENSE_ENTRY_UNAVAILABLE"):
        dense.search(corpus, unit, {}, 10)


@pytest.mark.parametrize(
    "values", [[0.0] * 384, [1.0] * 383, [math.nan] * 384, [math.inf] * 384, [2.0] * 384]
)
def test_invalid_geometry_cannot_fake_embeddings(values):
    with pytest.raises(NornError, match="INVALID_VECTOR"):
        vector(values)


def test_models_require_explicit_enable_and_exact_assets(tmp_path):
    with pytest.raises(NornError, match="LOCAL_MODELS_NOT_ENABLED"):
        ModelWorker(tmp_path, "encoder", enabled=False, checkpoint=lambda: None)
    with pytest.raises(NornError):
        verified(tmp_path, "encoder")
