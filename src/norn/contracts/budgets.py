"""One monotonic owner accounts for the whole recall, including failed model attempts."""

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Event

from norn.contracts.errors import NornError, require


@dataclass
class QueryBudget:
    deadline_ms: int
    cancelled: Event = field(default_factory=Event)
    max_model_calls: int = 256
    max_model_tokens: int = 200_000
    now: Callable[[], float] = time.monotonic
    model_calls: int = 0
    model_tokens: int = 0
    model_truncated: bool = False
    records: int = 0
    artifact_bytes: int = 0
    started: float = field(init=False)

    def __post_init__(self) -> None:
        require(0 < self.deadline_ms <= 600_000)
        self.started = self.now()

    def checkpoint(self) -> None:
        require(not self.cancelled.is_set(), "QUERY_CANCELLED")
        require((self.now() - self.started) * 1000 < self.deadline_ms, "QUERY_DEADLINE")

    def attempt(self, maximum_tokens: int) -> None:
        self.checkpoint()
        require(self.model_calls < self.max_model_calls, "MODEL_CALL_BUDGET")
        require(self.model_tokens + maximum_tokens <= self.max_model_tokens, "MODEL_TOKEN_BUDGET")
        self.model_calls += 1
        # Reserve the worst case before native work; failed attempts retain the reservation.
        self.model_tokens += maximum_tokens

    def complete(self, reserved: int, actual: int) -> None:
        require(0 <= actual <= reserved, "MODEL_TOKEN_ACCOUNTING")
        self.model_tokens -= reserved - actual
        self.checkpoint()

    def usage(self) -> dict[str, int]:
        return {
            "model_calls": self.model_calls,
            "model_tokens": self.model_tokens,
            "records": self.records,
            "artifact_bytes": self.artifact_bytes,
            "elapsed_ms": int((self.now() - self.started) * 1000),
        }

    def artifact(self, size: int) -> None:
        self.checkpoint()
        require(
            0 <= size <= 1_048_576 and self.artifact_bytes + size <= 67_108_864,
            "PROJECTION_ARTIFACT_BUDGET",
        )
        self.artifact_bytes += size

    @contextmanager
    def sqlite_guard(self, connection: sqlite3.Connection) -> Iterator[None]:
        previous = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        interrupted: list[NornError] = []

        def progress() -> int:
            try:
                self.checkpoint()
                return 0
            except NornError as error:
                interrupted.append(error)
                return 1

        connection.execute("PRAGMA busy_timeout=0")
        connection.set_progress_handler(progress, 1000)
        try:
            yield
        except sqlite3.Error:
            raise (
                interrupted[0] if interrupted else NornError("STORE_QUERY_UNAVAILABLE", "storage")
            ) from None
        finally:
            connection.set_progress_handler(None, 0)
            connection.execute(f"PRAGMA busy_timeout={previous}")
