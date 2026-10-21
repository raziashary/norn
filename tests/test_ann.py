import pytest
from conftest import clock, request

from norn.contracts.errors import NornError
from norn.retrieval import ann, dense, exact
from norn.retrieval.contracts import RecallRequest


def test_actual_faiss_reload_and_same_vector_control(engine):
    engine.write(request("a"))
    engine.write(request("b", place="ZoneB"))
    corpus = exact.eligible(engine, RecallRequest("parking", clock()))
    unit = (1.0, *([0.0] * 383))
    other = (0.0, 1.0, *([0.0] * 382))
    vectors = {r.key: v for r, v in zip(corpus.records, (unit, other), strict=True)}
    exhaustive = dense.search(corpus, unit, vectors, 1)
    approximate, measurement = ann.search(
        corpus, unit, vectors, 1, expected_keys=tuple(r.key for r in corpus.records)
    )
    assert approximate[0].record.key == exhaustive[0].record.key
    assert measurement["index_bytes"] > measurement["vector_bytes"] > 0
    assert measurement["memory_scope"].startswith("WHOLE_PROCESS")
    assert "scope" in measurement["process_memory_with_indices"]
    with pytest.raises(NornError, match="ANN_CORPUS_MISMATCH"):
        ann.search(corpus, unit, vectors, 1, expected_keys=())
