"""G1 bounded breadth-first traversal over the principal's eligible typed graph (P06-T04).

The traversal reads only a ``Graph`` already built for the principal (so a denied object is not a
node, an edge or a count here) and a ``Seed`` (the declared, shared starting weights). It never
queries canonical tables for topology, never reads a gold label, and never ranks by similarity.

Rules fixed by the owner on 14 November 2026 (see the T04 entry of ``ADR_LOG``):

* the default allowlist is ``REQUIRES`` (forward, requirer to required) and the reviewed
  ``IDENTITY_LINK`` (both ways), entity to entity; structural edges, ``HYPOTHESIZES_CAUSE`` and
  the non-traversable relations are off unless a caller narrows them in, and only traversable
  relations can be asked for;
* source candidates are the supports of the edge that reached each node and the defining source
  of each reached entity, in the rank order of the traversal;
* the pilot envelope is untuned: 4 hops, fanout 32, 1,000 unique nodes, 5,000 unique edges and
  20,000 processed transitions, all global across every seed and every iteration.

Budgets are global: unique nodes and unique edges admitted, and every arc examined counts as a
processed transition even when its target was visited before, so revisits are bounded work too.
A bound that binds is a named flag on the result (``HOP_LIMIT``, ``FANOUT_LIMIT``,
``NODE_BUDGET``, ``EDGE_BUDGET``, ``TRANSITION_BUDGET``), never a silent truncation, and the
result is then a bounded approximation, not the full reachable set. All counts and flags are
computed over the eligible graph only, so adding an object the principal cannot read changes no
byte of the result.
"""

import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from norn.canonical.registry import Registry
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.graph.adjacency import Graph
from norn.graph.contracts import RELATIONS, Arc, NodeRef
from norn.graph.seeds import EMPTY_SEED, Seed

DEFAULT_RELATIONS = frozenset({"REQUIRES", "IDENTITY_LINK"})
NO_LINKED_ANCHOR = "NO_LINKED_ANCHOR"
HOP_LIMIT = "HOP_LIMIT"
FANOUT_LIMIT = "FANOUT_LIMIT"
NODE_BUDGET = "NODE_BUDGET"
EDGE_BUDGET = "EDGE_BUDGET"
TRANSITION_BUDGET = "TRANSITION_BUDGET"
CHECK_EVERY = 64


@dataclass(frozen=True)
class Limits:
    """Global bounds of one traversal (pilot defaults, untuned: T21 pins the real envelope)."""

    max_hops: int = 4
    fanout: int = 32
    max_nodes: int = 1000
    max_edges: int = 5000
    max_transitions: int = 20_000

    def __post_init__(self) -> None:
        for name, cap in (
            ("max_hops", 16),
            ("fanout", 1000),
            ("max_nodes", 100_000),
            ("max_edges", 400_000),
            ("max_transitions", 10_000_000),
        ):
            value = getattr(self, name)
            require(type(value) is int and 1 <= value <= cap, "INVALID_TRAVERSAL_LIMIT")


@dataclass(frozen=True)
class Step:
    """One reached node with the exact edges of the path that reached it.

    ``score`` is None for breadth-first steps (the order is the hop, then the seed weight) and the
    damped best-path contribution for G2, which is not an activation and not a probability."""

    node: NodeRef
    hop: int
    origin: str  # entity id of the seed anchor the path starts at
    edge_id: str | None
    parent: NodeRef | None
    score: float | None
    path: tuple[str, ...]  # edge ids from the origin, in order


@dataclass(frozen=True)
class Traversal:
    algorithm: str
    relations: tuple[str, ...]
    limits: Limits
    gamma: float | None
    steps: tuple[Step, ...]  # ranked, best first
    edges: tuple[str, ...]  # unique edge ids examined, sorted
    counters: tuple[tuple[str, int], ...]
    flags: tuple[str, ...]
    unlinked: tuple[str, ...]  # seed anchors that are not nodes of this graph
    seed_digest: str

    @property
    def complete(self) -> bool:
        """True only when no bound bound and the seed had something to start from."""
        return not self.flags

    def payload(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "relations": list(self.relations),
            "limits": [
                self.limits.max_hops,
                self.limits.fanout,
                self.limits.max_nodes,
                self.limits.max_edges,
                self.limits.max_transitions,
            ],
            "gamma": self.gamma,
            "steps": [
                [s.node.kind, s.node.id, s.hop, s.origin, s.edge_id, s.score, list(s.path)]
                for s in self.steps
            ],
            "edges": list(self.edges),
            "counters": [list(c) for c in self.counters],
            "flags": list(self.flags),
            "unlinked": list(self.unlinked),
            "seed": self.seed_digest,
        }

    def digest(self) -> str:
        return digest(canonical(self.payload()).encode())


