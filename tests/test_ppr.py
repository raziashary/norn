"""P06-T05: G3 seeded personalised PageRank over the principal's eligible typed graph.

An exact rational oracle (dense linear solve and exact power steps over fractions, written from
the mathematical contract and sharing no code with the implementation) checks the sparse floating
point iteration on line, cycle, diamond, dangling, hub, weighted and budget-cut graphs; budgets,
mass, residual and truncation are asserted as counted over the eligible graph only; worlds that
differ only by a denied private bridge must give the reader identical bytes; real public-v2 pilot
chains prove the consumer path from seeds through the derived graph to proposed sources.
"""

import ast
import json
import math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import pytest
from conftest import HOST
from test_graph_paths import (
    FROM,
    REVISION,
    gold_reach,
    link,
    name_of,
    private_bridge_world,
    seed_of,
    world,
)
from test_graph_seeds import MARKER, basis_of, entity_with_key, loaded
from test_multihop_fixtures import first
from test_object_acl import fixed_clock, reader_of

from benchmark.adapters.baseline import interpret
from benchmark.fixtures.publication import publish
from benchmark.runs.graph_extraction import _entity_key
from norn.canonical.identity import review_identity
from norn.contracts.errors import NornError
from norn.extraction.relations import TRACK_TEXT, extract_relations
from norn.graph import ppr as ppr_module
from norn.graph.adjacency import build_graph, write_edge
from norn.graph.bfs import (
    EDGE_BUDGET,
    NO_LINKED_ANCHOR,
    NODE_BUDGET,
    TRANSITION_BUDGET,
    Limits,
    bfs,
)
from norn.graph.contracts import EdgeSpec, NodeRef
from norn.graph.ppr import (
    DEFAULT_ALPHA,
    NOT_CONVERGED,
    SCORE_SEMANTICS,
    PprLimits,
    activation_candidates,
    ppr,
    relation_weights,
)
from norn.graph.seeds import EMPTY_SEED, ChannelResult, Vote, construct_seed
from norn.integration.engine import Engine
from norn.retrieval.seed_channels import build_seed

ALPHA = Fraction(7, 10)
TIGHT = PprLimits(max_iterations=400, tolerance=1e-13)


class Oracle:
    """Exact fractions: the dense solve of (I - a P'^T) x = (1 - a) s and exact power steps.

    P' is row-stochastic over the full eligible out-weight; arcs into nodes outside ``keep`` are
    cut (their mass leaves), and a node with no allowed arc returns its mass to the seed."""

    def __init__(self, arcs, start, keep=None, alpha=ALPHA):
        self.alpha, self.arcs = alpha, arcs
        total = sum(start.values())
        self.start = {n: Fraction(w) / total for n, w in start.items()}
        nodes = {n for a in arcs for n in a[:2]} | set(self.start)
        self.keep = sorted(nodes if keep is None else keep)
        self.total = defaultdict(Fraction)
        for u, _v, w in arcs:
            self.total[u] += Fraction(w)

    def matrix(self):
        index = {n: i for i, n in enumerate(self.keep)}
        size = len(index)
        m = [[Fraction(int(i == j)) for j in range(size)] for i in range(size)]
        for u, v, w in self.arcs:
            if u in index and v in index:
                m[index[v]][index[u]] -= self.alpha * Fraction(w) / self.total[u]
        for u in self.keep:
            if self.total[u] == 0:
                for node, share in self.start.items():
                    m[index[node]][index[u]] -= self.alpha * share
        return index, m

    def solve(self):
        index, m = self.matrix()
        size = len(index)
        rhs = [(1 - self.alpha) * self.start.get(n, Fraction(0)) for n in self.keep]
        aug = [[*row, rhs[i]] for i, row in enumerate(m)]
        for col in range(size):
            pivot = next(r for r in range(col, size) if aug[r][col] != 0)
            aug[col], aug[pivot] = aug[pivot], aug[col]
            lead = aug[col][col]
            aug[col] = [x / lead for x in aug[col]]
            for r in range(size):
                if r != col and aug[r][col] != 0:
                    f = aug[r][col]
                    aug[r] = [x - f * y for x, y in zip(aug[r], aug[col], strict=True)]
        return {n: aug[index[n]][size] for n in self.keep}

    def steps(self, count):
        state = dict(self.start)
        for _ in range(count):
            nxt = defaultdict(Fraction)
            dangling = Fraction(0)
            for node, held in state.items():
                if self.total[node] == 0:
                    dangling += held
            for u, v, w in self.arcs:
                if v in self.keep and u in state and self.total[u] > 0:
                    nxt[v] += self.alpha * state[u] * Fraction(w) / self.total[u]
            for node, share in self.start.items():
                nxt[node] += ((1 - self.alpha) + self.alpha * dangling) * share
            state = dict(nxt)
        return state


