import copy
import json

import numpy as np
import pytest

from benchmark.runs import toy_cues as tc
from norn.contracts.errors import NornError


def test_ties_are_never_credited_and_are_counted_separately():
    target = np.array([3, 2, 2, 5])
    competitor = np.array([1, 2, 3, 5])
    counts = tc.classify(target, competitor)
    assert counts == {"correct": 1, "ties": 2, "errors": 1}
    assert counts["correct"] < counts["correct"] + counts["ties"]  # crediting ties would differ
    with pytest.raises(NornError, match="TOY_OVERLAP_SHAPE"):
        tc.classify(np.array([1, 2]), np.array([1]))


def test_cosine_is_hand_computed():
    a = np.array([[1.0, 0.0], [1.0, 1.0]])
    b = np.array([[0.0, 2.0], [2.0, 2.0]])
    assert tc.cosine(a, b).tolist() == pytest.approx([0.0, 1.0])


def test_small_simulation_is_deterministic_and_counts_every_trial():
    first = tc.simulate("V1", trials=60)
    again = tc.simulate("V1", trials=60)
    assert first == again
    for row in first.values():
        for part in row.values():
            assert sum(part.values()) == 60
    assert tc.simulate("V2", trials=60) != first  # the declared orderings are different draws
    with pytest.raises(NornError, match="TOY_VARIANT_UNKNOWN"):
        tc.simulate("V9")


def test_first_ordering_reproduces_the_declared_table_and_separates_ties():
    rows = tc.simulate("V1")
    comparison = tc.compare(rows)
    assert comparison["verdict"] == "EXACT_REPRODUCTION"
    low = rows[0.2]
    assert low["k41"]["ties"] > 0 and low["k41"]["correct"] + low["k41"]["ties"] <= tc.TRIALS
    # Weak-cue sparse support is mostly wrong or tied; dense cosine is almost always right.
    assert low["dense"]["correct"] / tc.TRIALS > 0.95 > low["k41"]["correct"] / tc.TRIALS


def test_a_failed_reproduction_stays_visible_and_the_scope_denies_real_embedding_claims(tmp_path):
    rows = tc.simulate("V1")
    altered = copy.deepcopy(tc.declared())
    altered["study_2"]["rows"]["0.35"]["k205_strict"] += 0.01
    comparison = tc.compare(rows, altered)
    assert comparison["verdict"] == "NOT_EXACT_REPRODUCTION"
    out = tmp_path / "cues.json"
    result = tc.run(out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert set(saved["variants"]) == {"V1", "V2"} and result["verdict"] == saved["verdict"]
    assert (
        "NOT_REAL_EMBEDDINGS" in saved["scope"]
        and "INFORMATION_RETENTION_MISMATCH" in saved["scope"]
    )
    assert "never credited" in saved["tie_rule"]
