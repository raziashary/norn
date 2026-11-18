"""Derived graph extraction quality on the public-v2 pilot role (P06-T02, development only).

Three tracks, each in its own throw-away store so no oracle edge can reach a derived one:

* ``TEMPLATE_READBACK`` on template renderings: the stored fact read back, zero extraction error
  by construction (the control the metrics must score perfect).
* ``NOISY_TEXT`` on template and NOISY_V1 renderings: the text reader of
  ``norn.extraction.relations``, which sees only the stored message.
* ``GOLD_DIAGNOSTIC`` on template renderings: edges written from the hidden gold graph, labelled
  with the oracle revision, an unequal upper bound that is never scored as a derived track.

Every derived track is scored against the gold edges that a published source states (gold edges
that only an unpublished private source states are counted and reported apart). The module reads
no model, network or Groq endpoint.
"""

import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark.adapters.baseline import host, load_sources
from benchmark.adapters.common import replay_clock
from benchmark.fixtures.multihop import MultiHopCase, multihop_cases
from benchmark.fixtures.noisy_render import noisy_case, require_labelled
from benchmark.fixtures.publication import publish
from benchmark.metrics.graph_quality import ORACLE_REVISION, EdgeObs, pool, score_edges
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.extraction.relations import (
    REVISIONS,
    TRACK_READBACK,
    TRACK_TEXT,
    extract_relations,
)
from norn.graph.adjacency import build_graph, write_edge
from norn.graph.contracts import EdgeSpec, NodeRef
from norn.integration.engine import Engine

RUN_KIND = "GRAPH_EXTRACTION_DEVELOPMENT"
TRACK_GOLD = "GOLD_DIAGNOSTIC"
STRATA = ("TEMPLATE", "NOISY_V1:en", "NOISY_V1:id", "NOISY_V1:mixed")
PLAN = (
    (TRACK_READBACK, "TEMPLATE"),
    (TRACK_TEXT, "TEMPLATE"),
    (TRACK_TEXT, "NOISY_V1:en"),
    (TRACK_TEXT, "NOISY_V1:id"),
    (TRACK_TEXT, "NOISY_V1:mixed"),
    (TRACK_GOLD, "TEMPLATE"),
)
MARKER = "__GOLD_CANARY__"


def gold_edges(case: MultiHopCase, published_ids: set[str]) -> tuple[list[EdgeObs], int]:
    """Gold edges stated by a published source, and the count only a private source states."""
    key = {hidden: k for hidden, _name, k in case.graph.nodes}
    kept, unpublished = [], 0
    for tail, head, relation, source in case.graph.edges:
        if source not in published_ids:
            unpublished += 1
            continue
        kept.append(EdgeObs(key[tail], key[head], relation, source, "GOLD"))
    return kept, unpublished


def _entity_key(engine: Engine, graph: Any, entity_id: str) -> str | None:
    """Governed key of an entity, following a reviewed identity link when it has none."""
    row = engine.db.connection.execute(
        "SELECT external_key FROM entities WHERE ns=? AND id=?", (engine.access.ns, entity_id)
    ).fetchone()
    if row is not None and row[0] is not None:
        return str(row[0])
    for arc in graph.neighbors(NodeRef("entity", entity_id), frozenset({"IDENTITY_LINK"})):
        linked = engine.db.connection.execute(
            "SELECT external_key FROM entities WHERE ns=? AND id=?",
            (engine.access.ns, arc.neighbor.id),
        ).fetchone()
        if linked is not None and linked[0] is not None:
            return str(linked[0])
    return None


def derived_edges(engine: Engine, revision: str, published_of: dict[str, str]) -> list[EdgeObs]:
    """REQUIRES edges of one producer revision, read back through the T01 graph reader."""
    graph = build_graph(engine.registry)
    result = []
    for edge in graph.edges:
        if edge.relation != "REQUIRES" or edge.producer_revision != revision:
            continue
        result.append(
            EdgeObs(
                _entity_key(engine, graph, edge.source.id),
                _entity_key(engine, graph, edge.target.id),
                edge.relation,
                published_of.get(edge.supports[0].source_id, "UNMAPPED"),
                revision,
            )
        )
    return result


