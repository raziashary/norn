"""P06-T04 to T06: the real M4 private-bridge control for every graph walk.

The M4 pilot clusters hold evaluator-side private sources (a private shortcut in the positive
variant, the only path in the missing variant). Here they are loaded under a label that the reader
may not read, the owner derives the typed graph from everything, and the reader's BFS, damped best
paths, PPR and heat kernel must be byte-identical to the same walks in a world
that never held the private sources: no private edge, node, source, count, flag or byte moves.
The owner, who may read them, sees a different graph, so the control can fail.
"""

import json
from dataclasses import replace

import pytest
from test_graph_seeds import MARKER, basis_of, entity_with_key
from test_multihop_fixtures import first
from test_object_acl import LABEL

from benchmark.adapters.baseline import host, load_sources
from benchmark.adapters.common import replay_clock
from benchmark.fixtures.publication import publish
from norn.contracts.errors import NornError
from norn.extraction.relations import TRACK_TEXT, extract_relations
from norn.graph.adjacency import build_graph
from norn.graph.bfs import Limits, bfs, path_candidates
from norn.graph.heat import HeatLimits, heat
from norn.graph.paths import damped_paths
from norn.graph.ppr import PprLimits, activation_candidates, ppr
from norn.graph.seeds import ChannelResult, Vote, construct_seed
from norn.integration.engine import Engine

WALK = Limits(max_hops=8, max_nodes=2000, max_edges=10_000, max_transitions=100_000)


def m4_world(tmp_path, name, template, *, with_private: bool):
    """Public sources always; the private ones (made loadable by the benchmark principal) only
    when asked. The edges are derived from everything the principal holds."""
    published = publish(template.case, (MARKER,))
    principal = published.query.principal
    extra = tuple(
        replace(p, allowed_principals=(principal,)) for p in template.graph.private_sources
    )
    given = replace(published, sources=published.sources + (extra if with_private else ()))
    clock = replay_clock(given)
    engine = Engine(tmp_path / name, host(given), create=True, clock=clock)
    engine.access.bootstrap()
    mapping, _identity = load_sources(engine, given, clock)
    extract_relations(engine.registry, TRACK_TEXT)  # the owner derives from everything it holds
    private_ids = {p.source_id for p in extra} if with_private else set()
    stored = {
        str(engine.registry.source_for_atom(atom)["source_id"])
        for atom, published_id in mapping.items()
        if published_id in private_ids
    }
    assert len(stored) == len(private_ids) == (len(extra) if with_private else 0)
    return engine, stored


def deny(engine, stored):
    """Label the private sources and take the label away from the benchmark principal."""
    for source in sorted(stored):
        engine.access.set_scope(source, LABEL)
    if stored:
        engine.access.grant(engine.access.host.principal, "READ", revoke=True, scope=LABEL)


def seed_for_id(engine, entity):
    channels = [ChannelResult("exact", "x-1", (Vote(entity),))]
    return construct_seed(engine.registry, channels, basis_of(engine))


def walks(graph, seed):
    return {
        "bfs": bfs(graph, seed, WALK),
        "paths": damped_paths(graph, seed, WALK),
        "ppr": ppr(graph, seed, PprLimits(max_iterations=200, tolerance=1e-9)),
        "ppr_capped": ppr(graph, seed, PprLimits(max_nodes=3)),
        "heat": heat(graph, seed, HeatLimits(max_terms=200, tail_tolerance=1e-9)),
        "heat_capped": heat(graph, seed, HeatLimits(max_nodes=3, max_transitions=40)),
    }


@pytest.mark.parametrize("variant", ["positive", "missing"])
def test_a_denied_real_m4_private_source_moves_no_byte_in_any_walk(tmp_path, variant):
    template = first("M4", variant)
    root_key = next(k for h, _n, k in template.graph.nodes if h == template.graph.seed_node)
    private_values = [p.observation.value for p in template.graph.private_sources]
    assert private_values and all(private_values)
    digests, owners, graphs = {}, {}, {}
    for label, with_private in (("plain", False), ("private", True)):
        engine, stored = m4_world(tmp_path, label, template, with_private=with_private)
        with engine:
            root = entity_with_key(engine, root_key)

            def seed_for(registry, basis, root=root):
                channels = [ChannelResult("exact", "x-1", (Vote(root),))]
                return construct_seed(registry, channels, basis)

            # Before the label the principal may read everything it loaded: the owner's view.
            owner_graph = build_graph(engine.registry)
            owners[label] = walks(owner_graph, seed_for(engine.registry, basis_of(engine)))
            graphs[label] = owner_graph
            private_edges = {
                e.id
                for e in owner_graph.edges
                if e.relation == "REQUIRES" and any(x.source_id in stored for x in e.supports)
            }
            heads = sorted({e.source.id for e in owner_graph.edges if e.id in private_edges})
            if with_private:
                assert private_edges and heads  # the private chain is a real part of the graph
                private_seed = construct_seed(
                    engine.registry,
                    [ChannelResult("exact", "x-1", tuple(Vote(h) for h in heads))],
                    basis_of(engine),
                )
                started = walks(owner_graph, private_seed)
                assert set(started["bfs"].edges) & private_edges  # the owner walks it
                assert any(e.node.id in heads for e in started["ppr"].entries)
            deny(engine, stored)
            graph = build_graph(engine.registry)  # the same principal, now denied the label
            results = walks(graph, seed_for(engine.registry, basis_of(engine)))
            digests[label] = {name: r.digest() for name, r in results.items()}
            encoded = json.dumps([r.payload() for r in results.values()])
            assert all(value not in encoded for value in private_values)
            assert all(source not in encoded for source in stored)
            if with_private:
                for head in heads:  # a denied entity cannot seed, and says what an unknown one says
                    with pytest.raises(NornError) as denied:
                        seed_for_id(engine, head)
                    with pytest.raises(NornError) as unknown:
                        seed_for_id(engine, "entity_" + "0" * 64)
                    assert denied.value.code == unknown.value.code
            proposed = {
                c.source_id for c in path_candidates(engine.registry, graph, results["bfs"])
            } | {
                c.source_id
                for run in ("ppr", "heat")
                for c in activation_candidates(engine.registry, graph, results[run])
            }
            assert not proposed & stored
    assert digests["plain"] == digests["private"]  # six walks, identical bytes in both worlds
    # Positive control: before the label the principal reads them, so its graph and bytes differ.
    plain_ids = {e.id for e in graphs["plain"].edges}
    assert plain_ids < {e.id for e in graphs["private"].edges}
    assert graphs["private"].digest() != graphs["plain"].digest()
