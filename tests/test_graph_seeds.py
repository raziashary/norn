"""P06-T03: one eligible, source-grounded, sum-one seed per query, identical for every graph reader.

Pure construction is proven with hand-computed masses on constructed sources; the exact and BM25
channels on real public-v2 pilot cases (no model); the dense channel only when the pinned local
models are present. ACL, tombstone, snapshot and knowledge-time controls use the same stores the
T01 and T16 tests use.
"""

import ast
import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import HOST, REPO, clock
from test_multihop_fixtures import first
from test_object_acl import LABEL, READER, fixed_clock, reader_of, source_of
from test_relation_extraction import built

from benchmark.adapters.baseline import host, interpret, load_sources
from benchmark.adapters.common import replay_clock
from benchmark.fixtures.publication import publish
from norn.contracts.errors import NornError
from norn.contracts.time import stamp
from norn.embedding.assets import fingerprint
from norn.extraction import relations
from norn.extraction.relations import TRACK_TEXT, extract_relations
from norn.graph import seeds as seeds_module
from norn.graph.adjacency import build_graph
from norn.graph.contracts import NodeRef
from norn.graph.seeds import (
    CONVENTIONAL,
    DENSE_ONLY,
    EMPTY_SEED,
    EXACT_DEGRADED,
    RRF_K,
    SEED_REVISION,
    ChannelResult,
    SeedBasis,
    Vote,
    anchor_entity,
    construct_seed,
)
from norn.integration.engine import Engine
from norn.retrieval import seed_channels
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.seed_channels import build_seed

MARKER = "__GOLD_CANARY__"
LATE = stamp(datetime(2030, 1, 1, tzinfo=UTC))
MODEL_ROOT = REPO / ".norn" / "models"


def entity_of(engine, atom_id: str) -> str:
    return anchor_entity(engine.registry, atom_id)


def basis_of(engine) -> SeedBasis:
    seq = int(
        engine.db.connection.execute(
            "SELECT commit_seq FROM namespaces WHERE ns=?", (engine.access.ns,)
        ).fetchone()[0]
    )
    return SeedBasis(seq, LATE, engine.access.check("READ"))


def three(engine):
    """Three keyed sources A, B, C: entity ids, atom ids and receipts."""
    receipts = built(
        engine,
        [
            (
                "a",
                "Svc-aaa",
                "Svc-aaa is registered and active. [key:svc.aaaaaaaa]",
                "svc.aaaaaaaa",
            ),
            (
                "b",
                "Svc-bbb",
                "Svc-bbb is registered and active. [key:svc.bbbbbbbb]",
                "svc.bbbbbbbb",
            ),
            (
                "c",
                "Svc-ccc",
                "Svc-ccc is registered and active. [key:svc.cccccccc]",
                "svc.cccccccc",
            ),
        ],
    )
    atoms = {k: v["atom_ids"][0] for k, v in receipts.items()}
    return atoms, {k: entity_of(engine, a) for k, a in atoms.items()}


# --- construction: hand-computed masses and the rules of the vector ----------------------------


