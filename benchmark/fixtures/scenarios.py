"""Concrete counterfactuals. Gold and private grouping never enter public queries."""

import re
from dataclasses import asdict, dataclass, replace

from benchmark.adapters.contracts import PublishedSource, Query
from benchmark.fixtures.entities import opaque
from benchmark.fixtures.render import render
from benchmark.fixtures.world import Episode, World
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.contracts.time import parse_instant

STATUSES = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONFLICT",
    "NOT_ESTABLISHED",
    "VERIFICATION_UNAVAILABLE",
}


@dataclass(frozen=True)
class Gold:
    query_id: str
    family: str
    cluster: str
    variant: str
    language: str
    expected_status: str
    reason: str
    acceptable_sets: tuple[tuple[str, ...], ...]
    slots: tuple[tuple[str, ...], ...]
    relevant_events: tuple[str, ...]
    forbidden_sources: tuple[str, ...]
    forbidden_canaries: tuple[str, ...]
    cue_missing_fraction: float
    projection_state: str
    partial_sets: tuple[tuple[str, ...], ...] = ()
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require(re.fullmatch(r"query_[0-9a-f]{64}", self.query_id) is not None, "INVALID_QUERY_ID")
        require(self.expected_status in STATUSES)
        require(0 <= self.cue_missing_fraction <= 1)
        require(self.expected_status != "SUPPORTED" or bool(self.acceptable_sets))
        require(
            self.expected_status != "PARTIALLY_SUPPORTED"
            or bool(self.partial_sets and self.missing_fields),
            "PARTIAL_GOLD_INCOMPLETE",
        )


@dataclass(frozen=True)
class Case:
    query: Query
    sources: tuple[PublishedSource, ...]
    gold: Gold

    @property
    def source_digest(self) -> str:
        return digest(canonical([s.public() for s in self.sources]).encode())


