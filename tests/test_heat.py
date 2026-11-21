"""P06-T06: G4 heat-kernel diffusion over the principal's eligible typed graph.

An independent exact rational oracle (a Taylor series of ``exp(t M)`` over fractions, built from
the generator ``M = P'^T - I`` directly and sharing no code with either implementation) checks the
dense matrix exponential and the sparse Poisson series on closed-form, line, diamond, hub,
multi-seed, weighted and budget-cut graphs. Tail, mass, locality, work and truncation behaviour is
asserted as counted over the eligible graph only; worlds that differ only by a denied private
bridge must give the reader identical bytes; real public-v2 pilot chains prove the consumer path.
"""

import ast
import json
import math
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
from norn.graph import heat as heat_module
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
from norn.graph.heat import (
    DEFAULT_SCALE,
    EXACT_NODE_CAP,
    MAX_SCALE,
    SCORE_SEMANTICS,
    TAIL_NOT_MET,
    HeatLimits,
    heat,
    heat_exact,
    poisson_weights,
)
from norn.graph.ppr import PprLimits, activation_candidates, ppr
from norn.graph.seeds import EMPTY_SEED, ChannelResult, Vote, construct_seed
from norn.integration.engine import Engine
from norn.retrieval.seed_channels import build_seed

SCALE = Fraction(2)


class HeatOracle:
    """exp(t M) s over fractions with M = P'^T - I, P' row-stochastic over the full eligible
    out-weight, arcs into nodes outside ``keep`` cut (their mass leaves) and a node with no
    allowed arc returning its mass to the seed."""

    def __init__(self, arcs, start, keep=None, scale=SCALE):
        self.scale, self.arcs = scale, arcs
        total = sum(start.values())
        self.start = {n: Fraction(w) / total for n, w in start.items()}
        nodes = {n for a in arcs for n in a[:2]} | set(self.start)
        self.keep = sorted(nodes if keep is None else keep)
        self.total: dict[str, Fraction] = {}
        for u, _v, w in arcs:
            self.total[u] = self.total.get(u, Fraction(0)) + Fraction(w)

    def generator(self):
        index = {n: i for i, n in enumerate(self.keep)}
        size = len(index)
        m = [[Fraction(-int(i == j)) for j in range(size)] for i in range(size)]
        for u, v, w in self.arcs:
            if u in index and v in index:
                m[index[v]][index[u]] += Fraction(w) / self.total[u]
        for u in self.keep:
            if self.total.get(u, 0) == 0:
                for node, share in self.start.items():
                    m[index[node]][index[u]] += share
        return index, m

    def solve(self, terms=90):
        index, m = self.generator()
        vector = [self.start.get(n, Fraction(0)) for n in self.keep]
        total = list(vector)
        for k in range(1, terms):
            vector = [
                self.scale * sum(m[i][j] * vector[j] for j in range(len(vector))) / k
                for i in range(len(vector))
            ]
            total = [x + y for x, y in zip(total, vector, strict=True)]
        assert all(abs(v) < Fraction(1, 10**30) for v in vector)  # the series is fully summed
        return {n: total[index[n]] for n in self.keep}


def activation_of(result):
    return {e.node.id: e.activation for e in result.entries}


def mass(result, name):
    return dict(result.mass)[name]


def counter(result, name):
    return dict(result.counters)[name]


def arcs_of_names(ent, edges, weight=1):
    return [(ent[a], ent[b], weight) for a, b in edges]


def assert_exact(result, exact, tolerance=1e-10):
    got = activation_of(result)
    for node in set(exact) | set(got):
        assert got.get(node, 0.0) == pytest.approx(float(exact.get(node, 0)), abs=tolerance), node


def assert_series(result, exact):
    """The partial sum underestimates every node and its L1 error is within the stated tail."""
    got = activation_of(result)
    error = 0.0
    for node in set(exact) | set(got):
        diff = float(exact.get(node, 0)) - got.get(node, 0.0)
        assert diff >= -1e-12, node  # every term is nonnegative, so the sum can only fall short
        error += abs(diff)
    assert result.tail is not None and result.error_bound == result.tail
    assert error <= result.tail + 1e-12  # the bound is a bound, not a hope


def cancel(calls):
    calls.append(1)
    raise NornError("QUERY_CANCELLED")


