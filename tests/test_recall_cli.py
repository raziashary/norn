"""Same source-backed recall scenario in development and an isolated installed wheel."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def scenario(python: str, root: Path, model_root: Path | None = None) -> dict[str, object]:
    command = [python, "-I", "-m", "norn.cli", "--store", str(root / "store")]
    if model_root is not None:
        command += ["--model-root", str(model_root), "--enable-models"]

    def invoke(*arguments: str, principal: str = "operator", expected: int = 0):
        run = subprocess.run(
            [*command, "--principal", principal, *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert run.returncode == expected, run.stdout + run.stderr
        return json.loads(run.stdout)

    invoke("init")
    write_file, query_file = root / "write.json", root / "query.json"

    def write(occurrence: str, day: int, value: str, correction=None):
        content = f"Alex parked in {value}."
        payload = {
            "request_id": occurrence,
            "delivery": occurrence,
            "occurrence": occurrence,
            "content": content,
            "event_time": {"kind": "EXACT", "start": f"2026-10-{day}T09:00:00+00:00"},
            "observed_at": f"2026-10-{day}T09:01:00+00:00",
            "schema_version": 1,
            "atoms": [
                {
                    "subject": "Alex",
                    "predicate": "parked_in",
                    "value": {"tag": "TEXT", "value": value},
                    "start": 0,
                    "end": len(content.encode()),
                    "epistemic": "USER_REPORTED",
                    "qualifiers": {"scope": "parking"},
                }
            ],
        }
        if correction is not None:
            payload["correction"] = correction
        write_file.write_text(json.dumps(payload), encoding="utf-8")
        return invoke("write", "--input", str(write_file))

    monday = write("monday", 19, "ZoneM")
    tuesday = write("tuesday", 20, "ZoneA")
    query = {
        "text": "Alex parking",
        "clock": {
            "evaluation_time": "2030-01-01T00:00:00+00:00",
            "timezone": "UTC",
            "basis": "VALID_TIME",
            "valid_at": "2026-10-20T09:00:00+00:00",
            "knowledge_at": "2030-01-01T00:00:00+00:00",
        },
        "subject": "Alex",
        "event_start": "2026-10-20T00:00:00+00:00",
        "event_end": "2026-10-21T00:00:00+00:00",
        "requested_fields": ["parked_in"],
        "deadline_ms": 120000,
    }

    def recall(arm="R0", principal="operator", expected=0):
        query["arm"] = arm
        query_file.write_text(json.dumps(query), encoding="utf-8")
        return invoke("recall", "--input", str(query_file), principal=principal, expected=expected)

    assert recall()["reason"] == "PROJECTION_NOT_READY"
    ready = invoke("project")
    assert ready["state"] == "READY"
    assert invoke("project")["snapshot_id"] == ready["snapshot_id"]
    arms = ("R0", "R1", "R2", "R3") if model_root else ("R0",)
    for arm in arms:
        result = recall(arm)
        assert result["status"] == "SUPPORTED" and result["coverage"] == "CONSISTENT_READY", result
        assert {r["event_id"] for r in result["evidence"]} == {tuesday["event_id"]}
        assert result["evidence"][0]["text"] == "Alex parked in ZoneA."
        assert result["evidence_tokens"] <= 2000
        counts = result["trace"]["stage_counts"]
        assert counts["before_rerank"] == counts["after_rerank"] == counts["after_dedup"]
        assert counts["channel_votes"] >= counts["after_dedup"] >= counts["final_evidence"]
        if arm == "R1":
            assert counts["lexical"] == counts["exact"] == 0
        assert monday["event_id"] not in json.dumps(result)
    correction = write(
        "correction",
        20,
        "ZoneB",
        {
            "prior_atom": tuesday["atom_ids"][0],
            "classification": "SUPERSEDES",
            "scope": "parking",
            "valid_from": "2026-10-20T00:00:00+00:00",
            "valid_to": None,
            "reason": "observed-correction",
        },
    )
    assert recall()["status"] == "VERIFICATION_UNAVAILABLE"
    invoke("project")
    result = recall()
    assert result["status"] == "SUPPORTED"
    current = [r for r in result["evidence"] if r["applicability"] == "CURRENT"]
    assert len(current) == 1 and current[0]["event_id"] == correction["event_id"]
    assert json.loads(current[0]["value_json"])["value"] == "ZoneB"
    invoke("grant", "reader", "READ")
    invoke("project")
    assert recall(principal="reader")["status"] == "SUPPORTED"
    invoke("revoke", "reader", "READ")
    denied = recall(principal="reader", expected=2)
    assert denied["error"] == "NOT_AUTHORIZED_OR_NOT_FOUND" and "Zone" not in json.dumps(denied)
    obligation = invoke(
        "deny", correction["event_id"], "--request-id", "erase", "--reason", "synthetic-control"
    )
    assert not obligation["physical_purge_complete"]
    assert any(row["artifact"] == "projection_artifacts" for row in obligation["obligations"])
    invoke("project")
    denied = recall()
    assert not denied["evidence"] and "ZoneB" not in json.dumps(denied)
    return {
        "arms": arms,
        "source_readback": True,
        "correction_reopen": True,
        "revocation": True,
        "current_denial": True,
        "physical_purge_complete": False,
        "python": python,
    }


def test_restarted_cli_recall_correction_revoke(tmp_path):
    assert scenario(sys.executable, tmp_path)["source_readback"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="norn-recall-smoke-") as directory:
        print(
            json.dumps(scenario(sys.executable, Path(directory), args.model_root), sort_keys=True)
        )
