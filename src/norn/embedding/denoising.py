"""B5 eligibility, deliberately distinct from ordinary cue-corruption training."""

from norn.contracts.errors import NornError


def capability() -> dict[str, str]:
    return {
        "variant": "B5",
        "status": "FEATURE_NOT_SUPPORTED",
        "reason": "NO_SEPARATE_GENERATIVE_HYPOTHESIS_OR_COMPUTE_APPROVAL",
    }


def encode() -> None:
    raise NornError("FEATURE_NOT_SUPPORTED")