def line_world(engine, size):
    names = [name_of(i) for i in range(size)]
    edges = list(zip(names, names[1:], strict=False))
    _r, ent, _s = world(engine, names, edges)
    return names, ent, edges, build_graph(engine.registry)


# --- the weights, the scale and the closed form --------------------------------------------------


def test_poisson_weights_are_a_stable_recurrence_and_the_scale_is_bounded():
    for scale in (0.5, 2.0, 17.0, MAX_SCALE):
        weights = poisson_weights(scale, 400)
        for k in (0, 1, 5, 40, 120):
            direct = math.exp(k * math.log(scale) - scale - math.lgamma(k + 1))
            assert weights[k] == pytest.approx(direct, rel=1e-12, abs=1e-300)
        assert math.fsum(weights) == pytest.approx(1.0, abs=1e-12)  # no mass lost to under/overflow
        assert all(0.0 < w < 1.0 for w in weights[:100])
    assert math.exp(-MAX_SCALE) > 1e-30  # the cap keeps exp(-t) far from underflow
    for bad in (0.0, -1.0, math.nan, math.inf, MAX_SCALE + 1e-9, 51.0, 2, True, "2", None):
        with pytest.raises(NornError, match="INVALID_SCALE"):
            poisson_weights(bad, 10)  # type: ignore[arg-type]
    assert DEFAULT_SCALE == 2.0
    assert "NOT_SECONDS" in SCORE_SEMANTICS


def test_a_two_cycle_has_the_closed_form_and_all_three_computations_agree(engine):
    names = [name_of(i) for i in range(2)]
    a, b = names
    edges = [(a, b), (b, a)]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[a])
    decay = math.exp(-2 * 2.0)
    hand = {ent[a]: (1 + decay) / 2, ent[b]: (1 - decay) / 2}  # (1 +- e^-2t) / 2
    exact = heat_exact(graph, seed)
    assert activation_of(exact) == pytest.approx(hand, abs=1e-12)
    series = heat(graph, seed)
    assert_series(series, {k: Fraction(v) for k, v in hand.items()})
    oracle = HeatOracle(arcs_of_names(ent, edges), {ent[a]: 1}).solve()
    assert_exact(exact, oracle, 1e-12)
    assert float(oracle[ent[a]]) == pytest.approx(hand[ent[a]], abs=1e-12)


def test_line_diamond_hub_and_dangling_graphs_match_the_oracle(tmp_path):
    cases = {
        "dangling line": ([name_of(i) for i in range(3)], [(0, 1), (1, 2)], 0),
        "diamond": ([name_of(i) for i in range(4)], [(0, 1), (0, 2), (1, 3), (2, 3)], 0),
        "cycle": ([name_of(i) for i in range(3)], [(0, 1), (1, 2), (2, 0)], 1),
        "hub": ([name_of(i) for i in range(21)], [(0, i) for i in range(1, 21)], 0),
    }
    for label, (names, index_edges, root) in cases.items():
        edges = [(names[a], names[b]) for a, b in index_edges]
        fresh = Engine(tmp_path / label.replace(" ", "-"), HOST, create=True, clock=fixed_clock)
        with fresh:
            fresh.access.bootstrap()
            _r, ent, _s = world(fresh, names, edges)
            graph = build_graph(fresh.registry)
            seed = seed_of(fresh, ent[names[root]])
            oracle = HeatOracle(arcs_of_names(ent, edges), {ent[names[root]]: 1}).solve()
            exact = heat_exact(graph, seed)
            assert_exact(exact, oracle)
            series = heat(graph, seed)
            assert_series(series, oracle)
            assert exact.complete and series.complete and series.converged, label
            assert mass(exact, "activation") == pytest.approx(1.0, abs=1e-9), label
            assert mass(series, "activation") == pytest.approx(1.0 - series.tail, abs=1e-9), label
            assert mass(series, "truncated") <= 1e-12 and mass(exact, "truncated") <= 1e-9
            assert mass(series, "max_mass_error") <= 1e-9, label


