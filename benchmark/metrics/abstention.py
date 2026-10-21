"""Both answer and abstention failures are retained; unobserved safety stays unknown."""

from dataclasses import asdict
from typing import Any

from benchmark.adapters.contracts import Result
from benchmark.fixtures.scenarios import Gold
from norn.contracts.identity import canonical


def abstention_score(
    result: Result, gold: Gold, complete_set: bool | None, partial_set: bool | None = None
) -> dict[str, Any]:
    observed = result.disposition == "OK"
    accepted = result.evidence_status in {"SUPPORTED", "PARTIALLY_SUPPORTED"} if observed else None
    answerable = gold.expected_status in {"SUPPORTED", "PARTIALLY_SUPPORTED"}
    partial_correct = (
        result.evidence_status == "PARTIALLY_SUPPORTED"
        and partial_set is True
        and set(result.missing_fields) == set(gold.missing_fields)
    )
    evidence_correct = (
        partial_correct
        if gold.expected_status == "PARTIALLY_SUPPORTED"
        else complete_set is True
        if gold.expected_status in {"SUPPORTED", "CONFLICT"}
        else True
    )
    payload = canonical(asdict(result))
    leaks = [
        marker
        for marker in (*gold.forbidden_sources, *gold.forbidden_canaries)
        if marker in payload
    ]
    correct = (
        (result.evidence_status == gold.expected_status and evidence_correct) if observed else None
    )
    return {
        "observed": observed,
        "answerable": answerable,
        "full_answerable": gold.expected_status == "SUPPORTED",
        "partial_answerable": gold.expected_status == "PARTIALLY_SUPPORTED",
        "partial_useful": partial_correct if observed and gold.partial_sets else None,
        "partial_utility": (
            sum(bool(set(slot) & {c.source_id for c in result.candidates}) for slot in gold.slots)
            / len(gold.slots)
            if partial_correct and gold.slots
            else 0.0
        )
        if observed and gold.partial_sets
        else None,
        "insufficient_for_full": gold.expected_status != "SUPPORTED",
        "accepted": accepted,
        "status_correct": result.evidence_status == gold.expected_status if observed else None,
        "correct_supported": correct,
        "false_answer": bool(accepted)
        and (
            not answerable
            or (gold.expected_status == "PARTIALLY_SUPPORTED" and not partial_correct)
        )
        if observed
        else None,
        "false_abstention": not accepted and answerable if observed else None,
        "missing_reason_correct": result.reason == gold.reason
        if observed and not answerable
        else None,
        "privacy_incidents": len(leaks),
        "privacy_observed": observed,
        "ambiguity_correct": result.evidence_status == "NOT_ESTABLISHED"
        if observed and gold.reason == "AMBIGUOUS"
        else None,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [row for row in rows if row["observed"]]
    answerable = [r for r in observed if r["answerable"]]
    insufficient = [r for r in observed if r["insufficient_for_full"]]
    partial = [r for r in observed if r["partial_answerable"]]
    ambiguous = [r for r in observed if r["ambiguity_correct"] is not None]
    reasons = [r for r in observed if r["missing_reason_correct"] is not None]
    accepted = [r for r in observed if r["accepted"]]
    return {
        "planned": len(rows),
        "completed": len(observed),
        "failure_counts": len(rows) - len(observed),
        "false_answer_rate": sum(r["false_answer"] for r in insufficient) / len(insufficient)
        if insufficient
        else None,
        "false_answer_denominator": len(insufficient),
        "false_abstention_rate": sum(r["false_abstention"] for r in answerable) / len(answerable)
        if answerable
        else None,
        "false_abstention_denominator": len(answerable),
        "selective_coverage": len(accepted) / len(observed) if observed else None,
        "selective_risk": sum(not r["correct_supported"] for r in accepted) / len(accepted)
        if accepted
        else None,
        "accepted_denominator": len(accepted),
        "partial_answer_usefulness": sum(r["partial_utility"] for r in partial) / len(partial)
        if partial
        else None,
        "qualified_partial_accuracy": sum(bool(r["partial_useful"]) for r in partial) / len(partial)
        if partial
        else None,
        "partial_answer_denominator": len(partial),
        "five_status_accuracy": sum(r["status_correct"] for r in observed) / len(observed)
        if observed
        else None,
        "status_denominator": len(observed),
        "ambiguity_detection_rate": sum(r["ambiguity_correct"] for r in ambiguous) / len(ambiguous)
        if ambiguous
        else None,
        "ambiguity_denominator": len(ambiguous),
        "missing_reason_accuracy": sum(r["missing_reason_correct"] for r in reasons) / len(reasons)
        if reasons
        else None,
        "missing_reason_denominator": len(reasons),
        "privacy_incidents": sum(r["privacy_incidents"] for r in rows),
        "privacy_observation_denominator": sum(r["privacy_observed"] for r in rows),
    }
