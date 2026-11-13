"""P06-T19: NOISY_V1 is labelled, deterministic, fact-preserving and free of generative code."""

import ast
import json
import re
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from test_multihop_fixtures import first, resolved_graph, walk

from benchmark.adapters.baseline import SCHEMA_CUES
from benchmark.fixtures import noisy_render
from benchmark.fixtures.entities import identity_plan
from benchmark.fixtures.multihop import MultiHopCase, multihop_cases
from benchmark.fixtures.noisy_render import (
    ABBREVIATIONS,
    CLAUSES,
    DISTRACTORS,
    LANGUAGES,
    PRODUCER,
    STRATUM,
    noisy_case,
    noisy_id,
    noisy_query_text,
    noisy_source,
    require_labelled,
    require_unlabelled,
)
from benchmark.fixtures.publication import publish
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical, digest

SEED = 47
NOISY_DIGEST = "f5faa61f13108bbeab33d2d1841e5eee95a165f6ec9a5fdc7eb55ac9a4763f3d"


@lru_cache(maxsize=1)
def templates() -> tuple[MultiHopCase, ...]:
    return multihop_cases(SEED, "pilot")


@lru_cache(maxsize=4)
def noisy(language: str, seed: int = SEED) -> tuple[MultiHopCase, ...]:
    return tuple(noisy_case(t, seed, language) for t in templates())


def message(source) -> str:
    return str(json.loads(source.text)["message"])


def corpus_digest(seed: int = SEED) -> str:
    return digest(
        canonical(
            [publish(m.case).payload() for language in LANGUAGES for m in noisy(language, seed)]
        ).encode()
    )


def test_same_seed_reproduces_identical_bytes_and_another_seed_does_not():
    assert corpus_digest() == corpus_digest() == NOISY_DIGEST
    assert corpus_digest(SEED + 1) != NOISY_DIGEST


def test_structured_facts_and_identifiers_survive_every_rendering():
    for language in LANGUAGES:
        for template, rendered in zip(templates(), noisy(language), strict=True):
            by_id = {s.source_id: s for s in template.case.sources}
            kept = {noisy_id(SEED, s.namespace, s.source_id, language): s for s in by_id.values()}
            assert set(kept) == {s.source_id for s in rendered.case.sources}
            for source in rendered.case.sources:
                original = kept[source.source_id]
                a, b = original.observation, source.observation
                facts = ("actor", "predicate", "value", "event_time", "recorded_at", "origin")
                assert all(getattr(a, f) == getattr(b, f) for f in facts)
                text = message(source)
                assert b.actor in text and b.value in text  # protected tokens are verbatim
                statement = noisy_render.statement_of(original)
                assert not statement or text.count(statement) == 1
                assert source.event_id == original.event_id
            template_plan = identity_plan(template.case.sources)
            plan = identity_plan(rendered.case.sources)
            assert sorted(k for _s, k in plan.keys) == sorted(k for _s, k in template_plan.keys)
            assert sorted(a for _s, a in plan.aliases) == sorted(
                a for _s, a in template_plan.aliases
            )


def filler_matches(word: str, template_word: str) -> bool:
    core = word.rstrip(".,:;")
    original = template_word.rstrip(".,:;")
    return (
        core == original
        or sorted(core) == sorted(original)  # one adjacent-letter typo
        or (original in ABBREVIATIONS and word.startswith(ABBREVIATIONS[original]))
    )


def recoverable(text: str, actor: str, predicate: str, value: str) -> bool:
    """A reader-equivalent check: some clause of the right predicate, in some language, fits."""
    for options in CLAUSES[predicate].values():
        for template in options:
            parts = re.split(r"(\{a\}|\{v\})", template)
            pattern, words = "", []
            for part in parts:
                if part == "{a}":
                    pattern += re.escape(actor)
                elif part == "{v}":
                    pattern += re.escape(value)
                else:
                    for token in re.split(r"( )", part):
                        if token == " ":
                            pattern += " "
                        elif token:
                            words.append(token)
                            pattern += r"(\S+)"
            found = re.search(pattern, text)
            if found and all(
                filler_matches(g, w) for g, w in zip(found.groups(), words, strict=True)
            ):
                return True
    return False


