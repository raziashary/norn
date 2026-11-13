"""P06-T18: public-v2 families M1 to M6, determinism, pools, graph degrees and custody."""

import json
import re

import pytest

from benchmark.adapters.baseline import host, load_sources
from benchmark.adapters.common import replay_clock
from benchmark.adapters.contracts import PublicInput
from benchmark.fixtures.entities import identity_plan
from benchmark.fixtures.multihop import (
    FAMILIES,
    MAX_POOL,
    MIN_POOL,
    PRIMARY,
    ROLE_CLUSTERS,
    SEARCH_BUDGET,
    MultiHopCase,
    multihop_cases,
    multihop_partition,
)
from benchmark.fixtures.partitions import TIERS, authorize_partition, partition
from benchmark.fixtures.publication import publish, validate_public
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical, digest
from norn.integration.engine import Engine

SEED = 47
PILOT_DIGEST = "0ee154bf832184d212e2c37c934eb6df4db17e30fad30413beda0cc3a69944ef"


def pilot() -> tuple[MultiHopCase, ...]:
    return multihop_cases(SEED, "pilot")


def first(family: str, variant: str = "positive") -> MultiHopCase:
    return next(
        m for m in pilot() if m.case.gold.family == family and m.case.gold.variant == variant
    )


def fixture_digest(cases: tuple[MultiHopCase, ...]) -> str:
    return digest(
        canonical(
            [
                (publish(m.case).payload(), m.case.gold.query_id, m.case.gold.expected_status)
                for m in cases
            ]
        ).encode()
    )


def resolved_graph(tmp_path, public: PublicInput, *, identity: bool = True):
    """Entity-level REQUIRES graph rebuilt from the published text through the T17 loader."""
    clock = replay_clock(public)
    engine = Engine(tmp_path / "store", host(public), create=True, clock=clock)
    engine.access.bootstrap()
    try:
        mapping, summary = load_sources(engine, public, clock)
        db, ns = engine.db.connection, engine.access.ns
        atom_of = {source: atom for atom, source in mapping.items()}
        key_of = dict(identity_plan(public.sources).keys)
        keyed = {
            k: e
            for e, k in db.execute(
                "SELECT id,external_key FROM entities WHERE ns=? AND external_key IS NOT NULL",
                (ns,),
            )
        }
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                x = parent[x]
            return x

        if identity:
            for left, right in db.execute(
                "SELECT left_id,right_id FROM identity_events WHERE ns=? AND decision='SAME_AS'",
                (ns,),
            ):
                parent[find(left)] = find(right)

        def node(source_id: str) -> str:
            if source_id in key_of:
                return find(keyed[key_of[source_id]])
            row = db.execute(
                "SELECT subject_ref FROM atoms WHERE ns=? AND id=?", (ns, atom_of[source_id])
            ).fetchone()
            return find(row[0])

        edges = {
            (node(s.source_id), find(keyed[s.observation.value]))
            for s in public.sources
            if s.observation.predicate == "requires" and s.observation.value in keyed
        }
        return edges, keyed, summary, find
    finally:
        engine.close()


def walk(edges: set[tuple[str, str]], start: str) -> int:
    length, seen = 0, {start}
    while True:
        nxt = sorted(b for a, b in edges if a == start and b not in seen)
        if len(nxt) != 1:
            return length
        start = nxt[0]
        seen.add(start)
        length += 1


def test_generator_is_deterministic_and_reproduces_its_digest():
    first_run, second_run = pilot(), pilot()
    assert fixture_digest(first_run) == fixture_digest(second_run) == PILOT_DIGEST
    other = multihop_cases(SEED + 1, "pilot")
    assert fixture_digest(other) != PILOT_DIGEST  # control: the digest depends on the seed


