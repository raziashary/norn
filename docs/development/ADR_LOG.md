# Architecture and research decision log

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

- **Status:** PARTIALLY_ACCEPTED (Python/uv environment); package layout remains PROPOSED.
- **Question:** Adopt a Python modular research package under `src/norn/`, managed with uv?
- **Why:** The blueprint uses Python-oriented examples and requires training/evaluation. Palladion offers Python reference code. No runtime manifest exists in Norn.
- **Options:** Python/uv proposal; another user-selected runtime/toolchain; separate runtime and training languages after a demonstrated need.
- **Recommendation:** Python/uv, one package and in-process pilot; pin compatible versions after environment checks. MDP paths are proposed against this layout, not claims that files exist. If declined, update path mappings before implementation.
- **What affects what:** P01 packaging, type contracts, CLI, testing commands, optional training adapters. No library/version/model/provider is selected by this recommendation.
- **Prior answer record:** Pending owner direction before P01 runtime bootstrap (before the setup amendment).
- **My answer (editable):** Owner created a uv `.venv/` and confirms it is the environment to reuse. Python/uv setup is accepted; `src/norn/` layout, package/dependency selection and implementation remain subject to their decisions and explicit Phase 1 GO. Do not recreate the environment during documentation work.
- **Amendment authority:** User setup instruction, 20 October 2026; see ADR-0010.
- **Authority:** Blueprint “Suggested project organization” is illustrative; current mandate authorizes planning only.
- **Verification:** P01-T01, G-CONTRACT; fresh environment and installed consumer proof required.

## ADR-0003 — Evidence, event identity, and independent state axes

- **Status:** PROPOSED.
- **Question:** Adopt the MDP's typed event/assertion/edge/source contracts and explicit retraction handling?
- **Why:** Blueprint “Epistemic types” includes RETRACTED while later calling epistemic and lifecycle state orthogonal. Retraction changes serving eligibility without changing how the original assertion was obtained.
- **Options:** Rewrite epistemic origin to RETRACTED; preserve original origin and append a retraction status event with a compatibility representation of RETRACTED.
- **Recommendation:** Preserve all seven blueprint values at import/export; internally store `epistemic_origin` plus append-only `assertion_status` events. RETRACTED inputs require a known original origin or UNKNOWN-origin quarantine, not fabricated observation authority. Effective API state can expose RETRACTED plus original origin. Seek owner confirmation before freezing this interpretation.
- **What affects what:** P01 contracts/schema, P03 evidence gate, P08 consolidation, P09 historical recall. No shipped contract exists yet.
- **My answer (editable):** Pending; do not treat the recommended resolution as a narrowing of the blueprint.
- **Authority:** Blueprint “Memory ontology,” “Three orthogonal kinds of state,” and universal decision escalation.
- **Verification:** P01-T02/P01-T03, G-CONTRACT/G-TEMPORAL; history/origin round-trip controls.

## ADR-0004 — Retention, immutable evidence, and physical deletion

- **Status:** PROPOSED.
- **Question:** What source content, audit metadata, backups, traces, and learned parameters must be purged, on which schedule?
- **Why:** Immutable history and authorized erasure must be reconciled explicitly. A tombstone blocks serving but is not proof of erasure everywhere.
- **Options:** Synthetic-only pilot with explicit test purge policies; production retention design after requirements; personalized online training with a separately approved unlearning/retraining contract.
- **Recommendation:** Synthetic-only pilot. Append denial/tombstone controls first; preserve only permitted minimal audit metadata. Track purge acknowledgments by artifact and backup generation. Do not train on private personal data or claim parameter unlearning without a measured policy.
- **What affects what:** P01 deletion model, P08 aggregate invalidation, P11 worker/cache/backup recovery, P12 privacy proofs. Exact time limits remain unset until owner requirements.
- **My answer (editable):** Pending before retention policy or any real data is introduced.
- **Authority:** Blueprint “Deletion, revocation, and retention,” open Q12, I1/I5/I6.
- **Verification:** G-DELETION; denied serving during outages plus explicit physical-purge reconciliation and restore controls.

## ADR-0005 — Time, snapshots, and query interpretation

- **Status:** PROPOSED.
- **Question:** Freeze UTC-aware stored instants, explicit source timezone/precision, and per-namespace sequence snapshots with current security checks?
- **Why:** Event time, observation time, recorded time, valid time, and knowledge-at-time differ. An old content snapshot cannot resurrect revoked permissions.
- **Options:** Single current clock; explicit typed temporal context with declared basis and unknown/interval times.
- **Recommendation:** The MDP temporal contract; query-relative language uses the request evaluation clock and declared timezone. Unknown time remains unknown. Content uses a declared snapshot; access and erasure use current authoritative controls. Reject mixed projection versions or disclose degraded capability.
- **What affects what:** P01/P03 contracts, P06 graph eligibility, P09 replay, P11 projection publication. Cross-partition global ordering is not implied by local commit_seq.
- **My answer (editable):** Pending before freezing runtime contracts.
- **Authority:** Blueprint “Bitemporal reasoning,” “Snapshot/read consistency,” I6/I7.
- **Verification:** G-TEMPORAL/G-SNAPSHOT; late-arrival, DST, historical correction and mid-read revoke controls.

## ADR-0006 — Palladion reuse boundary

- **Status:** PROPOSED.
- **Question:** Which reference components should be ported or reached through adapters?
- **Why:** Provenance, exact source resolution, hybrid baselines, manifests, scoring, and statistics are useful; Palladion memory categories, session rules, payment policy, and classifier are different contracts.
- **Options:** Copy the system; selective audited adaptation; clean implementation against source-backed contracts.
- **Recommendation:** Selective adaptation with provenance/license/source-commit receipts; no runtime dependency on a foreign checkout. Keep benchmark/agent consumers behind explicit adapters and prevent evaluation gold from entering the runtime package.
- **What affects what:** P01 utility review, P02 harness, P03 baseline, P09 consumers. Pin a verified source checkpoint; current reference checkout contains changing work.
- **My answer (editable):** Pending code reuse approval; documentation may describe candidates now.
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
- **My answer (editable):** Use Groq whenever an authorized task needs generative LLM inference. Allowed options: Qwen 3.8 27B, GPT OSS 120B, GPT OSS 20B. Select explicitly per run; no default or silent fallback inferred. Verify exact Groq API identifiers/account availability before first authorized integration. Embedding/reranker/training backbones, tokenizer, compute, backends and budgets remain unresolved. The supplied key is not permission to call now; wait for Phase 1 GO.
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

- **Status:** PROPOSED.
- **Question:** Preserve canonical event+outbox atomicity in the local pilot while delaying external stores?
- **Why:** Blueprint write invariants require coherent commits; its deployment sequence postpones distributed infrastructure to isolate algorithms.
- **Options:** No durable projection journal until Stage5; local transactional outbox from P01 and in-process consumers, external workers in P11.
- **Recommendation:** Local transactional outbox and idempotent in-process projections from P01/P03. P11 adds durable external delivery, leases, retries, shadow rebuilds and operational metrics without changing event identity or retrospectively crediting vendor changes as algorithmic gains.
- **What affects what:** P01 atomic schema, P03 local ready snapshot, P11 external publication. A pilot outbox row does not prove distributed recovery.
- **My answer (editable):** Pending before P01 schema freeze.
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