def test_several_seeds_and_relation_weights_match_the_oracle(engine):
    names = [name_of(i) for i in range(4)]
    a, b, c, d = names
    edges = [(a, c), (b, c), (c, d)]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[a], ent[b], weights=[ent[a]])
    vector = seed.vector()
    assert vector[ent[a]] > vector[ent[b]] > 0
    start = {ent[a]: vector[ent[a]], ent[b]: vector[ent[b]]}
    oracle = HeatOracle(arcs_of_names(ent, edges), start).solve()
    assert_exact(heat_exact(graph, seed), oracle)
    assert_series(heat(graph, seed), oracle)
    # A weighted identity link: the row of the linked node is split three to one.
    more = [name_of(i + 10) for i in range(3)]
    _r2, ent2, _s2 = world(engine, more, [(more[0], more[1])])
    atoms = {n: _r2[n]["atom_ids"][0] for n in more}
    review_identity(engine.registry, ent2[more[0]], ent2[more[2]], "SAME_AS", atoms[more[0]])
    graph2 = build_graph(engine.registry)
    weights = {"REQUIRES": 1, "IDENTITY_LINK": 3}
    arcs = [
        (ent2[more[0]], ent2[more[1]], 1),
        (ent2[more[0]], ent2[more[2]], 3),
        (ent2[more[2]], ent2[more[0]], 3),
    ]
    root = seed_of(engine, ent2[more[0]])
    oracle2 = HeatOracle(arcs, {ent2[more[0]]: 1}).solve()
    assert_exact(heat_exact(graph2, root, relations=weights), oracle2)
    assert_series(heat(graph2, root, relations=weights), oracle2)
    plain = activation_of(heat_exact(graph2, root))
    assert plain[ent2[more[2]]] != pytest.approx(
        activation_of(heat_exact(graph2, root, relations=weights))[ent2[more[2]]]
    )


# --- locality, tail and truncation ---------------------------------------------------------------


def test_a_small_scale_stays_local_and_the_tail_decides_how_far_the_series_reaches(engine):
    names, ent, edges, graph = line_world(engine, 12)
    seed = seed_of(engine, ent[names[0]])
    local = heat(graph, seed, scale=0.1)
    reached = [n for n in names if ent[n] in activation_of(local)]
    assert local.converged and local.complete
    assert reached == names[: counter(local, "terms")]  # one new hop per term, no farther
    assert counter(local, "terms") < len(names)
    values = [activation_of(local)[ent[n]] for n in reached]
    assert values == sorted(values, reverse=True) and values[0] > 0.9  # concentrated at the seed
    wide = heat(graph, seed, scale=4.0)
    assert len(wide.entries) > len(local.entries)  # a larger scale diffuses farther
    assert activation_of(wide)[ent[names[0]]] < values[0]
    assert_series(
        local,
        HeatOracle(arcs_of_names(ent, edges), {ent[names[0]]: 1}, scale=Fraction(1, 10)).solve(),
    )


def test_the_largest_scale_converges_without_underflow_or_overflow(engine):
    names, ent, edges, graph = line_world(engine, 6)
    seed = seed_of(engine, ent[names[0]])
    result = heat(graph, seed, scale=MAX_SCALE)
    assert result.converged and result.complete and counter(result, "terms") < 100
    assert all(math.isfinite(e.activation) and e.activation >= 0 for e in result.entries)
    assert mass(result, "activation") == pytest.approx(1.0 - result.tail, abs=1e-9)
    oracle = HeatOracle(arcs_of_names(ent, edges), {ent[names[0]]: 1}, scale=Fraction(50)).solve(
        terms=400
    )
    assert_series(result, oracle)
    assert_exact(heat_exact(graph, seed, scale=MAX_SCALE), oracle, 1e-9)


def test_a_run_out_of_terms_is_flagged_never_called_converged_and_its_bound_holds(engine):
    names, ent, edges, graph = line_world(engine, 6)
    seed = seed_of(engine, ent[names[0]])
    short = heat(graph, seed, HeatLimits(max_terms=3))
    assert counter(short, "terms") == 3 and not short.converged and not short.complete
    assert short.flags == (TAIL_NOT_MET,) and short.tail is not None and short.tail > 0.3
    oracle = HeatOracle(arcs_of_names(ent, edges), {ent[names[0]]: 1}).solve()
    assert_series(short, oracle)
    assert counter(short, "transitions") == 5 + 2 * 5  # admission plus two term passes of 5 arcs
    tight = heat(graph, seed, HeatLimits(tail_tolerance=1e-12, max_terms=100))
    assert tight.converged and tight.tail is not None and tight.tail <= 1e-12
    assert counter(tight, "terms") > counter(heat(graph, seed), "terms")
    assert_exact(tight, oracle, 1e-10)


