from dataclasses import replace

from conftest import clock, request

from norn.contracts.identity import canonical
from norn.retrieval import assembly, exact
from norn.retrieval.contracts import RecallRequest
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
