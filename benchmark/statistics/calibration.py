"""Calibration-only fit, proper scores, confidence ties and explicit denominators."""

import math
from dataclasses import dataclass
from typing import Any

from norn.contracts.errors import require


def probabilities(values: tuple[tuple[float, bool], ...]) -> None:
    require(bool(values), "NO_CALIBRATION_DENOMINATOR")
    require(
        all(type(p) in (int, float) and 0 <= p <= 1 and type(y) is bool for p, y in values),
        "INVALID_PROBABILITY_OR_TARGET",
    )


@dataclass(frozen=True)
class HistogramCalibration:
    bins: tuple[float, ...]
    counts: tuple[int, ...]
    source_partition: str
    source_digest: str

    def predict(self, probability: float) -> float:
        probabilities(((probability, True),))
        index = min(int(probability * len(self.bins)), len(self.bins) - 1)
        require(self.counts[index] > 0, "UNSUPPORTED_CALIBRATION_BIN")
        return self.bins[index]


def fit(
    values: tuple[tuple[float, bool], ...], partition: str, source_digest: str, bins: int = 10
) -> HistogramCalibration:
    probabilities(values)
    require(partition == "calibration", "CALIBRATION_PARTITION_REQUIRED")
    require(type(bins) is int and 1 <= bins <= 100)
    groups: list[list[bool]] = [[] for _ in range(bins)]
    for probability, correct in values:
        groups[min(int(probability * bins), bins - 1)].append(correct)
    return HistogramCalibration(
        tuple(sum(g) / len(g) if g else 0 for g in groups),
        tuple(len(g) for g in groups),
        partition,
        source_digest,
    )


def proper_scores(values: tuple[tuple[float, bool], ...], bins: int = 10) -> dict[str, Any]:
    probabilities(values)
    require(type(bins) is int and 1 <= bins <= 100)
    brier = sum((p - int(y)) ** 2 for p, y in values) / len(values)
    infinite = any((p == 0 and y) or (p == 1 and not y) for p, y in values)
    loss = None if infinite else -sum(math.log(p if y else 1 - p) for p, y in values) / len(values)
    groups: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for pair in values:
        groups[min(int(pair[0] * bins), bins - 1)].append(pair)
    ece = sum(
        abs(sum(p for p, _ in g) / len(g) - sum(y for _, y in g) / len(g)) * len(g)
        for g in groups
        if g
    ) / len(values)
    # Accept whole confidence-tie blocks; never improve AURC using hidden correctness ordering.
    risk_curve = []
    accepted = 0
    errors = 0
    aurc = 0.0
    for level in sorted({p for p, _ in values}, reverse=True):
        block = [y for p, y in values if p == level]
        accepted += len(block)
        errors += sum(not y for y in block)
        risk = errors / accepted
        aurc += risk * len(block) / len(values)
        risk_curve.append({"threshold": level, "coverage": accepted / len(values), "risk": risk})
    return {
        "n": len(values),
        "brier": brier,
        "log_loss": loss,
        "log_loss_state": "INFINITE" if infinite else "FINITE",
        "ece": ece,
        "aurc": aurc,
        "risk_coverage": risk_curve,
        "target": "ALL_MATERIAL_CLAIMS_CORRECT_AND_SUPPORTED",
    }


def zero_incident_bound(exposures: int, alpha: float = 0.05) -> float | None:
    require(type(exposures) is int and exposures >= 0 and 0 < alpha < 1)
    return 1 - alpha ** (1 / exposures) if exposures else None
