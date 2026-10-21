"""Explicit source renderer/parser; the exported JSON is the actual source bytes."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from benchmark.adapters.contracts import PublishedSource
from benchmark.fixtures.entities import opaque
from benchmark.fixtures.observations import Observation

if TYPE_CHECKING:
    from benchmark.fixtures.world import Fact
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest


def render(
    fact: Fact,
    *,
    seed: int,
    namespace: str,
    copy: int = 0,
    principals: tuple[str, ...] = ("reader",),
    language: str = "en",
) -> PublishedSource:
    observation = Observation(
        fact.actor, fact.predicate, fact.value, fact.event_time, fact.recorded_at, fact.origin
    )
    require(language in {"en", "id"})
    sentence = (
        f"{fact.actor}: {fact.predicate} = {fact.value}."
        if language == "en"
        else f"Catatan {fact.actor}: {fact.predicate} = {fact.value}."
    )
    text = canonical({"capture": asdict(observation), "message": sentence})
    key = opaque("source", "publication-v1", seed, namespace, fact.hidden_id, copy, language)
    return PublishedSource(
        key,
        opaque("event", seed, fact.actor, fact.event_time),
        opaque("atom", key),
        text,
        digest(text.encode()),
        namespace,
        principals,
        observation,
        fact.independence_group,
    )
