"""Public binding capability ledger, without hidden supervision or silent fallback."""

from norn.contracts.errors import require
from norn.embedding.binding import VARIANTS
from norn.embedding.denoising import capability as denoising


def capability(variant: str) -> dict[str, str]:
    if variant == "B5":
        return denoising()
    require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
    return {"variant": variant, "status": "EXPLICIT_PROJECT_AND_MODEL_ENABLEMENT_REQUIRED"}