@dataclass(frozen=True)
class Candidate:
    """A source recovered through the traversal and why it was reached."""

    source_id: str
    node: NodeRef
    hop: int
    kind: str  # EDGE_SUPPORT or DEFINING_SOURCE
    edge_id: str | None


def check_relations(relations: frozenset[str]) -> tuple[str, ...]:
    require(len(relations) > 0, "EMPTY_RELATION_ALLOWLIST")
    for name in relations:
        relation = RELATIONS.get(name)
        require(relation is not None and relation.traversable, "UNSUPPORTED_RELATION_ALLOWLIST")
    return tuple(sorted(relations))


def roots_of(graph: Graph, seed: Seed) -> tuple[list[tuple[NodeRef, float]], list[str], set[str]]:
    """Seed anchors that are graph nodes, best weight first; the rest are reported, never used."""
    require(isinstance(seed, Seed), "INVALID_SEED")
    roots: list[tuple[NodeRef, float]] = []
    unlinked: list[str] = []
    flags: set[str] = set()
    if not seed.anchors:
        flags.add(EMPTY_SEED)
    for anchor in sorted(seed.anchors, key=lambda a: (-a.weight, a.entity_id)):
        require(math.isfinite(anchor.weight) and anchor.weight > 0, "INVALID_SEED")
        node = NodeRef("entity", anchor.entity_id)
        if graph.has(node):
            roots.append((node, anchor.weight))
        else:
            unlinked.append(anchor.entity_id)
    if seed.anchors and not roots:
        flags.add(NO_LINKED_ANCHOR)  # nothing to start from is not a complete, empty answer
    return roots, unlinked, flags


def arcs_of(graph: Graph, node: NodeRef, relations: tuple[str, ...]) -> list[Arc]:
    return sorted(graph.neighbors(node, frozenset(relations)))


class Meter:
    """The global counters of one traversal; every method is O(1)."""

    def __init__(self, limits: Limits, checkpoint: Callable[[], None] | None):
        self.limits, self.checkpoint = limits, checkpoint
        self.edges: set[str] = set()
        self.transitions = 0
        self.fanout_cut = 0
        self.flags: set[str] = set()

    def tick(self) -> None:
        if self.checkpoint is not None and self.transitions % CHECK_EVERY == 0:
            self.checkpoint()

    def arcs(self, graph: Graph, node: NodeRef, relations: tuple[str, ...]) -> list[Arc]:
        """The arcs to follow from ``node`` after the per-node fanout bound."""
        found = arcs_of(graph, node, relations)
        if len(found) > self.limits.fanout:
            self.fanout_cut += len(found) - self.limits.fanout
            self.flags.add(FANOUT_LIMIT)
            found = found[: self.limits.fanout]
        return found

    def exhausted(self) -> bool:
        return TRANSITION_BUDGET in self.flags

    def transition(self, edge_id: str) -> bool:
        """Reserve one processed transition and admit its edge; False means do not follow it."""
        if self.transitions >= self.limits.max_transitions:
            self.flags.add(TRANSITION_BUDGET)
            return False
        self.tick()
        self.transitions += 1
        if edge_id not in self.edges:
            if len(self.edges) >= self.limits.max_edges:
                self.flags.add(EDGE_BUDGET)
                return False
            self.edges.add(edge_id)
        return True

    def counters(self, nodes: int, hop_cut: int) -> tuple[tuple[str, int], ...]:
        return (
            ("edges", len(self.edges)),
            ("fanout_cut_arcs", self.fanout_cut),
            ("hop_cut_nodes", hop_cut),
            ("nodes", nodes),
            ("transitions", self.transitions),
        )


