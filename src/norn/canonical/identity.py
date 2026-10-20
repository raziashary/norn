"""Occurrence identity and reviewed entity decisions, independent of labels."""

from typing import TYPE_CHECKING

from norn.canonical.outbox import allocate, publish
from norn.contracts.errors import require
from norn.contracts.identity import Namespace, label, stable_id

if TYPE_CHECKING:
    from norn.canonical.registry import Registry


def event_identity(namespace: Namespace, producer: str, occurrence: str) -> str:
    return stable_id("event", namespace.key, label(producer), label(occurrence, 256))


def entity_identity(
    namespace: Namespace,
    source_span_id: str,
    external_key: str | None = None,
    occurrence_ref: str | None = None,
) -> str:
    require(bool(source_span_id), "MISSING_PROVISIONAL_EVIDENCE")
    if external_key is not None:
        label(external_key, 256)
    else:
        require(occurrence_ref is not None, "MISSING_OCCURRENCE_IDENTITY")
    return stable_id(
        "entity",
        namespace.key,
        "verified" if external_key else "provisional",
        external_key or source_span_id,
        "verified" if external_key else str(occurrence_ref),
    )


def register_entity(
    registry: Registry, atom_id: str, alias: str, external_key: str | None = None
) -> str:
    label(alias)
    with registry.db.transaction() as connection:
        registry.access.check("ADMIN" if external_key else "WRITE")
        source = registry.source_for_atom(atom_id)
        span = source["id"]
        from norn.canonical.sources import SourceSpan

        text = registry.sources.resolve(
            SourceSpan(
                source["version_id"], source["start_byte"], source["end_byte"], source["digest"]
            )
        ).decode()
        require(alias in text, "UNANCHORED_ALIAS")
        entity = entity_identity(registry.access.host.namespace, span, external_key, atom_id)
        connection.execute(
            "INSERT OR IGNORE INTO objects VALUES(?,?,'entity')", (registry.ns, entity)
        )
        connection.execute(
            "INSERT OR IGNORE INTO entities VALUES(?,?,'ENTITY',?,?)",
            (registry.ns, entity, external_key, span),
        )
        alias_id = stable_id("alias", entity, span, alias)
        connection.execute(
            "INSERT OR IGNORE INTO entity_aliases VALUES(?,?,?,?,?)",
            (registry.ns, alias_id, entity, alias, span),
        )
        publish(connection, registry.ns, allocate(connection, registry.ns), "ENTITY", [entity])
    return entity


def review_identity(
    registry: Registry, left: str, right: str, decision: str, supporting_atom: str
) -> str:
    require(decision in {"SAME_AS", "DIFFERENT"} and left != right, "INVALID_IDENTITY_DECISION")
    with registry.db.transaction() as connection:
        registry.access.check("ADMIN")
        for entity in (left, right):
            registry.access.check("READ", entity)
            require(
                connection.execute(
                    "SELECT 1 FROM entities WHERE ns=? AND id=?", (registry.ns, entity)
                ).fetchone()
                is not None,
                "NOT_AUTHORIZED_OR_NOT_FOUND",
            )
        source = registry.source_for_atom(supporting_atom)
        seq = allocate(connection, registry.ns)
        identity = stable_id("identity", registry.ns, str(seq))
        connection.execute(
            "INSERT INTO identity_events VALUES(?,?,?,?,?,?,?,?)",
            (
                registry.ns,
                identity,
                left,
                right,
                decision,
                source["id"],
                registry.access.host.principal,
                seq,
            ),
        )
        publish(connection, registry.ns, seq, "IDENTITY_REVIEW", [left, right])
    return identity


def inspect_entity(registry: Registry, entity: str) -> dict[str, object]:
    registry.access.check("READ", entity)
    connection, ns = registry.db.connection, registry.ns
    row = connection.execute("SELECT * FROM entities WHERE ns=? AND id=?", (ns, entity)).fetchone()
    require(row is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
    source = connection.execute(
        "SELECT v.source_id FROM source_spans s JOIN source_versions v "
        "ON s.ns=v.ns AND s.version_id=v.id WHERE s.ns=? AND s.id=?",
        (ns, row["provisional_span_id"]),
    ).fetchone()
    require(source is not None, "STORE_INTEGRITY")
    registry.access.check("READ", source[0])
    aliases = connection.execute(
        "SELECT label FROM entity_aliases WHERE ns=? AND entity_id=?", (ns, entity)
    ).fetchall()
    decisions = connection.execute(
        "SELECT id,decision,left_id,right_id,span_id FROM identity_events "
        "WHERE ns=? AND (left_id=? OR right_id=?) ORDER BY recorded_seq",
        (ns, entity, entity),
    ).fetchall()
    for decision in decisions:
        for endpoint in (decision["left_id"], decision["right_id"]):
            registry.access.check("READ", endpoint)
        supporting = connection.execute(
            "SELECT v.source_id FROM source_spans s "
            "JOIN source_versions v ON s.ns=v.ns AND s.version_id=v.id "
            "WHERE s.ns=? AND s.id=?",
            (ns, decision["span_id"]),
        ).fetchone()
        require(supporting is not None, "STORE_INTEGRITY")
        registry.access.check("READ", supporting[0])
    registry.access.check("READ", entity)
    return {
        "entity_id": entity,
        "external_key": row["external_key"],
        "aliases": [r[0] for r in aliases],
        "review_history": [dict(r) for r in decisions],
    }
