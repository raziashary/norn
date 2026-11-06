CREATE TABLE atom_support_times (
 ns TEXT NOT NULL, support_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 PRIMARY KEY(ns,support_id), FOREIGN KEY(ns,support_id) REFERENCES atom_support(ns,id)
);
INSERT INTO atom_support_times
 SELECT x.ns,x.id,COALESCE(e.recorded_at,v.recorded_at) FROM atom_support x
 JOIN source_spans s ON s.ns=x.ns AND s.id=x.span_id
 JOIN source_versions v ON v.ns=s.ns AND v.id=s.version_id
 LEFT JOIN events e ON e.ns=x.ns AND e.commit_seq=x.recorded_seq;
CREATE INDEX atoms_by_event ON atoms(ns,event_id);
CREATE INDEX atoms_by_subject ON atoms(ns,subject_ref,predicate);
CREATE INDEX atoms_by_span ON atoms(ns,source_span_id);
CREATE INDEX atom_support_by_atom ON atom_support(ns,atom_id);
CREATE INDEX atom_support_by_span ON atom_support(ns,span_id);
CREATE INDEX assertion_events_by_atom ON assertion_events(ns,atom_id,recorded_seq);
CREATE INDEX relationships_by_from ON relationships(ns,from_id);
CREATE INDEX relationships_by_to ON relationships(ns,to_id);
CREATE INDEX source_spans_by_version ON source_spans(ns,version_id);
CREATE INDEX source_versions_by_source ON source_versions(ns,source_id);
CREATE INDEX events_by_source_version ON events(ns,source_version);
CREATE INDEX entity_aliases_by_entity ON entity_aliases(ns,entity_id);
CREATE INDEX derivation_inputs_by_input ON derivation_inputs(ns,input_id);
