"""public-v2: multi-hop families M1 to M6 over 20 to 60 sources per namespace (P06-T18).

Every chain link states its target by a governed external key and every node source carries one
``[key:..]`` (or ``[alias:..]``) statement in the message, so shared identity comes only from the
published text (T17). The hidden graph, private sources and role bookkeeping stay in
``GraphGold`` and never enter a published input.
"""

from dataclasses import dataclass

from benchmark.adapters.contracts import PublishedSource, Query
from benchmark.fixtures.entities import Entity, entity, opaque
from benchmark.fixtures.partitions import Partition
from benchmark.fixtures.render import render
from benchmark.fixtures.scenarios import Case, Gold
from benchmark.fixtures.world import Fact
from norn.contracts.errors import require

TAG = "public-v2"
SOURCE_TAG = "publication-v2"
FAMILIES = ("M1", "M2", "M3", "M4", "M5", "M6")
PRIMARY = ("M1", "M2", "M3", "M4")
VARIANTS = {
    "M1": ("positive", "missing"),
    "M2": ("positive", "missing"),
    "M3": ("positive", "missing"),
    "M4": ("positive", "missing"),
    "M5": ("positive", "ambiguous"),
    "M6": ("positive", "missing"),
}
# Owner decision (13 November 2026): primary-weighted split, clusters per family in
# (M1 to M4, M5 and M6). Totals: pilot 24, tune 48, evaluation 240 (200 on the primary families).
ROLE_CLUSTERS = {"pilot": (5, 2), "tune": (10, 4), "evaluation": (50, 20)}
SEARCH_BUDGET = 60
MIN_POOL, MAX_POOL = 20, 60
EVENT = "2026-10-20T09:00:00+00:00"
RECORDED = "2026-10-20T12:00:00+00:00"
KNOWLEDGE = "2026-10-23T00:00:00+00:00"

Node = tuple[str, str, str]  # (hidden id, display name, governed key)


@dataclass(frozen=True)
class GraphGold:
    """Evaluator-only hidden graph for one query; never published."""

    query_id: str
    family: str
    cluster: str
    variant: str
    nodes: tuple[Node, ...]
    edges: tuple[tuple[str, str, str, str], ...]  # (from hidden, to hidden, relation, source id)
    identity_links: tuple[tuple[str, str], ...]  # (stating source id, alias name)
    seed_node: str
    hub_node: str
    decoy_sources: tuple[str, ...]
    private_sources: tuple[PublishedSource, ...]
    pool_size: int


@dataclass(frozen=True)
class MultiHopCase:
    case: Case
    graph: GraphGold


@dataclass(frozen=True)
class Piece:
    tag: str
    source: PublishedSource
    role: str


def multihop_partition(seed: int, role: str) -> Partition:
    require(role in ROLE_CLUSTERS and type(seed) is int and seed >= 0, "INVALID_PARTITION")
    primary, secondary = ROLE_CLUSTERS[role]
    return Partition(
        role,
        tuple(
            (family, entity(seed, role, family, index))
            for family in FAMILIES
            for index in range(primary if family in PRIMARY else secondary)
        ),
    )


