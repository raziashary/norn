"""Same scenario runs under pytest and under an isolated installed wheel interpreter."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def scenario(python: str, root: Path) -> dict[str, object]:
    store = root / "pilot"
    command = [python, "-I", "-m", "norn.cli", "--store", str(store)]

    def invoke(*args: str, principal: str = "operator", expected: int = 0) -> object:
        result = subprocess.run(
            [*command, "--principal", principal, *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == expected, result.stdout + result.stderr
        return json.loads(result.stdout)

    resolved = invoke(
        "resolve-time",
        "yesterday",
        "--evaluation-time",
        "2026-03-09T16:00:00+00:00",
        "--timezone",
        "America/New_York",
    )
    assert resolved["resolved"]["start"] == "2026-03-08T05:00:00.000000+00:00"
    assert resolved["resolved"]["end"] == "2026-03-09T04:00:00.000000+00:00"
    assert invoke("init")["initialized"] is True

    def payload(occurrence: str, day: int, place: str = "ZoneA") -> dict[str, object]:
        content = f"Alex parked in {place}."
        return {
            "request_id": occurrence,
            "delivery": occurrence,
            "occurrence": occurrence,
            "content": content,
            "event_time": {"kind": "EXACT", "start": f"2026-10-{day:02d}T09:00:00+00:00"},
            "observed_at": f"2026-10-{day:02d}T09:01:00+00:00",
            "schema_version": 1,
            "atoms": [
                {
                    "subject": "Alex",
                    "predicate": "parked_in",
                    "value": {"tag": "TEXT", "value": place},
                    "start": 0,
                    "end": len(content.encode()),
                    "epistemic": "USER_REPORTED",
                    "qualifiers": {"scope": "parking"},
                }
            ],
        }

    source = root / "request.json"

    def write(data: dict[str, object], expected: int = 0) -> object:
        source.write_text(json.dumps(data), encoding="utf-8")
        return invoke("write", "--input", str(source), expected=expected)

    monday = write(payload("monday", 19))
    tuesday = write(payload("tuesday", 20))
    assert monday["event_id"] != tuesday["event_id"]
    assert write(payload("tuesday", 20)) == tuesday
    clock = [
        "--evaluation-time",
        "2030-01-01T00:00:00+00:00",
        "--timezone",
        "UTC",
        "--basis",
        "VALID_TIME",
        "--valid-at",
        "2026-10-20T09:00:00+00:00",
        "--knowledge-at",
        "2030-01-01T00:00:00+00:00",
    ]
    before = invoke("read", tuesday["event_id"], *clock)
    assert before["atoms"][0]["citations"][0]["text"] == "Alex parked in ZoneA."
    assert before["searchable"] is False and before["coverage"] == "CANONICAL_FALLBACK"
    changed = payload("correction", 20, "ZoneB")
    changed["correction"] = {
        "prior_atom": tuesday["atom_ids"][0],
        "classification": "SUPERSEDES",
        "scope": "parking",
        "valid_from": "2026-10-20T00:00:00+00:00",
        "valid_to": None,
        "reason": "reported-correction",
    }
    correction = write(changed)
    assert len(correction["relation_ids"]) == 1
    assert invoke("read", tuesday["event_id"], *clock)["atoms"][0]["applicability"] == "SUPERSEDED"
    historical = invoke(
        "read", tuesday["event_id"], *clock, "--snapshot", str(tuesday["commit_seq"])
    )
    assert historical["atoms"][0]["applicability"] == "CURRENT"
    current = invoke("read", correction["event_id"], *clock)
    assert current["atoms"][0]["value"]["value"] == "ZoneB"
    invoke("grant", "reader", "READ")
    assert (
        invoke("read", correction["event_id"], *clock, principal="reader")["outcome"] == "SUPPORTED"
    )
    invoke("revoke", "reader", "READ")
    denied = invoke("read", correction["event_id"], *clock, principal="reader", expected=2)
    assert denied["error"] == "NOT_AUTHORIZED_OR_NOT_FOUND"
    assert "ZoneB" not in json.dumps(denied)
    journal = invoke("journal")
    assert len([entry for entry in journal if entry["operation"] == "INGEST"]) == 3
    assert invoke("journal") == journal
    invalid = payload("bad-schema", 20)
    invalid["schema_version"] = 99
    assert write(invalid, expected=2)["error"] == "UNSUPPORTED_SCHEMA"
    invalid = payload("forged-authority", 20)
    invalid["authority"] = "APPROVED-PRIVATE-CANARY"
    error = write(invalid, expected=2)
    assert error["error"] == "INVALID_FIELDS" and "PRIVATE-CANARY" not in json.dumps(error)
    denied_source = invoke(
        "deny", correction["event_id"], "--request-id", "erase", "--reason", "synthetic-expiry"
    )
    assert denied_source["physical_purge_complete"] is False
    assert (
        invoke("read", correction["event_id"], *clock, expected=2)["error"]
        == "NOT_AUTHORIZED_OR_NOT_FOUND"
    )
    assert invoke("purge-status", "erase") == denied_source
    return {
        "distinct_events": 3,
        "duplicate_effects": 0,
        "journal_replay_stable": True,
        "historical_correction": "PASS",
        "current_revocation": "PASS",
        "source_readback": "PASS",
        "physical_purge_complete": False,
        "installed_python": python,
    }


def test_separate_process_write_restart_read_correct_revoke(tmp_path):
    assert scenario(sys.executable, tmp_path)["distinct_events"] == 3


if __name__ == "__main__":
    with TemporaryDirectory(prefix="norn-installed-smoke-") as directory:
        print(json.dumps(scenario(sys.executable, Path(directory)), sort_keys=True))
