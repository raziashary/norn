"""G2 damped best-path scoring over the principal's eligible typed graph (P06-T04).

A transparent, explanatory control, not an activation: each node keeps its single best simple
path, scored ``s(v0) * gamma^h * product(p_edge)`` with the seed weight ``s(v0)`` of the path's
origin and ``p_edge = 1 / (allowed out-arcs of the step's source)``, the same uniform
row-stochastic transition that personalised PageRank will use. Paths of at most ``max_hops`` hops
are compared by a layered relaxation, so a longer low-degree path can beat a shorter high-degree
one. A path needs no revisit check: every step multiplies the score by ``gamma < 1`` and
``p_edge <= 1``, so a cycle scores strictly below the earlier visit of its node and is never
accepted (the cycle test asserts it). The score is neither full PPR (it does not add up the many
walks that reach a node) nor a claim of causation: a node is ranked by how directly the typed
edges connect it to the seed, and the edges are exactly those whose support a reader can open.

Owner answers of 14 November 2026: gamma 0.7 and the pilot envelope are untuned defaults; one
best path per node; the allowlist and the global budgets are those of ``norn.graph.bfs``. The
per-node fanout bound truncates which arcs are followed, while ``p_edge`` keeps using the full
eligible out-degree, so degree normalisation is not distorted by the cut (which is flagged).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from norn.contracts.errors import require
from norn.graph.adjacency import Graph
from norn.graph.bfs import (
    DEFAULT_RELATIONS,
    HOP_LIMIT,
    NODE_BUDGET,
    Limits,
    Meter,
    Step,
    Traversal,
    arcs_of,
    check_relations,
    hop_cut,
    roots_of,
)
from norn.graph.contracts import NodeRef
from norn.graph.seeds import Seed

DEFAULT_GAMMA = 0.7
SCORE_SEMANTICS = "DIAGNOSTIC_BEST_PATH_NOT_PPR_NOT_CAUSAL"


@dataclass(frozen=True)
class _Best:
    score: float
    hop: int
    origin: str
    edge_id: str | None
    parent: NodeRef | None
    edges: tuple[str, ...]


def damped_paths(
    graph: Graph,
    seed: Seed,
    limits: Limits | None = None,
    gamma: float = DEFAULT_GAMMA,
    relations: frozenset[str] = DEFAULT_RELATIONS,
    checkpoint: Callable[[], None] | None = None,
) -> Traversal:
    """Best simple path per reachable node within the hop limit and the global budgets."""
    limits = limits or Limits()
    require(type(gamma) is float and math.isfinite(gamma) and 0.0 < gamma < 1.0, "INVALID_GAMMA")
    allowed = check_relations(relations)
    roots, unlinked, flags = roots_of(graph, seed)
    meter = Meter(limits, checkpoint)
    meter.flags |= flags
    best: dict[NodeRef, _Best] = {}
    for node, weight in roots:
        if len(best) >= limits.max_nodes:
            meter.flags.add(NODE_BUDGET)
            break
        best[node] = _Best(weight, 0, node.id, None, None, ())
    improved = sorted(best)
    for _layer in range(limits.max_hops):
        if not improved or meter.exhausted():
            break
        frozen = {n: best[n] for n in improved}  # paths of at most `layer` hops, as they stood
        changed: set[NodeRef] = set()
        for node in sorted(frozen):
            if checkpoint is not None:
                checkpoint()
            here = frozen[node]
            out_degree = len(arcs_of(graph, node, allowed))
            for arc in meter.arcs(graph, node, allowed):
                if not meter.transition(arc.edge_id):
                    if meter.exhausted():
                        break
                    continue
                score = here.score * gamma / out_degree
                require(math.isfinite(score) and score > 0, "PATH_SCORE_INVALID")
                known = best.get(arc.neighbor)
                if known is None and len(best) >= limits.max_nodes:
                    meter.flags.add(NODE_BUDGET)
                    continue
                if known is None or score > known.score:
                    best[arc.neighbor] = _Best(
                        score,
                        here.hop + 1,
                        here.origin,
                        arc.edge_id,
                        node,
                        (*here.edges, arc.edge_id),
                    )
                    changed.add(arc.neighbor)
            if meter.exhausted():
                break
        improved = sorted(changed)
    reached = {n: b.hop for n, b in best.items()}
    cut = hop_cut(graph, allowed, reached, limits.max_hops)
    if cut:
        meter.flags.add(HOP_LIMIT)
    ranked = sorted(best.items(), key=lambda item: (-item[1].score, item[1].hop, item[0]))
    steps = tuple(
        Step(n, b.hop, b.origin, b.edge_id, b.parent, b.score, b.edges) for n, b in ranked
    )
    return Traversal(
        "G2_DAMPED_PATH",
        allowed,
        limits,
        gamma,
        steps,
        tuple(sorted(meter.edges)),
        meter.counters(len(best), cut),
        tuple(sorted(meter.flags)),
        tuple(unlinked),
        seed.digest(),
    )
