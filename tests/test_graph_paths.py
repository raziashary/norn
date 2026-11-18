"""P06-T04: G1 bounded BFS and G2 damped best paths over the principal's eligible typed graph.

Hand-computed line, diamond, cycle, hub and ladder graphs prove direction, hops, scores, global
budgets and truncation flags; worlds that differ only by a denied private bridge prove that the
reader's traversal, counts and flags do not move; real public-v2 pilot cases prove the traversal
recovers the chains that the T02 derived graph states.
"""

import ast
import json
import math
from pathlib import Path

import pytest
from conftest import HOST
from test_graph_seeds import MARKER, basis_of, entity_with_key, loaded
from test_multihop_fixtures import first
from test_object_acl import LABEL, READER, fixed_clock, reader_of, source_of
from test_relation_extraction import built

from benchmark.adapters.baseline import interpret
from benchmark.fixtures.publication import publish
from benchmark.runs.graph_extraction import _entity_key, gold_edges
from norn.canonical.identity import review_identity
from norn.contracts.errors import NornError
from norn.extraction.relations import TRACK_TEXT, extract_relations
from norn.graph import bfs as bfs_module
from norn.graph import paths as paths_module
from norn.graph.adjacency import build_graph, write_edge
from norn.graph.bfs import (
    DEFAULT_RELATIONS,
    EDGE_BUDGET,
    FANOUT_LIMIT,
    HOP_LIMIT,
    NODE_BUDGET,
    TRANSITION_BUDGET,
    Limits,
    bfs,
    check_relations,
    path_candidates,
)
from norn.graph.contracts import EdgeSpec, NodeRef
from norn.graph.paths import DEFAULT_GAMMA, SCORE_SEMANTICS, damped_paths
from norn.graph.seeds import (
    EMPTY_SEED,
    ChannelResult,
    Vote,
    anchor_entity,
    construct_seed,
)
from norn.integration.engine import Engine
from norn.retrieval.seed_channels import build_seed

FROM = "2026-01-01T00:00:00Z"
REVISION = "test-paths-v1"
GAMMA = DEFAULT_GAMMA


def name_of(i: int) -> str:
    return f"n{i:07d}"


def world(engine, names, edges, relation="REQUIRES"):
    """One keyed source per name; each edge a->b is supported by the span of a's own source."""
    receipts = built(
        engine,
        [
            (
                n,
                f"Svc-{n}",
                f"Svc-{n} is registered and active. [key:svc.{n}]",
                f"svc.{n}",
            )
            for n in names
        ],
    )
    ent = {n: anchor_entity(engine.registry, receipts[n]["atom_ids"][0]) for n in names}
    span = {
        n: str(engine.registry.source_for_atom(receipts[n]["atom_ids"][0])["id"]) for n in names
    }
    link(engine, ent, span, edges, relation)
    return receipts, ent, span


def link(engine, ent, span, edges, relation="REQUIRES"):
    for a, b in edges:
        write_edge(
            engine.registry,
            EdgeSpec(
                relation,
                NodeRef("entity", ent[a]),
                NodeRef("entity", ent[b]),
                "DOCUMENT_ASSERTION",
                "*",
                (span[a],),
                FROM,
                REVISION,
            ),
        )


def seed_of(engine, *entities, weights=None):
    votes = tuple(Vote(e) for e in entities)
    channels = [ChannelResult("exact", "x-1", votes)]
    if weights:  # a second channel that favours the first entity, for unequal weights
        channels.append(ChannelResult("lexical", "l-1", tuple(Vote(e) for e in weights)))
    return construct_seed(engine.registry, channels, basis_of(engine))


def reached(traversal) -> dict[str, int]:
    return {s.node.id: s.hop for s in traversal.steps}


def counter(traversal, name: str) -> int:
    return dict(traversal.counters)[name]


# --- hand graphs: line, diamond, cycle -----------------------------------------------------------