class _Cluster:
    """Deterministic names, facts and sources for one entity cluster."""

    def __init__(self, seed: int, root: Entity):
        self.seed, self.root, self.cluster = seed, root, root.cluster_id
        self.namespace = "synthetic/" + opaque("scope", TAG, seed, self.cluster)[6:22] + "/local"
        self.pieces: dict[str, Piece] = {}
        self.private: dict[str, Piece] = {}
        self.nodes: dict[str, Node] = {}
        self.edges: list[tuple[str, str, str, str]] = []
        self.alias_links: list[tuple[str, str]] = []
        span = MAX_POOL - MIN_POOL + 1
        self.pool = MIN_POOL + int(opaque("pool", seed, self.cluster)[-4:], 16) % span

    def hexed(self, *parts: object) -> str:
        return opaque("hidden", self.seed, self.cluster, *parts)[7:]

    def node(self, index: int | str, prefix: str = "Svc") -> Node:
        if index == 0:
            return self.root.hidden_id, self.root.alias, "svc." + self.hexed("key", 0)[:14]
        return (
            opaque("hidden", "node", self.seed, self.cluster, index),
            f"{prefix}-{self.hexed('name', index)[:10]}",
            "svc." + self.hexed("key", index)[:14],
        )

    def add(
        self,
        tag: str,
        actor: str,
        predicate: str,
        value: str,
        suffix: str = "",
        role: str = "chain",
        *,
        private: bool = False,
        event_time: str = EVENT,
    ) -> str:
        fact = Fact(
            opaque("hidden", "fact", self.seed, self.cluster, tag),
            actor,
            predicate,
            value,
            event_time,
            RECORDED,
            "DIRECT_OBSERVATION",
            opaque("origin", self.seed, self.cluster, tag),
        )
        source = render(
            fact,
            seed=self.seed,
            namespace=self.namespace,
            principals=("other",) if private else ("reader",),
            suffix=suffix,
            tag=SOURCE_TAG,
        )
        (self.private if private else self.pieces)[tag] = Piece(tag, source, role)
        return source.source_id

    def link(
        self, tag: str, source: Node, target: Node, role: str = "chain", *, private: bool = False
    ) -> str:
        """A requirement link: the value is the target's governed key, the key is the source's."""
        suffix = f" [key:{source[2]}]"
        sid = self.add(tag, source[1], "requires", target[2], suffix, role, private=private)
        self.nodes.update({source[0]: source, target[0]: target})
        self.edges.append((source[0], target[0], "REQUIRES", sid))
        return sid

    def define(self, tag: str, node: Node, role: str = "define") -> str:
        self.nodes[node[0]] = node
        return self.add(tag, node[1], "registered", "active", f" [key:{node[2]}]", role)

    def fill(self, bait_of: str | None) -> None:
        """Name-bait mentions and background pairs up to the pool size; core is never altered."""
        if bait_of is not None:
            for index in range(2 + int(self.hexed("bait")[:2], 16) % 4):
                actor = f"Note-{self.hexed('bait', index)[:10]}"
                self.add(f"bait-{index}", actor, "mentions", bait_of, "", "bait")
        index = 0
        while len(self.pieces) < self.pool:
            if self.pool - len(self.pieces) >= 2:
                a, b = self.node(f"bg{index}a", "Bg"), self.node(f"bg{index}b", "Bg")
                self.link(f"bg-{index}-link", a, b, "background")
                self.define(f"bg-{index}-def", b, "background")
            else:
                actor = f"Bg-{self.hexed('bg', index)[:10]}"
                self.add(f"bg-{index}-solo", actor, "observed", "idle", "", "background")
            index += 1
        require(MIN_POOL <= len(self.pieces) <= MAX_POOL, "POOL_SIZE_OUT_OF_RANGE")