def activation_of(result):
    return {e.node.id: e.activation for e in result.entries}


def assert_matches(result, exact, tolerance=1e-9):
    got = activation_of(result)
    for node in set(exact) | set(got):
        assert got.get(node, 0.0) == pytest.approx(float(exact.get(node, 0)), abs=tolerance), node


def mass(result, name):
    return dict(result.mass)[name]


def counter(result, name):
    return dict(result.counters)[name]


def arcs_of_names(ent, edges, weight=1):
    return [(ent[a], ent[b], weight) for a, b in edges]


# --- exact oracle: line, cycle, diamond, dangling, hub ------------------------------------------


def test_a_line_with_a_dangling_end_matches_the_oracle_and_the_hand_value(engine):
    names = [name_of(i) for i in range(3)]
    a, b, c = names
    _r, ent, _s = world(engine, names, [(a, b), (b, c)])
    graph = build_graph(engine.registry)
    arcs = arcs_of_names(ent, [(a, b), (b, c)])
    result = ppr(graph, seed_of(engine, ent[a]), TIGHT)
    assert_matches(result, Oracle(arcs, {ent[a]: 1}).solve())
    got = activation_of(result)
    assert got[ent[a]] == pytest.approx(0.3 / (1 - 0.7**3))  # 300/657, by hand
    assert got[ent[b]] == pytest.approx(0.7 * got[ent[a]])
    assert got[ent[c]] == pytest.approx(0.7 * got[ent[b]])
    assert result.converged and result.complete and result.flags == ()
    assert mass(result, "activation") == pytest.approx(1.0) and mass(result, "truncated") == 0.0
    assert mass(result, "dangling_restarted") > 0  # c returns its mass to the seed
    assert mass(result, "max_mass_error") <= 1e-9
    # The default envelope converges to within its own bound of the exact fixed point.
    default = ppr(graph, seed_of(engine, ent[a]))
    exact = Oracle(arcs, {ent[a]: 1}).solve()
    distance = sum(abs(v - float(exact[n])) for n, v in activation_of(default).items())
    assert default.error_bound is not None and distance <= default.error_bound + 1e-12
    assert default.alpha == DEFAULT_ALPHA == 0.7 and default.converged and default.complete
    assert default.limits.max_iterations == 60
    # Why 60: at the first answer of 40 iterations the same chain stops at residual 1.3e-6.
    forty = ppr(graph, seed_of(engine, ent[a]), PprLimits(max_iterations=40))
    assert not forty.converged and forty.residual is not None and forty.residual > 1e-6


def test_the_transition_matrix_is_transposed_correctly_and_restart_is_the_seed(engine):
    names = [name_of(i) for i in range(3)]
    a, b, c = names
    _r, ent, _s = world(engine, names, [(a, b), (b, c)])
    graph = build_graph(engine.registry)
    # From the sink the walk never goes backwards: everything stays on the seed.
    sink = ppr(graph, seed_of(engine, ent[c]), TIGHT)
    assert activation_of(sink) == pytest.approx({ent[c]: 1.0})
    # From the middle only the forward neighbour gains; the upstream node gets nothing.
    middle = ppr(graph, seed_of(engine, ent[b]), TIGHT)
    got = activation_of(middle)
    assert ent[a] not in got and got[ent[c]] == pytest.approx(0.7 * got[ent[b]])
    assert got[ent[b]] == pytest.approx(0.3 / (1 - 0.7**2))
    # alpha 0 is pure restart: the seed is the answer after one step.
    only = ppr(graph, seed_of(engine, ent[a]), alpha=0.0)
    assert activation_of(only) == pytest.approx({ent[a]: 1.0}) and only.converged


