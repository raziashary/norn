"""R1 factory: exhaustive pinned dense retrieval."""

from benchmark.adapters.contracts import ArmSpec
from norn.embedding.assets import fingerprint

SPEC = ArmSpec(
    "R1",
    "COMMON_INPUT",
    ("source_read",),
    fingerprint("encoder"),
    "PUBLISHED_SOURCE_RECORDS_ONLY",
    "e5-small-pinned-tokenizer-v1",
)
