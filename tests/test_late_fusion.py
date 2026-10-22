import numpy as np
import pytest

from norn.contracts.errors import NornError
from norn.embedding.late_fusion import scores


def test_hand_rrf_depth_and_duplicate_identity():
    q = np.ones((3, 128)) / np.sqrt(128)
    m = np.stack([q, -q])
    result = scores(q, m, np.ones((2, 3)), ("a", "b"), 1)
    assert result.tolist() == pytest.approx([1 / 61, 0])
    with pytest.raises(NornError, match="BINDING_DUPLICATE_ID"):
        scores(q, m, np.ones((2, 3)), ("a", "a"), 1)
