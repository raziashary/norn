"""G4 heat-kernel diffusion over the principal's eligible typed graph (P06-T06).

Activation ``a(t) = exp(t (P' - I)) s`` where ``P'`` is the transposed row-stochastic transition
matrix of the allowed arcs that G3 uses, with the same dangling rule (a node with no allowed
outgoing arc returns its mass to the seed distribution), the same full-degree rows, the same
admitted subgraph (``norn.graph.ppr.prepare``), the same seed and the same budgets. ``t`` is a
mathematical diffusion scale, the mean number of steps of the Poisson walk below. It is not a
duration, not seconds and not a neural frequency, and the result is neither truth nor causation.

Two computations of the same quantity are provided, as the owner asked on 20 November 2026:

* ``heat`` is the sparse Poisson series ``exp(-t) sum_k t^k / k! (P'^T)^k s``. Each term is one
  whole pass over the walked arcs (reserved whole against the global transition budget, like a
  G3 iteration). Because every term has L1 mass at most one, the unsummed Poisson tail
  ``1 - sum_{j<=K} w_j`` is a true L1 bound on the error of the partial sum, and the run stops when
  that tail is at most ``tail_tolerance`` (default 1e-6), at ``max_terms`` (default 100) or when a
  budget binds. A run whose tail is not met is flagged ``TAIL_NOT_MET`` and is never a converged
  full result. Poisson weights come from the recurrence ``w_{k+1} = w_k t / (k + 1)`` and ``t`` is
  capped at 50, so ``exp(-t)`` (about 2e-22 at the cap) cannot underflow and no weight can
  overflow; a ``t`` outside ``(0, 50]`` is refused.
* ``heat_exact`` is a pure-Python scaling-and-squaring matrix exponential of the walked subgraph,
  refused above 64 nodes (``HEAT_EXACT_TOO_LARGE``). It is the exact control for the series, not a
  production path, and it takes no tail (its error is floating-point round-off only).

When a node or edge budget cuts the subgraph, arcs into the cut part leak mass exactly as in G3
(rows keep their full-degree weight, nothing is renormalised) and the result is flagged and
labelled a bounded approximation; ``truncated`` reports the summed mass the cut removed. The
module reads a ``Graph`` and a ``Seed`` only: a denied object is not a node, an arc or a count.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.graph.adjacency import Graph
from norn.graph.bfs import TRANSITION_BUDGET
from norn.graph.contracts import NodeRef
from norn.graph.ppr import Entry, PprLimits, Walk, prepare, relation_weights
from norn.graph.seeds import Seed

DEFAULT_SCALE = 2.0
MAX_SCALE = 50.0
EXACT_NODE_CAP = 64
TAIL_NOT_MET = "TAIL_NOT_MET"
EXACT_TOO_LARGE = "HEAT_EXACT_TOO_LARGE"
MASS_VIOLATION = "HEAT_MASS_VIOLATION"
NON_FINITE = "HEAT_NON_FINITE"
SCORE_SEMANTICS = "DIFFUSION_PROPOSES_IDS_NOT_TRUTH_NOT_CAUSAL_NOT_ACCESS_SCALE_NOT_SECONDS"


@dataclass(frozen=True)
class HeatLimits:
    """Global bounds and tolerances of one run (pilot defaults, untuned)."""

    max_terms: int = 100
    tail_tolerance: float = 1e-6
    mass_tolerance: float = 1e-9
    max_nodes: int = 1000
    max_edges: int = 5000
    max_transitions: int = 20_000

    def __post_init__(self) -> None:
        for name, cap in (
            ("max_terms", 1000),
            ("max_nodes", 100_000),
            ("max_edges", 400_000),
            ("max_transitions", 10_000_000),
        ):
            value = getattr(self, name)
            require(type(value) is int and 1 <= value <= cap, "INVALID_HEAT_LIMIT")
        for name in ("tail_tolerance", "mass_tolerance"):
            value = getattr(self, name)
            require(
                type(value) is float and math.isfinite(value) and 0.0 < value <= 1.0,
                "INVALID_HEAT_LIMIT",
            )

    def budgets(self) -> PprLimits:
        """The same node, edge and transition budgets a G3 run would use."""
        return PprLimits(
            max_nodes=self.max_nodes,
            max_edges=self.max_edges,
            max_transitions=self.max_transitions,
        )


@dataclass(frozen=True)
class Heat:
    algorithm: str
    relations: tuple[tuple[str, float], ...]
    limits: HeatLimits
    scale: float
    entries: tuple[Entry, ...]  # ranked, most activated first
    edges: tuple[str, ...]  # unique edge ids admitted, sorted
    counters: tuple[tuple[str, int], ...]
    mass: tuple[tuple[str, float], ...]
    tail: float | None  # unsummed Poisson mass; None for the exact exponential
    error_bound: float | None  # L1 bound on the error: the tail; None for the exact exponential
    converged: bool  # the tail was met (series) or the exponential was formed (exact)
    flags: tuple[str, ...]
    unlinked: tuple[str, ...]
    unlinked_weight: float
    seed_digest: str

    @property
    def complete(self) -> bool:
        """True only when no bound bound, the tail was met and the seed had something to start."""
        return not self.flags

    def payload(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "relations": [list(r) for r in self.relations],
            "limits": [
                self.limits.max_terms,
                self.limits.tail_tolerance,
                self.limits.mass_tolerance,
                self.limits.max_nodes,
                self.limits.max_edges,
                self.limits.max_transitions,
            ],
            "scale": self.scale,
            "entries": [[e.node.kind, e.node.id, e.activation, e.via_edge] for e in self.entries],
            "edges": list(self.edges),
            "counters": [list(c) for c in self.counters],
            "mass": [list(m) for m in self.mass],
            "tail": self.tail,
            "error_bound": self.error_bound,
            "converged": self.converged,
            "flags": list(self.flags),
            "unlinked": list(self.unlinked),
            "unlinked_weight": self.unlinked_weight,
            "seed": self.seed_digest,
        }

    def digest(self) -> str:
        return digest(canonical(self.payload()).encode())


def check_scale(scale: float) -> float:
    require(
        type(scale) is float and math.isfinite(scale) and 0.0 < scale <= MAX_SCALE,
        "INVALID_SCALE",
    )
    return scale


def poisson_weights(scale: float, terms: int) -> list[float]:
    """``exp(-t) t^k / k!`` for k below ``terms``, by recurrence (no factorial, no overflow)."""
    check_scale(scale)
    weights = [math.exp(-scale)]
    for k in range(1, terms):
        weights.append(weights[-1] * scale / k)
    return weights


def _finish(
    algorithm: str,
    weights: dict[str, float],
    limits: HeatLimits,
    scale: float,
    walk: Walk,
    state: dict[NodeRef, float],
    via: dict[NodeRef, str],
    counters: tuple[tuple[str, int], ...],
    mass: tuple[tuple[str, float], ...],
    tail: float | None,
    converged: bool,
    flags: set[str],
    unlinked: tuple[str, ...],
    lost: float,
    seed: Seed,
) -> Heat:
    ranked = sorted(((n, v) for n, v in state.items() if v > 0.0), key=lambda i: (-i[1], i[0]))
    entries = tuple(Entry(n, v, via.get(n)) for n, v in ranked)
    return Heat(
        algorithm,
        tuple(sorted(weights.items())),
        limits,
        scale,
        entries,
        tuple(sorted(walk.edges)),
        counters,
        mass,
        tail,
        tail,
        converged,
        tuple(sorted(flags)),
        unlinked,
        lost,  # a seed sums to one, so the unlinked weight is also the unlinked share
        seed.digest(),
    )


def heat(
    graph: Graph,
    seed: Seed,
    limits: HeatLimits | None = None,
    scale: float = DEFAULT_SCALE,
    relations: Mapping[str, float] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> Heat:
    """Sparse Poisson series from the seed distribution within the global budgets."""
    limits = limits or HeatLimits()
    check_scale(scale)
    weights = relation_weights(relations)
    prepared = prepare(graph, seed, weights, limits.budgets(), checkpoint)
    walk, start, flags = prepared.walk, prepared.start, prepared.flags
    arcs_per_term = sum(len(r) for r in walk.rows.values())
    poisson = poisson_weights(scale, limits.max_terms)
    transitions = walk.transitions
    terms = 0  # passes over the arcs; term zero is the seed itself and costs none
    state: dict[NodeRef, float] = {}
    walker: dict[NodeRef, float] = dict(start)
    flow: dict[tuple[NodeRef, str], float] = {}
    covered = 0.0  # Poisson mass of the terms summed so far
    dangled = worst = 0.0
    if start:
        for node, share in start.items():
            state[node] = poisson[0] * share
        covered = poisson[0]
    while start and TRANSITION_BUDGET not in flags and 1 - covered > limits.tail_tolerance:
        if terms + 1 >= limits.max_terms:
            break
        if transitions + arcs_per_term > limits.max_transitions:
            flags.add(TRANSITION_BUDGET)  # a term is reserved whole or not run at all
            break
        if checkpoint is not None:
            checkpoint()
        transitions += arcs_per_term
        weight = poisson[terms + 1]
        following: dict[NodeRef, float] = {}
        dangling_mass = cut_mass = 0.0
        for node in sorted(walker):
            held = walker[node]
            if node in walk.dangling:
                dangling_mass += held
                continue
            for target, share, edge_id in walk.rows[node]:
                moved = held * share
                following[target] = following.get(target, 0.0) + moved
                key = (target, edge_id)
                flow[key] = flow.get(key, 0.0) + weight * moved
            cut_mass += held * walk.cut[node]
        for node, share in start.items():
            following[node] = following.get(node, 0.0) + dangling_mass * share
        error = abs(math.fsum(following.values()) - (math.fsum(walker.values()) - cut_mass))
        require(all(math.isfinite(v) and v >= 0.0 for v in following.values()), NON_FINITE)
        if error > limits.mass_tolerance:
            raise NornError(MASS_VIOLATION)
        worst = max(worst, error)
        walker = following
        for node, value in walker.items():
            state[node] = state.get(node, 0.0) + weight * value
        covered += weight
        dangled += weight * dangling_mass
        terms += 1
    tail = max(0.0, 1.0 - covered) if start else 0.0
    converged = not start or tail <= limits.tail_tolerance
    if start and not converged:
        flags.add(TAIL_NOT_MET)
    best: dict[NodeRef, tuple[float, str]] = {}
    for (target, edge_id), amount in sorted(flow.items()):
        if target not in best or (amount, edge_id) > best[target]:
            best[target] = (amount, edge_id)
    via = {n: e for n, (_a, e) in best.items()}
    held_mass = math.fsum(state.values())
    return _finish(
        "G4_HEAT_SERIES",
        weights,
        limits,
        scale,
        walk,
        state,
        via,
        (
            ("cut_arcs", walk.cut_arcs),
            ("edges", len(walk.edges)),
            ("nodes", len(walk.order)),
            ("terms", terms + 1 if start else 0),
            ("transitions", transitions),
        ),
        (
            ("activation", held_mass),
            ("dangling_restarted", dangled),
            ("max_mass_error", worst),
            ("truncated", max(0.0, covered - held_mass) if start else 0.0),
        ),
        tail,
        converged,
        flags,
        prepared.unlinked,
        prepared.lost,
        seed,
    )


def _multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    size = len(a)
    return [
        [math.fsum(a[i][k] * b[k][j] for k in range(size) if a[i][k] != 0.0) for j in range(size)]
        for i in range(size)
    ]


def _exponential(
    matrix: list[list[float]], checkpoint: Callable[[], None] | None
) -> list[list[float]]:
    """exp(matrix) by scaling and squaring with a Taylor core (round-off only)."""
    size = len(matrix)
    norm = max(
        (math.fsum(abs(matrix[i][j]) for i in range(size)) for j in range(size)), default=0.0
    )
    squarings = 0 if norm <= 0.5 else math.ceil(math.log2(norm / 0.5))
    scaled = [[v / 2**squarings for v in row] for row in matrix]
    identity = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
    result = [row[:] for row in identity]
    term = [row[:] for row in identity]
    for k in range(1, 20):  # ||scaled|| <= 0.5, so the 20th term is below 1e-19
        term = _multiply(term, scaled)
        term = [[v / k for v in row] for row in term]
        result = [
            [x + y for x, y in zip(r, t, strict=True)] for r, t in zip(result, term, strict=True)
        ]
    for _ in range(squarings):
        if checkpoint is not None:
            checkpoint()
        result = _multiply(result, result)
    return result


def heat_exact(
    graph: Graph,
    seed: Seed,
    limits: HeatLimits | None = None,
    scale: float = DEFAULT_SCALE,
    relations: Mapping[str, float] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> Heat:
    """exp(t (P' - I)) s on the walked subgraph by a dense matrix exponential (at most 64 nodes)."""
    limits = limits or HeatLimits()
    check_scale(scale)
    weights = relation_weights(relations)
    prepared = prepare(graph, seed, weights, limits.budgets(), checkpoint)
    walk, start, flags = prepared.walk, prepared.start, prepared.flags
    require(len(walk.order) <= EXACT_NODE_CAP, EXACT_TOO_LARGE)
    nodes = sorted(walk.order)
    index = {n: i for i, n in enumerate(nodes)}
    size = len(nodes)
    state: dict[NodeRef, float] = dict(start)
    worst = 0.0
    if start and TRANSITION_BUDGET not in flags:
        generator = [[-1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
        for node in nodes:
            column = index[node]
            if node in walk.dangling:
                for root, share in start.items():
                    generator[index[root]][column] += share
                continue
            for target, share, _edge in walk.rows[node]:
                generator[index[target]][column] += share
        grown = [[v * scale for v in row] for row in generator]
        kernel = _exponential(grown, checkpoint)
        seed_vector = [start.get(n, 0.0) for n in nodes]
        values = [
            math.fsum(kernel[i][j] * seed_vector[j] for j in range(size)) for i in range(size)
        ]
        require(all(math.isfinite(v) for v in values), NON_FINITE)
        require(all(v >= -1e-12 for v in values), NON_FINITE)
        state = {n: max(0.0, values[index[n]]) for n in nodes}
        total = math.fsum(state.values())
        if walk.cut_arcs == 0:
            worst = abs(total - 1.0)
            if worst > limits.mass_tolerance:
                raise NornError(MASS_VIOLATION)
        elif total > 1.0 + limits.mass_tolerance:
            raise NornError(MASS_VIOLATION)
    done = bool(start) and TRANSITION_BUDGET not in flags
    held = math.fsum(state.values())
    return _finish(
        "G4_HEAT_EXACT",
        weights,
        limits,
        scale,
        walk,
        state,
        {},
        (
            ("cut_arcs", walk.cut_arcs),
            ("edges", len(walk.edges)),
            ("nodes", len(walk.order)),
            ("terms", 0),
            ("transitions", walk.transitions),
        ),
        (
            ("activation", held),
            ("max_mass_error", worst),
            ("truncated", max(0.0, 1.0 - held) if done else 0.0),
        ),
        None,
        done or not start,
        flags,
        prepared.unlinked,
        prepared.lost,
        seed,
    )
