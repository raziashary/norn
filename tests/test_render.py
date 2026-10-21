from benchmark.adapters.common import parse_source
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.render import render
from benchmark.fixtures.world import build_world


def test_source_roundtrip_and_no_hidden_fact_ids():
    world = build_world(47, partition(47, "smoke"))
    for episode in world.episodes:
        for fact in episode.facts:
            source = render(fact, seed=world.seed, namespace="t/w/p")
            actual = parse_source(source)
            assert (actual.actor, actual.value, actual.event_time) == (
                fact.actor,
                fact.value,
                fact.event_time,
            )
            assert fact.hidden_id not in str(source.public())
            assert "true_cause" not in source.text and world.gold_canary not in source.text
