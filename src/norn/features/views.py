"""Source-derived facet fan-out with explicit applicability and measured owner work."""

import time
from dataclasses import dataclass

from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.features import actions, context, salience, semantic
from norn.retrieval.contracts import Record

FACETS = ("context", "semantic", "actions")
REVISION = digest(
    canonical(
        (context.REVISION, semantic.REVISION, actions.REVISION, salience.REVISION, FACETS)
    ).encode()
)


@dataclass(frozen=True)
class Views:
    event_id: str
    records: tuple[Record, ...]
    texts: tuple[str | None, ...]
    durations_ns: tuple[int, ...]
    invocations: tuple[bool, ...]
    salience: salience.NeutralSalience

    @property
    def mask(self) -> tuple[bool, ...]:
        return tuple(t is not None for t in self.texts)

    @property
    def single_text(self) -> str:
        return canonical(dict(zip(FACETS, self.texts, strict=True)))


def derive(records: tuple[Record, ...], *, full_fanout: bool = False) -> Views:
    require(type(full_fanout) is bool)
    texts: list[str | None] = []
    durations = []
    invoked = []
    for facet in FACETS:
        tick = time.perf_counter_ns()
        needed = (
            facet != "actions"
            or full_fanout
            or any(
                r.predicate == "observed_action"
                and r.origin == "DIRECT_OBSERVATION"
                and r.status == "ACTIVE"
                for r in records
            )
        )
        value = None
        if facet == "context":
            value = context.derive(records).text
        elif facet == "semantic":
            value = semantic.text(records)
        elif needed:
            value = actions.derive(records).text
        durations.append(time.perf_counter_ns() - tick)
        invoked.append(needed)
        texts.append(value)
    return Views(
        records[0].event_id,
        records,
        tuple(texts),
        tuple(durations),
        tuple(invoked),
        salience.NeutralSalience(),
    )