def test_a_line_is_walked_forward_only_with_exact_hops_paths_and_sources(engine):
    names = [name_of(i) for i in range(4)]
    receipts, ent, _span = world(engine, names, list(zip(names, names[1:], strict=False)))
    graph = build_graph(engine.registry)
    a, b, c, d = (ent[n] for n in names)
    result = bfs(graph, seed_of(engine, a))
    assert reached(result) == {a: 0, b: 1, c: 2, d: 3}
    assert [s.node.id for s in result.steps] == [a, b, c, d]  # FIFO order
    assert result.complete and result.flags == () and result.unlinked == ()
    assert (counter(result, "nodes"), counter(result, "edges")) == (4, 3)
    assert counter(result, "transitions") == 3
    last = result.steps[-1]
    assert len(last.path) == 3 and last.origin == a and last.score is None
    assert set(last.path) == set(result.edges)
    # REQUIRES is directed: from the last node nothing is reachable, and the walk is not undone.
    assert reached(bfs(graph, seed_of(engine, d))) == {d: 0}
    # Hop limit: the target is missing and the result says it is truncated.
    short = bfs(graph, seed_of(engine, a), Limits(max_hops=2))
    assert d not in reached(short) and c in reached(short)
    assert short.flags == (HOP_LIMIT,) and not short.complete
    assert counter(short, "hop_cut_nodes") == 1
    exact_fit = bfs(graph, seed_of(engine, a), Limits(max_hops=3))
    assert d in reached(exact_fit) and exact_fit.flags == ()
    # Source recovery: the sources of the four entities, each reached with a reason.
    found = path_candidates(engine.registry, graph, result)
    expected = [source_of(engine, receipts[n]["event_id"]) for n in names]
    assert [x.source_id for x in found] == expected
    assert {x.kind for x in found} == {"DEFINING_SOURCE"}  # edge supports repeat these sources
    # G2: exact damped scores, out-degree one everywhere.
    paths = damped_paths(graph, seed_of(engine, a))
    scores = {s.node.id: s.score for s in paths.steps}
    assert scores == pytest.approx({a: 1.0, b: GAMMA, c: GAMMA**2, d: GAMMA**3})
    assert [s.node.id for s in paths.steps] == [a, b, c, d]  # best score first
    near = damped_paths(graph, seed_of(engine, a), Limits(max_hops=2))
    assert d not in reached(near) and c in reached(near)  # the hop bound holds for G2 as well
    assert near.flags == (HOP_LIMIT,) and counter(near, "hop_cut_nodes") == 1
    assert damped_paths(graph, seed_of(engine, a), Limits(max_hops=3)).flags == ()


def test_a_diamond_is_visited_once_and_g2_keeps_the_best_single_path_not_a_sum(engine):
    names = [name_of(i) for i in range(4)]
    a, b, c, d = names
    _r, ent, _s = world(engine, names, [(a, b), (a, c), (b, d), (c, d)])
    graph = build_graph(engine.registry)
    result = bfs(graph, seed_of(engine, ent[a]))
    assert reached(result) == {ent[a]: 0, ent[b]: 1, ent[c]: 1, ent[d]: 2}
    assert len(result.steps) == 4
    assert (counter(result, "edges"), counter(result, "transitions")) == (4, 4)  # c->d revisits d
    assert len(result.steps[-1].path) == 2
    paths = damped_paths(graph, seed_of(engine, ent[a]))
    score = {s.node.id: s.score for s in paths.steps}
    assert score[ent[b]] == pytest.approx(GAMMA * 0.5)  # out-degree two: p = 1/2
    assert score[ent[d]] == pytest.approx(GAMMA * 0.5 * GAMMA * 1.0)  # 0.245
    assert score[ent[d]] != pytest.approx(2 * GAMMA * 0.5 * GAMMA)  # not the summed 0.49
    step = next(s for s in paths.steps if s.node.id == ent[d])
    assert len(step.path) == 2 and step.score == score[ent[d]]
    assert paths.algorithm == "G2_DAMPED_PATH" and paths.gamma == GAMMA
    assert SCORE_SEMANTICS == "DIAGNOSTIC_BEST_PATH_NOT_PPR_NOT_CAUSAL"


