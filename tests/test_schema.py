import sqlite3

import pytest
from conftest import HOST, clock, legacy_writer, request

from norn.canonical.database import SCHEMA_VERSION, Database
from norn.canonical.registry import Registry
from norn.canonical.sources import SourceStore
from norn.contracts.errors import NornError
from norn.governance.access import Access
from norn.integration.engine import Engine


def test_populated_upgrade_verified_backup_restore_and_immutable_rows(tmp_path):
    root = tmp_path / "store"
    path = root / "canonical.sqlite3"
    old = legacy_writer(Database(path, create=True, target=1))
    access = Access(old, HOST)
    access.bootstrap()
    registry = Registry(old, SourceStore(root / "blobs"), access)
    receipt = registry.ingest(request())
    old.close()
    upgraded = Database(path)
    assert upgraded.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert upgraded.connection.execute("SELECT id FROM events").fetchone()[0] == receipt["event_id"]
    backup = upgraded.connection.execute("SELECT backup_ref FROM schema_migrations WHERE version=2")
    backup_path = backup.fetchone()[0]
    with sqlite3.connect(backup_path) as restored:
        assert restored.execute("PRAGMA user_version").fetchone()[0] == 1
        assert restored.execute("SELECT id FROM events").fetchone()[0] == receipt["event_id"]
        assert restored.execute("SELECT count(*) FROM atoms").fetchone()[0] == 1
        assert restored.execute("SELECT count(*) FROM outbox").fetchone()[0] == 2
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        upgraded.connection.execute("UPDATE principals SET id='replacement'")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        upgraded.connection.execute(
            "INSERT OR REPLACE INTO principals VALUES(?,?,?)",
            (HOST.namespace.key, HOST.principal, "replacement"),
        )
    upgraded.close()
    with Engine(root, HOST) as reader:
        assert (
            reader.read(receipt["event_id"], clock()).serialize()["atoms"][0]["value"]["value"]
            == "ZoneA"
        )


def test_foreign_future_and_interrupted_store_refused(tmp_path):
    foreign = tmp_path / "foreign.sqlite3"
    sqlite3.connect(foreign).close()
    with pytest.raises(NornError, match="FOREIGN_STORE"):
        Database(foreign)
    path = tmp_path / "canonical.sqlite3"
    db = Database(path, create=True)
    db.connection.execute("PRAGMA user_version=999")
    db.close()
    with pytest.raises(NornError, match="UNSUPPORTED_SCHEMA"):
        Database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        connection.execute("UPDATE migration_state SET dirty=1")
    with pytest.raises(NornError, match="INTERRUPTED_UPGRADE"):
        Database(path)


def test_actual_composite_namespace_foreign_key(engine):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        engine.db.connection.execute("INSERT INTO principals VALUES('other/w/p','owner','host')")


def seeded_v4_store(tmp_path):
    """A populated schema-4 store with primary and additional-evidence supports."""

    from conftest import TUESDAY

    from norn.canonical.corrections import CorrectionRequest

    root = tmp_path / "v4"
    old = legacy_writer(Database(root / "canonical.sqlite3", create=True, target=4))
    access = Access(old, HOST)
    access.bootstrap()
    registry = Registry(old, SourceStore(root / "blobs"), access)
    first = registry.ingest(request())
    extra = registry.ingest(
        request("extra"),
        correction=CorrectionRequest(
            first["atom_ids"][0], "ADDITIONAL_EVIDENCE", "parking", TUESDAY, None, "corroboration"
        ),
    )
    old.close()
    return root, first, extra


