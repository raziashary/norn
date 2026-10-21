from benchmark.fixtures.partitions import FAMILIES, partition
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world


def test_all_families_twins_languages_and_constructed_control_meanings():
    cases = scenarios(build_world(47, partition(47, "smoke")))
    assert len(cases) == 135
    for family in FAMILIES:
        selected = [c for c in cases if c.gold.family == family]
        assert {c.gold.variant for c in selected} == {"positive", "ambiguous", "missing"}
        assert {c.gold.language for c in selected} == {"en", "id", "mixed"}
        for case in selected:
            if case.gold.variant == "positive":
                assert case.gold.expected_status in {"SUPPORTED", "PARTIALLY_SUPPORTED"}
                assert case.gold.acceptable_sets or case.gold.partial_sets
                assert all(
                    set(ids) <= {s.source_id for s in case.sources}
                    for ids in case.gold.acceptable_sets
                )
            elif case.gold.variant == "missing":
                assert case.gold.expected_status in {"NOT_ESTABLISHED", "VERIFICATION_UNAVAILABLE"}
                assert not case.gold.acceptable_sets
    masks = sorted({c.gold.cue_missing_fraction for c in cases if c.gold.family == "E2"})
    assert len(masks) == 5 and masks[-1] > 0.5
    chain = next(c for c in cases if c.gold.family == "E3" and c.gold.variant == "positive")
    assert len(chain.gold.slots) == 4
    assert {
        len(c.gold.slots) for c in cases if c.gold.family == "E3" and c.gold.variant == "positive"
    } == {1, 2, 3, 4}
    for a, b in zip(chain.sources, chain.sources[1:], strict=False):
        assert a.observation.value == b.observation.actor
    mention = next(c for c in cases if c.gold.reason == "MENTION_IS_NOT_REQUIREMENT")
    assert mention.query.text == chain.query.text
    assert mention.sources[-1].observation.predicate == "mentions"
    assert not mention.gold.acceptable_sets
    rare = next(c for c in cases if c.gold.family == "E13" and c.gold.variant == "positive")
    assert any(s.observation.value == "900" for s in rare.sources)
    causal = next(c for c in cases if c.gold.family == "E4" and c.gold.variant == "missing")
    assert causal.gold.reason == "HYPOTHESIS_NOT_VERIFIED_CAUSE"
