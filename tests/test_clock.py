"""Canonical recording time is host-owned and injectable, never silently the machine date."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import HOST, TUESDAY, clock, request

from benchmark.adapters.common import ReplayClock
from norn.canonical.database import SCHEMA_VERSION, Database
from norn.contracts.errors import NornError
from norn.governance.access import Access
from norn.integration.engine import Engine

RECORDED = datetime(2026, 10, 20, 9, 5, tzinfo=UTC)


def test_replayed_record_is_known_at_its_own_recording_time_regardless_of_the_machine_date(
    tmp_path,
):
    replay = ReplayClock(RECORDED)
    with Engine(tmp_path / "store", HOST, create=True, clock=replay) as engine:
        engine.access.bootstrap()
        receipt = engine.write(request())
        assert engine.read(receipt["event_id"], clock(knowledge=RECORDED)).serialize()["atoms"]
        with pytest.raises(NornError, match="NOT_ESTABLISHED"):
            engine.read(receipt["event_id"], clock(knowledge=RECORDED - timedelta(seconds=1)))
        durable = engine.registry.receipt(receipt["event_id"])["durable_at"]
        assert durable == "2026-10-20T09:05:00.000000+00:00"
    assert datetime.now(UTC) > RECORDED  # the bound is the injected instant, not today


def test_replay_clock_stamps_each_write_and_later_state_changes(tmp_path):
    replay = ReplayClock(RECORDED)
    with Engine(tmp_path / "store", HOST, create=True, clock=replay) as engine:
        engine.access.bootstrap()
        first = engine.write(request("first"))
        replay.set(RECORDED + timedelta(hours=1))
        second = engine.write(request("second", place="ZoneB"))
        rows = engine.db.connection.execute(
            "SELECT id,recorded_at FROM events ORDER BY commit_seq"
        ).fetchall()
        assert [r["id"] for r in rows] == [first["event_id"], second["event_id"]]
        assert [r["recorded_at"][:16] for r in rows] == ["2026-10-20T09:05", "2026-10-20T10:05"]
        grants = engine.db.connection.execute("SELECT DISTINCT recorded_at FROM scope_grants")
        assert {row[0][:16] for row in grants} == {"2026-10-20T09:05"}


def test_naive_injected_clock_is_rejected_instead_of_guessing_a_zone(tmp_path):
    with Engine(
        tmp_path / "store", HOST, create=True, clock=lambda: TUESDAY.replace(tzinfo=None)
    ) as engine:
        with pytest.raises(NornError, match="NAIVE_TIME"):
            engine.access.bootstrap()


def test_failed_upgrade_rolls_back_without_bricking_the_store(tmp_path, monkeypatch):
    root = tmp_path / "store"
    path = root / "canonical.sqlite3"
    old = Database(path, create=True, target=1)
    Access(old, HOST).bootstrap()
    old.close()

    def broken(self):
        raise NornError("INJECTED_MIGRATION_FAILURE")

    with monkeypatch.context() as patch:
        patch.setattr(Database, "_immutability", broken)
        with pytest.raises(NornError, match="INJECTED_MIGRATION_FAILURE"):
            Database(path)
    # The marker must not outlive a rolled-back transaction; a later healthy attempt succeeds.
    upgraded = Database(path)
    assert upgraded.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    upgraded.close()
