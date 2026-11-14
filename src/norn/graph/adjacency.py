"""Canonical typed adjacency rebuilt from the registry for one principal (P06-T01).

``write_edge`` is the only governed writer of ``graph_edges``; ``build_graph`` is the reader that
seed and traversal code call. The graph holds only what the principal may read at an explicit
snapshot: every node passes ``Access.eligible``, every stored edge additionally has all of its
support sources eligible and both endpoints present, and structural edges (an atom belongs to its
event, was observed in its source, mentions its entities; a reviewed SAME_AS decision links two
entities) are derived from canonical records, never from similarity. An object the principal
cannot read is absent from nodes, edges, arcs and the digest, so adding one changes nothing the
principal sees.
"""

import sqlite3
from dataclasses import dataclass, field

from norn.canonical.outbox import allocate, publish
from norn.canonical.registry import Registry
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, stable_id
from norn.graph.contracts import (
    RELATIONS,
    Arc,
    EdgeSpec,
    GraphEdge,
    GraphSnapshot,
    NodeRef,
    Support,
)

DENIED = "NOT_AUTHORIZED_OR_NOT_FOUND"
STRUCTURAL_REVISION = "canonical-structure-v1"
MAX_NODES = 100_000
MAX_EDGES = 400_000

_SOURCE_OF_SPAN = (
    "SELECT v.source_id FROM source_spans s JOIN source_versions v "
    "ON s.ns=v.ns AND s.version_id=v.id WHERE s.ns=? AND s.id=?"
)


@dataclass(frozen=True)
class Graph:
    """An immutable, deterministic view: same canonical state and principal, same digest."""

    snapshot: GraphSnapshot
    nodes: tuple[NodeRef, ...]
    edges: tuple[GraphEdge, ...]
    arcs: dict[NodeRef, tuple[Arc, ...]]
    invalid_edges: int = 0
    _by_id: dict[str, GraphEdge] = field(default_factory=dict, repr=False, compare=False)

    def edge(self, edge_id: str) -> GraphEdge | None:
        return self._by_id.get(edge_id)

    def has(self, node: NodeRef) -> bool:
        return node in self.arcs

    def neighbors(
        self,
        node: NodeRef,
        relations: frozenset[str] | None = None,
        *,
        reverse: bool = False,
    ) -> tuple[Arc, ...]:
        """Arcs leaving ``node`` along the stated direction (symmetric relations either way);
        ``reverse=True`` also follows directed edges backwards. Unknown nodes have none."""
        return tuple(
            a
            for a in self.arcs.get(node, ())
            if (a.forward or reverse) and (relations is None or a.relation in relations)
        )

    def digest(self) -> str:
        return digest(
            canonical(
                {
                    "valid_at": self.snapshot.valid_at,
                    "nodes": [[n.kind, n.id] for n in self.nodes],
                    "edges": [e.payload() for e in self.edges],
                }
            ).encode()
        )


def write_edge(registry: Registry, spec: EdgeSpec) -> str:
    """Store one governed edge with its supports; replaying the same request adds nothing."""
    spec.validate()
    ns, access = registry.ns, registry.access
    with registry.db.transaction() as connection:
        access.check("WRITE")
        for node in (spec.source, spec.target):
            access.check("READ", node.id)
            row = connection.execute(
                "SELECT kind FROM objects WHERE ns=? AND id=?", (ns, node.id)
            ).fetchone()
            require(row is not None and row[0] == node.kind, DENIED)
        for span in spec.support_spans:
            owner = connection.execute(_SOURCE_OF_SPAN, (ns, span)).fetchone()
            require(owner is not None, DENIED)
            access.check("READ", str(owner[0]))
        edge_id = spec.identity(ns)
        if connection.execute(
            "SELECT 1 FROM graph_edges WHERE ns=? AND id=?", (ns, edge_id)
        ).fetchone():
            return edge_id
        seq = allocate(connection, ns)
        connection.execute("INSERT INTO objects VALUES(?,?,'graph_edge')", (ns, edge_id))
        connection.execute(
            "INSERT INTO graph_edges(ns,id,from_id,from_kind,to_id,to_kind,relation_type,"
            "epistemic,status,scope,source_span_id,valid_from,valid_to,producer_revision,"
            "commit_seq) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ns,
                edge_id,
                spec.source.id,
                spec.source.kind,
                spec.target.id,
                spec.target.kind,
                spec.relation,
                spec.epistemic,
                spec.status,
                spec.scope,
                min(spec.support_spans),
                spec.valid_from,
                spec.valid_to,
                spec.producer_revision,
                seq,
            ),
        )
        for span in sorted(spec.support_spans):
            connection.execute(
                "INSERT INTO graph_edge_support VALUES(?,?,?,?)",
                (ns, edge_id, span, spec.producer_revision),
            )
        publish(connection, ns, seq, "GRAPH_EDGE", [edge_id])
    return edge_id


