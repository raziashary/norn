"""Learned binding capability specifications; checkpoints are separate run identities."""

from benchmark.adapters.contracts import ArmSpec
from norn.embedding.assets import fingerprint

SPECS = {
    variant: ArmSpec(
        variant,
        "COMMON_INPUT",
        ("source_read",),
        fingerprint("encoder"),
        "PUBLIC_SOURCE_RECORDS_ONLY",
        "e5-small-pinned-tokenizer-v1",
    )
    for variant in ("B3", "B4", "S3", "S4")
}
