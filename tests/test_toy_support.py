import copy
import json

import numpy as np
import pytest

from benchmark.runs import toy_support as ts
from norn.contracts.errors import NornError


def test_top_k_support_and_overlap_are_hand_computed():
    values = np.array([[1.0, 5.0, 3.0, 4.0]])
    assert ts.top_k_mask(values, 2).tolist() == [[False, True, False, True]]
    same = np.array([[1.0, 5.0, 3.0, 4.0]])
    reverse = np.array([[5.0, 1.0, 4.0, 3.0]])  # supports {0, 2} versus {1, 3}
    partial = np.array([[1.0, 5.0, 9.0, 2.0]])  # support {1, 2}: shares index 1 only
    assert ts.overlaps(values, same, 2).tolist() == [1.0]
    assert ts.overlaps(values, reverse, 2).tolist() == [0.0]
    assert ts.overlaps(values, partial, 2).tolist() == [0.5]
    with pytest.raises(NornError, match="TOY_K_INVALID"):
        ts.top_k_mask(values, 4)


def test_support_overlap_is_not_cosine_similarity():
    a = np.array([[1.0, 9.0, 0.0, 8.0, 0.0]])
    b = np.array([[9.0, 1.0, 0.0, 2.0, 0.0]])
    assert ts.overlaps(a, b, 2).tolist() == [1.0 / 2]  # supports {1,3} and {0,1}
    c = np.array([[1.0, 5.0, 0.0, 4.0, 0.0]])  # same support as a, different weights
    assert ts.overlaps(a, c, 2).tolist() == [1.0]
    cosine = float((a * c).sum() / (np.linalg.norm(a) * np.linalg.norm(c)))
    assert cosine < 0.999  # identical supports, cosine below 1: the metrics differ


def test_independent_supports_match_k_over_d_and_correlated_ones_match_the_joint_tail():
    cells = ts.simulate("V1")
    for k in ts.KS:
        cell = cells[(k, 0.0)]
        assert abs(cell["mean"] - k / ts.DIMENSION) <= 3 * cell["standard_error"]
    expected = ts.declared()["study_1"]["mean_support_overlap"]
    for k in ts.KS:
        for rho in ts.RHOS:
            tail = ts.joint_tail_expectation(k, rho)  # computed without any simulation
            assert abs(tail - expected[f"k{k}"][str(rho)]) < 0.01, (k, rho)
            measured = cells[(k, rho)]
            assert abs(measured["mean"] - tail) < 0.01


def test_first_ordering_reproduces_the_declared_numbers_exactly():
    comparison = ts.compare(ts.simulate("V1"))
    assert comparison["verdict"] == "EXACT_REPRODUCTION" and comparison["exact_reproduction"]
    assert all(abs(c["deviation"]) <= 0.00005 for c in comparison["cells"])


def test_a_failed_reproduction_stays_visible():
    cells = ts.simulate("V1")
    altered = copy.deepcopy(ts.declared())
    altered["study_1"]["mean_support_overlap"]["k41"]["0.7"] += 0.001
    comparison = ts.compare(cells, altered)
    assert comparison["verdict"] == "NOT_EXACT_REPRODUCTION"
    bad = next(c for c in comparison["cells"] if (c["k"], c["rho"]) == (41, 0.7))
    assert not bad["exact"] and bad["within_3_se"]  # consistent in noise, still not exact
    with pytest.raises(NornError, match="TOY_VARIANT_UNKNOWN"):
        ts.simulate("V9")


def test_report_lists_every_declared_ordering_and_the_scope_warning(tmp_path):
    out = tmp_path / "support.json"
    result = ts.run(out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert set(saved["variants"]) == {"V1", "V2", "V3"} and saved["numpy"] == np.__version__
    assert "NOT_COSINE" in saved["scope"] and "NOT_REAL_EMBEDDINGS" in saved["scope"]
    assert result["verdict"] == saved["verdict"] and "V1" in saved["exact_variants"]
    assert saved["ordering_note"].startswith("three declared orderings")
