"""ADR-0027 Q-F for the P05 run kinds: held-out and factorial runs can be externally attested."""

import json

import pytest

from benchmark.runs import cli
from benchmark.runs.seal import attest, facts, verify
from norn.contracts.errors import NornError


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")


def heldout_run(root):
    write(root / "manifest.json", {"code_digest": "c" * 64, "kind": "P05_LOSS_HELDOUT"})
    write(root / "selection.json", {"selected": "T1"})
    for role in ("tune", "evaluation"):
        write(root / f"ledger-{role}.jsonl", f'{{"row": "{role}"}}\n')
        write(root / f"completion-{role}.json", {"last_digest": role[0] * 64})
    return root


def factorial_run(root):
    write(root / "manifest.json", {"code_digest": "d" * 64, "kind": "P05_LOSS_FACTORIAL"})
    write(root / "training.json", {"jobs": []})
    return root


def test_heldout_attestation_binds_both_ledgers_the_selection_and_the_chain_heads(tmp_path):
    run = heldout_run(tmp_path / "run")
    seal = tmp_path / "seals" / "heldout.json"
    value = attest(run, seal)
    assert value["kind"] == "heldout" and value["tune_final_chain"] == "t" * 64
    assert verify(run, seal)["evaluation_final_chain"] == "e" * 64
    # Each bound artifact, changed alone, breaks verification (positive controls).
    for name, changed in (
        ("ledger-evaluation.jsonl", '{"row": "rewritten"}\n'),
        ("ledger-tune.jsonl", '{"row": "rewritten"}\n'),
        ("selection.json", '{"selected": "T7"}'),
        ("completion-tune.json", '{"last_digest": "x"}'),
    ):
        original = (run / name).read_text(encoding="utf-8")
        write(run / name, changed)
        with pytest.raises(NornError, match="RUN_ATTESTATION_MISMATCH"):
            verify(run, seal)
        write(run / name, original)
        assert verify(run, seal)
    with pytest.raises(NornError, match="ATTESTATION_INSIDE_RUN"):
        attest(run, run / "inside.json")


def test_factorial_attestation_binds_the_manifest_and_training_record(tmp_path):
    run = factorial_run(tmp_path / "run")
    seal = tmp_path / "seals" / "factorial.json"
    assert attest(run, seal)["kind"] == "factorial"
    write(run / "training.json", {"jobs": [{"seed": 11}]})
    with pytest.raises(NornError, match="RUN_ATTESTATION_MISMATCH"):
        verify(run, seal)


def test_an_unrecognised_directory_resolves_to_no_run_kind(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(NornError, match="RUN_KIND_UNRESOLVED"):
        facts(tmp_path / "empty")


def test_report_commands_need_an_attestation_or_the_labelled_opt_out(tmp_path):
    run = heldout_run(tmp_path / "run")
    with pytest.raises(NornError, match="ATTESTATION_REQUIRED"):
        cli._evidence_status(run, None, False)
    assert cli._evidence_status(run, None, True) == "DEVELOPMENT_ONLY_NOT_CITABLE"
    seal = tmp_path / "seals" / "heldout.json"
    attest(run, seal)
    assert cli._evidence_status(run, seal, False) == "ATTESTED"
    with pytest.raises(NornError, match="ATTESTATION_OR_DEVELOPMENT_ONLY"):
        cli._evidence_status(run, seal, True)
    write(run / "ledger-tune.jsonl", '{"row": "rewritten"}\n')
    with pytest.raises(NornError, match="RUN_ATTESTATION_MISMATCH"):
        cli._evidence_status(run, seal, False)