def test_masses_are_reciprocal_rank_votes_normalised_to_one_with_one_vote_per_entity(engine):
    atoms, ent = three(engine)
    channels = [
        ChannelResult("exact", "x-1", (Vote(ent["c"]), Vote(ent["a"], (atoms["a"],)))),
        ChannelResult(
            "lexical",
            "l-1",
            (Vote(ent["a"], (atoms["a"],)), Vote(ent["b"], (atoms["b"],)), Vote(ent["a"])),
        ),
        ChannelResult("dense", "d-1", (Vote(ent["b"]), Vote(ent["a"]))),
    ]
    seed = construct_seed(engine.registry, channels, basis_of(engine))
    # exact votes at rank 1 whatever their order; the repeated lexical entity counts once, at its
    # best rank, and does not push B down to rank 3.
    raw = {
        ent["a"]: 1 / (RRF_K + 1) + 1 / (RRF_K + 1) + 1 / (RRF_K + 2),
        ent["b"]: 1 / (RRF_K + 2) + 1 / (RRF_K + 1),
        ent["c"]: 1 / (RRF_K + 1),
    }
    total = sum(raw.values())
    assert seed.vector() == pytest.approx({e: m / total for e, m in raw.items()}, abs=1e-15)
    assert sum(seed.vector().values()) == pytest.approx(1.0, abs=1e-12)
    assert all(w > 0 for w in seed.vector().values())
    anchor = {a.entity_id: a for a in seed.anchors}
    assert anchor[ent["a"]].channels == ("dense", "exact", "lexical")
    assert anchor[ent["a"]].atom_ids == (atoms["a"],) and anchor[ent["c"]].atom_ids == ()
    assert seed.channels == (("dense", "d-1", 2), ("exact", "x-1", 2), ("lexical", "l-1", 2))
    assert seed.revision == SEED_REVISION and seed.flags == () and seed.reasons == ()
    # Reordering the channels or votes inside the exact channel changes no byte.
    again = construct_seed(
        engine.registry,
        [
            channels[2],
            ChannelResult("exact", "x-1", (Vote(ent["a"], (atoms["a"],)), Vote(ent["c"]))),
            channels[1],
        ],
        basis_of(engine),
    )
    assert again.digest() == seed.digest()
    # Positive control: a different channel version is a different recorded seed.
    other = construct_seed(
        engine.registry, [replace(channels[0], version="x-2"), *channels[1:]], basis_of(engine)
    )
    assert other.digest() != seed.digest() and other.vector() == seed.vector()


def test_a_binding_channel_is_accepted_with_its_version_and_unknown_or_repeated_ones_are_not(
    engine,
):
    atoms, ent = three(engine)
    basis = basis_of(engine)
    binding = ChannelResult("binding", "b4-test-v1", (Vote(ent["b"], (atoms["b"],)),))
    seed = construct_seed(engine.registry, [binding], basis)
    assert seed.channels == (("binding", "b4-test-v1", 1),) and seed.vector() == {ent["b"]: 1.0}
    for bad, code in (
        ([ChannelResult("magic", "v", (Vote(ent["a"]),))], "SEED_UNKNOWN_CHANNEL"),
        ([binding, binding], "SEED_DUPLICATE_CHANNEL"),
        ([], "SEED_NO_CHANNELS"),
    ):
        with pytest.raises(NornError, match=code):
            construct_seed(engine.registry, bad, basis)
    wide = ChannelResult("lexical", "v", tuple(Vote(ent["a"]) for _ in range(1001)))
    with pytest.raises(NornError, match="SEED_CHANNEL_BUDGET"):
        construct_seed(engine.registry, [wide], basis)


def test_empty_channels_are_explicit_and_an_empty_exact_channel_is_reported_degraded(engine):
    atoms, ent = three(engine)
    basis = basis_of(engine)
    seed = construct_seed(
        engine.registry,
        [
            ChannelResult("exact", "x-1", (), "NO_EXACT_CUE"),
            ChannelResult("lexical", "l-1", (Vote(ent["b"], (atoms["b"],)),)),
            ChannelResult("dense", "d-1", (), "NO_MATCH"),
        ],
        basis,
    )
    assert seed.flags == (EXACT_DEGRADED,)  # the other empty channel is not an exact failure
    assert seed.reasons == (("dense", "NO_MATCH"), ("exact", "NO_EXACT_CUE"))
    assert seed.vector() == {ent["b"]: 1.0}  # the surviving channel still seeds
    nothing = construct_seed(
        engine.registry, [ChannelResult("exact", "x-1", (), "NO_MATCH")], basis
    )
    assert nothing.anchors == () and nothing.vector() == {}
    assert nothing.flags == (EMPTY_SEED, EXACT_DEGRADED)
    # Control: a populated exact channel is not degraded.
    ok = construct_seed(engine.registry, [ChannelResult("exact", "x-1", (Vote(ent["a"]),))], basis)
    assert EXACT_DEGRADED not in ok.flags and EMPTY_SEED not in ok.flags


