"""S0 is a disabled treatment; zero is not an observed emotional measurement."""

from dataclasses import dataclass

from norn.contracts.errors import require

REVISION = "salience-disabled-s0-v1"


@dataclass(frozen=True)
class NeutralSalience:
    present: bool = False
    value: None = None
    treatment: str = "S0"

    def __post_init__(self) -> None:
        require(
            self.present is False and self.value is None and self.treatment == "S0",
            "SALIENCE_TREATMENT_NOT_SUPPORTED",
        )