def _case(
    world: World, episode: Episode, variant: str, language: str, missing_fraction: float = 0.0
) -> Case:
    family = episode.family
    namespace = (
        "synthetic/" + opaque("scope", world.seed, episode.entity.cluster_id)[6:22] + "/local"
    )
    all_sources = [render(f, seed=world.seed, namespace=namespace) for f in episode.facts]
    target = 1 if len(all_sources) > 1 else 0
    chosen = [all_sources[target]]
    alternatives: list[tuple[str, ...]] = [(chosen[0].source_id,)]
    slots: list[tuple[str, ...]] = [(chosen[0].source_id,)]
    predicate = episode.facts[target].predicate
    date = episode.facts[target].event_time[:10]
    request = f"{episode.entity.alias} {predicate} {date}"
    if family in {"E1", "E2", "E10", "E14"}:
        request = (
            f"Find the observed parking location for actor {episode.entity.alias} "
            f"at event date {date} in the captured parking message."
        )
    status, reason = "SUPPORTED", "SUFFICIENT"
    forbidden: list[str] = []
    canaries: list[str] = []
    projection = "CANONICAL_FALLBACK"
    knowledge = "2026-10-23T00:00:00+00:00"
    if family == "E3":
        request = f"Which complete requirement chain starts at {episode.entity.alias}?"
        chosen = list(all_sources)
        slots = [(s.source_id,) for s in chosen]
        alternatives = [tuple(s.source_id for s in chosen)]
    elif family == "E4":
        request = f"Which release is an observed cause for {episode.entity.alias}?"
        chosen = [all_sources[0]]
        slots = [(chosen[0].source_id,)]
        alternatives = [slots[0]]
        for index in range(12):
            hub = replace(
                episode.facts[1],
                hidden_id=opaque("hidden", episode.entity.cluster_id, "hub", index),
                actor="popular-service",
                predicate="mentions",
                value=f"release-{index}",
            )
            all_sources.append(render(hub, seed=world.seed, namespace=namespace))
    elif family == "E5":
        request = f"What verified correction applies to {episode.entity.alias} parking {date}?"
        chosen = list(all_sources)
        slots = [(s.source_id,) for s in chosen]
        alternatives = [tuple(s.source_id for s in chosen)]
    elif family == "E6":
        request = f"What zone do the authorities approve for {episode.entity.alias} at {date}?"
        chosen = [all_sources[0]]
        all_sources = [all_sources[0]] if variant == "positive" else all_sources
        alternatives, slots = [(chosen[0].source_id,)], [(chosen[0].source_id,)]
    elif family == "E8":
        chosen = [all_sources[0]]
        request = f"What exact invoice amount applies to {episode.entity.alias}?"
        alternatives, slots = [(chosen[0].source_id,)], [(chosen[0].source_id,)]
    elif family == "E9":
        request = f"Which release and rollback pair is recorded for {episode.entity.alias}?"
        chosen = list(all_sources)
        slots = [(s.source_id,) for s in chosen]
        alternatives = [tuple(s.source_id for s in chosen)]
    elif family == "E10":
        hidden = replace(
            episode.facts[target],
            hidden_id=opaque("hidden", episode.entity.cluster_id, "forbidden"),
            value=opaque("PRIVATE", episode.entity.cluster_id),
        )
        private = render(hidden, seed=world.seed, namespace=namespace, principals=("other",))
        all_sources.append(private)
        forbidden, canaries = [private.source_id], [hidden.value]
    elif family == "E11":
        chosen = [all_sources[0]]
        request = f"Where was {episode.entity.alias} observed parking on 2026-10-19?"
        alternatives, slots = [(chosen[0].source_id,)], [(chosen[0].source_id,)]
    elif family == "E12":
        projection = "CANONICAL_FALLBACK"
        request = f"What exact canonical parking observation covers {episode.entity.alias} {date}?"
    elif family == "E13":
        chosen = [all_sources[5], all_sources[6]]
        request = (
            f"What rare latency exception and subsequent reversal concern {episode.entity.alias}?"
        )
        slots = [(s.source_id,) for s in chosen]
        alternatives = [tuple(s.source_id for s in chosen)]
    # Valid alternate evidence is rendered from the same captured fact, not a new origin.
    if len(chosen) == 1 and family not in {"E10", "E6"}:
        index = next(i for i, source in enumerate(all_sources) if source == chosen[0])
        alternate = render(
            episode.facts[index], seed=world.seed, namespace=namespace, copy=1, language="id"
        )
        all_sources.append(alternate)
        alternatives.append((alternate.source_id,))
        slots[0] = (*slots[0], alternate.source_id)
    if variant == "ambiguous":
        if family in {"E5", "E11"}:
            base = episode.facts[1] if family == "E5" else episode.facts[0]
            other = replace(
                base,
                hidden_id=opaque("hidden", base.hidden_id, "competing"),
                value="ZoneC",
                event_time=base.event_time if family == "E5" else "2026-10-20T09:00:00+00:00",
            )
            all_sources.append(render(other, seed=world.seed, namespace=namespace))
        status, reason = "NOT_ESTABLISHED", "AMBIGUOUS"
        request = f"What is the applicable record for {episode.entity.alias}?"
        alternatives = []
        if family in {"E5", "E6"}:
            status, reason = "CONFLICT", "CONTRADICTORY_SOURCES"
            competing = [all_sources[1], all_sources[-1]] if family == "E5" else all_sources[:2]
            slots = [(s.source_id,) for s in competing]
            alternatives = [tuple(s.source_id for s in competing)]
        if family == "E7":
            reason = "MISSING_TIME_BASIS"
        if family == "E12":
            status, reason, projection = "VERIFICATION_UNAVAILABLE", "MIXED_VERSIONS", "UNAVAILABLE"
    elif variant == "missing":
        status, reason = "NOT_ESTABLISHED", "MISSING_SUPPORT"
        missing_ids = set(slots[-1])
        all_sources = [s for s in all_sources if s.source_id not in missing_ids]
        if family == "E6":
            all_sources = []
        alternatives = []
        if family == "E7":
            # Same source exists, but knowledge-at precedes its late recording.
            all_sources = [render(episode.facts[0], seed=world.seed, namespace=namespace)]
            knowledge = "2026-10-20T00:00:00+00:00"
        if family == "E4":
            reason = "HYPOTHESIS_NOT_VERIFIED_CAUSE"
        if family == "E12":
            status, reason, projection = (
                "VERIFICATION_UNAVAILABLE",
                "REQUIRED_CAPABILITY",
                "UNAVAILABLE",
            )
    if language == "id":
        actor = episode.entity.alias
        prompts = {
            "E1": f"Di mana {actor} parkir pada {date}?",
            "E2": f"Temukan lokasi parkir yang diamati untuk {actor} pada {date}.",
            "E3": f"Apa rantai ketergantungan lengkap yang dimulai dari {actor}?",
            "E4": f"Rilis mana yang diamati sebagai penyebab gangguan {actor}?",
            "E5": f"Koreksi parkir terverifikasi mana berlaku untuk {actor} pada {date}?",
            "E6": f"Zona mana disetujui sumber berwenang untuk {actor} pada {date}?",
            "E7": f"Apa catatan parkir {actor} pada tanggal kejadian {date}?",
            "E8": f"Berapa nilai tagihan tepat untuk {actor}?",
            "E9": f"Pasangan rilis dan rollback mana tercatat untuk {actor}?",
            "E10": f"Di mana {actor} parkir pada {date}?",
            "E11": f"Di mana {actor} diamati parkir pada 2026-10-19?",
            "E12": f"Apa pengamatan parkir kanonik untuk {actor} pada {date}?",
            "E13": f"Apa pengecualian latensi langka dan pembalikannya untuk {actor}?",
            "E14": f"Di mana {actor} parkir pada {date}?",
        }
        request = (
            f"Catatan mana yang berlaku untuk {actor}?"
            if variant == "ambiguous"
            else prompts[family]
        )
    elif language == "mixed":
        request = "Tolong recall bukti: " + request
    requested_fraction = missing_fraction
    if missing_fraction:
        # Preserve the identity/date anchors, mask only other available cue tokens.
        words = request.split()
        count = min(int(len(words) * missing_fraction), max(0, len(words) - 2))
        for index in range(count):
            if episode.entity.alias not in words[index] and date not in words[index]:
                words[index] = "[masked]"
        request = " ".join(words)
        missing_fraction = words.count("[masked]") / len(words)
    qid = opaque("query", "public-v1", world.seed, namespace, variant, language, requested_fraction)
    required = (
        ("source_read", "graph") if family == "E12" and variant == "missing" else ("source_read",)
    )
    query = Query(
        qid,
        request,
        namespace,
        "reader",
        "2026-10-23T00:00:00+00:00",
        knowledge,
        "UTC",
        10,
        2000,
        required,
        projection,
    )
    accessible = tuple(
        s
        for s in all_sources
        if query.principal in s.allowed_principals
        and parse_instant(s.observation.recorded_at) <= parse_instant(query.knowledge_at)
    )
    gold = Gold(
        qid,
        family,
        episode.entity.cluster_id,
        variant,
        language,
        status,
        reason,
        tuple(alternatives),
        tuple(slots),
        tuple(sorted({s.event_id for s in chosen})),
        tuple(forbidden),
        tuple(canaries),
        missing_fraction,
        projection,
    )
    return Case(query, accessible, gold)


