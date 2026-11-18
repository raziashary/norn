"""Eligible, source-grounded seed vectors for graph readers (P06-T03).

A seed is one nonnegative, sum-one weighting over eligible entity anchors, built from the ranked
votes of named channels (exact, BM25, dense T0, optionally binding). The same seed object is the
declared control handed identically to every graph algorithm and reused over every topology, so
nothing here reads the graph, an edge, a gold label or an evaluator module: a seed is a function
of the principal's eligible canonical records and the channel results alone.

Rules fixed by the owner on 14 November 2026 (see the T03 entry of ``ADR_LOG``):

* anchors are entities; a candidate atom's mass goes to the entity it is about (the keyed entity
  its own source defines, else its subject entity, the identity policy of T17 and the stating
  entity of T02), the atom ids kept as provenance, and one entity counts once per channel (its
  best rank), so an entity with many matching atoms is not favoured over one with a single match;
* each channel votes ``1 / (RRF_K + rank)`` (the conventional fusion rule, exact votes at rank
  one), the votes of an entity add up and the vector is normalised to sum one;
* a channel result is accepted as given with its name and version recorded, which is how a
  binding channel is supported without being run in M1.

Every anchor is checked against canonical state before it can carry mass: readable through
``Access.eligible`` (ACL, tombstone, erasure) and present at the explicit snapshot and knowledge
time. An anchor that fails is an error, never a silent drop or a count, so a denied object is
indistinguishable from an absent one in everything a reader receives. The digest leaves out the
snapshot and the security epoch, namespace-wide counters that would reveal unseen writes.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from norn.canonical.registry import Registry
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, label

SEED_REVISION = "seed-entity-rrf60-v1"
RRF_K = 60
CHANNELS = ("exact", "lexical", "dense", "binding")
CONVENTIONAL = ("exact", "lexical", "dense")
DENSE_ONLY = ("dense",)
EXACT_DEGRADED = "EXACT_CHANNEL_DEGRADED"
AMBIGUOUS_NAME = "AMBIGUOUS_NAME"
EMPTY_SEED = "EMPTY_SEED"
MAX_VOTES = 1000
SUM_TOLERANCE = 1e-12


@dataclass(frozen=True)
class Vote:
    """One ranked entry of a channel: the entity it names and the atoms that support it."""

    entity_id: str
    atom_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChannelResult:
    """The ranked votes of one channel, best first (the exact channel is unordered: every vote
    counts at rank one), with the version of whatever produced them."""

    name: str
    version: str
    votes: tuple[Vote, ...]
    reason: str | None = None  # why the channel is empty, when it is
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeedBasis:
    """The explicit canonical basis the votes were computed at."""

    snapshot: int
    knowledge_at: str
    security_epoch: int


@dataclass(frozen=True)
class Anchor:
    entity_id: str
    weight: float
    atom_ids: tuple[str, ...]
    channels: tuple[str, ...]


@dataclass(frozen=True)
class Seed:
    revision: str
    channels: tuple[tuple[str, str, int], ...]  # (name, version, distinct entities voted)
    anchors: tuple[Anchor, ...]  # sorted by entity id
    flags: tuple[str, ...]
    reasons: tuple[tuple[str, str], ...] = field(default=())  # (channel, why it was empty)

    def vector(self) -> dict[str, float]:
        return {a.entity_id: a.weight for a in self.anchors}

    def payload(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "channels": [list(c) for c in self.channels],
            "anchors": [
                [a.entity_id, a.weight, list(a.atom_ids), list(a.channels)] for a in self.anchors
            ],
            "flags": list(self.flags),
            "reasons": [list(r) for r in self.reasons],
        }

    def digest(self) -> str:
        return digest(canonical(self.payload()).encode())


# The entity an atom is about, under the identity policy: the keyed entity that the atom's own
# source span defines (the stating entity, where derived REQUIRES edges attach), else the atom's
# subject entity. ``norn.extraction.relations`` resolves its stating entity by the same rule.
_ANCHOR = (
    "COALESCE((SELECT k.id FROM entities k WHERE k.ns=a.ns AND k.provisional_span_id="
    "a.source_span_id AND k.external_key IS NOT NULL ORDER BY k.id LIMIT 1), a.subject_ref)"
)


def anchor_entity(registry: Registry, atom_id: str) -> str:
    """The anchor entity of one atom; raises when the atom does not exist."""
    row = registry.db.connection.execute(
        "SELECT " + _ANCHOR + " FROM atoms a WHERE a.ns=? AND a.id=?", (registry.ns, atom_id)
    ).fetchone()
    require(row is not None, "SEED_ANCHOR_NOT_ELIGIBLE")
    return str(row[0])


def eligible_entity(registry: Registry, basis: SeedBasis, entity_id: str) -> bool:
    """Whether the principal may read the entity and an atom about it exists at the basis."""
    if not registry.access.eligible("READ", entity_id):
        return False
    return (
        registry.db.connection.execute(
            "SELECT 1 FROM atoms a JOIN events e ON e.ns=a.ns AND e.id=a.event_id "
            "WHERE a.ns=? AND " + _ANCHOR + "=? AND a.commit_seq<=? AND e.recorded_at<=? LIMIT 1",
            (registry.ns, entity_id, basis.snapshot, basis.knowledge_at),
        ).fetchone()
        is not None
    )


def _check_entity(registry: Registry, basis: SeedBasis, entity_id: str) -> None:
    label(entity_id)
    require(registry.access.eligible("READ", entity_id), "SEED_ANCHOR_NOT_ELIGIBLE")
    require(eligible_entity(registry, basis, entity_id), "SEED_ANCHOR_STALE")


def _check_atom(registry: Registry, basis: SeedBasis, entity_id: str, atom_id: str) -> None:
    label(atom_id)
    require(registry.access.eligible("READ", atom_id), "SEED_ANCHOR_NOT_ELIGIBLE")
    present = registry.db.connection.execute(
        "SELECT 1 FROM atoms a JOIN events e ON e.ns=a.ns AND e.id=a.event_id "
        "WHERE a.ns=? AND a.id=? AND " + _ANCHOR + "=? AND a.commit_seq<=? AND e.recorded_at<=?",
        (registry.ns, atom_id, entity_id, basis.snapshot, basis.knowledge_at),
    ).fetchone()
    require(present is not None, "SEED_ANCHOR_STALE")


def _ranked(result: ChannelResult) -> dict[str, tuple[int, set[str]]]:
    """Best rank and supporting atoms per distinct entity of one channel."""
    require(len(result.votes) <= MAX_VOTES, "SEED_CHANNEL_BUDGET")
    ranked: dict[str, tuple[int, set[str]]] = {}
    for vote in result.votes:
        if vote.entity_id in ranked:
            ranked[vote.entity_id][1].update(vote.atom_ids)
            continue
        rank = 1 if result.name == "exact" else len(ranked) + 1
        ranked[vote.entity_id] = (rank, set(vote.atom_ids))
    return ranked


def construct_seed(registry: Registry, channels: Sequence[ChannelResult], basis: SeedBasis) -> Seed:
    """The one seed of these channel results; raises on any anchor that is not eligible now."""
    registry.access.check("READ")
    require(len(channels) > 0, "SEED_NO_CHANNELS")
    names = [c.name for c in channels]
    require(len(set(names)) == len(names), "SEED_DUPLICATE_CHANNEL")
    require(all(n in CHANNELS for n in names), "SEED_UNKNOWN_CHANNEL")
    require(basis.snapshot >= 0 and bool(basis.knowledge_at), "SEED_BASIS_INVALID")
    mass: dict[str, float] = {}
    atoms: dict[str, set[str]] = {}
    voted: dict[str, list[str]] = {}
    summary: list[tuple[str, str, int]] = []
    flags: set[str] = set()
    reasons: list[tuple[str, str]] = []
    checked: set[str] = set()
    for result in sorted(channels, key=lambda c: c.name):
        label(result.version)
        ranked = _ranked(result)
        summary.append((result.name, result.version, len(ranked)))
        flags.update(result.flags)
        if not ranked:
            reasons.append((result.name, result.reason or "NO_MATCH"))
            if result.name == "exact":
                flags.add(EXACT_DEGRADED)
        for entity_id in sorted(ranked):
            rank, supporting = ranked[entity_id]
            if entity_id not in checked:
                _check_entity(registry, basis, entity_id)
                checked.add(entity_id)
            for atom_id in supporting:
                _check_atom(registry, basis, entity_id, atom_id)
            mass[entity_id] = mass.get(entity_id, 0.0) + 1.0 / (RRF_K + rank)
            atoms.setdefault(entity_id, set()).update(supporting)
            voted.setdefault(entity_id, []).append(result.name)
    require(all(math.isfinite(m) and m > 0 for m in mass.values()), "SEED_MASS_INVALID")
    total = sum(mass[e] for e in sorted(mass))
    anchors: list[Anchor] = []
    if mass:
        require(math.isfinite(total) and total > 0, "SEED_MASS_INVALID")
        anchors = [
            Anchor(e, mass[e] / total, tuple(sorted(atoms[e])), tuple(sorted(voted[e])))
            for e in sorted(mass)
        ]
        require(abs(sum(a.weight for a in anchors) - 1.0) < SUM_TOLERANCE, "SEED_MASS_INVALID")
    else:
        flags.add(EMPTY_SEED)
    registry.access.recheck("READ", basis.security_epoch)
    return Seed(
        SEED_REVISION,
        tuple(summary),
        tuple(anchors),
        tuple(sorted(flags)),
        tuple(sorted(reasons)),
    )