def test_roles_have_the_owner_decided_cluster_counts_and_are_disjoint():
    counts = {}
    seen: dict[str, set[str]] = {}
    for role in ROLE_CLUSTERS:
        entities = multihop_partition(SEED, role).entities
        counts[role] = (
            len(entities),
            sum(1 for f, _e in entities if f in PRIMARY),
        )
        seen[role] = {e.cluster_id for _f, e in entities} | {e.hidden_id for _f, e in entities}
    assert counts == {"pilot": (24, 20), "tune": (48, 40), "evaluation": (240, 200)}
    roles = list(seen)
    assert all(not (seen[a] & seen[b]) for i, a in enumerate(roles) for b in roles[i + 1 :]), (
        "a cluster appears in two roles"
    )
    # The P05 tiers (including the evaluation-style calibration and locked tiers) are not reused.
    for tier in TIERS:
        v1 = {e.cluster_id for _f, e in partition(SEED, tier, 3).entities} | {
            e.hidden_id for _f, e in partition(SEED, tier, 3).entities
        }
        assert not any(v1 & ids for ids in seen.values())


def test_v2_roles_are_authorised_only_for_their_own_tier():
    authorize_partition("pilot", "pilot")
    authorize_partition("tune", "tune")
    authorize_partition("evaluation", "evaluation", sealed=True)
    with pytest.raises(NornError, match="LOCKED_NOT_SEALED"):
        authorize_partition("evaluation", "evaluation")
    with pytest.raises(NornError, match="PARTITION_ACCESS_DENIED"):
        authorize_partition("tune", "evaluation", sealed=True)
    with pytest.raises(NornError, match="PARTITION_ACCESS_DENIED"):
        authorize_partition("confirmatory", "evaluation", sealed=True)


def test_pools_exceed_the_output_cap_and_fit_the_search_budget():
    cases = pilot()
    assert {m.case.gold.family for m in cases} == set(FAMILIES)
    for m in cases:
        query = m.case.query
        assert query.max_candidates == 10 and query.search_budget == SEARCH_BUDGET
        assert MIN_POOL <= len(m.case.sources) <= MAX_POOL
        assert len(m.case.sources) > query.max_candidates
        assert len(m.case.sources) <= query.search_budget
        assert m.graph.pool_size == len(m.case.sources)
    assert max(len(m.case.sources) for m in cases) - min(len(m.case.sources) for m in cases) > 10


def test_search_budget_is_public_v2_only_and_v1_bytes_do_not_move():
    v1 = publish(scenarios(build_world(SEED, partition(SEED, "development")))[0])
    assert v1.query.search_budget is None and "search_budget" not in v1.payload()["query"]
    v2 = publish(first("M1").case)
    assert v2.payload()["query"]["search_budget"] == SEARCH_BUDGET
    assert validate_public(json.loads(canonical(v2.payload()))).query.search_budget == 60
    low = json.loads(canonical(v2.payload()))
    low["query"]["search_budget"] = 5  # below the 10-slot output limit
    with pytest.raises(NornError, match="INVALID_SEARCH_BUDGET"):
        validate_public(low)


def test_published_inputs_hold_no_gold_private_source_or_label():
    for m in pilot():
        public = publish(m.case, ("__GOLD_CANARY__",))
        encoded = canonical(public.payload())
        for private in m.graph.private_sources:
            assert private.source_id not in encoded and private.text not in encoded
            assert private.allowed_principals == ("other",)
        for canary in m.case.gold.forbidden_canaries:
            assert canary not in encoded
        assert m.case.gold.cluster not in encoded and m.graph.seed_node not in encoded
        assert re.search(r"\bM[1-6]\b|decoy|bait|distractor|hidden_", encoded) is None
        assert {s.source_id for s in m.case.sources}.isdisjoint(m.case.gold.forbidden_sources)
    # Control: the custody check can fail when a canary is present.
    leaky = first("M4").case
    with pytest.raises(NornError, match="PRIVATE_INFORMATION_LEAK"):
        publish(leaky, (leaky.sources[0].observation.actor,))