def scenarios(world: World) -> tuple[Case, ...]:
    result = []
    for episode in world.episodes:
        for variant in ("positive", "ambiguous", "missing"):
            for language in ("en", "id", "mixed"):
                result.append(_case(world, episode, variant, language))
        if episode.family == "E2":
            for fraction in (0.1, 0.3, 0.5, 0.7):
                result.append(_case(world, episode, "positive", "en", fraction))
        if episode.family == "E3":
            base = _case(world, episode, "positive", "en")
            for hops in (1, 2, 3):
                qid = opaque("query", base.query.query_id, "prefix", hops)
                query = replace(
                    base.query,
                    query_id=qid,
                    text=f"Give the first {hops} requirement links from {episode.entity.alias}.",
                )
                selected = base.sources[:hops]
                gold = replace(
                    base.gold,
                    query_id=qid,
                    slots=tuple((s.source_id,) for s in selected),
                    acceptable_sets=(tuple(s.source_id for s in selected),),
                    relevant_events=tuple(sorted({s.event_id for s in selected})),
                )
                result.append(Case(query, base.sources, gold))
            # Same complete-chain question, but the final captured relation is only co-occurrence.
            mention = replace(
                episode.facts[-1],
                predicate="mentions",
                hidden_id=opaque("hidden", episode.facts[-1].hidden_id, "mention"),
            )
            qid = opaque("query", base.query.query_id, "mention-twin")
            sources = (
                *base.sources[:-1],
                render(mention, seed=world.seed, namespace=base.query.namespace),
            )
            gold = replace(
                base.gold,
                query_id=qid,
                variant="missing",
                expected_status="NOT_ESTABLISHED",
                reason="MENTION_IS_NOT_REQUIREMENT",
                acceptable_sets=(),
            )
            result.append(Case(replace(base.query, query_id=qid), sources, gold))
        if episode.family == "E9":
            base = _case(world, episode, "positive", "en")
            qid = opaque("query", base.query.query_id, "qualified-partial")
            source = base.sources[0]
            gold = replace(
                base.gold,
                query_id=qid,
                expected_status="PARTIALLY_SUPPORTED",
                reason="MISSING_ROLLBACK",
                acceptable_sets=(),
                partial_sets=((source.source_id,),),
                missing_fields=("rollback",),
            )
            result.append(Case(replace(base.query, query_id=qid), (source,), gold))
    require(len({c.query.query_id for c in result}) == len(result), "DUPLICATE_QUERY")
    return tuple(result)


def gold_payload(case: Case) -> dict[str, object]:
    # Optional new annotations are absent when inapplicable, preserving reviewed bindings.
    result = asdict(case.gold)
    for name in ("partial_sets", "missing_fields"):
        if not result[name]:
            result.pop(name)
    return result
