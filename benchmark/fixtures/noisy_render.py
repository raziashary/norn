"""NOISY_V1: a labelled, seeded, deterministic rendering stratum over public-v2 cases (P06-T19).

The transform keeps every structured fact (the authenticated ``capture`` is unchanged except for
the stratum label in ``producer``) and rewrites only the natural-language ``message``: paraphrased
predicates, filler-word typos and abbreviations, clause reordering, distractor clauses and the
en, id and mixed wording. Identifiers are protected and always verbatim: display names, values,
and the ``[key:..]`` / ``[alias:..]`` statements that carry shared identity (T17).

No model, network or generative renderer is used or importable here; all choices come from
digests of (seed, source id, slot), never from ``random``.
"""

import json
import re
from dataclasses import asdict, replace

from benchmark.adapters.contracts import PublicInput, PublishedSource, Query
from benchmark.fixtures.entities import ALIAS_STATEMENT, KEY_STATEMENT, opaque
from benchmark.fixtures.multihop import GraphGold, MultiHopCase
from benchmark.fixtures.observations import Observation
from benchmark.fixtures.scenarios import Case, Gold
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest

STRATUM = "NOISY_V1"
PRODUCER = "synthetic-recorder-noisy-v1"
SOURCE_TAG = "publication-v2-noisy"
LANGUAGES = ("en", "id", "mixed")

# Fact clauses per predicate and language; {a} is the actor and {v} the value, both protected.
CLAUSES: dict[str, dict[str, tuple[str, ...]]] = {
    "requires": {
        "en": (
            "{a} depends on {v}.",
            "{a} needs {v} in place.",
            "{v} is required by {a}.",
            "{a} cannot run without {v}.",
        ),
        "id": (
            "{a} bergantung pada {v}.",
            "{a} membutuhkan {v}.",
            "{v} dibutuhkan oleh {a}.",
        ),
    },
    "registered": {
        "en": ("{a} is registered and {v}.", "{a} was registered, status {v}."),
        "id": ("{a} sudah terdaftar dan {v}.", "{a} terdaftar, status {v}."),
    },
    "mentions": {
        "en": ("{a} mentioned {v}.", "Note from {a}: see {v}."),
        "id": ("{a} menyebut {v}.", "Catatan dari {a}: lihat {v}."),
    },
    "parked_in": {
        "en": ("{a} parked in {v}.", "{v} is where {a} parked."),
        "id": ("{a} parkir di {v}.", "{v} tempat {a} parkir."),
    },
    "observed": {
        "en": ("{a} was observed {v}.", "Observed: {a} {v}."),
        "id": ("{a} terlihat {v}.", "Teramati: {a} {v}."),
    },
}
DISTRACTORS = {
    "en": (
        "Reminder: the maintenance window moved to Friday.",
        "The desk closed an unrelated ticket today.",
        "Weather was mild during the shift.",
        "The coffee machine on the second floor is broken again.",
    ),
    "id": (
        "Pengingat: jadwal pemeliharaan dipindah ke hari Jumat.",
        "Meja layanan menutup tiket lain hari ini.",
        "Cuaca cukup sejuk selama shift.",
        "Mesin kopi di lantai dua rusak lagi.",
    ),
}
ABBREVIATIONS = {
    "depends": "dep.",
    "required": "reqd",
    "registered": "reg.",
    "observed": "obs.",
    "mentioned": "mentd",
    "Reminder": "Rmdr",
}
LAYOUTS = 4
PLACEHOLDER = re.compile(r"(\{a\}|\{v\})")


def pick(seed: int, source_id: str, slot: str, count: int, index: int = 0) -> int:
    require(count > 0)
    return int(opaque("noise", seed, source_id, slot, index)[-8:], 16) % count


def _typo(word: str, choice: int) -> str:
    """Swap two adjacent inner letters; leaves short words and identifiers alone."""
    if len(word) < 5 or not word.isalpha():
        return word
    position = 1 + choice % (len(word) - 3)
    return word[:position] + word[position + 1] + word[position] + word[position + 2 :]


def _noisy_filler(text: str, seed: int, source_id: str, slot: str) -> str:
    words = []
    for index, word in enumerate(text.split(" ")):
        core = word.rstrip(".,:;")
        tail = word[len(core) :]
        roll = pick(seed, source_id, f"{slot}-filler", 8, index)
        if core in ABBREVIATIONS and roll < 3:
            core = ABBREVIATIONS[core]
        elif roll == 3:
            core = _typo(core, pick(seed, source_id, f"{slot}-typo", 97, index))
        words.append(core + tail)
    return " ".join(words)


def _clause(obs: Observation, language: str, seed: int, source_id: str) -> str:
    require(obs.predicate in CLAUSES, "UNSUPPORTED_NOISY_PREDICATE")
    lang = language
    if language == "mixed":
        lang = ("en", "id")[pick(seed, source_id, "mixed-lang", 2)]
    options = CLAUSES[obs.predicate][lang]
    template = options[pick(seed, source_id, "clause", len(options))]
    parts = []
    for index, part in enumerate(PLACEHOLDER.split(template)):
        if part == "{a}":
            parts.append(obs.actor)
        elif part == "{v}":
            parts.append(obs.value)
        else:
            parts.append(_noisy_filler(part, seed, source_id, f"p{index}"))
    return "".join(parts)


def _distractors(language: str, seed: int, source_id: str) -> list[str]:
    result = []
    for index in range(pick(seed, source_id, "distractor-count", 3)):
        lang = language
        if language == "mixed":
            lang = ("en", "id")[pick(seed, source_id, "distractor-lang", 2, index)]
        pool = DISTRACTORS[lang]
        # Consecutive offsets from one start keep the distractors of a source distinct.
        sentence = pool[(pick(seed, source_id, "distractor", len(pool)) + index) % len(pool)]
        result.append(_noisy_filler(sentence, seed, source_id, f"d{index}"))
    return result


