"""P06-T01: the typed graph is rebuilt deterministically from the registry and only for what the
principal may read; similarity, bad provenance and bad directions never create or keep an edge."""

import ast
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import HOST, request
from test_object_acl import LABEL, READER, fixed_clock, reader_of, source_of

from norn.canonical.identity import review_identity
from norn.contracts.errors import NornError
from norn.governance.access import HostIdentity
from norn.graph import adjacency
from norn.graph.adjacency import build_graph, write_edge
from norn.graph.contracts import RELATIONS, EdgeSpec, GraphSnapshot, NodeRef
from norn.integration.engine import Engine

REVISION = "test-graph-v1"
FROM = "2026-01-01T00:00:00Z"


def span_of(engine, atom_id: str) -> str:
    return str(engine.registry.source_for_atom(atom_id)["id"])


def subject_of(engine, atom_id: str) -> str:
    return str(
        engine.db.connection.execute(
            "SELECT subject_ref FROM atoms WHERE id=?", (atom_id,)
        ).fetchone()[0]
    )


def spec(source: NodeRef, target: NodeRef, spans, relation="REQUIRES", **overrides) -> EdgeSpec:
    base = EdgeSpec(
        relation, source, target, "DOCUMENT_ASSERTION", "*", tuple(spans), FROM, REVISION
    )
    return replace(base, **overrides)


def world(engine, *places: str):
    """One event per place; returns receipts in order."""
    return [engine.write(request(f"occ-{i}", place=p)) for i, p in enumerate(places)]


def chain(engine):
    """Three entities A, B, C from three atoms; REQUIRES A->B and B->C stored with support."""
    receipts = world(engine, "ZoneA", "ZoneB", "ZoneC")
    atoms = [r["atom_ids"][0] for r in receipts]
    entities = [NodeRef("entity", subject_of(engine, a)) for a in atoms]
    spans = [span_of(engine, a) for a in atoms]
    first = write_edge(engine.registry, spec(entities[0], entities[1], [spans[0]]))
    second = write_edge(engine.registry, spec(entities[1], entities[2], [spans[1]]))
    return receipts, atoms, entities, spans, (first, second)


def reach(graph, start: NodeRef, relations=None, *, reverse=False) -> list[NodeRef]:
    seen, frontier = [start], [start]
    while frontier:
        node = frontier.pop(0)
        for arc in graph.neighbors(node, relations, reverse=reverse):
            if arc.neighbor not in seen:
                seen.append(arc.neighbor)
                frontier.append(arc.neighbor)
    return seen


def test_the_event_atom_entity_source_graph_reloads_deterministically(tmp_path):
    root = tmp_path / "store"
    with Engine(root, HOST, create=True, clock=fixed_clock) as engine:
        engine.access.bootstrap()
        receipts, atoms, entities, spans, edges = chain(engine)
        graph = build_graph(engine.registry)
        digest = graph.digest()
        assert build_graph(engine.registry).digest() == digest  # same state, same bytes
        kinds = [n.kind for n in graph.nodes]
        assert (kinds.count("event"), kinds.count("atom"), kinds.count("entity")) == (3, 3, 3)
        assert kinds.count("source") == 3
        structural = {(e.relation) for e in graph.edges if not e.stored}
        assert structural == {"PART_OF_EVENT", "OBSERVED_IN", "MENTIONS"}
        for atom_id, receipt in zip(atoms, receipts, strict=True):
            atom = NodeRef("atom", atom_id)
            found = {(a.relation, a.neighbor) for a in graph.neighbors(atom)}
            assert ("PART_OF_EVENT", NodeRef("event", receipt["event_id"])) in found
            assert ("MENTIONS", NodeRef("entity", subject_of(engine, atom_id))) in found
        stored = [e for e in graph.edges if e.stored]
        assert {e.id for e in stored} == set(edges)
        assert all(s.source_id for e in stored for s in e.supports)
    with Engine(root, HOST, clock=fixed_clock) as reopened:  # restart: rebuilt from the registry
        again = build_graph(reopened.registry)
        assert again.digest() == digest
        assert again.nodes == graph.nodes and again.edges == graph.edges
        assert again.arcs == graph.arcs