def test_the_transition_budget_spans_admission_and_every_term_and_never_half_applies_one(engine):
    names, ent, edges, graph = line_world(engine, 3)
    seed = seed_of(engine, ent[names[0]])
    arcs = arcs_of_names(ent, edges)
    two = heat(graph, seed, HeatLimits(max_transitions=6))  # 2 to admit + 2 whole terms of 2
    assert counter(two, "terms") == 3 and counter(two, "transitions") == 6
    assert TRANSITION_BUDGET in two.flags and TAIL_NOT_MET in two.flags and not two.converged
    weights = poisson_weights(2.0, 3)
    state = {ent[names[0]]: 1.0}
    summed = {ent[names[0]]: weights[0]}
    for k in (1, 2):  # exact power steps of P' (dangling mass back to the seed)
        nxt = {}
        for u, held in state.items():
            outs = [(v, w) for a, v, w in arcs if a == u]
            if not outs:
                nxt[ent[names[0]]] = nxt.get(ent[names[0]], 0.0) + held
            for v, w in outs:
                nxt[v] = nxt.get(v, 0.0) + held * w / len(outs)
        state = nxt
        for node, value in state.items():
            summed[node] = summed.get(node, 0.0) + weights[k] * value
    assert activation_of(two) == pytest.approx(summed, abs=1e-12)  # three whole terms, no fourth
    one = heat(graph, seed, HeatLimits(max_transitions=5))
    assert counter(one, "terms") == 2 and counter(one, "transitions") == 4
    starved = heat(graph, seed, HeatLimits(max_transitions=1))
    assert counter(starved, "terms") == 1 and TRANSITION_BUDGET in starved.flags
    assert activation_of(starved) == pytest.approx({ent[names[0]]: weights[0]})
    assert starved.tail == pytest.approx(1.0 - weights[0]) and not starved.complete
    assert counter(starved, "transitions") == 1 and counter(starved, "nodes") == 2  # admission cap
    assert not starved.converged
    wasteful = heat(graph, seed, HeatLimits(max_transitions=100))
    assert counter(wasteful, "transitions") == 2 + 2 * (counter(wasteful, "terms") - 1)
    # The dangling rate is Poisson weighted: pass k holds the mass of step k - 1, which sits on
    # the sink every third step (the line has three nodes).
    passes = counter(wasteful, "terms") - 1
    every = poisson_weights(2.0, passes + 1)
    expected = math.fsum(every[k] for k in range(1, passes + 1) if (k - 1) % 3 == 2)
    assert mass(wasteful, "dangling_restarted") == pytest.approx(expected, rel=1e-9)


def test_a_node_or_edge_cap_cuts_the_subgraph_and_reports_the_lost_mass(engine):
    names, ent, edges, graph = line_world(engine, 5)
    seed = seed_of(engine, ent[names[0]])
    kept = {ent[n] for n in names[:3]}
    oracle = HeatOracle(arcs_of_names(ent, edges), {ent[names[0]]: 1}, keep=kept).solve()
    cap = HeatLimits(max_nodes=3, tail_tolerance=1e-9, max_terms=200)
    series, exact = heat(graph, seed, cap), heat_exact(graph, seed, cap)
    assert NODE_BUDGET in series.flags and NODE_BUDGET in exact.flags and not series.complete
    assert counter(series, "nodes") == 3 and counter(series, "cut_arcs") == 1
    assert_exact(exact, oracle)  # the bounded problem, full-degree rows
    assert_series(series, oracle)
    assert mass(series, "truncated") > 0 and mass(exact, "truncated") > 0
    assert mass(exact, "truncated") == pytest.approx(1.0 - mass(exact, "activation"))
    full = heat_exact(graph, seed)
    assert mass(full, "activation") == pytest.approx(1.0, abs=1e-9)
    edge_cap = heat(graph, seed, HeatLimits(max_edges=2))
    assert counter(edge_cap, "edges") == 2 and EDGE_BUDGET in edge_cap.flags
    assert mass(edge_cap, "truncated") > 0


