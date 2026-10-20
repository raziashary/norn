"""Safe errors shared by public operations; never include source bodies."""

from uuid import uuid4


class NornError(Exception):
    def __init__(self, code: str, stage: str = "validation", *, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.retryable = retryable
        self.correlation_id = uuid4().hex

    def envelope(self) -> dict[str, object]:
        return {
            "error": self.code,
            "stage": self.stage,
            "retryable": self.retryable,
            "correlation_id": self.correlation_id,
            "partial_result_valid": False,
            "budget_used": {"provider_calls": 0},
        }


def require(condition: bool, code: str = "INVALID_CONTRACT") -> None:
    if not condition:
        raise NornError(code)
