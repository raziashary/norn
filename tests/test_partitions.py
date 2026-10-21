import pytest

from benchmark.fixtures.partitions import TIERS, authorize_partition, partition
from norn.contracts.errors import NornError


def test_cluster_partition_before_paraphrases_and_role_custody():
    identities = []
    for tier in TIERS:
        selected = partition(47, tier)
        entities = {e.hidden_id for _, e in selected.entities}
        clusters = {e.cluster_id for _, e in selected.entities}
        assert not any(entities & before[0] or clusters & before[1] for before in identities)
        identities.append((entities, clusters))
    authorize_partition("trainer", "development")
    authorize_partition("confirmatory", "locked", sealed=True)
    for role, tier in (
        ("trainer", "locked"),
        ("calibrator", "development"),
        ("tuner", "calibration"),
    ):
        with pytest.raises(NornError, match="PARTITION_ACCESS_DENIED"):
            authorize_partition(role, tier)
    with pytest.raises(NornError, match="LOCKED_NOT_SEALED"):
        authorize_partition("confirmatory", "locked")
