"""Canonical equality/time eligibility before bounded windows and every ranking channel."""

import json
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from norn.contracts.errors import NornError, require
from norn.contracts.time import stamp
from norn.retrieval.contracts import EligibleCorpus, Hit, RecallRequest, Record

if TYPE_CHECKING:
    from norn.integration.engine import Engine


def _window(request: RecallRequest) -> tuple[list[str], list[str]]:
    clauses: list[str] = []
    values: list[str] = []
    if request.event_start:
        clauses.append(
            "(json_extract(e.event_time,'$.start')>=? OR "
            "(json_extract(e.event_time,'$.kind')='INTERVAL' AND "
            "json_extract(e.event_time,'$.end')>?))"
        )
        values.extend([stamp(request.event_start)] * 2)
    if request.event_end:
        clauses.append("json_extract(e.event_time,'$.start')<?")
        values.append(stamp(request.event_end))
    return clauses, values


def _unindexed(engine: Engine, request: RecallRequest, snapshot: int) -> bool:
    if request.atom_id is not None or request.entity_id is not None:
        return False  # Exact canonical keys cannot refer to an unextracted assertion/entity.
    clauses = [
        "e.ns=?",
        "e.commit_seq<=?",
        "e.recorded_at<=?",
        "v.recorded_at<=?",
        "NOT EXISTS (SELECT 1 FROM atoms a WHERE a.ns=e.ns AND a.event_id=e.id)",
        "NOT EXISTS (SELECT 1 FROM tombstones t WHERE t.ns=e.ns "
        "AND t.object_id IN (e.id,v.source_id))",
    ]
    values: list[str | int] = [
        engine.access.ns,
        snapshot,
        stamp(request.clock.knowledge_at),
        stamp(request.clock.knowledge_at),
    ]
    if request.event_id is not None:
        clauses.append("e.id=?")
        values.append(request.event_id)
    window, parameters = _window(request)
    clauses.extend(window)
    values.extend(parameters)
    return (
        engine.db.connection.execute(
            "SELECT 1 FROM events e JOIN source_versions v ON e.ns=v.ns AND e.source_version=v.id "
            "WHERE " + " AND ".join(clauses) + " LIMIT 1",
            values,
        ).fetchone()
        is not None
    )


