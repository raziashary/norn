"""R2 factory: exact/BM25/dense canonical RRF."""

from benchmark.adapters.contracts import ArmSpec
from norn.embedding.assets import fingerprint

SPEC = ArmSpec(
    "R2",
    "COMMON_INPUT",
    ("source_read",),
    fingerprint("encoder"),
    "PUBLISHED_SOURCE_RECORDS_ONLY",
    "e5-small-pinned-tokenizer-v1",
)