def write_gold_diagnostic(
    engine: Engine, edges: list[EdgeObs], atom_of: dict[str, str]
) -> dict[str, int]:
    """Oracle edges into this store under the oracle revision; unmappable ones are counted."""
    registry = engine.registry
    by_key = {
        str(r[1]): str(r[0])
        for r in engine.db.connection.execute(
            "SELECT id,external_key FROM entities WHERE ns=? AND external_key IS NOT NULL",
            (registry.ns,),
        )
    }
    written = unmapped = 0
    for edge in edges:
        if edge.tail not in by_key or edge.head not in by_key or edge.source not in atom_of:
            unmapped += 1
            continue
        span = str(registry.source_for_atom(atom_of[edge.source])["id"])
        recorded = str(
            engine.db.connection.execute(
                "SELECT ev.recorded_at FROM atoms a "
                "JOIN events ev ON ev.ns=a.ns AND ev.id=a.event_id WHERE a.ns=? AND a.id=?",
                (registry.ns, atom_of[edge.source]),
            ).fetchone()[0]
        )
        write_edge(
            registry,
            EdgeSpec(
                "REQUIRES",
                NodeRef("entity", by_key[edge.tail]),
                NodeRef("entity", by_key[edge.head]),
                "DOCUMENT_ASSERTION",
                "*",
                (span,),
                recorded,
                ORACLE_REVISION,
            ),
        )
        written += 1
    return {"written": written, "unmapped": unmapped}


def measure_case(track: str, stratum: str, case: MultiHopCase, work: Path) -> dict[str, Any]:
    """Build the store for one (track, case), extract or write, score, and remove the store."""
    published = publish(case.case, (MARKER,))
    if stratum != "TEMPLATE":
        require_labelled(published)
    ids = {s.source_id for s in published.sources}
    gold, unpublished = gold_edges(case, ids)
    root = work / digest(canonical([track, stratum, case.case.query.query_id]).encode())[:24]
    require(not root.exists(), "GRAPH_STORE_EXISTS")
    clock = replay_clock(published)
    with Engine(root, host(published), create=True, clock=clock) as engine:
        engine.access.bootstrap()
        mapping, identity = load_sources(engine, published, clock)
        atom_of = {source: atom for atom, source in mapping.items()}
        published_of = {
            str(engine.registry.source_for_atom(atom)["source_id"]): source
            for atom, source in mapping.items()
        }
        if track == TRACK_GOLD:
            extra: dict[str, Any] = write_gold_diagnostic(engine, gold, atom_of)
            revision = ORACLE_REVISION
        else:
            report = extract_relations(engine.registry, track)
            revision = REVISIONS[track]
            extra = {
                "requires": report.requires,
                "hypotheses": report.hypotheses,
                "skipped": dict(report.skipped),
            }
        derived = derived_edges(engine, revision, published_of)
        keys = {
            str(r[0])
            for r in engine.db.connection.execute(
                "SELECT external_key FROM entities WHERE external_key IS NOT NULL"
            )
        }
    shutil.rmtree(root)
    gold_keys = {k for _h, _n, k in case.graph.nodes}
    # A gold edge whose endpoint key no published source defines has no entity to attach to under
    # the identity policy (T17): that is an identity-policy limit, reported apart from how well
    # the relation itself was read.
    representable = [g for g in gold if g.tail in keys and g.head in keys]
    oracle = track == TRACK_GOLD
    return {
        "track": track,
        "stratum": stratum,
        "family": case.graph.family,
        "variant": case.graph.variant,
        "language": case.case.gold.language,
        "score": score_edges(derived, gold, oracle_track=oracle),
        "score_representable": score_edges(derived, representable, oracle_track=oracle),
        "unrepresentable_gold_edges": len(gold) - len(representable),
        "unpublished_gold_edges": unpublished,
        "extra": extra,
        "identity": {
            "registered_keys": len(keys),
            "gold_keys": len(gold_keys),
            "unknown_registered_keys": len(keys - gold_keys),
            "alias_links": identity["alias_links"],
            "gold_alias_links": sum(1 for s, _n in case.graph.identity_links if s in ids),
            "unresolved_aliases": len(identity["unresolved"]),
        },
    }