def test_a_cycle_terminates_and_never_revisits_or_overwrites_the_seed(engine):
    names = [name_of(i) for i in range(3)]
    a, b, c = names
    _r, ent, _s = world(engine, names, [(a, b), (b, c), (c, a)])
    graph = build_graph(engine.registry)
    result = bfs(graph, seed_of(engine, ent[a]))
    assert reached(result) == {ent[a]: 0, ent[b]: 1, ent[c]: 2}
    assert counter(result, "transitions") == 3 and result.complete  # c->a is examined, not walked
    paths = damped_paths(graph, seed_of(engine, ent[a]))
    root = next(s for s in paths.steps if s.node.id == ent[a])
    assert root.hop == 0 and root.score == 1.0 and root.path == ()
    assert all(len(set(s.path)) == len(s.path) for s in paths.steps)


# --- hubs, global budgets and truncation ---------------------------------------------------------


def hub(engine, fan: int):
    names = [name_of(i) for i in range(fan + 1)]
    receipts, ent, span = world(engine, names, [(names[0], n) for n in names[1:]])
    return names, ent, build_graph(engine.registry)


def test_a_hub_beyond_the_fanout_is_cut_flagged_and_still_degree_normalised(engine):
    names, ent, graph = hub(engine, 40)
    root = ent[names[0]]
    cut = bfs(graph, seed_of(engine, root))
    assert len(cut.steps) == 1 + 32 and cut.flags == (FANOUT_LIMIT,)
    assert counter(cut, "fanout_cut_arcs") == 8 and counter(cut, "transitions") == 32
    again = bfs(graph, seed_of(engine, root))
    assert [s.node.id for s in again.steps] == [s.node.id for s in cut.steps]  # same 32, always
    wide = bfs(graph, seed_of(engine, root), Limits(fanout=40))
    assert len(wide.steps) == 41 and wide.flags == () and counter(wide, "fanout_cut_arcs") == 0
    paths = damped_paths(graph, seed_of(engine, root))
    kids = [s for s in paths.steps if s.hop == 1]
    assert len(kids) == 32 and paths.flags == (FANOUT_LIMIT,)
    assert all(s.score == pytest.approx(GAMMA / 40) for s in kids)  # full out-degree, not 32


def test_unique_node_edge_and_transition_budgets_are_global_across_seeds_and_layers(engine):
    names = [name_of(i) for i in range(6)]
    a1, a2, a3, b1, b2, b3 = names
    _r, ent, _s = world(engine, names, [(a1, a2), (a2, a3), (b1, b2), (b2, b3)])
    graph = build_graph(engine.registry)
    both = seed_of(engine, ent[a1], ent[b1])
    full = bfs(graph, both)
    assert len(full.steps) == 6 and full.complete
    tight = bfs(graph, both, Limits(max_nodes=4))  # four nodes in all, not four per seed
    assert counter(tight, "nodes") == 4 and NODE_BUDGET in tight.flags
    assert {s.node.id for s in tight.steps} == {ent[a1], ent[b1], ent[a2], ent[b2]}
    edges = bfs(graph, both, Limits(max_edges=1))
    assert counter(edges, "edges") == 1 and EDGE_BUDGET in edges.flags
    work = bfs(graph, both, Limits(max_transitions=3))
    assert counter(work, "transitions") == 3 and work.flags == (TRANSITION_BUDGET,)
    assert counter(work, "nodes") < 6 and counter(work, "nodes") <= 5
    for limit in (Limits(max_nodes=4), Limits(max_edges=1), Limits(max_transitions=3)):
        assert not damped_paths(graph, both, limit).complete


