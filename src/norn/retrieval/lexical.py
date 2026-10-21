"""BM25+ IDF (Robertson positive form), Unicode word tokens, no stemming/stop words."""

import math
import re
from collections import Counter
from collections.abc import Callable, Mapping

from norn.contracts.errors import require
from norn.retrieval.contracts import EligibleCorpus, Hit

REVISION = "bm25-positive-idf-unicode-word-v1"
K1 = 1.2
B = 0.75


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[^\W_]+(?:[-_][^\W_]+)*", text.casefold()))


def search(
    corpus: EligibleCorpus,
    text: str,
    limit: int,
    index: Mapping[str, Mapping[str, int]] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[Hit, ...]:
    require(type(limit) is int and 1 <= limit <= 1000)
    terms = tuple(sorted(set(tokenize(text))))
    if not terms or not corpus.records:
        return ()
    frequencies = []
    document_frequency: Counter[str] = Counter()
    term_set = set(terms)
    for record in corpus.records:
        if checkpoint:
            checkpoint()
        counts = Counter(index[record.key]) if index is not None else Counter(tokenize(record.text))
        frequencies.append(counts)
        document_frequency.update(term_set.intersection(counts))
    lengths = [sum(f.values()) for f in frequencies]
    average = sum(lengths) / len(lengths)
    if average == 0:
        return ()
    ranked = []
    for record, f, length in zip(corpus.records, frequencies, lengths, strict=True):
        if checkpoint:
            checkpoint()
        score = 0.0
        for term in terms:
            frequency = f[term]
            if frequency:
                df = document_frequency[term]
                idf = math.log(1 + (len(frequencies) - df + 0.5) / (df + 0.5))
                score += (
                    idf * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / average))
                )
        if score > 0:
            ranked.append(Hit(record, score, "lexical"))
    return tuple(sorted(ranked, key=lambda h: (-h.score, h.record.key))[:limit])
