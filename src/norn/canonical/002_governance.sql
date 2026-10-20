CREATE TABLE derivations (
 ns TEXT NOT NULL, id TEXT NOT NULL, output_id TEXT NOT NULL, revision TEXT NOT NULL,
 config_digest TEXT NOT NULL, created_at TEXT NOT NULL,
 validation_state TEXT NOT NULL CHECK(validation_state='UNVALIDATED'),
 PRIMARY KEY(ns,id), FOREIGN KEY(ns,id) REFERENCES objects(ns,id),
 FOREIGN KEY(ns,output_id) REFERENCES objects(ns,id)
);
CREATE TABLE derivation_inputs (
 ns TEXT NOT NULL, derivation_id TEXT NOT NULL, input_id TEXT NOT NULL,
 source_digest TEXT NOT NULL, independence_group TEXT NOT NULL,
 PRIMARY KEY(ns,derivation_id,input_id), FOREIGN KEY(ns,derivation_id) REFERENCES derivations(ns,id),
 FOREIGN KEY(ns,input_id) REFERENCES objects(ns,id)
);