def test_g2_repeated_work_is_budgeted_even_when_every_edge_was_seen_before(engine):
    names = [name_of(i) for i in range(4)]
    h, m, low, c = names[0], names[1], names[2], names[3]
    d = name_of(4)
    _r, ent, _s = world(engine, names + [d], [(h, m), (m, c), (low, c), (c, d)])
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[h], ent[low], weights=[ent[h]])  # H heavier than L
    weights = seed.vector()
    assert weights[ent[h]] > weights[ent[low]] > 0
    paths = damped_paths(graph, seed)
    assert (counter(paths, "edges"), counter(paths, "transitions")) == (4, 5)  # c->d twice
    top = next(s for s in paths.steps if s.node.id == ent[d])
    assert top.hop == 3 and top.origin == ent[h]  # the heavier seed's longer path wins
    assert top.score == pytest.approx(weights[ent[h]] * GAMMA**3)
    low_c = weights[ent[low]] * GAMMA
    assert next(s for s in paths.steps if s.node.id == ent[c]).score > low_c  # c was improved
    capped = damped_paths(graph, seed, Limits(max_transitions=4))
    assert capped.flags == (TRANSITION_BUDGET,) and counter(capped, "transitions") == 4
    assert counter(capped, "nodes") <= counter(paths, "nodes")
    # Control: breadth-first examines each arc once, so the same graph costs four transitions.
    assert counter(bfs(graph, seed), "transitions") == 4


def test_g2_a_worse_path_met_later_never_replaces_a_better_one(engine):
    names = [name_of(i) for i in range(6)]
    _r, ent, span = world(engine, names, [])
    first_mid, second_mid = sorted(names[1:3], key=lambda n: ent[n])  # processed in this order
    s, t, u, v = names[0], names[3], names[4], names[5]
    link(
        engine,
        ent,
        span,
        [(s, first_mid), (s, second_mid), (first_mid, t), (second_mid, t)]
        + [(second_mid, u), (second_mid, v)],  # the later middle node has out-degree three
    )
    graph = build_graph(engine.registry)
    result = damped_paths(graph, seed_of(engine, ent[s]))
    step = next(x for x in result.steps if x.node.id == ent[t])
    assert step.score == pytest.approx(GAMMA * 0.5 * GAMMA)  # via the out-degree-one middle node
    assert step.parent == NodeRef("entity", ent[first_mid])


def test_g2_a_layer_is_relaxed_from_the_paths_of_the_previous_layer_only(engine):
    names = [name_of(i) for i in range(3)]
    _r, ent, span = world(engine, names, [])
    heavy, light = sorted(names[:2], key=lambda n: ent[n])  # heavy is expanded first
    t = names[2]
    link(engine, ent, span, [(heavy, light), (light, t)])
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[heavy], ent[light], weights=[ent[heavy]])
    weights = seed.vector()
    assert weights[ent[heavy]] > weights[ent[light]] > 0
    one = damped_paths(graph, seed, Limits(max_hops=1))
    assert all(x.hop <= 1 for x in one.steps)  # no path longer than the limit sneaks in
    reached_t = next(x for x in one.steps if x.node.id == ent[t])
    assert reached_t.hop == 1 and reached_t.origin == ent[light]
    assert reached_t.score == pytest.approx(weights[ent[light]] * GAMMA)
    two = damped_paths(graph, seed, Limits(max_hops=2))
    better = next(x for x in two.steps if x.node.id == ent[t])
    assert better.hop == 2 and better.origin == ent[heavy]  # the longer, heavier path wins
    assert better.score == pytest.approx(weights[ent[heavy]] * GAMMA**2)


def test_seeds_with_nothing_to_walk_are_explicit_and_never_invented_elsewhere(engine):
    names = [name_of(i) for i in range(3)]
    a, b, lonely = names
    _r, ent, _s = world(engine, names, [(a, b)])
    graph = build_graph(engine.registry)
    isolated = bfs(graph, seed_of(engine, ent[lonely]))  # a keyed entity with no edge: not a node
    assert isolated.steps == () and isolated.unlinked == (ent[lonely],)
    mixed = bfs(graph, seed_of(engine, ent[a], ent[lonely]))
    assert reached(mixed) == {ent[a]: 0, ent[b]: 1} and mixed.unlinked == (ent[lonely],)
    empty = construct_seed(
        engine.registry, [ChannelResult("lexical", "l", (), "NO_MATCH")], basis_of(engine)
    )
    for run in (bfs(graph, empty), damped_paths(graph, empty)):
        assert run.steps == () and EMPTY_SEED in run.flags and not run.complete
    with pytest.raises(NornError, match="INVALID_SEED"):
        bfs(graph, object())  # type: ignore[arg-type]