def test_migration_005_backfills_support_times_with_verified_backup_and_indexes(tmp_path):
    root, first, extra = seeded_v4_store(tmp_path)
    with Engine(root, HOST) as upgraded:
        connection = upgraded.db.connection
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        backup_ref = connection.execute(
            "SELECT backup_ref FROM schema_migrations WHERE version=5"
        ).fetchone()[0]
        with sqlite3.connect(backup_ref) as before:
            assert before.execute("PRAGMA user_version").fetchone()[0] == 4
            assert before.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert before.execute("SELECT count(*) FROM atom_support").fetchone()[0] == 3
            tables = {r[0] for r in before.execute("SELECT name FROM sqlite_master")}
            assert "atom_support_times" not in tables
        # Each backfilled time is the recording instant of the event that created the support.
        rows = connection.execute(
            "SELECT x.support_kind,t.recorded_at,e.recorded_at AS event_at FROM atom_support x "
            "JOIN atom_support_times t ON t.ns=x.ns AND t.support_id=x.id "
            "JOIN events e ON e.ns=x.ns AND e.commit_seq=x.recorded_seq ORDER BY x.recorded_seq"
        ).fetchall()
        assert [r["support_kind"] for r in rows] == ["PRIMARY", "PRIMARY", "ADDITIONAL"]
        assert all(r["recorded_at"] == r["event_at"] for r in rows)
        assert (
            connection.execute("SELECT count(*) FROM atom_support_times").fetchone()[0]
            == connection.execute("SELECT count(*) FROM atom_support").fetchone()[0]
        )
        plan = " ".join(
            r[3]
            for r in connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM atoms WHERE ns=? AND event_id=?",
                (upgraded.access.ns, first["event_id"]),
            )
        )
        assert "atoms_by_event" in plan
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE atom_support_times SET recorded_at='x'")
        atoms = upgraded.read(first["event_id"], clock()).serialize()["atoms"]
        assert len(atoms[0]["citations"]) == 2


def test_failed_005_upgrade_leaves_the_v4_store_intact_and_retryable(tmp_path, monkeypatch):
    root, first, _extra = seeded_v4_store(tmp_path)
    path = root / "canonical.sqlite3"

    def injected(self):
        raise sqlite3.OperationalError("injected failure after the 005 statements ran")

    with monkeypatch.context() as patch:
        patch.setattr(Database, "_immutability", injected)
        with pytest.raises(NornError, match="CANONICAL_TRANSACTION_FAILED"):
            Database(path)
    with sqlite3.connect(path, isolation_level=None) as raw:
        assert raw.execute("PRAGMA user_version").fetchone()[0] == 4
        assert raw.execute("SELECT dirty FROM migration_state").fetchone()[0] == 0
        assert raw.execute("SELECT count(*) FROM atom_support").fetchone()[0] == 3
        names = {r[0] for r in raw.execute("SELECT name FROM sqlite_master")}
        assert "atom_support_times" not in names and "atoms_by_event" not in names
    with Engine(root, HOST) as retried:
        assert retried.read(first["event_id"], clock()).serialize()["atoms"]
    # A stray object with a 005 name is refused before any migration work starts.
    other, _f, _e = seeded_v4_store(tmp_path / "other")
    with sqlite3.connect(other / "canonical.sqlite3", isolation_level=None) as raw:
        raw.execute("CREATE INDEX atoms_by_event ON atoms(ns,event_id)")
    with pytest.raises(NornError, match="SCHEMA_CATALOG_MISMATCH"):
        Database(other / "canonical.sqlite3")


def test_a_missing_or_altered_index_is_a_catalog_mismatch(engine):
    engine.db.connection.execute("DROP INDEX atoms_by_event")
    engine.close()
    with pytest.raises(NornError, match="SCHEMA_CATALOG_MISMATCH"):
        Database(engine.db.path)


def test_failed_backup_leaves_no_partial_file_and_can_be_retried(engine, tmp_path, monkeypatch):
    import norn.canonical.database as database_module

    target = tmp_path / "backup.sqlite3"
    ticks = iter([0.0] + [100.0] * 100)
    with monkeypatch.context() as patch:
        patch.setattr(database_module.time, "monotonic", lambda: next(ticks))
        with pytest.raises(NornError, match="BACKUP_DEADLINE"):
            engine.db.backup(target)
    assert not target.exists()
    assert engine.db.backup(target) == target
    with sqlite3.connect(target) as copy:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
