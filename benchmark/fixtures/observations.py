"""Source-side authenticated synthetic capture, not evaluator causal truth."""

from dataclasses import dataclass

from norn.contracts.errors import require
from norn.contracts.time import parse_instant


@dataclass(frozen=True)
class Observation:
    actor: str
    predicate: str
    value: str
    event_time: str
    recorded_at: str
    origin: str
    producer: str = "synthetic-recorder-v1"

    def __post_init__(self) -> None:
        require(
            all(
                type(v) is str and 0 < len(v) <= 4096
                for v in (self.actor, self.predicate, self.value, self.producer)
            )
        )
        require(
            self.origin
            in {
                "DIRECT_OBSERVATION",
                "USER_REPORTED",
                "DOCUMENT_ASSERTION",
                "MODEL_INFERENCE",
                "HYPOTHESIS",
                "DERIVED_AGGREGATE",
            }
        )
        parse_instant(self.event_time)
        parse_instant(self.recorded_at)
