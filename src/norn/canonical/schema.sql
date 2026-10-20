CREATE TABLE namespaces (
 ns TEXT PRIMARY KEY, tenant TEXT NOT NULL, workspace TEXT NOT NULL, partition TEXT NOT NULL,
 commit_seq INTEGER NOT NULL DEFAULT 0 CHECK(commit_seq>=0),
 security_epoch INTEGER NOT NULL DEFAULT 0 CHECK(security_epoch>=0),
 UNIQUE(tenant,workspace,partition), CHECK(ns=tenant||'/'||workspace||'/'||partition)
);
CREATE TABLE schema_migrations (
 version INTEGER PRIMARY KEY, digest TEXT NOT NULL, applied_at TEXT NOT NULL, backup_ref TEXT
);
CREATE TABLE migration_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), dirty INTEGER NOT NULL);
INSERT INTO migration_state VALUES(1,0);
CREATE TABLE principals (
 ns TEXT NOT NULL, id TEXT NOT NULL, external_auth_subject TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);
CREATE TABLE scope_grants (
 ns TEXT NOT NULL, id TEXT NOT NULL, principal_id TEXT NOT NULL, scope TEXT NOT NULL,
 operation TEXT NOT NULL CHECK(operation IN ('READ','WRITE','ADMIN')),
 decision TEXT NOT NULL CHECK(decision IN ('GRANT','REVOKE')), security_epoch INTEGER NOT NULL,
 recorded_at TEXT NOT NULL, actor TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,principal_id) REFERENCES principals(ns,id),
 FOREIGN KEY(ns,actor) REFERENCES principals(ns,id)
);
CREATE TABLE retention_policies (
 ns TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL, policy TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);
CREATE TABLE objects (
 ns TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL,
 PRIMARY KEY(ns,id), UNIQUE(ns,id,kind), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);
