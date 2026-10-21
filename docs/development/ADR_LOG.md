# Architecture and research decision log

## ADR-0019 — P03 local reader implementation details

Measured-error correction21 October2026: completed development004 exposed a public adapter
bug: explicit predicate detection used only present sources and bypassed the declared
compound cue. A release-and-rollback question with only release evidence lost its rollback
prerequisite. Main confirmed the public input and sole end reviewer independently confirmed
the mechanism. Interpreter v3 derives requested fields from the frozen public schema and
matching question cues, unioned with public-observed predicate extensions; missing evidence
cannot redefine the question. Regression includes actual public R0 recall of qualified
partial support. This is an in-scope T08/T11 bug fix, no gold input, label/threshold/model
tuning, or new semantic framework. Full005 comparison completed with the new source hash in E-P03-003;
completed004, its valid report/ANN and006 installed wheel remain version-scoped evidence.

Final scope refinement21 October2026: field conflicts require identical canonical subject,
qualifiers and event time (or explicit canonical contradiction), preserving unresolved
same-name ambiguity. Projection records/readback retain qualifiers. The public-only query
interpreter v2 treats chain roots as retrieval cues, removes a global subject filter that
excluded neighboring steps, and leaves typed-path sufficiency unestablished rather than
claiming one field proves a chain. No gold, labels, thresholds or new graph mechanism are
introduced. ANN reports serialized index/vector bytes separately from observed whole-process
working sets while original/reopened indices and serialized copies coexist; those observations
are not isolated native allocation or simultaneous machine peaks. These refinements implement
P03-T04/T07/T08/T11 scope and evidence requirements.

Implementation refinement21 October2026: model compatibility fingerprints bind both
publisher assets and the approved inference method (prefixes,512-token limit, dimension,
masked FP64 accumulation/unit normalization and FP32 output, or raw FP32 rerank logits).
Existing arithmetic/weights are unchanged; method fields now drive prefix/length/dimension
checks and appear in run manifests. Runtime replies expose used model fingerprints.
The canonical snapshot reader receives expected revisions from the projection owner,
selects compatible generations and never imports retrieval/model policy. Backup verifies
and preserves legacy artifact integrity without advertising legacy geometry as current.
These are MDP geometry/readback obligations within ADR-0017, not new models or dependencies.
Final current-source proof and legacy-generation controls are recorded in E-P03-003; E-P03-001 retains implementation history.

- **Status:** ACCEPTED implementation choices within MDP read-flow and ADR-0017/0018.
- **Question:** How do the approved local baseline and projection readers expose their exact scope?
- **Why:** Ready metadata alone cannot establish source/model coherence, and a citation is not natural-language entailment.
- **Options:** MDP's explicit structured prerequisites and immutable local artifacts; unsupported implicit semantic adjudication.
- **Recommendation / decision:** Runtime requested fields/predicates are explicit host inputs. A benchmark query interpreter may derive them only from public question text/schema; no gold/family labels. Unknown semantic prerequisites remain MISSING_CASE_INPUT. Full local journal replay builds immutable per-record lexical/vector artifacts, exact ordered readbacks and additive schema3 snapshots. Current canonical sequence/security must still match before publication. Actual evidence packet serialization, including status and locators, is token-counted. Model-enabled paired baselines use the same pinned E5 tokenizer for every arm; asset-free R0 uses declared Unicode word counting as a separate profile. Native workers use bounded JSON frames and one resident model at a time; switching releases the previous process. No automatic retries or model fallback.
- **What affects what:** P03-T01/T03 supporting request/asset files; T08 field sufficiency/assembly; T09 manifest/artifact/backup readers; T10 engine lifecycle and telemetry; T11 public-only adapter interpretation and token manifests. Public source records retain distinct canonical occurrences; published IDs are mapped back only after canonical source readback, without alias-based identity merges. This is a declared common-input source-record ingestion profile, not perfect event extraction.
- **My answer (editable):** Main implementation detail, grounded in the accepted MDP and owner-approved dependencies/schema/workers. No new external contract or research threshold is selected.
- **Authority:** MDP Conventional baseline details, Baseline scoring and token-bound assembly contracts, Sufficiency and uncertainty; blueprint I1–I10; ADR-0017/0018.
- **Verification:** E-P03-003:131 tests, actual R0–R3 public consumers/540 paired results, installed reopen/correction/revoke/native controls and sole end review resolved. All12 cards close locally; scientific outcome INCONCLUSIVE, broader semantics remain unestablished.

