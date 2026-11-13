"""Replay the sufficiency decision on stored chain-family observations (read-only).

A false abstention on a chain query can come from three separate mechanisms: the benchmark
interpreter withholds the requested fields, the field-only gate fires a rule on the evidence it
sees, or the evidence is simply incomplete. This reader separates them so a later graph arm's
chain gain is not credited when it came from a changed gate. It opens stored artifacts only;
it never runs retrieval, never reads a credential and never writes into the run.
"""

import argparse
import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from benchmark.adapters.baseline import interpret
from benchmark.adapters.contracts import PublicInput
from benchmark.fixtures.publication import validate_public
from benchmark.fixtures.scenarios import Gold
from benchmark.metrics.evidence_sets import evidence_scores
from benchmark.runs.manifest import file_digest, load
from benchmark.runs.validate import gold_from
from norn.contracts.errors import require
from norn.governance.sufficiency import decide
from norn.retrieval.contracts import Record

FAMILY = "E3"
CLASSES = (
    "ADAPTER_ONLY",
    "ADAPTER_AND_GATE_RULE",
    "RECALL_AND_ADAPTER",
    "RECALL_ADAPTER_AND_GATE_RULE",
)


def records_from(evidence: list[dict[str, Any]]) -> tuple[Record, ...]:
    """Rebuild the exposed records; an unknown or missing key is a schema failure."""
    names = {f.name for f in fields(Record)}
    out = []
    for item in evidence:
        require(set(item) == names, "EVIDENCE_RECORD_SCHEMA")
        out.append(Record(**{**item, "aliases": tuple(item["aliases"])}))
    return tuple(out)


def replay(
    published: PublicInput, arm: str, packet: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    """Gate-side replay; takes no gold, so no label can influence it."""
    request = interpret(published, arm)
    disposition = result["disposition"]
    base = {
        "arm": arm,
        "observed_status": packet.get("status"),
        "observed_reason": packet.get("reason"),
        "adapter_fields": list(request.requested_fields),
        # Published ids from the result candidates, as the evaluator scores them; the packet's
        # own source ids are engine-internal and never match the published ids.
        "exposed_sources": list(dict.fromkeys(c["source_id"] for c in result["candidates"])),
    }
    if disposition != "OK" or not packet:
        return {**base, "replayable": False, "replay_reason": disposition}
    records = records_from(packet["evidence"])
    reproduced = decide(records, request, complete=True)
    # Counterfactual: the gate is handed the predicates of the exposed records as the
    # requested fields, the one input the adapter withholds for a chain question.
    counterfactual_fields = tuple(sorted({r.predicate for r in records}))
    counterfactual = decide(
        records, replace(request, requested_fields=counterfactual_fields), complete=True
    )
    return {
        **base,
        "replayable": True,
        "reproduced": (reproduced.status, reproduced.reason)
        == (packet["status"], packet["reason"]),
        "replayed_status": reproduced.status,
        "replayed_reason": reproduced.reason,
        "counterfactual_fields": list(counterfactual_fields),
        "counterfactual_status": counterfactual.status,
        "counterfactual_reason": counterfactual.reason,
    }


def classify(row: dict[str, Any], gold: Gold, published: PublicInput) -> dict[str, Any]:
    """Join the gate-side replay with the evaluator's slots (the only place gold is read)."""
    scores = evidence_scores(
        tuple(row["exposed_sources"]), gold, frozenset(s.source_id for s in published.sources)
    )
    out = {
        **row,
        "variant": gold.variant,
        "language": gold.language,
        "expected_status": gold.expected_status,
        "expected_reason": gold.reason,
        "slot_coverage": scores["slot_coverage"],
        "slot_denominator": scores["slot_denominator"],
        "complete_set": scores["complete_set"],
        "false_abstention": None,
        "mechanism": None,
    }
    if not row["replayable"] or gold.expected_status != "SUPPORTED":
        return out
    out["false_abstention"] = row["observed_status"] != "SUPPORTED"
    if not out["false_abstention"]:
        return out
    gate = row["counterfactual_status"] != "SUPPORTED"
    complete = scores["complete_set"] is True
    out["mechanism"] = CLASSES[(0 if complete else 2) + (1 if gate else 0)]
    return out


def replay_run(root: Path, *, family: str = FAMILY) -> dict[str, Any]:
    completion = load(root / "completion.json")
    require(file_digest(root / "ledger.jsonl") == completion["ledger_digest"], "LEDGER_CHANGED")
    require(
        file_digest(root / "manifest.json") == completion["manifest_digest"], "MANIFEST_CHANGED"
    )
    golds = {row["query_id"]: gold_from(row) for row in load(root / "evaluator/gold.json")}
    ledger = [json.loads(line) for line in (root / "ledger.jsonl").read_text("utf-8").splitlines()]
    rows = []
    for entry in ledger:
        gold = golds[entry["query_id"]]
        if gold.family != family:
            continue
        published = validate_public(load(root / "published" / (entry["query_id"] + ".json")))
        packet = (entry.get("baseline_diagnostics") or {}).get("packet") or {}
        gate = replay(published, entry["arm_id"], packet, entry["result"])
        rows.append({"query_id": entry["query_id"], **classify(gate, gold, published)})
    positives = [r for r in rows if r["false_abstention"] is not None]
    abstentions = [r for r in positives if r["false_abstention"]]
    summary: dict[str, Any] = {
        "observations": len(rows),
        "not_replayable": sum(not r["replayable"] for r in rows),
        "unreproduced": sum(r["replayable"] and not r["reproduced"] for r in rows),
        "applicable_positive": len(positives),
        "false_abstentions": len(abstentions),
        "observed_reasons": _count(abstentions, "observed_reason"),
        "counterfactual_rules": _count(abstentions, "counterfactual_reason"),
        "mechanisms": _count(abstentions, "mechanism"),
        "by_arm": {
            arm: {
                "false_abstentions": sum(r["arm"] == arm for r in abstentions),
                "complete_sets": sum(
                    r["complete_set"] is True for r in positives if r["arm"] == arm
                ),
            }
            for arm in sorted({r["arm"] for r in rows})
        },
    }
    return {
        "schema": 1,
        "family": family,
        "run_manifest_digest": completion["manifest_digest"],
        "run_ledger_digest": completion["ledger_digest"],
        "scope": (
            "Read-only replay of the exposed evidence records of stored observations; the "
            "gate input before packet truncation is not stored. Development fixture, no "
            "retrieval or model call, no credential."
        ),
        "summary": summary,
        "rows": rows,
    }


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row[key])] = counts.get(str(row[key]), 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay_run(args.run)
    text = json.dumps(result, indent=1, sort_keys=True)
    if args.output:
        require(not args.output.exists(), "OUTPUT_EXISTS")
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(result["summary"], indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
