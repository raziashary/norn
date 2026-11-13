CREATE TABLE relation_types (
 name TEXT PRIMARY KEY,
 traversable INTEGER NOT NULL CHECK(traversable IN (0,1)),
 causal INTEGER NOT NULL CHECK(causal IN (0,1)),
 CHECK(name<>'HYPOTHESIZES_CAUSE' OR causal=0)
);
INSERT INTO relation_types VALUES
 ('MENTIONS',1,0),('PART_OF_EVENT',1,0),('OBSERVED_IN',1,0),('OCCURRED_BEFORE',1,0),
 ('OCCURRED_AFTER',1,0),('RELATED_TO',1,0),('REQUIRES',1,0),('CONTRADICTS',0,0),
 ('SUPERSEDES',0,0),('DERIVED_FROM',1,0),('HYPOTHESIZES_CAUSE',1,0),('VERIFIED_CAUSE',1,1),
 ('IDENTITY_LINK',1,0);
CREATE TABLE object_scopes (
 ns TEXT NOT NULL, id TEXT NOT NULL, object_id TEXT NOT NULL, scope TEXT NOT NULL,
 security_epoch INTEGER NOT NULL, recorded_at TEXT NOT NULL, actor TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,object_id) REFERENCES sources(ns,id),
 FOREIGN KEY(ns,actor) REFERENCES principals(ns,id)
);
CREATE TABLE graph_edges (
 ns TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'graph_edge' CHECK(kind='graph_edge'),
 from_id TEXT NOT NULL, from_kind TEXT NOT NULL CHECK(from_kind IN ('atom','entity','event','source')),
 to_id TEXT NOT NULL, to_kind TEXT NOT NULL CHECK(to_kind IN ('atom','entity','event','source')),
 relation_type TEXT NOT NULL,
 epistemic TEXT NOT NULL CHECK(epistemic IN ('DIRECT_OBSERVATION','USER_REPORTED',
 'DOCUMENT_ASSERTION','MODEL_INFERENCE','HYPOTHESIS','DERIVED_AGGREGATE')),
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','RETRACTED','UNRESOLVED')),
 scope TEXT NOT NULL, source_span_id TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_to TEXT, producer_revision TEXT NOT NULL, commit_seq INTEGER NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,id,kind) REFERENCES objects(ns,id,kind),
 FOREIGN KEY(ns,from_id,from_kind) REFERENCES objects(ns,id,kind),
 FOREIGN KEY(ns,to_id,to_kind) REFERENCES objects(ns,id,kind),
 FOREIGN KEY(relation_type) REFERENCES relation_types(name),
 FOREIGN KEY(ns,source_span_id) REFERENCES source_spans(ns,id),
 CHECK(NOT (from_id=to_id AND from_kind=to_kind)), CHECK(valid_to IS NULL OR valid_from<valid_to),
 CHECK(relation_type<>'HYPOTHESIZES_CAUSE' OR epistemic IN ('HYPOTHESIS','MODEL_INFERENCE')),
 CHECK(relation_type<>'VERIFIED_CAUSE' OR epistemic IN
 ('DIRECT_OBSERVATION','USER_REPORTED','DOCUMENT_ASSERTION'))
);
CREATE TABLE graph_edge_support (
 ns TEXT NOT NULL, edge_id TEXT NOT NULL, span_id TEXT NOT NULL, revision TEXT NOT NULL,
 PRIMARY KEY(ns,edge_id,span_id), FOREIGN KEY(ns,edge_id) REFERENCES graph_edges(ns,id),
 FOREIGN KEY(ns,span_id) REFERENCES source_spans(ns,id)
);
CREATE TABLE graph_manifests (
 ns TEXT NOT NULL, id TEXT NOT NULL, canonical_seq INTEGER NOT NULL,
 security_epoch INTEGER NOT NULL, capability TEXT NOT NULL CHECK(capability='graph'),
 revision TEXT NOT NULL, source_digest TEXT NOT NULL, entries_digest TEXT NOT NULL,
 entry_count INTEGER NOT NULL CHECK(entry_count>=0), created_at TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);
CREATE INDEX object_scopes_by_object ON object_scopes(ns,object_id,security_epoch);
CREATE INDEX graph_edges_by_from ON graph_edges(ns,from_id);
CREATE INDEX graph_edges_by_to ON graph_edges(ns,to_id);
CREATE INDEX graph_edge_support_by_span ON graph_edge_support(ns,span_id);