def test_limits_gamma_and_allowlists_are_validated(engine):
    names = [name_of(i) for i in range(2)]
    _r, ent, _s = world(engine, names, [(names[0], names[1])])
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[names[0]])
    for bad in (0, -1, 17):
        with pytest.raises(NornError, match="INVALID_TRAVERSAL_LIMIT"):
            Limits(max_hops=bad)
    with pytest.raises(NornError, match="INVALID_TRAVERSAL_LIMIT"):
        Limits(fanout=True)  # type: ignore[arg-type]
    for gamma in (0.0, 1.0, -0.5, 2.0, math.nan, math.inf, 1):
        with pytest.raises(NornError, match="INVALID_GAMMA"):
            damped_paths(graph, seed, gamma=gamma)  # type: ignore[arg-type]
    assert damped_paths(graph, seed, gamma=0.5).steps[1].score == pytest.approx(0.5)
    for relations in (frozenset({"CONTRADICTS"}), frozenset({"NOT_A_RELATION"})):
        with pytest.raises(NornError, match="UNSUPPORTED_RELATION_ALLOWLIST"):
            bfs(graph, seed, relations=relations)
    with pytest.raises(NornError, match="EMPTY_RELATION_ALLOWLIST"):
        bfs(graph, seed, relations=frozenset())
    assert check_relations(DEFAULT_RELATIONS) == ("IDENTITY_LINK", "REQUIRES")
    cancelled = []

    def stop() -> None:
        cancelled.append(1)
        raise NornError("QUERY_CANCELLED")

    with pytest.raises(NornError, match="QUERY_CANCELLED"):
        bfs(graph, seed, checkpoint=stop)
    with pytest.raises(NornError, match="QUERY_CANCELLED"):
        damped_paths(graph, seed, checkpoint=stop)
    assert len(cancelled) == 2


# --- typed policy: identity links, hypotheses, structural edges ---------------------------------


def test_a_reviewed_identity_link_is_crossed_both_ways_and_a_hypothesis_is_never_followed(engine):
    names = [name_of(i) for i in range(4)]
    a, alias, c, d = names
    receipts, ent, span = world(engine, names, [(alias, c)])
    atoms = {n: receipts[n]["atom_ids"][0] for n in names}
    graph = build_graph(engine.registry)
    assert ent[c] not in reached(bfs(graph, seed_of(engine, ent[a])))  # similar names never merge
    review_identity(engine.registry, ent[a], ent[alias], "SAME_AS", atoms[a])
    # A hypothesised causal edge between events must not carry any traversal.
    write_edge(
        engine.registry,
        EdgeSpec(
            "HYPOTHESIZES_CAUSE",
            NodeRef("event", receipts[a]["event_id"]),
            NodeRef("event", receipts[d]["event_id"]),
            "HYPOTHESIS",
            "*",
            (span[a],),
            FROM,
            REVISION,
        ),
    )
    linked = build_graph(engine.registry)
    forward = bfs(linked, seed_of(engine, ent[a]))
    assert reached(forward) == {ent[a]: 0, ent[alias]: 1, ent[c]: 2}
    backward = bfs(linked, seed_of(engine, ent[alias]))
    assert ent[a] in reached(backward) and ent[c] in reached(backward)
    assert ent[d] not in reached(forward) and ent[d] not in reached(backward)
    assert not any(s.node.kind != "entity" for s in forward.steps)
    # The identity step is an edge a reader can open: its supports are the reviewing atom's source.
    link_step = next(s for s in forward.steps if s.node.id == ent[alias])
    assert linked.edge(link_step.edge_id).relation == "IDENTITY_LINK"
    # Only when a caller narrows the allowlist to identity alone is the REQUIRES step dropped.
    only_identity = bfs(linked, seed_of(engine, ent[a]), relations=frozenset({"IDENTITY_LINK"}))
    assert reached(only_identity) == {ent[a]: 0, ent[alias]: 1}
    assert ent[c] not in reached(only_identity)


