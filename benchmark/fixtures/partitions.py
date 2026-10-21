"""Trusted evaluator partition policy; no paraphrase-level random split."""

from dataclasses import dataclass

from benchmark.fixtures.entities import Entity, entity
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest

TIERS = ("smoke", "development", "calibration", "locked")
FAMILIES = tuple(f"E{i}" for i in range(1, 15))


@dataclass(frozen=True)
class Partition:
    tier: str
    entities: tuple[tuple[str, Entity], ...]

    @property
    def sha256(self) -> str:
        return digest(
            canonical([(f, e.hidden_id, e.cluster_id) for f, e in self.entities]).encode()
        )


def partition(seed: int, tier: str, clusters_per_family: int = 1) -> Partition:
    require(
        tier in TIERS and type(clusters_per_family) is int and 1 <= clusters_per_family <= 100,
        "INVALID_PARTITION",
    )
    return Partition(
        tier,
        tuple(
            (family, entity(seed, tier, family, index))
            for family in FAMILIES
            for index in range(clusters_per_family)
        ),
    )


def authorize_partition(role: str, tier: str, *, sealed: bool = False) -> None:
    roles = {
        "smoke": {"smoke"},
        "trainer": {"development"},
        "tuner": {"development"},
        "calibrator": {"calibration"},
        "confirmatory": {"locked"},
    }
    require(role in roles and tier in roles[role], "PARTITION_ACCESS_DENIED")
    require(tier != "locked" or sealed, "LOCKED_NOT_SEALED")