def hop_cut(
    graph: Graph, relations: tuple[str, ...], reached: dict[NodeRef, int], max_hops: int
) -> int:
    """Nodes at the hop limit that still have an allowed arc to a node never reached."""
    return sum(
        1
        for node, hop in sorted(reached.items())
        if hop == max_hops
        and any(a.neighbor not in reached for a in arcs_of(graph, node, relations))
    )


def bfs(
    graph: Graph,
    seed: Seed,
    limits: Limits | None = None,
    relations: frozenset[str] = DEFAULT_RELATIONS,
    checkpoint: Callable[[], None] | None = None,
) -> Traversal:
    """FIFO breadth-first walk from the seed anchors; each node keeps its first (shortest) path."""
    limits = limits or Limits()
    allowed = check_relations(relations)
    roots, unlinked, flags = roots_of(graph, seed)
    meter = Meter(limits, checkpoint)
    meter.flags |= flags
    visited: dict[NodeRef, Step] = {}
    queue: deque[NodeRef] = deque()
    for node, _weight in roots:
        if len(visited) >= limits.max_nodes:
            meter.flags.add(NODE_BUDGET)
            break
        visited[node] = Step(node, 0, node.id, None, None, None, ())
        queue.append(node)
    exhausted = False
    while queue and not exhausted:
        if checkpoint is not None:
            checkpoint()
        node = queue.popleft()
        step = visited[node]
        if step.hop >= limits.max_hops:
            continue
        for arc in meter.arcs(graph, node, allowed):
            if not meter.transition(arc.edge_id):
                if meter.exhausted():
                    exhausted = True
                    break
                continue
            if arc.neighbor in visited:
                continue
            if len(visited) >= limits.max_nodes:
                meter.flags.add(NODE_BUDGET)
                continue
            visited[arc.neighbor] = Step(
                arc.neighbor,
                step.hop + 1,
                step.origin,
                arc.edge_id,
                node,
                None,
                (*step.path, arc.edge_id),
            )
            queue.append(arc.neighbor)
    reached = {n: s.hop for n, s in visited.items()}
    cut = hop_cut(graph, allowed, reached, limits.max_hops)
    if cut:
        meter.flags.add(HOP_LIMIT)
    return Traversal(
        "G1_BFS",
        allowed,
        limits,
        None,
        tuple(visited.values()),
        tuple(sorted(meter.edges)),
        meter.counters(len(visited), cut),
        tuple(sorted(meter.flags)),
        tuple(unlinked),
        seed.digest(),
    )


def defining_sources(registry: Registry, entity_ids: list[str]) -> dict[str, str]:
    """The source each entity was first defined by, when the principal may read that source."""
    if not entity_ids:
        return {}
    marks = ",".join("?" for _ in entity_ids)
    rows = registry.db.connection.execute(
        "SELECT e.id, v.source_id FROM entities e "
        "JOIN source_spans s ON s.ns=e.ns AND s.id=e.provisional_span_id "
        "JOIN source_versions v ON v.ns=s.ns AND v.id=s.version_id "
        "WHERE e.ns=? AND e.id IN (" + marks + ")",
        (registry.ns, *entity_ids),
    ).fetchall()
    return {str(r[0]): str(r[1]) for r in rows if registry.access.eligible("READ", str(r[1]))}


def path_candidates(
    registry: Registry, graph: Graph, traversal: Traversal
) -> tuple[Candidate, ...]:
    """Sources recovered by a traversal, first reason only, in the traversal's rank order.

    A step contributes the supports of the edge that reached it (all readable, because the graph
    keeps an edge only when every support is) and the defining source of an entity node."""
    defining = defining_sources(
        registry, [s.node.id for s in traversal.steps if s.node.kind == "entity"]
    )
    found: dict[str, Candidate] = {}
    for step in traversal.steps:
        if step.edge_id is not None:
            edge = graph.edge(step.edge_id)
            require(edge is not None, "TRAVERSAL_EDGE_UNKNOWN")
            assert edge is not None
            for support in edge.supports:
                found.setdefault(
                    support.source_id,
                    Candidate(support.source_id, step.node, step.hop, "EDGE_SUPPORT", step.edge_id),
                )
        owner = defining.get(step.node.id) if step.node.kind == "entity" else None
        if owner is not None:
            found.setdefault(
                owner, Candidate(owner, step.node, step.hop, "DEFINING_SOURCE", step.edge_id)
            )
    return tuple(found.values())