def test_the_same_seed_graph_and_budgets_give_g3_and_g4_the_same_walked_subgraph(engine):
    names, ent, _edges, graph = line_world(engine, 6)
    seed = seed_of(engine, ent[names[0]])
    for g3, g4 in (
        (PprLimits(), HeatLimits()),
        (PprLimits(max_nodes=4), HeatLimits(max_nodes=4)),
        (PprLimits(max_edges=3), HeatLimits(max_edges=3)),
    ):
        a, b = ppr(graph, seed, g3), heat(graph, seed, g4)
        for name in ("nodes", "edges", "cut_arcs"):
            assert counter(a, name) == counter(b, name)
        assert a.edges == b.edges
        assert {f for f in a.flags if f.endswith("_BUDGET")} == {
            f for f in b.flags if f.endswith("_BUDGET")
        }
    assert heat(graph, seed).limits.budgets() == PprLimits()  # defaults are the PPR budgets


def test_the_proposed_edge_is_the_one_that_carried_the_most_flow(engine):
    names = [name_of(i) for i in range(6)]
    _r, ent, span = world(engine, names, [])
    root, b, c, t, u, v = names
    link(engine, ent, span, [(root, b), (root, c), (b, t), (c, t), (b, u), (b, v)])
    graph = build_graph(engine.registry)
    result = heat(graph, seed_of(engine, ent[root]))
    entry = next(e for e in result.entries if e.node.id == ent[t])
    edge = graph.edge(entry.via_edge) if entry.via_edge else None
    assert edge is not None and edge.source.id == ent[c]  # c -> t, not the thinner b -> t
    assert next(e for e in result.entries if e.node.id == ent[root]).via_edge is None  # no inflow
    assert all(e.via_edge is None for e in heat_exact(graph, seed_of(engine, ent[root])).entries)


# --- seeds, validation and cancellation ----------------------------------------------------------


def test_seeds_with_nothing_to_walk_are_explicit_and_activate_nothing_elsewhere(engine):
    names = [name_of(i) for i in range(3)]
    _r, ent, _s = world(engine, names, [(names[0], names[1])])
    graph = build_graph(engine.registry)
    empty = construct_seed(engine.registry, [ChannelResult("exact", "x-1", ())], basis_of(engine))
    for run in (heat, heat_exact):
        result = run(graph, empty)
        assert result.flags == (EMPTY_SEED,) and result.entries == () and not result.complete
        alone = run(graph, seed_of(engine, ent[names[2]]))
        assert alone.unlinked == (ent[names[2]],) and alone.entries == ()
        assert alone.flags == (NO_LINKED_ANCHOR,) and not alone.complete
        assert alone.unlinked_weight == 1.0
        lopsided = seed_of(engine, ent[names[0]], ent[names[2]], weights=[ent[names[0]]])
        mixed = run(graph, lopsided)
        assert mixed.unlinked == (ent[names[2]],)
        assert mixed.unlinked_weight == pytest.approx(lopsided.vector()[ent[names[2]]])
        assert sum(activation_of(mixed).values()) > 0.99 - (mixed.tail or 0.0)


def test_scale_limits_size_seed_and_a_cancelling_checkpoint_are_validated_or_refused(engine):
    names, ent, _edges, graph = line_world(engine, 3)
    seed = seed_of(engine, ent[names[0]])
    for run in (heat, heat_exact):
        for bad in (0.0, -1.0, math.nan, math.inf, 50.5, 2, True):
            with pytest.raises(NornError, match="INVALID_SCALE"):
                run(graph, seed, scale=bad)  # type: ignore[arg-type]
        with pytest.raises(NornError, match="INVALID_SEED"):
            run(graph, object())  # type: ignore[arg-type]
        with pytest.raises(NornError, match="UNSUPPORTED_RELATION_ALLOWLIST"):
            run(graph, seed, relations={"CONTRADICTS": 1.0})

        calls: list[int] = []
        with pytest.raises(NornError, match="QUERY_CANCELLED"):
            run(graph, seed, checkpoint=lambda sink=calls: cancel(sink))
        assert len(calls) == 1
    for bad_limit in (
        {"max_terms": 0},
        {"max_terms": 1001},
        {"max_nodes": True},
        {"tail_tolerance": 0.0},
        {"tail_tolerance": 1},
        {"mass_tolerance": math.nan},
        {"max_edges": 0},
        {"max_transitions": 0},
    ):
        with pytest.raises(NornError, match="INVALID_HEAT_LIMIT"):
            HeatLimits(**bad_limit)  # type: ignore[arg-type]


