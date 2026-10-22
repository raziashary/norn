"""Non-executable, bounded numeric checkpoints with exact method/data/training lineage."""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from norn.canonical.sources import safe_path
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest
from norn.embedding.assets import fingerprint
from norn.embedding.binding import REVISION, BindingModel, shapes
from norn.features.views import REVISION as FEATURES

MAX_BYTES = 1_048_576


@dataclass(frozen=True)
class Checkpoint:
    model: BindingModel
    sha256: str
    payload: dict[str, Any]


def payload(model: BindingModel, receipt: dict[str, Any], data_digest: str) -> dict[str, Any]:
    require(
        receipt.get("updates", 0) > 0 and receipt.get("backbone") == "FROZEN",
        "UNTRAINED_BINDING_CHECKPOINT",
    )
    return {
        "schema": 1,
        "method": REVISION,
        "backbone": fingerprint("encoder"),
        "features": FEATURES,
        "variant": model.variant,
        "data_digest": data_digest,
        "training": receipt,
        "parameters": {
            k: base64.b64encode(v.astype("<f4").tobytes()).decode("ascii")
            for k, v in model.parameters.items()
        },
    }


def parse(raw: bytes) -> Checkpoint:
    try:
        require(0 < len(raw) <= MAX_BYTES, "CHECKPOINT_BUDGET")
        value = json.loads(raw)
        require(
            type(value) is dict
            and set(value)
            == {
                "schema",
                "method",
                "backbone",
                "features",
                "variant",
                "data_digest",
                "training",
                "parameters",
            },
            "CHECKPOINT_SCHEMA",
        )
        require(
            value["schema"] == 1
            and value["method"] == REVISION
            and value["backbone"] == fingerprint("encoder")
            and value["features"] == FEATURES,
            "CHECKPOINT_REVISION_MISMATCH",
        )
        require(
            type(value["data_digest"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", value["data_digest"]) is not None,
            "CHECKPOINT_DATA_DIGEST",
        )
        receipt = value["training"]
        require(
            type(receipt) is dict
            and type(receipt.get("updates")) is int
            and 0 < receipt["updates"] <= 200
            and receipt.get("seed") in (11, 29, 47)
            and receipt.get("backbone") == "FROZEN",
            "UNTRAINED_BINDING_CHECKPOINT",
        )
        expected = shapes(value["variant"])
        require(
            type(value["parameters"]) is dict and set(value["parameters"]) == set(expected),
            "CHECKPOINT_PARAMETERS",
        )
        parameters = {}
        for key, shape in expected.items():
            encoded = value["parameters"][key]
            require(type(encoded) is str and len(encoded) <= MAX_BYTES, "CHECKPOINT_PARAMETERS")
            decoded = base64.b64decode(encoded, validate=True)
            require(len(decoded) == int(np.prod(shape)) * 4, "CHECKPOINT_PARAMETERS")
            parameters[key] = np.frombuffer(decoded, dtype="<f4").astype(np.float64).reshape(shape)
        model = BindingModel(value["variant"], parameters=parameters)
        require(model.parameter_count == receipt.get("parameters"), "CHECKPOINT_PARAMETERS")
        for parameter in model.parameters.values():
            parameter.flags.writeable = False
        return Checkpoint(model, digest(raw), value)
    except ValueError, TypeError, KeyError, UnicodeError:
        raise NornError("INVALID_BINDING_CHECKPOINT") from None


def save(path: Path, model: BindingModel, receipt: dict[str, Any], data_digest: str) -> Checkpoint:
    safe_path(path)
    raw = (canonical(payload(model, receipt, data_digest)) + "\n").encode()
    verified = parse(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    return verified


def load(path: Path) -> Checkpoint:
    safe_path(path)
    with path.open("rb") as stream:
        return parse(stream.read(MAX_BYTES + 1))
