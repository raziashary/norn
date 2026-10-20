import sqlite3

import pytest

from norn.canonical.database import Database
from norn.contracts.errors import NornError


def test_missing_table_or_immutability_guard_cannot_report_ready(tmp_path):
    for damage in ("DROP TABLE authority_events", "DROP TRIGGER immutable_atoms_UPDATE"):
        path = tmp_path / ("case-" + str(len(list(tmp_path.iterdir()))) + ".sqlite3")
        db = Database(path, create=True)
        db.close()
        with sqlite3.connect(path) as connection:
            connection.execute(damage)
        with pytest.raises(NornError, match="SCHEMA_CATALOG_MISMATCH"):
            Database(path)


def test_corrupt_database_refuses_and_releases_handle(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not a SQLite database" * 100)
    with pytest.raises(NornError, match="STORE_INTEGRITY"):
        Database(path)
    # Windows refuses renaming a file with an outstanding SQLite handle.
    path.rename(tmp_path / "released.sqlite3")


def test_same_name_weakened_trigger_body_refuses_before_serving(tmp_path):
    path = tmp_path / "tampered.sqlite3"
    Database(path, create=True).close()
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER immutable_atoms_UPDATE")
        connection.execute(
            "CREATE TRIGGER immutable_atoms_UPDATE BEFORE UPDATE ON atoms BEGIN SELECT 1; END"
        )
    with pytest.raises(NornError, match="SCHEMA_CATALOG_MISMATCH"):
        Database(path)
