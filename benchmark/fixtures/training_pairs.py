"""Versioned supervised pairs for P05: multi-positive sets and screened hard negatives.

Only the development ``train`` role is readable here (``authorize_partition("trainer", ...)``);
tune, evaluation, calibration and locked cases never reach this module. Every pair records

* the positives: every source the gold accepts (alternative valid evidence and paraphrases of the
  same event), or all eligible sources when the cue is ambiguous (several events are equally
  plausible, so none may be forced into a single positive);
* the negatives, each tagged with the field in which it differs from its anchor positive and
  screened so that no valid alternative is ever marked negative.

A negative is either an existing corpus source (``CORPUS``) or a source synthesized from a
positive by changing exactly one field (``ONE_FIELD``: value, event time or origin). Superseded
versions and cross-tenant negatives are not generated: supersession needs correction lineage and
tenant separation is enforced by deterministic filtering, not learned (blueprint 8.3/8.4).
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray

from benchmark.adapters.contracts import PublishedSource
from benchmark.fixtures.binding_cases import ROLE_INDICES, cases
from benchmark.fixtures.entities import opaque
from benchmark.fixtures.partitions import authorize_partition
from benchmark.fixtures.render import render
from benchmark.fixtures.scenarios import Case
from benchmark.fixtures.world import Fact
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest

PAIRS_VERSION = "training-pairs-v1"
ONE_FIELD_NAMES = ("value", "event_time", "origin")
CORPUS_FIELDS = (*ONE_FIELD_NAMES, "MULTI", "UNRELATED")


@dataclass(frozen=True)
class Negative:
    source_id: str
    kind: str  # CORPUS (existing source) or ONE_FIELD (synthesized from the anchor)
    field: str  # the differing field, MULTI (several) or UNRELATED (different actor/predicate)
    anchor: str  # the positive this negative is compared with or derived from
    source: PublishedSource | None = None  # public record, present only for ONE_FIELD

    def __post_init__(self) -> None:
        require(self.kind in {"CORPUS", "ONE_FIELD"}, "NEGATIVE_KIND")
        require(
            (self.kind == "ONE_FIELD") == (self.source is not None)
            and self.field in (ONE_FIELD_NAMES if self.kind == "ONE_FIELD" else CORPUS_FIELDS),
            "NEGATIVE_FIELD",
        )


@dataclass(frozen=True)
class TrainingPair:
    query_id: str
    query_text: str
    family: str
    variant: str
    language: str
    cluster: str
    ambiguous: bool
    positives: tuple[str, ...]
    positive_sets: tuple[tuple[str, ...], ...]
    negatives: tuple[Negative, ...]
    screened: tuple[tuple[str, int], ...]  # reason -> candidates withheld from the negatives

    def __post_init__(self) -> None:
        require(bool(self.positives), "PAIR_POSITIVE_MISSING")
        negative_ids = {n.source_id for n in self.negatives}
        require(
            len(negative_ids) == len(self.negatives) and not negative_ids & set(self.positives),
            "PAIR_NEGATIVE_IS_POSITIVE",
        )
        require(not self.ambiguous or not self.negatives, "PAIR_AMBIGUOUS_NEGATIVE")


@dataclass(frozen=True)
class TrainingPairs:
    version: str
    role: str
    seed: int
    smoke: bool
    pairs: tuple[TrainingPair, ...]
    skipped: tuple[tuple[str, str], ...]  # query id -> reason

    def payload(self) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(canonical(asdict(self)))
        return result

    @property
    def sha256(self) -> str:
        return digest(canonical(self.payload()).encode())


def _content(observation: Any) -> tuple[str, str, str, str, str]:
    return (
        observation.actor,
        observation.predicate,
        observation.value,
        observation.event_time,
        observation.origin,
    )


def _differing(left: Any, right: Any) -> tuple[str, ...]:
    return tuple(name for name in ONE_FIELD_NAMES if getattr(left, name) != getattr(right, name))


def _bump_value(value: str) -> str:
    """A similarly worded, wrong value: bump the last number, else the last letter."""
    digits = [i for i, ch in enumerate(value) if ch.isdigit()]
    if digits:
        end = digits[-1]
        start = end
        while start > 0 and value[start - 1].isdigit():
            start -= 1
        return value[:start] + str(int(value[start : end + 1]) + 1) + value[end + 1 :]
    letters = [i for i, ch in enumerate(value) if ch.isalpha() and ch.isascii()]
    require(bool(letters), "PAIR_VALUE_NOT_PERTURBABLE")
    i = letters[-1]
    ch = value[i]
    base = ord("A") if ch.isupper() else ord("a")
    return value[:i] + chr(base + (ord(ch) - base + 1) % 26) + value[i + 1 :]


def _perturbed(source: PublishedSource, name: str) -> Fact:
    observation = source.observation
    value, event_time, origin = observation.value, observation.event_time, observation.origin
    if name == "value":
        value = _bump_value(value)
    elif name == "event_time":
        event_time = (datetime.fromisoformat(event_time) + timedelta(days=1)).isoformat()
    else:
        origin = "HYPOTHESIS" if origin != "HYPOTHESIS" else "DIRECT_OBSERVATION"
    return Fact(
        opaque("hidden", PAIRS_VERSION, source.source_id, name),
        observation.actor,
        observation.predicate,
        value,
        event_time,
        observation.recorded_at,
        origin,
        source.independence_group,
    )


def pair_from_case(case: Case, *, seed: int) -> tuple[TrainingPair | None, str]:
    """Build one pair from a case; the caller owns role custody (see ``build_pairs``)."""
    gold = case.gold
    sources = {s.source_id: s for s in case.sources}
    ambiguous = gold.reason == "AMBIGUOUS"
    accepted = tuple(
        dict.fromkeys(i for group in (*gold.acceptable_sets, *gold.partial_sets) for i in group)
    )
    positives = tuple(sources) if ambiguous else tuple(i for i in accepted if i in sources)
    if not positives:
        return None, "NO_ELIGIBLE_SUPERVISED_POSITIVE"
    screened: dict[str, int] = {}
    negatives: list[Negative] = []
    if not ambiguous:
        positive_content: dict[tuple[str, str, str, str, str], str] = {}
        for i in positives:  # the first positive of each content is its anchor
            positive_content.setdefault(_content(sources[i].observation), i)
        anchors = {i: sources[i].observation for i in positives}
        relevant = set(gold.relevant_events)
        for source_id, source in sources.items():
            if source_id in positives:
                continue
            if _content(source.observation) in positive_content:
                screened["DUPLICATE_OF_POSITIVE_CONTENT"] = (
                    screened.get("DUPLICATE_OF_POSITIVE_CONTENT", 0) + 1
                )
                continue
            if source.event_id in relevant:
                screened["SAME_EVENT_AS_POSITIVE"] = screened.get("SAME_EVENT_AS_POSITIVE", 0) + 1
                continue
            # Compare with the positive about the same actor and predicate, if there is one.
            peers = [
                i
                for i, o in anchors.items()
                if (o.actor, o.predicate)
                == (source.observation.actor, source.observation.predicate)
            ]
            if not peers:
                negatives.append(Negative(source_id, "CORPUS", "UNRELATED", positives[0]))
                continue
            nearest = min(peers, key=lambda i: len(_differing(source.observation, anchors[i])))
            differing = _differing(source.observation, anchors[nearest])
            negatives.append(
                Negative(
                    source_id,
                    "CORPUS",
                    differing[0] if len(differing) == 1 else "MULTI",
                    nearest,
                )
            )
        taken = {_content(s.observation) for s in sources.values()}
        for anchor_id in positive_content.values():
            origin = sources[anchor_id]
            for name in ONE_FIELD_NAMES:
                fact = _perturbed(origin, name)
                made = render(fact, seed=seed, namespace=origin.namespace)
                if _content(made.observation) in taken:
                    # The change reproduced an existing source: it may be valid evidence.
                    screened["ONE_FIELD_COLLIDES_WITH_CORPUS"] = (
                        screened.get("ONE_FIELD_COLLIDES_WITH_CORPUS", 0) + 1
                    )
                    continue
                taken.add(_content(made.observation))
                negatives.append(Negative(made.source_id, "ONE_FIELD", name, anchor_id, made))
    sets = (
        (tuple(positives),)
        if ambiguous
        else tuple(tuple(i for i in group if i in sources) for group in gold.acceptable_sets)
    )
    pair = TrainingPair(
        gold.query_id,
        case.query.text,
        gold.family,
        gold.variant,
        gold.language,
        gold.cluster,
        ambiguous,
        positives,
        tuple(group for group in sets if group),
        tuple(negatives),
        tuple(sorted(screened.items())),
    )
    return pair, ""


def build_pairs(role: str = "train", *, seed: int = 20261021, smoke: bool = False) -> TrainingPairs:
    """Pairs for the trainer. Only the ``train`` role is available; anything else is denied."""
    require(role == "train", "PAIRS_ROLE_DENIED")
    authorize_partition("trainer", "development")
    pairs, skipped = [], []
    for case in cases("train", seed=seed, smoke=smoke):
        pair, reason = pair_from_case(case, seed=seed)
        if pair is None:
            skipped.append((case.query.query_id, reason))
        else:
            pairs.append(pair)
    require(bool(pairs), "TRAINING_POSITIVES_EMPTY")
    return TrainingPairs(PAIRS_VERSION, "train", seed, smoke, tuple(pairs), tuple(skipped))


def assert_disjoint_from_heldout(pairs: TrainingPairs) -> dict[str, int]:
    """Prove no train pair shares a cluster, query or source with the tune/evaluation roles."""
    require(pairs.role == "train" and pairs.version == PAIRS_VERSION, "PAIRS_ROLE_DENIED")
    clusters = {p.cluster for p in pairs.pairs}
    queries = {p.query_id for p in pairs.pairs}
    sources = {i for p in pairs.pairs for i in (*p.positives, *(n.source_id for n in p.negatives))}
    checked = 0
    for role in ROLE_INDICES:
        if role == "train":
            continue
        for case in cases(role, seed=pairs.seed, smoke=pairs.smoke):
            checked += 1
            held = {s.source_id for s in case.sources}
            require(
                case.gold.cluster not in clusters
                and case.query.query_id not in queries
                and not held & sources,
                "HELDOUT_LABEL_IN_TRAINING",
            )
    return {"heldout_cases_checked": checked}


def dumps(pairs: TrainingPairs) -> str:
    return canonical({"pairs": pairs.payload(), "sha256": pairs.sha256})


def loads(text: str) -> TrainingPairs:
    """Read versioned pairs, re-deriving the digest and refusing any non-train content."""
    raw = json.loads(text)
    require(type(raw) is dict and set(raw) == {"pairs", "sha256"}, "PAIRS_SCHEMA")
    body = raw["pairs"]
    require(body["version"] == PAIRS_VERSION and body["role"] == "train", "PAIRS_VERSION_OR_ROLE")
    pairs = TrainingPairs(
        body["version"],
        body["role"],
        body["seed"],
        body["smoke"],
        tuple(_pair(item) for item in body["pairs"]),
        tuple((a, b) for a, b in body["skipped"]),
    )
    require(pairs.sha256 == raw["sha256"], "PAIRS_DIGEST")
    return pairs


def _source(item: dict[str, Any] | None) -> PublishedSource | None:
    if item is None:
        return None
    from benchmark.fixtures.observations import Observation

    return PublishedSource(
        **{
            **item,
            "allowed_principals": tuple(item["allowed_principals"]),
            "observation": Observation(**item["observation"]),
        }
    )


def _pair(item: dict[str, Any]) -> TrainingPair:
    return TrainingPair(
        **{
            **item,
            "positives": tuple(item["positives"]),
            "positive_sets": tuple(tuple(g) for g in item["positive_sets"]),
            "negatives": tuple(
                Negative(**{**n, "source": _source(n["source"])}) for n in item["negatives"]
            ),
            "screened": tuple((a, b) for a, b in item["screened"]),
        }
    )


def labels(
    pair: TrainingPair, memory_ids: tuple[str, ...]
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """``(positive, allowed)`` rows for one query over an ordered memory list.

    A memory is allowed only when it is a positive or a screened negative: a source the pair
    knows nothing about is excluded from the denominator instead of being treated as a negative.
    """
    require(len(set(memory_ids)) == len(memory_ids), "PAIR_MEMORY_DUPLICATE")
    positive = np.array([i in pair.positives for i in memory_ids], dtype=bool)
    known = {n.source_id for n in pair.negatives}
    allowed = positive | np.array([i in known for i in memory_ids], dtype=bool)
    require(bool(positive.any()), "PAIR_POSITIVE_NOT_IN_MEMORY")
    return positive, allowed


__all__ = [
    "Negative",
    "TrainingPair",
    "TrainingPairs",
    "assert_disjoint_from_heldout",
    "build_pairs",
    "dumps",
    "labels",
    "loads",
    "pair_from_case",
]
