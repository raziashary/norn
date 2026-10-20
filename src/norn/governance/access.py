"""Trusted-host identities and uncached current grants.

HostIdentity is supplied by the embedding host, never parsed from a write body.
The local CLI is an OS/filesystem-trusted operator, not a network authenticator.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from norn.canonical.database import Database
from norn.canonical.outbox import allocate, publish
from norn.contracts.errors import require
from norn.contracts.identity import Namespace, canonical, label
from norn.contracts.time import stamp

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

    def check(self, operation: str, object_id: str | None = None) -> int:
        require(operation in {"READ", "WRITE", "ADMIN"})
        row = self.db.connection.execute(
            "SELECT decision FROM scope_grants WHERE ns=? AND principal_id=? AND scope='*' "
            "AND operation=? ORDER BY security_epoch DESC LIMIT 1",
            (self.ns, self.host.principal, operation),
        ).fetchone()
        require(row is not None and row[0] == "GRANT", DENIED)
        if object_id is not None:
            row = self.db.connection.execute(
                "SELECT 1 FROM objects WHERE ns=? AND id=? AND NOT EXISTS "
                "(SELECT 1 FROM tombstones WHERE ns=? AND object_id=?)",
                (self.ns, object_id, self.ns, object_id),
            ).fetchone()
            require(row is not None, DENIED)
        return int(
            self.db.connection.execute(
                "SELECT security_epoch FROM namespaces WHERE ns=?", (self.ns,)
            ).fetchone()[0]
        )

    def _grant(
        self, connection: sqlite3.Connection, principal: str, operation: str, decision: str
    ) -> None:
        epoch = connection.execute(
            "UPDATE namespaces SET security_epoch=security_epoch+1 "
            "WHERE ns=? RETURNING security_epoch",
            (self.ns,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO scope_grants VALUES(?,?,?,'*',?,?,?,?,?)",
            (
                self.ns,
                uuid4().hex,
                principal,
                operation,
                decision,
                epoch,
                stamp(datetime.now(UTC)),
                self.host.principal,
            ),
        )

    def grant(self, principal: str, operation: str, *, revoke: bool = False) -> None:
        label(principal)
        require(operation in {"READ", "WRITE", "ADMIN"}, "INVALID_OPERATION")
        require(type(revoke) is bool)
        with self.db.transaction() as connection:
            self.check("ADMIN")
            connection.execute(
                "INSERT OR IGNORE INTO principals VALUES(?,?,?)",
                (self.ns, principal, "host:" + principal),
            )
            self._grant(connection, principal, operation, "REVOKE" if revoke else "GRANT")
            publish(connection, self.ns, allocate(connection, self.ns), "ACCESS_CHANGED", [])
