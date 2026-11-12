import json
import subprocess
import sys


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "benchmark.runs.cli", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=45,
    )


def test_actual_cli_run_reopen_report_and_corrupt_manifest(tmp_path):
    root = tmp_path / "run"
    run = cli("run-controls", root)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["observations"] == 405
    report_path = tmp_path / "report.json"
    reopened = cli("validate", root, "--development-only", "--report", report_path)
    assert reopened.returncode == 0, reopened.stderr
    report = json.loads(report_path.read_bytes())
    assert len(report["observations"]) == 405 and report["research_efficacy"] == "NOT_EVALUATED"
    assert report["arms"]["perfect"]["complete_set_itt"] == 1
    assert report["arms"]["empty"]["complete_set_itt"] == 0
    assert report["arms"]["perfect"]["qualified_partial_accuracy"] == 1
    assert report["arms"]["perfect"]["partial_answer_usefulness"] == 1
    partial = next(
        r
        for r in report["observations"]
        if r["arm_id"] == "perfect" and r["answer"]["partial_answerable"]
    )
    assert partial["answer"]["correct_supported"] is True
    assert partial["retrieval"]["partial_set"] is True
    assert partial["retrieval"]["complete_set"] is None
    overclaim = next(
        r
        for r in report["observations"]
        if r["arm_id"] == "shuffled" and r["query_id"] == partial["query_id"]
    )
    assert overclaim["answer"]["false_answer"] is True
    ledger = [json.loads(line) for line in (root / "ledger.jsonl").read_text().splitlines()]
    returned = next(
        r["result"]
        for r in ledger
        if r["arm_id"] == "perfect" and r["query_id"] == partial["query_id"]
    )
    assert returned["missing_fields"] == ["rollback"] and len(returned["candidates"]) == 1
    manifest = root / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    failed = cli("validate", root, "--development-only")
    assert failed.returncode == 2 and json.loads(failed.stderr)["error"] == "MANIFEST_CHANGED"
    assert not failed.stdout


def test_cli_calibration_partition_guard_and_audit_pack(tmp_path):
    data = tmp_path / "calibration"
    run = cli(
        "run-controls",
        data,
        "--partition",
        "calibration",
        "--role",
        "calibrator",
        "--arms",
        "confidence",
        "--sample-only",
    )
    assert run.returncode == 0, run.stderr
    output = tmp_path / "fit.json"
    fitted = cli("calibrate", data, output, "--development-only")
    assert fitted.returncode == 0, fitted.stderr
    model = json.loads(output.read_bytes())["calibration"]
    assert model["counts"][5] > 0 and model["source_partition"] == "calibration"
    smoke = tmp_path / "smoke"
    assert cli("run-controls", smoke, "--arms", "confidence", "--sample-only").returncode == 0
    rejected = cli("calibrate", smoke, tmp_path / "forbidden.json", "--development-only")
    assert rejected.returncode == 2
    assert json.loads(rejected.stderr)["error"] == "CALIBRATION_PARTITION_REQUIRED"
    fake = tmp_path / "self-labeled.json"
    fake.write_text(json.dumps({"partition": "calibration", "values": [[0.2, True]]}))
    assert cli("calibrate", fake, tmp_path / "fake-fit.json", "--development-only").returncode == 2
    pack = tmp_path / "audit.md"
    audit = cli("audit-pack", pack)
    assert audit.returncode == 0, audit.stderr
    assert (
        json.loads(audit.stdout)["pack_digest"]
        == "432d4aa5dd7c1b86d9aeab24c680d7def53d2d727b46b9b09eb0a27d57b8215a"
    )
    assert pack.read_text(encoding="utf-8").count("## E") == 126


def test_cli_validate_and_calibrate_refuse_an_unattested_run_by_default(tmp_path):
    root = tmp_path / "run"
    assert cli("run-controls", root, "--arms", "perfect", "--sample-only").returncode == 0
    for command in (("validate", root), ("calibrate", root, tmp_path / "fit.json")):
        refused = cli(*command)
        assert refused.returncode == 2 and not refused.stdout
        assert json.loads(refused.stderr)["error"] == "ATTESTATION_REQUIRED"
    assert not (tmp_path / "fit.json").exists()
