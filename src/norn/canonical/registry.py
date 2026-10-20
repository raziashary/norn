"""Canonical writes: a single transaction owns event, atoms, support and journal."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from norn.canonical.database import Database
from norn.canonical.identity import entity_identity, event_identity
from norn.canonical.outbox import allocate, publish
from norn.canonical.sources import SourceStore
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, label, stable_id
from norn.contracts.time import TimeValue, aware, stamp
from norn.extraction.atoms import ExtractedAtom, FixtureAtom, extract
from norn.governance.access import POLICY, Access

if TYPE_CHECKING:
    from norn.canonical.corrections import CorrectionRequest


@dataclass(frozen=True)
class WriteRequest:
    request_id: str
    producer: str
    delivery: str
    occurrence: str
    content: bytes
    event_time: TimeValue
    observed_at: datetime
    atoms: tuple[FixtureAtom, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        for value in (self.request_id, self.producer, self.delivery, self.occurrence):
            label(value, 256)
        require(type(self.content) is bytes and 0 < len(self.content) <= 1_048_576)
        require(isinstance(self.event_time, TimeValue))
        object.__setattr__(self, "observed_at", aware(self.observed_at))
        require(type(self.atoms) is tuple and len(self.atoms) <= 64)
        require(type(self.schema_version) is int and self.schema_version == 1, "UNSUPPORTED_SCHEMA")

    def payload(self) -> str:
        return canonical(
            {
                "producer": self.producer,
                "occurrence": self.occurrence,
                "content": digest(self.content),
                "event_time": self.event_time.payload(),
                "observed_at": stamp(self.observed_at),
                "schema_version": self.schema_version,
                "atoms": [atom.payload() for atom in self.atoms],
            }
        )


class Registry:
    def __init__(self, database: Database, sources: SourceStore, access: Access):
        self.db = database
        self.sources = sources
        self.access = access
        self.ns = access.ns

    def receipt(self, event_id: str) -> dict[str, Any]:
        self.access.check("READ", event_id)
        event = self.db.connection.execute(
            "SELECT * FROM events WHERE ns=? AND id=?", (self.ns, event_id)
        ).fetchone()
        require(event is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
        atoms = self.db.connection.execute(
            "SELECT id FROM atoms WHERE ns=? AND event_id=? ORDER BY id", (self.ns, event_id)
        ).fetchall()
        return {
            "event_id": event_id,
            "atom_ids": [a[0] for a in atoms],
            "relation_ids": [
                r[0]
                for r in self.db.connection.execute(
                    "SELECT r.id FROM relationships r JOIN atoms a ON r.ns=a.ns AND r.from_id=a.id "
                    "WHERE a.ns=? AND a.event_id=? ORDER BY r.id",
                    (self.ns, event_id),
                ).fetchall()
            ],
            "commit_seq": event["commit_seq"],
            "source_version": event["source_version"],
            "durable_at": event["recorded_at"],
            "projection_state": "INDEX_PENDING",
            "searchable": False,
            "schema_version": 1,
        }

    def ingest(
        self, request: WriteRequest, *, correction: CorrectionRequest | None = None
    ) -> dict[str, Any]:
        self.access.check("WRITE")
        self.access.check("READ")
        require(request.producer == self.access.host.principal, "UNTRUSTED_PRODUCER")
        payload_digest = digest(
            canonical([request.payload(), correction.payload() if correction else None]).encode()
        )
        event_id = event_identity(self.access.host.namespace, request.producer, request.occurrence)
        version = self.sources.put(request.content)
        extracted = extract(self.sources, version, request.atoms)
        now = stamp(datetime.now(UTC))
        with self.db.transaction() as connection:
            self.access.check("WRITE")
            prior = connection.execute(
                "SELECT payload_digest,event_id FROM deliveries "
                "WHERE ns=? AND producer=? AND delivery=?",
                (self.ns, request.producer, request.delivery),
            ).fetchone()
            if prior is not None:
                require(prior["payload_digest"] == payload_digest, "IDEMPOTENCY_CONFLICT")
                event_id = prior["event_id"]
            else:
                existing = connection.execute(
                    "SELECT 1 FROM events WHERE ns=? AND id=?", (self.ns, event_id)
                ).fetchone()
                require(existing is None, "OCCURRENCE_EXISTS_USE_ADDITIONAL_EVIDENCE")
                seq = allocate(connection, self.ns)
                self._source(connection, version, request.producer, now)
                connection.execute("INSERT INTO objects VALUES(?,?,'event')", (self.ns, event_id))
                connection.execute(
                    "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,1)",
                    (
                        self.ns,
                        event_id,
                        request.producer,
                        request.occurrence,
                        version,
                        canonical(request.event_time.payload()),
                        stamp(request.observed_at),
                        now,
                        seq,
                    ),
                )
                atom_ids = []
                subject_entity = None
                if correction is not None:
                    require(len(extracted) == 1, "CORRECTION_REQUIRES_ONE_ATOM")
                    self.source_for_atom(correction.prior_atom)
                    target = connection.execute(
                        "SELECT subject_ref FROM atoms WHERE ns=? AND id=?",
                        (self.ns, correction.prior_atom),
                    ).fetchone()
                    subject_entity = target[0]
                    self.access.check("READ", subject_entity)
                    require(
                        connection.execute(
                            "SELECT 1 FROM entity_aliases WHERE ns=? AND entity_id=? AND label=?",
                            (self.ns, subject_entity, extracted[0].fixture.subject),
                        ).fetchone()
                        is not None,
                        "CORRECTION_IDENTITY_MISMATCH",
                    )
                for index, atom in enumerate(extracted):
                    atom_ids.append(
                        self._atom(connection, event_id, index, atom, seq, subject_entity)
                    )
                connection.execute(
                    "INSERT INTO deliveries VALUES(?,?,?,?,?,?)",
                    (self.ns, request.producer, request.delivery, payload_digest, event_id, now),
                )
                relation_ids = []
                if correction is not None:
                    from norn.canonical.corrections import append_relation

                    require(len(atom_ids) == 1, "CORRECTION_REQUIRES_ONE_ATOM")
                    relation_ids.append(append_relation(self, correction, atom_ids[0], seq))
                publish(connection, self.ns, seq, "INGEST", [event_id, *atom_ids, *relation_ids])
        return self.receipt(event_id)

    def _source(self, connection: sqlite3.Connection, version: str, producer: str, now: str) -> str:
        source_id = stable_id("source", self.ns, version)
        connection.execute(
            "INSERT OR IGNORE INTO objects VALUES(?,?,'source')", (self.ns, source_id)
        )
        connection.execute(
            "INSERT OR IGNORE INTO sources VALUES(?,?,?,'TEXT','UNVERIFIED',?)",
            (self.ns, source_id, producer, POLICY),
        )
        self.access.check("READ", source_id)
        connection.execute(
            "INSERT OR IGNORE INTO source_versions VALUES(?,?,?,?,?,"
            "'text/plain;charset=utf-8',?,?,?,1)",
            (
                self.ns,
                version,
                source_id,
                version,
                len(self.sources.read(version)),
                version,
                self.access.host.principal,
                now,
            ),
        )
        return source_id

    def _span(self, connection: sqlite3.Connection, atom: ExtractedAtom) -> str:
        span = atom.span
        span_id = stable_id("span", self.ns, span.version_id, str(span.start), str(span.end))
        connection.execute(
            "INSERT OR IGNORE INTO source_spans VALUES(?,?,?,?,?,?,'utf-8')",
            (self.ns, span_id, span.version_id, span.start, span.end, span.sha256),
        )
        return span_id

    def _atom(
        self,
        connection: sqlite3.Connection,
        event_id: str,
        index: int,
        extracted: ExtractedAtom,
        seq: int,
        subject_entity: str | None,
    ) -> str:
        fixture = extracted.fixture
        from norn.contracts.identity import ObjectRef

        if isinstance(fixture.value.value, ObjectRef):
            reference = fixture.value.value
            require(reference.namespace == self.access.host.namespace, "CROSS_NAMESPACE_REFERENCE")
            self.access.check("READ", reference.object_id)
            require(
                connection.execute(
                    "SELECT 1 FROM entities WHERE ns=? AND id=?", (self.ns, reference.object_id)
                ).fetchone()
                is not None,
                "NOT_AUTHORIZED_OR_NOT_FOUND",
            )
        span_id = self._span(connection, extracted)
        atom_id = stable_id("atom", self.ns, event_id, str(index), canonical(fixture.payload()))
        if subject_entity is None:
            subject_entity = entity_identity(self.access.host.namespace, span_id, None, atom_id)
            connection.execute(
                "INSERT INTO objects VALUES(?,?,'entity')", (self.ns, subject_entity)
            )
            connection.execute(
                "INSERT INTO entities VALUES(?,?,'PROVISIONAL',NULL,?)",
                (self.ns, subject_entity, span_id),
            )
        connection.execute(
            "INSERT OR IGNORE INTO entity_aliases VALUES(?,?,?,?,?)",
            (
                self.ns,
                stable_id("alias", subject_entity, span_id, fixture.subject),
                subject_entity,
                fixture.subject,
                span_id,
            ),
        )
        connection.execute("INSERT INTO objects VALUES(?,?,'atom')", (self.ns, atom_id))
        value = fixture.payload()["value"]
        connection.execute(
            "INSERT INTO atoms VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?)",
            (
                self.ns,
                atom_id,
                event_id,
                subject_entity,
                fixture.predicate,
                fixture.value.tag,
                canonical(value),
                fixture.value.value.object_id
                if isinstance(fixture.value.value, ObjectRef)
                else None,
                canonical(fixture.qualifiers),
                fixture.epistemic.origin,
                fixture.epistemic.external,
                span_id,
                "fixture-v1",
                extracted.status,
                seq,
            ),
        )
        connection.execute(
            "INSERT INTO atom_support VALUES(?,?,?,?,'PRIMARY',?,?,?)",
            (
                self.ns,
                stable_id("support", atom_id, span_id),
                atom_id,
                span_id,
                stable_id("independence", self.ns, extracted.span.version_id),
                "fixture-v1",
                seq,
            ),
        )
        return atom_id

    def event_row(self, event_id: str) -> sqlite3.Row:
        self.access.check("READ", event_id)
        row = self.db.connection.execute(
            "SELECT * FROM events WHERE ns=? AND id=?", (self.ns, event_id)
        ).fetchone()
        require(row is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
        return cast(sqlite3.Row, row)

    def source_for_atom(self, atom_id: str) -> sqlite3.Row:
        self.access.check("READ", atom_id)
        row = self.db.connection.execute(
            "SELECT s.*,v.source_id FROM atoms a JOIN source_spans s "
            "ON a.ns=s.ns AND a.source_span_id=s.id JOIN source_versions v "
            "ON s.ns=v.ns AND s.version_id=v.id WHERE a.ns=? AND a.id=?",
            (self.ns, atom_id),
        ).fetchone()
        require(row is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
        self.access.check("READ", row["source_id"])
        return cast(sqlite3.Row, row)
