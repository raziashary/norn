import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import HOST, clock, request

from norn.contracts.errors import NornError
from norn.integration.engine import Engine


def test_atomic_write_readback_and_no_read_mutation(engine):
    receipt = engine.write(request())
    assert receipt["projection_state"] == "INDEX_PENDING" and receipt["searchable"] is False
    changes = engine.db.connection.total_changes
    result = engine.read(receipt["event_id"], clock()).serialize()
    assert result["atoms"][0]["citations"][0]["text"] == "Alex parked in ZoneA."
    assert result["atoms"][0]["authority"] == "UNVERIFIED"
    assert engine.db.connection.total_changes == changes
    journal = engine.journal()
    assert journal == engine.journal()
    assert journal[-1]["object_ids"] == [receipt["event_id"], *receipt["atom_ids"]]
    with Engine(engine.root, HOST) as reopened:
        assert reopened.read(receipt["event_id"], clock()).serialize()["atoms"] == result["atoms"]


def test_parallel_duplicate_delivery_one_canonical_effect(engine):
    def write_once(_):
        with Engine(engine.root, HOST) as other:
            return other.write(request())

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(write_once, range(8)))
    assert all(r == receipts[0] for r in receipts)
    for table in ("events", "atoms", "deliveries", "atom_support"):
        assert engine.db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
    assert len([r for r in engine.journal() if r["operation"] == "INGEST"]) == 1


def test_outbox_constraint_failure_rolls_back_all_canonical_rows(engine):
    connection = engine.db.connection
    connection.execute(
        "CREATE TRIGGER reject_journal BEFORE INSERT ON outbox "
        "BEGIN SELECT RAISE(ABORT,'synthetic fault'); END;"
    )
    before = connection.execute("SELECT commit_seq FROM namespaces").fetchone()[0]
    with pytest.raises(NornError, match="CANONICAL_TRANSACTION_FAILED"):
        engine.write(request())
    assert connection.execute("SELECT commit_seq FROM namespaces").fetchone()[0] == before
    for table in ("events", "atoms", "deliveries", "atom_support", "sources", "source_versions"):
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_process_crash_rolls_back_uncommitted_publication(engine):
    code = """import os,sqlite3,sys
c=sqlite3.connect(sys.argv[1],isolation_level=None)
c.execute('BEGIN IMMEDIATE')
c.execute('UPDATE namespaces SET commit_seq=999')
c.execute("INSERT INTO objects VALUES('tenant/workspace/local','event_uncommitted','event')")
os._exit(23)
"""
    result = subprocess.run([sys.executable, "-c", code, str(engine.db.path)], timeout=15)
    assert result.returncode == 23
    assert engine.db.connection.execute("SELECT commit_seq FROM namespaces").fetchone()[0] == 1
    assert engine.db.connection.execute("SELECT count(*) FROM objects").fetchone()[0] == 0


def published_blobs(engine):
    return sorted(p.name for p in (engine.root / "blobs").iterdir() if not p.name.startswith("."))


def staging_files(engine):
    return sorted(
        p.name for p in (engine.root / "blobs").iterdir() if p.name.startswith(".pending")
    )


def test_rejected_ingest_leaves_no_unreachable_source_blob(engine):
    from dataclasses import replace

    connection = engine.db.connection
    connection.execute(
        "CREATE TRIGGER reject_journal BEFORE INSERT ON outbox "
        "BEGIN SELECT RAISE(ABORT,'synthetic fault'); END;"
    )
    # Fault after all SQL ran, plus a pre-transaction validation failure: neither may publish.
    with pytest.raises(NornError, match="CANONICAL_TRANSACTION_FAILED"):
        engine.write(request("late-fault"))
    bad = request("unanchored", place="ZoneB")
    with pytest.raises(NornError, match="UNANCHORED_VALUE"):
        engine.write(
            replace(
                bad,
                atoms=(
                    replace(bad.atoms[0], value=type(bad.atoms[0].value)("TEXT", "NotInTheSource")),
                ),
            )
        )
    assert published_blobs(engine) == [] and staging_files(engine) == []
    connection.execute("DROP TRIGGER reject_journal")
    receipt = engine.write(request("accepted"))
    # Positive control: an accepted write publishes exactly its source and readback matches.
    assert len(published_blobs(engine)) == 1 and staging_files(engine) == []
    assert engine.read(receipt["event_id"], clock()).serialize()["atoms"]


def test_stale_staging_files_are_swept_but_a_live_writers_file_is_kept(engine):
    import os
    import time

    blobs = engine.root / "blobs"
    stale, fresh = blobs / ".pending-stale", blobs / ".pending-fresh"
    stale.write_bytes(b"abandoned by a crash")
    fresh.write_bytes(b"belongs to a live writer")
    old = time.time() - 7200
    os.utime(stale, (old, old))
    engine.write(request("sweeps"))
    assert not stale.exists() and fresh.exists()