def test_zero_or_nonfinite_mass_and_wrong_basis_cannot_seed(engine, monkeypatch):
    atoms, ent = three(engine)
    basis = basis_of(engine)
    votes = [ChannelResult("lexical", "l-1", (Vote(ent["a"]),))]
    assert construct_seed(engine.registry, votes, basis).vector() == {ent["a"]: 1.0}
    for bad in (math.inf, math.nan):
        monkeypatch.setattr(seeds_module, "RRF_K", bad)
        with pytest.raises(NornError, match="SEED_MASS_INVALID"):
            construct_seed(engine.registry, votes, basis)
    monkeypatch.undo()
    with pytest.raises(NornError, match="SEED_BASIS_INVALID"):
        construct_seed(engine.registry, votes, replace(basis, snapshot=-1))


# --- eligibility: denied, absent, foreign and stale anchors never seed -------------------------


def test_an_anchor_that_is_unknown_foreign_denied_or_stale_is_an_error_not_mass(tmp_path):
    with Engine(tmp_path / "w", HOST, create=True, clock=fixed_clock) as engine:
        engine.access.bootstrap()
        atoms, ent = three(engine)
        before = basis_of(engine)
        late = built(
            engine,
            [
                (
                    "d",
                    "Svc-ddd",
                    "Svc-ddd is registered and active. [key:svc.dddddddd]",
                    "svc.dddddddd",
                )
            ],
        )
        late_atom = late["d"]["atom_ids"][0]
        late_entity = entity_of(engine, late_atom)
        now = basis_of(engine)
        assert construct_seed(
            engine.registry, [ChannelResult("exact", "x", (Vote(late_entity),))], now
        )
        errors = {}
        for name, votes, basis in (
            ("unknown", (Vote("entity_" + "0" * 64),), now),
            ("not an id", (Vote("not an id!"),), now),
            ("after snapshot", (Vote(late_entity),), before),
            (
                "recorded after knowledge",
                (Vote(ent["a"]),),
                replace(now, knowledge_at="2000-01-01T00:00:00Z"),
            ),
            ("atom of another entity", (Vote(ent["a"], (atoms["b"],)),), now),
            ("atom after snapshot", (Vote(ent["a"], (late_atom,)),), before),
        ):
            with pytest.raises(NornError) as error:
                construct_seed(engine.registry, [ChannelResult("lexical", "l", votes)], basis)
            errors[name] = error.value.code
        assert errors["unknown"] == errors["not an id"] or errors["not an id"] == "INVALID_LABEL"
        assert errors["unknown"] == "SEED_ANCHOR_NOT_ELIGIBLE"
        assert errors["after snapshot"] == errors["recorded after knowledge"] == "SEED_ANCHOR_STALE"
        assert (
            errors["atom of another entity"] == errors["atom after snapshot"] == "SEED_ANCHOR_STALE"
        )
        # A denied entity gives exactly the error an unknown id gives.
        engine.access.grant(READER, "READ")
        engine.access.set_scope(source_of(engine, late["d"]["event_id"]), LABEL)
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
        with reader_of(engine) as reader:
            reader_basis = SeedBasis(now.snapshot, LATE, reader.access.check("READ"))
            with pytest.raises(NornError) as denied:
                construct_seed(
                    reader.registry,
                    [ChannelResult("exact", "x", (Vote(late_entity),))],
                    reader_basis,
                )
            assert denied.value.code == errors["unknown"]
            assert construct_seed(
                reader.registry, [ChannelResult("exact", "x", (Vote(ent["a"]),))], reader_basis
            ).vector() == {ent["a"]: 1.0}  # positive control: a readable anchor still seeds
        # An erased source leaves no anchor either.
        engine.deny(source_of(engine, late["d"]["event_id"]), "erase-seed-1", "synthetic-expiry")
        with pytest.raises(NornError, match="SEED_ANCHOR_NOT_ELIGIBLE"):
            construct_seed(
                engine.registry,
                [ChannelResult("exact", "x", (Vote(late_entity),))],
                basis_of(engine),
            )


