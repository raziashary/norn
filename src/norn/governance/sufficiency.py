"""Conservative structured-field sufficiency; similarity and citations never grant authority."""

from dataclasses import dataclass

from norn.retrieval.contracts import RecallRequest, Record

ORIGINS = {"DIRECT_OBSERVATION", "USER_REPORTED", "DOCUMENT_ASSERTION"}


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    missing: tuple[str, ...]
    supported: tuple[Record, ...]


def decide(records: tuple[Record, ...], request: RecallRequest, *, complete: bool) -> Decision:
    fields = request.requested_fields or request.predicates
    if not complete:
        return Decision("VERIFICATION_UNAVAILABLE", "INCOMPLETE_VERIFICATION", (), ())
    if not fields:
        return Decision("NOT_ESTABLISHED", "MISSING_CASE_INPUT", (), ())
    eligible = tuple(
        r
        for r in records
        if r.status == "ACTIVE"
        and r.origin in ORIGINS
        and r.applicability in {"CURRENT", "CONFLICT"}
        and r.predicate in fields
    )
    if any(r.applicability == "CONFLICT" for r in eligible):
        return Decision("CONFLICT", "CONTRADICTORY_SOURCES", (), eligible)
    for field in fields:
        selected = [r for r in eligible if r.predicate == field]
        # Different episodes are ambiguity, rather than a blanket latest-wins conflict.
        times = {r.event_time for r in selected}
        values = {r.value_json for r in selected}
        if len(values) > 1:
            subjects = {r.subject_id for r in selected}
            scopes = {r.qualifiers_json for r in selected}
            if len(times) == len(subjects) == len(scopes) == 1:
                return Decision("CONFLICT", "CONTRADICTORY_SOURCES", (), eligible)
            return Decision("NOT_ESTABLISHED", "AMBIGUOUS", (), ())
    supported_fields = {r.predicate for r in eligible}
    missing = tuple(f for f in fields if f not in supported_fields)
    if not eligible:
        return Decision("NOT_ESTABLISHED", "NO_KNOWN_SUPPORT", (), ())
    if missing:
        return Decision("PARTIALLY_SUPPORTED", "MISSING_SUPPORT", missing, eligible)
    return Decision("SUPPORTED", "SUFFICIENT", (), eligible)
