"""Versioned SQLite store, atomic migrations, validated backups and explicit readiness."""

import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from norn.canonical.sources import safe_path
from norn.contracts.errors import NornError, require
from norn.contracts.identity import digest
from norn.contracts.time import stamp

APPLICATION_ID = 0x4E4F524E
SCHEMA_VERSION = 4
MIGRATIONS = ("schema.sql", "002_governance.sql", "003_projection.sql", "004_binding.sql")
MUTABLE_TABLES = {"namespaces", "migration_state"}


def statements(sql: str) -> Iterator[str]:
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer
            buffer = ""
    require(not buffer.strip(), "INVALID_MIGRATION")


def immutable_trigger(table: str, operation: str) -> str:
    return (
        f'CREATE TRIGGER "immutable_{table}_{operation}" '
        f'BEFORE {operation} ON "{table}" BEGIN '
        "SELECT RAISE(ABORT,'immutable canonical record'); END"
    )


class Database:
    def __init__(self, path: Path, *, create: bool = False, target: int = SCHEMA_VERSION):
        require(target in range(1, SCHEMA_VERSION + 1), "UNSUPPORTED_SCHEMA")
        safe_path(path)
        existed = path.exists()
        require(existed or create, "STORE_NOT_FOUND")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute("PRAGMA recursive_triggers=ON")
            self.connection.execute("PRAGMA synchronous=FULL")
            current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
            app = self.connection.execute("PRAGMA application_id").fetchone()[0]
            require((not existed and current == 0) or app == APPLICATION_ID, "FOREIGN_STORE")
            require(0 <= current <= target, "UNSUPPORTED_SCHEMA")
            if current:
                self._verify(current)
            if current < target:
                backup = (
                    self.backup(path.with_name(path.name + ".before-upgrade-" + uuid4().hex))
                    if current
                    else None
                )
                if current:
                    self.connection.execute("UPDATE migration_state SET dirty=1")
                with self.transaction():
                    for version in range(current + 1, target + 1):
                        raw = Path(__file__).with_name(MIGRATIONS[version - 1]).read_bytes()
                        for sql in statements(raw.decode()):
                            self.connection.execute(sql)
                        self.connection.execute(
                            "INSERT INTO schema_migrations VALUES(?,?,?,?)",
                            (
                                version,
                                digest(raw),
                                stamp(datetime.now(UTC)),
                                str(backup) if backup else None,
                            ),
                        )
                    self._immutability()
                    self.connection.execute("UPDATE migration_state SET dirty=0")
                    self.connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    self.connection.execute(f"PRAGMA user_version={target}")
            self._verify(target)
        except sqlite3.Error:
            self.connection.close()
            raise NornError("STORE_INTEGRITY", "storage") from None
        except BaseException:
            self.connection.close()
            raise

    def _verify(self, version: int) -> None:
        try:
            expected_tables = {}
            for name in MIGRATIONS[:version]:
                for sql in statements(Path(__file__).with_name(name).read_text(encoding="utf-8")):
                    match = re.match(r"\s*CREATE TABLE (\w+)", sql)
                    if match:
                        expected_tables[match[1]] = " ".join(sql.strip().rstrip(";").split())
            actual_tables = {
                row[0]: " ".join(row[1].strip().rstrip(";").split())
                for row in self.connection.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='table'"
                )
            }
            require(expected_tables == actual_tables, "SCHEMA_CATALOG_MISMATCH")
            actual_triggers = {
                r[0]: " ".join(r[1].strip().rstrip(";").split())
                for r in self.connection.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger'"
                )
            }
            required_triggers = {
                f"immutable_{table}_{operation}": " ".join(
                    immutable_trigger(table, operation).split()
                )
                for table in expected_tables
                if table not in MUTABLE_TABLES
                for operation in ("UPDATE", "DELETE")
            }
            require(actual_triggers == required_triggers, "SCHEMA_CATALOG_MISMATCH")
            require(
                self.connection.execute("SELECT dirty FROM migration_state").fetchone()[0] == 0,
                "INTERRUPTED_UPGRADE",
            )
            rows = self.connection.execute(
                "SELECT version,digest FROM schema_migrations ORDER BY version"
            )
            actual = [(r[0], r[1]) for r in rows]
            expected = [
                (i + 1, digest(Path(__file__).with_name(name).read_bytes()))
                for i, name in enumerate(MIGRATIONS[:version])
            ]
            require(actual == expected, "SCHEMA_DIGEST_MISMATCH")
            require(
                not self.connection.execute("PRAGMA foreign_key_check").fetchall(),
                "STORE_INTEGRITY",
            )
            require(
                self.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                "STORE_INTEGRITY",
            )
        except sqlite3.DatabaseError:
            raise NornError("STORE_INTEGRITY", "storage") from None

    def _immutability(self) -> None:
        tables = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        for row in tables:
            table = row[0]
            if table not in MUTABLE_TABLES:
                for operation in ("UPDATE", "DELETE"):
                    self.connection.execute(
                        immutable_trigger(table, operation).replace(
                            "CREATE TRIGGER", "CREATE TRIGGER IF NOT EXISTS", 1
                        )
                        + ";"
                    )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            self.connection.execute("COMMIT")
        except sqlite3.Error:
            self.connection.execute("ROLLBACK")
            raise NornError("CANONICAL_TRANSACTION_FAILED", "storage") from None
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    def backup(self, destination: Path) -> Path:
        safe_path(destination)
        require(not destination.exists(), "BACKUP_EXISTS")
        deadline = time.monotonic() + 5

        def progress(status: int, remaining: int, total: int) -> None:
            require(time.monotonic() <= deadline, "BACKUP_DEADLINE")

        with sqlite3.connect(destination) as backup:
            self.connection.backup(backup, pages=256, progress=progress)
            require(
                backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "BACKUP_INTEGRITY"
            )
            require(not backup.execute("PRAGMA foreign_key_check").fetchall(), "BACKUP_INTEGRITY")
        return destination

    def close(self) -> None:
        self.connection.close()
