import shutil
import sqlite3
from pathlib import Path

import pytest
from conftest import HOST, clock, request

from norn.canonical.database import MIGRATIONS, SCHEMA_VERSION, Database, statements
from norn.canonical.registry import Registry
from norn.canonical.sources import SourceStore
from norn.contracts.errors import NornError
from norn.governance.access import Access
from norn.integration.engine import Engine

GRAPH_TABLES = {
    "relation_types",
    "object_scopes",
    "graph_edges",
    "graph_edge_support",
    "graph_manifests",
}


def seeded_v5_store(tmp_path: Path):
    """A populated schema-5 store with one event, one atom and one correction edge."""
    from conftest import TUESDAY

    from norn.canonical.corrections import CorrectionRequest

    root = tmp_path / "v5"
    old = Database(root / "canonical.sqlite3", create=True, target=5)
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


def names(connection: sqlite3.Connection) -> set[str]:
    return {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}


def test_the_catalog_is_version_six_and_a_fresh_store_has_every_graph_table(tmp_path):
    assert SCHEMA_VERSION == 6 and MIGRATIONS[-1] == "006_graph.sql"
    path = tmp_path / "fresh" / "canonical.sqlite3"
    Database(path, create=True).close()
    reopened = Database(path)  # a second open re-verifies catalog, digests and triggers
    try:
        connection = reopened.connection
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        assert GRAPH_TABLES <= names(connection)
        assert connection.execute("SELECT count(*) FROM relation_types").fetchone()[0] == 13
        causal = connection.execute(
            "SELECT causal FROM relation_types WHERE name='HYPOTHESIZES_CAUSE'"
        ).fetchone()[0]
        assert causal == 0
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE relation_types SET causal=1")
    finally:
        reopened.close()


def test_a_populated_v5_store_upgrades_after_a_verified_backup_and_keeps_its_rows(tmp_path):
    root, first, extra = seeded_v5_store(tmp_path)
    with Engine(root, HOST) as upgraded:
        connection = upgraded.db.connection
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        backup_ref = connection.execute(
            "SELECT backup_ref FROM schema_migrations WHERE version=6"
        ).fetchone()[0]
        with sqlite3.connect(backup_ref) as before:
            assert before.execute("PRAGMA user_version").fetchone()[0] == 5
            assert before.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert not GRAPH_TABLES & names(before)
            assert before.execute("SELECT count(*) FROM relationships").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM relationships").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM graph_edges").fetchone()[0] == 0
        atoms = upgraded.read(first["event_id"], clock()).serialize()["atoms"]
        assert atoms and len(atoms[0]["citations"]) == 2


def test_a_failed_upgrade_leaves_the_v5_store_intact_and_retryable(tmp_path, monkeypatch):
    root, first, _extra = seeded_v5_store(tmp_path)
    path = root / "canonical.sqlite3"

    def injected(self):
        raise sqlite3.OperationalError("injected failure after the 006 statements ran")

    with monkeypatch.context() as patch:
        patch.setattr(Database, "_immutability", injected)
        with pytest.raises(NornError, match="CANONICAL_TRANSACTION_FAILED"):
            Database(path)
    with sqlite3.connect(path, isolation_level=None) as raw:
        assert raw.execute("PRAGMA user_version").fetchone()[0] == 5
        assert raw.execute("SELECT dirty FROM migration_state").fetchone()[0] == 0
        assert not GRAPH_TABLES & names(raw)
    with Engine(root, HOST) as retried:
        assert retried.read(first["event_id"], clock()).serialize()["atoms"]
    other, _f, _e = seeded_v5_store(tmp_path / "other")
    with sqlite3.connect(other / "canonical.sqlite3", isolation_level=None) as raw:
        raw.execute("CREATE TABLE graph_edges (stray TEXT)")
    with pytest.raises(NornError, match="SCHEMA_CATALOG_MISMATCH"):
        Database(other / "canonical.sqlite3")


def test_the_upgrade_refuses_to_run_when_the_backup_cannot_be_verified(tmp_path, monkeypatch):
    root, _first, _extra = seeded_v5_store(tmp_path)
    path = root / "canonical.sqlite3"

    def refused(self, destination):
        raise NornError("BACKUP_INTEGRITY", "storage")

    with monkeypatch.context() as patch:
        patch.setattr(Database, "backup", refused)
        with pytest.raises(NornError, match="BACKUP_INTEGRITY"):
            Database(path)
    with sqlite3.connect(path, isolation_level=None) as raw:
        assert raw.execute("PRAGMA user_version").fetchone()[0] == 5
        assert raw.execute("SELECT dirty FROM migration_state").fetchone()[0] == 0
        assert not GRAPH_TABLES & names(raw)