def test_a_cycle_has_no_dangling_mass_and_matches_the_oracle(engine):
    names = [name_of(i) for i in range(3)]
    a, b, c = names
    edges = [(a, b), (b, c), (c, a)]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    result = ppr(graph, seed_of(engine, ent[b]), TIGHT)
    assert_matches(result, Oracle(arcs_of_names(ent, edges), {ent[b]: 1}).solve())
    assert activation_of(result)[ent[b]] == pytest.approx(0.3 / (1 - 0.7**3))
    assert mass(result, "dangling_restarted") == 0.0 and result.complete
    assert mass(result, "activation") == pytest.approx(1.0)


def test_a_diamond_adds_up_both_walks_where_the_best_path_keeps_one(engine):
    names = [name_of(i) for i in range(4)]
    a, b, c, d = names
    edges = [(a, b), (a, c), (b, d), (c, d)]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    result = ppr(graph, seed_of(engine, ent[a]), TIGHT)
    assert_matches(result, Oracle(arcs_of_names(ent, edges), {ent[a]: 1}).solve())
    got = activation_of(result)
    assert got[ent[d]] == pytest.approx(2 * 0.7 * got[ent[b]])  # both branches reach d
    assert got[ent[b]] == got[ent[c]] and got[ent[d]] > got[ent[b]]
    assert (counter(result, "nodes"), counter(result, "edges")) == (4, 4)


def test_a_hub_with_dangling_leaves_matches_the_oracle(engine):
    names = [name_of(i) for i in range(41)]
    hub = names[0]
    edges = [(hub, n) for n in names[1:]]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    result = ppr(graph, seed_of(engine, ent[hub]), TIGHT)
    assert_matches(result, Oracle(arcs_of_names(ent, edges), {ent[hub]: 1}).solve())
    got = activation_of(result)
    leaves = [v for n, v in got.items() if n != ent[hub]]
    assert len(leaves) == 40 and all(v == pytest.approx(0.7 * got[ent[hub]] / 40) for v in leaves)
    assert result.complete and counter(result, "nodes") == 41


def test_several_seeds_with_unequal_weights_match_the_oracle(engine):
    names = [name_of(i) for i in range(4)]
    a, b, c, d = names
    edges = [(a, c), (b, c), (c, d)]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[a], ent[b], weights=[ent[a]])
    vector = seed.vector()
    assert vector[ent[a]] > vector[ent[b]] > 0
    result = ppr(graph, seed, TIGHT)
    exact = Oracle(arcs_of_names(ent, edges), {ent[a]: vector[ent[a]], ent[b]: vector[ent[b]]})
    assert_matches(result, exact.solve())
    assert result.seed_digest == seed.digest()


def test_relation_weights_scale_the_rows_and_are_validated(engine):
    names = [name_of(i) for i in range(3)]
    a, b, c = names
    _r, ent, span = world(engine, names, [(a, b)])
    atoms = {n: _r[n]["atom_ids"][0] for n in names}
    review_identity(engine.registry, ent[a], ent[c], "SAME_AS", atoms[a])
    graph = build_graph(engine.registry)
    arcs = [(ent[a], ent[b], 1), (ent[a], ent[c], 3), (ent[c], ent[a], 3)]
    heavy = ppr(
        graph, seed_of(engine, ent[a]), TIGHT, relations={"REQUIRES": 1, "IDENTITY_LINK": 3}
    )
    assert_matches(heavy, Oracle(arcs, {ent[a]: 1}).solve())
    plain = ppr(graph, seed_of(engine, ent[a]), TIGHT)
    assert activation_of(plain)[ent[c]] != pytest.approx(activation_of(heavy)[ent[c]])
    scaled = ppr(
        graph, seed_of(engine, ent[a]), TIGHT, relations={"REQUIRES": 5, "IDENTITY_LINK": 5}
    )
    assert activation_of(scaled) == pytest.approx(activation_of(plain))  # only ratios matter
    only = ppr(graph, seed_of(engine, ent[a]), TIGHT, relations={"REQUIRES": 1})
    assert ent[c] not in activation_of(only)  # the identity link is not allowed
    dropped = relation_weights({"REQUIRES": 2, "IDENTITY_LINK": 0})
    assert dropped == {"REQUIRES": 2.0}  # a zero weight removes the relation
    for bad in (-1, math.nan, math.inf, True, "1", None):
        with pytest.raises(NornError, match="INVALID_RELATION_WEIGHT"):
            relation_weights({"REQUIRES": 1, "IDENTITY_LINK": bad})  # type: ignore[dict-item]
        with pytest.raises(NornError, match="INVALID_RELATION_WEIGHT"):
            relation_weights({"REQUIRES": bad})  # type: ignore[dict-item]
    with pytest.raises(NornError, match="INVALID_RELATION_WEIGHT"):
        relation_weights({"REQUIRES": 0})
    for relations in ({"CONTRADICTS": 1.0}, {"NOT_A_RELATION": 1.0}):
        with pytest.raises(NornError, match="UNSUPPORTED_RELATION_ALLOWLIST"):
            relation_weights(relations)
    with pytest.raises(NornError, match="EMPTY_RELATION_ALLOWLIST"):
        relation_weights({})