def test_every_message_keeps_a_recoverable_fact_clause():
    count = 0
    for language in LANGUAGES:
        for m in noisy(language):
            for source in m.case.sources + m.graph.private_sources:
                o = source.observation
                assert recoverable(message(source), o.actor, o.predicate, o.value), message(source)
                count += 1
    assert count > 3000
    # Control: a clause with the value replaced by another token is not recoverable.
    source = noisy("en")[0].case.sources[0]
    o = source.observation
    assert not recoverable(message(source), o.actor, o.predicate, "svc.0000000000")


def test_noise_is_actually_applied_and_languages_differ():
    en, ind, mixed = (noisy(language) for language in LANGUAGES)
    texts = {
        language: [message(s) for m in noisy(language) for s in m.case.sources]
        for language in LANGUAGES
    }
    template_texts = [message(s) for t in templates() for s in t.case.sources]
    assert sum(a != b for a, b in zip(texts["en"], template_texts, strict=True)) > 0.9 * len(
        template_texts
    )
    joined = " ".join(texts["en"])
    assert any(a in joined for a in ABBREVIATIONS.values())  # abbreviations
    assert any(d.split()[0] in joined for d in DISTRACTORS["en"])  # distractor clauses
    assert any(not t.endswith("]") and "[key:" in t and not t.startswith("[") for t in texts["en"])
    vocabulary = {
        w.strip(".,:;")
        for group in (*CLAUSES.values(), DISTRACTORS)
        for options in group.values()
        for sentence in options
        for w in sentence.split()
    }
    typos = [
        w
        for w in (w.strip(".,:;") for w in joined.split())
        if w.isalpha() and w not in vocabulary and any(sorted(w) == sorted(v) for v in vocabulary)
    ]
    assert typos  # adjacent-letter typos in filler words
    assert any("membutuhkan" in t or "bergantung" in t for t in texts["id"])
    assert not any("depends on" in t or "is required by" in t for t in texts["id"])
    assert any("membutuhkan" in t for t in texts["mixed"]) and any(
        "depends on" in t for t in texts["mixed"]
    )
    assert texts["en"] != texts["id"] != texts["mixed"]
    assert len(en) == len(ind) == len(mixed) == len(templates())


def test_the_stratum_is_labelled_and_unlabelled_noisy_input_is_rejected():
    for language in LANGUAGES:
        for m in noisy(language):
            public = publish(m.case)
            require_labelled(public)
            assert {s.observation.producer for s in public.sources} == {PRODUCER}
            assert m.case.gold.language == language
    template_public = publish(templates()[0].case)
    require_unlabelled(template_public)
    with pytest.raises(NornError, match="UNLABELLED_NOISY_RENDERING"):
        require_labelled(template_public)
    rendered = publish(noisy("en")[0].case)
    stripped = replace(
        rendered.sources[0],
        observation=replace(rendered.sources[0].observation, producer="synthetic-recorder-v1"),
    )
    with pytest.raises(NornError, match="UNLABELLED_NOISY_RENDERING"):
        require_labelled(replace(rendered, sources=(stripped, *rendered.sources[1:])))
    with pytest.raises(NornError, match="TEMPLATE_INPUT_LABELLED_NOISY"):
        require_unlabelled(rendered)
    assert STRATUM == "NOISY_V1"
    assert noisy("en")[0].case.query.query_id != templates()[0].case.query.query_id


