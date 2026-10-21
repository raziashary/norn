"""Idempotent full local outbox replay, immutable artifacts, atomic readback publication."""

import json
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from norn.canonical import outbox, snapshots
from norn.canonical.sources import SourceStore
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest, stable_id
from norn.contracts.time import QueryClock, stamp
from norn.embedding.assets import fingerprint
from norn.embedding.baseline import LocalModels, vector
from norn.retrieval import dense, exact, lexical
from norn.retrieval.contracts import EligibleCorpus, RecallRequest

if TYPE_CHECKING:
    from norn.integration.engine import Engine


def artifacts(engine: Engine) -> SourceStore:
    return SourceStore(engine.root / "projections")


def readback(
    engine: Engine,
    manifest_id: str,
    *,
    keys: frozenset[str] | None = None,
    budget: QueryBudget | None = None,
    current_revision: bool = True,
) -> dict[str, dict[str, Any]]:
    engine.access.check("READ")
    ns = engine.access.ns
    manifest = engine.db.connection.execute(
        "SELECT * FROM projection_manifests WHERE ns=? AND id=?", (ns, manifest_id)
    ).fetchone()
    require(manifest is not None, "PROJECTION_NOT_READY")
    expected_revision = (
        lexical.REVISION if manifest["capability"] == "lexical" else fingerprint("encoder")
    )
    if current_revision:
        require(manifest["revision"] == expected_revision, "PROJECTION_REVISION_MISMATCH")
    rows = engine.db.connection.execute(
        "SELECT record_key,atom_id,event_id,source_version,start_byte,end_byte,"
        "span_digest,artifact_digest "
        "FROM projection_entries WHERE ns=? AND manifest_id=? ORDER BY record_key LIMIT 100001",
        (ns, manifest_id),
    ).fetchall()
    require(len(rows) <= 100_000 and len(rows) == manifest["entry_count"], "PROJECTION_READBACK")
    require(
        snapshots.entries_digest([tuple(r) for r in rows]) == manifest["entries_digest"],
        "PROJECTION_READBACK",
    )
    require(
        digest(canonical(sorted((r["record_key"], r["span_digest"]) for r in rows)).encode())
        == manifest["source_digest"],
        "PROJECTION_SOURCE_MISMATCH",
    )
    if keys is not None:
        require(keys <= {r["record_key"] for r in rows}, "PROJECTION_SOURCE_MISMATCH")
    store = artifacts(engine)
    result: dict[str, dict[str, Any]] = {}
    bytes_read = 0
    for row in rows:
        if keys is not None and row["record_key"] not in keys:
            continue
        if budget is not None:
            budget.checkpoint()
        raw = store.read(row["artifact_digest"])
        bytes_read += len(raw)
        require(bytes_read <= 67_108_864, "PROJECTION_ARTIFACT_BUDGET")
        if budget is not None:
            budget.artifact(len(raw))
        payload = json.loads(raw)
        require(
            type(payload) is dict
            and payload.get("record_key") == row["record_key"]
            and payload.get("span_digest") == row["span_digest"],
            "PROJECTION_READBACK",
        )
        if current_revision and manifest["capability"] == "dense":
            vector(payload["vector"])
        result[row["record_key"]] = payload
    return result


