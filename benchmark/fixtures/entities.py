"""Disjoint scenario/entity clusters fixed before wording variations."""

from dataclasses import dataclass

from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest


def opaque(kind: str, *parts: object) -> str:
    return kind + "_" + digest(canonical(parts).encode())


@dataclass(frozen=True)
class Entity:
    hidden_id: str
    alias: str
    cluster_id: str


def entity(seed: int, partition: str, family: str, index: int) -> Entity:
    require(type(seed) is int and seed >= 0 and type(index) is int and index >= 0)
    cluster = opaque("hidden", "cluster", seed, partition, family, index)
    key = opaque("hidden", "entity", seed, cluster)
    return Entity(key, "Sari-" + opaque("alias", seed, cluster)[6:16], cluster)