# --- budgets, truncation, residual and cancellation ----------------------------------------------


def line_world(engine, size):
    names = [name_of(i) for i in range(size)]
    edges = list(zip(names, names[1:], strict=False))
    _r, ent, _s = world(engine, names, edges)
    return names, ent, edges, build_graph(engine.registry)


def test_a_node_cap_cuts_the_subgraph_reports_the_lost_mass_and_never_renormalises(engine):
    names, ent, edges, graph = line_world(engine, 5)
    cap = ppr(
        graph,
        seed_of(engine, ent[names[0]]),
        PprLimits(max_nodes=3, max_iterations=400, tolerance=1e-13),
    )
    assert counter(cap, "nodes") == 3 and NODE_BUDGET in cap.flags and not cap.complete
    assert counter(cap, "cut_arcs") == 1 and len(cap.entries) == 3
    kept = {ent[n] for n in names[:3]}
    exact = Oracle(arcs_of_names(ent, edges), {ent[names[0]]: 1}, keep=kept).solve()
    assert_matches(cap, exact)  # the bounded problem, with its full-degree rows
    assert mass(cap, "truncated") > 0 and mass(cap, "activation") < 1.0
    # Mass balance at the fixed point: M = 1 - alpha + alpha M - leak (M: held mass).
    assert mass(cap, "activation") == pytest.approx(1.0 - mass(cap, "truncated") / 0.3, abs=1e-9)
    full = ppr(graph, seed_of(engine, ent[names[0]]), TIGHT)
    assert activation_of(cap)[ent[names[2]]] != pytest.approx(activation_of(full)[ent[names[2]]])


def test_a_node_cap_admits_breadth_first_so_the_nearest_nodes_are_kept(engine):
    names = [name_of(i) for i in range(5)]
    _r, ent, span = world(engine, names, [])
    near, far = sorted(names[1:3], key=lambda n: ent[n])  # near is expanded first
    root, tail_a, tail_b = names[0], names[3], names[4]
    link(engine, ent, span, [(root, near), (root, far), (near, tail_a), (far, tail_b)])
    graph = build_graph(engine.registry)
    capped = ppr(graph, seed_of(engine, ent[root]), PprLimits(max_nodes=4))
    kept = {e.node.id for e in capped.entries}
    assert kept == {ent[root], ent[near], ent[far], ent[tail_a]} and NODE_BUDGET in capped.flags
    assert counter(capped, "cut_arcs") == 1  # far -> tail_b is the only arc left outside


def test_an_edge_cap_is_global_and_flagged(engine):
    names, ent, edges, graph = line_world(engine, 5)
    cap = ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(max_edges=2))
    assert counter(cap, "edges") == 2 and EDGE_BUDGET in cap.flags and not cap.complete
    assert counter(cap, "nodes") == 3 and mass(cap, "truncated") > 0


