"""Fixed reranker over the supplied pool; evidence budget uses the pinned tokenizer."""

import math
from pathlib import Path

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.embedding.assets import verified
from norn.embedding.baseline import LocalModels
from norn.retrieval.contracts import Hit


class EvidenceTokenizer:
    version = "e5-small-pinned-tokenizer-v1"

    def __init__(self, root: Path):
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(verified(root, "encoder") / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=True).ids)


def rerank(
    hits: tuple[Hit, ...], text: str, models: LocalModels, budget: QueryBudget
) -> tuple[Hit, ...]:
    output: list[Hit] = []
    for offset in range(0, len(hits), 4):
        batch = hits[offset : offset + 4]
        scores = models.infer("reranker", tuple(h.record.text for h in batch), budget, query=text)
        require(
            len(scores) == len(batch)
            and all(type(s) in (float, int) and math.isfinite(s) for s in scores),
            "MODEL_OUTPUT_SCHEMA",
        )
        output.extend(Hit(h.record, float(s), "rerank") for h, s in zip(batch, scores, strict=True))
    return tuple(sorted(output, key=lambda h: (-h.score, h.record.key)))
