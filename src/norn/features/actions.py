"""Observed, source-anchored action sequences; process results are never task reward."""

import json
from dataclasses import dataclass

from norn.contracts.errors import require
from norn.contracts.identity import canonical
from norn.contracts.time import parse_instant
from norn.features.context import ContextView
from norn.features.context import derive as context
from norn.retrieval.contracts import Record

REVISION = "observed-actions-v1"
FIELDS = ("action_step", "attempted_tool", "observed_result", "observed_at")


@dataclass(frozen=True)
class ActionStep:
    step: int
    tool: str
    result: str
    observed_at: str
    record_key: str


@dataclass(frozen=True)
class ActionView:
    context: ContextView
    steps: tuple[ActionStep, ...]

    @property
    def applicability(self) -> str:
        return "OBSERVED" if self.steps else "NOT_APPLICABLE"

    @property
    def text(self) -> str | None:
        if not self.steps:
            return None
        return canonical([(s.step, s.tool, s.result, s.observed_at) for s in self.steps])


def derive(records: tuple[Record, ...]) -> ActionView:
    owner = context(records)
    steps = []
    for record in records:
        if record.predicate != "observed_action" or record.origin != "DIRECT_OBSERVATION":
            continue
        if record.status != "ACTIVE":
            continue
        fields = dict(json.loads(record.qualifiers_json))
        require(all(k in fields for k in FIELDS), "ACTION_INPUT_MISSING")
        require(
            all(
                type(fields[k]) is str and 0 < len(fields[k]) <= 256 and fields[k] in record.text
                for k in FIELDS
            ),
            "UNANCHORED_ACTION",
        )
        raw = fields["action_step"]
        require(raw.isascii() and raw.isdecimal() and len(raw) <= 2, "INVALID_ACTION_STEP")
        parse_instant(fields["observed_at"])
        steps.append(
            ActionStep(
                int(raw),
                fields["attempted_tool"],
                fields["observed_result"],
                fields["observed_at"],
                record.key,
            )
        )
    steps.sort(key=lambda s: s.step)
    require([s.step for s in steps] == list(range(len(steps))), "ACTION_SEQUENCE_GAP_OR_DUPLICATE")
    require(
        all(
            parse_instant(a.observed_at) <= parse_instant(b.observed_at)
            for a, b in zip(steps, steps[1:], strict=False)
        ),
        "ACTION_TIME_ORDER",
    )
    return ActionView(owner, tuple(steps))
