import json
import sqlite3
from pathlib import Path

import pytest
from conftest import HOST, clock, request

from norn.canonical.database import Database
from norn.canonical.registry import Registry
from norn.canonical.sources import SourceStore
from norn.contracts.errors import NornError
from norn.governance.access import Access
from norn.integration.engine import Engine
from norn.retrieval.contracts import RecallRequest

MODELS = Path(".norn/models").absolute()


def test_interrupted_publication_replays_and_legacy_backup_is_integrity_only(tmp_path, monkeypatch):
    from norn.canonical.snapshots import entries_digest
    from norn.contracts.identity import canonical, digest
    from norn.projection import binding
    from norn.projection.local import artifacts

    root = tmp_path / "replay"
    with Engine(root, HOST, create=True, model_root=MODELS, enable_models=True) as engine:
        engine.access.bootstrap()
        engine.write(request())
        original = binding.readback
        with monkeypatch.context() as patch:

            def interrupted(*args, **kwargs):
                raise NornError("INTERRUPTED_BEFORE_READY")

            patch.setattr(binding, "readback", interrupted)
            with pytest.raises(NornError, match="INTERRUPTED_BEFORE_READY"):
                engine.project_binding("B0")
        assert (
            engine.db.connection.execute("SELECT count(*) FROM binding_manifests").fetchone()[0]
            == 1
        )
        assert engine.db.connection.execute("SELECT count(*) FROM binding_ready").fetchone()[0] == 0
        query = RecallRequest("Alex parked ZoneA", clock(), requested_fields=("parked_in",))
        assert (
            engine.recall_binding(query, "B0").serialize()["reason"]
            == "BINDING_PROJECTION_NOT_READY"
        )
        built = engine.project_binding("B0")
        assert engine.recall_binding(query, "B0").serialize()["status"] == "SUPPORTED"
        manifest, payloads = original(engine, built["snapshot_id"])
        entries = [
            list(r)
            for r in engine.db.connection.execute(
                "SELECT record_key,atom_id,event_id,source_version,start_byte,end_byte,"
                "span_digest,artifact_digest "
                "FROM binding_entries WHERE manifest_id=?",
                (built["snapshot_id"],),
            )
        ]
        payload = next(iter(payloads.values()))
        payload["revision"] = "legacy-geometric-method"
        payload["vector"] = [0.0]
        entries[0][-1] = artifacts(engine).put(canonical(payload).encode())
        legacy_ck = artifacts(engine).put(canonical({"method": "legacy-checkpoint"}).encode())
        values = list(manifest.values())
        values[1], values[5], values[6], values[8] = (
            "legacy-generation",
            payload["revision"],
            legacy_ck,
            entries_digest(entries),
        )
        with engine.db.transaction() as connection:
            connection.execute(
                "INSERT INTO binding_manifests VALUES(?,?,?,?,?,?,?,?,?,?,?)", values
            )
            connection.execute(
                "INSERT INTO binding_entries VALUES(?,?,?,?,?,?,?,?,?,?)",
                (engine.access.ns, "legacy-generation", *entries[0]),
            )
        with pytest.raises(NornError, match="BINDING_REVISION_MISMATCH"):
            original(engine, "legacy-generation")
        assert (
            original(engine, "legacy-generation", current_revision=False)[0]["checkpoint_digest"]
            == legacy_ck
        )
        assert engine.backup(tmp_path / "legacy-backup")["verified"]
        path = engine.root / "projections" / entries[0][-1]
        path.write_bytes(json.dumps({"poison": True}).encode())
        assert digest(path.read_bytes()) != entries[0][-1]
        with pytest.raises(NornError, match="SOURCE_INTEGRITY"):
            original(engine, "legacy-generation", current_revision=False)
    with Engine(tmp_path / "legacy-backup", HOST) as restored:
        assert (
            original(restored, "legacy-generation", current_revision=False)[0]["revision"]
            == "legacy-geometric-method"
        )


def test_populated_schema3_upgrade_preserves_source_and_restorable_backup(tmp_path):
    root = tmp_path / "upgrade"
    old = Database(root / "canonical.sqlite3", create=True, target=3)
    access = Access(old, HOST)
    access.bootstrap()
    receipt = Registry(old, SourceStore(root / "blobs"), access).ingest(request())
    old.close()
    with Engine(root, HOST) as upgraded:
        row = upgraded.db.connection.execute(
            "SELECT backup_ref FROM schema_migrations WHERE version=4"
        )
        with sqlite3.connect(row.fetchone()[0]) as backup:
            assert backup.execute("PRAGMA user_version").fetchone()[0] == 3
            assert backup.execute("SELECT id FROM events").fetchone()[0] == receipt["event_id"]
            assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            upgraded.read(receipt["event_id"], clock()).serialize()["atoms"][0]["value"]["value"]
            == "ZoneA"
        )


