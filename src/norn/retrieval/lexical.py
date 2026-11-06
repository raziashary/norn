"""BM25+ IDF (Robertson positive form), Unicode word tokens, no stemming/stop words.

Tokens: each word; for a hyphen/underscore compound also its parts (so "park" finds "park_zone"
while "E503-Alpha" still matches as one identifier); CJK runs as overlapping character bigrams
(single characters when alone), since those scripts have no spaces to split on.
"""

import math
import re
from collections import Counter
from collections.abc import Callable, Mapping

from norn.contracts.errors import require
from norn.retrieval.contracts import EligibleCorpus, Hit

REVISION = "bm25-positive-idf-compound-parts-cjk-bigram-v2"
K1 = 1.2
B = 0.75


_WORD = re.compile(r"[^\W_]+(?:[-_][^\W_]+)*")
_JOINER = re.compile(r"[-_]")
_CJK = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+")


def _pieces(part: str) -> list[str]:
    pieces: list[str] = []
    position = 0
    for match in _CJK.finditer(part):
        if match.start() > position:
            pieces.append(part[position : match.start()])
        run = match.group()
        pieces.extend([run] if len(run) == 1 else [run[i : i + 2] for i in range(len(run) - 1)])
        position = match.end()
    if position < len(part):
        pieces.append(part[position:])
    return pieces


def tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for word in _WORD.findall(text.casefold()):
        parts = _JOINER.split(word)
        if len(parts) > 1:
            tokens.append(word)
        for part in parts:
            tokens.extend(_pieces(part))
    return tuple(tokens)


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