def test_the_transition_budget_spans_admission_and_every_iteration_and_never_half_applies(engine):
    names, ent, edges, graph = line_world(engine, 3)
    arcs = arcs_of_names(ent, edges)
    start = {ent[names[0]]: 1}
    base = ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(max_transitions=100))
    assert counter(base, "transitions") == 2 + 2 * counter(base, "iterations")
    two = ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(max_transitions=6))
    assert counter(two, "iterations") == 2 and counter(two, "transitions") == 6
    assert TRANSITION_BUDGET in two.flags and NOT_CONVERGED in two.flags and not two.converged
    assert_matches(two, Oracle(arcs, start).steps(2), tolerance=1e-12)  # two whole iterations
    one = ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(max_transitions=5))
    assert counter(one, "iterations") == 1 and counter(one, "transitions") == 4
    assert_matches(one, Oracle(arcs, start).steps(1), tolerance=1e-12)  # not a partial second
    starved = ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(max_transitions=1))
    assert counter(starved, "iterations") == 0 and TRANSITION_BUDGET in starved.flags
    assert activation_of(starved) == {ent[names[0]]: 1.0}  # still the seed, and it says so
    assert counter(starved, "transitions") == 1 and counter(starved, "nodes") == 2  # admission cap
    assert not starved.complete and starved.residual is None and starved.error_bound is None


def test_a_run_out_of_iterations_is_flagged_with_an_honest_error_bound(engine):
    names = [name_of(i) for i in range(3)]
    edges = [(names[0], names[1]), (names[1], names[2]), (names[2], names[0])]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    short = ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(max_iterations=3))
    assert counter(short, "iterations") == 3 and not short.converged
    assert short.flags == (NOT_CONVERGED,) and not short.complete
    exact = Oracle(arcs_of_names(ent, edges), {ent[names[0]]: 1}).solve()
    error = sum(abs(v - float(exact[n])) for n, v in activation_of(short).items())
    assert short.residual is not None and short.error_bound is not None
    assert error <= short.error_bound  # the stated bound holds; it is not a guess
    assert short.error_bound == pytest.approx(0.7 / 0.3 * short.residual)
    assert counter(short, "transitions") == 3 + 3 * 3
    loose = ppr(
        graph, seed_of(engine, ent[names[0]]), PprLimits(max_iterations=400, tolerance=1e-1)
    )
    assert loose.converged and counter(loose, "iterations") < 10  # a looser residual stops earlier


def test_seeds_with_nothing_to_walk_are_explicit_and_activate_nothing_elsewhere(engine):
    names = [name_of(i) for i in range(3)]
    _r, ent, _s = world(engine, names, [(names[0], names[1])])
    graph = build_graph(engine.registry)
    empty = construct_seed(engine.registry, [ChannelResult("exact", "x-1", ())], basis_of(engine))
    result = ppr(graph, empty)
    assert result.flags == (EMPTY_SEED,) and result.entries == () and not result.complete
    assert counter(result, "iterations") == 0
    # An entity with no edge is not a node of the graph: reported, never activated.
    alone = ppr(graph, seed_of(engine, ent[names[2]]))
    assert alone.unlinked == (ent[names[2]],) and alone.entries == ()
    assert alone.unlinked_weight == 1.0
    # Nothing to start from is flagged, so an empty result is never a complete answer.
    assert alone.flags == (NO_LINKED_ANCHOR,) and not alone.complete
    lopsided = seed_of(engine, ent[names[0]], ent[names[2]], weights=[ent[names[0]]])
    mixed = ppr(graph, lopsided, TIGHT)
    assert mixed.unlinked == (ent[names[2]],)
    assert mixed.unlinked_weight == pytest.approx(lopsided.vector()[ent[names[2]]])
    assert 0.0 < mixed.unlinked_weight < 0.5
    assert mass(mixed, "activation") == pytest.approx(1.0)  # the linked seed carries the restart
    tiny = ppr(graph, seed_of(engine, ent[names[0]], ent[names[1]]), PprLimits(max_nodes=1))
    assert NODE_BUDGET in tiny.flags and counter(tiny, "nodes") == 1
    assert mass(tiny, "activation") == pytest.approx(1.0 - mass(tiny, "truncated") / 0.3, abs=1e-5)


