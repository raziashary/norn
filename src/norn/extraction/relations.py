"""Derived graph from stored sources: REQUIRES edges and speculative causal hypotheses (P06-T02).

Two derived tracks write governed edges (``norn.graph.adjacency.write_edge``) into the registry
of the store they read, each under its own producer revision so a reader can always tell them
apart:

* ``TEMPLATE_READBACK`` reads the canonical atom (predicate and value). For template renderings
  this is the zero-extraction-error control: the text and the stored fact are the same statement.
* ``NOISY_TEXT`` reads only the ``message`` of the stored source text and never the structured
  capture, with a small bilingual grammar tolerant of one adjacent-letter typo and of listed
  abbreviations. It is imperfect by design; what it misses is measured, not hidden.

Nothing here imports the benchmark, a gold graph or a similarity model, and no entity is ever
resolved by name: a clause endpoint is a registered governed key, or the stating source's own
entity (the keyed entity defined by the same span, else the atom's subject). An unknown key stays
unresolved. Speculation never becomes a requirement: a hedged requirement is reported and not
written, and a causal clause becomes ``HYPOTHESIZES_CAUSE`` with origin HYPOTHESIS between the
two events; this module never writes ``VERIFIED_CAUSE``.
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field

from norn.canonical.registry import Registry
from norn.canonical.sources import SourceSpan
from norn.contracts.errors import require
from norn.graph.adjacency import write_edge
from norn.graph.contracts import EdgeSpec, NodeRef

TRACK_READBACK = "TEMPLATE_READBACK"
TRACK_TEXT = "NOISY_TEXT"
REVISIONS = {TRACK_READBACK: "relations-readback-v1", TRACK_TEXT: "relations-text-v1"}
PUNCTUATION = ".,:;!?()"

# Statement markers that carry governed identity are not relation text.
_STATEMENT = re.compile(r"\[(?:key|alias):[^\]]*\]")
# Identifier-shaped tokens: a hyphenated display name or a dotted governed key.
_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9]*[-.][A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$")

REQUIRE_WORDS = frozenset(
    "depend depends needs need requires require required needed bergantung membutuhkan butuh "
    "dibutuhkan".split()
)
REQUIRE_ABBREVIATIONS = frozenset({"dep", "reqd", "req"})
PASSIVE_WORDS = frozenset({"required", "needed", "dibutuhkan", "reqd"})
BY_WORDS = frozenset({"by", "oleh"})
CAUSE_WORDS = frozenset({"caused", "causes", "cause", "menyebabkan", "disebabkan"})
HEDGE_WORDS = frozenset(
    "might may maybe perhaps possibly probably seems mungkin diduga kemungkinan".split()
)
CANNOT_RUN = ("cannot", "run", "without")
MAX_GAP_WORDS = 7


def _clean(word: str) -> str:
    return word.strip(PUNCTUATION).casefold()


def _close(word: str, target: str) -> bool:
    """Equal, or one adjacent-letter swap of a word long enough that a swap is a typo."""
    if word == target:
        return True
    if len(word) != len(target) or len(word) < 5:
        return False
    diff = [i for i in range(len(word)) if word[i] != target[i]]
    return (
        len(diff) == 2
        and diff[1] == diff[0] + 1
        and word[diff[0]] == target[diff[1]]
        and word[diff[1]] == target[diff[0]]
    )


def _is_word(word: str, vocabulary: frozenset[str]) -> bool:
    return any(_close(word, v) for v in vocabulary)


@dataclass(frozen=True)
class Clause:
    """One relation statement read from text: ``kind`` is REQUIRES, CAUSE or one of the
    guarded outcomes; ``first`` and ``second`` are the two identifier tokens in text order and
    ``subject``/``object`` follow the voice of the sentence (requirer and required, cause and
    effect)."""

    kind: str
    subject: str
    object: str
    hedged: bool


def read_message(message: str) -> list[Clause]:
    """Clauses from one message; pure, deterministic, no registry or model involved."""
    text = _STATEMENT.sub(" ", message)
    tokens = text.split()
    idents = [i for i, t in enumerate(tokens) if _IDENT.match(t.strip(PUNCTUATION))]
    clauses: list[Clause] = []
    for left, right in zip(idents, idents[1:], strict=False):
        gap = [_clean(t) for t in tokens[left + 1 : right]]
        if len(gap) > MAX_GAP_WORDS:
            continue
        before = [_clean(t) for t in tokens[max(0, left - 4) : left]]
        first, second = tokens[left].strip(PUNCTUATION), tokens[right].strip(PUNCTUATION)
        hedged = any(_is_word(w, HEDGE_WORDS) for w in before + gap)
        causal = any(_is_word(w, CAUSE_WORDS) for w in gap)
        requires = any(
            _is_word(w, REQUIRE_WORDS) or w in REQUIRE_ABBREVIATIONS for w in gap
        ) or _has_run(gap, CANNOT_RUN)
        if causal:
            by = any(_is_word(w, BY_WORDS) for w in gap)
            cause, effect = (second, first) if by else (first, second)
            clauses.append(Clause("CAUSE", cause, effect, hedged))
        elif requires:
            passive = any(_is_word(w, PASSIVE_WORDS) or w == "reqd" for w in gap) and any(
                _is_word(w, BY_WORDS) for w in gap
            )
            requirer, required = (second, first) if passive else (first, second)
            clauses.append(Clause("REQUIRES", requirer, required, hedged))
    return clauses


def _has_run(gap: list[str], phrase: tuple[str, ...]) -> bool:
    position = 0
    for word in gap:
        if position < len(phrase) and _close(word, phrase[position]):
            position += 1
    return position == len(phrase)


@dataclass
class RelationReport:
    track: str
    revision: str
    atoms_read: int = 0
    requires: int = 0
    hypotheses: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    edge_ids: list[str] = field(default_factory=list)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


class _Reader:
    def __init__(self, registry: Registry):
        self.registry, self.ns = registry, registry.ns
        self.connection = registry.db.connection
        self.key_entity = {
            str(r[1]): str(r[0])
            for r in self.connection.execute(
                "SELECT id,external_key FROM entities WHERE ns=? AND external_key IS NOT NULL",
                (self.ns,),
            )
            if registry.access.eligible("READ", str(r[0]))
        }

    def stating_entity(self, atom_id: str, subject: str, span: str) -> str:
        """The keyed entity defined by the atom's own span, else the atom's subject entity."""
        keyed = self.connection.execute(
            "SELECT id FROM entities WHERE ns=? AND provisional_span_id=? "
            "AND external_key IS NOT NULL ORDER BY id LIMIT 1",
            (self.ns, span),
        ).fetchone()
        return subject if keyed is None else str(keyed[0])

    def labels(self, entity: str) -> set[str]:
        return {
            str(r[0])
            for r in self.connection.execute(
                "SELECT label FROM entity_aliases WHERE ns=? AND entity_id=?", (self.ns, entity)
            )
        }

    def event_of_entity(self, entity: str) -> str | None:
        row = self.connection.execute(
            "SELECT ev.id FROM entities e JOIN events ev ON ev.ns=e.ns "
            "JOIN source_spans s ON s.ns=e.ns AND s.id=e.provisional_span_id "
            "AND ev.source_version=s.version_id WHERE e.ns=? AND e.id=? ORDER BY ev.id LIMIT 1",
            (self.ns, entity),
        ).fetchone()
        return None if row is None else str(row[0])

    def message_of(self, atom_id: str) -> str:
        source = self.registry.source_for_atom(atom_id)
        raw = self.registry.sources.resolve(
            SourceSpan(
                source["version_id"], source["start_byte"], source["end_byte"], source["digest"]
            )
        ).decode()
        try:
            return str(json.loads(raw)["message"])
        except ValueError, KeyError, TypeError:
            return ""


def extract_relations(registry: Registry, track: str) -> RelationReport:
    """Write the derived edges of one track for every readable atom; return what was skipped."""
    require(track in REVISIONS, "UNSUPPORTED_TRACK")
    registry.access.check("WRITE")
    revision = REVISIONS[track]
    report = RelationReport(track, revision)
    reader = _Reader(registry)
    rows = reader.connection.execute(
        "SELECT a.id,a.event_id,a.subject_ref,a.source_span_id,a.predicate,a.object_type,"
        "a.object_value,ev.recorded_at FROM atoms a "
        "JOIN events ev ON ev.ns=a.ns AND ev.id=a.event_id WHERE a.ns=? ORDER BY a.id",
        (registry.ns,),
    ).fetchall()
    for row in rows:
        atom_id = str(row["id"])
        if not registry.access.eligible("READ", atom_id):
            continue
        report.atoms_read += 1
        stating = reader.stating_entity(atom_id, row["subject_ref"], row["source_span_id"])
        if track == TRACK_READBACK:
            clauses = _readback(row)
        else:
            clauses = read_message(reader.message_of(atom_id))
        for clause in clauses:
            _write(registry, reader, report, row, stating, clause, revision)
    return report


def _readback(row: sqlite3.Row) -> list[Clause]:
    """The stored fact as a clause: no reading, no error by construction."""
    predicate, kind, value = row["predicate"], row["object_type"], row["object_value"]
    if predicate != "requires" or kind != "TEXT":
        return []
    stored = json.loads(value)
    require(type(stored) is dict and stored.get("tag") == "TEXT", "STORED_VALUE_SHAPE")
    return [Clause("REQUIRES", "@self", str(stored["value"]), False)]


def _resolve(reader: _Reader, token: str, stating: str) -> str | None:
    """A dotted token is a governed key and must be registered. Any other token is the stating
    entity itself (``@self``, or a display name that is consistent with the entity's labels);
    a name is never matched against another entity."""
    if token == "@self":
        return stating
    if "." in token:
        return reader.key_entity.get(token)
    labels = reader.labels(stating)
    return stating if not labels or token in labels else None


def _write(
    registry: Registry,
    reader: _Reader,
    report: RelationReport,
    row: sqlite3.Row,
    stating: str,
    clause: Clause,
    revision: str,
) -> None:
    span, event, recorded = row["source_span_id"], row["event_id"], row["recorded_at"]
    if clause.kind == "REQUIRES":
        if clause.hedged:
            report.skip("HEDGED_REQUIREMENT")  # speculation is not a requirement
            return
        ends = _ends(reader, clause, stating)
        if ends is None:
            report.skip("UNRESOLVED_ENDPOINT")
            return
        source, target = ends
        if source == target:
            report.skip("SELF_REQUIREMENT")
            return
        spec = EdgeSpec(
            "REQUIRES", NodeRef("entity", source), NodeRef("entity", target),
            "DOCUMENT_ASSERTION", "*", (span,), recorded, revision,
        )  # fmt: skip
        report.edge_ids.append(write_edge(registry, spec))
        report.requires += 1
        return
    # CAUSE: the stating event is whichever side names the stating entity; the other side must be
    # a registered key whose defining event exists. Always a hypothesis, never VERIFIED_CAUSE.
    pair = _ends(reader, clause, stating)
    if pair is None:
        report.skip("UNRESOLVED_ENDPOINT")
        return
    cause, effect = (reader.event_of_entity(pair[0]), reader.event_of_entity(pair[1]))
    cause = event if pair[0] == stating else cause
    effect = event if pair[1] == stating else effect
    if cause is None or effect is None or cause == effect:
        report.skip("UNRESOLVED_EVENT")
        return
    spec = EdgeSpec(
        "HYPOTHESIZES_CAUSE", NodeRef("event", cause), NodeRef("event", effect),
        "HYPOTHESIS", "*", (span,), recorded, revision,
    )  # fmt: skip
    report.edge_ids.append(write_edge(registry, spec))
    report.hypotheses += 1


def _ends(reader: _Reader, clause: Clause, stating: str) -> tuple[str, str] | None:
    """Both endpoints of a clause as entity ids, or None when either stays unresolved."""
    first = _resolve(reader, clause.subject, stating)
    second = _resolve(reader, clause.object, stating)
    return None if first is None or second is None else (first, second)
