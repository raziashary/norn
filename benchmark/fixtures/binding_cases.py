"""Development-only disjoint-instance roles, fixed before wording and supervised labels."""

from dataclasses import replace

from benchmark.fixtures.entities import opaque
from benchmark.fixtures.partitions import Partition, partition
from benchmark.fixtures.render import render
from benchmark.fixtures.scenarios import Case, Gold, scenarios
from benchmark.fixtures.world import build_world
from norn.contracts.errors import require

ROLE_INDICES = {"train": (0, 1), "tune": (2,), "evaluation": (3,)}


def cases(role: str, *, seed: int = 20261021, smoke: bool = False) -> tuple[Case, ...]:
    require(role in ROLE_INDICES, "BINDING_ROLE")
    all_parts = partition(seed, "development", 4)
    selected = tuple(
        pair for index, pair in enumerate(all_parts.entities) if index % 4 in ROLE_INDICES[role]
    )
    world = build_world(seed, Partition("development", selected))
    result = list(scenarios(world))
    for episode in world.episodes:
        if episode.family != "E2":
            continue
        ns = "synthetic/" + opaque("scope", seed, episode.entity.cluster_id)[6:22] + "/local"
        captures = []
        for index, outcome in enumerate(("exit0", "timeout")):
            at = f"2026-10-{19 + index}T09:00:00+00:00"
            observed = (
                f"step=0;tool=restart;result={outcome};at={at}|"
                f"step=1;tool=probe;result={outcome};at={at}"
            )
            fact = replace(
                episode.facts[0],
                hidden_id=opaque("hidden", episode.entity.cluster_id, "action", index),
                predicate="observed_action",
                value=observed,
                origin="DIRECT_OBSERVATION",
                event_time=at,
            )
            captures.append(render(fact, seed=seed, namespace=ns))
        base = next(c for c in result if c.gold.cluster == episode.entity.cluster_id)
        for variant, wording, status, targets in (
            (
                "action-outcome",
                f"Which observed_action for {episode.entity.alias} returned exit0?",
                "SUPPORTED",
                ((captures[0].source_id,),),
            ),
            (
                "action-partial",
                f"Recall {episode.entity.alias} restart exit0 observed_action",
                "SUPPORTED",
                ((captures[0].source_id,),),
            ),
            (
                "action-ambiguous",
                f"Which observed_action concerns {episode.entity.alias}?",
                "NOT_ESTABLISHED",
                (),
            ),
        ):
            qid = opaque("query", base.query.query_id, variant)
            query = replace(base.query, query_id=qid, text=wording)
            gold = Gold(
                qid,
                "E2",
                episode.entity.cluster_id,
                variant,
                "en",
                status,
                "AMBIGUOUS" if not targets else "SUFFICIENT",
                targets,
                tuple((s.source_id,) for s in captures) if not targets else targets,
                (captures[0].event_id,),
                (),
                (),
                0.5 if "partial" in variant else 0.0,
                "CANONICAL_FALLBACK",
            )
            result.append(Case(query, tuple(captures), gold))
    if smoke:
        # All categories remain represented; smoke is mechanical only.
        action_case = next(c for c in result if c.gold.variant == "action-outcome")
        result = [
            next(c for c in result if c.gold.family == family)
            for family in sorted({c.gold.family for c in result})
        ]
        result.append(action_case)
    require(len({c.query.query_id for c in result}) == len(result), "DUPLICATE_QUERY")
    return tuple(result)
