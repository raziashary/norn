"""Exhaustive cosine control over exactly the eligible, compatible vectors."""

from collections.abc import Callable, Mapping

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.embedding.assets import METHODS
from norn.embedding.baseline import LocalModels, vector
from norn.retrieval.contracts import EligibleCorpus, Hit


def encode(
    texts: tuple[str, ...], models: LocalModels, budget: QueryBudget, *, query: bool = False
) -> tuple[tuple[float, ...], ...]:
    prefix = METHODS["encoder"]["query_prefix" if query else "passage_prefix"]
    output: list[tuple[float, ...]] = []
    for offset in range(0, len(texts), 4):
        values = models.infer(
            "encoder", tuple(prefix + t for t in texts[offset : offset + 4]), budget
        )
        output.extend(vector(v) for v in values)
    require(len(output) == len(texts), "MODEL_OUTPUT_SCHEMA")
    return tuple(output)


def search(
    corpus: EligibleCorpus,
    query: tuple[float, ...],
    vectors: Mapping[str, tuple[float, ...]],
    limit: int,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[Hit, ...]:
    q = vector(list(query))
    hits = []
    for record in corpus.records:
        if checkpoint:
            checkpoint()
        require(record.key in vectors, "DENSE_ENTRY_UNAVAILABLE")
        value = vector(list(vectors[record.key]))
        hits.append(Hit(record, sum(a * b for a, b in zip(q, value, strict=True)), "dense"))
    return tuple(sorted(hits, key=lambda h: (-h.score, h.record.key))[:limit])