## ADR-0018 — Bounded native model workers

- **Status:** ACCEPTED by owner on21 October2026.
- **Question:** How can query cancellation and deadlines bound native ONNX execution and clean owned resources?
- **Why:** Cooperative Python cancellation alone cannot reliably interrupt a blocked native call. P03-T10 requires one actual budget owner and no orphan work.
- **Options:** Isolated reusable local worker processes; in-process ONNX cooperative cancellation.
- **Recommendation / decision:** Standard-library spawned worker processes, explicit pinned local files, bounded input/output messages, serial inference under the query owner, deadline/cancellation termination of only owned workers, and deterministic close/join. No worker network, credentials, retry/fallback or new dependency. Main owns all code/tests; this does not authorize extra agents.
- **What affects what:** Embedding/rerank native runtime, query-budget owner, model initialization/calls/failure accounting and engine lifecycle. Pure lexical/exact paths remain usable without loading optional models. Implementation keeps one resident model worker, reusing it until a model switch; operations remain serial and actual memory/cold/warm costs are disclosed (ADR-0019).
- **My answer (editable):** Owner answered “Approve isolated model workers (Recommended)” through question reply `call_6ad6fbb8a90940b385f77f46c0ec80f0`.
- **Authority:** P03 mandate, explicit owner answer, P03-T10 and blueprint I8.
- **Verification:** Actual models, startup/normal inference/deadline/cancel/error/close controls and process cleanup are required; no helper-only or fake response substitutes. Executed actual installed native controls and cleanup PASS in E-P03-003; no general OS hang/capacity guarantee.

## ADR-0017 — P03 mandate, approved retrieval assets and durable projections

