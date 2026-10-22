"""Immediate logical denial plus explicit, incomplete physical-purge obligations."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from norn.canonical.outbox import allocate, publish
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, label
from norn.contracts.time import stamp
from norn.governance.access import POLICY

if TYPE_CHECKING:
    from norn.canonical.registry import Registry


def dependents(registry: Registry, selector: str) -> list[str]:
    """Compute bounded canonical and derivation closure, retaining all IDs."""
    connection, ns = registry.db.connection, registry.ns
    seen: set[str] = set()
    pending = [selector]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        require(len(seen) <= 10_000, "LINEAGE_BUDGET")
        queries = (
            (
                "SELECT e.id FROM events e JOIN source_versions v "
                "ON e.ns=v.ns AND e.source_version=v.id "
                "WHERE e.ns=? AND v.source_id=?",
                current,
            ),
            ("SELECT id FROM atoms WHERE ns=? AND event_id=?", current),
            ("SELECT id FROM atoms WHERE ns=? AND subject_ref=?", current),
            ("SELECT id FROM atoms WHERE ns=? AND object_ref=?", current),
            ("SELECT event_id FROM atoms WHERE ns=? AND id=?", current),
            (
                "SELECT a.atom_id FROM atom_support a JOIN source_spans s "
                "ON a.ns=s.ns AND a.span_id=s.id JOIN source_versions v "
                "ON s.ns=v.ns AND s.version_id=v.id WHERE a.ns=? AND v.source_id=?",
                current,
            ),
            (
                "SELECT e.id FROM entities e JOIN source_spans s "
                "ON e.ns=s.ns AND e.provisional_span_id=s.id JOIN source_versions v "
                "ON s.ns=v.ns AND s.version_id=v.id WHERE e.ns=? AND v.source_id=?",
                current,
            ),
            ("SELECT id FROM relationships WHERE ns=? AND (from_id=? OR to_id=?)", current),
            (
                "SELECT d.id FROM derivation_inputs i JOIN derivations d "
                "ON i.ns=d.ns AND i.derivation_id=d.id WHERE i.ns=? AND i.input_id=?",
                current,
            ),
            ("SELECT output_id FROM derivations WHERE ns=? AND id=?", current),
        )
        for sql, value in queries:
            args = (ns, value, value) if "OR to_id" in sql else (ns, value)
            rows = connection.execute(sql + " LIMIT 10001", args).fetchall()
            require(len(rows) <= 10_000, "LINEAGE_BUDGET")
            pending.extend(row[0] for row in rows)
            require(len(pending) <= 100_000, "LINEAGE_BUDGET")
    return sorted(seen)


def deny(registry: Registry, selector: str, request_id: str, reason: str) -> dict[str, object]:
    label(request_id)
    label(reason)
    connection, ns = registry.db.connection, registry.ns
    with registry.db.transaction():
        registry.access.check("ADMIN")
        prior = connection.execute(
            "SELECT * FROM deletion_requests WHERE ns=? AND id=?", (ns, request_id)
        ).fetchone()
        if prior is not None:
            require(
                prior["selector_id"] == selector and prior["reason"] == reason,
                "IDEMPOTENCY_CONFLICT",
            )
        else:
            registry.access.check("READ", selector)
            objects = dependents(registry, selector)
            seq = allocate(connection, ns)
            connection.execute(
                "INSERT INTO deletion_requests VALUES(?,?,?,?,1,?,?,?,?)",
                (
                    ns,
                    request_id,
                    selector,
                    POLICY,
                    registry.access.host.principal,
                    stamp(datetime.now(UTC)),
                    seq,
                    reason,
                ),
            )
            for object_id in objects:
                connection.execute(
                    "INSERT INTO tombstones VALUES(?,?,?,?)", (ns, object_id, request_id, seq)
                )
                # Selectors remain metadata-only; no physical erasure is claimed.
                for artifact in (
                    "canonical_sql",
                    "derived_representations",
                    "traces",
                    "backup_generations",
                ):
                    connection.execute(
                        "INSERT INTO purge_obligations VALUES(?,?,?,?,'PENDING')",
                        (ns, request_id, artifact, object_id),
                    )
                versions = connection.execute(
                    "SELECT v.id FROM source_versions v WHERE v.ns=? AND (v.source_id=? OR v.id IN "
                    "(SELECT e.source_version FROM events e WHERE e.ns=? AND e.id=?))",
                    (ns, object_id, ns, object_id),
                ).fetchall()
                for version in versions:
                    connection.execute(
                        "INSERT OR IGNORE INTO purge_obligations "
                        "VALUES(?,?,'source_blobs',?,'PENDING')",
                        (ns, request_id, version[0]),
                    )
                artifacts = connection.execute(
                    "SELECT DISTINCT artifact_digest FROM projection_entries WHERE ns=? "
                    "AND (atom_id=? OR event_id=?) LIMIT 10001",
                    (ns, object_id, object_id),
                ).fetchall()
                require(len(artifacts) <= 10_000, "LINEAGE_BUDGET")
                for artifact in artifacts:
                    connection.execute(
                        "INSERT OR IGNORE INTO purge_obligations "
                        "VALUES(?,?,'projection_artifacts',?,'PENDING')",
                        (ns, request_id, artifact[0]),
                    )
                binding_artifacts = connection.execute(
                    "SELECT artifact_digest FROM binding_entries WHERE ns=? "
                    "AND (atom_id=? OR event_id=?) UNION "
                    "SELECT m.checkpoint_digest FROM binding_entries e JOIN binding_manifests m "
                    "ON e.ns=m.ns AND e.manifest_id=m.id WHERE e.ns=? "
                    "AND (e.atom_id=? OR e.event_id=?) AND m.checkpoint_digest<>'NONE' LIMIT 10001",
                    (ns, object_id, object_id, ns, object_id, object_id),
                ).fetchall()
                require(len(binding_artifacts) <= 10_000, "LINEAGE_BUDGET")
                # Checkpoints may be shared by unaffected generations. These are
                # reconciliation obligations, never authority to unlink shared CAS bytes.
                for artifact in binding_artifacts:
                    connection.execute(
                        "INSERT OR IGNORE INTO purge_obligations "
                        "VALUES(?,?,'binding_artifacts',?,'PENDING')",
                        (ns, request_id, artifact[0]),
                    )
            publish(connection, ns, seq, "SERVING_DENIED", objects)
    return purge_status(registry, request_id)


def purge_status(registry: Registry, request_id: str) -> dict[str, object]:
    registry.access.check("ADMIN")
    rows = registry.db.connection.execute(
        "SELECT artifact,selector,status FROM purge_obligations "
        "WHERE ns=? AND request_id=? ORDER BY artifact,selector",
        (registry.ns, request_id),
    ).fetchall()
    require(bool(rows), "NOT_AUTHORIZED_OR_NOT_FOUND")
    obligations = [dict(row) for row in rows]
    return {
        "request_id": request_id,
        "serving_denied": True,
        "physical_purge_complete": False,
        "obligations": obligations,
        "manifest_digest": digest(canonical(obligations).encode()),
    }
