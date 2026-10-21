"""Append-only local snapshot identities; readiness always requires exact artifact readback."""

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical, digest

if TYPE_CHECKING:
    from norn.integration.engine import Engine


def find(engine: Engine, seq: int, epoch: int, revisions: Mapping[str, str]) -> dict[str, Any]:
    engine.access.check("READ")
    rows = engine.db.connection.execute(
        "SELECT * FROM ready_snapshots WHERE ns=? AND canonical_seq=? AND security_epoch=? "
        "ORDER BY id LIMIT 33",
        (engine.access.ns, seq, epoch),
    ).fetchall()
    require(len(rows) <= 32, "SNAPSHOT_VERSION_BUDGET")
    for row in rows:
        if set(revisions) <= set(json.loads(row["capabilities"])):
            manifests = json.loads(row["manifests"])
            compatible = True
            for capability, expected in revisions.items():
                manifest = engine.db.connection.execute(
                    "SELECT revision,canonical_seq,security_epoch,capability "
                    "FROM projection_manifests "
                    "WHERE ns=? AND id=?",
                    (engine.access.ns, manifests[capability]),
                ).fetchone()
                if manifest is None or tuple(manifest) != (expected, seq, epoch, capability):
                    compatible = False
                    break
            if compatible:
                return dict(row)
    raise NornError("PROJECTION_NOT_READY")


def entries_digest(entries: list[tuple[object, ...]]) -> str:
    return digest(canonical(entries).encode())
