"""Source-normalized field reservations and deterministic, tokenizer-bounded packets."""

from collections.abc import Callable
from dataclasses import asdict
from typing import Any, Protocol

from norn.contracts.identity import canonical
from norn.governance.sufficiency import Decision, decide
from norn.retrieval.contracts import RecallRequest, Record


class TokenCounter(Protocol):
    version: str

    def count(self, text: str) -> int: ...


def packet(records: tuple[Record, ...], request: RecallRequest, complete: bool) -> dict[str, Any]:
    decision = decide(records, request, complete=complete)
    return {
        "status": decision.status,
        "reason": decision.reason,
        "missing_fields": decision.missing,
        "evidence": [asdict(r) for r in records],
    }


def assemble(
    records: tuple[Record, ...],
    request: RecallRequest,
    tokenizer: TokenCounter,
    *,
    complete: bool,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], int, Decision]:
    fields = request.requested_fields or request.predicates
    full_decision = decide(records, request, complete=complete)
    # Reserve one candidate for each requested field, then fill by supplied rank.
    reserved = [next((r for r in records if r.predicate == field), None) for field in fields]
    ordered = list(dict.fromkeys(r for r in reserved if r is not None))
    ordered.extend(r for r in records if r not in ordered)
    selected: list[Record] = []
    for record in ordered:
        if checkpoint:
            checkpoint()
        if len(selected) >= request.final_limit:
            break
        candidate_packet = packet(tuple([*selected, record]), request, complete)
        if tokenizer.count(canonical(candidate_packet)) <= request.max_evidence_tokens:
            selected.append(record)
    result = packet(tuple(selected), request, complete)
    if full_decision.status == "CONFLICT" or full_decision.reason == "AMBIGUOUS":
        result.update(status=full_decision.status, reason=full_decision.reason, missing_fields=())
    tokens = tokenizer.count(canonical(result))
    if tokens > request.max_evidence_tokens:
        # Even the mandatory status header does not fit. No text is exposed.
        result = {
            "status": "VERIFICATION_UNAVAILABLE",
            "reason": "EVIDENCE_TOKEN_BUDGET",
            "missing_fields": (),
            "evidence": [],
        }
        tokens = tokenizer.count(canonical(result))
        if tokens > request.max_evidence_tokens:
            result = {}
            tokens = 0
    return result, tokens, decide(tuple(selected), request, complete=complete)
