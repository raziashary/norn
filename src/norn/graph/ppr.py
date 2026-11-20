"""G3 seeded personalised PageRank over the principal's eligible typed graph (P06-T05).

Activation ``a`` is the fixed point of ``a = (1 - alpha) s + alpha P' a`` where ``P'`` is the
transposed row-stochastic transition matrix of the allowed arcs. ``alpha`` is the forward
propagation weight and ``1 - alpha`` the restart. Owner answers of 14 November 2026 (T05 entry of
``ADR_LOG``):

* **dangling rule:** a node with no allowed outgoing arc returns its mass to the seed
  distribution, so total mass stays one and nothing leaks to a non-seed node; the dense oracle in
  the tests uses the same rule;
* **budget cut:** rows always normalise by the node's full eligible out-weight. When the global
  node or edge budget leaves an arc out of the walked subgraph, the mass sent along it is counted
  as ``truncated`` (the mass leaving in the last iteration), never renormalised away, and the
  result is flagged as a bounded approximation (it is then not the stationary distribution of the
  full eligible graph);
* **defaults (untuned, T21 pins the envelope):** alpha 0.7, at most 60 iterations, L1 residual
  tolerance 1e-6 and a separate mass tolerance 1e-9, 1,000 unique nodes, 5,000 unique edges and
  20,000 processed transitions, all global over admission and every iteration. The first answer
  of 40 iterations left a three-node chain at residual 1.3e-6, so the owner raised it to 60;
* **weights:** every allowed arc weighs one unless the caller gives a per-relation nonnegative
  finite weight; there are no learned or evidence-strength weights.

The walked subgraph is the part of the eligible graph reachable from the seed over the allowed
relations, admitted breadth first in a fixed order until a budget binds. Every arc examined in
admission and in every iteration counts as a processed transition (revisits are work too), and an
iteration is reserved whole, so a transition budget never leaves a half-applied update. The result
is read only: it proposes identifiers and never grants truth, access or approval, and a node the
principal cannot read is not a node, an arc or a count here.
"""

import math
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from norn.canonical.registry import Registry
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.graph.adjacency import Graph
from norn.graph.bfs import (
    CHECK_EVERY,
    DEFAULT_RELATIONS,
    EDGE_BUDGET,
    NODE_BUDGET,
    TRANSITION_BUDGET,
    arcs_of,
    check_relations,
    defining_sources,
    roots_of,
)
from norn.graph.contracts import NodeRef
from norn.graph.seeds import Seed

DEFAULT_ALPHA = 0.7
NOT_CONVERGED = "NOT_CONVERGED"
SCORE_SEMANTICS = "ACTIVATION_PROPOSES_IDS_NOT_TRUTH_NOT_CAUSAL_NOT_ACCESS"
MASS_VIOLATION = "PPR_MASS_VIOLATION"
NON_FINITE = "PPR_NON_FINITE"


@dataclass(frozen=True)
class PprLimits:
    """Global bounds and tolerances of one run (pilot defaults, untuned)."""

    max_iterations: int = 60
    tolerance: float = 1e-6
    mass_tolerance: float = 1e-9
    max_nodes: int = 1000
    max_edges: int = 5000
    max_transitions: int = 20_000

    def __post_init__(self) -> None:
        for name, cap in (
            ("max_iterations", 1000),
            ("max_nodes", 100_000),
            ("max_edges", 400_000),
            ("max_transitions", 10_000_000),
        ):
            value = getattr(self, name)
            require(type(value) is int and 1 <= value <= cap, "INVALID_PPR_LIMIT")
        for name in ("tolerance", "mass_tolerance"):
            value = getattr(self, name)
            require(
                type(value) is float and math.isfinite(value) and 0.0 < value <= 1.0,
                "INVALID_PPR_LIMIT",
            )


@dataclass(frozen=True)
class Entry:
    """One activated node; ``via_edge`` is the arc that carried most mass to it in the last
    iteration (None for a node that only receives restart mass)."""

    node: NodeRef
    activation: float
    via_edge: str | None


