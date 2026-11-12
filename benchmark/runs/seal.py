"""External attestation of a finished run.

A run's own ``completion.json`` is rewritable together with a corrupted ledger, so it cannot
vouch for itself. An attestation records the digests of the manifest, completion, ledger and final
hash-chain head in a file kept *outside* the run directory (committed with the evidence), and
verification recomputes all of them from the run.
"""

from pathlib import Path
from typing import Any

from benchmark.runs.manifest import file_digest, load, write_once
from norn.contracts.errors import require

# kind -> (completion file, ledger file, chain key inside the completion)
LAYOUTS = {
    "conventional": ("completion.json", "ledger.jsonl", "final_chain_digest"),
    "binding": ("binding-completion.json", "binding-ledger.jsonl", "last_digest"),
}


HELDOUT_ROLES = ("tune", "evaluation")


def _layout(root: Path) -> str:
    kinds = [k for k, (completion, _l, _c) in LAYOUTS.items() if (root / completion).is_file()]
    if (root / "completion-tune.json").is_file():
        kinds.append("heldout")
    elif (root / "training.json").is_file() and not kinds:
        kinds.append("factorial")
    require(len(kinds) == 1, "RUN_KIND_UNRESOLVED")
    return kinds[0]


def _heldout(root: Path) -> dict[str, Any]:
    """Two scored roles, each with its own completion, chained ledger and the frozen selection."""
    from benchmark.runs.binding import ledger_digest

    value: dict[str, Any] = {"selection_digest": file_digest(root / "selection.json")}
    for role in HELDOUT_ROLES:
        completion = load(root / f"completion-{role}.json")
        value[f"{role}_completion_digest"] = file_digest(root / f"completion-{role}.json")
        value[f"{role}_ledger_digest"] = ledger_digest(root / f"ledger-{role}.jsonl")
        value[f"{role}_final_chain"] = completion["last_digest"]
    return value


def facts(root: Path) -> dict[str, Any]:
    kind = _layout(root)
    if kind in ("heldout", "factorial"):
        manifest = load(root / "manifest.json")
        common = {
            "schema": 1,
            "kind": kind,
            "manifest_digest": file_digest(root / "manifest.json"),
            "code_digest": manifest["code_digest"],
        }
        if kind == "heldout":
            return {**common, **_heldout(root)}
        return {**common, "training_digest": file_digest(root / "training.json")}
    completion_name, ledger_name, chain_key = LAYOUTS[kind]
    manifest = load(root / "manifest.json")
    completion = load(root / completion_name)
    if kind == "binding":
        from benchmark.runs.binding import ledger_digest

        ledger = ledger_digest(root / ledger_name)
    else:
        ledger = file_digest(root / ledger_name)
    return {
        "schema": 1,
        "kind": kind,
        "manifest_digest": file_digest(root / "manifest.json"),
        "completion_digest": file_digest(root / completion_name),
        "ledger_digest": ledger,
        "final_chain": completion[chain_key],
        "code_digest": manifest["code_digest"],
    }


def attest(root: Path, destination: Path) -> dict[str, Any]:
    root, destination = root.resolve(), destination.resolve()
    require(root not in destination.parents, "ATTESTATION_INSIDE_RUN")
    value = facts(root)
    value["attestation_digest"] = write_once(destination, value)
    return value


def verify(root: Path, attestation: Path) -> dict[str, Any]:
    expected = dict(load(attestation))
    require(set(expected) == set(facts(root)), "ATTESTATION_SCHEMA")
    require(expected == facts(root), "RUN_ATTESTATION_MISMATCH")
    return expected
