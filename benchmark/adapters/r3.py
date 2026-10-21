"""R3 factory: the same R2 pool and pinned fixed-depth reranker."""

from benchmark.adapters.contracts import ArmSpec
from norn.embedding.assets import fingerprint

SPEC = ArmSpec(
    "R3",
    "COMMON_INPUT",
    ("source_read",),
    fingerprint("encoder") + ":" + fingerprint("reranker"),
    "PUBLISHED_SOURCE_RECORDS_ONLY",
    "e5-small-pinned-tokenizer-v1",
)