# --- a denied bridge is never walked and moves no count, flag or byte ---------------------------


def private_bridge_world(tmp_path, name, *, with_private: bool, private_first: bool):
    """Public a->b and a->x; optionally a private entity P bridging b->P->c (P's source is
    label-denied to the reader), so c is reachable only through P."""
    engine = Engine(tmp_path / name, HOST, create=True, clock=fixed_clock)
    engine.access.bootstrap()
    names = [name_of(i) for i in range(4)]  # a b x c
    a, b, x, c = names
    p = name_of(9)
    if with_private and private_first:
        world(engine, [p], [])
    receipts, ent, span = world(engine, names, [(a, b), (a, x)])
    if with_private and not private_first:
        world(engine, [p], [])
    private_entity = private_source = None
    if with_private:
        private_entity, private_span, private_source = (
            str(v)
            for v in engine.db.connection.execute(
                "SELECT e.id, e.provisional_span_id, v.source_id FROM entities e "
                "JOIN source_spans s ON s.id=e.provisional_span_id "
                "JOIN source_versions v ON v.id=s.version_id WHERE e.external_key=?",
                (f"svc.{p}",),
            ).fetchone()
        )
        for tail, head in ((ent[b], private_entity), (private_entity, ent[c])):
            write_edge(
                engine.registry,
                EdgeSpec(
                    "REQUIRES",
                    NodeRef("entity", tail),
                    NodeRef("entity", head),
                    "DOCUMENT_ASSERTION",
                    "*",
                    (private_span,),
                    FROM,
                    REVISION,
                ),
            )
    engine.access.grant(READER, "READ")
    if with_private:
        engine.access.set_scope(private_source, LABEL)
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
    return engine, ent, private_entity, private_source


def test_a_denied_bridge_is_never_walked_and_adds_no_count_flag_or_byte(tmp_path):
    runs = []
    for index, (with_private, early) in enumerate(((False, False), (True, False), (True, True))):
        engine, ent, private, private_source = private_bridge_world(
            tmp_path, f"w{index}", with_private=with_private, private_first=early
        )
        with engine:
            names = list(ent)
            a, b, x, c = (ent[n] for n in names)
            owner_graph = build_graph(engine.registry)
            owner = bfs(owner_graph, seed_of(engine, a))
            with reader_of(engine) as reader:
                graph = build_graph(reader.registry)
                seed = construct_seed(
                    reader.registry,
                    [ChannelResult("exact", "x-1", (Vote(a),))],
                    basis_of(reader),
                )
                tight = Limits(max_nodes=2)
                results = [
                    bfs(graph, seed),
                    bfs(graph, seed, tight),
                    damped_paths(graph, seed),
                    damped_paths(graph, seed, tight),
                ]
                runs.append([r.digest() for r in results])
                plain = results[0]
                assert reached(plain) == {a: 0, b: 1, x: 1}  # c sits behind the denied bridge
                assert c not in reached(plain) and plain.complete
                assert results[1].flags and not results[1].complete  # a bound binds identically
                if private is not None:
                    assert private in reached(owner) and c in reached(owner)  # positive control
                    assert private not in reached(plain)
                    assert private not in json.dumps([r.payload() for r in results])
                    sources = path_candidates(reader.registry, graph, plain)
                    assert private_source not in {s.source_id for s in sources}
                    # A traversal handed in from a more privileged principal is not trusted: the
                    # defining source of its private root is checked against the caller's rights.
                    root_only = bfs(owner_graph, seed_of(engine, private), Limits(max_nodes=1))
                    assert [s.node.id for s in root_only.steps] == [private]
                    own = path_candidates(engine.registry, owner_graph, root_only)
                    assert private_source in {s.source_id for s in own}  # positive control
                    assert path_candidates(reader.registry, graph, root_only) == ()
    assert runs[0] == runs[1] == runs[2]  # four traversals, identical bytes in all three worlds


