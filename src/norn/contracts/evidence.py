"""Independent epistemic/state axes and immutable typed fixture values."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import cast

from norn.contracts.errors import require
from norn.contracts.identity import MAX_TEXT, ObjectRef
from norn.contracts.time import TimeValue


class Epistemic(StrEnum):
    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    USER_REPORTED = "USER_REPORTED"
    DOCUMENT_ASSERTION = "DOCUMENT_ASSERTION"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    DERIVED_AGGREGATE = "DERIVED_AGGREGATE"
    RETRACTED = "RETRACTED"


class AssertionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RETRACTED = "RETRACTED"
    UNRESOLVED = "UNRESOLVED"


class Lifecycle(StrEnum):
    COMMITTED = "COMMITTED"
    INDEX_PENDING = "INDEX_PENDING"
    TOMBSTONED = "TOMBSTONED"


class Applicability(StrEnum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    SUPERSEDED = "SUPERSEDED"
    FUTURE = "FUTURE"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class Outcome(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONFLICT = "CONFLICT"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


@dataclass(frozen=True)
class EpistemicState:
    external: Epistemic
    original: Epistemic | None = None

    def __post_init__(self) -> None:
        require(type(self.external) is Epistemic)
        require(
            self.original is None
            or (type(self.original) is Epistemic and self.original != Epistemic.RETRACTED)
        )
        require(self.external == Epistemic.RETRACTED or self.original is None)

    @property
    def origin(self) -> Epistemic | None:
        return self.original if self.external == Epistemic.RETRACTED else self.external

    @property
    def status(self) -> AssertionStatus:
        if self.origin is None:
            return AssertionStatus.UNRESOLVED
        return (
            AssertionStatus.RETRACTED
            if self.external == Epistemic.RETRACTED
            else AssertionStatus.ACTIVE
        )


@dataclass(frozen=True)
class TaggedValue:
    tag: str
    value: str | int | bool | TimeValue | ObjectRef | None

    def __post_init__(self) -> None:
        allowed = {"TEXT", "INTEGER", "DECIMAL", "BOOLEAN", "TIME", "ENTITY_REF", "JSON_NULL"}
        require(self.tag in allowed, "INVALID_TAG")
        match self.tag:
            case "TEXT":
                require(type(self.value) is str and 0 < len(self.value) <= MAX_TEXT)
            case "INTEGER":
                require(type(self.value) is int and -(2**63) <= self.value < 2**63)
            case "BOOLEAN":
                require(type(self.value) is bool)
            case "JSON_NULL":
                require(self.value is None)
            case "DECIMAL":
                require(type(self.value) is str and 0 < len(self.value) <= 128)
                try:
                    require(Decimal(cast(str, self.value)).is_finite(), "NONFINITE_VALUE")
                except InvalidOperation:
                    require(False, "INVALID_DECIMAL")
            case "TIME":
                require(isinstance(self.value, TimeValue))
            case "ENTITY_REF":
                require(isinstance(self.value, ObjectRef) and self.value.kind == "entity")
