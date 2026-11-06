"""Append scoped source-backed correction edges without rewriting assertions."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
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


MAX_RELATIONS = 256
MAX_CONTROLS = 256
MAX_SUPPORTS = 64
"""Per-atom ceilings shared with Engine.read: appends beyond them would make an immutable atom
permanently unreadable, so they are refused at write time instead."""


def _bounded(connection: sqlite3.Connection, sql: str, params: tuple[str, ...], limit: int) -> None:
    count = connection.execute(sql, params).fetchone()[0]
    require(count < limit, "ATOM_APPEND_BUDGET")


def append_relation(
    registry: Registry, request: CorrectionRequest, new_atom: str, seq: int, recorded_at: str
) -> str:
    registry.access.check("WRITE")
    if request.classification == "SUPERSEDES":
        registry.access.check("ADMIN")
    connection, ns = registry.db.connection, registry.ns
    registry.source_for_atom(request.prior_atom)  # current access and existence check
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
    for atom in (request.prior_atom, new_atom):
        _bounded(
            connection,
            "SELECT count(*) FROM relationships WHERE ns=? AND (from_id=? OR to_id=?)",
            (ns, atom, atom),
            MAX_RELATIONS,
        )
    if request.classification == "ADDITIONAL_EVIDENCE":
        require(prior["object_value"] == new["object_value"], "EVIDENCE_VALUE_MISMATCH")
        _bounded(
            connection,
            "SELECT count(*) FROM atom_support WHERE ns=? AND atom_id=?",
            (ns, request.prior_atom),
            MAX_SUPPORTS,
        )
        support = registry.source_for_atom(new_atom)
        support_id = stable_id("support", request.prior_atom, new_atom)
        connection.execute(
            "INSERT INTO atom_support VALUES(?,?,?,?,'ADDITIONAL',?,'fixture-v1',?)",
            (
                ns,
                support_id,
                request.prior_atom,
                new["source_span_id"],
                stable_id("independence", ns, support["version_id"]),
                seq,
            ),
        )
        # The link is knowable only from the moment it was recorded, not from the older
        # source version's own recording time.
        connection.execute(
            "INSERT INTO atom_support_times VALUES(?,?,?)", (ns, support_id, recorded_at)
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
    return edge


def retract(
    registry: Registry, atom_id: str, valid_from: datetime, valid_to: datetime | None, reason: str
) -> int:
    """Withdraw an atom: its own producer may retract it; anyone else needs ADMIN."""
    valid_interval(valid_from, valid_to)
    label(reason)
    with registry.db.transaction() as connection:
        registry.access.check("WRITE")
        registry.source_for_atom(atom_id)
        producer = connection.execute(
            "SELECT e.producer FROM atoms a JOIN events e ON a.ns=e.ns AND a.event_id=e.id "
            "WHERE a.ns=? AND a.id=?",
            (registry.ns, atom_id),
        ).fetchone()
        require(producer is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
        if producer[0] != registry.access.host.principal:
            registry.access.check("ADMIN")
        _bounded(
            connection,
            "SELECT count(*) FROM assertion_events WHERE ns=? AND atom_id=?",
            (registry.ns, atom_id),
            MAX_CONTROLS,
        )
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
                registry.db.now(),
                registry.access.host.principal,
                reason,
            ),
        )
        publish(connection, registry.ns, seq, "RETRACT", [atom_id])
    return seq