def test_real_binding_project_reopen_source_current_denial_and_backup(tmp_path):
    root = tmp_path / "binding"
    with Engine(root, HOST, create=True, model_root=MODELS, enable_models=True) as engine:
        engine.access.bootstrap()
        receipt = engine.write(request())
        query = RecallRequest("Alex parked ZoneA", clock(), requested_fields=("parked_in",))
        assert (
            engine.recall_binding(query, "B0").serialize()["reason"]
            == "BINDING_PROJECTION_NOT_READY"
        )
        first = engine.project_binding("B0")
        assert engine.project_binding("B0")["snapshot_id"] == first["snapshot_id"]
        backup = tmp_path / "backup"
        assert engine.backup(backup)["verified"]
    with Engine(root, HOST, model_root=MODELS, enable_models=True) as engine:
        for variant in ("B0", "B1", "B2"):
            if variant != "B0":
                engine.project_binding(variant)
            result = engine.recall_binding(query, variant).serialize()
            assert result["status"] == "SUPPORTED"
            assert result["evidence"][0]["text"] == "Alex parked in ZoneA."
            assert result["authorizes_action"] is False
        held = engine.recall_binding(query, "B0")
        engine.deny(receipt["event_id"], "deny-binding", "test")
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            held.serialize()
        assert (
            engine.recall_binding(query, "B0").serialize()["reason"]
            == "BINDING_PROJECTION_NOT_READY"
        )
        obligations = engine.db.connection.execute(
            "SELECT artifact FROM purge_obligations"
        ).fetchall()
        assert "binding_artifacts" in {r[0] for r in obligations}
        engine.project_binding("B0")
        denied = engine.recall_binding(query, "B0").serialize()
        assert not denied["evidence"] and "ZoneA" not in str(denied)
    with Engine(backup, HOST, model_root=MODELS, enable_models=True) as restored:
        assert restored.recall_binding(query, "B0").serialize()["status"] == "SUPPORTED"


def test_public_binding_owns_native_cancellation_and_deadline(tmp_path, monkeypatch):
    import multiprocessing
    from dataclasses import replace
    from threading import Event, Timer

    with Engine(
        tmp_path / "native", HOST, create=True, model_root=MODELS, enable_models=True
    ) as engine:
        engine.access.bootstrap()
        engine.write(request())
        engine.project_binding("B0")
        models = engine.local_models
        worker = models.worker
        pid = worker.process.pid
        original = worker.call
        stop = Event()
        timer = Timer(0.03, stop.set)

        def observed_call(*args, **kwargs):
            timer.start()
            return original(*args, **kwargs)

        query = RecallRequest("parking " * 1200, clock(), deadline_ms=120000)
        try:
            with monkeypatch.context() as patch:
                patch.setattr(worker, "call", observed_call)
                failed = engine.recall_binding(query, "B0", cancelled=stop).serialize()
            assert failed["reason"] == "QUERY_CANCELLED" and not failed["evidence"]
            assert failed["trace"]["usage"]["model_calls"] == 1
            assert models.worker is None and pid not in {
                p.pid for p in multiprocessing.active_children()
            }
        finally:
            timer.cancel()
            if timer.ident is not None:
                timer.join(1)
        failed = engine.recall_binding(replace(query, deadline_ms=50), "B0").serialize()
        assert failed["reason"] == "QUERY_DEADLINE" and not failed["evidence"]
        assert models.worker is None
        assert (
            engine.recall_binding(
                RecallRequest("Alex", clock(), requested_fields=("parked_in",), deadline_ms=120000),
                "B0",
            ).serialize()["status"]
            == "SUPPORTED"
        )


def test_denial_enumerates_copied_checkpoint_and_preserves_shared_reference(tmp_path):
    from test_binding import batch

    from norn.embedding.binding import BindingModel
    from norn.embedding.checkpoint import save
    from norn.embedding.training import train
    from norn.projection.local import artifacts

    model = BindingModel("B3")
    receipt = train(model, (batch(),), seed=11, updates=2)
    checkpoint = tmp_path / "checkpoint.json"
    saved = save(checkpoint, model, receipt, "0" * 64)
    with Engine(
        tmp_path / "shared", HOST, create=True, model_root=MODELS, enable_models=True
    ) as engine:
        engine.access.bootstrap()
        first = engine.write(request())
        other = engine.write(request("other", place="ZoneB"))
        engine.project_binding("B3", checkpoint)
        affected = {
            r[0]
            for r in engine.db.connection.execute(
                "SELECT artifact_digest FROM binding_entries WHERE event_id=?", (first["event_id"],)
            )
        }
        denied = engine.deny(first["event_id"], "deny-shared", "synthetic-control")
        selectors = {
            r["selector"] for r in denied["obligations"] if r["artifact"] == "binding_artifacts"
        }
        assert affected | {saved.sha256} <= selectors
        assert all(r["status"] == "PENDING" for r in denied["obligations"])
        assert denied["physical_purge_complete"] is False
        engine.project_binding("B3", checkpoint)
        query = RecallRequest(
            "ZoneB", clock(), event_id=other["event_id"], requested_fields=("parked_in",)
        )
        packet = engine.recall_binding(query, "B3", checkpoint).serialize()
        assert (
            packet["status"] == "SUPPORTED"
            and packet["evidence"][0]["text"] == "Alex parked in ZoneB."
        )
        assert artifacts(engine).read(saved.sha256) == checkpoint.read_bytes()
        assert (
            engine.db.connection.execute(
                "SELECT count(*) FROM binding_manifests WHERE checkpoint_digest=?", (saved.sha256,)
            ).fetchone()[0]
            == 2
        )