CREATE TABLE sources (
 ns TEXT NOT NULL, id TEXT NOT NULL, producer TEXT NOT NULL, kind TEXT NOT NULL,
 authority_class TEXT NOT NULL CHECK(authority_class='UNVERIFIED'), policy_id TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,policy_id) REFERENCES retention_policies(ns,id)
);
CREATE TABLE source_versions (
 ns TEXT NOT NULL, id TEXT NOT NULL, source_id TEXT NOT NULL, digest TEXT NOT NULL,
 byte_length INTEGER NOT NULL CHECK(byte_length>0 AND byte_length<=1048576),
 media_type TEXT NOT NULL CHECK(media_type='text/plain;charset=utf-8'),
 content_uri TEXT NOT NULL, created_by TEXT NOT NULL, recorded_at TEXT NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,source_id) REFERENCES sources(ns,id),
 FOREIGN KEY(ns,created_by) REFERENCES principals(ns,id), CHECK(id=digest AND content_uri=digest)
);
CREATE TABLE source_spans (
 ns TEXT NOT NULL, id TEXT NOT NULL, version_id TEXT NOT NULL,
 start_byte INTEGER NOT NULL CHECK(start_byte>=0), end_byte INTEGER NOT NULL,
 digest TEXT NOT NULL, encoding TEXT NOT NULL CHECK(encoding='utf-8'),
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,version_id) REFERENCES source_versions(ns,id),
 CHECK(end_byte>start_byte)
);
CREATE TABLE authority_events (
 ns TEXT NOT NULL, id TEXT NOT NULL, source_id TEXT NOT NULL, purpose TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('APPROVED','REVOKED')), actor TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_to TEXT, recorded_seq INTEGER NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,source_id) REFERENCES sources(ns,id),
 FOREIGN KEY(ns,actor) REFERENCES principals(ns,id), CHECK(valid_to IS NULL OR valid_from<valid_to)
);
CREATE TABLE entities (
 ns TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL, external_key TEXT,
 provisional_span_id TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,provisional_span_id) REFERENCES source_spans(ns,id), UNIQUE(ns,external_key)
);
CREATE TABLE entity_aliases (
 ns TEXT NOT NULL, id TEXT NOT NULL, entity_id TEXT NOT NULL, label TEXT NOT NULL,
 span_id TEXT NOT NULL, PRIMARY KEY(ns,id), FOREIGN KEY(ns,entity_id) REFERENCES entities(ns,id),
 FOREIGN KEY(ns,span_id) REFERENCES source_spans(ns,id)
);
CREATE TABLE identity_events (
 ns TEXT NOT NULL, id TEXT NOT NULL, left_id TEXT NOT NULL, right_id TEXT NOT NULL,
 decision TEXT NOT NULL CHECK(decision IN ('SAME_AS','DIFFERENT')), span_id TEXT NOT NULL,
 reviewer TEXT NOT NULL, recorded_seq INTEGER NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,left_id) REFERENCES entities(ns,id),
 FOREIGN KEY(ns,right_id) REFERENCES entities(ns,id),
 FOREIGN KEY(ns,span_id) REFERENCES source_spans(ns,id),
 FOREIGN KEY(ns,reviewer) REFERENCES principals(ns,id), CHECK(left_id<>right_id)
);
CREATE TABLE events (
 ns TEXT NOT NULL, id TEXT NOT NULL, producer TEXT NOT NULL, occurrence TEXT NOT NULL,
 source_version TEXT NOT NULL, event_time TEXT NOT NULL CHECK(json_valid(event_time)),
 observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL, commit_seq INTEGER NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 PRIMARY KEY(ns,id), UNIQUE(ns,producer,occurrence), FOREIGN KEY(ns,id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,source_version) REFERENCES source_versions(ns,id)
);
CREATE TABLE deliveries (
 ns TEXT NOT NULL, producer TEXT NOT NULL, delivery TEXT NOT NULL, payload_digest TEXT NOT NULL,
 event_id TEXT NOT NULL, received_at TEXT NOT NULL,
 PRIMARY KEY(ns,producer,delivery), FOREIGN KEY(ns,event_id) REFERENCES events(ns,id)
);
CREATE TABLE atoms (
 ns TEXT NOT NULL, id TEXT NOT NULL, event_id TEXT NOT NULL, subject_ref TEXT NOT NULL,
 predicate TEXT NOT NULL, object_type TEXT NOT NULL
 CHECK(object_type IN ('TEXT','INTEGER','DECIMAL','BOOLEAN','TIME','ENTITY_REF','JSON_NULL')),
 object_value TEXT NOT NULL CHECK(json_valid(object_value)),
 object_ref TEXT,
 qualifiers TEXT NOT NULL CHECK(json_valid(qualifiers)), qualifier_schema INTEGER NOT NULL CHECK(qualifier_schema=1),
 origin TEXT CHECK(origin IN ('DIRECT_OBSERVATION','USER_REPORTED','DOCUMENT_ASSERTION',
 'MODEL_INFERENCE','HYPOTHESIS','DERIVED_AGGREGATE')),
 external_epistemic TEXT NOT NULL CHECK(external_epistemic IN ('DIRECT_OBSERVATION','USER_REPORTED',
 'DOCUMENT_ASSERTION','MODEL_INFERENCE','HYPOTHESIS','DERIVED_AGGREGATE','RETRACTED')),
 source_span_id TEXT NOT NULL, extraction_revision TEXT NOT NULL,
 initial_status TEXT NOT NULL CHECK(initial_status IN ('ACTIVE','RETRACTED','UNRESOLVED')),
 commit_seq INTEGER NOT NULL, PRIMARY KEY(ns,id), FOREIGN KEY(ns,id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,subject_ref) REFERENCES entities(ns,id),
 FOREIGN KEY(ns,object_ref) REFERENCES entities(ns,id),
 CHECK((object_type='ENTITY_REF' AND object_ref IS NOT NULL) OR
       (object_type<>'ENTITY_REF' AND object_ref IS NULL)),
 FOREIGN KEY(ns,event_id) REFERENCES events(ns,id),
 FOREIGN KEY(ns,source_span_id) REFERENCES source_spans(ns,id)
);
CREATE TABLE atom_support (
 ns TEXT NOT NULL, id TEXT NOT NULL, atom_id TEXT NOT NULL, span_id TEXT NOT NULL,
 support_kind TEXT NOT NULL CHECK(support_kind IN ('PRIMARY','ADDITIONAL')),
 independence_group TEXT NOT NULL, producer_revision TEXT NOT NULL, recorded_seq INTEGER NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,atom_id) REFERENCES atoms(ns,id),
 FOREIGN KEY(ns,span_id) REFERENCES source_spans(ns,id)
);
CREATE TABLE assertion_events (
 ns TEXT NOT NULL, id TEXT NOT NULL, atom_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','RETRACTED','UNRESOLVED')),
 valid_from TEXT NOT NULL, valid_to TEXT, recorded_seq INTEGER NOT NULL,
 recorded_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,atom_id) REFERENCES atoms(ns,id),
 FOREIGN KEY(ns,actor) REFERENCES principals(ns,id), CHECK(valid_to IS NULL OR valid_from<valid_to)
);
CREATE TABLE relationships (
 ns TEXT NOT NULL, id TEXT NOT NULL, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
 relation_type TEXT NOT NULL CHECK(relation_type IN ('SUPERSEDES','CONTRADICTS','ADDITIONAL_EVIDENCE')),
 epistemic TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_to TEXT, producer_revision TEXT NOT NULL, commit_seq INTEGER NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,from_id) REFERENCES atoms(ns,id), FOREIGN KEY(ns,to_id) REFERENCES atoms(ns,id),
 CHECK(from_id<>to_id), CHECK(valid_to IS NULL OR valid_from<valid_to)
);
CREATE TABLE edge_support (
 ns TEXT NOT NULL, edge_id TEXT NOT NULL, atom_id TEXT NOT NULL, span_id TEXT NOT NULL,
 revision TEXT NOT NULL, PRIMARY KEY(ns,edge_id,atom_id),
 FOREIGN KEY(ns,edge_id) REFERENCES relationships(ns,id), FOREIGN KEY(ns,atom_id) REFERENCES atoms(ns,id),
 FOREIGN KEY(ns,span_id) REFERENCES source_spans(ns,id)
);
CREATE TABLE corrections (
 ns TEXT NOT NULL, id TEXT NOT NULL, prior_atom_id TEXT NOT NULL, new_atom_id TEXT NOT NULL,
 class TEXT NOT NULL CHECK(class IN ('SUPERSEDES','CONTRADICTS','ADDITIONAL_EVIDENCE')),
 scope TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT,
 recorded_seq INTEGER NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,id) REFERENCES relationships(ns,id),
 FOREIGN KEY(ns,prior_atom_id) REFERENCES atoms(ns,id), FOREIGN KEY(ns,new_atom_id) REFERENCES atoms(ns,id),
 FOREIGN KEY(ns,actor) REFERENCES principals(ns,id), CHECK(valid_to IS NULL OR valid_from<valid_to)
);
CREATE TABLE outbox (
 ns TEXT NOT NULL, id TEXT NOT NULL, commit_seq INTEGER NOT NULL, operation TEXT NOT NULL,
 objects TEXT NOT NULL CHECK(json_valid(objects)), payload_digest TEXT NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 PRIMARY KEY(ns,id), UNIQUE(ns,commit_seq), FOREIGN KEY(ns) REFERENCES namespaces(ns)
);

