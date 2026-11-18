"""Channel votes for graph seeds, built on the conventional recall owners (P06-T03).

The eligible corpus, the BM25 ranking and the dense T0 cosine come unchanged from
``norn.retrieval`` (so ACL, tombstone, time and snapshot filters run before any ranking); this
module only turns their hits into entity votes and hands them to ``norn.graph.seeds``, which
checks every anchor again and builds the vector. It reads no graph, edge or gold label.

The exact channel has two cues: the existing request fields (``subject``, ``entity_id``,
``atom_id``, ``event_id``, event window) and governed keys named in the query text. A key matches
only a registered key exactly, never by similarity; a name never seeds through the text, so a
name that matches nothing, or a key nobody registered, seeds nothing. An empty exact channel is
reported, with its reason, as ``EXACT_CHANNEL_DEGRADED``.
"""

from threading import Event
from typing import TYPE_CHECKING

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.contracts.time import stamp
from norn.embedding.assets import fingerprint
from norn.graph.seeds import (
    AMBIGUOUS_NAME,
    CONVENTIONAL,
    ChannelResult,
    Seed,
    SeedBasis,
    Vote,
    anchor_entity,
    construct_seed,
    eligible_entity,
)
from norn.projection import local
from norn.retrieval import dense, exact, lexical
from norn.retrieval.contracts import EligibleCorpus, Hit, RecallRequest

if TYPE_CHECKING:
    from norn.integration.engine import Engine

EXACT_VERSION = "exact-canonical-key-v1"
PUNCTUATION = ".,:;!?()[]{}\"'"
MAX_KEY_TOKENS = 256


def _votes(engine: Engine, hits: tuple[Hit, ...]) -> tuple[Vote, ...]:
    return tuple(
        Vote(anchor_entity(engine.registry, h.record.atom_id), (h.record.atom_id,)) for h in hits
    )


def key_entities(engine: Engine, text: str, basis: SeedBasis) -> tuple[str, ...]:
    """Readable entities whose registered governed key is a token of ``text``, exactly."""
    tokens = sorted({t.strip(PUNCTUATION) for t in text.split()} - {""})[:MAX_KEY_TOKENS]
    if not tokens:
        return ()
    rows = engine.db.connection.execute(
        "SELECT id FROM entities WHERE ns=? AND external_key IN ("
        + ",".join("?" for _ in tokens)
        + ") ORDER BY id",
        (engine.access.ns, *tokens),
    ).fetchall()
    return tuple(str(r[0]) for r in rows if eligible_entity(engine.registry, basis, str(r[0])))


def exact_channel(
    engine: Engine, request: RecallRequest, corpus: EligibleCorpus, basis: SeedBasis
) -> ChannelResult:
    keyed = key_entities(engine, request.text, basis)
    cue = bool(
        request.event_id
        or request.atom_id
        or request.entity_id
        or request.subject
        or request.event_start
    )
    fields = exact.lookup(corpus, request)
    field_votes = _votes(engine, fields)
    flags: list[str] = []
    if request.subject and len({v.entity_id for v in field_votes}) > 1:
        flags.append(AMBIGUOUS_NAME)  # one name, several entities: all seeded, none preferred
    over = cue and not fields and len(corpus.records) > request.candidate_limit
    if over:
        flags.append("EXACT_FIELD_CUE_OVER_LIMIT")
    votes = tuple(Vote(e) for e in keyed) + field_votes
    if votes:
        reason = None
    elif over:
        reason = "OVER_CANDIDATE_LIMIT"
    else:
        reason = "NO_MATCH" if cue else "NO_EXACT_CUE"
    return ChannelResult("exact", EXACT_VERSION, votes, reason, tuple(flags))


def dense_channel(
    engine: Engine, request: RecallRequest, corpus: EligibleCorpus, budget: QueryBudget
) -> ChannelResult:
    models = engine.local_models
    if models is None:
        raise NornError("LOCAL_MODELS_NOT_ENABLED")
    _snapshot_id, index = local.load(engine, corpus, ("dense",), budget)
    query = dense.encode((request.text,), models, budget, query=True)[0]
    vectors = {k: tuple(v["vector"]) for k, v in index["dense"].items()}
    nearest = dense.search(corpus, query, vectors, request.candidate_limit, budget.checkpoint)
    return ChannelResult(
        "dense", fingerprint("encoder"), _votes(engine, nearest), None if nearest else "NO_MATCH"
    )


def build_seed(
    engine: Engine,
    request: RecallRequest,
    channels: tuple[str, ...] = CONVENTIONAL,
    *,
    cancelled: Event | None = None,
) -> Seed:
    """The seed of one query over the named channels, at the request's snapshot and clock."""
    require(
        len(set(channels)) == len(channels) and set(channels) <= set(CONVENTIONAL),
        "SEED_CHANNEL_NOT_GATHERED",
    )
    budget = QueryBudget(request.deadline_ms, cancelled if cancelled is not None else Event())
    try:
        with budget.sqlite_guard(engine.db.connection):
            epoch = engine.access.check("READ")
            corpus = exact.eligible(engine, request, budget.checkpoint)
            basis = SeedBasis(corpus.snapshot, stamp(request.clock.knowledge_at), epoch)
            flags = () if corpus.complete else ("ELIGIBLE_CORPUS_INCOMPLETE",)
            results: list[ChannelResult] = []
            if "exact" in channels:
                results.append(exact_channel(engine, request, corpus, basis))
            if "lexical" in channels:
                hits = lexical.search(
                    corpus, request.text, request.candidate_limit, None, budget.checkpoint
                )
                results.append(
                    ChannelResult(
                        "lexical",
                        lexical.REVISION,
                        _votes(engine, hits),
                        None if hits else "NO_MATCH",
                    )
                )
            if "dense" in channels:
                results.append(dense_channel(engine, request, corpus, budget))
            results = [
                ChannelResult(r.name, r.version, r.votes, r.reason, (*r.flags, *flags))
                for r in results
            ]
            return construct_seed(engine.registry, results, basis)
    except BaseException:
        engine.close_models()
        raise