def test_a_security_change_during_construction_is_not_served(engine):
    atoms, ent = three(engine)
    basis = basis_of(engine)
    engine.access.grant(READER, "READ")  # any security change bumps the epoch
    with pytest.raises(NornError, match="QUERY_SECURITY_CHANGED"):
        construct_seed(engine.registry, [ChannelResult("exact", "x", (Vote(ent["a"]),))], basis)


# --- the channels over real pilot cases (no model) ---------------------------------------------


def loaded(tmp_path, template, name="case", **engine_options):
    published = publish(template.case, (MARKER,))
    clk = replay_clock(published)
    engine = Engine(tmp_path / name, host(published), create=True, clock=clk, **engine_options)
    engine.access.bootstrap()
    load_sources(engine, published, clk)
    return engine, published


def key_of(template, hidden: str) -> str:
    return next(k for h, _n, k in template.graph.nodes if h == hidden)


def entity_with_key(engine, key: str) -> str:
    return str(
        engine.db.connection.execute(
            "SELECT id FROM entities WHERE external_key=?", (key,)
        ).fetchone()[0]
    )


def test_a_registered_key_in_the_query_seeds_exactly_and_outweighs_a_same_name_entity(tmp_path):
    template = first("M5")
    engine, published = loaded(tmp_path, template)
    with engine:
        key = key_of(template, template.graph.seed_node)
        assert f"key {key}" in published.query.text
        request = interpret(published, "R0")
        seed = build_seed(engine, request, ("exact", "lexical"))
        keyed = entity_with_key(engine, key)
        vector = seed.vector()
        assert keyed in vector and sum(vector.values()) == pytest.approx(1.0, abs=1e-12)
        anchor = next(a for a in seed.anchors if a.entity_id == keyed)
        assert anchor.channels == ("exact", "lexical")
        name = published.query.text.split(" (key")[0].split()[-1]
        same_name = [
            str(r[0])
            for r in engine.db.connection.execute(
                "SELECT x.entity_id FROM entity_aliases x JOIN entities e ON e.id=x.entity_id "
                "WHERE x.label=? AND e.external_key IS NOT NULL AND e.id<>?",
                (name, keyed),
            )
        ]
        assert same_name and all(e in vector and 0 < vector[e] < vector[keyed] for e in same_name)
        assert EXACT_DEGRADED not in seed.flags and seed.channels[0][:2] == (
            "exact",
            seed_channels.EXACT_VERSION,
        )
        # Exact only: the key's entity carries all the mass.
        assert build_seed(engine, request, ("exact",)).vector() == {keyed: 1.0}
        # The ambiguous variant names no key: exact is empty and reported, lexical still seeds.
        weak = replace(request, text=request.text.split(" (key")[0] + "?")
        degraded = build_seed(engine, weak, ("exact", "lexical"))
        assert EXACT_DEGRADED in degraded.flags
        assert ("exact", "NO_EXACT_CUE") in degraded.reasons
        assert keyed in degraded.vector() and all(w > 0 for w in degraded.vector().values())


def test_a_chain_query_has_no_exact_cue_and_the_seed_comes_from_the_ranked_channel(tmp_path):
    template = first("M1")
    engine, published = loaded(tmp_path, template)
    with engine:
        seed = build_seed(engine, interpret(published, "R0"), ("exact", "lexical"))
        assert seed.flags == (EXACT_DEGRADED,) and seed.reasons == (("exact", "NO_EXACT_CUE"),)
        assert seed.anchors and sum(seed.vector().values()) == pytest.approx(1.0, abs=1e-12)
        assert next(c for c in seed.channels if c[0] == "lexical")[2] > 0


