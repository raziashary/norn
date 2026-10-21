import json

import pytest

from benchmark.runs.manifest import file_digest, load, write_once
from benchmark.runs.runner import run_controls
from benchmark.runs.validate import validate_run
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical, digest


def rewrite_ledger(root, change):
    """Rehash deliberate corruption so semantic guards, rather than hashes alone, must fail."""
    rows = [json.loads(line) for line in (root / "ledger.jsonl").read_text().splitlines()]
    change(rows)
    completion = load(root / "completion.json")
    previous = completion["manifest_digest"]
    counts = {}
    for row in rows:
        row.pop("record_digest")
        row["previous_digest"] = previous
        previous = digest(canonical(row).encode())
        row["record_digest"] = previous
        kind = row["result"]["disposition"]
        counts[kind] = counts.get(kind, 0) + 1
    (root / "ledger.jsonl").write_text("".join(canonical(r) + "\n" for r in rows), encoding="utf-8")
    completion.update(
        ledger_digest=file_digest(root / "ledger.jsonl"),
        final_chain_digest=previous,
        observations=len(rows),
        dispositions=counts,
    )
    (root / "completion.json").write_text(canonical(completion), encoding="utf-8")


def test_reopened_run_retains_all_dispositions_and_denominators(tmp_path):
    root = tmp_path / "run"
    names = (
        "perfect",
        "empty",
        "shuffled",
        "error",
        "timeout",
        "unsupported",
        "invalid",
        "not_run",
        "native:R4",
    )
    completion = run_controls(root, names=names)
    report = validate_run(root)
    assert report["pairs"] == completion["observations"] == 135 * len(names)
    assert set(completion["dispositions"]) == {
        "OK",
        "ERROR",
        "TIMEOUT",
        "UNSUPPORTED",
        "INVALID",
        "NOT_RUN",
    }
    arms = report["arms"]
    assert arms["perfect"]["complete_set_itt"] == 1
    assert arms["empty"]["complete_set_itt"] == 0
    assert 0 < arms["shuffled"]["complete_set_itt"] < 1
    assert arms["native:R4"]["completed"] == 0
    assert report["audit"]["state"] == "PENDING_OR_DISPUTED"
    assert report["contrasts"]["perfect-minus-empty"]["training_seeds"] == [None]
    with pytest.raises(NornError, match="RUN_DIRECTORY_EXISTS"):
        run_controls(root)
    with pytest.raises(FileExistsError):
        write_once(root / "manifest.json", {})


@pytest.mark.parametrize(
    "kind,code",
    [
        ("missing", "MISSING_LEDGER_PAIR"),
        ("duplicate", "LEDGER_PAIR_ACCOUNTING"),
        ("best_of_n", "LEDGER_PAIR_ACCOUNTING"),
        ("stage", "UNOBSERVED_METRIC_STAGE"),
        ("raw", "RAW_RESULT_CHANGED"),
        ("fallback", "HIDDEN_PROVIDER_FALLBACK"),
    ],
)
def test_rehashed_corruptions_fail_for_actual_reason(tmp_path, kind, code):
    root = tmp_path / "run"
    run_controls(root, sample_only=True, names=("perfect",))

    def change(rows):
        if kind == "missing":
            rows.pop()
        elif kind == "duplicate":
            rows.append(dict(rows[0]))
        elif kind == "best_of_n":
            rows[0]["attempt"] = 2
        elif kind == "stage":
            rows[0]["result"]["stage"] = "PRE_VERIFICATION"
        elif kind == "raw":
            rows[0]["raw_response"]["reason"] = "changed"
        else:
            rows[0]["raw_response"]["provider_calls"] = 1

    rewrite_ledger(root, change)
    with pytest.raises(NornError, match=code):
        validate_run(root)


def test_changed_manifest_source_and_extra_public_filename_rejected(tmp_path):
    root = tmp_path / "run"
    run_controls(root, sample_only=True, names=("empty",))
    path = next((root / "published").glob("*.json"))
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(NornError, match="RUN_ARTIFACT_CHANGED"):
        validate_run(root)
    path.write_bytes(original)
    (root / "published" / "required_slot_hidden.json").write_text("{}")
    with pytest.raises(NornError, match="UNDECLARED_PUBLIC_FILE"):
        validate_run(root)


def test_relabeling_smoke_as_calibration_fails_even_after_rehash(tmp_path):
    root = tmp_path / "run"
    run_controls(root, sample_only=True, names=("confidence",))
    manifest = load(root / "manifest.json")
    manifest.update(partition="calibration", partition_role="calibrator")
    (root / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    completion = load(root / "completion.json")
    completion["manifest_digest"] = file_digest(root / "manifest.json")
    (root / "completion.json").write_text(canonical(completion), encoding="utf-8")
    rewrite_ledger(root, lambda rows: None)
    with pytest.raises(NornError, match="WORLD_PARTITION_LINEAGE_CHANGED"):
        validate_run(root)
