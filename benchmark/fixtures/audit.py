"""Hash-bound human audit workflow; constructed labels never impersonate humans."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmark.fixtures.scenarios import Case, gold_payload
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest


@dataclass(frozen=True)
class Judgment:
    query_id: str
    annotator: str
    role: str
    independent: bool
    source_digest: str
    gold_digest: str
    agrees: bool
    rationale: str
    adjudicates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require(self.role in {"HUMAN", "AUTHOR_MODEL", "TEST_FIXTURE"})
        require(type(self.independent) is bool and type(self.agrees) is bool)
        require(0 < len(self.annotator) <= 128 and 0 < len(self.rationale) <= 4096)
        require(self.role == "HUMAN" or not self.independent, "FALSE_HUMAN_INDEPENDENCE")


def binding(case: Case) -> tuple[str, str]:
    return case.source_digest, digest(canonical(gold_payload(case)).encode())


def audit_state(case: Case, judgments: tuple[Judgment, ...]) -> str:
    source_hash, gold_hash = binding(case)
    selected = [j for j in judgments if j.query_id == case.query.query_id]
    require(
        all(j.source_digest == source_hash and j.gold_digest == gold_hash for j in selected),
        "STALE_AUDIT_BINDING",
    )
    humans = [j for j in selected if j.role == "HUMAN" and j.independent]
    require(len({j.annotator for j in humans}) == len(humans), "DUPLICATE_ANNOTATOR")
    if not humans:
        return "PENDING_HUMAN_REVIEW"
    dissent = [j for j in humans if not j.agrees]
    if not dissent:
        return "HUMAN_REVIEWED"
    # Two independent annotations plus a distinct independent adjudicator are required.
    if len(humans) < 3:
        return "DISPUTED"
    for human in humans:
        others = {j.annotator for j in humans if j.annotator != human.annotator}
        if human.agrees and len(others.intersection(human.adjudicates)) >= 2:
            return "ADJUDICATED"
    return "DISPUTED"


def stratified_sample(cases: tuple[Case, ...]) -> tuple[Case, ...]:
    """Every family/twin, with EN/ID/mixed rotated within each family (42 cases)."""
    selected: dict[tuple[str, str], Case] = {}
    for case in cases:
        variant_index = ("positive", "ambiguous", "missing").index(case.gold.variant)
        language = ("en", "id", "mixed")[(int(case.gold.family[1:]) + variant_index) % 3]
        if case.gold.language != language or case.gold.cue_missing_fraction:
            continue
        key = case.gold.family, case.gold.variant
        selected.setdefault(key, case)
    return tuple(selected[key] for key in sorted(selected))


def write_audit_pack(cases: tuple[Case, ...], destination: Path) -> str:
    sample = stratified_sample(cases)
    pack = [
        {
            "query": asdict(c.query),
            "source_digest": binding(c)[0],
            "gold_digest": binding(c)[1],
            "constructed_gold": gold_payload(c),
            "sources": [s.public() for s in c.sources],
        }
        for c in sample
    ]
    sha = digest(canonical(pack).encode())
    text = [
        "# P02 stratified label audit",
        "",
        "State: PENDING_HUMAN_REVIEW.",
        "These are constructed fixture labels, not independent human judgments.",
        "Pack SHA256: `" + sha + "`.",
        "Review source sufficiency, identity, time/authority, ambiguity, EN/ID wording and",
        "alternate evidence. Record disagreements; disputed cases require independent",
        "double annotation/adjudication. No model/coordinator agreement counts as human truth.",
        "",
    ]
    for case, row in zip(sample, pack, strict=True):
        gold = case.gold
        text.extend(
            [
                f"## {gold.family} / {gold.variant} / {gold.language}",
                "",
                f"Query ID: `{case.query.query_id}`",
                f"Question: {case.query.text}",
                f"Constructed status: **{gold.expected_status}** ({gold.reason}).",
                f"Source digest: `{row['source_digest']}`; gold digest: `{row['gold_digest']}`.",
                "Sources:",
            ]
        )
        text.extend(f"- `{s.source_id}`: {s.text}" for s in case.sources)
        text.extend(["", "Acceptable source sets: `" + canonical(gold.acceptable_sets) + "`.", ""])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(text))
    return sha


def load_judgments(path: Path) -> tuple[Judgment, ...]:
    require(path.is_file() and path.stat().st_size <= 64_000_000, "AUDIT_RECORD_BUDGET")
    raw: Any = json.loads(path.read_bytes())
    require(type(raw) is list and len(raw) <= 10_000, "AUDIT_RECORD_BUDGET")
    result = []
    for item in raw:
        require(type(item) is dict, "AUDIT_RECORD_SCHEMA")
        item["adjudicates"] = tuple(item.get("adjudicates", []))
        result.append(Judgment(**item))
    return tuple(result)


def audit_summary(cases: tuple[Case, ...], judgments: tuple[Judgment, ...]) -> dict[str, Any]:
    require(
        {j.query_id for j in judgments} <= {c.query.query_id for c in cases},
        "AUDIT_QUERY_NOT_IN_RUN",
    )
    sample = stratified_sample(cases)
    states: dict[str, int] = {}
    for case in cases:
        state = audit_state(case, judgments)
        if case in sample:
            states[state] = states.get(state, 0) + 1
    reviewed = sum(states.get(s, 0) for s in ("HUMAN_REVIEWED", "ADJUDICATED"))
    return {
        "sample_size": len(sample),
        "run_cases": len(cases),
        "states": states,
        "reviewed_sample": reviewed,
        "sampling": "FAMILY_VARIANT_LANGUAGE_ROTATION_V1",
        "state": "SAMPLE_REVIEWED" if reviewed == len(sample) else "PENDING_OR_DISPUTED",
        "provenance": "DECLARED_JUDGMENTS; HUMAN_ATTESTATION_REQUIRES_EXTERNAL_RECEIPT",
    }
