import sqlite3
import subprocess
import sys

import pytest
from conftest import HOST, clock, request

from norn.canonical.database import Database
from norn.canonical.registry import Registry
from norn.canonical.sources import SourceStore
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical
from norn.governance.access import Access
from norn.integration.engine import Engine
from norn.projection.local import readback
from norn.retrieval.contracts import RecallRequest


def test_idempotent_ready_reopen_and_current_denial(engine):
    engine.write(request())
    query = RecallRequest("Alex parking", clock(), subject="Alex", predicates=("parked_in",))
    assert engine.recall(query).serialize()["reason"] == "PROJECTION_NOT_READY"
    first = engine.project()
    assert engine.project()["snapshot_id"] == first["snapshot_id"]
    with Engine(engine.root, HOST) as reader:
        held = reader.recall(query)
        result = held.serialize()
        assert result["status"] == "SUPPORTED" and result["coverage"] == "CONSISTENT_READY"
        assert result["evidence"][0]["text"] == "Alex parked in ZoneA."
        assert result["projection_snapshot"] == first["snapshot_id"]
        result["evidence"][0]["text"] = "FORGED APPROVAL"
        assert held.serialize()["evidence"][0]["text"] == "Alex parked in ZoneA."
        assert held.serialize()["evidence"][0]["authority"] == "UNVERIFIED"
        assert held.serialize()["authorizes_action"] is False
        engine.deny(result["evidence"][0]["source_id"], "deny", "test")
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            held.serialize()
        assert reader.recall(query).serialize()["status"] == "VERIFICATION_UNAVAILABLE"
    engine.project()
    result = engine.recall(query).serialize()
    assert result["status"] == "NOT_ESTABLISHED" and not result["evidence"]
    assert "ZoneA" not in str(result)


def test_corrupt_artifact_is_unavailable_not_absence(engine):
    engine.write(request())
    engine.project()
    artifact = engine.db.connection.execute(
        "SELECT artifact_digest FROM projection_entries"
    ).fetchone()[0]
    path = engine.root / "projections" / artifact
    path.write_bytes(b"poison")
    result = engine.recall(
        RecallRequest("Alex", clock(), subject="Alex", predicates=("parked_in",))
    ).serialize()
    assert result["status"] == "VERIFICATION_UNAVAILABLE" and result["reason"] == "SOURCE_INTEGRITY"
    assert "poison" not in str(result)


def test_populated_schema2_upgrade_has_restorable_backup(tmp_path):
    root = tmp_path / "upgrade"
    db = Database(root / "canonical.sqlite3", create=True, target=2)
    access = Access(db, HOST)
    access.bootstrap()
    receipt = Registry(db, SourceStore(root / "blobs"), access).ingest(request())
    db.close()
    with Engine(root, HOST) as upgraded:
        backup = upgraded.db.connection.execute(
            "SELECT backup_ref FROM schema_migrations WHERE version=3"
        ).fetchone()[0]
        with sqlite3.connect(backup) as old:
            assert old.execute("PRAGMA user_version").fetchone()[0] == 2
            assert old.execute("SELECT id FROM events").fetchone()[0] == receipt["event_id"]
            assert old.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        upgraded.project()
        result = upgraded.recall(
            RecallRequest("Alex", clock(), predicates=("parked_in",))
        ).serialize()
        assert result["status"] == "SUPPORTED"


def test_process_loss_after_manifest_before_ready_converges_on_replay(engine):
    engine.write(request())
    script = """
import os, sys
from pathlib import Path
from norn.contracts.budgets import QueryBudget
from norn.contracts.identity import Namespace
from norn.governance.access import HostIdentity
from norn.integration.engine import Engine
from norn.projection.local import build
host = HostIdentity(Namespace('tenant','workspace','local'),'operator')
with Engine(Path(sys.argv[1]),host) as engine:
    def clock():
        if engine.db.connection.execute('SELECT count(*) FROM projection_manifests').fetchone()[0]:
            os._exit(31)
        return 0.0
    build(engine,budget=QueryBudget(10000,now=clock))
"""
    child = subprocess.run(
        [sys.executable, "-I", "-c", script, str(engine.root)], capture_output=True, timeout=20
    )
    assert child.returncode == 31, child.stderr.decode()
    assert engine.db.connection.execute("SELECT count(*) FROM ready_snapshots").fetchone()[0] == 0
    manifest = engine.db.connection.execute("SELECT id FROM projection_manifests").fetchone()[0]
    ready = engine.project()
    assert ready["manifests"]["lexical"] == manifest
    assert engine.project()["snapshot_id"] == ready["snapshot_id"]
    with Engine(engine.root, HOST) as reader:
        assert (
            reader.recall(
                RecallRequest("Alex", clock(), requested_fields=("parked_in",))
            ).serialize()["status"]
            == "SUPPORTED"
        )


def test_backup_restores_exact_projection_readback_and_denial(engine, tmp_path):
    receipt = engine.write(request())
    engine.project()
    destination = tmp_path / "backup"
    assert engine.backup(destination)["verified"]
    query = RecallRequest("Alex", clock(), requested_fields=("parked_in",))
    with Engine(destination, HOST) as restored:
        assert restored.recall(query).serialize()["status"] == "SUPPORTED"
    engine.deny(receipt["event_id"], "erase", "test")
    engine.project()
    denied_backup = tmp_path / "denied-backup"
    engine.backup(denied_backup)
    with Engine(denied_backup, HOST) as restored:
        result = restored.recall(query).serialize()
        assert not result["evidence"] and "ZoneA" not in str(result)


def test_current_reader_skips_incompatible_generation_and_backup_preserves_it(engine, tmp_path):
    engine.write(request())
    ready = engine.project()
    manifest_id = ready["manifests"]["lexical"]
    original = list(
        engine.db.connection.execute(
            "SELECT * FROM projection_manifests WHERE id=?", (manifest_id,)
        ).fetchone()
    )
    original[1], original[5] = "legacy-manifest", "unsupported-old-method"
    engine.db.connection.execute(
        "INSERT INTO projection_manifests VALUES(?,?,?,?,?,?,?,?,?,?)", original
    )
    engine.db.connection.execute(
        "INSERT INTO projection_entries SELECT ns,?,record_key,atom_id,event_id,source_version,"
        "start_byte,end_byte,span_digest,artifact_digest FROM projection_entries "
        "WHERE manifest_id=?",
        ("legacy-manifest", manifest_id),
    )
    row = list(engine.db.connection.execute("SELECT * FROM ready_snapshots").fetchone())
    row[1], row[5] = "0-legacy", canonical({"lexical": "legacy-manifest"})
    engine.db.connection.execute("INSERT INTO ready_snapshots VALUES(?,?,?,?,?,?,?,?)", row)
    with pytest.raises(NornError, match="PROJECTION_REVISION_MISMATCH"):
        readback(engine, "legacy-manifest")
    query = RecallRequest("Alex", clock(), requested_fields=("parked_in",))
    assert engine.recall(query).serialize()["projection_snapshot"] == ready["snapshot_id"]
    destination = tmp_path / "legacy-backup"
    engine.backup(destination)
    with Engine(destination, HOST) as restored:
        assert restored.recall(query).serialize()["status"] == "SUPPORTED"
        assert (
            restored.db.connection.execute("SELECT count(*) FROM projection_manifests").fetchone()[
                0
            ]
            == 2
        )