def test_a_stored_edge_is_idempotent_and_carries_independent_support(engine):
    _r, atoms, entities, spans, (first, _second) = chain(engine)
    before = engine.db.connection.execute("SELECT count(*) FROM outbox").fetchone()[0]
    replay = spec(entities[0], entities[1], [spans[0]])
    assert write_edge(engine.registry, replay) == first  # same request, same edge
    assert engine.db.connection.execute("SELECT count(*) FROM outbox").fetchone()[0] == before
    # A second, independent support makes a different edge with both supports and its own revision.
    both = spec(entities[0], entities[1], [spans[2], spans[0]], producer_revision="other-rev")
    other = write_edge(engine.registry, both)
    assert other != first
    edge = build_graph(engine.registry).edge(other)
    assert edge is not None and {s.span_id for s in edge.supports} == {spans[0], spans[2]}
    assert {s.revision for s in edge.supports} == {"other-rev"}
    assert edge.epistemic == "DOCUMENT_ASSERTION" and edge.scope == "*"
    assert (edge.valid_from, edge.valid_to) == (FROM, None)


def test_name_similarity_never_merges_and_only_a_reviewed_identity_links(engine):
    receipts = world(engine, "ZoneA", "ZoneB", "ZoneC")  # three atoms, one subject name "Alex"
    atoms = [r["atom_ids"][0] for r in receipts]
    entities = [NodeRef("entity", subject_of(engine, a)) for a in atoms]
    assert len({e.id for e in entities}) == 3  # equal names stay distinct provisional entities
    graph = build_graph(engine.registry)
    assert all(e.relation != "IDENTITY_LINK" for e in graph.edges)
    assert entities[1] not in reach(graph, entities[0])
    # DIFFERENT never creates a link; SAME_AS with a supporting atom does, in both directions.
    review_identity(engine.registry, entities[0].id, entities[2].id, "DIFFERENT", atoms[0])
    assert all(e.relation != "IDENTITY_LINK" for e in build_graph(engine.registry).edges)
    review_identity(engine.registry, entities[0].id, entities[1].id, "SAME_AS", atoms[0])
    linked = build_graph(engine.registry)
    link = next(e for e in linked.edges if e.relation == "IDENTITY_LINK")
    assert {link.source, link.target} == {entities[0], entities[1]}
    assert entities[1] in reach(linked, entities[0]) and entities[0] in reach(linked, entities[1])
    assert entities[2] not in reach(linked, entities[0])


def test_direction_is_policy_and_non_traversable_relations_have_no_arcs(engine):
    _r, atoms, entities, spans, _e = chain(engine)
    graph = build_graph(engine.registry)
    a, b, c = entities
    assert reach(graph, a, frozenset({"REQUIRES"})) == [a, b, c]  # forward only
    assert reach(graph, c, frozenset({"REQUIRES"})) == [c]  # a directed edge is not symmetric
    assert reach(graph, c, frozenset({"REQUIRES"}), reverse=True) == [c, b, a]
    assert graph.neighbors(NodeRef("entity", "entity_unknown")) == ()  # unknown node, no arcs
    # CONTRADICTS and SUPERSEDES are stored for explanation but never traversed.
    atom_nodes = [NodeRef("atom", x) for x in atoms]
    contradiction = write_edge(
        engine.registry, spec(atom_nodes[0], atom_nodes[1], [spans[0]], relation="CONTRADICTS")
    )
    superseded = write_edge(
        engine.registry, spec(atom_nodes[1], atom_nodes[2], [spans[1]], relation="SUPERSEDES")
    )
    more = build_graph(engine.registry)
    assert more.edge(contradiction) is not None and more.edge(superseded) is not None
    assert not RELATIONS["CONTRADICTS"].traversable and not RELATIONS["SUPERSEDES"].traversable
    assert all(
        arc.edge_id not in (contradiction, superseded)
        for node in more.nodes
        for arc in more.neighbors(node, reverse=True)
    )


