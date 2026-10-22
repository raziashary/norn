"""Deterministic episode context; identities remain keys and unknown time stays unknown.

Inputs must come from the canonical eligibility/readback path. Derivation retains
source locators; the public reader must revalidate current access before serving.
"""

import json
from dataclasses import dataclass

from norn.canonical.sources import SourceSpan
from norn.contracts.errors import require
from norn.contracts.identity import canonical
from norn.retrieval.contracts import Record

REVISION = "canonical-context-v1"


@dataclass(frozen=True)
class ContextView:
    namespace: str
    event_id: str
    snapshot: int
    subject_ids: tuple[str, ...]
    actor_labels: tuple[str, ...]
    event_time_json: str
    locations: tuple[str, ...]
    sources: tuple[SourceSpan, ...]

    @property
    def text(self) -> str:
        """Only source-observed labels/time/location enter the representation.

        Opaque canonical identity keys are for deterministic filters/readback;
        encoding them would make accidental identifier memorization a signal.
        """
        time = json.loads(self.event_time_json)
        return canonical(
            {
                "actors": self.actor_labels,
                "time": time,
                "locations": self.locations,
            }
        )


def derive(records: tuple[Record, ...]) -> ContextView:
    require(type(records) is tuple and 0 < len(records) <= 64, "FEATURE_RECORD_BUDGET")
    first = records[0]
    identity = (first.namespace, first.event_id, first.snapshot, first.event_time)
    require(
        all((r.namespace, r.event_id, r.snapshot, r.event_time) == identity for r in records),
        "FEATURE_OCCURRENCE_MISMATCH",
    )
    locations = set()
    for record in records:
        qualifiers = dict(json.loads(record.qualifiers_json))
        # A host-annotated location is context. Narrative mentions and a similarly
        # named entity are not enough to invent a location or merge identity.
        if "location" in qualifiers:
            require(
                type(qualifiers["location"]) is str
                and bool(qualifiers["location"])
                and qualifiers["location"] in record.text,
                "UNANCHORED_CONTEXT",
            )
            locations.add(qualifiers["location"])
    spans = {SourceSpan(r.source_version, r.start_byte, r.end_byte, r.sha256) for r in records}
    return ContextView(
        first.namespace,
        first.event_id,
        first.snapshot,
        tuple(sorted({r.subject_id for r in records})),
        tuple(sorted({alias for r in records for alias in r.aliases})),
        first.event_time,
        tuple(sorted(locations)),
        tuple(sorted(spans, key=lambda s: (s.version_id, s.start, s.end, s.sha256))),
    )
