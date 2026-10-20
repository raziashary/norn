"""Atomic local publication journal and a bounded integrity-checking reader.

Reading a journal page never marks a projection READY or acknowledges external
delivery. Consumers retain an explicit cursor; replay is read-only and repeatable.
"""

import json
import sqlite3

from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, stable_id


def allocate(connection: sqlite3.Connection, ns: str) -> int:
    row = connection.execute(
        "UPDATE namespaces SET commit_seq=commit_seq+1 WHERE ns=? RETURNING commit_seq", (ns,)
    ).fetchone()
    require(row is not None, "NOT_AUTHORIZED_OR_NOT_FOUND")
    return int(row[0])


def publish(
    connection: sqlite3.Connection, ns: str, seq: int, operation: str, objects: list[str]
) -> None:
    payload = canonical(objects)
    connection.execute(
        "INSERT INTO outbox VALUES(?,?,?,?,?,?,1)",
        (ns, stable_id("outbox", ns, str(seq)), seq, operation, payload, digest(payload.encode())),
    )


def read_page(
    connection: sqlite3.Connection, ns: str, after: int = 0, limit: int = 100
) -> list[dict[str, object]]:
    require(type(after) is int and after >= 0)
    require(type(limit) is int and 1 <= limit <= 1000, "JOURNAL_BUDGET")
    rows = connection.execute(
        "SELECT * FROM outbox WHERE ns=? AND commit_seq>? ORDER BY commit_seq LIMIT ?",
        (ns, after, limit),
    ).fetchall()
    result = []
    for row in rows:
        require(digest(row["objects"].encode()) == row["payload_digest"], "JOURNAL_INTEGRITY")
        result.append(
            {
                "commit_seq": row["commit_seq"],
                "operation": row["operation"],
                "object_ids": json.loads(row["objects"]),
                "schema_version": 1,
                "payload_digest": row["payload_digest"],
            }
        )
    return result
