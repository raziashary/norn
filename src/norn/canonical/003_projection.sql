CREATE TABLE projection_manifests (
 ns TEXT NOT NULL, id TEXT NOT NULL, canonical_seq INTEGER NOT NULL,
 security_epoch INTEGER NOT NULL, capability TEXT NOT NULL CHECK(capability IN ('lexical','dense')),
 revision TEXT NOT NULL, source_digest TEXT NOT NULL, entries_digest TEXT NOT NULL,
 entry_count INTEGER NOT NULL CHECK(entry_count>=0), created_at TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);
CREATE TABLE projection_entries (
 ns TEXT NOT NULL, manifest_id TEXT NOT NULL, record_key TEXT NOT NULL,
 atom_id TEXT NOT NULL, event_id TEXT NOT NULL, source_version TEXT NOT NULL,
 start_byte INTEGER NOT NULL, end_byte INTEGER NOT NULL, span_digest TEXT NOT NULL,
 artifact_digest TEXT NOT NULL,
 PRIMARY KEY(ns,manifest_id,record_key),
 FOREIGN KEY(ns,manifest_id) REFERENCES projection_manifests(ns,id),
 FOREIGN KEY(ns,atom_id) REFERENCES atoms(ns,id),
 FOREIGN KEY(ns,event_id) REFERENCES events(ns,id),
 FOREIGN KEY(ns,source_version) REFERENCES source_versions(ns,id)
);
CREATE TABLE ready_snapshots (
 ns TEXT NOT NULL, id TEXT NOT NULL, canonical_seq INTEGER NOT NULL,
 security_epoch INTEGER NOT NULL, capabilities TEXT NOT NULL, manifests TEXT NOT NULL,
 journal_digest TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);