def test_an_unknown_name_or_a_near_miss_of_a_key_seeds_nothing_and_says_so(tmp_path):
    template = first("M5")
    engine, published = loaded(tmp_path, template)
    with engine:
        key = key_of(template, template.graph.seed_node)
        request = interpret(published, "R0")
        near = key[:-1] + ("0" if key[-1] != "0" else "1")
        registered = {
            k for (k,) in engine.db.connection.execute("SELECT external_key FROM entities")
        }
        assert near not in registered and key in registered
        wrong = replace(request, text=f"Which chain starts at Nobody-0000000000 (key {near})?")
        exact_only = build_seed(engine, wrong, ("exact",))
        assert exact_only.anchors == () and set(exact_only.flags) == {EMPTY_SEED, EXACT_DEGRADED}
        assert exact_only.reasons == (("exact", "NO_EXACT_CUE"),)
        unknown = build_seed(engine, replace(request, text="Nobody-0000000000"), ("lexical",))
        assert unknown.anchors == () and unknown.reasons == (("lexical", "NO_MATCH"),)
        # Control: the real key in the same sentence seeds.
        real = replace(wrong, text=wrong.text.replace(near, key))
        assert build_seed(engine, real, ("exact",)).anchors
        with pytest.raises(NornError, match="SEED_CHANNEL_NOT_GATHERED"):
            build_seed(engine, request, ("exact", "binding"))
        with pytest.raises(NornError, match="LOCAL_MODELS_NOT_ENABLED"):
            build_seed(engine, request, ("dense",))


def test_a_name_that_matches_several_entities_seeds_all_and_is_flagged(engine):
    built(
        engine,
        [
            (
                "n1",
                "Twin-1234",
                "Twin-1234 is registered and active. [key:svc.twin0001]",
                "svc.twin0001",
            ),
            (
                "n2",
                "Twin-1234",
                "Twin-1234 is registered and active. [key:svc.twin0002]",
                "svc.twin0002",
            ),
            (
                "n3",
                "Solo-5678",
                "Solo-5678 is registered and active. [key:svc.solo0001]",
                "svc.solo0001",
            ),
        ],
    )
    request = RecallRequest("who is Twin-1234", clock(), subject="Twin-1234", candidate_limit=20)
    seed = build_seed(engine, request, ("exact",))
    assert seed_channels.AMBIGUOUS_NAME in seed.flags and len(seed.anchors) == 2
    assert [round(a.weight, 12) for a in seed.anchors] == [0.5, 0.5]  # none preferred
    single = build_seed(
        engine, RecallRequest("who is Solo-5678", clock(), subject="Solo-5678"), ("exact",)
    )
    assert seed_channels.AMBIGUOUS_NAME not in single.flags and len(single.anchors) == 1
    # More matches than a candidate list holds is a scope, not an exact lookup: say so.
    tight = build_seed(
        engine,
        RecallRequest(
            "who is Twin-1234", clock(), subject="Twin-1234", candidate_limit=1, final_limit=1
        ),
        ("exact",),
    )
    assert tight.anchors == () and EXACT_DEGRADED in tight.flags
    assert tight.reasons == (("exact", "OVER_CANDIDATE_LIMIT"),)


# --- the reader is shown nothing it may not read, in any world ---------------------------------


def private_seed_world(tmp_path, name, *, with_private: bool, private_first: bool):
    engine = Engine(tmp_path / name, HOST, create=True, clock=fixed_clock)
    engine.access.bootstrap()
    private = None
    spec_private = [
        (
            "priv",
            "Svc-priv",
            "Svc-priv is registered and active. [key:svc.priv0001]",
            "svc.priv0001",
        )
    ]
    if with_private and private_first:
        private = built(engine, spec_private)["priv"]
    built(
        engine,
        [
            (
                "p1",
                "Svc-pub1",
                "Svc-pub1 is registered and active. [key:svc.pub00001]",
                "svc.pub00001",
            ),
            (
                "p2",
                "Svc-pub2",
                "Svc-pub2 depends on svc.pub00001. [key:svc.pub00002]",
                "svc.pub00002",
            ),
        ],
    )
    if with_private and not private_first:
        private = built(engine, spec_private)["priv"]
    engine.access.grant(READER, "READ")
    if private is not None:
        engine.access.set_scope(source_of(engine, private["event_id"]), LABEL)
        engine.access.grant(READER, "READ", revoke=True, scope=LABEL)
    return engine, private