def test_missing_provenance_bad_direction_and_unsupported_edges_cannot_be_written(engine):
    _r, atoms, entities, spans, _e = chain(engine)
    atom = NodeRef("atom", atoms[0])
    event = NodeRef("event", engine.db.connection.execute("SELECT id FROM events").fetchone()[0])
    cases = {
        "no support": (spec(entities[0], entities[1], []), "MISSING_PROVENANCE"),
        "duplicate support": (
            spec(entities[0], entities[1], [spans[0], spans[0]]),
            "DUPLICATE_SUPPORT",
        ),
        "unknown relation": (
            spec(entities[0], entities[1], [spans[0]], relation="FRIENDS_WITH"),
            "UNSUPPORTED_RELATION",
        ),
        "entity part of event": (
            spec(entities[0], event, [spans[0]], relation="PART_OF_EVENT"),
            "UNSUPPORTED_DIRECTION",
        ),
        "event part of atom": (
            spec(event, atom, [spans[0]], relation="PART_OF_EVENT"),
            "UNSUPPORTED_DIRECTION",
        ),
        "self edge": (spec(entities[0], entities[0], [spans[0]]), "SELF_EDGE"),
        "hypothesis as observation": (
            spec(atom, NodeRef("atom", atoms[1]), [spans[0]], relation="HYPOTHESIZES_CAUSE"),
            "HYPOTHESIS_NOT_CAUSE",
        ),
        "verified cause from a hypothesis": (
            spec(
                atom,
                NodeRef("atom", atoms[1]),
                [spans[0]],
                relation="VERIFIED_CAUSE",
                epistemic="HYPOTHESIS",
            ),
            "CAUSE_NEEDS_SUPPORTED_ORIGIN",
        ),
        "validity reversed": (
            spec(entities[0], entities[1], [spans[0]], valid_to="2025-01-01T00:00:00Z"),
            "INVALID_VALIDITY",
        ),
        "validity without zone": (
            spec(entities[0], entities[1], [spans[0]], valid_from="2026-01-01T00:00:00"),
            "INVALID_VALIDITY",
        ),
        "support span that does not exist": (
            spec(entities[0], entities[1], ["span_missing"]),
            "NOT_AUTHORIZED_OR_NOT_FOUND",
        ),
        "endpoint of the wrong kind": (
            spec(
                NodeRef("atom", entities[0].id),
                entities[1],
                [spans[0]],
                relation="RELATED_TO",
            ),
            "NOT_AUTHORIZED_OR_NOT_FOUND",
        ),
        "endpoint that does not exist": (
            spec(entities[0], NodeRef("entity", "entity_nope"), [spans[0]]),
            "NOT_AUTHORIZED_OR_NOT_FOUND",
        ),
    }
    count = engine.db.connection.execute("SELECT count(*) FROM graph_edges").fetchone()[0]
    for name, (bad, code) in cases.items():
        with pytest.raises(NornError, match=code):
            write_edge(engine.registry, bad)
        assert name  # label for the failure report
    assert engine.db.connection.execute("SELECT count(*) FROM graph_edges").fetchone()[0] == count
    # Positive control: the same helper accepts the good form of each rejected request.
    assert write_edge(engine.registry, spec(atom, NodeRef("atom", atoms[1]), [spans[0]]))
    assert write_edge(
        engine.registry,
        spec(
            atom,
            NodeRef("atom", atoms[1]),
            [spans[0]],
            relation="HYPOTHESIZES_CAUSE",
            epistemic="HYPOTHESIS",
        ),
    )


def inject(connection: sqlite3.Connection, ns: str, edge_id: str, **values) -> None:
    """Bypass the writer (as a corrupted or foreign producer would) to test the reader."""
    row = {
        "from_id": "",
        "from_kind": "entity",
        "to_id": "",
        "to_kind": "entity",
        "relation_type": "REQUIRES",
        "status": "ACTIVE",
        "valid_from": FROM,
        "valid_to": None,
        "commit_seq": 1,
        "span": "",
    } | values
    connection.execute("INSERT OR IGNORE INTO objects VALUES(?,?,'graph_edge')", (ns, edge_id))
    connection.execute(
        "INSERT INTO graph_edges(ns,id,from_id,from_kind,to_id,to_kind,relation_type,epistemic,"
        "status,scope,source_span_id,valid_from,valid_to,producer_revision,commit_seq) "
        "VALUES(?,?,?,?,?,?,?,'DOCUMENT_ASSERTION',?,'*',?,?,?,'raw',?)",
        (
            ns,
            edge_id,
            row["from_id"],
            row["from_kind"],
            row["to_id"],
            row["to_kind"],
            row["relation_type"],
            row["status"],
            row["span"],
            row["valid_from"],
            row["valid_to"],
            row["commit_seq"],
        ),
    )