def statement_of(source: PublishedSource) -> str:
    """The single identity statement of a template source, verbatim, or the empty string."""
    message = _message(source)
    found = [m.group(0) for m in KEY_STATEMENT.finditer(message)]
    found += [m.group(0) for m in ALIAS_STATEMENT.finditer(message)]
    require(len(found) <= 1, "AMBIGUOUS_IDENTITY_STATEMENT")
    return found[0] if found else ""


def _message(source: PublishedSource) -> str:
    return str(json.loads(source.text)["message"])


def noisy_id(seed: int, namespace: str, source_id: str, language: str) -> str:
    """Stable id of a source's noisy rendering, also for sources a variant leaves unpublished."""
    return opaque("source", SOURCE_TAG, seed, namespace, source_id, language)


def noisy_source(source: PublishedSource, seed: int, language: str) -> PublishedSource:
    require(language in LANGUAGES, "UNSUPPORTED_NOISY_LANGUAGE")
    obs = source.observation
    key = noisy_id(seed, source.namespace, source.source_id, language)
    layout = pick(seed, source.source_id, "layout", LAYOUTS)
    fact = _clause(obs, language, seed, source.source_id)
    statement = statement_of(source)
    extra = _distractors(language, seed, source.source_id)
    if language == "mixed" and pick(seed, source.source_id, "interjection", 3) == 0:
        fact = "btw, " + fact
    first, rest = (extra[0], extra[1:]) if extra else ("", [])
    order = {
        0: [fact, statement, *extra],
        1: [statement, fact, *extra],
        2: [first, fact, statement, *rest],
        3: [fact, first, statement, *rest],
    }[layout]
    message = " ".join(part for part in order if part)
    labelled = replace(obs, producer=PRODUCER)
    text = canonical({"capture": asdict(labelled), "message": message})
    return replace(
        source,
        source_id=key,
        atom_id=opaque("atom", key),
        text=text,
        sha256=digest(text.encode()),
        observation=labelled,
    )


def label_of(source: PublishedSource) -> str | None:
    return STRATUM if source.observation.producer == PRODUCER else None


def require_labelled(public: PublicInput) -> None:
    """Every source of a noisy input carries the stratum label; an unlabelled one is rejected."""
    require(bool(public.sources), "NOISY_INPUT_EMPTY")
    require(all(label_of(s) == STRATUM for s in public.sources), "UNLABELLED_NOISY_RENDERING")


def require_unlabelled(public: PublicInput) -> None:
    """A template input must not carry the noisy label (keeps the strata distinguishable)."""
    require(all(label_of(s) is None for s in public.sources), "TEMPLATE_INPUT_LABELLED_NOISY")


_CHAIN = re.compile(r"^Which complete requirement chain starts at (\S+?)( \(key (\S+)\))?\?$")
_PARKING = re.compile(r"^Where was (\S+) observed parking on (\d{4}-\d{2}-\d{2})\?$")


def noisy_query_text(text: str, language: str) -> str:
    """Language variants of the template question; names, keys and dates stay verbatim."""
    require(language in LANGUAGES, "UNSUPPORTED_NOISY_LANGUAGE")
    if language == "en":
        return text
    chain, parking = _CHAIN.match(text), _PARKING.match(text)
    require(chain is not None or parking is not None, "UNSUPPORTED_QUESTION_TEMPLATE")
    if chain is not None:
        suffix = f" (kunci {chain.group(3)})" if chain.group(3) else ""
        indonesian = f"Rantai persyaratan lengkap mana yang dimulai dari {chain.group(1)}{suffix}?"
    else:
        assert parking is not None
        indonesian = f"Di mana {parking.group(1)} diamati parkir pada {parking.group(2)}?"
    return indonesian if language == "id" else "Tolong recall bukti: " + text


def noisy_case(template: MultiHopCase, seed: int, language: str) -> MultiHopCase:
    """The same facts and the same gold under NOISY_V1 wording, with remapped source ids."""
    namespace = template.case.query.namespace

    def remap(ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(noisy_id(seed, namespace, i, language) for i in ids)

    sources = tuple(noisy_source(s, seed, language) for s in template.case.sources)
    private = tuple(noisy_source(s, seed, language) for s in template.graph.private_sources)
    gold = template.case.gold
    qid = opaque("query", gold.query_id, STRATUM, language)
    query: Query = replace(
        template.case.query,
        query_id=qid,
        text=noisy_query_text(template.case.query.text, language),
    )
    new_gold = Gold(
        qid,
        gold.family,
        gold.cluster,
        gold.variant,
        language,
        gold.expected_status,
        gold.reason,
        tuple(remap(s) for s in gold.acceptable_sets),
        tuple(remap(slot) for slot in gold.slots),
        gold.relevant_events,
        remap(gold.forbidden_sources),
        gold.forbidden_canaries,
        gold.cue_missing_fraction,
        gold.projection_state,
    )
    graph = template.graph
    new_graph = GraphGold(
        qid,
        graph.family,
        graph.cluster,
        graph.variant,
        graph.nodes,
        tuple((a, b, rel, remap((s,))[0]) for a, b, rel, s in graph.edges),
        tuple((remap((s,))[0], name) for s, name in graph.identity_links),
        graph.seed_node,
        graph.hub_node,
        remap(graph.decoy_sources),
        private,
        graph.pool_size,
    )
    return MultiHopCase(Case(query, sources, new_gold), new_graph)


def noisy_cases(
    templates: tuple[MultiHopCase, ...], seed: int, language: str
) -> tuple[MultiHopCase, ...]:
    return tuple(noisy_case(t, seed, language) for t in templates)
