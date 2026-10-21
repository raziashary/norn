"""Only exact namespace-bound source/atom/event identity earns evidence credit."""

from benchmark.adapters.common import validate_result
from benchmark.adapters.contracts import ArmSpec, PublicInput, Result
from norn.retrieval.assembly import TokenCounter


def normalized_sources(
    published: PublicInput, result: Result, spec: ArmSpec, token_counter: TokenCounter | None = None
) -> tuple[str, ...]:
    validate_result(published, result, spec, token_counter)
    return tuple(dict.fromkeys(item.source_id for item in result.candidates))