def test_a_wrong_exponential_is_refused_by_the_mass_guard_of_the_exact_path(engine, monkeypatch):
    names, ent, _edges, graph = line_world(engine, 3)
    seed = seed_of(engine, ent[names[0]])
    size = 3

    def scaled(factor):
        return lambda matrix, checkpoint: [
            [factor * (1.0 if i == j else 0.0) for j in range(size)] for i in range(size)
        ]

    assert heat_exact(graph, seed).complete  # control: the real kernel passes the guard
    monkeypatch.setattr(heat_module, "_exponential", scaled(0.9))
    with pytest.raises(NornError, match="HEAT_MASS_VIOLATION"):  # mass 0.9 on a closed graph
        heat_exact(graph, seed)
    monkeypatch.setattr(heat_module, "_exponential", scaled(1.5))
    with pytest.raises(NornError, match="HEAT_MASS_VIOLATION"):  # mass above one
        heat_exact(graph, seed)
    cut = HeatLimits(max_nodes=2)  # a cut subgraph may lose mass but never gain it
    monkeypatch.setattr(heat_module, "_exponential", scaled(0.9))
    assert heat_exact(graph, seed, cut).flags == (NODE_BUDGET,)
    monkeypatch.setattr(heat_module, "_exponential", scaled(1.5))
    with pytest.raises(NornError, match="HEAT_MASS_VIOLATION"):
        heat_exact(graph, seed, cut)


def test_the_exact_exponential_is_refused_beyond_its_node_cap(engine):
    names = [name_of(i) for i in range(EXACT_NODE_CAP + 2)]
    edges = [(names[0], n) for n in names[1:]]
    _r, ent, _s = world(engine, names, edges)
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[names[0]])
    with pytest.raises(NornError, match="HEAT_EXACT_TOO_LARGE"):
        heat_exact(graph, seed)
    series = heat(graph, seed)  # the sparse series has no such cap
    assert series.converged and counter(series, "nodes") == EXACT_NODE_CAP + 2
    assert mass(series, "activation") == pytest.approx(1.0 - series.tail, abs=1e-9)
    capped = heat_exact(graph, seed, HeatLimits(max_nodes=EXACT_NODE_CAP))
    assert counter(capped, "nodes") == EXACT_NODE_CAP and NODE_BUDGET in capped.flags


def test_a_mass_error_beyond_its_tolerance_fails_loudly(engine):
    names = [name_of(i) for i in range(8)]
    _r, ent, _s = world(engine, names, [(names[0], n) for n in names[1:]])  # shares of 1/7
    graph = build_graph(engine.registry)
    seed = seed_of(engine, ent[names[0]])
    rounding = mass(heat(graph, seed), "max_mass_error")
    assert rounding > 0.0  # these shares are inexact, so the balance has a real error to refuse
    with pytest.raises(NornError, match="HEAT_MASS_VIOLATION"):
        heat(graph, seed, HeatLimits(mass_tolerance=rounding / 2))
    assert heat(graph, seed).converged  # control: the same run passes at the default tolerance


# --- typed policy and a denied bridge ------------------------------------------------------------


def test_hypotheses_carry_no_diffusion(engine):
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
    for result in (
        heat(graph, seed_of(engine, ent[a])),
        heat_exact(graph, seed_of(engine, ent[a])),
    ):
        assert set(activation_of(result)) == {ent[a], ent[b]}
        assert all(e.node.kind == "entity" for e in result.entries)