def build(
    engine: Engine, *, models: LocalModels | None = None, budget: QueryBudget | None = None
) -> dict[str, Any]:
    budget = budget or QueryBudget(600_000)
    engine.access.check("ADMIN")
    now = datetime.now(UTC)
    request = RecallRequest(
        "projection",
        QueryClock(now, "UTC", "KNOWLEDGE_AT", now, now),
        max_scan_records=100_000,
        deadline_ms=600_000,
    )
    with budget.sqlite_guard(engine.db.connection):
        corpus = exact.eligible(engine, request, budget.checkpoint)
    require(corpus.complete, corpus.reason or "PROJECTION_INPUT_BUDGET")
    seq, epoch, ns = corpus.snapshot, corpus.security_epoch, engine.access.ns
    journal = []
    after = 0
    while after < seq:
        budget.checkpoint()
        require(seq <= 100_000, "JOURNAL_REPLAY_BUDGET")
        page = outbox.read_page(engine.db.connection, ns, after, 1000)
        require(bool(page), "JOURNAL_GAP")
        for entry in page:
            require(entry["commit_seq"] == after + 1, "JOURNAL_GAP")
            after += 1
            journal.append(entry)
        require(after <= seq, "PROJECTION_SUPERSEDED")
    journal_digest = digest(canonical(journal).encode())
    source_digest = digest(canonical(sorted((r.key, r.sha256) for r in corpus.records)).encode())
    store = artifacts(engine)
    manifests = {}
    capabilities = ("lexical", "dense") if models is not None else ("lexical",)
    for capability in capabilities:
        revision = lexical.REVISION if capability == "lexical" else fingerprint("encoder")
        entries: list[tuple[object, ...]] = []
        for record in sorted(corpus.records, key=lambda r: r.key):
            budget.checkpoint()
            payload: dict[str, Any] = {"record_key": record.key, "span_digest": record.sha256}
            if capability == "lexical":
                payload["terms"] = dict(Counter(lexical.tokenize(record.text)))
            else:
                if models is None:
                    raise AssertionError("dense capability requires models")
                payload["vector"] = dense.encode((record.text,), models, budget)[0]
            artifact = store.put(canonical(payload).encode())
            entries.append(
                (
                    record.key,
                    record.atom_id,
                    record.event_id,
                    record.source_version,
                    record.start_byte,
                    record.end_byte,
                    record.sha256,
                    artifact,
                )
            )
        checksum = snapshots.entries_digest(entries)
        manifest_id = stable_id(
            "projection", ns, str(seq), str(epoch), capability, revision, source_digest, checksum
        )
        with engine.db.transaction() as connection:
            require(engine.access.check("ADMIN") == epoch, "PROJECTION_SUPERSEDED")
            require(
                connection.execute(
                    "SELECT commit_seq FROM namespaces WHERE ns=?", (ns,)
                ).fetchone()[0]
                == seq,
                "PROJECTION_SUPERSEDED",
            )
            connection.execute(
                "INSERT OR IGNORE INTO projection_manifests VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    ns,
                    manifest_id,
                    seq,
                    epoch,
                    capability,
                    revision,
                    source_digest,
                    checksum,
                    len(entries),
                    stamp(now),
                ),
            )
            for artifact_entry in entries:
                connection.execute(
                    "INSERT OR IGNORE INTO projection_entries VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (ns, manifest_id, *artifact_entry),
                )
        readback(engine, manifest_id, budget=budget)
        manifests[capability] = manifest_id
    snapshot_id = stable_id(
        "snapshot", ns, str(seq), str(epoch), canonical(manifests), journal_digest
    )
    budget.checkpoint()
    with engine.db.transaction() as connection:
        require(engine.access.check("ADMIN") == epoch, "PROJECTION_SUPERSEDED")
        require(
            connection.execute("SELECT commit_seq FROM namespaces WHERE ns=?", (ns,)).fetchone()[0]
            == seq,
            "PROJECTION_SUPERSEDED",
        )
        for manifest_id in manifests.values():
            readback(engine, manifest_id, budget=budget)
        connection.execute(
            "INSERT OR IGNORE INTO ready_snapshots VALUES(?,?,?,?,?,?,?,?)",
            (
                ns,
                snapshot_id,
                seq,
                epoch,
                canonical(capabilities),
                canonical(manifests),
                journal_digest,
                stamp(now),
            ),
        )
    return {
        "snapshot_id": snapshot_id,
        "canonical_seq": seq,
        "security_epoch": epoch,
        "capabilities": capabilities,
        "manifests": manifests,
        "state": "READY",
        "usage": budget.usage(),
    }


def load(
    engine: Engine, corpus: EligibleCorpus, capabilities: tuple[str, ...], budget: QueryBudget
) -> tuple[str, dict[str, dict[str, dict[str, Any]]]]:
    revisions = {
        capability: lexical.REVISION if capability == "lexical" else fingerprint("encoder")
        for capability in capabilities
    }
    snapshot = snapshots.find(engine, corpus.snapshot, corpus.security_epoch, revisions)
    manifests = json.loads(snapshot["manifests"])
    output = {}
    for capability in capabilities:
        budget.checkpoint()
        output[capability] = readback(
            engine,
            manifests[capability],
            keys=frozenset(r.key for r in corpus.records),
            budget=budget,
        )
        for record in corpus.records:
            require(
                record.key in output[capability]
                and output[capability][record.key]["span_digest"] == record.sha256,
                "PROJECTION_SOURCE_MISMATCH",
            )
    return snapshot["id"], output
