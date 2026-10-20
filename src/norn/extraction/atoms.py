"""Deterministic fixture contract, not natural-language or authority inference.

The host supplies exact subject/object spans and a predicate. The extractor checks
anchoring and preserves uncertainty. A predicate is a fixture annotation; source
provenance alone never establishes semantic entailment or normative approval.
"""

from dataclasses import dataclass

from norn.canonical.sources import SourceSpan, SourceStore
from norn.contracts.errors import require
from norn.contracts.evidence import AssertionStatus, EpistemicState, TaggedValue
from norn.contracts.identity import canonical, label


@dataclass(frozen=True)
class FixtureAtom:
    subject: str
    predicate: str
    value: TaggedValue
    start: int
    end: int
    epistemic: EpistemicState
    qualifiers: tuple[tuple[str, str], ...] = ()
    unresolved: bool = False

    def __post_init__(self) -> None:
        label(self.subject)
        label(self.predicate)
        require(isinstance(self.value, TaggedValue) and isinstance(self.epistemic, EpistemicState))
        require(type(self.start) is int and type(self.end) is int and 0 <= self.start < self.end)
        require(type(self.qualifiers) is tuple and len(self.qualifiers) <= 16)
        require(type(self.unresolved) is bool)
        keys = []
        for item in self.qualifiers:
            require(type(item) is tuple and len(item) == 2)
            key, value = item
            label(key)
            require(type(value) is str and len(value) <= 256)
            keys.append(key)
        require(len(keys) == len(set(keys)), "DUPLICATE_QUALIFIER")

    def payload(self) -> dict[str, object]:
        from norn.contracts.identity import ObjectRef
        from norn.contracts.time import TimeValue

        value = self.value.value
        encoded: object = value
        if isinstance(value, TimeValue):
            encoded = value.payload()
        elif isinstance(value, ObjectRef):
            encoded = {
                "namespace": value.namespace.key,
                "kind": value.kind,
                "object_id": value.object_id,
            }
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "value": {"tag": self.value.tag, "value": encoded},
            "start": self.start,
            "end": self.end,
            "epistemic": {
                "external": self.epistemic.external.value,
                "original": self.epistemic.original.value if self.epistemic.original else None,
            },
            "qualifiers": self.qualifiers,
            "unresolved": self.unresolved,
        }


@dataclass(frozen=True)
class ExtractedAtom:
    fixture: FixtureAtom
    span: SourceSpan
    status: AssertionStatus


def extract(
    store: SourceStore, version: str, fixtures: tuple[FixtureAtom, ...]
) -> tuple[ExtractedAtom, ...]:
    require(type(fixtures) is tuple and len(fixtures) <= 64, "ATOM_BUDGET")
    result = []
    for fixture in fixtures:
        require(isinstance(fixture, FixtureAtom))
        span = store.span(version, fixture.start, fixture.end)
        text = store.resolve(span).decode()
        value = fixture.value
        if value.tag in {"TEXT", "INTEGER", "DECIMAL"}:
            require(str(value.value) in text, "UNANCHORED_VALUE")
        require(fixture.subject in text, "UNANCHORED_SUBJECT")
        # No inferred action, cause, approval or entity identity is generated.
        status = AssertionStatus.UNRESOLVED if fixture.unresolved else fixture.epistemic.status
        canonical(fixture.payload())  # Refuse unsupported/nonfinite serialized values.
        result.append(ExtractedAtom(fixture, span, status))
    return tuple(result)
