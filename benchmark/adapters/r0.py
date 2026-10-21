"""R0 factory: exact union and the declared BM25 variant."""

from benchmark.adapters.contracts import ArmSpec

SPEC = ArmSpec(
    "R0",
    "COMMON_INPUT",
    ("source_read",),
    "NONE",
    "PUBLISHED_SOURCE_RECORDS_ONLY",
    "e5-small-pinned-tokenizer-v1",
)
