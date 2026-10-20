"""Content-addressed UTF-8 sources; publish bytes before acknowledging SQL state."""

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from norn.contracts.errors import NornError, require
from norn.contracts.identity import digest

MAX_SOURCE_BYTES = 1_048_576


def safe_path(path: Path) -> None:
    require(
        not any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)),
        "UNSAFE_SOURCE_PATH",
    )


@dataclass(frozen=True)
class SourceSpan:
    version_id: str
    start: int
    end: int
    sha256: str

    def __post_init__(self) -> None:
        require(re.fullmatch(r"[0-9a-f]{64}", self.version_id) is not None, "INVALID_DIGEST")
        require(re.fullmatch(r"[0-9a-f]{64}", self.sha256) is not None, "INVALID_DIGEST")
        require(
            type(self.start) is int
            and type(self.end) is int
            and 0 <= self.start < self.end <= MAX_SOURCE_BYTES,
            "INVALID_SPAN",
        )


class SourceStore:
    def __init__(self, root: Path):
        safe_path(root)
        self.root = root.absolute()
        self.root.mkdir(parents=True, exist_ok=True)
        safe_path(self.root)

    def _path(self, version: str) -> Path:
        require(re.fullmatch(r"[0-9a-f]{64}", version) is not None, "INVALID_DIGEST")
        path = self.root / version
        safe_path(path)
        return path

    def put(self, content: bytes) -> str:
        require(
            type(content) is bytes and 0 < len(content) <= MAX_SOURCE_BYTES, "INVALID_SOURCE_SIZE"
        )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise NornError("INVALID_ENCODING") from None
        version = digest(content)
        target = self._path(version)
        temporary = self.root / (".pending-" + uuid4().hex)
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
        require(self.read(version) == content, "SOURCE_INTEGRITY")
        return version

    def read(self, version: str) -> bytes:
        path = self._path(version)
        try:
            with path.open("rb") as stream:
                metadata = os.fstat(stream.fileno())
                require(
                    stat.S_ISREG(metadata.st_mode) and metadata.st_size <= MAX_SOURCE_BYTES,
                    "SOURCE_INTEGRITY",
                )
                content = stream.read(MAX_SOURCE_BYTES + 1)
        except FileNotFoundError:
            raise NornError("SOURCE_UNAVAILABLE", "source") from None
        require(digest(content) == version, "SOURCE_INTEGRITY")
        return content

    def span(self, version: str, start: int, end: int) -> SourceSpan:
        content = self.read(version)
        require(
            type(start) is int and type(end) is int and 0 <= start < end <= len(content),
            "INVALID_SPAN",
        )
        try:
            content[:start].decode("utf-8")
            piece = content[start:end]
            piece.decode("utf-8")
        except UnicodeDecodeError:
            raise NornError("INVALID_UTF8_BOUNDARY") from None
        return SourceSpan(version, start, end, digest(piece))

    def resolve(self, span: SourceSpan) -> bytes:
        actual = self.span(span.version_id, span.start, span.end)
        require(actual == span, "SPAN_INTEGRITY")
        return self.read(span.version_id)[span.start : span.end]
