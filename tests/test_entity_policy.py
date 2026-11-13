"""P06-T17: shared identity only from a governed key or a source-grounded alias statement."""

import ast
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from benchmark.adapters.baseline import host, load_sources
from benchmark.adapters.common import replay_clock
from benchmark.adapters.contracts import PublicInput, PublishedSource
from benchmark.fixtures import entities
from benchmark.fixtures.entities import identity_plan
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import publish
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from norn.canonical.identity import register_entity
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical, digest, stable_id
from norn.governance.access import Access, HostIdentity
from norn.integration.engine import Engine

ENTITY_SQL = "SELECT count(*) FROM entities WHERE ns=?"


def template() -> PublicInput:
    world = build_world(47, partition(47, "development"))
    return publish(scenarios(world)[0], (world.gold_canary,))


def source_with(base: PublishedSource, name: str, actor: str, message: str) -> PublishedSource:
    """A published source whose message carries the identity statement under test."""
    observation = replace(base.observation, actor=actor, value=f"v-{name}")
    text = canonical({"capture": asdict(observation), "message": message})
    return replace(
        base,
        source_id=stable_id("source", name),
        event_id=stable_id("event", name),
        atom_id=stable_id("atom", name),
        text=text,
        sha256=digest(text.encode()),
        observation=observation,
    )


def world_of(*specs: tuple[str, str, str]) -> PublicInput:
    base = template()
    sources = tuple(source_with(base.sources[0], n, a, m) for n, a, m in specs)
    return replace(base, sources=sources)


def load(tmp_path: Path, published: PublicInput):
    clock = replay_clock(published)
    engine = Engine(tmp_path / "store", host(published), create=True, clock=clock)
    engine.access.bootstrap()
    return engine, load_sources(engine, published, clock)


def entities_for(engine: Engine, actor: str) -> set[str]:
    rows = engine.db.connection.execute(
        "SELECT DISTINCT entity_id FROM entity_aliases WHERE ns=? AND label=?",
        (engine.access.ns, actor),
    )
    return {r[0] for r in rows}


def test_plan_reads_only_published_statements_and_rejects_ambiguity():
    published = world_of(
        ("a", "Sari", "Sari parked [key:acct-7]"),
        ("b", "Sari", "plain note"),
        ("c", "Dewi", "Dewi parked [alias:Sari]"),
    )
    plan = identity_plan(published.sources)
    ids = {s.observation.actor + s.text[-6:]: s.source_id for s in published.sources}
    assert [k for _s, k in plan.keys] == ["acct-7"] and [a for _s, a in plan.aliases] == ["Sari"]
    assert len(ids) == 3
    with pytest.raises(NornError, match="AMBIGUOUS_IDENTITY_STATEMENT"):
        identity_plan(world_of(("d", "Sari", "x [key:one] [key:two]")).sources)


def test_same_key_shares_one_entity_and_names_alone_never_merge(tmp_path):
    published = world_of(
        ("a", "Sari", "Sari parked [key:acct-7]"),
        ("b", "Sari-B", "Sari-B parked [key:acct-7]"),
        ("c", "Sari", "Sari parked elsewhere"),
        ("d", "Sari", "Sari parked again"),
    )
    engine, (mapping, identity) = load(tmp_path, published)
    try:
        assert identity["keys"] == 2 and identity["shared_entities"] == 1
        keyed = engine.db.connection.execute(
            "SELECT id FROM entities WHERE ns=? AND external_key='acct-7'", (engine.access.ns,)
        ).fetchall()
        assert len(keyed) == 1  # two sources, one governed entity
        # Control: the two unkeyed sources with the same display name stay separate occurrences.
        atom_of = {source: atom for atom, source in mapping.items()}
        unkeyed = {
            engine.db.connection.execute(
                "SELECT subject_ref FROM atoms WHERE ns=? AND id=?",
                (engine.access.ns, atom_of[published.sources[i].source_id]),
            ).fetchone()[0]
            for i in (2, 3)
        }
        assert len(unkeyed) == 2 and keyed[0][0] not in unkeyed
        assert (
            engine.db.connection.execute(
                "SELECT count(*) FROM identity_events WHERE ns=?", (engine.access.ns,)
            ).fetchone()[0]
            == 0
        )
    finally:
        engine.close()


