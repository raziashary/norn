"""Namespace-qualified identity and deterministic, versioned hashes."""

import hashlib
import json
import re
from dataclasses import dataclass

from norn.contracts.errors import require

MAX_TEXT = 16_384


def label(value: str, limit: int = 128) -> str:
    require(type(value) is str and 0 < len(value) <= limit, "INVALID_LABEL")
    require(re.fullmatch(r"[A-Za-z0-9_.:@-]+", value) is not None, "INVALID_LABEL")
    return value


def canonical(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_id(kind: str, *parts: str) -> str:
    label(kind)
    return kind + "_" + digest(canonical(["norn-id-v1", *parts]).encode())


@dataclass(frozen=True)
class Namespace:
    tenant: str
    workspace: str
    partition: str

    def __post_init__(self) -> None:
        for part in (self.tenant, self.workspace, self.partition):
            label(part)

    @property
    def key(self) -> str:
        return "/".join((self.tenant, self.workspace, self.partition))


@dataclass(frozen=True)
class ObjectRef:
    namespace: Namespace
    kind: str
    object_id: str

    def __post_init__(self) -> None:
        require(self.kind in {"event", "atom", "entity", "source", "edge", "derivation"})
        require(
            re.fullmatch(self.kind + r"_[0-9a-f]{64}", self.object_id) is not None, "INVALID_ID"
        )