def selected_cases(seed: int, limit_per_family: int | None) -> dict[str, list[MultiHopCase]]:
    templates = multihop_cases(seed, "pilot")
    if limit_per_family is not None:
        taken: Counter[str] = Counter()
        kept = []
        for case in templates:
            if taken[case.graph.family] < limit_per_family:
                kept.append(case)
                taken[case.graph.family] += 1
        templates = tuple(kept)
    result: dict[str, list[MultiHopCase]] = {}
    for stratum in STRATA:
        language = stratum.split(":")[1] if ":" in stratum else None
        result[stratum] = [
            t if language is None else noisy_case(t, seed, language) for t in templates
        ]
    return result


def run_graph_extraction(
    work: Path, *, seed: int = 47, limit_per_family: int | None = None
) -> dict[str, Any]:
    """Measure every (track, stratum) of the plan on the pilot role and pool the scores."""
    work.mkdir(parents=True, exist_ok=True)
    cases = selected_cases(seed, limit_per_family)
    rows = [
        measure_case(track, stratum, case, work)
        for track, stratum in PLAN
        for case in cases[stratum]
    ]
    cells: dict[str, Any] = {}
    for track, stratum in PLAN:
        for family in sorted({r["family"] for r in rows}):
            chosen = [
                r
                for r in rows
                if (r["track"], r["stratum"], r["family"]) == (track, stratum, family)
            ]
            cells[f"{track}|{stratum}|{family}"] = pool([r["score"] for r in chosen]) | {
                "representable": pool([r["score_representable"] for r in chosen]),
                "unrepresentable_gold_edges": sum(r["unrepresentable_gold_edges"] for r in chosen),
                "unpublished_gold_edges": sum(r["unpublished_gold_edges"] for r in chosen),
                "skipped": dict(
                    sum((Counter(r["extra"].get("skipped", {})) for r in chosen), Counter())
                ),
                "identity": {
                    k: sum(r["identity"][k] for r in chosen) for k in chosen[0]["identity"]
                },
            }
    pooled_representable = {
        f"{track}|{stratum}": pool(
            [
                r["score_representable"]
                for r in rows
                if (r["track"], r["stratum"]) == (track, stratum)
            ]
        )
        for track, stratum in PLAN
    }
    pooled = {
        f"{track}|{stratum}": pool(
            [r["score"] for r in rows if (r["track"], r["stratum"]) == (track, stratum)]
        )
        for track, stratum in PLAN
    }
    return {
        "run_kind": RUN_KIND,
        "label": "DEVELOPMENT_PILOT_ROLE; NOT_A_CONFIRMATORY_RESULT",
        "seed": seed,
        "partition": "pilot",
        "limit_per_family": limit_per_family,
        "cases_per_stratum": {s: len(c) for s, c in cases.items()},
        "revisions": REVISIONS | {TRACK_GOLD: ORACLE_REVISION},
        "pooled": pooled,
        "pooled_representable": pooled_representable,
        "cells": cells,
        "examples": [
            {
                "track": r["track"],
                "stratum": r["stratum"],
                "family": r["family"],
                "spurious": r["score"]["spurious"],
                "missed": r["score_representable"]["missed"],
            }
            for r in rows
            if r["score_representable"]["spurious"] or r["score_representable"]["missed"]
        ][:40],
        "model_free": True,
    }
