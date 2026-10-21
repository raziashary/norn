"""RRF v1: one vote per canonical record per channel; exact candidates are retained."""

from norn.contracts.errors import require
from norn.retrieval.contracts import Hit, Record

VERSION = "rrf-k60-exact-union-v1"


def fuse(
    exact: tuple[Hit, ...], channels: tuple[tuple[Hit, ...], ...], limit: int
) -> tuple[Hit, ...]:
    require(1 <= limit <= 1000)
    scores: dict[str, float] = {}
    records: dict[str, Record] = {}
    for channel in (exact, *channels):
        seen: set[str] = set()
        for rank, hit in enumerate(channel, 1):
            key = hit.record.key
            require(key not in seen, "DUPLICATE_CHANNEL_VOTE")
            seen.add(key)
            require(key not in records or records[key] == hit.record, "CANDIDATE_IDENTITY_MISMATCH")
            records[key] = hit.record
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    exact_keys = {h.record.key for h in exact}
    # The exact channel has the same bounded depth as every other channel.
    require(len(exact_keys) <= limit, "EXACT_UNION_BUDGET")
    selected = (
        list(exact_keys)
        + [key for key in ordered if key not in exact_keys][: limit - len(exact_keys)]
    )
    return tuple(
        Hit(records[key], scores[key], "fusion")
        for key in sorted(selected, key=lambda key: (-scores[key], key))
    )