CREATE TABLE deletion_requests (
 ns TEXT NOT NULL, id TEXT NOT NULL, selector_id TEXT NOT NULL, policy_id TEXT NOT NULL,
 policy_version INTEGER NOT NULL CHECK(policy_version=1), requested_by TEXT NOT NULL,
 requested_at TEXT NOT NULL, serving_denied_seq INTEGER NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,selector_id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,policy_id) REFERENCES retention_policies(ns,id),
 FOREIGN KEY(ns,requested_by) REFERENCES principals(ns,id)
);
CREATE TABLE tombstones (
 ns TEXT NOT NULL, object_id TEXT NOT NULL, request_id TEXT NOT NULL,
 effective_seq INTEGER NOT NULL, PRIMARY KEY(ns,object_id,request_id),
 FOREIGN KEY(ns,object_id) REFERENCES objects(ns,id), FOREIGN KEY(ns,request_id) REFERENCES deletion_requests(ns,id)
);
CREATE TABLE purge_obligations (
 ns TEXT NOT NULL, request_id TEXT NOT NULL, artifact TEXT NOT NULL, selector TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status='PENDING'), PRIMARY KEY(ns,request_id,artifact,selector),
 FOREIGN KEY(ns,request_id) REFERENCES deletion_requests(ns,id)
);