def _check_policy(registry: Registry) -> None:
    """The in-code relation policy must equal the stored ``relation_types`` rows."""
    rows = registry.db.connection.execute(
        "SELECT name,traversable,causal FROM relation_types"
    ).fetchall()
    stored = {r[0]: (bool(r[1]), bool(r[2])) for r in rows}
    expected = {r.name: (r.traversable, r.causal) for r in RELATIONS.values()}
    require(stored == expected, "GRAPH_POLICY_MISMATCH")


def _current_seq(registry: Registry) -> int:
    row = registry.db.connection.execute(
        "SELECT commit_seq FROM namespaces WHERE ns=?", (registry.ns,)
    ).fetchone()
    require(row is not None, DENIED)
    return int(row[0])


def build_graph(
    registry: Registry,
    snapshot: GraphSnapshot | None = None,
    *,
    max_nodes: int = MAX_NODES,
    max_edges: int = MAX_EDGES,
) -> Graph:
    """Rebuild the principal's eligible typed graph; exceeding a budget fails, never truncates."""
    require(max_nodes > 0 and max_edges > 0, "INVALID_GRAPH_BUDGET")
    registry.access.check("READ")
    _check_policy(registry)
    snap = snapshot or GraphSnapshot(_current_seq(registry))
    require(snap.seq >= 0, "INVALID_SNAPSHOT")
    builder = _Builder(registry, snap, max_nodes, max_edges)
    return builder.build()


