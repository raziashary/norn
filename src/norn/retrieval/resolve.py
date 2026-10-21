"""Ranked payloads never supply truth: reload current canonical evidence and exact bytes."""

import json
from dataclasses import replace
from typing import TYPE_CHECKING

from norn.contracts.errors import NornError, require
from norn.retrieval.contracts import Hit, RecallRequest, Record

if TYPE_CHECKING:
    from norn.integration.engine import Engine


def resolve(engine: Engine, hit: Hit, request: RecallRequest, snapshot: int, epoch: int) -> Record:
    record = hit.record
    require(
        record.namespace == engine.access.ns and record.snapshot == snapshot,
        "CANDIDATE_SNAPSHOT_MISMATCH",
    )
    require(engine.access.check("READ", record.atom_id) == epoch, "QUERY_SECURITY_CHANGED")
    view = engine.read(record.event_id, replace(request.clock, snapshot=snapshot)).serialize()
    atom = next((a for a in view["atoms"] if a["atom_id"] == record.atom_id), None)
    if atom is None:
        raise NornError("CANDIDATE_IDENTITY_MISMATCH")
    primary = next(c for c in atom["citations"] if c["support_kind"] == "PRIMARY")
    source = engine.registry.source_for_atom(record.atom_id)
    aliases = tuple(
        r[0]
        for r in engine.db.connection.execute(
            "SELECT label FROM entity_aliases WHERE ns=? AND entity_id=? ORDER BY label",
            (engine.access.ns, atom["subject_ref"]),
        )
    )
    require(
        record.aliases == aliases and json.loads(record.event_time) == view["event_time"],
        "CANDIDATE_SOURCE_MISMATCH",
    )
    require(
        (
            record.source_id,
            record.source_version,
            record.start_byte,
            record.end_byte,
            record.sha256,
            record.text,
            record.subject_id,
            record.predicate,
            record.origin,
            record.authority,
            record.status,
            record.applicability,
            json.loads(record.value_json),
            json.loads(record.qualifiers_json),
        )
        == (
            source["source_id"],
            primary["source_version"],
            primary["start_byte"],
            primary["end_byte"],
            primary["sha256"],
            primary["text"],
            atom["subject_ref"],
            atom["predicate"],
            atom["origin"],
            atom["authority"],
            atom["assertion_status"],
            atom["applicability"],
            atom["value"],
            atom["qualifiers"],
        ),
        "CANDIDATE_SOURCE_MISMATCH",
    )
    require(engine.access.check("READ") == epoch, "QUERY_SECURITY_CHANGED")
    return record