def eligible(
    engine: Engine, request: RecallRequest, checkpoint: Callable[[], None] | None = None
) -> EligibleCorpus:
    epoch = engine.access.check("READ")
    connection = engine.db.connection
    ns = engine.access.ns
    current = int(
        connection.execute("SELECT commit_seq FROM namespaces WHERE ns=?", (ns,)).fetchone()[0]
    )
    snapshot = current if request.clock.snapshot is None else request.clock.snapshot
    require(snapshot <= current, "FUTURE_SNAPSHOT")
    clauses = ["a.ns=?", "a.commit_seq<=?", "e.recorded_at<=?", "v.recorded_at<=?"]
    params: list[str | int] = [
        ns,
        snapshot,
        stamp(request.clock.knowledge_at),
        stamp(request.clock.knowledge_at),
    ]
    for column, value in (
        ("e.id", request.event_id),
        ("a.id", request.atom_id),
        ("a.subject_ref", request.entity_id),
        ("x.label", request.subject),
    ):
        if value is not None:
            clauses.append(column + "=?")
            params.append(value)
    if request.predicates:
        clauses.append("a.predicate IN (" + ",".join("?" for _ in request.predicates) + ")")
        params.extend(request.predicates)
    window, parameters = _window(request)
    clauses.extend(window)
    params.extend(parameters)
    # Current denial overrides historical snapshots, before any LIMIT or ranking.
    clauses.append(
        "NOT EXISTS (SELECT 1 FROM tombstones t WHERE t.ns=a.ns AND "
        "t.object_id IN (a.id,a.event_id,a.subject_ref,a.object_ref,v.source_id))"
    )
    # Engine.read returns a whole event. Preclude any denied nested atom/support or
    # relation endpoint before LIMIT; an unreadable event must not starve others.
    clauses.append(
        "NOT EXISTS (SELECT 1 FROM atoms b LEFT JOIN atom_support bs ON "
        "b.ns=bs.ns AND b.id=bs.atom_id LEFT JOIN source_spans sp ON "
        "bs.ns=sp.ns AND bs.span_id=sp.id LEFT JOIN source_versions sv ON "
        "sp.ns=sv.ns AND sp.version_id=sv.id JOIN tombstones t ON t.ns=b.ns "
        "AND t.object_id IN (b.id,b.subject_ref,b.object_ref,sv.source_id) "
        "WHERE b.ns=a.ns AND b.event_id=a.event_id)"
    )
    clauses.append(
        "NOT EXISTS (SELECT 1 FROM atoms b JOIN relationships rel ON b.ns=rel.ns "
        "AND b.id IN (rel.from_id,rel.to_id) JOIN atoms endpoint ON "
        "endpoint.ns=rel.ns AND endpoint.id IN (rel.from_id,rel.to_id) "
        "JOIN events ee ON endpoint.ns=ee.ns AND endpoint.event_id=ee.id "
        "JOIN source_versions ev ON ee.ns=ev.ns AND ee.source_version=ev.id "
        "JOIN tombstones t ON t.ns=rel.ns AND t.object_id IN "
        "(rel.id,endpoint.id,ev.source_id) WHERE b.ns=a.ns AND b.event_id=a.event_id)"
    )
    sql = (
        "SELECT DISTINCT a.id,a.event_id FROM atoms a JOIN events e ON a.ns=e.ns "
        "AND a.event_id=e.id JOIN source_versions v ON e.ns=v.ns AND e.source_version=v.id "
        "JOIN entity_aliases x ON a.ns=x.ns AND a.subject_ref=x.entity_id WHERE "
        + " AND ".join(clauses)
        + " ORDER BY a.event_id,a.id LIMIT ?"
    )
    params.append(request.max_scan_records + 1)
    rows = connection.execute(sql, params).fetchall()
    complete = len(rows) <= request.max_scan_records
    unindexed = _unindexed(engine, request, snapshot)
    complete = complete and not unindexed
    selected = rows[: request.max_scan_records]
    views = {}
    records = []
    bytes_read = 0
    for row in selected:
        if checkpoint:
            checkpoint()
        try:
            if row["event_id"] not in views:
                views[row["event_id"]] = engine.read(
                    row["event_id"], replace(request.clock, snapshot=snapshot)
                ).serialize()
            view = views[row["event_id"]]
            atom = next(a for a in view["atoms"] if a["atom_id"] == row["id"])
            primary = next(c for c in atom["citations"] if c["support_kind"] == "PRIMARY")
            engine.access.check("READ", row["id"])
        except NornError as error:
            if error.code == "NOT_AUTHORIZED_OR_NOT_FOUND":
                complete = False
                continue
            raise
        bytes_read += len(primary["text"].encode())
        if bytes_read > 16_777_216:
            complete = False
            break
        source = engine.registry.source_for_atom(row["id"])
        aliases = tuple(
            r[0]
            for r in connection.execute(
                "SELECT label FROM entity_aliases WHERE ns=? AND entity_id=? ORDER BY label",
                (ns, atom["subject_ref"]),
            )
        )
        records.append(
            Record(
                ns,
                row["event_id"],
                row["id"],
                atom["subject_ref"],
                aliases,
                atom["predicate"],
                json.dumps(atom["value"], sort_keys=True),
                json.dumps(atom["qualifiers"], sort_keys=True),
                atom["origin"],
                atom["authority"],
                atom["assertion_status"],
                atom["applicability"],
                json.dumps(view["event_time"], sort_keys=True),
                source["source_id"],
                primary["source_version"],
                primary["start_byte"],
                primary["end_byte"],
                primary["sha256"],
                primary["text"],
                snapshot,
            )
        )
    require(engine.access.check("READ") == epoch, "QUERY_SECURITY_CHANGED")
    return EligibleCorpus(
        tuple(records),
        snapshot,
        epoch,
        complete,
        "UNINDEXED_SOURCE" if unindexed else (None if complete else "ELIGIBLE_CORPUS_BUDGET"),
    )


def lookup(corpus: EligibleCorpus, request: RecallRequest) -> tuple[Hit, ...]:
    if not (
        request.event_id
        or request.atom_id
        or request.entity_id
        or request.subject
        or request.event_start
    ):
        return ()
    return tuple(Hit(record, 1.0, "exact") for record in corpus.records[: request.candidate_limit])