def test_limits_alpha_and_seed_are_validated_and_a_checkpoint_cancels(engine):
    names, ent, _edges, graph = line_world(engine, 3)
    seed = seed_of(engine, ent[names[0]])
    for alpha in (1.0, -0.1, 2.0, math.nan, math.inf, 0, True):
        with pytest.raises(NornError, match="INVALID_ALPHA"):
            ppr(graph, seed, alpha=alpha)  # type: ignore[arg-type]
    for bad in (
        {"max_iterations": 0},
        {"max_iterations": 1001},
        {"max_nodes": True},
        {"max_edges": 0},
        {"max_transitions": 0},
        {"tolerance": 0.0},
        {"tolerance": 2.0},
        {"tolerance": 1},
        {"mass_tolerance": math.nan},
    ):
        with pytest.raises(NornError, match="INVALID_PPR_LIMIT"):
            PprLimits(**bad)  # type: ignore[arg-type]
    with pytest.raises(NornError, match="INVALID_SEED"):
        ppr(graph, object())  # type: ignore[arg-type]
    calls = []

    def stop() -> None:
        calls.append(1)
        raise NornError("QUERY_CANCELLED")

    with pytest.raises(NornError, match="QUERY_CANCELLED"):
        ppr(graph, seed, checkpoint=stop)
    assert len(calls) == 1
    assert SCORE_SEMANTICS == "ACTIVATION_PROPOSES_IDS_NOT_TRUTH_NOT_CAUSAL_NOT_ACCESS"


def test_a_mass_error_beyond_its_tolerance_fails_loudly(engine):
    names, ent, _edges, graph = line_world(engine, 3)
    with pytest.raises(NornError, match="PPR_MASS_VIOLATION"):
        ppr(graph, seed_of(engine, ent[names[0]]), PprLimits(mass_tolerance=1e-300), alpha=0.7)
    # Control: the same run under the default tolerance succeeds, so the failure is the tolerance.
    assert ppr(graph, seed_of(engine, ent[names[0]])).converged


def test_the_proposed_edge_is_the_one_that_carried_the_most_mass(engine):
    names = [name_of(i) for i in range(6)]
    _r, ent, span = world(engine, names, [])
    root, b, c, t, u, v = names
    link(
        engine,
        ent,
        span,
        [(root, b), (root, c), (b, t), (c, t), (b, u), (b, v)],  # b spreads its mass over three
    )
    graph = build_graph(engine.registry)
    result = ppr(graph, seed_of(engine, ent[root]), TIGHT)
    entry = next(e for e in result.entries if e.node.id == ent[t])
    assert entry.via_edge is not None
    edge = graph.edge(entry.via_edge)
    assert edge is not None and edge.source.id == ent[c]  # c -> t, not the thinner b -> t


# --- typed policy ------------------------------------------------------------------------------


def test_hypotheses_and_non_entity_nodes_carry_no_activation(engine):
    names = [name_of(i) for i in range(3)]
    a, b, d = names
    receipts, ent, span = world(engine, names, [(a, b)])
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
    graph = build_graph(engine.registry)
    result = ppr(graph, seed_of(engine, ent[a]), TIGHT)
    assert set(activation_of(result)) == {ent[a], ent[b]}
    assert all(e.node.kind == "entity" for e in result.entries)


# --- a denied bridge is never walked and moves no count, flag or byte ---------------------------


def test_a_denied_bridge_moves_no_activation_count_flag_or_byte(tmp_path):
    runs = []
    for index, (with_private, early) in enumerate(((False, False), (True, False), (True, True))):
        engine, ent, private, private_source = private_bridge_world(
            tmp_path, f"w{index}", with_private=with_private, private_first=early
        )
        with engine:
            a, b, x, c = (ent[n] for n in ent)
            owner = ppr(build_graph(engine.registry), seed_of(engine, a), TIGHT)
            with reader_of(engine) as reader:
                graph = build_graph(reader.registry)
                seed = construct_seed(
                    reader.registry, [ChannelResult("exact", "x-1", (Vote(a),))], basis_of(reader)
                )
                results = [
                    ppr(graph, seed),
                    ppr(graph, seed, TIGHT),
                    ppr(graph, seed, PprLimits(max_nodes=2)),
                    ppr(graph, seed, PprLimits(max_transitions=4)),
                ]
                runs.append([r.digest() for r in results])
                plain = results[0]
                assert set(activation_of(plain)) == {a, b, x} and c not in activation_of(plain)
                assert results[2].flags and results[3].flags  # a bound binds identically
                if private is not None:
                    assert private in activation_of(owner) and c in activation_of(owner)
                    assert private not in json.dumps([r.payload() for r in results])
                    assert private_source not in {
                        s.source_id for s in activation_candidates(reader.registry, graph, plain)
                    }
                    # An activation handed in from a more privileged principal is not trusted: the
                    # defining source of its private entity is checked against the caller's rights.
                    root_only = ppr(
                        build_graph(engine.registry),
                        seed_of(engine, private),
                        PprLimits(max_nodes=1),
                    )
                    assert [e.node.id for e in root_only.entries] == [private]
                    own = activation_candidates(
                        engine.registry, build_graph(engine.registry), root_only
                    )
                    assert private_source in {s.source_id for s in own}  # positive control
                    assert activation_candidates(reader.registry, graph, root_only) == ()
    assert runs[0] == runs[1] == runs[2]


