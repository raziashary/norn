"""Only exact namespace-bound source/atom/event identity earns evidence credit."""

from benchmark.adapters.common import validate_result
from benchmark.adapters.contracts import ArmSpec, PublicInput, Result


def normalized_sources(published: PublicInput, result: Result, spec: ArmSpec) -> tuple[str, ...]:
    validate_result(published, result, spec)
    return tuple(dict.fromkeys(item.source_id for item in result.candidates))
