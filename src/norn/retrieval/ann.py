"""Optional HNSW diagnostic over the same already-eligible FP32 vectors as exhaustive search."""

import time
from collections.abc import Mapping
from typing import Any

from norn.contracts.errors import require
from norn.embedding.baseline import vector
from norn.retrieval.contracts import EligibleCorpus, Hit
from norn.telemetry.resources import memory


def search(
    corpus: EligibleCorpus,
    query: tuple[float, ...],
    vectors: Mapping[str, tuple[float, ...]],
    limit: int,
    *,
    ef_search: int = 32,
    expected_keys: tuple[str, ...],
) -> tuple[tuple[Hit, ...], dict[str, Any]]:
    import faiss
    import numpy as np

    require(1 <= limit <= 1000 and ef_search in {16, 32, 64, 128}, "ANN_CONFIG")
    keys = tuple(r.key for r in corpus.records)
    require(keys == expected_keys, "ANN_CORPUS_MISMATCH")
    require(set(keys) <= vectors.keys(), "DENSE_ENTRY_UNAVAILABLE")
    q = vector(list(query))
    matrix = np.asarray([vector(list(vectors[k])) for k in keys], dtype=np.float32)
    if not keys:
        return (), {"count": 0, "index_bytes": 0, "build_ns": 0, "search_ns": 0}
    faiss.omp_set_num_threads(1)
    before = memory()
    started = time.perf_counter_ns()
    index = faiss.IndexHNSWFlat(384, 16, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = 40
    index.hnsw.efSearch = ef_search
    index.add(matrix)
    encoded = faiss.serialize_index(index)
    # Actual reload of the same derived native index is part of this diagnostic.
    reopened = faiss.deserialize_index(encoded)
    build_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    scores, positions = reopened.search(np.asarray([q], dtype=np.float32), min(limit, len(keys)))
    search_ns = time.perf_counter_ns() - started
    hits = tuple(
        Hit(corpus.records[int(i)], float(s), "ann")
        for s, i in zip(scores[0], positions[0], strict=True)
        if i >= 0
    )
    require(len({h.record.key for h in hits}) == len(hits), "ANN_DUPLICATE")
    return tuple(sorted(hits, key=lambda h: (-h.score, h.record.key))), {
        "count": len(keys),
        "index_bytes": int(encoded.nbytes),
        "vector_bytes": int(matrix.nbytes),
        "process_memory_before": before,
        "process_memory_with_indices": memory(),
        "memory_scope": "WHOLE_PROCESS_WITH_ORIGINAL_REOPENED_INDEX_AND_SERIALIZED_COPY",
        "build_ns": build_ns,
        "search_ns": search_ns,
        "faiss_version": faiss.__version__,
        "metric": "NORMALIZED_INNER_PRODUCT",
        "m": 16,
        "ef_construction": 40,
        "ef_search": ef_search,
        "threads": 1,
        "stage": "SAME_VECTOR_APPROXIMATION",
        "graph": "SEARCH_ACCELERATOR_ONLY",
    }