def test_the_reader_drops_what_the_writer_would_have_refused(engine):
    _r, atoms, entities, spans, (first, _second) = chain(engine)
    c = engine.db.connection
    common = {"from_id": entities[0].id, "to_id": entities[2].id, "span": spans[0]}
    ns = engine.access.ns
    inject(c, ns, "edge_bad_direction", relation_type="PART_OF_EVENT", **common)
    inject(c, ns, "edge_retracted", status="RETRACTED", **common)
    inject(c, ns, "edge_unresolved", status="UNRESOLVED", **common)
    inject(c, ns, "edge_expired", valid_to="2026-02-01T00:00:00Z", **common)
    graph = build_graph(engine.registry)
    assert graph.invalid_edges == 1  # only the readable edge that breaks the direction policy
    present = {e.id for e in graph.edges}
    assert first in present  # positive control: a well formed stored edge survives
    assert not present & {"edge_bad_direction", "edge_retracted", "edge_unresolved"}
    assert "edge_expired" in present  # no valid-time basis was requested, so it is not filtered
    at = build_graph(engine.registry, GraphSnapshot(engine_seq(engine), "2026-06-01T00:00:00Z"))
    assert "edge_expired" not in {e.id for e in at.edges} and first in {e.id for e in at.edges}
    early = build_graph(engine.registry, GraphSnapshot(engine_seq(engine), "2025-06-01T00:00:00Z"))
    assert not [e for e in early.edges if e.stored]  # nothing is valid before the validity start


def engine_seq(engine) -> int:
    return int(
        engine.db.connection.execute(
            "SELECT commit_seq FROM namespaces WHERE ns=?", (engine.access.ns,)
        ).fetchone()[0]
    )


def test_the_snapshot_basis_decides_which_atoms_and_edges_exist(engine):
    first_receipt = engine.write(request("first", place="ZoneA"))
    cut = engine_seq(engine)
    second_receipt = engine.write(request("second", place="ZoneB"))
    old = build_graph(engine.registry, GraphSnapshot(cut))
    new = build_graph(engine.registry)
    assert NodeRef("atom", first_receipt["atom_ids"][0]) in old.nodes
    assert NodeRef("atom", second_receipt["atom_ids"][0]) not in old.nodes
    assert NodeRef("atom", second_receipt["atom_ids"][0]) in new.nodes
    assert old.digest() != new.digest()
    assert build_graph(engine.registry, GraphSnapshot(cut)).digest() == old.digest()
    assert old.snapshot == GraphSnapshot(cut) and new.snapshot.seq == engine_seq(engine)


def private_world(engine, *, with_private: bool, private_first: bool = False):
    """Public chain plus (optionally) a private source whose label the reader is denied."""
    private = None
    if with_private and private_first:
        private = engine.write(request("private", place="ZoneP"))
    receipts, atoms, entities, spans, edges = chain(engine)
    if with_private and not private_first:
        private = engine.write(request("private", place="ZoneP"))
    engine.access.grant(READER, "READ")
    if private is not None:
        engine.access.set_scope(source_of(engine, private["event_id"]), LABEL)
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
    return private, entities, spans


def test_an_unreadable_object_is_absent_and_adding_one_changes_no_byte_the_reader_sees(tmp_path):
    digests, shapes = [], []
    for index, (with_private, first) in enumerate(((False, False), (True, False), (True, True))):
        with Engine(tmp_path / f"w{index}", HOST, create=True, clock=fixed_clock) as engine:
            engine.access.bootstrap()
            private, entities, spans = private_world(
                engine, with_private=with_private, private_first=first
            )
            with reader_of(engine) as reader:
                graph = build_graph(reader.registry)
                digests.append(graph.digest())
                shapes.append((len(graph.nodes), len(graph.edges)))
                assert len(graph.edges) >= 9  # the public chain is visible: positive control
                if private is not None:
                    hidden = {private["event_id"], *private["atom_ids"]}
                    assert not hidden & {n.id for n in graph.nodes}
                    assert source_of(engine, private["event_id"]) not in {n.id for n in graph.nodes}
    assert digests[0] == digests[1] == digests[2]  # also when the private write came first
    assert shapes[0] == shapes[1] == shapes[2]


