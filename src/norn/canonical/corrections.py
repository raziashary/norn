"""Append scoped source-backed correction edges without rewriting assertions."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from norn.canonical.outbox import allocate, publish
from norn.contracts.errors import require
from norn.contracts.identity import canonical, label, stable_id
from norn.contracts.time import aware, stamp
from norn.governance.temporal import valid_interval

if TYPE_CHECKING:
    from norn.canonical.registry import Registry


@dataclass(frozen=True)
class CorrectionRequest:
    prior_atom: str
    classification: str
    scope: str
    valid_from: datetime
    valid_to: datetime | None
    reason: str

    def __post_init__(self) -> None:
        label(self.prior_atom)
        require(self.classification in {"SUPERSEDES", "CONTRADICTS", "ADDITIONAL_EVIDENCE"})
        label(self.scope)
        label(self.reason)
        object.__setattr__(self, "valid_from", aware(self.valid_from))
        if self.valid_to is not None:
            object.__setattr__(self, "valid_to", aware(self.valid_to))
        valid_interval(self.valid_from, self.valid_to)

    def payload(self) -> dict[str, object]:
        return {
            "prior_atom": self.prior_atom,
            "class": self.classification,
            "scope": self.scope,
            "valid_from": stamp(self.valid_from),
            "valid_to": stamp(self.valid_to) if self.valid_to else None,
            "reason": self.reason,
        }


def append_relation(registry: Registry, request: CorrectionRequest, new_atom: str, seq: int) -> str:
    registry.access.check("WRITE")
    if request.classification == "SUPERSEDES":
        registry.access.check("ADMIN")
    connection, ns = registry.db.connection, registry.ns
    prior_source = registry.source_for_atom(request.prior_atom)
    registry.source_for_atom(new_atom)
    prior = connection.execute(
        "SELECT * FROM atoms WHERE ns=? AND id=?", (ns, request.prior_atom)
    ).fetchone()
    new = connection.execute("SELECT * FROM atoms WHERE ns=? AND id=?", (ns, new_atom)).fetchone()
    require(prior is not None and new is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
    require(
        prior["subject_ref"] == new["subject_ref"]
        and prior["predicate"] == new["predicate"]
        and prior["qualifiers"] == new["qualifiers"],
        "CORRECTION_SCOPE_MISMATCH",
    )
    scope = dict(json.loads(prior["qualifiers"])).get("scope", "default")
    require(request.scope == scope, "CORRECTION_SCOPE_MISMATCH")
    require(request.prior_atom != new_atom, "SUPERSESSION_CYCLE")
    # Iterative bounded reachability: no recursion or blanket latest-wins rule.
    visited: set[str] = set()
    pending = [request.prior_atom]
    while pending:
        current = pending.pop()
        require(current != new_atom, "SUPERSESSION_CYCLE")
        if current in visited:
            continue
        visited.add(current)
        require(len(visited) <= 10_000, "LINEAGE_BUDGET")
        rows = connection.execute(
            "SELECT to_id FROM relationships WHERE ns=? AND from_id=? "
            "AND relation_type='SUPERSEDES'",
            (ns, current),
        ).fetchall()
        pending.extend(row[0] for row in rows)
    if request.classification == "ADDITIONAL_EVIDENCE":
        require(prior["object_value"] == new["object_value"], "EVIDENCE_VALUE_MISMATCH")
        support = registry.source_for_atom(new_atom)
        connection.execute(
            "INSERT INTO atom_support VALUES(?,?,?,?,'ADDITIONAL',?,'fixture-v1',?)",
            (
                ns,
                stable_id("support", request.prior_atom, new_atom),
                request.prior_atom,
                new["source_span_id"],
                stable_id("independence", ns, support["version_id"]),
                seq,
            ),
        )
    edge = stable_id("edge", ns, request.prior_atom, new_atom, canonical(request.payload()))
    connection.execute("INSERT INTO objects VALUES(?,?,'edge')", (ns, edge))
    connection.execute(
        "INSERT INTO relationships VALUES(?,?,?,?,?,?,'ACTIVE',?,?,?,'fixture-v1',?)",
        (
            ns,
            edge,
            new_atom,
            request.prior_atom,
            request.classification,
            new["origin"] or "UNKNOWN",
            request.scope,
            stamp(request.valid_from),
            stamp(request.valid_to) if request.valid_to else None,
            seq,
        ),
    )
    connection.execute(
        "INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            ns,
            edge,
            request.prior_atom,
            new_atom,
            request.classification,
            request.scope,
            stamp(request.valid_from),
            stamp(request.valid_to) if request.valid_to else None,
            seq,
            registry.access.host.principal,
            request.reason,
        ),
    )
    connection.execute(
        "INSERT INTO edge_support VALUES(?,?,?,?,'fixture-v1')",
        (ns, edge, new_atom, new["source_span_id"]),
    )
    require(prior_source is not None)
    return edge


def retract(
    registry: Registry, atom_id: str, valid_from: datetime, valid_to: datetime | None, reason: str
) -> int:
    valid_interval(valid_from, valid_to)
    label(reason)
    with registry.db.transaction() as connection:
        registry.access.check("WRITE")
        registry.source_for_atom(atom_id)
        seq = allocate(connection, registry.ns)
        connection.execute(
            "INSERT INTO assertion_events VALUES(?,?,?,'RETRACTED',?,?,?,?,?,?)",
            (
                registry.ns,
                stable_id("status", registry.ns, str(seq)),
                atom_id,
                stamp(valid_from),
                stamp(valid_to) if valid_to else None,
                seq,
                stamp(datetime.now(UTC)),
                registry.access.host.principal,
                reason,
            ),
        )
        publish(connection, registry.ns, seq, "RETRACT", [atom_id])
    return seq
