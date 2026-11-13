"""Trusted-host identities and uncached current grants.

HostIdentity is supplied by the embedding host, never parsed from a write body.
The local CLI is an OS/filesystem-trusted operator, not a network authenticator.
"""

import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from norn.canonical.database import Database
from norn.canonical.outbox import allocate, publish
from norn.contracts.errors import NornError, require
from norn.contracts.identity import Namespace, canonical, label
from norn.governance.eligibility import SCOPE_ALL, Eligibility

DENIED = "NOT_AUTHORIZED_OR_NOT_FOUND"
POLICY = "synthetic-pilot-v1"


@dataclass(frozen=True)
class HostIdentity:
    namespace: Namespace
    principal: str

    def __post_init__(self) -> None:
        require(isinstance(self.namespace, Namespace))
        label(self.principal)


class Access:
    def __init__(self, database: Database, host: HostIdentity):
        self.db = database
        self.host = host
        self.ns = host.namespace.key
        self._scoped = (
            database.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='object_scopes'"
            ).fetchone()
            is not None
        )

    def bootstrap(self) -> None:
        """One-time local operator provisioning, only into an absent namespace."""
        ns = self.host.namespace
        with self.db.transaction() as connection:
            require(
                connection.execute("SELECT 1 FROM namespaces WHERE ns=?", (self.ns,)).fetchone()
                is None,
                "NAMESPACE_EXISTS",
            )
            connection.execute(
                "INSERT INTO namespaces(ns,tenant,workspace,partition) VALUES(?,?,?,?)",
                (self.ns, ns.tenant, ns.workspace, ns.partition),
            )
            connection.execute(
                "INSERT INTO principals VALUES(?,?,?)",
                (self.ns, self.host.principal, "local-operator:" + self.host.principal),
            )
            connection.execute(
                "INSERT INTO retention_policies VALUES(?,?,1,?)",
                (
                    self.ns,
                    POLICY,
                    canonical(
                        {
                            "data": "SYNTHETIC_ONLY",
                            "serving_denial": "IMMEDIATE",
                            "physical_purge": "EXPLICIT_PENDING",
                            "training": False,
                            "audit": "IDs/reason codes only",
                            "backups": "PENDING",
                        }
                    ),
                ),
            )
            for operation in ("READ", "WRITE", "ADMIN"):
                self._grant(connection, self.host.principal, operation, "GRANT")
            seq = allocate(connection, self.ns)
            publish(connection, self.ns, seq, "BOOTSTRAP", [])

    def _gate(self, operation: str) -> bool:
        row = self.db.connection.execute(
            "SELECT decision FROM scope_grants WHERE ns=? AND principal_id=? AND scope='*' "
            "AND operation=? ORDER BY security_epoch DESC LIMIT 1",
            (self.ns, self.host.principal, operation),
        ).fetchone()
        return row is not None and bool(row[0] == "GRANT")

    @property
    def labels(self) -> Eligibility:
        return Eligibility(self.db.connection, self.ns, self.host.principal, scoped=self._scoped)

    def acl_allows(self, operation: str, object_id: str) -> bool:
        """Label eligibility only (no tombstone), for callers that drop rather than deny."""
        return self.labels.allows(operation, object_id)

    def eligible(self, operation: str, object_id: str | None = None) -> bool:
        """The single non-raising rule; ``check`` is this plus the raising public contract."""
        require(operation in {"READ", "WRITE", "ADMIN"})
        if not self._gate(operation):
            return False
        if object_id is None:
            return True
        row = self.db.connection.execute(
            "SELECT 1 FROM objects WHERE ns=? AND id=? AND NOT EXISTS "
            "(SELECT 1 FROM tombstones WHERE ns=? AND object_id=?)",
            (self.ns, object_id, self.ns, object_id),
        ).fetchone()
        return row is not None and self.acl_allows(operation, object_id)

    def check(self, operation: str, object_id: str | None = None) -> int:
        require(self.eligible(operation, object_id), DENIED)
        return int(
            self.db.connection.execute(
                "SELECT security_epoch FROM namespaces WHERE ns=?", (self.ns,)
            ).fetchone()[0]
        )

    def recheck(self, operation: str, epoch: int, object_id: str | None = None) -> int:
        """Re-verify a read at query time; a label or grant change since ``epoch`` is reported as
        QUERY_SECURITY_CHANGED, a tombstone keeps its own immediate denial."""
        try:
            current = self.check(operation, object_id)
        except NornError as error:
            if error.code != DENIED or object_id is None:
                raise
            tombstoned = self.db.connection.execute(
                "SELECT 1 FROM tombstones WHERE ns=? AND object_id=?", (self.ns, object_id)
            ).fetchone()
            now = self.db.connection.execute(
                "SELECT security_epoch FROM namespaces WHERE ns=?", (self.ns,)
            ).fetchone()[0]
            if tombstoned is None and now != epoch:
                raise NornError("QUERY_SECURITY_CHANGED", "retrieval") from None
            raise
        require(current == epoch, "QUERY_SECURITY_CHANGED")
        return current

    def _grant(
        self,
        connection: sqlite3.Connection,
        principal: str,
        operation: str,
        decision: str,
        scope: str = SCOPE_ALL,
    ) -> None:
        epoch = connection.execute(
            "UPDATE namespaces SET security_epoch=security_epoch+1 "
            "WHERE ns=? RETURNING security_epoch",
            (self.ns,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO scope_grants VALUES(?,?,?,?,?,?,?,?,?)",
            (
                self.ns,
                uuid4().hex,
                principal,
                scope,
                operation,
                decision,
                epoch,
                self.db.now(),
                self.host.principal,
            ),
        )

    def grant(
        self, principal: str, operation: str, *, revoke: bool = False, scope: str = SCOPE_ALL
    ) -> None:
        label(principal)
        require(operation in {"READ", "WRITE", "ADMIN"}, "INVALID_OPERATION")
        require(type(revoke) is bool)
        require(scope == SCOPE_ALL or bool(label(scope)), "INVALID_SCOPE")
        with self.db.transaction() as connection:
            self.check("ADMIN")
            connection.execute(
                "INSERT OR IGNORE INTO principals VALUES(?,?,?)",
                (self.ns, principal, "host:" + principal),
            )
            self._grant(connection, principal, operation, "REVOKE" if revoke else "GRANT", scope)
            publish(connection, self.ns, allocate(connection, self.ns), "ACCESS_CHANGED", [])

    def set_scope(self, source_id: str, scope: str) -> None:
        """Label a source (ADMIN). Append-only: the newest epoch wins, and the epoch moves."""
        label(source_id)
        require(scope == SCOPE_ALL or bool(label(scope)), "INVALID_SCOPE")
        with self.db.transaction() as connection:
            self.check("ADMIN")
            require(
                connection.execute(
                    "SELECT 1 FROM sources WHERE ns=? AND id=?", (self.ns, source_id)
                ).fetchone()
                is not None,
                DENIED,
            )
            epoch = connection.execute(
                "UPDATE namespaces SET security_epoch=security_epoch+1 "
                "WHERE ns=? RETURNING security_epoch",
                (self.ns,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO object_scopes VALUES(?,?,?,?,?,?,?)",
                (
                    self.ns,
                    uuid4().hex,
                    source_id,
                    scope,
                    epoch,
                    self.db.now(),
                    self.host.principal,
                ),
            )
            publish(
                connection, self.ns, allocate(connection, self.ns), "ACCESS_CHANGED", [source_id]
            )
