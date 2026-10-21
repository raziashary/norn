"""Owner-approved public model assets. Acquisition is explicit, bounded and hash checked."""

import hashlib
import os
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from norn.canonical.sources import safe_path
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest


class ModelAsset(TypedDict):
    repository: str
    revision: str
    license: str
    files: dict[str, tuple[int, str]]


class InferenceMethod(TypedDict):
    revision: str
    max_length: int
    dimension: int
    query_prefix: str
    passage_prefix: str
    postprocess: str


METHODS: dict[str, InferenceMethod] = {
    "encoder": {
        "revision": "e5-masked-mean-f64-unit-f32-v1",
        "max_length": 512,
        "dimension": 384,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "postprocess": (
            "FP32 hidden states; int64 mask promotes mean/norm to FP64; unit FP32 output; cosine"
        ),
    },
    "reranker": {
        "revision": "cross-encoder-raw-logit-f32-v1",
        "max_length": 512,
        "dimension": 1,
        "query_prefix": "",
        "passage_prefix": "",
        "postprocess": "query/document pair; FP32 scalar logit; descending relevance; no sigmoid",
    },
}


MODELS: dict[str, ModelAsset] = {
    "encoder": {
        "repository": "intfloat/multilingual-e5-small",
        "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
        "license": "MIT",
        "files": {
            "onnx/model.onnx": (
                470268510,
                "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
            ),
            "tokenizer.json": (
                17082730,
                "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
            ),
        },
    },
    "reranker": {
        "repository": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "revision": "1427fd652930e4ba29e8149678df786c240d8825",
        "license": "Apache-2.0",
        "files": {
            "onnx/model.onnx": (
                470883696,
                "3e9a03ed1e966f7c5288dd4230e3d6a9bf5e3a170a06f1f4241c5bca12c6487c",
            ),
            "tokenizer.json": (
                17082660,
                "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626",
            ),
        },
    },
}


def fingerprint(kind: str) -> str:
    require(kind in MODELS, "UNKNOWN_MODEL")
    return digest(canonical({"asset": MODELS[kind], "method": METHODS[kind]}).encode())


def verified(root: Path, kind: str, checkpoint: Callable[[], None] | None = None) -> Path:
    require(kind in MODELS, "UNKNOWN_MODEL")
    directory = root / kind
    safe_path(directory)
    for relative, (size, expected) in MODELS[kind]["files"].items():
        path = directory / relative
        safe_path(path)
        require(path.is_file() and path.stat().st_size == size, "MODEL_ASSET_MISSING_OR_SIZE")
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for piece in iter(lambda: stream.read(1_048_576), b""):
                if checkpoint is not None:
                    checkpoint()
                h.update(piece)
        require(h.hexdigest() == expected, "MODEL_ASSET_DIGEST")
    return directory


def acquire(root: Path, *, enabled: bool = False, deadline_seconds: int = 900) -> None:
    require(enabled is True, "ASSET_DOWNLOAD_NOT_ENABLED")
    require(type(deadline_seconds) is int and 1 <= deadline_seconds <= 1800)
    safe_path(root)
    deadline = time.monotonic() + deadline_seconds
    for kind, model in MODELS.items():
        for relative, (size, expected) in model["files"].items():
            destination = root / kind / relative
            safe_path(destination)
            if destination.exists():
                # Existing state is never overwritten or silently repaired.
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".partial-" + uuid4().hex)
            url = (
                "https://huggingface.co/"
                + model["repository"]
                + "/resolve/"
                + model["revision"]
                + "/"
                + relative
                + "?download=true"
            )
            h = hashlib.sha256()
            count = 0
            with (
                urllib.request.urlopen(url, timeout=30) as response,
                temporary.open("xb") as stream,
            ):
                while True:
                    require(time.monotonic() < deadline, "MODEL_DOWNLOAD_DEADLINE")
                    block = response.read(1_048_576)
                    if not block:
                        break
                    count += len(block)
                    require(count <= size, "MODEL_DOWNLOAD_SIZE")
                    stream.write(block)
                    h.update(block)
                    if count % (32 * 1_048_576) == 0:
                        print(kind, relative, count, "bytes received", flush=True)
                stream.flush()
                os.fsync(stream.fileno())
            require(count == size and h.hexdigest() == expected, "MODEL_DOWNLOAD_DIGEST")
            require(not destination.exists(), "MODEL_DESTINATION_RACE")
            os.replace(temporary, destination)
            print(kind, relative, "verified", count, "bytes", flush=True)
        verified(root, kind)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--enable-download", action="store_true")
    args = parser.parse_args()
    acquire(args.root, enabled=args.enable_download)


if __name__ == "__main__":
    main()