def test_a_denied_endpoint_or_support_removes_the_edge_but_the_readable_graph_stays(engine):
    receipts, atoms, entities, spans, (first, second) = chain(engine)
    secret = engine.write(request("secret", place="ZoneS"))
    secret_atom = NodeRef("atom", secret["atom_ids"][0])
    secret_span = span_of(engine, secret["atom_ids"][0])
    to_secret = write_edge(
        engine.registry, spec(entities[0], secret_atom, [spans[0]], relation="RELATED_TO")
    )
    mixed = write_edge(engine.registry, spec(entities[0], entities[2], [spans[0], secret_span]))
    engine.access.grant(READER, "READ")
    with reader_of(engine) as reader:
        before = build_graph(reader.registry)
        assert {to_secret, mixed, first} <= {e.id for e in before.edges}  # positive control
        engine.access.set_scope(source_of(engine, secret["event_id"]), LABEL)
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
        after = build_graph(reader.registry)
    ids = {e.id for e in after.edges}
    assert first in ids and second in ids  # unrelated edges stay
    assert to_secret not in ids  # the endpoint is unreadable
    assert mixed not in ids  # one of its supports is unreadable (every support must be readable)
    assert secret_atom not in after.nodes


def test_a_tombstoned_source_removes_its_atoms_and_the_edges_it_supports(engine):
    receipts, atoms, entities, spans, (first, second) = chain(engine)
    owner = engine.registry.source_for_atom(atoms[0])["source_id"]
    assert first in {e.id for e in build_graph(engine.registry).edges}
    engine.deny(owner, "erase-graph-1", "synthetic-expiry")
    after = build_graph(engine.registry)
    ids = {e.id for e in after.edges}
    assert first not in ids and second in ids
    assert NodeRef("atom", atoms[0]) not in after.nodes
    assert NodeRef("source", owner) not in after.nodes


def test_budgets_and_policy_drift_fail_visibly_instead_of_truncating(engine, monkeypatch):
    chain(engine)
    with pytest.raises(NornError, match="GRAPH_BUDGET_EXCEEDED"):
        build_graph(engine.registry, max_nodes=3)
    with pytest.raises(NornError, match="GRAPH_BUDGET_EXCEEDED"):
        build_graph(engine.registry, max_edges=2)
    with pytest.raises(NornError, match="INVALID_GRAPH_BUDGET"):
        build_graph(engine.registry, max_nodes=0)
    assert build_graph(engine.registry, max_nodes=1000, max_edges=1000).nodes  # control
    # The stored policy rows must equal the in-code policy; a drift is refused, not tolerated.
    drifted = replace(RELATIONS["REQUIRES"], traversable=False)
    monkeypatch.setitem(adjacency.RELATIONS, "REQUIRES", drifted)
    with pytest.raises(NornError, match="GRAPH_POLICY_MISMATCH"):
        build_graph(engine.registry)
    monkeypatch.undo()
    assert build_graph(engine.registry).nodes


def test_a_principal_without_a_read_grant_gets_no_graph_and_the_same_error_as_absent(engine):
    chain(engine)
    stranger = Engine(engine.root, HostIdentity(engine.access.host.namespace, "nobody"))
    with stranger, pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        build_graph(stranger.registry)


def test_the_graph_package_uses_no_similarity_model_or_network_code():
    root = Path(adjacency.__file__).parent
    imported = set()
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
    forbidden = (
        "norn.embedding",
        "norn.retrieval",
        "norn.projection",
        "socket",
        "urllib",
        "random",
    )
    assert not [m for m in imported if m.startswith(forbidden)], imported
    assert {"norn.canonical.registry", "norn.graph.contracts"} <= imported  # control: parsed


def test_erasure_reaches_graph_edges_and_a_tombstoned_edge_alone_is_absent(engine):
    _r, atoms, entities, spans, (first, second) = chain(engine)
    extra = write_edge(
        engine.registry, spec(entities[0], entities[2], [spans[2], spans[1]], relation="RELATED_TO")
    )
    # An edge can be denied on its own; its endpoints and supports stay readable and stay nodes.
    engine.deny(first, "erase-edge-1", "synthetic-expiry")
    graph = build_graph(engine.registry)
    assert first not in {e.id for e in graph.edges} and second in {e.id for e in graph.edges}
    assert set(entities) <= set(graph.nodes)
    # Denying a source erases every edge that cites it as one of its supports, not only atoms.
    owner = engine.registry.source_for_atom(atoms[1])["source_id"]
    result = engine.deny(owner, "erase-source-1", "synthetic-expiry")
    selectors = {o["selector"] for o in result["obligations"] if o["artifact"] == "canonical_sql"}
    assert {second, extra} <= selectors  # the support source of both edges was erased
    tombstoned = {
        r[0] for r in engine.db.connection.execute("SELECT object_id FROM tombstones").fetchall()
    }
    assert {first, second, extra} <= tombstoned
    after = build_graph(engine.registry)
    assert not {first, second, extra} & {e.id for e in after.edges}
