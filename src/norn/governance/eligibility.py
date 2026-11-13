"""Per-object read eligibility from source scope labels (ADR-0029 P06-Q7, design section 2).

Pure, non-raising and uncached: every call reads the current grants and labels. The rule:

* A source carries one label (default ``'*'``, newest ``object_scopes`` row wins).
* An operation on label S is allowed iff the newest ``scope_grants`` row for the principal,
  operation and S is a GRANT, or there is no row at S and the newest row at ``'*'`` is a GRANT.
  A REVOKE at S therefore overrides a GRANT at ``'*'`` (deny overrides).
* Derived objects take their visibility from their sources at read time: an atom or event from
  its primary support only; an entity if at least one contributing source is readable; a
  relationship or graph edge only if both endpoints and every support are readable; a derivation
  only if its output and every input are.

Tombstones are not decided here; ``Access`` combines both so one rule serves every caller.
"""

import json
import sqlite3

SCOPE_ALL = "*"
_SOURCE_OF_SPAN = (
    "SELECT v.source_id FROM source_spans s JOIN source_versions v "
    "ON s.ns=v.ns AND s.version_id=v.id WHERE s.ns=? AND s.id=?"
)


class Eligibility:
    def __init__(
        self, connection: sqlite3.Connection, ns: str, principal: str, *, scoped: bool = True
    ):
        # ``scoped`` is False on a store older than schema 6, which has no labels: every source
        # is then '*' and only the namespace grant decides, exactly as before.
        self.connection, self.ns, self.principal, self.scoped = connection, ns, principal, scoped

    def decision(self, operation: str, label: str) -> bool:
        row = self.connection.execute(
            "SELECT decision FROM scope_grants WHERE ns=? AND principal_id=? AND scope=? "
            "AND operation=? ORDER BY security_epoch DESC LIMIT 1",
            (self.ns, self.principal, label, operation),
        ).fetchone()
        if row is not None:
            return bool(row[0] == "GRANT")
        return label != SCOPE_ALL and self.decision(operation, SCOPE_ALL)

    def source_label(self, source_id: str) -> str:
        if not self.scoped:
            return SCOPE_ALL
        row = self.connection.execute(
            "SELECT scope FROM object_scopes WHERE ns=? AND object_id=? "
            "ORDER BY security_epoch DESC LIMIT 1",
            (self.ns, source_id),
        ).fetchone()
        return SCOPE_ALL if row is None else str(row[0])

    def source_readable(self, operation: str, source_id: str) -> bool:
        return self.decision(operation, self.source_label(source_id))

    def _span_source(self, span_id: str) -> str | None:
        row = self.connection.execute(_SOURCE_OF_SPAN, (self.ns, span_id)).fetchone()
        return None if row is None else str(row[0])

    def _spans_readable(self, operation: str, spans: list[str], *, every: bool) -> bool:
        sources = [self._span_source(s) for s in spans]
        if any(s is None for s in sources):
            return False  # a dangling support is not evidence of access
        verdicts = [self.source_readable(operation, str(s)) for s in sources]
        return bool(verdicts) and (all(verdicts) if every else any(verdicts))

    def allows(self, operation: str, object_id: str) -> bool:
        """Label eligibility of one object; absent and denied are the same answer (False)."""
        row = self.connection.execute(
            "SELECT kind FROM objects WHERE ns=? AND id=?", (self.ns, object_id)
        ).fetchone()
        if row is None:
            return False
        return self._by_kind(operation, str(row[0]), object_id)

    def _by_kind(self, operation: str, kind: str, object_id: str) -> bool:
        ns, db = self.ns, self.connection
        if kind == "source":
            return self.source_readable(operation, object_id)
        if kind == "event":
            row = db.execute(
                "SELECT v.source_id FROM events e JOIN source_versions v ON e.ns=v.ns "
                "AND e.source_version=v.id WHERE e.ns=? AND e.id=?",
                (ns, object_id),
            ).fetchone()
            return row is not None and self.source_readable(operation, str(row[0]))
        if kind == "atom":
            row = db.execute(
                "SELECT source_span_id FROM atoms WHERE ns=? AND id=?", (ns, object_id)
            ).fetchone()
            return row is not None and self._spans_readable(operation, [row[0]], every=True)
        if kind == "entity":
            spans = [
                str(r[0])
                for r in db.execute(
                    "SELECT provisional_span_id FROM entities WHERE ns=? AND id=? "
                    "UNION SELECT span_id FROM entity_aliases WHERE ns=? AND entity_id=? "
                    "UNION SELECT source_span_id FROM atoms WHERE ns=? "
                    "AND (subject_ref=? OR object_ref=?)",
                    (ns, object_id, ns, object_id, ns, object_id, object_id),
                )
            ]
            return self._spans_readable(operation, spans, every=False)
        if kind == "edge":
            row = db.execute(
                "SELECT from_id,to_id FROM relationships WHERE ns=? AND id=?", (ns, object_id)
            ).fetchone()
            if row is None:
                return False
            spans = [
                str(r[0])
                for r in db.execute(
                    "SELECT span_id FROM edge_support WHERE ns=? AND edge_id=?", (ns, object_id)
                )
            ]
            return (
                self.allows(operation, row[0])
                and self.allows(operation, row[1])
                and (not spans or self._spans_readable(operation, spans, every=True))
            )
        if kind == "graph_edge":
            row = db.execute(
                "SELECT from_id,to_id,source_span_id FROM graph_edges WHERE ns=? AND id=?",
                (ns, object_id),
            ).fetchone()
            if row is None:
                return False
            spans = [str(row[2])] + [
                str(r[0])
                for r in db.execute(
                    "SELECT span_id FROM graph_edge_support WHERE ns=? AND edge_id=?",
                    (ns, object_id),
                )
            ]
            return (
                self.allows(operation, row[0])
                and self.allows(operation, row[1])
                and self._spans_readable(operation, spans, every=True)
            )
        if kind == "derivation":
            row = db.execute(
                "SELECT output_id FROM derivations WHERE ns=? AND id=?", (ns, object_id)
            ).fetchone()
            inputs = [
                str(r[0])
                for r in db.execute(
                    "SELECT input_id FROM derivation_inputs WHERE ns=? AND derivation_id=?",
                    (ns, object_id),
                )
            ]
            return (
                row is not None
                and self.allows(operation, row[0])
                and all(self.allows(operation, i) for i in inputs)
            )
        return False  # an unknown kind is never granted by default

    def denied_sources(self, operation: str) -> list[str]:
        """Sources whose current label denies the operation, for SQL exclusion before LIMIT."""
        if not self.scoped:
            return []
        rows = self.connection.execute(
            "SELECT o.object_id,o.scope FROM object_scopes o WHERE o.ns=? AND o.security_epoch="
            "(SELECT max(security_epoch) FROM object_scopes "
            "WHERE ns=o.ns AND object_id=o.object_id)",
            (self.ns,),
        ).fetchall()
        verdicts: dict[str, bool] = {}
        denied = []
        for source_id, label in rows:
            if label not in verdicts:
                verdicts[label] = self.decision(operation, label)
            if not verdicts[label]:
                denied.append(str(source_id))
        return sorted(denied)

    def denied_sources_json(self, operation: str) -> str:
        return json.dumps(self.denied_sources(operation))