@dataclass(frozen=True)
class Activation:
    algorithm: str
    relations: tuple[tuple[str, float], ...]
    limits: PprLimits
    alpha: float
    entries: tuple[Entry, ...]  # ranked, most activated first
    edges: tuple[str, ...]  # unique edge ids admitted, sorted
    counters: tuple[tuple[str, int], ...]
    mass: tuple[tuple[str, float], ...]
    residual: float | None  # L1 change of the last iteration; None when none was run
    error_bound: float | None  # alpha / (1 - alpha) * residual: L1 distance to the fixed point
    converged: bool
    flags: tuple[str, ...]
    unlinked: tuple[str, ...]
    unlinked_weight: float
    seed_digest: str

    @property
    def complete(self) -> bool:
        """True only when no bound bound, the run converged and the seed had something to start."""
        return not self.flags

    def payload(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "relations": [list(r) for r in self.relations],
            "limits": [
                self.limits.max_iterations,
                self.limits.tolerance,
                self.limits.mass_tolerance,
                self.limits.max_nodes,
                self.limits.max_edges,
                self.limits.max_transitions,
            ],
            "alpha": self.alpha,
            "entries": [[e.node.kind, e.node.id, e.activation, e.via_edge] for e in self.entries],
            "edges": list(self.edges),
            "counters": [list(c) for c in self.counters],
            "mass": [list(m) for m in self.mass],
            "residual": self.residual,
            "error_bound": self.error_bound,
            "converged": self.converged,
            "flags": list(self.flags),
            "unlinked": list(self.unlinked),
            "unlinked_weight": self.unlinked_weight,
            "seed": self.seed_digest,
        }

    def digest(self) -> str:
        return digest(canonical(self.payload()).encode())


@dataclass(frozen=True)
class Candidate:
    """A source proposed by the activation and why (the proposal is never evidence of truth)."""

    source_id: str
    node: NodeRef
    activation: float
    kind: str  # EDGE_SUPPORT or DEFINING_SOURCE
    edge_id: str | None


def relation_weights(relations: Mapping[str, float] | None) -> dict[str, float]:
    """The allowed relations with a positive weight; refuses negative, non-finite or boolean."""
    given = dict.fromkeys(DEFAULT_RELATIONS, 1.0) if relations is None else dict(relations)
    check_relations(frozenset(given))
    weights: dict[str, float] = {}
    for name, value in given.items():
        require(
            type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "INVALID_RELATION_WEIGHT",
        )
        if value > 0:
            weights[name] = float(value)
    require(len(weights) > 0, "INVALID_RELATION_WEIGHT")
    return weights


@dataclass
class Walk:
    """The subgraph admitted for one run, with its rows and the work spent building it."""

    order: list[NodeRef]
    rows: dict[NodeRef, list[tuple[NodeRef, float, str]]]  # target, weight / out-weight, edge id
    cut: dict[NodeRef, float]  # fraction of a node's out-weight left outside the subgraph
    dangling: set[NodeRef]
    edges: set[str]
    transitions: int
    cut_arcs: int
    flags: set[str]


