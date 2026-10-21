"""Installed local facade over canonical owners; all reads enforce current security."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any, Self

from norn.canonical import corrections, outbox
from norn.canonical.database import SCHEMA_VERSION, Database
from norn.canonical.registry import Registry, WriteRequest
from norn.canonical.sources import SourceSpan, SourceStore, safe_path
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, label, stable_id
from norn.contracts.time import QueryClock, stamp
from norn.embedding.baseline import LocalModels
from norn.governance import deletion
from norn.governance.access import Access, HostIdentity
from norn.governance.temporal import contains
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.rerank import EvidenceTokenizer
from norn.retrieval.service import RecallView


class EvidenceView:
    """Serialization is a second current-authorization boundary, even after assembly."""

    def __init__(self, engine: Engine, objects: list[str], data: dict[str, Any]):
        self._engine = engine
        self._objects = tuple(objects)
        self._data = data

    def serialize(self) -> dict[str, Any]:
        result = json.loads(canonical(self._data))
        for object_id in self._objects:
            epoch = self._engine.access.check("READ", object_id)
        result["security_epoch"] = epoch
        return result  # type: ignore[no-any-return]


class Engine:
    def __init__(
        self,
        root: Path,
        host: HostIdentity,
        *,
        create: bool = False,
        model_root: Path | None = None,
        enable_models: bool = False,
    ):
        safe_path(root)
        self.root = root.absolute()
        self.db = Database(self.root / "canonical.sqlite3", create=create)
        try:
            self.sources = SourceStore(self.root / "blobs")
            self.access = Access(self.db, host)
            self.registry = Registry(self.db, self.sources, self.access)
            require(not enable_models or model_root is not None, "MODEL_ROOT_REQUIRED")
            self.local_models = (
                LocalModels(model_root, enabled=True) if enable_models and model_root else None
            )
            self.evidence_tokenizer = (
                EvidenceTokenizer(model_root) if model_root is not None else None
            )
        except BaseException:
            self.db.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.close_models()
        finally:
            self.db.close()

    def close_models(self) -> None:
        if self.local_models is not None:
            self.local_models.close()

    def recall(self, request: RecallRequest, *, cancelled: Event | None = None) -> RecallView:
        from norn.retrieval.service import recall

        return recall(self, request, cancelled=cancelled)

    def project(self) -> dict[str, Any]:
        from norn.projection.local import build

        return build(self, models=self.local_models)

    def write(
        self, request: WriteRequest, *, correction: corrections.CorrectionRequest | None = None
    ) -> dict[str, Any]:
        return self.registry.ingest(request, correction=correction)

    def read(self, event_id: str, clock: QueryClock) -> EvidenceView:
        event = self.registry.event_row(event_id)
        current_seq = self.db.connection.execute(
            "SELECT commit_seq FROM namespaces WHERE ns=?", (self.access.ns,)
        ).fetchone()[0]
        snapshot = current_seq if clock.snapshot is None else clock.snapshot
        require(snapshot <= current_seq, "FUTURE_SNAPSHOT")
        known = stamp(clock.knowledge_at)
        require(
            event["commit_seq"] <= snapshot and event["recorded_at"] <= known, "NOT_ESTABLISHED"
        )
        ns = self.access.ns
        version = self.db.connection.execute(
            "SELECT * FROM source_versions WHERE ns=? AND id=?", (ns, event["source_version"])
        ).fetchone()
        require(version is not None, "STORE_INTEGRITY")
        self.access.check("READ", version["source_id"])
        require(len(self.sources.read(version["id"])) == version["byte_length"], "SOURCE_INTEGRITY")
        rows = self.db.connection.execute(
            "SELECT * FROM atoms WHERE ns=? AND event_id=? ORDER BY id", (ns, event_id)
        ).fetchall()
        require(len(rows) <= 64, "ATOM_BUDGET")
        result = []
        evidence_bytes = 0
        checked = [event_id, version["source_id"]]
        valid = stamp(clock.valid_at)
        conflicts = []
        for row in rows:
            self.access.check("READ", row["id"])
            self.access.check("READ", row["subject_ref"])
            checked.extend([row["id"], row["subject_ref"]])
            if row["object_ref"] is not None:
                self.access.check("READ", row["object_ref"])
                checked.append(row["object_ref"])
            status = row["initial_status"]
            controls = self.db.connection.execute(
                "SELECT * FROM assertion_events WHERE ns=? AND atom_id=? AND recorded_seq<=? "
                "AND recorded_at<=? ORDER BY recorded_seq LIMIT 257",
                (ns, row["id"], snapshot, known),
            ).fetchall()
            require(len(controls) <= 256, "CONTROL_BUDGET")
            for control in controls:
                if contains(control["valid_from"], control["valid_to"], valid):
                    status = control["status"]
            applicable = "CURRENT" if status == "ACTIVE" else "UNKNOWN"
            edges = self.db.connection.execute(
                "SELECT r.*,e.recorded_at FROM relationships r JOIN atoms a "
                "ON r.ns=a.ns AND r.from_id=a.id JOIN events e ON a.ns=e.ns AND a.event_id=e.id "
                "WHERE r.ns=? AND (r.to_id=? OR r.from_id=?) AND r.commit_seq<=? "
                "AND e.recorded_at<=? ORDER BY r.id LIMIT 257",
                (ns, row["id"], row["id"], snapshot, known),
            ).fetchall()
            require(len(edges) <= 256, "RELATION_BUDGET")
            for edge in edges:
                # Do not expose a relation endpoint without its current source access.
                self.access.check("READ", edge["id"])
                for endpoint in (edge["from_id"], edge["to_id"]):
                    source = self.registry.source_for_atom(endpoint)
                    checked.extend([endpoint, source["source_id"]])
                checked.append(edge["id"])
                active = contains(edge["valid_from"], edge["valid_to"], valid)
                if edge["relation_type"] == "SUPERSEDES":
                    if edge["to_id"] == row["id"] and active:
                        applicable = "SUPERSEDED"
                    elif edge["from_id"] == row["id"] and not active:
                        applicable = "FUTURE" if valid < edge["valid_from"] else "HISTORICAL"
                elif edge["relation_type"] == "CONTRADICTS" and active:
                    applicable = "CONFLICT"
                    conflicts.append(edge["id"])
            citations = []
            supports = self.db.connection.execute(
                "SELECT s.*,v.source_id,x.independence_group,x.support_kind FROM atom_support x "
                "JOIN source_spans s ON x.ns=s.ns AND x.span_id=s.id JOIN source_versions v "
                "ON s.ns=v.ns AND s.version_id=v.id WHERE x.ns=? AND x.atom_id=? "
                "AND x.recorded_seq<=? AND v.recorded_at<=? ORDER BY x.id LIMIT 65",
                (ns, row["id"], snapshot, known),
            ).fetchall()
            require(0 < len(supports) <= 64, "SUPPORT_INTEGRITY_OR_BUDGET")
            for support in supports:
                evidence_bytes += support["end_byte"] - support["start_byte"]
                require(evidence_bytes <= 1_048_576, "EVIDENCE_BUDGET")
                self.access.check("READ", support["source_id"])
                checked.append(support["source_id"])
                span = SourceSpan(
                    support["version_id"],
                    support["start_byte"],
                    support["end_byte"],
                    support["digest"],
                )
                citations.append(
                    {
                        "span_id": support["id"],
                        "source_version": span.version_id,
                        "start_byte": span.start,
                        "end_byte": span.end,
                        "sha256": span.sha256,
                        "text": self.sources.resolve(span).decode(),
                        "independence_group": support["independence_group"],
                        "support_kind": support["support_kind"],
                    }
                )
            result.append(
                {
                    "atom_id": row["id"],
                    "subject_ref": row["subject_ref"],
                    "predicate": row["predicate"],
                    "value": json.loads(row["object_value"]),
                    "qualifiers": json.loads(row["qualifiers"]),
                    "origin": row["origin"],
                    "epistemic": "RETRACTED"
                    if status == "RETRACTED"
                    else row["external_epistemic"],
                    "assertion_status": status,
                    "applicability": applicable,
                    "authority": "UNVERIFIED",
                    "citations": citations,
                }
            )
        active_atoms = [
            a
            for a in result
            if a["assertion_status"] == "ACTIVE"
            and a["applicability"] == "CURRENT"
            and a["origin"] in {"DIRECT_OBSERVATION", "USER_REPORTED", "DOCUMENT_ASSERTION"}
        ]
        outcome = "CONFLICT" if conflicts else ("SUPPORTED" if active_atoms else "NOT_ESTABLISHED")
        data = {
            "namespace": ns,
            "canonical_schema": SCHEMA_VERSION,
            "extraction_revision": "fixture-v1",
            "event_id": event_id,
            "event_time": json.loads(event["event_time"]),
            "observed_at": event["observed_at"],
            "recorded_at": event["recorded_at"],
            "evaluation_time": stamp(clock.evaluation_time),
            "timezone": clock.timezone,
            "temporal_basis": clock.basis,
            "valid_at": valid,
            "knowledge_at": known,
            "snapshot": snapshot,
            "atoms": result,
            "conflicts": sorted(set(conflicts)),
            "outcome": outcome,
            "coverage": "CANONICAL_FALLBACK",
            "projection_state": "INDEX_PENDING",
            "searchable": False,
            "missing_capabilities": ["lexical", "dense", "graph"],
            "budget_used": {"atoms": len(result), "provider_calls": 0},
        }
        view = EvidenceView(self, checked, data)
        view.serialize()  # Recheck before returning the view; serialization rechecks again.
        return view

    def journal(self, after: int = 0, limit: int = 100) -> list[dict[str, object]]:
        self.access.check("ADMIN")
        result = outbox.read_page(self.db.connection, self.access.ns, after, limit)
        self.access.check("ADMIN")
        return result

    def deny(self, selector: str, request_id: str, reason: str) -> dict[str, object]:
        return deletion.deny(self.registry, selector, request_id, reason)

    def lineage(self, output: str, inputs: tuple[str, ...], revision: str) -> str:
        """Register an unvalidated derivation dependency; never promote its assertion."""
        label(revision)
        require(type(inputs) is tuple and 0 < len(inputs) <= 64 and len(set(inputs)) == len(inputs))
        ns = self.access.ns
        with self.db.transaction() as connection:
            self.access.check("WRITE")
            self.registry.source_for_atom(output)
            row = connection.execute("SELECT origin FROM atoms WHERE ns=? AND id=?", (ns, output))
            require(
                row.fetchone()[0] in {"MODEL_INFERENCE", "HYPOTHESIS", "DERIVED_AGGREGATE"},
                "INVALID_DERIVATION_ORIGIN",
            )
            for item in inputs:
                self.registry.source_for_atom(item)
            seen: set[str] = set()
            pending = [output]
            while pending:
                current = pending.pop()
                require(current not in inputs, "LINEAGE_CYCLE")
                if current in seen:
                    continue
                seen.add(current)
                require(len(seen) <= 10_000, "LINEAGE_BUDGET")
                downstream = connection.execute(
                    "SELECT d.output_id FROM derivation_inputs i JOIN derivations d "
                    "ON i.ns=d.ns AND i.derivation_id=d.id "
                    "WHERE i.ns=? AND i.input_id=? LIMIT 10001",
                    (ns, current),
                ).fetchall()
                require(len(downstream) <= 10_000, "LINEAGE_BUDGET")
                pending.extend(r[0] for r in downstream)
                require(len(pending) <= 100_000, "LINEAGE_BUDGET")
            derivation = stable_id("derivation", ns, output, canonical(inputs), revision)
            connection.execute("INSERT INTO objects VALUES(?,?,'derivation')", (ns, derivation))
            connection.execute(
                "INSERT INTO derivations VALUES(?,?,?,?,?,?,'UNVALIDATED')",
                (
                    ns,
                    derivation,
                    output,
                    revision,
                    digest(canonical(inputs).encode()),
                    stamp(datetime.now(UTC)),
                ),
            )
            for item in inputs:
                source = self.registry.source_for_atom(item)
                connection.execute(
                    "INSERT INTO derivation_inputs VALUES(?,?,?,?,?)",
                    (
                        ns,
                        derivation,
                        item,
                        source["version_id"],
                        stable_id("independence", ns, source["version_id"]),
                    ),
                )
            outbox.publish(
                connection, ns, outbox.allocate(connection, ns), "DERIVATION", [derivation]
            )
        return derivation

    def backup(self, destination: Path) -> dict[str, object]:
        safe_path(destination)
        self.access.check("ADMIN")
        require(
            self.db.connection.execute(
                "SELECT count(*) FROM namespaces WHERE ns<>?", (self.access.ns,)
            ).fetchone()[0]
            == 0,
            "MULTI_NAMESPACE_BACKUP_UNSUPPORTED",
        )
        require(not destination.exists(), "BACKUP_EXISTS")
        destination.mkdir(parents=True)
        self.db.backup(destination / "canonical.sqlite3")
        # Synthetic local pilot only. Content-addressed blobs never change after publication.
        blobs = destination / "blobs"
        blobs.mkdir()
        for path in self.sources.root.iterdir():
            if len(path.name) == 64:
                self.sources.read(path.name)
                shutil.copyfile(path, blobs / path.name)
        projection_root = self.root / "projections"
        if projection_root.exists():
            projection_store = SourceStore(projection_root)
            restored_projections = destination / "projections"
            restored_projections.mkdir()
            for path in projection_root.iterdir():
                if len(path.name) == 64:
                    projection_store.read(path.name)
                    shutil.copyfile(path, restored_projections / path.name)
        with Engine(destination, self.access.host) as restored:
            live_rows = self.db.connection.execute("SELECT * FROM outbox ORDER BY ns,commit_seq")
            backup_rows = restored.db.connection.execute(
                "SELECT * FROM outbox ORDER BY ns,commit_seq"
            )
            while True:
                live_page, backup_page = live_rows.fetchmany(1000), backup_rows.fetchmany(1000)
                require(
                    [tuple(r) for r in live_page] == [tuple(r) for r in backup_page],
                    "BACKUP_READBACK",
                )
                if not live_page:
                    break
            for version in restored.db.connection.execute(
                "SELECT id,byte_length FROM source_versions"
            ):
                require(
                    len(restored.sources.read(version["id"])) == version["byte_length"],
                    "BACKUP_READBACK",
                )
            from norn.projection.local import readback

            for manifest in restored.db.connection.execute(
                "SELECT id FROM projection_manifests WHERE ns=?", (self.access.ns,)
            ):
                # Preserve legacy immutable artifacts without treating them as serving-ready.
                readback(restored, manifest[0], current_revision=False)
        return {
            "path": str(destination),
            "verified": True,
            "scope": "local synthetic SQL/blobs/projections; deletion controls preserved",
        }
