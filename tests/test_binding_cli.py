"""Actual source-backed binding CLI in both editable and isolated wheel environments."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def scenario(
    python: str, root: Path, models: Path, checkpoints: dict[str, Path]
) -> dict[str, object]:
    command = [
        python,
        "-I",
        "-m",
        "norn.cli",
        "--store",
        str(root / "store"),
        "--model-root",
        str(models),
        "--enable-models",
    ]

    def invoke(*args: str, expected: int = 0):
        run = subprocess.run(
            [*command, *args], capture_output=True, text=True, timeout=180, cwd=root
        )
        assert run.returncode == expected, run.stdout + run.stderr
        return json.loads(run.stdout)

    invoke("init")
    content = "Alex parked in ZoneA."
    write = {
        "request_id": "episode",
        "delivery": "episode",
        "occurrence": "episode",
        "content": content,
        "event_time": {"kind": "EXACT", "start": "2026-10-20T09:00:00+00:00"},
        "observed_at": "2026-10-20T09:00:00+00:00",
        "schema_version": 1,
        "atoms": [
            {
                "subject": "Alex",
                "predicate": "parked_in",
                "value": {"tag": "TEXT", "value": "ZoneA"},
                "start": 0,
                "end": len(content),
                "epistemic": "DIRECT_OBSERVATION",
                "qualifiers": {"scope": "parking"},
            }
        ],
    }
    path = root / "write.json"
    path.write_text(json.dumps(write), encoding="utf-8")
    receipt = invoke("write", "--input", str(path))
    query = {
        "text": "Alex parking ZoneA",
        "requested_fields": ["parked_in"],
        "clock": {
            "evaluation_time": "2030-01-01T00:00:00+00:00",
            "timezone": "UTC",
            "basis": "VALID_TIME",
            "valid_at": "2026-10-20T09:00:00+00:00",
            "knowledge_at": "2030-01-01T00:00:00+00:00",
        },
        "deadline_ms": 120000,
    }
    query_path = root / "query.json"
    query_path.write_text(json.dumps(query), encoding="utf-8")
    for variant in ("B0", "B1", "B2", "B3", "B4", "S3", "S4"):
        extra = ["--checkpoint", str(checkpoints[variant])] if variant in checkpoints else []
        projected = invoke("binding-project", "--variant", variant, *extra)
        assert projected["state"] == "READY"
        packet = invoke("binding-recall", "--variant", variant, *extra, "--input", str(query_path))
        assert packet["status"] == "SUPPORTED", packet
        assert packet["evidence"][0]["text"] == content and packet["authorizes_action"] is False
    corrected = json.loads(json.dumps(write))
    corrected.update(
        request_id="correction",
        delivery="correction",
        occurrence="correction",
        content="Alex parked in ZoneB.",
    )
    corrected["atoms"][0]["value"]["value"] = "ZoneB"
    corrected["correction"] = {
        "prior_atom": receipt["atom_ids"][0],
        "classification": "SUPERSEDES",
        "scope": "parking",
        "valid_from": "2026-10-20T00:00:00+00:00",
        "valid_to": None,
        "reason": "observed-correction",
    }
    path.write_text(json.dumps(corrected), encoding="utf-8")
    correction = invoke("write", "--input", str(path))
    for variant in ("B0", "B3"):
        extra = ["--checkpoint", str(checkpoints[variant])] if variant in checkpoints else []
        assert (
            invoke("binding-recall", "--variant", variant, *extra, "--input", str(query_path))[
                "reason"
            ]
            == "BINDING_PROJECTION_NOT_READY"
        )
        invoke("binding-project", "--variant", variant, *extra)
        packet = invoke("binding-recall", "--variant", variant, *extra, "--input", str(query_path))
        current = [r for r in packet["evidence"] if r["applicability"] == "CURRENT"]
        assert len(current) == 1 and current[0]["event_id"] == correction["event_id"]
    invoke("grant", "reader", "READ")
    invoke("binding-project", "--variant", "B0")
    assert (
        invoke(
            "--principal", "reader", "binding-recall", "--variant", "B0", "--input", str(query_path)
        )["status"]
        == "SUPPORTED"
    )
    invoke("revoke", "reader", "READ")
    denied = invoke(
        "--principal",
        "reader",
        "binding-recall",
        "--variant",
        "B0",
        "--input",
        str(query_path),
        expected=2,
    )
    assert denied["error"] == "NOT_AUTHORIZED_OR_NOT_FOUND" and "Zone" not in str(denied)
    denied = invoke(
        "deny", receipt["event_id"], "--request-id", "binding-erase", "--reason", "test"
    )
    assert denied["physical_purge_complete"] is False
    invoke(
        "deny",
        correction["event_id"],
        "--request-id",
        "binding-erase-correction",
        "--reason",
        "test",
    )
    stale = invoke("binding-recall", "--variant", "B0", "--input", str(query_path))
    assert stale["status"] == "VERIFICATION_UNAVAILABLE"
    invoke("binding-project", "--variant", "B0")
    empty = invoke("binding-recall", "--variant", "B0", "--input", str(query_path))
    assert empty["status"] == "NOT_ESTABLISHED" and "Zone" not in str(empty)
    return {
        "variants": ["B0", "B1", "B2", "B3", "B4", "S3", "S4"],
        "source_readback": True,
        "current_denial": True,
        "correction_and_revocation": True,
        "python": python,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    args = parser.parse_args()
    checkpoints = {
        v: (args.checkpoint_root / f"{v}-11.json").absolute() for v in ("B3", "B4", "S3", "S4")
    }
    with TemporaryDirectory(prefix="norn-binding-cli-") as temporary:
        print(
            json.dumps(
                scenario(sys.executable, Path(temporary), args.model_root.absolute(), checkpoints)
            )
        )