def admit(
    graph: Graph,
    roots: list[NodeRef],
    weights: dict[str, float],
    limits: PprLimits,
    checkpoint: Callable[[], None] | None,
) -> Walk:
    names = tuple(sorted(weights))
    admitted: set[NodeRef] = set()
    order: list[NodeRef] = []
    queue: deque[NodeRef] = deque()
    flags: set[str] = set()
    for node in roots:
        if len(admitted) >= limits.max_nodes:
            flags.add(NODE_BUDGET)
            break
        admitted.add(node)
        order.append(node)
        queue.append(node)
    raw: dict[NodeRef, list[tuple[NodeRef, float, str]]] = {}
    out_weight: dict[NodeRef, float] = {}
    cut_weight: dict[NodeRef, float] = {}
    edges: set[str] = set()
    transitions = cut_arcs = 0
    while queue and TRANSITION_BUDGET not in flags:
        if checkpoint is not None:
            checkpoint()
        node = queue.popleft()
        arcs = arcs_of(graph, node, names)
        out_weight[node] = sum(weights[a.relation] for a in arcs)
        raw[node] = []
        cut_weight[node] = 0.0
        for arc in arcs:
            if transitions >= limits.max_transitions:
                flags.add(TRANSITION_BUDGET)
                break
            if checkpoint is not None and transitions % CHECK_EVERY == 0:
                checkpoint()
            transitions += 1
            target, weight = arc.neighbor, weights[arc.relation]
            new_edge = arc.edge_id not in edges
            if new_edge and len(edges) >= limits.max_edges:
                flags.add(EDGE_BUDGET)
            elif target not in admitted and len(admitted) >= limits.max_nodes:
                flags.add(NODE_BUDGET)
            else:
                if target not in admitted:
                    admitted.add(target)
                    order.append(target)
                    queue.append(target)
                edges.add(arc.edge_id)
                raw[node].append((target, weight, arc.edge_id))
                continue
            cut_weight[node] += weight
            cut_arcs += 1
    rows: dict[NodeRef, list[tuple[NodeRef, float, str]]] = {}
    cut: dict[NodeRef, float] = {}
    dangling: set[NodeRef] = set()
    for node in order:
        total = out_weight.get(node)
        if total is None or TRANSITION_BUDGET in flags:  # unexpanded: no iteration will run
            rows[node], cut[node] = [], 0.0
            continue
        if total == 0.0:
            dangling.add(node)
            rows[node], cut[node] = [], 0.0
            continue
        rows[node] = [(t, w / total, e) for t, w, e in raw[node]]
        cut[node] = cut_weight[node] / total
    return Walk(order, rows, cut, dangling, edges, transitions, cut_arcs, flags)


@dataclass
class Prepared:
    """The walked subgraph and the seed distribution over its kept roots (shared by G3 and G4,
    so both diffuse the same seed over the same eligible subgraph under the same budgets)."""

    walk: Walk
    start: dict[NodeRef, float]  # sums to one over the roots the walk kept, or empty
    unlinked: tuple[str, ...]
    lost: float  # the seed weight on anchors that are not nodes of the graph
    flags: set[str]


def prepare(
    graph: Graph,
    seed: Seed,
    weights: dict[str, float],
    limits: PprLimits,
    checkpoint: Callable[[], None] | None,
) -> Prepared:
    roots, unlinked, flags = roots_of(graph, seed)
    anchor_weight = {a.entity_id: a.weight for a in seed.anchors}
    lost = math.fsum(anchor_weight[e] for e in unlinked)
    walk = admit(graph, [n for n, _w in roots], weights, limits, checkpoint)
    flags |= walk.flags
    # A root that a tiny node budget kept out of the walk is lost (flagged NODE_BUDGET).
    taken = [(n, w) for n, w in roots if n in walk.rows]
    kept = math.fsum(w for _n, w in taken)
    start = {node: w / kept for node, w in taken} if kept > 0 else {}
    return Prepared(walk, start, tuple(unlinked), lost, flags)


