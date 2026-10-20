import sqlite3

import pytest
from conftest import HOST, clock, request

from norn.canonical.database import Database
from norn.canonical.registry import Registry
from norn.canonical.sources import SourceStore
from norn.contracts.errors import NornError
from norn.governance.access import Access
from norn.integration.engine import Engine


def test_populated_upgrade_verified_backup_restore_and_immutable_rows(tmp_path):
    root = tmp_path / "store"
    path = root / "canonical.sqlite3"
    old = Database(path, create=True, target=1)
    access = Access(old, HOST)
    access.bootstrap()
    registry = Registry(old, SourceStore(root / "blobs"), access)
    receipt = registry.ingest(request())
    old.close()
    upgraded = Database(path)
    assert upgraded.connection.execute("PRAGMA user_version").fetchone()[0] == 2
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
        connection.execute("PRAGMA user_version=2")
        connection.execute("UPDATE migration_state SET dirty=1")
    with pytest.raises(NornError, match="INTERRUPTED_UPGRADE"):
        Database(path)


def test_actual_composite_namespace_foreign_key(engine):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        engine.db.connection.execute("INSERT INTO principals VALUES('other/w/p','owner','host')")