# --- the consumer: real pilot cases through seeds, the derived graph and both traversals --------


def key_reach(engine, graph, traversal) -> set[str]:
    keys = set()
    for step in traversal.steps:
        key = _entity_key(engine, graph, step.node.id)
        if key is not None:
            keys.add(key)
    return keys


def gold_reach(case, published_ids, registered: set[str], start: str, hops: int) -> set[str]:
    edges, _unpublished = gold_edges(case, published_ids)
    edges = [e for e in edges if e.tail in registered and e.head in registered]
    frontier, seen = {start}, {start}
    for _ in range(hops):
        frontier = {e.head for e in edges if e.tail in frontier} - seen
        seen |= frontier
    return seen


@pytest.mark.parametrize("family", ["M1", "M2", "M3", "M5"])
def test_from_the_chain_root_the_traversals_recover_what_the_derived_graph_states(tmp_path, family):
    template = first(family)
    engine, published = loaded(tmp_path, template)
    with engine:
        extract_relations(engine.registry, TRACK_TEXT)
        graph = build_graph(engine.registry)
        root_key = next(k for h, _n, k in template.graph.nodes if h == template.graph.seed_node)
        root = entity_with_key(engine, root_key)
        seed = seed_of(engine, root)
        limits = Limits(max_hops=8, max_nodes=2000, max_transitions=100_000)
        ids = {s.source_id for s in publish(template.case, (MARKER,)).sources}
        registered = {
            k for (k,) in engine.db.connection.execute("SELECT external_key FROM entities") if k
        }
        expected = gold_reach(template, ids, registered, root_key, 8)
        assert len(expected) >= 3  # a real chain, not just the root
        for run in (bfs(graph, seed, limits), damped_paths(graph, seed, limits)):
            assert run.complete and key_reach(engine, graph, run) >= expected - {None}
            found = path_candidates(engine.registry, graph, run)
            assert found and all(
                engine.registry.access.eligible("READ", c.source_id) for c in found
            )
        # The conventional seed of the actual query feeds the same traversal without error.
        conventional = build_seed(engine, interpret(published, "R0"), ("exact", "lexical"))
        for run in (bfs(graph, conventional), damped_paths(graph, conventional)):
            assert run.seed_digest == conventional.digest() and run.algorithm.startswith("G")


# --- isolation ----------------------------------------------------------------------------------


def test_the_traversal_modules_import_no_gold_evaluator_retrieval_or_randomness():
    forbidden = ("benchmark", "random", "socket", "urllib", "norn.retrieval", "norn.embedding")
    for module in (bfs_module, paths_module):
        path = Path(module.__file__)
        imported = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert not [m for m in imported if m.startswith(forbidden)], (path.name, imported)
        assert "norn.graph.adjacency" in imported or "norn.graph.bfs" in imported


def test_a_traversal_is_deterministic_and_reloads_to_the_same_bytes(tmp_path):
    root = tmp_path / "store"
    names = [name_of(i) for i in range(5)]
    digests = []
    with Engine(root, HOST, create=True, clock=fixed_clock) as engine:
        engine.access.bootstrap()
        _r, ent, _s = world(
            engine,
            names,
            [
                (names[0], names[1]),
                (names[0], names[2]),
                (names[1], names[3]),
                (names[2], names[3]),
                (names[3], names[4]),
            ],
        )
        seed = seed_of(engine, ent[names[0]])
        graph = build_graph(engine.registry)
        digests = [bfs(graph, seed).digest(), damped_paths(graph, seed).digest()]
        assert digests == [bfs(graph, seed).digest(), damped_paths(graph, seed).digest()]
    with Engine(root, HOST, clock=fixed_clock) as reopened:
        again = build_graph(reopened.registry)
        assert [bfs(again, seed).digest(), damped_paths(again, seed).digest()] == digests
