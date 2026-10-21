"""Trace allowlist: no prompt, evidence text, raw identifiers or exception strings."""

from norn.contracts.budgets import QueryBudget
from norn.contracts.identity import digest


def trace(
    namespace: str,
    arm: str,
    snapshot: int | None,
    stages: dict[str, int],
    budget: QueryBudget,
    reason: str,
) -> dict[str, object]:
    return {
        "scope_hash": digest(namespace.encode()),
        "arm": arm,
        "snapshot": snapshot,
        "stage_counts": dict(stages),
        "usage": budget.usage(),
        "reason": reason,
        "provider_calls": 0,
        "retry_count": 0,
    }
