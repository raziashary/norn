from dataclasses import replace
from pathlib import Path

import pytest
from conftest import clock, request

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical
from norn.retrieval import assembly, exact
from norn.retrieval.contracts import Hit, RecallRequest
from norn.retrieval.rerank import EvidenceTokenizer, rerank
from norn.retrieval.service import UnicodeTokenizer


def test_final_exposure_reserves_fields_and_counts_status_locators(engine):
    engine.write(request())
    query = RecallRequest(
        "parking and rollback", clock(), requested_fields=("parked_in", "rollback")
    )
    first = exact.eligible(engine, query).records[0]
    second = replace(first, atom_id="rollback", predicate="rollback")
    distractors = tuple(
        replace(first, atom_id=f"other-{i}", predicate="mentions") for i in range(8)
    )
    tokenizer = UnicodeTokenizer()
    packet, tokens, _ = assembly.assemble(
        (*distractors, first, second), replace(query, final_limit=2), tokenizer, complete=True
    )
    assert [r["predicate"] for r in packet["evidence"]] == ["parked_in", "rollback"]
    assert packet["status"] == "SUPPORTED"
    assert tokens == tokenizer.count(canonical(packet)) > tokenizer.count(first.text + second.text)


class _Scorer:
    """Stands in for LocalModels.infer; records the batches the reranker sends."""

    def __init__(self, scores):
        self.scores = scores
        self.batches = []

    def infer(self, role, texts, budget, *, query):
        assert role == "reranker" and query == "q"
        self.batches.append(texts)
        return [self.scores[t] for t in texts]


def _pool(engine, count):
    engine.write(request())
    first = exact.eligible(engine, RecallRequest("q", clock())).records[0]
    return tuple(
        Hit(replace(first, atom_id=f"a{i}", text=f"t{i}"), 0.0, "fusion") for i in range(count)
    )


def test_rerank_batches_by_four_orders_by_score_then_key_and_relabels_stage(engine):
    pool = _pool(engine, 6)
    scores = {f"t{i}": s for i, s in enumerate((0.1, 0.9, 0.9, -2.0, 0.5, 0.9))}
    scorer = _Scorer(scores)
    ranked = rerank(pool, "q", scorer, QueryBudget(10_000))
    assert [len(b) for b in scorer.batches] == [4, 2]
    assert {h.channel for h in ranked} == {"rerank"}
    assert [h.score for h in ranked] == [0.9, 0.9, 0.9, 0.5, 0.1, -2.0]
    tied = [h.record.key for h in ranked[:3]]
    assert tied == sorted(tied)


@pytest.mark.parametrize("bad", ([0.1], [0.1, float("nan")], [0.1, float("inf")], [0.1, "x"]))
def test_rerank_rejects_malformed_model_output(engine, bad):
    pool = _pool(engine, 2)

    class Broken:
        def infer(self, *args, **kwargs):
            return bad

    with pytest.raises(NornError, match="MODEL_OUTPUT_SCHEMA"):
        rerank(pool, "q", Broken(), QueryBudget(10_000))


MODEL_ROOT = Path(__file__).resolve().parents[1] / ".norn" / "models"


@pytest.mark.skipif(not (MODEL_ROOT / "encoder").is_dir(), reason="pinned encoder not installed")
def test_evidence_tokenizer_counts_special_tokens_with_the_pinned_vocabulary():
    tokenizer = EvidenceTokenizer(MODEL_ROOT)
    assert tokenizer.version == "e5-small-pinned-tokenizer-v1"
    # Empty text still carries [CLS] and [SEP]; each extra word adds at least one token.
    assert tokenizer.count("") == 2
    assert tokenizer.count("Alex parked in ZoneA") > tokenizer.count("Alex") > 2
