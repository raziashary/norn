"""Disjoint scenario/entity clusters fixed before wording variations."""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

from benchmark.adapters.contracts import PublishedSource
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


# Identity policy (ADR-0029 P06-Q2). Shared identity arises only from what the published text
# itself states: a governed external key or an explicit alias statement in the message. Equal or
# similar display names never merge. Nothing here reads gold, evaluator or world objects.
KEY_STATEMENT = re.compile(r"\[key:([A-Za-z0-9_.:@-]{1,128})\]")
ALIAS_STATEMENT = re.compile(r"\[alias:([A-Za-z0-9_.:@-]{1,128})\]")


@dataclass(frozen=True)
class IdentityPlan:
    """(source id, statement) pairs in published order; the loader applies them as ADMIN."""

    keys: tuple[tuple[str, str], ...]
    aliases: tuple[tuple[str, str], ...]


def identity_plan(sources: Iterable[PublishedSource]) -> IdentityPlan:
    keys: list[tuple[str, str]] = []
    aliases: list[tuple[str, str]] = []
    for source in sources:
        require(digest(source.text.encode()) == source.sha256, "PUBLISHED_SOURCE_DIGEST")
        message = json.loads(source.text)["message"]
        found_keys, found_aliases = KEY_STATEMENT.findall(message), ALIAS_STATEMENT.findall(message)
        # One statement of each kind per source keeps the claim attributable to one span.
        require(len(found_keys) <= 1 and len(found_aliases) <= 1, "AMBIGUOUS_IDENTITY_STATEMENT")
        keys.extend((source.source_id, k) for k in found_keys)
        aliases.extend((source.source_id, a) for a in found_aliases)
    return IdentityPlan(tuple(keys), tuple(aliases))
