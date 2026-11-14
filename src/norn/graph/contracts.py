"""Typed graph vocabulary: nodes, relations, direction policy and edge validation (P06-T01).

The relation table mirrors the ``relation_types`` rows of migration 006 (checked against the
database when a graph is built). Direction is server policy: each relation allows only the listed
(from kind, to kind) pairs, so an unsupported direction is rejected on write and absent on read.
Similarity, frequency and graph activation never create a relation here; only a governed key, a
reviewed identity link or a source-supported statement does.
"""

from dataclasses import dataclass
from datetime import datetime

from norn.contracts.errors import NornError, require
from norn.contracts.identity import label, stable_id

NODE_KINDS = ("event", "atom", "entity", "source")
EPISTEMIC = (
    "DIRECT_OBSERVATION",
    "USER_REPORTED",
    "DOCUMENT_ASSERTION",
    "MODEL_INFERENCE",
    "HYPOTHESIS",
    "DERIVED_AGGREGATE",
)
SUPPORTED_ORIGINS = ("DIRECT_OBSERVATION", "USER_REPORTED", "DOCUMENT_ASSERTION")
STATUSES = ("ACTIVE", "RETRACTED", "UNRESOLVED")

_ANY = tuple((a, b) for a in NODE_KINDS for b in NODE_KINDS)


@dataclass(frozen=True, order=True)
class NodeRef:
    kind: str
    id: str

    def __post_init__(self) -> None:
        require(self.kind in NODE_KINDS, "UNSUPPORTED_NODE_KIND")
        require(bool(self.id), "MISSING_NODE_ID")


@dataclass(frozen=True)
class Relation:
    name: str
    traversable: bool
    causal: bool
    symmetric: bool
    endpoints: tuple[tuple[str, str], ...]

    def allows(self, source: str, target: str) -> bool:
        return (source, target) in self.endpoints or (
            self.symmetric and (target, source) in self.endpoints
        )


def _relation(
    name: str,
    traversable: bool,
    endpoints: tuple[tuple[str, str], ...],
    *,
    causal: bool = False,
    symmetric: bool = False,
) -> Relation:
    return Relation(name, traversable, causal, symmetric, endpoints)


RELATIONS: dict[str, Relation] = {
    r.name: r
    for r in (
        _relation(
            "MENTIONS", True, (("atom", "entity"), ("event", "entity"), ("source", "entity"))
        ),
        _relation("PART_OF_EVENT", True, (("atom", "event"),)),
        _relation("OBSERVED_IN", True, (("atom", "source"), ("event", "source"))),
        _relation("OCCURRED_BEFORE", True, (("event", "event"),)),
        _relation("OCCURRED_AFTER", True, (("event", "event"),)),
        _relation("RELATED_TO", True, _ANY, symmetric=True),
        _relation("REQUIRES", True, (("entity", "entity"), ("atom", "atom"), ("event", "event"))),
        _relation("CONTRADICTS", False, (("atom", "atom"),), symmetric=True),
        _relation("SUPERSEDES", False, (("atom", "atom"), ("event", "event"))),
        _relation(
            "DERIVED_FROM",
            True,
            (("atom", "atom"), ("atom", "source"), ("entity", "atom"), ("entity", "source")),
        ),
        _relation("HYPOTHESIZES_CAUSE", True, (("atom", "atom"), ("event", "event"))),
        _relation("VERIFIED_CAUSE", True, (("atom", "atom"), ("event", "event")), causal=True),
        _relation("IDENTITY_LINK", True, (("entity", "entity"),), symmetric=True),
    )
}


@dataclass(frozen=True)
class Support:
    span_id: str
    source_id: str
    revision: str


@dataclass(frozen=True)
class EdgeSpec:
    """What a producer asks to store; the canonical writer validates it before any row exists."""

    relation: str
    source: NodeRef
    target: NodeRef
    epistemic: str
    scope: str
    support_spans: tuple[str, ...]
    valid_from: str
    producer_revision: str
    valid_to: str | None = None
    status: str = "ACTIVE"

    def validate(self) -> None:
        relation = RELATIONS.get(self.relation)
        require(relation is not None, "UNSUPPORTED_RELATION")
        assert relation is not None
        require(relation.allows(self.source.kind, self.target.kind), "UNSUPPORTED_DIRECTION")
        require(self.source != self.target, "SELF_EDGE")
        require(self.epistemic in EPISTEMIC, "UNSUPPORTED_EPISTEMIC")
        require(self.status in STATUSES, "UNSUPPORTED_STATUS")
        require(bool(self.support_spans), "MISSING_PROVENANCE")
        require(len(set(self.support_spans)) == len(self.support_spans), "DUPLICATE_SUPPORT")
        if self.scope != "*":
            label(self.scope)
        label(self.producer_revision)
        start = _instant(self.valid_from)
        require(self.valid_to is None or start < _instant(self.valid_to), "INVALID_VALIDITY")
        if self.relation == "HYPOTHESIZES_CAUSE":
            require(self.epistemic in ("HYPOTHESIS", "MODEL_INFERENCE"), "HYPOTHESIS_NOT_CAUSE")
        if self.relation == "VERIFIED_CAUSE":
            require(self.epistemic in SUPPORTED_ORIGINS, "CAUSE_NEEDS_SUPPORTED_ORIGIN")

    def identity(self, namespace: str) -> str:
        """Content-derived id: the same request is the same edge, so a replay adds nothing."""
        return stable_id(
            "graph_edge",
            namespace,
            self.relation,
            self.source.kind,
            self.source.id,
            self.target.kind,
            self.target.id,
            self.epistemic,
            self.scope,
            self.valid_from,
            self.valid_to or "",
            self.producer_revision,
            self.status,
            *sorted(self.support_spans),
        )


def _instant(value: str) -> datetime:
    require(value.endswith("Z") or "+" in value, "INVALID_VALIDITY")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise NornError("INVALID_VALIDITY") from None


@dataclass(frozen=True)
class GraphEdge:
    id: str
    relation: str
    source: NodeRef
    target: NodeRef
    epistemic: str | None  # None for a structural edge derived from canonical records
    status: str
    scope: str
    supports: tuple[Support, ...]
    valid_from: str | None
    valid_to: str | None
    producer_revision: str
    commit_seq: int

    @property
    def stored(self) -> bool:
        return self.epistemic is not None

    def payload(self) -> dict[str, object]:
        """Visible content only: the namespace-wide commit counter is deliberately left out, so a
        write the principal cannot see never changes the bytes it receives."""
        return {
            "id": self.id,
            "relation": self.relation,
            "from": [self.source.kind, self.source.id],
            "to": [self.target.kind, self.target.id],
            "epistemic": self.epistemic,
            "status": self.status,
            "scope": self.scope,
            "supports": [[s.span_id, s.source_id, s.revision] for s in self.supports],
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "producer_revision": self.producer_revision,
        }


@dataclass(frozen=True, order=True)
class Arc:
    """One traversable step: leaving ``origin`` along ``edge_id`` to ``neighbor``."""

    neighbor: NodeRef
    edge_id: str
    relation: str
    forward: bool


@dataclass(frozen=True)
class GraphSnapshot:
    """The explicit basis of one build: canonical sequence and optional valid-time instant."""

    seq: int
    valid_at: str | None = None