def ppr(
    graph: Graph,
    seed: Seed,
    limits: PprLimits | None = None,
    alpha: float = DEFAULT_ALPHA,
    relations: Mapping[str, float] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> Activation:
    """Power iteration from the seed distribution within the global budgets."""
    limits = limits or PprLimits()
    require(type(alpha) is float and math.isfinite(alpha) and 0.0 <= alpha < 1.0, "INVALID_ALPHA")
    weights = relation_weights(relations)
    prepared = prepare(graph, seed, weights, limits, checkpoint)
    walk, start, flags = prepared.walk, prepared.start, prepared.flags
    iterations = 0
    residual: float | None = None
    converged = not start  # nothing to iterate from is trivially at rest
    leaked = dangled = worst = 0.0
    transitions = walk.transitions
    arcs_per_iteration = sum(len(r) for r in walk.rows.values())
    state: dict[NodeRef, float] = dict(start)
    via: dict[NodeRef, tuple[float, str]] = {}
    while start and TRANSITION_BUDGET not in flags and iterations < limits.max_iterations:
        if transitions + arcs_per_iteration > limits.max_transitions:
            flags.add(TRANSITION_BUDGET)  # an iteration is reserved whole or not run at all
            break
        if checkpoint is not None:
            checkpoint()
        transitions += arcs_per_iteration
        following: dict[NodeRef, float] = {}
        best: dict[NodeRef, tuple[float, str]] = {}
        dangling_mass = cut_mass = 0.0
        for node in sorted(state):
            held = state[node]
            if node in walk.dangling:
                dangling_mass += held
                continue
            for target, share, edge_id in walk.rows[node]:
                moved = alpha * held * share
                following[target] = following.get(target, 0.0) + moved
                known = best.get(target)
                if known is None or (moved, edge_id) > known:
                    best[target] = (moved, edge_id)
            cut_mass += held * walk.cut[node]
        restart = (1.0 - alpha) + alpha * dangling_mass
        for node, share in start.items():
            following[node] = following.get(node, 0.0) + restart * share
        mass_before = math.fsum(state.values())
        mass_after = math.fsum(following.values())
        expected = (1.0 - alpha) + alpha * (mass_before - cut_mass)
        error = abs(mass_after - expected)
        require(all(math.isfinite(v) and v >= 0.0 for v in following.values()), NON_FINITE)
        if error > limits.mass_tolerance:
            raise NornError(MASS_VIOLATION)
        worst = max(worst, error)
        leaked, dangled = alpha * cut_mass, alpha * dangling_mass  # the last iteration's rate
        residual = math.fsum(
            abs(following.get(n, 0.0) - state.get(n, 0.0)) for n in set(following) | set(state)
        )
        state, via = following, best
        iterations += 1
        if residual <= limits.tolerance:
            converged = True
            break
    if start and not converged:
        flags.add(NOT_CONVERGED)
    ranked = sorted(((n, v) for n, v in state.items() if v > 0.0), key=lambda i: (-i[1], i[0]))
    entries = tuple(
        Entry(n, v, via[n][1] if n in via and iterations > 0 else None) for n, v in ranked
    )
    bound = None if residual is None else alpha / (1.0 - alpha) * residual
    return Activation(
        "G3_PPR",
        tuple(sorted(weights.items())),
        limits,
        alpha,
        entries,
        tuple(sorted(walk.edges)),
        (
            ("cut_arcs", walk.cut_arcs),
            ("edges", len(walk.edges)),
            ("iterations", iterations),
            ("nodes", len(walk.order)),
            ("transitions", transitions),
        ),
        (
            ("activation", math.fsum(state.values())),
            ("dangling_restarted", dangled),
            ("max_mass_error", worst),
            ("truncated", leaked),
        ),
        residual,
        bound,
        converged,
        tuple(sorted(flags)),
        prepared.unlinked,
        prepared.lost,  # a seed sums to one, so the unlinked weight is also the unlinked share
        seed.digest(),
    )


class Ranked(Protocol):
    @property
    def entries(self) -> tuple[Entry, ...]: ...


def activation_candidates(
    registry: Registry, graph: Graph, activation: Ranked
) -> tuple[Candidate, ...]:
    """Sources the activation proposes, first reason only, in activation order.

    A node contributes the supports of the arc that carried most mass to it (all readable, since
    the graph keeps an edge only when every support is) and the defining source of an entity,
    which is checked against the caller's own rights."""
    defining = defining_sources(
        registry, [e.node.id for e in activation.entries if e.node.kind == "entity"]
    )
    found: dict[str, Candidate] = {}
    for entry in activation.entries:
        if entry.via_edge is not None:
            edge = graph.edge(entry.via_edge)
            require(edge is not None, "ACTIVATION_EDGE_UNKNOWN")
            assert edge is not None
            for support in edge.supports:
                found.setdefault(
                    support.source_id,
                    Candidate(
                        support.source_id,
                        entry.node,
                        entry.activation,
                        "EDGE_SUPPORT",
                        entry.via_edge,
                    ),
                )
        owner = defining.get(entry.node.id) if entry.node.kind == "entity" else None
        if owner is not None:
            found.setdefault(
                owner,
                Candidate(owner, entry.node, entry.activation, "DEFINING_SOURCE", entry.via_edge),
            )
    return tuple(found.values())