def test_a_denied_private_object_seeds_nothing_and_changes_no_byte_the_reader_sees(tmp_path):
    text = "what does svc.pub00002 need, and svc.priv0001 and Svc-priv"
    digests, owner_vectors = [], []
    for index, (with_private, private_first) in enumerate(
        ((False, False), (True, False), (True, True))
    ):
        engine, private = private_seed_world(
            tmp_path, f"w{index}", with_private=with_private, private_first=private_first
        )
        with engine:
            request = RecallRequest(text, clock(), candidate_limit=20)
            owner_seed = build_seed(engine, request, ("exact", "lexical"))
            owner_vectors.append(owner_seed.vector())
            with reader_of(engine) as reader:
                reader_seed = build_seed(reader, request, ("exact", "lexical"))
                digests.append(reader_seed.digest())
                assert len(reader_seed.anchors) >= 1  # positive control: the public entity seeds
                if private is not None:
                    hidden = entity_of(engine, private["atom_ids"][0])
                    assert hidden in owner_seed.vector()  # the owner does see it
                    assert hidden not in reader_seed.vector()
                    assert private["atom_ids"][0] not in json.dumps(reader_seed.payload())
    assert digests[0] == digests[1] == digests[2]
    assert len(owner_vectors[1]) == len(owner_vectors[0]) + 1


def test_an_erased_source_stops_seeding_at_once(tmp_path):
    with Engine(tmp_path / "w", HOST, create=True, clock=fixed_clock) as engine:
        engine.access.bootstrap()
        receipts = built(
            engine,
            [
                (
                    "a",
                    "Svc-aaa",
                    "Svc-aaa is registered and active. [key:svc.aaaaaaaa]",
                    "svc.aaaaaaaa",
                )
            ],
        )
        request = RecallRequest("svc.aaaaaaaa", clock(), candidate_limit=20)
        assert build_seed(engine, request, ("exact", "lexical")).anchors
        engine.deny(
            source_of(engine, receipts["a"]["event_id"]), "erase-seed-2", "synthetic-expiry"
        )
        after = build_seed(engine, request, ("exact", "lexical"))
        assert after.anchors == () and EMPTY_SEED in after.flags


def test_a_stranger_without_a_read_grant_gets_the_absent_error(engine):
    three(engine)
    stranger = Engine(engine.root, type(HOST)(engine.access.host.namespace, "nobody"))
    with stranger, pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
        build_seed(stranger, RecallRequest("svc.aaaaaaaa", clock()), ("exact",))


# --- label independence and topology independence ----------------------------------------------


def test_seed_construction_imports_no_evaluator_gold_graph_or_randomness():
    forbidden = ("benchmark", "random", "socket", "urllib", "norn.graph.adjacency")
    for module in (seeds_module, seed_channels):
        path = Path(module.__file__)
        imported = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert not [m for m in imported if m.startswith(forbidden)], (path.name, imported)
        assert any(m.startswith("norn.") for m in imported)  # control: the parse found imports


def test_shuffled_hidden_gold_leaves_the_seed_bytes_identical_and_the_query_does_not(tmp_path):
    template = first("M5")
    gold = template.case.gold
    shuffled = replace(
        template,
        case=replace(
            template.case,
            gold=replace(
                gold,
                slots=tuple(reversed(gold.slots)),
                acceptable_sets=tuple(reversed(gold.acceptable_sets)),
                relevant_events=tuple(reversed(gold.relevant_events)),
                forbidden_sources=tuple(reversed(gold.forbidden_sources)),
            ),
        ),
        graph=replace(
            template.graph,
            edges=tuple(reversed(template.graph.edges)),
            seed_node=template.graph.hub_node,
        ),
    )
    assert shuffled.case.gold != gold and shuffled.graph != template.graph  # control: labels moved
    digests = []
    for index, case in enumerate((template, shuffled)):
        engine, published = loaded(tmp_path, case, f"g{index}")
        with engine:
            digests.append(
                build_seed(engine, interpret(published, "R0"), ("exact", "lexical")).digest()
            )
    assert digests[0] == digests[1]
    engine, published = loaded(tmp_path, template, "g2")
    with engine:
        request = interpret(published, "R0")
        changed = replace(
            request, text="Which complete requirement chain starts at Sari-0000000000?"
        )
        assert build_seed(engine, changed, ("exact", "lexical")).digest() != digests[0]


