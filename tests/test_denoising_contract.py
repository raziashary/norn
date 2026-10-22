import pytest

from benchmark.adapters.binding_arms import capability
from norn.contracts.errors import NornError
from norn.embedding.denoising import encode


def test_disabled_b5_is_explicit_and_cannot_become_an_embedding():
    assert capability("B5")["status"] == "FEATURE_NOT_SUPPORTED"
    with pytest.raises(NornError, match="FEATURE_NOT_SUPPORTED"):
        encode()