def test_noise_leaks_no_label_and_distractors_carry_no_protected_content():
    cues = {c for cues_, fields in SCHEMA_CUES for c in (*cues_, *fields)}
    for sentences in DISTRACTORS.values():
        for sentence in sentences:
            lowered = sentence.casefold()
            assert not re.search(r"\d|svc\.|\[|key", lowered), sentence
            assert not any(c in lowered for c in cues), sentence
    for language in LANGUAGES:
        for m in noisy(language):
            public = publish(m.case, ("__GOLD_CANARY__",))
            encoded = canonical(public.payload())
            assert re.search(r"\bM[1-6]\b|hidden_|decoy|bait|distractor", encoded) is None
            for private in m.graph.private_sources:
                assert private.source_id not in encoded
            for canary in m.case.gold.forbidden_canaries:
                assert canary not in encoded


def test_gold_is_remapped_to_the_noisy_sources_without_changing_what_it_says():
    for language in LANGUAGES:
        for template, rendered in zip(templates(), noisy(language), strict=True):
            old, new = template.case.gold, rendered.case.gold
            assert (old.family, old.variant, old.expected_status, old.reason) == (
                new.family,
                new.variant,
                new.expected_status,
                new.reason,
            )
            assert old.relevant_events == new.relevant_events
            published = {s.source_id for s in rendered.case.sources}
            if new.expected_status == "SUPPORTED":
                assert {i for slot in new.slots for i in slot} <= published
            assert not set(new.forbidden_sources) & published
            assert len(new.forbidden_sources) == len(old.forbidden_sources)
            assert {s.source_id for s in rendered.graph.private_sources} == set(
                new.forbidden_sources
            )
            assert set(rendered.graph.decoy_sources) <= published
            assert new.query_id != old.query_id and new.language == language


def test_question_variants_keep_names_keys_and_dates_verbatim():
    for template in templates():
        text = template.case.query.text
        names = re.findall(r"Sari-\w+|svc\.\w+|\d{4}-\d{2}-\d{2}", text)
        for language in LANGUAGES:
            variant = noisy_query_text(text, language)
            assert all(n in variant for n in names)
        assert noisy_query_text(text, "en") == text
        assert noisy_query_text(text, "mixed").startswith("Tolong recall bukti: ")
    with pytest.raises(NornError, match="UNSUPPORTED_QUESTION_TEMPLATE"):
        noisy_query_text("Tell me everything", "id")
    with pytest.raises(NornError, match="UNSUPPORTED_NOISY_LANGUAGE"):
        noisy_source(templates()[0].case.sources[0], SEED, "fr")


def test_noise_does_not_break_the_graph_the_loader_rebuilds(tmp_path):
    for family, hops in (("M1", 2), ("M3", 2)):
        template = first(family)
        rendered = noisy_case(template, SEED, "mixed")
        edges, keyed, _s, find = resolved_graph(tmp_path / family, publish(rendered.case))
        seed_key = next(k for h, _n, k in rendered.graph.nodes if h == rendered.graph.seed_node)
        assert walk(edges, find(keyed[seed_key])) == hops
    template = first("M2")
    rendered = noisy_case(template, SEED, "id")
    public = publish(rendered.case)
    edges, keyed, summary, find = resolved_graph(tmp_path / "M2", public)
    seed_key = next(k for h, _n, k in rendered.graph.nodes if h == rendered.graph.seed_node)
    assert summary["alias_links"] == 1 and summary["unresolved"] == []
    assert walk(edges, find(keyed[seed_key])) == len(rendered.case.gold.slots) - 1


def test_the_module_imports_no_generative_model_or_network_code():
    tree = ast.parse(Path(noisy_render.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    allowed = {"json", "re", "dataclasses", "norn.contracts.errors", "norn.contracts.identity"}
    assert all(
        m in allowed or m.startswith("benchmark.fixtures.") or m == "benchmark.adapters.contracts"
        for m in imported
    ), imported
    assert {"benchmark.fixtures.multihop", "json"} <= imported  # control: imports were parsed
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "random" not in names and "socket" not in names
