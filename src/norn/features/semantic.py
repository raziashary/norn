"""Exact canonical source text, without a hidden assertion or identity encoding."""

from norn.features.context import derive as context
from norn.retrieval.contracts import Record

REVISION = "source-span-semantic-v1"


def text(records: tuple[Record, ...]) -> str:
    context(records)  # Require one occurrence, namespace, snapshot and source time.
    return "\n".join(dict.fromkeys(r.text for r in sorted(records, key=lambda r: r.key)))