def _build(seed: int, family: str, root: Entity, variant: str) -> MultiHopCase:
    c = _Cluster(seed, root)
    n0, n1, n2 = c.node(0), c.node(1), c.node(2)
    chain_question = f"Which complete requirement chain starts at {n0[1]}?"
    request = chain_question
    slots: list[tuple[str, ...]] = []
    hub = ""
    decoys: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    canaries: tuple[str, ...] = ()
    drop: set[str] = set()
    bait: str | None = n0[1]

    if family == "M1":
        slots = [(c.link("l0", n0, n1),), (c.link("l1", n1, n2),)]
        c.define("d2", n2)
        drop = {"l1"}
    elif family == "M2":
        # Three or four hops; hop 2 is stated under an alias name of node 1, whose own key is
        # defined by a separate source: the identity bridge is evidence the answer needs.
        hops = 3 + int(c.hexed("hops")[0], 16) % 2
        chain = [n0, n1, n2] + [c.node(i + 3) for i in range(hops - 2)]
        alias_name = f"Alt-{c.hexed('alias')[:10]}"
        slots.append((c.link("l0", chain[0], chain[1]),))
        bridge = c.define("d1", chain[1], "identity")
        stated = c.add("l1", alias_name, "requires", chain[2][2], f" [alias:{chain[1][1]}]")
        c.nodes[chain[2][0]] = chain[2]
        c.edges.append((chain[1][0], chain[2][0], "REQUIRES", stated))
        c.alias_links.append((stated, chain[1][1]))
        slots.append((stated,))
        slots.extend((c.link(f"l{i}", chain[i], chain[i + 1]),) for i in range(2, hops))
        slots.append((bridge,))
        c.define("dn", chain[hops])
        drop = {f"l{hops - 1}"}
    elif family == "M3":
        hub = n1[0]
        slots = [(c.link("l0", n0, n1),), (c.link("l1", n1, n2),)]
        c.define("d2", n2)
        count = 12 + int(c.hexed("decoys")[:2], 16) % 29
        decoys = tuple(
            c.link(f"decoy-{i}", c.node(f"decoy{i}", "Dep"), n1, "decoy") for i in range(count)
        )
        drop = {"l1"}
    elif family == "M4":
        # Public detour l0, l1; a private shortcut through a node only the other principal reads.
        slots = [(c.link("l0", n0, n1),), (c.link("l1", n1, n2),)]
        c.define("d2", n2)
        hidden_mid = c.node("private", "Prv")
        p0 = c.link("p0", n0, hidden_mid, "private", private=True)
        p1 = c.link("p1", hidden_mid, n2, "private", private=True)
        forbidden, canaries = (p0, p1), (hidden_mid[2],)
        drop = {"l1"}
    elif family == "M5":
        # Two entities share one display name; only the governed key tells them apart.
        o0 = (opaque("hidden", "node", seed, c.cluster, "twin"), n0[1], c.node("twin")[2])
        o1, o2 = c.node("twin1"), c.node("twin2")
        slots = [(c.link("l0", n0, n1),), (c.link("l1", n1, n2),)]
        c.define("d2", n2)
        for tag, src, dst in (("t0", o0, o1), ("t1", o1, o2)):
            sid = c.add(
                tag,
                src[1],
                "requires",
                dst[2],
                f" [key:{src[2]}]",
                "distractor",
                event_time="2026-10-19T09:00:00+00:00",
            )
            c.nodes.update({src[0]: src, dst[0]: dst})
            c.edges.append((src[0], dst[0], "REQUIRES", sid))
        c.define("td2", o2, "distractor")
        request = f"Which complete requirement chain starts at {n0[1]} (key {n0[2]})?"
    else:  # M6: near-duplicate episodes of one entity, distinguished only by the event date
        episodes = 4 + int(c.hexed("episodes")[0], 16) % 5
        days = [f"2026-10-{10 + i:02d}" for i in range(episodes)]
        target = days[int(c.hexed("target")[:2], 16) % episodes]
        c.nodes[n0[0]] = n0
        for day in days:
            sid = c.add(
                f"ep-{day}",
                n0[1],
                "parked_in",
                "ZoneA",
                f" [key:{n0[2]}]",
                "episode",
                event_time=f"{day}T09:00:00+00:00",
            )
            if day == target:
                slots, drop = [(sid,)], {f"ep-{day}"}
        request, bait = f"Where was {n0[1]} observed parking on {target}?", None

    status, reason = "SUPPORTED", "SUFFICIENT"
    if variant == "missing":
        status = "NOT_ESTABLISHED"
        reason = "PRIVATE_BRIDGE_UNREADABLE" if family == "M4" else "MISSING_SUPPORT"
        for tag in drop:
            del c.pieces[tag]
    elif variant == "ambiguous":
        status, reason, request = "NOT_ESTABLISHED", "AMBIGUOUS_SAME_NAME", chain_question
    c.fill(bait)
    published = tuple(sorted((p.source for p in c.pieces.values()), key=lambda s: s.source_id))
    qid = opaque("query", TAG, seed, c.namespace, variant, "en")
    query = Query(
        qid,
        request,
        c.namespace,
        "reader",
        KNOWLEDGE,
        KNOWLEDGE,
        "UTC",
        10,
        2000,
        ("source_read",),
        SEARCH_BUDGET,
    )
    supported = status == "SUPPORTED"
    event_of = {s.source_id: s.event_id for s in published}
    gold = Gold(
        qid,
        family,
        c.cluster,
        variant,
        "en",
        status,
        reason,
        (tuple(s for slot in slots for s in slot),) if supported else (),
        tuple(slots),
        tuple(sorted({event_of[s] for slot in slots for s in slot})) if supported else (),
        forbidden,
        canaries,
        0.0,
        "CANONICAL_FALLBACK",
    )
    graph = GraphGold(
        qid,
        family,
        c.cluster,
        variant,
        tuple(sorted(c.nodes.values())),
        tuple(c.edges),
        tuple(c.alias_links),
        n0[0],
        hub,
        decoys,
        tuple(p.source for p in c.private.values()),
        len(published),
    )
    return MultiHopCase(Case(query, published, gold), graph)


def multihop_cases(seed: int, role: str) -> tuple[MultiHopCase, ...]:
    result = [
        _build(seed, family, root, variant)
        for family, root in multihop_partition(seed, role).entities
        for variant in VARIANTS[family]
    ]
    require(len({m.case.query.query_id for m in result}) == len(result), "DUPLICATE_QUERY")
    return tuple(result)