def test_m4_positive_has_a_public_detour_and_missing_leaves_only_the_private_path():
    positive, missing = first("M4"), first("M4", "missing")
    assert positive.case.gold.expected_status == "SUPPORTED"
    assert len(positive.case.gold.forbidden_sources) == 2 == len(positive.graph.private_sources)
    assert missing.case.gold.expected_status == "NOT_ESTABLISHED"
    assert missing.case.gold.reason == "PRIVATE_BRIDGE_UNREADABLE"
    needed = {s for slot in positive.case.gold.slots for s in slot}
    published = {s.source_id for s in positive.case.sources}
    assert needed <= published
    assert not (needed <= {s.source_id for s in missing.case.sources})


def test_chain_and_alias_degrees_come_out_of_the_identity_policy(tmp_path):
    for family, hops in (("M1", 2), ("M3", 2), ("M4", 2), ("M5", 2)):
        m = first(family)
        public = publish(m.case)
        edges, keyed, _summary, find = resolved_graph(tmp_path / f"{family}", public)
        seed_key = next(k for h, _n, k in m.graph.nodes if h == m.graph.seed_node)
        assert walk(edges, find(keyed[seed_key])) == hops, family
    m = first("M2")
    public = publish(m.case)
    hops = len(m.case.gold.slots) - 1
    edges, keyed, summary, find = resolved_graph(tmp_path / "M2", public)
    seed_key = next(k for h, _n, k in m.graph.nodes if h == m.graph.seed_node)
    assert summary["alias_links"] == 1 and summary["unresolved"] == []
    assert walk(edges, find(keyed[seed_key])) == hops
    # Negative control: without the SAME_AS link the chain breaks at the alias hop.
    edges, keyed, _s, find = resolved_graph(tmp_path / "M2b", public, identity=False)
    assert walk(edges, find(keyed[seed_key])) == 1


def test_hub_has_the_intended_degrees_and_same_names_never_merge(tmp_path):
    m = first("M3")
    public = publish(m.case)
    edges, keyed, _summary, find = resolved_graph(tmp_path / "M3", public)
    hub = find(keyed[next(k for h, _n, k in m.graph.nodes if h == m.graph.hub_node)])
    assert len(m.graph.decoy_sources) >= 12
    assert sum(1 for _a, b in edges if b == hub) == len(m.graph.decoy_sources) + 1
    assert sum(1 for a, _b in edges if a == hub) == 1
    m = first("M5")
    public = publish(m.case)
    edges, keyed, summary, find = resolved_graph(tmp_path / "M5", public)
    name = next(n for h, n, _k in m.graph.nodes if h == m.graph.seed_node)
    twins = {k for _h, n, k in m.graph.nodes if n == name}
    assert len(twins) == 2 and len({keyed[k] for k in twins}) == 2
    assert summary["alias_links"] == 0
    q = m.case.gold
    seed_key = next(k for h, _n, k in m.graph.nodes if h == m.graph.seed_node)
    assert q.expected_status == "SUPPORTED" and seed_key in public.query.text
    assert [k for k in twins if k in public.query.text] == [seed_key]  # only the intended key
    ambiguous = first("M5", "ambiguous").case.gold
    assert ambiguous.expected_status == "NOT_ESTABLISHED" and ambiguous.acceptable_sets == ()


def test_near_duplicate_episodes_share_one_entity_and_differ_by_date(tmp_path):
    m = first("M6")
    public = publish(m.case)
    episodes = [s for s in public.sources if s.observation.predicate == "parked_in"]
    assert len(episodes) >= 4 and len({s.observation.event_time for s in episodes}) == len(episodes)
    assert len({(s.observation.actor, s.observation.value) for s in episodes}) == 1
    _edges, keyed, summary, _find = resolved_graph(tmp_path / "M6", public)
    assert summary["keys"] >= len(episodes) and len(keyed) == summary["shared_entities"]
    missing = first("M6", "missing").case
    assert missing.gold.slots[0][0] not in {s.source_id for s in missing.sources}