- **Status:** ACCEPTED by owner on21 October2026; implementation IN_PROGRESS.
- **Question:** Which real dense/reranker/ANN assets and persistence changes may P03 use?
- **Why:** P03 exit requires actual R0–R3 and reopened local ready snapshots. ADR-0007 previously left model/backend choices unresolved; the start adversary also identified missing schema ownership in P03-T09.
- **Options:** Pinned local FP32 ONNX models; explicitly different quantized condition; different compute/models. Additive canonical schema3 versus external projection persistence.
- **Recommendation / decision:** Owner approved FP32 `intfloat/multilingual-e5-small` (MIT; revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`) and `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (Apache-2.0; revision `1427fd652930e4ba29e8149678df786c240d8825`). Use optional retrieval dependencies NumPy2.5.4/tokenizers0.23.3/ONNX Runtime1.31.0/faiss-cpu1.15.1; no generative inference or Groq call. Query/passage prefixing, mean pooling, normalized384-dimensional geometry, published tokenizers and FP32 artifacts are pinned. Exact exhaustive same-vector search remains the ANN diagnostic; FAISS approximation is separately measured. Models load only by explicit enabled local configuration; missing assets cannot yield fake vectors or hidden fallback.
- **What affects what:** P03-T01–T12, optional package extra, model acquisition/manifest, dense/rerank/ANN adapters, tokenizer budgets and fair development reports. Owner approved additive schema3 projection manifests/readback entries/ready snapshots and extending P03-T09 to the migration/database owner. Existing canonical records remain immutable; populated upgrade must verify a restorable backup first. No meaningful existing store is used for tests.
- **My answer (editable):** Owner answered “Approve FP32 models and optional dependencies (Recommended)” and “Approve additive schema3 (Recommended)” through question reply `call_3f0742fe8fa24d21a00abe2b3a5c3685`. Original P02 commit publication was explicitly authorized and completed; P03 GO authorizes implementation, not another later main push.
- **Authority:** Current P03 goal, explicit owner answers, MDP P03/read-flow/projection contracts and blueprint I1–I10/Stage0.
- **Verification:** Metadata preflight confirms published revisions/artifacts/licenses and cp314 Windows wheels. Laptop: Ryzen3 4300U/4threads/7.4GB RAM, integrated Radeon,109GB free disk, observed0.7GB free RAM. CPU-only/one model operation at a time, bounded batches/deadlines; actual memory, latency and failures must be recorded, no performance claim inferred. Main implements/tests; sole start adversary and end reviewer GPT6 Luna Medium. Final executed proof E-P03-003; local engineering completion, scientific superiority INCONCLUSIVE.
- **Sources:** [E5 model](https://huggingface.co/intfloat/multilingual-e5-small), [reranker](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), publisher model APIs/file hashes, [ONNX Runtime package](https://pypi.org/project/onnxruntime/1.31.0/), [FAISS package](https://pypi.org/project/faiss-cpu/1.15.1/). Revisions/licenses were read before acquisition; acquisition and initial actual native inference now verified in E-P03-001. Final local retrieval proof and owning gates pass in E-P03-003; cross-phase obligations remain partial.

## ADR-0016 — P02 end-review corrections before publication

- **Status:** RESOLVED before publication; sole end reviewer verified owner fixes and actual consumer assertions.
- **Question:** How must calibration prove partition custody and qualified partial answers prove support?
- **Why:** Sole Luna Medium end reviewer found that a caller-supplied calibration string could relabel test data, and that the initial scorer lacked a tested qualified-partial path. Main confirmed both by tracing the actual CLI/scorer bodies.
- **Options:** Leave untrusted numeric demos outside promoted artifacts; bind fitting to actual authorized run artifacts. Treat every incomplete answer as error; separately score supported subsets and explicit unknowns.
- **Recommendation / decision:** Calibration CLI reopens validator-checked calibration/calibrator runs, binds fitted values to manifest/completion/arm lineage and consumes actual emitted confidence/target rows. A named constant0.5 diagnostic control supplies math-only forecasts; no model or provider. Validator regenerates deterministic world/partition/source/gold lineage, so relabeling and rehashing smoke data still fails. Qualified partial gold has supported subsets and explicit missing fields; result/scorer enforce them and distinguish full completeness, partial usefulness and status accuracy. The existing42 reviewed cases keep identical canonical gold/source bindings; optional inapplicable gold annotations are omitted from serialization. One additional unaudited E9 partial case exercises the fifth status.
- **What affects what:** P02-T04/T08/T09/T10/T11, adapter result/Gold/metrics/calibration CLI/tests/docs. P01 contracts/schema are unchanged. Earlier P02 runs are invalidated by changed code digest and must be regenerated; their receipts remain historical evidence.
- **My answer (editable):** Main resolves confirmed in-scope defects against blueprint17.3/23.2 and MDP evaluation; this does not invent an owner response or authorize a new dependency, study or push.
- **Authority:** Existing P02 mandate, end-review findings, blueprint qualified partial answers/calibration custody and accepted ADR-0015.
- **Verification:** Focused partial-support/unknown/overclaim controls, actual calibration CLI and rehashed partition-relabel rejection, retained42-case pack hash, full regression/build/installed smoke and same-reviewer resolution PASS in E-P02-003; direct/relative/imported-dynamic-capability aliases have dedicated rejection controls.

## ADR-0015 — P02 partition unit and transfer boundary

- **Status:** ACCEPTED by owner on21 October2026.
- **Question:** Does scenario-family/entity partitioning require holding out whole E1–E14 task categories, or independent scenario/entity instances within each category?
- **Why:** Every failure stratum needs custody coverage; the blueprint's wording leaves the grouping level ambiguous.
- **Options:** Disjoint scenario/entity instances in every category; hold out entire task categories and study category transfer separately.
- **Recommendation / decision:** Group whole scenario/entity instances before wording variation, with all14 categories in each tier. The generator fixes disjoint cluster/entity IDs before paraphrases. No template-level or task-category generalization claim follows.
- **What affects what:** P02-T04 partitions, generator/source/gold manifests and later study interpretation. Smoke/development/calibration/locked roles remain distinct; no locked execution or threshold approval is granted.
- **My answer (editable):** Owner answered “Approve disjoint instances in every category (Recommended)” to question reply `call_9b7522e72d1b4d489d220db051b9ddf3`.
- **Authority:** Explicit owner clarification of blueprint22.3 and RESEARCH_PROTOCOL dataset construction step5.
- **Verification:** Disjoint instance/entity/cluster tests across all four tiers, with every E1–E14 category represented; final phase receipt records commands. This approval does not change the reviewed42-case pack.

## ADR-0014 — P02 mandate, benchmark ownership and editor configuration

- **Status:** ACCEPTED_SCOPE; grounded implementation details; owner human sample reviewed.
- **Question:** What does the P02 GO authorize and how is its independent benchmark kept separate?
- **Why:** Owner explicitly requested P02-T01 through T11. P01 is published at4618156. Owner also added BasedPyright settings inside the mypy table, then confirmed their intended analyzer through the question tool.
- **Options:** Reuse the accepted Python/std-library environment and planned benchmark paths; introduce foreign tooling or conflate controls with real retrieval arms.
- **Recommendation / decision:** Original `benchmark/` evaluator package, standard-library typed fixtures/rendering/JSON artifacts/adapters/metrics/statistics/CLI; no foreign source copying, runtime-to-evaluator import, provider call or new dependency. Published inputs and evaluator-only gold/labels remain distinct. Installed packaging includes the planned benchmark CLI; P01 runtime/schema stay unchanged. Move the owner's diagnostics into `[tool.basedpyright]`, preserving each value, without installing that analyzer or weakening strict mypy. Official configuration reference: https://docs.basedpyright.com/latest/configuration/config-files/.
- **What affects what:** All eleven P02 cards, packaging and editor table. P02 controls establish harness mechanics; R0-R10 algorithms, P03 retrieval and scientific efficacy remain later work. Code-first truth is constructed truth, not independent human annotation. Prepare concrete stratified audit material and require real human provenance; disputed cases need independent double annotation/adjudication before an audited claim.
- **My answer (editable):** Owner gave P02 GO and selected BasedPyright editor settings. On21 October2026 the owner personally reviewed and agreed with all42 cases in pack `ae3dd3091f60b15124ab3a6cae517c9ecb8a696575f2503de2c93372a6afbb9b` through question reply `call_2127135824264567b9273ce521f44fa9`. The pack was recomputed unchanged before42 digest-bound HUMAN judgments were recorded. No disputes were reported; no model reviewer is called a human. Other details implement the existing MDP rather than inventing owner answers.
- **Authority:** Current P02 goal, question-tool response, MDP P02/evaluation, RESEARCH_PROTOCOL dataset custody and blueprint22–23.
- **Verification:** Start adversary GPT6 Luna Medium read-only audit complete; no ambient credential-like variables, no .env read. Current worktree has only the owner's diagnostic additions at entry. Exact tests and evidence will be recorded as executed.

Date: 20 October 2026 (Asia/Bangkok). Status, authority, owner answer, and verification are separate fields. A proposed recommendation is not a decision. Read the latest user instruction and editable owner answer before dependent implementation. Preserve prior answers when superseding; retract an incorrect claim visibly rather than deleting its history.

## ADR-0001 — Scope and document ownership

- **Status:** ACCEPTED.
- **Question:** Where does the development suite live and which document owns detailed design?
- **Why:** The user explicitly requested `docs/development` and a substantially detailed MDP using Palladion/Arcana as format references.
- **Options:** One detailed MDP with supporting role-specific anchors; fragmented subsystem specifications.
- **Recommendation / decision:** One canonical folder; algorithms, schema proposals, flows, module ownership, phases, and atomic cards stay inside MASTER_DEV_PLAN. Supporting documents link to that design.
- **What affects what:** All suite links and future recovery. No source files, runtime dependencies, instructions/configuration files, or external systems are changed by this choice.
- **My answer (editable):** User's current request authorizes this documentation scope and location; this is a scope record, not an invented quotation.
- **Authority:** Current user objective, 20 October 2026.
- **Verification:** G-DOC PASS, E-DOC-001 through E-DOC-004; complete documentation scope validated and independently reviewed. No runtime approval or behavior inferred.

## ADR-0002 — Runtime and package layout

- **Status:** ACCEPTED for P01; timezone data decision recorded separately.
- **Question:** Adopt a Python modular research package under `src/norn/`, managed with uv?
- **Why:** The blueprint uses Python-oriented examples and requires training/evaluation. Palladion offers Python reference code. At the initial P00 decision, no runtime manifest existed in Norn.
- **Options:** Python/uv proposal; another user-selected runtime/toolchain; separate runtime and training languages after a demonstrated need.
- **Recommendation:** Python/uv, one package and in-process pilot; pin compatible versions after environment checks. MDP paths are proposed against this layout, not claims that files exist. If declined, update path mappings before implementation.
- **What affects what:** P01 packaging, type contracts, CLI, testing commands, optional training adapters. No library/version/model/provider is selected by this recommendation.
- **Prior answer record:** Pending owner direction before P01 runtime bootstrap (before the setup amendment).
- **My answer (editable):** Owner approved the recommended setup through the question tool: `src/norn/`, standard-library SQLite/dataclasses/argparse runtime, Hatchling, pytest, Ruff, mypy and build, reusing the existing uv environment. Earlier setup-only answer is preserved above as the prior answer record. Timezone data was subsequently found absent on this Windows host; the owner approved tzdata in the subsequent question-tool response (ADR-0012).
- **Amendment authority:** User setup instruction, 20 October 2026; see ADR-0010.
- **Authority:** Blueprint “Suggested project organization” is illustrative; the later owner question-tool response and ADR-0012 authorize P01 implementation.
- **Verification:** P01-T01, G-CONTRACT; fresh environment and installed consumer proof required.

## ADR-0003 — Evidence, event identity, and independent state axes

- **Status:** ACCEPTED for the synthetic P01 pilot; see owner answer below.
- **Question:** Adopt the MDP's typed event/assertion/edge/source contracts and explicit retraction handling?
- **Why:** Blueprint “Epistemic types” includes RETRACTED while later calling epistemic and lifecycle state orthogonal. Retraction changes serving eligibility without changing how the original assertion was obtained.
- **Options:** Rewrite epistemic origin to RETRACTED; preserve original origin and append a retraction status event with a compatibility representation of RETRACTED.
- **Recommendation:** Preserve all seven blueprint values at import/export; internally store `epistemic_origin` plus append-only `assertion_status` events. RETRACTED inputs require a known original origin or UNKNOWN-origin quarantine, not fabricated observation authority. Effective API state can expose RETRACTED plus original origin. Seek owner confirmation before freezing this interpretation.
- **What affects what:** P01 contracts/schema, P03 evidence gate, P08 consolidation, P09 historical recall. No shipped contract exists yet.
- **Prior answer record:** Pending before the P01 question-tool answers.
- **My answer (editable):** Owner approved preserving original epistemic origin with append-only retraction status, including all seven blueprint import/export values. Status ACCEPTED for P01; unknown original origin remains quarantined rather than fabricated.
- **Authority:** Blueprint “Memory ontology,” “Three orthogonal kinds of state,” and universal decision escalation.
- **Verification:** P01-T02/P01-T03, G-CONTRACT/G-TEMPORAL; history/origin round-trip controls.

## ADR-0004 — Retention, immutable evidence, and physical deletion

- **Status:** ACCEPTED for the synthetic P01 pilot.
- **Question:** What source content, audit metadata, backups, traces, and learned parameters must be purged, on which schedule?
- **Why:** Immutable history and authorized erasure must be reconciled explicitly. A tombstone blocks serving but is not proof of erasure everywhere.
- **Options:** Synthetic-only pilot with explicit test purge policies; production retention design after requirements; personalized online training with a separately approved unlearning/retraining contract.
- **Recommendation:** Synthetic-only pilot. Append denial/tombstone controls first; preserve only permitted minimal audit metadata. Track purge acknowledgments by artifact and backup generation. Do not train on private personal data or claim parameter unlearning without a measured policy.
- **What affects what:** P01 deletion model, P08 aggregate invalidation, P11 worker/cache/backup recovery, P12 privacy proofs. Exact time limits remain unset until owner requirements.
- **Prior answer record:** Pending before the P01 question-tool answers.
- **My answer (editable):** Owner approved a synthetic-only P01 pilot, local SQLite/blobs, immediate serving denial with explicit pending physical-purge obligations, and no personal-data training. Status ACCEPTED for this pilot; production schedules and parameter erasure remain unapproved.
- **Authority:** Blueprint “Deletion, revocation, and retention,” open Q12, I1/I5/I6.
- **Verification:** G-DELETION; denied serving during outages plus explicit physical-purge reconciliation and restore controls.

## ADR-0005 — Time, snapshots, and query interpretation

- **Status:** ACCEPTED for the synthetic P01 pilot.
- **Question:** Freeze UTC-aware stored instants, explicit source timezone/precision, and per-namespace sequence snapshots with current security checks?
- **Why:** Event time, observation time, recorded time, valid time, and knowledge-at-time differ. An old content snapshot cannot resurrect revoked permissions.
- **Options:** Single current clock; explicit typed temporal context with declared basis and unknown/interval times.
- **Recommendation:** The MDP temporal contract; query-relative language uses the request evaluation clock and declared timezone. Unknown time remains unknown. Content uses a declared snapshot; access and erasure use current authoritative controls. Reject mixed projection versions or disclose degraded capability.
- **What affects what:** P01/P03 contracts, P06 graph eligibility, P09 replay, P11 projection publication. Cross-partition global ordering is not implied by local commit_seq.
- **Prior answer record:** Pending before the P01 question-tool answers.
- **My answer (editable):** Owner approved explicit UTC-aware event/valid/knowledge/query clocks and current ACL checks for historical reads. Status ACCEPTED for P01; valid-to is exclusive as proposed in the approved temporal semantics.
- **Authority:** Blueprint “Bitemporal reasoning,” “Snapshot/read consistency,” I6/I7.
- **Verification:** G-TEMPORAL/G-SNAPSHOT; late-arrival, DST, historical correction and mid-read revoke controls.

## ADR-0006 — Palladion reuse boundary

- **Status:** ACCEPTED for the synthetic P01 pilot.
- **Question:** Which reference components should be ported or reached through adapters?
- **Why:** Provenance, exact source resolution, hybrid baselines, manifests, scoring, and statistics are useful; Palladion memory categories, session rules, payment policy, and classifier are different contracts.
- **Options:** Copy the system; selective audited adaptation; clean implementation against source-backed contracts.
- **Recommendation:** Selective adaptation with provenance/license/source-commit receipts; no runtime dependency on a foreign checkout. Keep benchmark/agent consumers behind explicit adapters and prevent evaluation gold from entering the runtime package.
- **What affects what:** P01 utility review, P02 harness, P03 baseline, P09 consumers. Pin a verified source checkpoint; current reference checkout contains changing work.
- **Prior answer record:** Pending before the P01 question-tool answers.
- **My answer (editable):** Owner approved original Norn implementation informed by reference patterns, without copying Palladion code. Status ACCEPTED for P01. No foreign runtime dependency or code port is authorized.
- **Authority:** Current investigation accepted as planning input; no blanket code-copy authority inferred.
- **Verification:** G-REUSE, dependency/license/consumer tests and recorded fork delta before porting.

## ADR-0007 — Model, provider, compute, and optional backends

- **Status:** PARTIALLY_ACCEPTED (Groq and permitted generative model options); remaining model/compute/backend choices PROPOSED.
- **Question:** Which encoder/training backbone, token counter, hardware, provider, vector/graph backend, and resource envelope are available?
- **Why:** Fair comparisons depend on pinned models and actual budgets; credentials are not intent to call a service.
- **Options:** Local pinned assets; explicitly enabled paid/free provider; lightweight exact pilot before ANN/distributed engines.
- **Recommendation:** First prove deterministic fixtures/exact baselines; select model and backend with compatibility, language, license, and cost evidence. Keep Redis/Qdrant/Neo4j optional later treatments. No heavy per-region hypernetworks or implicit provider fallback.
- **What affects what:** P03 dense/reranker, P04 training, P06 graph, P07 generated branches, P10 compression, P11 operational adapters.
- **Prior answer record:** Pending; no download, training job, provider call, listener, or runtime dependency installation authorized by suite creation.
- **My answer (editable):** Use Groq whenever an authorized task needs generative LLM inference. Allowed options: Qwen 3.8 27B, GPT OSS 120B, GPT OSS 20B. Select explicitly per run; no default or silent fallback inferred. Verify exact Groq API identifiers/account availability before first authorized integration. Embedding/reranker/training backbones, tokenizer, compute, backends and budgets remain unresolved. The supplied key alone is not permission to call; P01 GO does not need a generative call, and any later provider integration still needs explicit enablement/budgets.
- **Amendment authority:** User model/setup instruction, 20 October 2026; ADR-0010.
- **Authority:** Blueprint I10 and staged experiments.
- **Verification:** G-BUDGET/G-RESEARCH; manifest pins, explicit enable flags, failed-attempt accounting, no-network disabled path.

## ADR-0008 — Experimental advancement and negative results

- **Status:** BLUEPRINT_CONSTRAINT.
- **Question:** Must a favored biological mechanism win to finish the research program?
- **Why:** It would invalidate the study to hide null results or keep widening budgets until a preferred arm wins.
- **Options:** Freeze only the full architecture; hierarchical experiments with retain/reject decisions.
- **Recommendation / constraint:** Preserve simpler winners. A completed valid experiment may reject a mechanism; that closes its investigation, not its efficacy gate. More expensive dependent arms need the blueprint's positive prerequisite or a separately approved exploratory question. Required unavailable arms remain explicitly unsupported, never silently omitted.
- **What affects what:** P04–P13 advancement and readiness states. Strong performance claims need locked data, defined practical effect/regression limits, uncertainty and resource comparison.
- **My answer (editable):** Blueprint requirement, not a fabricated new owner response. Numeric study thresholds remain pending pilot power estimation.
- **Authority:** Blueprint I10, “What would change our scientific conclusion?”, Stage1/2 gates.
- **Verification:** G-RESEARCH/G-CONFIRMATORY; study reports preserve failure and disabled-arm disposition.

## ADR-0009 — Pilot outbox and later operational projection track

- **Status:** ACCEPTED for the synthetic P01 pilot.
- **Question:** Preserve canonical event+outbox atomicity in the local pilot while delaying external stores?
- **Why:** Blueprint write invariants require coherent commits; its deployment sequence postpones distributed infrastructure to isolate algorithms.
- **Options:** No durable projection journal until Stage5; local transactional outbox from P01 and in-process consumers, external workers in P11.
- **Recommendation:** Local transactional outbox and idempotent in-process projections from P01/P03. P11 adds durable external delivery, leases, retries, shadow rebuilds and operational metrics without changing event identity or retrospectively crediting vendor changes as algorithmic gains.
- **What affects what:** P01 atomic schema, P03 local ready snapshot, P11 external publication. A pilot outbox row does not prove distributed recovery.
- **Prior answer record:** Pending before the P01 question-tool answers.
- **My answer (editable):** Owner approved atomic canonical event plus local outbox writes in the synthetic SQLite/blob pilot. Status ACCEPTED for P01; external projection workers remain later-phase work.
- **Authority:** Blueprint “Encoding and write pipeline,” “Pilot simplification,” “Transactional outbox,” Stage5.
- **Verification:** G-INGEST/G-SNAPSHOT/G-OPS with phase-local obligations kept separate.

## ADR-0010 — Owner setup, Groq policy, scoped publication and Phase 1 hold

- **Status:** ACCEPTED.
- **Question:** Which new owner instructions change current setup and publication scope?
- **Why:** Owner supplied a repository-root `.env` with a Groq key, `.gitignore`, and existing uv environment; requested documentation updates/publication and explicitly said to wait for GO for Phase 1.
- **Options:** Reuse owner setup and record explicit policy; recreate environment or infer a broader runtime mandate.
- **Recommendation / decision:** Reuse `.venv/`; preserve `.gitignore` excluding `.env`, `venv/`, `.venv/`. For future authorized generative inference use Groq with explicit choice among Qwen 3.8 27B, GPT OSS 120B and GPT OSS 20B. No default, silent fallback or encoder selection inferred. This task updates/publishes documentation/configuration only. Phase 1 remains WAIT_FOR_GO.
- **What affects what:** Current MDP/setup/commands, project context, risks/readiness, instruction file and scoped push to established origin/main. Credential values remain local and ignored; no runtime implementation or provider call.
- **My answer (editable):** Direct current user instruction authorizes these setup/model choices, documentation changes and this scoped push; it explicitly withholds Phase 1 until GO.
- **Authority:** User messages, 20 October 2026. This publication approval is scoped, not standing permission for later main pushes.
- **Verification:** E-DOC-005; file existence, ignored-status and venv interpreter metadata checked without reading `.env`; docs CLI/negative controls/staged checks required. Key variable name, validity and model-account availability are not tested.

**Superseded scope:** ADR-0012 supersedes the historical Phase 1 hold above. Its scoped documentation push is fulfilled; provider/setup policy remains applicable.

## ADR-0011 — Single Norn instruction file adapted from both references

- **Status:** ACCEPTED.
- **Question:** How should the project-owned Palladion instruction files be combined?
- **Why:** Owner explicitly requested reading the multiple Palladion AGENTS files, combining their useful rules, tailoring them to Norn and pushing one root instruction file.
- **Options:** Concatenate reference text; tailor one Norn root AGENTS with links to canonical records.
- **Recommendation / decision:** Root `AGENTS.md` combines source grounding, exact task/consumer proof, reviewer boundaries, secret/live-data safety, metric/custody controls, decision history, no-stale records and scoped closeout. Do not import payment-domain architecture, HTTP-only benchmark constraint, historical Haiku model or prior project publication exceptions. Current GPT6 Luna Medium standing rule governs.
- **What affects what:** Whole-repository workflow and documentation navigation. Runtime design remains in MDP and current status in PROGRESS, not duplicated architecture/state histories in instructions.
- **My answer (editable):** Direct current user request authorizes creating and publishing this single project instruction file.
- **Authority:** User's follow-up instruction, 20 October 2026.
- **Verification:** E-DOC-005; both project-owned reference AGENTS read in full, Norn links/checker and scoped independent end review; no foreign files modified.

## ADR-0012 — P01 implementation mandate and approved foundation

- **Status:** ACCEPTED.
- **Question:** May P01 implementation begin, and which pending foundation choices are resolved?
- **Why:** The owner explicitly requested completing P01 and approved all three question-tool decision groups on 20 October 2026.
- **Options:** Continue the earlier hold; implement the approved local synthetic foundation.
- **Recommendation / decision:** Implement P01-T01 through T12 in dependency order. ADR-0002/0003/0004/0005/0006/0009 answers above are accepted within their stated P01 scope. The owner separately approved `tzdata`: this Windows environment has zero IANA zones and `ZoneInfo('UTC')` fails without it. Runtime uses standard-library SQLite/dataclasses/argparse/zoneinfo plus that timezone data package. No Groq call is necessary for deterministic fixtures.
- **What affects what:** Packaging, clocks, source contracts, SQLite schema, canonical reader, journal and installed facade. P03 search and P11 workers remain future work. The earlier ADR-0010 hold is superseded for P01 only; its historical publication authority remains scoped.
- **My answer (editable):** Owner approved recommended setup, semantics and synthetic pilot, then approved tzdata through the question tool. No new main push approval has been given.
- **Authority:** Current P01 goal and question-tool responses, 20 October 2026.
- **Verification:** Start adversary read the full blueprint and P01 contracts/cards; phase evidence will be recorded as executed. Initial state was IN_PROGRESS; final P01 proof and review closure are E-P01-003.

## ADR-0013 — Ground the physical foundation in governed references

- **Status:** IMPLEMENTATION_DECISION within accepted P01 contracts.
- **Question:** How do local physical IDs and controls implement the MDP's identity, time and source obligations?
- **Why:** Integration checks found that labels alone are not governed subject identity, and later-added support must not appear in an earlier knowledge/snapshot view.
- **Options:** Retain label equality or add wrappers around reads; fix the owning canonical representations and queries.
- **Recommendation / decision:** At atomic ingestion create an occurrence-qualified provisional entity and source-backed alias; atoms reference entities through actual namespace composite FKs. Identical bytes/labels across occurrences do not merge identities. Explicit targeted correction binds to its target identity only after current access and alias checks, followed by matching predicate/qualifiers/scope and ADMIN for supersession. Source/support recording sequences and times constrain historical citation reads. Time serialization stays in contracts, avoiding a dependency from extraction back into registry. All traversal/cycle checks are iterative.
- **What affects what:** P01-T02/T05/T07/T08/T10/T11, canonical identity/schema/registry, subject/object entity FKs/current access, lineage selectors, reader and regression controls. No shipped contract or foreign code is changed. P03 authority and P11 external guarantees remain future work.
- **My answer (editable):** Main implementation detail grounded in approved synthetic semantics and existing MDP identity/FK obligations; not an invented additional owner response.
- **Authority:** Accepted ADR-0003/0005/0012; MDP contracts, canonical schema and identity decision table; blueprint I1-I7.
- **Verification:** E-P01-001/E-P01-002 and tests/test_identity.py, test_corrections.py, test_contracts.py. Verified by E-P01-003 and resolved independent end review.