# --- the consumer: real pilot cases through seeds, the derived graph and proposed sources -------


def keys_of(engine, graph, result) -> set[str]:
    found = (_entity_key(engine, graph, e.node.id) for e in result.entries)
    return {k for k in found if k is not None}


@pytest.mark.parametrize("family", ["M1", "M2", "M3", "M5"])
def test_from_the_chain_root_activation_covers_the_chain_and_proposes_readable_sources(
    tmp_path, family
):
    template = first(family)
    engine, published = loaded(tmp_path, template)
    with engine:
        extract_relations(engine.registry, TRACK_TEXT)
        graph = build_graph(engine.registry)
        root_key = next(k for h, _n, k in template.graph.nodes if h == template.graph.seed_node)
        root = entity_with_key(engine, root_key)
        seed = seed_of(engine, root)
        result = ppr(graph, seed, PprLimits(max_iterations=200, tolerance=1e-9))
        ids = {s.source_id for s in publish(template.case, (MARKER,)).sources}
        registered = {
            k for (k,) in engine.db.connection.execute("SELECT external_key FROM entities") if k
        }
        expected = gold_reach(template, ids, registered, root_key, 8)
        assert len(expected) >= 3
        assert result.converged and result.complete
        assert keys_of(engine, graph, result) >= expected - {None}
        walked = bfs(graph, seed, Limits(max_hops=16, max_nodes=2000, max_transitions=100_000))
        assert {e.node for e in result.entries} == {s.node for s in walked.steps}  # same support
        top = result.entries[0]
        assert top.node.id == root and top.activation > 0.3  # the restart keeps the seed on top
        found = activation_candidates(engine.registry, graph, result)
        assert found and all(engine.registry.access.eligible("READ", c.source_id) for c in found)
        assert {c.kind for c in found} <= {"EDGE_SUPPORT", "DEFINING_SOURCE"}
        conventional = build_seed(engine, interpret(published, "R0"), ("exact", "lexical"))
        run = ppr(graph, conventional)
        assert run.seed_digest == conventional.digest() and run.algorithm == "G3_PPR"


# --- isolation, determinism ------------------------------------------------------------------


def test_the_ppr_module_imports_no_gold_evaluator_retrieval_or_randomness():
    forbidden = ("benchmark", "random", "socket", "urllib", "norn.retrieval", "norn.embedding")
    path = Path(ppr_module.__file__)
    imported = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not [m for m in imported if m.startswith(forbidden)], imported
    assert "numpy" not in imported and "norn.graph.adjacency" in imported


def test_an_activation_is_deterministic_and_reloads_to_the_same_bytes(tmp_path):
    root = tmp_path / "store"
    names = [name_of(i) for i in range(5)]
    edges = [(names[0], names[1]), (names[0], names[2]), (names[1], names[3])]
    edges += [(names[2], names[3]), (names[3], names[4]), (names[4], names[0])]
    with Engine(root, HOST, create=True, clock=fixed_clock) as engine:
        engine.access.bootstrap()
        _r, ent, _s = world(engine, names, edges)
        seed = seed_of(engine, ent[names[0]])
        graph = build_graph(engine.registry)
        first_run = ppr(graph, seed).digest()
        assert first_run == ppr(graph, seed).digest()
        assert ppr(graph, seed, alpha=0.5).digest() != first_run  # the parameter is in the bytes
    with Engine(root, HOST, clock=fixed_clock) as reopened:
        assert ppr(build_graph(reopened.registry), seed).digest() == first_run