def test_a_restored_backup_is_a_working_v5_store_that_upgrades_again(tmp_path):
    root, first, _extra = seeded_v5_store(tmp_path)
    with Engine(root, HOST) as upgraded:
        backup_ref = upgraded.db.connection.execute(
            "SELECT backup_ref FROM schema_migrations WHERE version=6"
        ).fetchone()[0]
    restored = tmp_path / "restored"
    (restored).mkdir()
    shutil.copy(backup_ref, restored / "canonical.sqlite3")
    shutil.copytree(root / "blobs", restored / "blobs")
    with Engine(restored, HOST) as again:
        assert again.db.connection.execute("PRAGMA user_version").fetchone()[0] == 6
        assert again.read(first["event_id"], clock()).serialize()["atoms"]


def _edge(connection, edge_id, **overrides):
    """Insert a graph edge between the first two entities (or a stated kind) of a v6 store."""
    row = connection.execute("SELECT ns,id FROM source_spans LIMIT 1").fetchone()
    ns, span = row[0], row[1]
    atom = connection.execute("SELECT id FROM atoms LIMIT 1").fetchone()[0]
    entity = connection.execute("SELECT id FROM entities LIMIT 1").fetchone()[0]
    values = {
        "from_id": atom,
        "from_kind": "atom",
        "to_id": entity,
        "to_kind": "entity",
        "relation_type": "MENTIONS",
        "epistemic": "DOCUMENT_ASSERTION",
        "status": "ACTIVE",
        "source_span_id": span,
    } | overrides
    connection.execute("INSERT OR IGNORE INTO objects VALUES(?,?,'graph_edge')", (ns, edge_id))
    connection.execute(
        "INSERT INTO graph_edges(ns,id,from_id,from_kind,to_id,to_kind,relation_type,epistemic,"
        "status,scope,source_span_id,valid_from,producer_revision,commit_seq) "
        "VALUES(?,?,?,?,?,?,?,?,?,'s',?,'2026-01-01T00:00:00Z','rev',1)",
        (
            ns,
            edge_id,
            values["from_id"],
            values["from_kind"],
            values["to_id"],
            values["to_kind"],
            values["relation_type"],
            values["epistemic"],
            values["status"],
            values["source_span_id"],
        ),
    )


def test_the_edge_constraints_accept_a_good_edge_and_refuse_each_bad_one(tmp_path):
    root, _first, _extra = seeded_v5_store(tmp_path)
    with Engine(root, HOST) as engine:
        connection = engine.db.connection
        _edge(connection, "edge_good")  # positive control: the same helper succeeds
        assert connection.execute("SELECT count(*) FROM graph_edges").fetchone()[0] == 1
        refused = {
            "unknown relation type": ({"relation_type": "FRIENDS_WITH"}, "FOREIGN KEY"),
            "unknown endpoint kind": ({"to_kind": "span"}, "CHECK"),
            "endpoint kind not matching its object": ({"to_kind": "atom"}, "FOREIGN KEY"),
            "missing support span": ({"source_span_id": None}, "NOT NULL"),
            "support span that does not exist": ({"source_span_id": "span_nope"}, "FOREIGN KEY"),
            "hypothesized cause as an observation": (
                {"relation_type": "HYPOTHESIZES_CAUSE", "epistemic": "DIRECT_OBSERVATION"},
                "CHECK",
            ),
            "verified cause from a hypothesis": (
                {"relation_type": "VERIFIED_CAUSE", "epistemic": "HYPOTHESIS"},
                "CHECK",
            ),
        }
        for label, (overrides, message) in refused.items():
            with pytest.raises(sqlite3.IntegrityError, match=message):
                _edge(connection, "edge_" + label.replace(" ", "_"), **overrides)
        assert connection.execute("SELECT count(*) FROM graph_edges").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE graph_edges SET status='RETRACTED'")


def test_the_relation_catalog_cannot_flag_a_hypothesized_cause_as_causal():
    sql = (Path("src/norn/canonical") / "006_graph.sql").read_text(encoding="utf-8")
    create = next(
        s for s in statements(sql) if s.lstrip().startswith("CREATE TABLE relation_types")
    )
    with sqlite3.connect(":memory:") as bare:
        bare.execute(create)
        bare.execute("INSERT INTO relation_types VALUES('VERIFIED_CAUSE',1,1)")  # control
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            bare.execute("INSERT INTO relation_types VALUES('HYPOTHESIZES_CAUSE',1,1)")