class _Builder:
    def __init__(self, registry: Registry, snap: GraphSnapshot, max_nodes: int, max_edges: int):
        self.registry, self.snap = registry, snap
        self.max_nodes, self.max_edges = max_nodes, max_edges
        self.connection, self.ns = registry.db.connection, registry.ns
        self.nodes: set[NodeRef] = set()
        self.edges: dict[str, GraphEdge] = {}
        self.invalid = 0
        self._readable: dict[str, bool] = {}

    def readable(self, object_id: str) -> bool:
        if object_id not in self._readable:
            self._readable[object_id] = self.registry.access.eligible("READ", object_id)
        return self._readable[object_id]

    def admit(self, node: NodeRef) -> bool:
        if node in self.nodes:
            return True
        if not self.readable(node.id):
            return False
        require(len(self.nodes) < self.max_nodes, "GRAPH_BUDGET_EXCEEDED")
        self.nodes.add(node)
        return True

    def source_of(self, span_id: str) -> str | None:
        row = self.connection.execute(_SOURCE_OF_SPAN, (self.ns, span_id)).fetchone()
        return None if row is None else str(row[0])

    def support(self, span_id: str, revision: str) -> Support | None:
        owner = self.source_of(span_id)
        if owner is None or not self.readable(owner):
            return None
        return Support(span_id, owner, revision)

    def add(self, edge: GraphEdge) -> None:
        require(len(self.edges) < self.max_edges, "GRAPH_BUDGET_EXCEEDED")
        self.edges[edge.id] = edge

    def structural(
        self, relation: str, source: NodeRef, target: NodeRef, span: str, seq: int
    ) -> None:
        if source not in self.nodes or target not in self.nodes:
            return
        support = self.support(span, STRUCTURAL_REVISION)
        if support is None:
            return
        edge_id = stable_id("structural", self.ns, relation, source.id, target.id)
        self.add(
            GraphEdge(
                edge_id,
                relation,
                source,
                target,
                None,
                "ACTIVE",
                "*",
                (support,),
                None,
                None,
                STRUCTURAL_REVISION,
                seq,
            )
        )

    def build(self) -> Graph:
        seq, db, ns = self.snap.seq, self.connection, self.ns
        stored = self._stored_rows()
        events = db.execute(
            "SELECT e.id,v.source_id,e.commit_seq FROM events e JOIN source_versions v "
            "ON e.ns=v.ns AND e.source_version=v.id WHERE e.ns=? AND e.commit_seq<=? ORDER BY e.id",
            (ns, seq),
        ).fetchall()
        atoms = db.execute(
            "SELECT id,event_id,subject_ref,object_ref,source_span_id,commit_seq FROM atoms "
            "WHERE ns=? AND commit_seq<=? ORDER BY id",
            (ns, seq),
        ).fetchall()
        identities = db.execute(
            "SELECT left_id,right_id,span_id,recorded_seq FROM identity_events "
            "WHERE ns=? AND decision='SAME_AS' AND recorded_seq<=? ORDER BY id",
            (ns, seq),
        ).fetchall()
        for row in events:
            self.admit(NodeRef("event", row[0]))
            self.admit(NodeRef("source", row[1]))
        for atom_row in atoms:
            atom_id, event_id, subject, obj, span, atom_seq = tuple(atom_row)
            atom = NodeRef("atom", atom_id)
            if not self.admit(atom):
                continue
            self.admit(NodeRef("event", event_id))
            owner = self.source_of(span)
            if owner is not None:
                self.admit(NodeRef("source", owner))
            for entity in (subject, obj):
                if entity is not None:
                    self.admit(NodeRef("entity", entity))
        for left, right, _span, _seq in identities:
            self.admit(NodeRef("entity", left))
            self.admit(NodeRef("entity", right))
        for row in stored:
            for kind, object_id in (
                (row["from_kind"], row["from_id"]),
                (row["to_kind"], row["to_id"]),
            ):
                self.admit(NodeRef(kind, object_id))
        for atom_row in atoms:
            atom_id, event_id, subject, obj, span, atom_seq = tuple(atom_row)
            atom = NodeRef("atom", atom_id)
            if atom not in self.nodes:
                continue
            self.structural("PART_OF_EVENT", atom, NodeRef("event", event_id), span, atom_seq)
            owner = self.source_of(span)
            if owner is not None:
                self.structural("OBSERVED_IN", atom, NodeRef("source", owner), span, atom_seq)
            for entity in (subject, obj):
                if entity is not None:
                    self.structural("MENTIONS", atom, NodeRef("entity", entity), span, atom_seq)
        for left, right, span, recorded in identities:
            self.structural(
                "IDENTITY_LINK", NodeRef("entity", left), NodeRef("entity", right), span, recorded
            )
        for row in stored:
            self._stored(row)
        return self._finish()

    def _stored_rows(self) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM graph_edges WHERE ns=? AND commit_seq<=? AND status='ACTIVE' "
            "ORDER BY id",
            (self.ns, self.snap.seq),
        ).fetchall()
        at = self.snap.valid_at
        return [
            r
            for r in rows
            if at is None
            or (r["valid_from"] <= at and (r["valid_to"] is None or at < r["valid_to"]))
        ]

    def _stored(self, row: sqlite3.Row) -> None:
        """A stored edge needs its own eligibility (every support, both endpoints) and a valid
        direction; an eligible edge that breaks policy is counted, an ineligible one is absent."""
        source, target = (
            NodeRef(row["from_kind"], row["from_id"]),
            NodeRef(row["to_kind"], row["to_id"]),
        )
        if not self.readable(row["id"]) or source not in self.nodes or target not in self.nodes:
            return
        spans = [row["source_span_id"]] + [
            str(r[0])
            for r in self.connection.execute(
                "SELECT span_id FROM graph_edge_support WHERE ns=? AND edge_id=? ORDER BY span_id",
                (self.ns, row["id"]),
            )
        ]
        revisions = {
            str(r[0]): str(r[1])
            for r in self.connection.execute(
                "SELECT span_id,revision FROM graph_edge_support WHERE ns=? AND edge_id=?",
                (self.ns, row["id"]),
            )
        }
        supports: list[Support] = []
        for span in dict.fromkeys(spans):
            found = self.support(span, revisions.get(span, row["producer_revision"]))
            if found is None:
                return  # an unreadable or dangling support makes the edge absent
            supports.append(found)
        relation = RELATIONS.get(row["relation_type"])
        if relation is None or not relation.allows(source.kind, target.kind) or not supports:
            self.invalid += 1
            return
        self.add(
            GraphEdge(
                row["id"],
                relation.name,
                source,
                target,
                row["epistemic"],
                row["status"],
                row["scope"],
                tuple(sorted(supports, key=lambda s: s.span_id)),
                row["valid_from"],
                row["valid_to"],
                row["producer_revision"],
                row["commit_seq"],
            )
        )

    def _finish(self) -> Graph:
        edges = tuple(sorted(self.edges.values(), key=lambda e: e.id))
        arcs: dict[NodeRef, list[Arc]] = {n: [] for n in self.nodes}
        for edge in edges:
            relation = RELATIONS[edge.relation]
            if not relation.traversable:
                continue
            arcs[edge.source].append(Arc(edge.target, edge.id, edge.relation, True))
            arcs[edge.target].append(Arc(edge.source, edge.id, edge.relation, relation.symmetric))
        return Graph(
            self.snap,
            tuple(sorted(self.nodes)),
            edges,
            {n: tuple(sorted(a)) for n, a in arcs.items()},
            self.invalid,
            {e.id: e for e in edges},
        )
