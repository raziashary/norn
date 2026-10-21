"""Immutable JSON artifacts and identities of actual imported code, not intent."""

import hashlib
import json
import os
import platform
from pathlib import Path
from typing import Any

import benchmark
import norn
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest


def code_digest() -> str:
    identities = []
    for name, module in (("benchmark", benchmark), ("norn", norn)):
        root = Path(str(module.__file__)).parent
        for path in sorted(root.rglob("*")):
            if path.suffix in {".py", ".sql"}:
                identities.append(
                    (name + "/" + path.relative_to(root).as_posix(), digest(path.read_bytes()))
                )
    return digest(canonical(identities).encode())


def write_once(path: Path, value: object) -> str:
    require(
        not path.is_symlink() and not any(p.is_symlink() or p.is_junction() for p in path.parents),
        "UNSAFE_ARTIFACT_PATH",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (canonical(value) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def load(path: Path) -> Any:
    require(
        path.is_file()
        and not path.is_symlink()
        and not path.is_junction()
        and not any(p.is_symlink() or p.is_junction() for p in path.parents)
        and path.stat().st_size <= 64_000_000,
        "ARTIFACT_MISSING_OR_BUDGET",
    )
    return json.loads(path.read_bytes())


def file_digest(path: Path) -> str:
    require(
        path.is_file()
        and not path.is_symlink()
        and not path.is_junction()
        and not any(p.is_symlink() or p.is_junction() for p in path.parents)
        and path.stat().st_size <= 64_000_000,
        "ARTIFACT_MISSING_OR_BUDGET",
    )
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for piece in iter(lambda: stream.read(65_536), b""):
            h.update(piece)
    return h.hexdigest()


def hardware() -> dict[str, object]:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "gpu": "NOT_USED",
        "concurrency": 1,
        "cache": "IN_PROCESS_CONTROL_NO_INDEX",
        "provider_prices": "NOT_APPLICABLE_NO_PROVIDER",
        "tokenizer": "whitespace-v1",
    }
