"""Pair query/seed rows, then resample family clusters and training seeds."""

import random
import statistics
from dataclasses import dataclass
from typing import Any

from norn.contracts.errors import require


@dataclass(frozen=True)
class PairedValue:
    query_id: str
    cluster_id: str
    training_seed: int | None
    value: float

    def __post_init__(self) -> None:
        require(type(self.value) in (int, float) and 0 <= self.value <= 1, "INVALID_PAIRED_VALUE")
        require(
            self.training_seed is None or type(self.training_seed) is int, "INVALID_TRAINING_SEED"
        )


def paired_difference(
    a: tuple[PairedValue, ...],
    b: tuple[PairedValue, ...],
    *,
    seed: int,
    samples: int = 1000,
    min_clusters: int = 5,
) -> dict[str, Any]:
    require(
        type(samples) is int
        and 10 <= samples <= 10_000
        and type(min_clusters) is int
        and min_clusters >= 2,
        "STATISTICAL_BUDGET",
    )
    left = {(v.query_id, v.training_seed): v for v in a}
    right = {(v.query_id, v.training_seed): v for v in b}
    require(
        len(left) == len(a) and len(right) == len(b) and left.keys() == right.keys() and bool(left),
        "UNPAIRED_OR_DUPLICATE_CASES",
    )
    groups: dict[str, dict[int | None, list[float]]] = {}
    for key, value in left.items():
        require(value.cluster_id == right[key].cluster_id, "CLUSTER_MISMATCH")
        groups.setdefault(value.cluster_id, {}).setdefault(value.training_seed, []).append(
            value.value - right[key].value
        )
    seeds = sorted({k[1] for k in left}, key=lambda value: (value is not None, value or 0))
    query_seeds: dict[str, set[int | None]] = {}
    for query_id, training_seed in left:
        query_seeds.setdefault(query_id, set()).add(training_seed)
    require(
        all(values == set(seeds) for values in query_seeds.values())
        and all(set(group) == set(seeds) for group in groups.values()),
        "UNBALANCED_TRAINING_SEEDS",
    )
    # Equal family-cluster weighting avoids paraphrase-rich groups dominating the estimate.
    point = statistics.mean(
        statistics.mean(statistics.mean(values) for values in group.values())
        for group in groups.values()
    )
    result: dict[str, Any] = {
        "difference": point,
        "clusters": len(groups),
        "pairs": len(left),
        "training_seeds": seeds,
        "estimand": "EQUAL_CLUSTER_MEAN_DIFFERENCE",
        "confidence_interval": None,
        "state": "DESCRIPTIVE_SMALL_SAMPLE",
    }
    if len(groups) < min_clusters:
        return result
    rng = random.Random(seed)
    clusters = sorted(groups)
    draws = []
    for _ in range(samples):
        chosen_seeds = rng.choices(seeds, k=len(seeds))
        chosen_clusters = rng.choices(clusters, k=len(clusters))
        draws.append(
            statistics.mean(
                statistics.mean(statistics.mean(groups[c][s]) for s in chosen_seeds)
                for c in chosen_clusters
            )
        )
    draws.sort()
    result.update(
        state="EXPLORATORY_CLUSTER_BOOTSTRAP",
        samples=samples,
        bootstrap_seed=seed,
        confidence_interval=[draws[int((samples - 1) * 0.025)], draws[int((samples - 1) * 0.975)]],
        confidence_level=0.95,
        power="NOT_ESTABLISHED",
    )
    return result


def holm(p_values: dict[str, float]) -> dict[str, float]:
    require(
        bool(p_values) and all(type(p) in (int, float) and 0 <= p <= 1 for p in p_values.values()),
        "INVALID_P_VALUE",
    )
    ordered = sorted(p_values, key=lambda key: (p_values[key], key))
    previous = 0.0
    adjusted = {}
    for rank, key in enumerate(ordered):
        previous = max(previous, min(1.0, (len(ordered) - rank) * p_values[key]))
        adjusted[key] = previous
    return adjusted