def test_a_denied_bridge_moves_no_diffusion_count_flag_or_byte(tmp_path):
    runs = []
    for index, (with_private, early) in enumerate(((False, False), (True, False), (True, True))):
        engine, ent, private, private_source = private_bridge_world(
            tmp_path, f"w{index}", with_private=with_private, private_first=early
        )
        with engine:
            a, b, x, c = (ent[n] for n in ent)
            owner = heat(build_graph(engine.registry), seed_of(engine, a))
            with reader_of(engine) as reader:
                graph = build_graph(reader.registry)
                seed = construct_seed(
                    reader.registry, [ChannelResult("exact", "x-1", (Vote(a),))], basis_of(reader)
                )
                results = [
                    heat(graph, seed),
                    heat_exact(graph, seed),
                    heat(graph, seed, HeatLimits(max_nodes=2)),
                    heat_exact(graph, seed, HeatLimits(max_nodes=2)),
                    heat(graph, seed, HeatLimits(max_transitions=4)),
                ]
                runs.append([r.digest() for r in results])
                assert set(activation_of(results[0])) == {a, b, x}
                assert c not in activation_of(results[0]) and results[0].complete
                assert results[2].flags and results[3].flags and results[4].flags
                if private is not None:
                    assert private in activation_of(owner) and c in activation_of(owner)
                    assert private not in json.dumps([r.payload() for r in results])
                    assert private_source not in {
                        s.source_id
                        for s in activation_candidates(reader.registry, graph, results[0])
                    }
                    root_only = heat(
                        build_graph(engine.registry),
                        seed_of(engine, private),
                        HeatLimits(max_nodes=1),
                    )
                    assert [e.node.id for e in root_only.entries] == [private]
                    own = activation_candidates(
                        engine.registry, build_graph(engine.registry), root_only
                    )
                    assert private_source in {s.source_id for s in own}  # positive control
                    assert activation_candidates(reader.registry, graph, root_only) == ()
    assert runs[0] == runs[1] == runs[2]


# --- the consumer: real pilot cases --------------------------------------------------------------


@pytest.mark.parametrize("family", ["M1", "M2", "M3", "M5"])
def test_from_the_chain_root_diffusion_covers_the_chain_and_proposes_readable_sources(
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
        result = heat(graph, seed, HeatLimits(max_terms=200, tail_tolerance=1e-9))
        ids = {s.source_id for s in publish(template.case, (MARKER,)).sources}
        registered = {
            k for (k,) in engine.db.connection.execute("SELECT external_key FROM entities") if k
        }
        expected = gold_reach(template, ids, registered, root_key, 8)
        assert len(expected) >= 3
        assert result.converged and result.complete
        found_keys = {_entity_key(engine, graph, e.node.id) for e in result.entries} - {None}
        assert found_keys >= expected - {None}
        walked = bfs(graph, seed, Limits(max_hops=16, max_nodes=2000, max_transitions=100_000))
        assert {e.node for e in result.entries} <= {s.node for s in walked.steps}
        if counter(result, "nodes") <= EXACT_NODE_CAP:
            exact = heat_exact(graph, seed)
            assert_series(result, {e.node.id: Fraction(e.activation) for e in exact.entries})
        else:
            with pytest.raises(NornError, match="HEAT_EXACT_TOO_LARGE"):
                heat_exact(graph, seed)
        found = activation_candidates(engine.registry, graph, result)
        assert found and all(engine.registry.access.eligible("READ", c.source_id) for c in found)
        conventional = build_seed(engine, interpret(published, "R0"), ("exact", "lexical"))
        run = heat(graph, conventional)
        assert run.seed_digest == conventional.digest() and run.algorithm == "G4_HEAT_SERIES"


# --- isolation, determinism ----------------------------------------------------------------------


def test_the_heat_module_imports_no_gold_evaluator_retrieval_randomness_or_numpy():
    forbidden = ("benchmark", "random", "socket", "urllib", "norn.retrieval", "norn.embedding")
    path = Path(heat_module.__file__)
    imported = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not [m for m in imported if m.startswith(forbidden)], imported
    assert "numpy" not in imported and "norn.graph.ppr" in imported


def test_a_diffusion_is_deterministic_and_reloads_to_the_same_bytes(tmp_path):
    root = tmp_path / "store"
    names = [name_of(i) for i in range(5)]
    edges = [(names[0], names[1]), (names[0], names[2]), (names[1], names[3])]
    edges += [(names[2], names[3]), (names[3], names[4]), (names[4], names[0])]
    with Engine(root, HOST, create=True, clock=fixed_clock) as engine:
        engine.access.bootstrap()
        _r, ent, _s = world(engine, names, edges)
        seed = seed_of(engine, ent[names[0]])
        graph = build_graph(engine.registry)
        digests = [heat(graph, seed).digest(), heat_exact(graph, seed).digest()]
        assert digests == [heat(graph, seed).digest(), heat_exact(graph, seed).digest()]
        assert heat(graph, seed, scale=1.0).digest() != digests[0]  # the scale is in the bytes
        assert digests[0] != digests[1]
    with Engine(root, HOST, clock=fixed_clock) as reopened:
        again = build_graph(reopened.registry)
        assert [heat(again, seed).digest(), heat_exact(again, seed).digest()] == digests
