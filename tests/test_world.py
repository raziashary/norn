from benchmark.fixtures.partitions import partition
from benchmark.fixtures.world import build_world


def test_deterministic_typed_world_and_private_causes():
    a = build_world(47, partition(47, "smoke"))
    assert a == build_world(47, partition(47, "smoke"))
    assert a.sha256 != build_world(48, partition(48, "smoke")).sha256
    assert len(a.episodes) == 14
    cause = next(e for e in a.episodes if e.family == "E4")
    assert cause.facts[0].true_cause and not cause.facts[1].true_cause
    assert cause.facts[1].origin == "HYPOTHESIS"
