"""Immutable source-backed binding artifacts with exact readback before READY."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from norn.canonical import snapshots
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, stable_id
from norn.contracts.time import QueryClock, stamp
from norn.embedding import checkpoint, denoising
from norn.embedding.binding import LEARNED, VARIANTS
from norn.embedding.feature_encoder import FeatureEncoder, method
from norn.embedding.numerics import array
from norn.features.salience import NeutralSalience
from norn.features.views import derive
from norn.projection.local import artifacts, replay
from norn.retrieval import exact
from norn.retrieval.contracts import EligibleCorpus, RecallRequest, Record

if TYPE_CHECKING:
    from norn.integration.engine import Engine


def current(engine: Engine, seq: int, epoch: int) -> None:
    require(engine.access.check("ADMIN") == epoch, "PROJECTION_SUPERSEDED")
    require(
        engine.db.connection.execute(
            "SELECT commit_seq FROM namespaces WHERE ns=?", (engine.access.ns,)
        ).fetchone()[0]
        == seq,
        "PROJECTION_SUPERSEDED",
    )


def build(
    engine: Engine,
    variant: str,
    checkpoint_path: Path | None = None,
    *,
    full_fanout: bool = False,
    budget: QueryBudget | None = None,
) -> dict[str, Any]:
    if variant == "B5":
        denoising.encode()
    require(variant in VARIANTS, "UNSUPPORTED_BINDING_VARIANT")
    budget = budget or QueryBudget(600_000)
    engine.access.check("ADMIN")
    codec = FeatureEncoder(engine, budget)
    ck = checkpoint.load(checkpoint_path) if checkpoint_path is not None else None
    require((variant in LEARNED) == (ck is not None), "BINDING_CHECKPOINT_REQUIRED")
    require(ck is None or ck.model.variant == variant, "CHECKPOINT_VARIANT_MISMATCH")
    checkpoint_digest = ck.sha256 if ck else "NONE"
    revision = method(variant, checkpoint_digest)
    store = artifacts(engine)
    if ck is not None:
        assert checkpoint_path is not None
        require(
            store.put(checkpoint_path.read_bytes()) == checkpoint_digest,
            "CHECKPOINT_SOURCE_CHANGED",
        )
    now = datetime.now(UTC)
    request = RecallRequest(
        "binding projection",
        QueryClock(now, "UTC", "KNOWLEDGE_AT", now, now),
        max_scan_records=4096,
        deadline_ms=600_000,
    )
    with budget.sqlite_guard(engine.db.connection):
        corpus = exact.eligible(engine, request, budget.checkpoint)
    require(corpus.complete, corpus.reason or "BINDING_CORPUS_BUDGET")
    seq, epoch, ns = corpus.snapshot, corpus.security_epoch, engine.access.ns
    journal_digest = replay(engine, seq, budget)
    grouped: dict[str, list[Record]] = {}
    for record in corpus.records:
        grouped.setdefault(record.event_id, []).append(record)
    entries: list[tuple[object, ...]] = []
    durations = [0, 0, 0]
    invocations = [0, 0, 0]
    for event_id, values in sorted(grouped.items()):
        budget.checkpoint()
        records = tuple(sorted(values, key=lambda r: r.key))
        views = derive(records, full_fanout=full_fanout)
        vector = codec.memory(views, variant, ck.model if ck else None)
        payload = {
            "event_id": event_id,
            "record_keys": [r.key for r in records],
            "spans": {r.key: r.sha256 for r in records},
            "revision": revision,
            "mask": views.mask,
            "salience": asdict(views.salience),
            "texts": views.texts,
            "vector": vector.astype(np.float32).tolist(),
        }
        artifact = store.put(canonical(payload).encode())
        for record in records:
            entries.append(
                (
                    record.key,
                    record.atom_id,
                    event_id,
                    record.source_version,
                    record.start_byte,
                    record.end_byte,
                    record.sha256,
                    artifact,
                )
            )
        durations = [a + b for a, b in zip(durations, views.durations_ns, strict=True)]
        invocations = [a + int(b) for a, b in zip(invocations, views.invocations, strict=True)]
    entries.sort()
    checksum = snapshots.entries_digest(entries)
    source_digest = digest(canonical(sorted((r.key, r.sha256) for r in corpus.records)).encode())
    identity = stable_id(
        "binding", ns, str(seq), str(epoch), variant, revision, source_digest, checksum
    )
    with engine.db.transaction() as connection:
        current(engine, seq, epoch)
        connection.execute(
            "INSERT OR IGNORE INTO binding_manifests VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                ns,
                identity,
                seq,
                epoch,
                variant,
                revision,
                checkpoint_digest,
                source_digest,
                checksum,
                len(entries),
                stamp(now),
            ),
        )
        for entry in entries:
            connection.execute(
                "INSERT OR IGNORE INTO binding_entries VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ns, identity, *entry),
            )
    readback(engine, identity, budget=budget)
    budget.checkpoint()
    with engine.db.transaction() as connection:
        current(engine, seq, epoch)
        readback(engine, identity, budget=budget)
        connection.execute(
            "INSERT OR IGNORE INTO binding_ready VALUES(?,?,?,?)",
            (ns, identity, journal_digest, stamp(now)),
        )
    return {
        "snapshot_id": identity,
        "canonical_seq": seq,
        "security_epoch": epoch,
        "variant": variant,
        "revision": revision,
        "checkpoint": checkpoint_digest,
        "state": "READY",
        "usage": budget.usage(),
        "event_count": len(grouped),
        "facet_invocations": invocations,
        "facet_ns": durations,
        "full_fanout": full_fanout,
        "embedding_bytes_per_event": 1536,
    }


def readback(
    engine: Engine,
    identity: str,
    *,
    keys: frozenset[str] | None = None,
    budget: QueryBudget | None = None,
    current_revision: bool = True,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    engine.access.check("READ")
    manifest_row = engine.db.connection.execute(
        "SELECT * FROM binding_manifests WHERE ns=? AND id=?", (engine.access.ns, identity)
    ).fetchone()
    require(manifest_row is not None, "BINDING_PROJECTION_NOT_READY")
    manifest = dict(manifest_row)
    if current_revision:
        require(
            manifest["revision"] == method(manifest["variant"], manifest["checkpoint_digest"]),
            "BINDING_REVISION_MISMATCH",
        )
    rows = engine.db.connection.execute(
        "SELECT record_key,atom_id,event_id,source_version,start_byte,end_byte,span_digest,"
        "artifact_digest FROM binding_entries WHERE ns=? AND manifest_id=? ORDER BY record_key "
        "LIMIT 4097",
        (engine.access.ns, identity),
    ).fetchall()
    require(len(rows) <= 4096 and len(rows) == manifest["entry_count"], "BINDING_READBACK")
    require(
        snapshots.entries_digest([tuple(r) for r in rows]) == manifest["entries_digest"],
        "BINDING_READBACK",
    )
    require(
        digest(canonical([(r["record_key"], r["span_digest"]) for r in rows]).encode())
        == manifest["source_digest"],
        "BINDING_SOURCE_MISMATCH",
    )
    require(keys is None or keys <= {r["record_key"] for r in rows}, "BINDING_SOURCE_MISMATCH")
    store = artifacts(engine)
    output = {}
    loaded: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for row in rows:
        if keys is not None and row["record_key"] not in keys:
            continue
        if budget:
            budget.checkpoint()
        artifact = row["artifact_digest"]
        if artifact not in loaded:
            raw = store.read(artifact)
            total_bytes += len(raw)
            require(total_bytes <= 67_108_864, "PROJECTION_ARTIFACT_BUDGET")
            if budget:
                budget.artifact(len(raw))
            payload = json.loads(raw)
            require(
                payload["event_id"] == row["event_id"]
                and payload["revision"] == manifest["revision"],
                "BINDING_READBACK",
            )
            if current_revision:
                require(
                    payload["salience"] == asdict(NeutralSalience()), "BINDING_SALIENCE_CHANGED"
                )
                vector = array(payload["vector"], (384,))
                mask = array(payload["mask"], (3,))
                require(
                    bool(((mask == 0) | (mask == 1)).all()) and bool(mask.any()),
                    "BINDING_MASK_SHAPE",
                )
                norms = np.linalg.norm(vector.reshape(3, 128), axis=1)
                require(
                    bool(np.allclose(norms, mask, atol=1e-4))
                    if manifest["variant"] == "B1"
                    else bool(np.isclose(np.linalg.norm(vector), 1, atol=1e-4)),
                    "INVALID_VECTOR_NORM",
                )
            loaded[artifact] = payload
        payload = loaded[artifact]
        require(
            row["record_key"] in payload["record_keys"]
            and payload["spans"].get(row["record_key"]) == row["span_digest"],
            "BINDING_SOURCE_MISMATCH",
        )
        output[row["record_key"]] = payload
    if manifest["checkpoint_digest"] != "NONE":
        raw = store.read(manifest["checkpoint_digest"])
        if budget:
            budget.artifact(len(raw))
        if current_revision:
            ck = checkpoint.parse(raw)
            require(
                ck.sha256 == manifest["checkpoint_digest"]
                and ck.model.variant == manifest["variant"],
                "CHECKPOINT_VARIANT_MISMATCH",
            )
    return manifest, output


def load(
    engine: Engine,
    corpus: EligibleCorpus,
    variant: str,
    checkpoint_digest: str,
    budget: QueryBudget,
) -> tuple[str, dict[str, dict[str, Any]]]:
    rows = engine.db.connection.execute(
        "SELECT m.id FROM binding_manifests m JOIN binding_ready r "
        "ON m.ns=r.ns AND m.id=r.manifest_id WHERE m.ns=? AND m.canonical_seq=? "
        "AND m.security_epoch=? AND m.variant=? AND m.revision=? "
        "ORDER BY m.id LIMIT 2",
        (
            engine.access.ns,
            corpus.snapshot,
            corpus.security_epoch,
            variant,
            method(variant, checkpoint_digest),
        ),
    ).fetchall()
    require(len(rows) == 1, "BINDING_PROJECTION_NOT_READY")
    identity = rows[0][0]
    _manifest, payloads = readback(
        engine, identity, keys=frozenset(r.key for r in corpus.records), budget=budget
    )
    for record in corpus.records:
        require(
            record.key in payloads and payloads[record.key]["spans"][record.key] == record.sha256,
            "BINDING_SOURCE_MISMATCH",
        )
    return identity, payloads
