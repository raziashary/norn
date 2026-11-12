"""Content-addressed UTF-8 sources; publish bytes before acknowledging SQL state."""

import os
import re
import stat
import time
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


STAGING_PREFIX = ".pending-"
STAGING_MAX_AGE_SECONDS = 3600


def span_of(content: bytes, version: str, start: int, end: int) -> SourceSpan:
    """Validate a UTF-8-aligned span of ``content`` (the bytes named by ``version``)."""
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


@dataclass(frozen=True)
class StagedSource:
    """Durable but unpublished bytes: invisible to readers until ``SourceStore.publish``."""

    version: str
    path: Path
    content: bytes


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

    def stage(self, content: bytes) -> StagedSource:
        """Validate and durably stage bytes without publishing them under their content address."""
        require(
            type(content) is bytes and 0 < len(content) <= MAX_SOURCE_BYTES, "INVALID_SOURCE_SIZE"
        )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise NornError("INVALID_ENCODING") from None
        version = digest(content)
        self._path(version)
        temporary = self.root / (STAGING_PREFIX + uuid4().hex)
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return StagedSource(version, temporary, content)

    def publish(self, staged: StagedSource) -> str:
        """Atomically expose staged bytes under their digest (idempotent) and verify readback."""
        try:
            os.link(staged.path, self._path(staged.version))
        except FileExistsError:
            pass
        require(self.read(staged.version) == staged.content, "SOURCE_INTEGRITY")
        return staged.version

    def discard(self, staged: StagedSource) -> None:
        staged.path.unlink(missing_ok=True)

    def put(self, content: bytes) -> str:
        staged = self.stage(content)
        try:
            return self.publish(staged)
        finally:
            self.discard(staged)

    def sweep_staging(self, max_age_seconds: int = STAGING_MAX_AGE_SECONDS) -> int:
        """Remove staging files abandoned by a crash; fresh ones belong to a live writer."""
        removed = 0
        cutoff = time.time() - max_age_seconds
        for entry in self.root.iterdir():
            if not entry.name.startswith(STAGING_PREFIX):
                continue
            try:
                if not entry.is_file() or entry.is_symlink() or entry.stat().st_mtime >= cutoff:
                    continue
                entry.unlink()
            except FileNotFoundError:
                # A live writer discarded its staging file between the listing and this check.
                continue
            removed += 1
        return removed

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
        return span_of(self.read(version), version, start, end)

    def resolve(self, span: SourceSpan) -> bytes:
        actual = self.span(span.version_id, span.start, span.end)
        require(actual == span, "SPAN_INTEGRITY")
        return self.read(span.version_id)[span.start : span.end]
