from dataclasses import replace

from conftest import clock, request

from norn.canonical.corrections import CorrectionRequest
from norn.contracts.identity import canonical
from norn.governance.sufficiency import decide
from norn.retrieval import assembly, exact
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.service import UnicodeTokenizer


def test_five_statuses_and_origins_are_independent_of_rank(engine):
    engine.write(request())
    query = RecallRequest("parking", clock(), requested_fields=("parked_in",))
    r = exact.eligible(engine, query).records[0]
    assert decide((r,), query, complete=True).status == "SUPPORTED"
    partial = replace(query, requested_fields=("parked_in", "rollback"))
    assert decide((r,), partial, complete=True).missing == ("rollback",)
    assert decide((r,), partial, complete=True).status == "PARTIALLY_SUPPORTED"
    assert decide((), query, complete=True).status == "NOT_ESTABLISHED"
    assert decide((r,), query, complete=False).status == "VERIFICATION_UNAVAILABLE"
    assert (
        decide(
            (r, replace(r, value_json='{"tag":"TEXT","value":"ZoneB"}')), query, complete=True
        ).status
        == "CONFLICT"
    )
    for origin in ("HYPOTHESIS", "MODEL_INFERENCE", "DERIVED_AGGREGATE"):
        assert (
            decide((replace(r, origin=origin),), query, complete=True).status == "NOT_ESTABLISHED"
        )
    assert (
        decide((r,), replace(query, requested_fields=()), complete=True).reason
        == "MISSING_CASE_INPUT"
    )


def test_packing_does_not_erase_conflict_and_counts_full_packet(engine):
    engine.write(request())
    query = RecallRequest("parking", clock(), requested_fields=("parked_in",), final_limit=1)
    r = exact.eligible(engine, query).records[0]
    other = replace(r, atom_id="other", value_json='{"tag":"TEXT","value":"ZoneB"}')
    tokenizer = UnicodeTokenizer()
    packet, tokens, _ = assembly.assemble((r, other), query, tokenizer, complete=True)
    assert packet["status"] == "CONFLICT" and len(packet["evidence"]) == 1
    assert tokens == tokenizer.count(canonical(packet)) <= query.max_evidence_tokens
    packet, tokens, _ = assembly.assemble(
        (r,), replace(query, max_evidence_tokens=1), tokenizer, complete=True
    )
    assert packet == {} and tokens == 0


def test_same_name_is_not_identity_but_explicit_contradiction_remains_conflict(engine):
    first = engine.write(request("a"))
    second = engine.write(request("b", place="ZoneB"))
    query = RecallRequest("Alex parking", clock(), subject="Alex", requested_fields=("parked_in",))
    engine.project()
    result = engine.recall(query).serialize()
    assert result["status"] == "NOT_ESTABLISHED" and result["reason"] == "AMBIGUOUS"
    assert len({r["subject_id"] for r in result["evidence"]}) == 2
    assert {r["event_id"] for r in result["evidence"]} == {first["event_id"], second["event_id"]}
    engine.write(
        request("contradiction", place="ZoneC"),
        correction=CorrectionRequest(
            first["atom_ids"][0],
            "CONTRADICTS",
            "parking",
            query.clock.valid_at,
            None,
            "explicit-conflict",
        ),
    )
    engine.project()
    assert engine.recall(query).serialize()["status"] == "CONFLICT"


def test_different_assertion_scopes_are_preserved_and_not_conflated(engine):
    from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
    from norn.extraction.atoms import FixtureAtom

    content = b"Alex parked in ZoneA for work and ZoneB for home."
    atoms = tuple(
        FixtureAtom(
            "Alex",
            "parked_in",
            TaggedValue("TEXT", value),
            0,
            len(content),
            EpistemicState(Epistemic.USER_REPORTED),
            (("scope", scope),),
        )
        for value, scope in (("ZoneA", "work"), ("ZoneB", "home"))
    )
    engine.write(replace(request("scopes"), content=content, atoms=atoms))
    engine.project()
    query = RecallRequest("Alex parking", clock(), requested_fields=("parked_in",))
    result = engine.recall(query).serialize()
    assert result["status"] == "NOT_ESTABLISHED" and result["reason"] == "AMBIGUOUS"
    # P01 creates separate provisional identities per atom, even in one source span.
    assert len({r["subject_id"] for r in result["evidence"]}) == 2
    assert {r["qualifiers_json"] for r in result["evidence"]} == {
        '[["scope", "work"]]',
        '[["scope", "home"]]',
    }
