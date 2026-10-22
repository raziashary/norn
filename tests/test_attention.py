import numpy as np

from norn.embedding.binding import BindingModel
from norn.embedding.numerics import normalize


def test_masked_facet_values_cannot_change_attention_code():
    rng = np.random.default_rng(3)
    model = BindingModel("B4")
    x = normalize(rng.normal(size=(2, 3, 384)))[0]
    mask = np.array([[1.0, 1.0, 0.0], [1.0, 0.0, 1.0]])
    before = model.forward(x, mask)[0]
    x[0, 2] = 1000
    x[1, 1] = -1000
    assert np.allclose(before, model.forward(x, mask)[0])
