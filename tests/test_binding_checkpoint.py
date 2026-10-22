import json

import numpy as np
import pytest
from test_binding import batch

from norn.contracts.errors import NornError
from norn.contracts.identity import canonical
from norn.embedding.binding import BindingModel
from norn.embedding.checkpoint import load, parse, save
from norn.embedding.numerics import contrastive
from norn.embedding.training import train


def test_checkpoint_reopen_is_exact_bounded_non_executable_and_requires_training(tmp_path):
    model, b = BindingModel("B4"), batch()
    receipt = train(model, (b,), seed=11, updates=2)
    path = tmp_path / "checkpoint.json"
    original = save(path, model, receipt, "0" * 64)
    restored = load(path)
    assert original.sha256 == restored.sha256
    before = model.forward(b.facets, b.mask)[0]
    assert np.allclose(restored.model.forward(b.facets, b.mask)[0], before, atol=1e-6)
    assert path.stat().st_size < 1_048_576
    for p in restored.model.parameters.values():
        assert not p.flags.writeable
    altered = json.loads(path.read_bytes())
    altered["training"]["updates"] = 0
    with pytest.raises(NornError, match="UNTRAINED_BINDING_CHECKPOINT"):
        parse(canonical(altered).encode())
    altered["training"]["updates"] = 2
    altered["method"] = "wrong-geometry"
    with pytest.raises(NornError, match="CHECKPOINT_REVISION_MISMATCH"):
        parse(canonical(altered).encode())
    with pytest.raises(NornError, match="CHECKPOINT_BUDGET"):
        parse(b" " * 1_048_577)
    with pytest.raises(NornError, match="INVALID_BINDING_CHECKPOINT"):
        parse(b"{bad json")


def test_all_acceptable_positives_do_not_force_single_episode_and_deadline_stops():
    values = np.eye(3)
    loss, dq, dm = contrastive(
        values, values, np.ones((3, 3), dtype=bool), np.ones((3, 3), dtype=bool)
    )
    assert abs(loss) < 1e-12 and np.allclose(dq, 0) and np.allclose(dm, 0)
    times = iter((0.0, 1201.0))
    with pytest.raises(NornError, match="TRAINING_DEADLINE"):
        train(BindingModel("B3"), (batch(),), seed=11, now=lambda: next(times))
