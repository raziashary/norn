import numpy as np
import pytest

from norn.contracts.errors import NornError
from norn.embedding.concatenate import encode


def test_equal_weight_scaling_missing_mask_and_fixed_384_bytes_geometry():
    x = np.ones((2, 3, 384))
    mask = np.array([[1.0, 1.0, 0.0], [1.0, 1.0, 1.0]])
    z = encode(x, mask).reshape(2, 3, 128)
    assert np.allclose(np.linalg.norm(z[0], axis=1), [2**-0.5, 2**-0.5, 0])
    assert np.allclose(np.linalg.norm(z[1], axis=1), [3**-0.5] * 3)
    assert z.astype(np.float32).nbytes == 2 * 1536
    with pytest.raises(NornError, match="BINDING_ALL_MISSING"):
        encode(x, np.zeros((2, 3)))