def test_alias_statement_links_a_unique_target_with_source_support(tmp_path):
    published = world_of(
        ("a", "Aleksander", "Aleksander parked"),
        ("b", "Alex", "Alex is the same person as Aleksander [alias:Aleksander]"),
    )
    engine, (mapping, identity) = load(tmp_path, published)
    try:
        assert identity["alias_links"] == 1 and identity["unresolved"] == []
        rows = engine.db.connection.execute(
            "SELECT decision,span_id FROM identity_events WHERE ns=?", (engine.access.ns,)
        ).fetchall()
        assert [r[0] for r in rows] == ["SAME_AS"]
        supporting_atom = engine.db.connection.execute(
            "SELECT id FROM atoms WHERE ns=? AND source_span_id=?",
            (engine.access.ns, rows[0][1]),
        ).fetchone()[0]
        # The claim cites the span of the source that states the alias, not the target's.
        assert mapping[supporting_atom] == published.sources[1].source_id
    finally:
        engine.close()


def test_alias_to_an_ambiguous_or_unknown_target_is_not_linked(tmp_path):
    published = world_of(
        ("a", "Sari", "Sari parked"),
        ("b", "Sari", "Sari parked too"),  # same name, no statement: a distractor
        ("c", "Dewi", "Dewi is Sari [alias:Sari]"),
        ("d", "Wati", "Wati is Nobody [alias:Nobody]"),
    )
    engine, (mapping, identity) = load(tmp_path, published)
    try:
        assert identity["alias_links"] == 0
        assert sorted(u["reason"] for u in identity["unresolved"]) == [
            "AMBIGUOUS_ALIAS_TARGET",
            "UNKNOWN_ALIAS_TARGET",
        ]
        assert (
            engine.db.connection.execute(
                "SELECT count(*) FROM identity_events WHERE ns=?", (engine.access.ns,)
            ).fetchone()[0]
            == 0
        )
        assert len(entities_for(engine, "Sari")) == 2
    finally:
        engine.close()


def test_registering_a_key_needs_admin(tmp_path):
    published = world_of(("a", "Sari", "Sari parked [key:acct-7]"))
    engine, (mapping, _identity) = load(tmp_path, published)
    try:
        reader = Access(engine.db, HostIdentity(engine.access.host.namespace, "writer-only"))
        engine.registry.access = reader  # a principal with no ADMIN grant
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            register_entity(engine.registry, next(iter(mapping)), "Sari", "acct-9")
    finally:
        engine.close()


def test_loader_imports_no_gold_world_or_evaluator_objects():
    tree = ast.parse(Path(entities.__file__).read_text(encoding="utf-8"))
    imported = {
        n.module if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in (n.names if isinstance(n, ast.Import) else [n])
    }
    forbidden = {"benchmark.fixtures.world", "benchmark.fixtures.scenarios", "benchmark.metrics"}
    assert not any(str(m).startswith(tuple(forbidden)) for m in imported if m)
    assert json.dumps(sorted(str(m) for m in imported))  # control: imports were actually parsed
    assert "benchmark.adapters.contracts" in imported


def test_alias_to_a_keyed_entity_resolves_through_its_provisional_twin(tmp_path):
    published = world_of(
        ("a", "Aleksander", "Aleksander parked [key:acct-1]"),
        ("b", "Alex", "Alex is Aleksander [alias:Aleksander]"),
    )
    engine, (_mapping, identity) = load(tmp_path, published)
    try:
        # The keyed entity and the provisional twin of its defining source are one occurrence.
        assert identity["alias_links"] == 1 and identity["unresolved"] == []
        right = engine.db.connection.execute(
            "SELECT e.external_key FROM identity_events i JOIN entities e ON e.ns=i.ns "
            "AND e.id=i.right_id WHERE i.ns=?",
            (engine.access.ns,),
        ).fetchone()[0]
        assert right == "acct-1"  # linked to the governed entity, not its twin
    finally:
        engine.close()