def test_a_seed_is_the_same_over_any_topology_and_lands_on_the_nodes_edges_attach_to(tmp_path):
    template = first("M1")
    engine, published = loaded(tmp_path, template)
    with engine:
        request = interpret(published, "R0")
        before = build_seed(engine, request, ("exact", "lexical"))
        report = extract_relations(engine.registry, TRACK_TEXT)
        assert report.requires > 5  # a derived topology now exists
        after = build_seed(engine, request, ("exact", "lexical"))
        assert after.digest() == before.digest()  # the graph never entered the seed
        graph = build_graph(engine.registry)
        nodes = set(graph.nodes)
        assert all(NodeRef("entity", e) in nodes for e in before.vector())
        # The consumer: an anchor has REQUIRES arcs, so a graph reader can start from the seed.
        reachable = [
            e
            for e in before.vector()
            if graph.neighbors(NodeRef("entity", e), frozenset({"REQUIRES"}))
        ]
        assert reachable
        # One rule: the anchor of every readable atom is the stating entity the T02 reader uses.
        reader = relations._Reader(engine.registry)
        rows = engine.db.connection.execute(
            "SELECT id,subject_ref,source_span_id FROM atoms WHERE ns=?", (engine.access.ns,)
        ).fetchall()
        assert len(rows) > 20
        for row in rows:
            stating = reader.stating_entity(row["id"], row["subject_ref"], row["source_span_id"])
            assert anchor_entity(engine.registry, row["id"]) == stating


# --- the dense channel, when the pinned local models are present -------------------------------


@pytest.mark.skipif(
    not (MODEL_ROOT / "encoder").is_dir(), reason="needs the pinned local encoder in .norn/models"
)
def test_the_dense_t0_channel_seeds_with_its_model_version_and_alone_for_the_dense_arm(tmp_path):
    template = first("M5")
    engine, published = loaded(
        tmp_path, template, "dense", model_root=MODEL_ROOT, enable_models=True
    )
    with engine:
        engine.project()
        request = interpret(published, "R0")
        full = build_seed(engine, request, CONVENTIONAL)
        dense = build_seed(engine, request, DENSE_ONLY)
        assert dense.channels == (("dense", fingerprint("encoder"), len(dense.anchors)),)
        assert dense.anchors and sum(dense.vector().values()) == pytest.approx(1.0, abs=1e-12)
        assert {c[0] for c in full.channels} == {"exact", "lexical", "dense"}
        assert build_seed(engine, request, CONVENTIONAL).digest() == full.digest()
        assert EXACT_DEGRADED not in dense.flags  # not asked for, so not degraded


def test_an_incomplete_eligible_corpus_is_reported_on_the_seed(engine):
    atoms, ent = three(engine)
    whole = build_seed(engine, RecallRequest("svc.aaaaaaaa", clock()), ("exact", "lexical"))
    assert "ELIGIBLE_CORPUS_INCOMPLETE" not in whole.flags and ent["a"] in whole.vector()
    cut = build_seed(
        engine, RecallRequest("svc.aaaaaaaa", clock(), max_scan_records=1), ("exact", "lexical")
    )
    assert "ELIGIBLE_CORPUS_INCOMPLETE" in cut.flags


def test_a_negative_vote_cannot_hide_inside_a_positive_total(engine, monkeypatch):
    atoms, ent = three(engine)
    votes = [ChannelResult("lexical", "l-1", (Vote(ent["a"]), Vote(ent["b"])))]
    basis = basis_of(engine)
    assert len(construct_seed(engine.registry, votes, basis).anchors) == 2
    monkeypatch.setattr(seeds_module, "RRF_K", -1.8)  # masses -1.25 and 5.0: total 3.75 > 0
    with pytest.raises(NornError, match="SEED_MASS_INVALID"):
        construct_seed(engine.registry, votes, basis)
