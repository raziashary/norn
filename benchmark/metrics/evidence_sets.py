"""Alternative minimal support sets; copied alternatives never add required slots."""

from typing import Any

from benchmark.fixtures.scenarios import Gold


def evidence_scores(
    ids: tuple[str, ...], gold: Gold, published_ids: frozenset[str]
) -> dict[str, Any]:
    actual = set(ids)
    available_slots = [set(slot) & published_ids for slot in gold.slots]
    satisfiable = [slot for slot in available_slots if slot]
    covered = sum(bool(slot & actual) for slot in satisfiable)
    coverage = covered / len(satisfiable) if satisfiable else None
    alternatives = [set(s) for s in gold.acceptable_sets if set(s) <= published_ids]
    partials = [set(s) for s in gold.partial_sets if set(s) <= published_ids]
    return {
        "slot_coverage": coverage,
        "slot_denominator": len(satisfiable),
        "unsatisfiable_slots": len(available_slots) - len(satisfiable),
        "complete_set": any(s <= actual for s in alternatives) if alternatives else None,
        "complete_set_reason": None if alternatives else "NO_SATISFIABLE_ACCEPTABLE_SET",
        "partial_set": any(s <= actual for s in partials) and actual <= set().union(*partials)
        if partials
        else None,
    }
