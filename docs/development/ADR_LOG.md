# Architecture and research decision log

## ADR-0027 — Review findings, recorded deviations and P05 start conditions

- **Status:** PROPOSED by main on 7 November 2026; **Q-D ANSWERED by the owner on 7 November 2026 (approved as written)**; Q-A, Q-B, Q-C, Q-E, Q-F, Q-G remain unanswered. Nothing else below is an owner approval. The items marked Q-A to Q-G are the only ones that block a card; everything else is disclosure.
- **Question:** Which departures from the literal ADR-0025 answers happened while executing them, which findings of the two Haiku 5.5 high-effort reviews (P05 start adversary, pre-P05 end reviewer) need an owner decision, and what may P05 start before those answers?
- **Why:** The reviews read the full blueprint and the repository and found places where the executed work differs from the owner's wording or where P05 would silently inherit a limit. AGENTS.md requires departures and reinterpretations to be visible, not folded into a green summary.
- **Options:** Record and continue with disclosed limits (chosen for items A1-A7); ask the owner before the affected card (Q-A to Q-G); revert the executed work (rejected, no defect found that needs it).
- **Recommendation / decision:**
  - **A. Departures recorded (code kept, wording corrected in RISKS/EVIDENCE):**
    1. Item 1: the immutable P03/P04 ledgers were not re-scored. Their inputs no longer pass `benchmark/fixtures/publication.py` (the public query lost `coverage_state`), so old values stay labelled history and the new metrics apply to `p05-pre-r-002` and `p05-pre-b-001`.
    2. Item 2: the fixture tag `public-v1` was reused. Query IDs are unchanged while the published inputs differ (preparation `input_digest` differs per query), so "same 540 pairs" means the same pair IDs, not the same inputs. Compare runs by input digest, never by query ID alone. A tag bump would also invalidate `-002` and `-001`; it is left to the first P05 re-publication.
    3. Item 4: S4 was verified, not re-shaped. `shapes()` is unchanged and the capacity ratio of S4 to B4 is within 1% (test); the repair is the forward/backward placement of the type embedding (binding REVISION v2).
    4. Item 6: the source blob is linked as the last statement before COMMIT, not after it. Reason: a crash after COMMIT would leave canonical rows pointing at a missing source (data loss); a failure between the link and COMMIT leaves only an unreferenced digest-named blob (storage leak, no loss). Residual: `sweep_staging` reclaims only `.pending-*` names, so such a blob stays until the P12 reference reconciliation. R24 now says so.
    5. Item 8: ledger and chain digests are bound by an external attestation file written after the run (a manifest is written before the run and cannot hold them). `validate_run` verifies it only when `--attestation` is passed, and a test asserts the default path still accepts a rewritten ledger; every evidence citation in E-FIX-002 passed the attestation. Mandatory enforcement is Q-F.
    6. The library training envelope now accepts any `0 <= seed < 2**32`; the study seeds 11, 29, 47 are pinned in `benchmark/runs/binding.py` CONFIG and checkpoints record them.
    7. `request_id` was removed from the CLI write JSON as part of the approved dead-code removal. The strict field check now rejects payloads that still send it (`INVALID_FIELDS`); this is a visible CLI contract break.
  - **B. Open questions (no default is applied):**
    - **Q-A (blocks P05-T07):** may binding dimensions above 384, the 2,000,000-byte parameter budget, the 1,048,576-byte checkpoint cap and the 384-coordinate serving cap (ADR-0021) change for the dimension sweep? Recommendation: keep 384 for P05-T01 to T06 and run the sweep at 384 with a stated limit unless the owner raises the caps.
    - **Q-B (blocks the language claim in T08):** every role contains en, id and mixed cases, so unseen-language transfer is untestable. Recommendation: claim paraphrase and unseen-identity transfer only, or add a language-held-out split by owner decision.
    - **Q-C (affects how P05 outcomes are labelled):** the development tune and evaluation roles are 14 clusters each and were already reported in P04. Recommendation: label every P05 outcome development-exploratory with that reuse disclosed; before margins are frozen, generate a larger development pool (`partition()` supports up to 100 clusters per family) whose evaluation role is unreported.
    - **Q-D (blocks the first tune-role run):** R09 margins and endpoints are still UNSET. Per ADR-0026 main proposes them and the owner approves before they are frozen. Recommendation: main writes the proposal after P05-T02 and before any tune-role run; without approval P05 may report only exploratory contrasts. **The proposal (`docs/development/evidence/p05_r09_margin_proposal.md`, 7 November 2026): five contrasts, minimum benefit +0.05, regression bounds 0.02, and a power table, was APPROVED AS WRITTEN by the owner on 7 November 2026 and is frozen; its section 7 records the operational definitions fixed before any tune-role read.**
    - **Q-E:** `engine.py` sets CONFLICT whenever an asserting CONTRADICTS edge exists, even when the contradicted endpoint is a HYPOTHESIS. Should a non-asserting endpoint set the query outcome? ADR-0025 item 3 constrains only the contradicting source.
    - **Q-F:** should `validate_run` require an attestation for any run cited as evidence, or should the digests move into a post-run manifest section?
    - **Q-G:** candidate expansion is bounded by events (`candidate_limit`) but every atom of each kept event is resolved under a time-only checkpoint (worst case about 64,000 atoms). Add an explicit expanded-hit cap that fails closed before P06 graph work (R30)?
  - **C. What may start now:** P05-T01 (pair building from the train role only), T02, T03 on the 384-d existing shapes, T04; T05 and T06 once the generator procedure, NumPy version (2.5.4 per ADR-0017), tolerance and expected-output file are pinned in the card before code. No tune-role run before Q-D; T07 waits for Q-A. Findings about stale mandate and reviewer wording are already corrected.
- **What affects what:** P05-T01 to T09, G-LEARNING/G-SEPARATION/G-RESEARCH wording, R09/R24/R26/R30, `benchmark/fixtures/partitions.py` custody, any later reuse of `p05-pre-*` numbers.
- **My answer (editable):** Q-D: "Approve as written" (owner, question tool, 7 November 2026) on the R09 margin proposal: sections 2–4 frozen (five contrasts, minimum benefit +0.05, regression bounds 0.02, Holm), section 7 operational definitions recorded by main before any tune-role read. Q-C was not chosen by that answer; P05 outcomes are labelled development-exploratory (the conservative label under every option) and Q-C stays open. Q-A, Q-B, Q-E, Q-F and Q-G: no answer.
- **Authority:** Owner answer to Q-D above; the rest is main's proposal following the two reviews on 7 November 2026; ADR-0025/0026 remain the owner's words.
- **Verification:** Each A item cites the code or test that shows it (registry.py publish call, validate.py attestation branch, tests/test_runner.py rewrite test, training.py envelope, cli.py parse_write); reviewer findings were checked against the cited files before being recorded.

## ADR-0026 — P05 mandate, cleanup order, reviewer model and standing rules

- **Status:** ACCEPTED by owner on 6 November 2026.
- **Question:** May P05 start after the audit cleanup, with which substrate, compute, sweep scope, margins, reviewers, Groq use and publication rule?
- **Why:** ADR-0022 hands P04 over as a sequencing record, not a mandate. The audit (E-FIX-001) and ADR-0025 answers add repair work that must finish so P05 starts on a correct B4, a stable schema and a re-measured baseline.
- **Options:** Cleanup only; T01-T04 only; all nine cards after cleanup (chosen).
- **Recommendation / decision:** Order: (1) record answers; (2) metric/E12/digest/authority/blob/candidate-unit fixes with tests; (3) migration 005 and engine/minor retrieval fixes; (4) dead code, test gaps, audit pack and statistics wiring; (5) B4 fix, retrain, R0-R3 and binding re-run; (6) documentation dedupe, evidence, Haiku start adversary and end review; then P05-T01..T09 in dependency order, continuing within the mandate without repeated permission requests. Substrate: frozen pinned E5-small plus small heads. Compute: local CPU, a wall-time cap written in the receipt before each study, stop and ask on expected overrun. Sweep: hierarchical reduced grid (dimension with identity codes, then sparsity, then learned versus random at the winners), every cell reported, equal-storage and exhaustive-search controls kept. Margins: main proposes practical efficacy and regression margins from the development pilot, the owner answers in an ADR, then they are frozen before any locked or confirmatory evaluation, with no post-result revision. Reviewers: the start adversary and sole end reviewer stay, now both Claude Haiku 5.5 at high effort (supersedes the GPT 6 Luna Medium rule in AGENTS.md for new work; historical receipts keep their original reviewer). Groq: GPT OSS 120B only, explicit per run, for bounded fixed-generator QA if used; a small fixed call/token cap recorded before the run, retries counted, hard stop on rate limit, owner asked before exceeding; exact API identifier and account availability verified first; no call merely to test the key. Publication: commit verified units freely; every push to main waits for the owner's explicit yes.
- **What affects what:** AGENTS.md reviewer rule and MDP execution contract, P05 cards T01-T09, G-LEARNING/G-RESEARCH, R09 margins, ADR-0007 compute and model choices, every later consumer of the retained code or simpler winner.
- **My answer (editable):** Owner answers of 6 November 2026 as stated above. GPT OSS 120B was the owner's choice after being asked which allowed Groq model; Qwen 3.8 27B and GPT OSS 20B are not authorized for this mandate.
- **Authority:** Owner question-tool answers, 6 November 2026; ADR-0007/0010/0020/0022/0024/0025.
- **Verification:** Steps 1–5 are recorded in E-FIX-002 (commands, caps, digests, exits, old-versus-new comparison); step 6 documentation and the reviews follow. Each step records exact commands, hashes, exit, readback and limits in EVIDENCE_LOG; the reviewer brief follows AGENTS.md self-contained, read-only, credential-free rules; P05 closes only with the sole end review resolved.

## ADR-0025 — Audit findings escalated for owner decision

- **Status:** ACCEPTED by owner on 6 November 2026 (answers below); executed in E-FIX-002 with the departures from the literal answers recorded in ADR-0027 section A (items 1–8 and 10; item 9 is measured first in P11). RISKS R19–R31 carry the per-item disposition; installed-wheel proof of migration 005 remains for the next wheel build.
- **Question:** Which audit findings change a metric definition, trained architecture, security semantics, stored schema or published evidence, and so need an owner answer before repair?
- **Why:** The 6 November 2026 five-reader audit (E-FIX-001) found defects whose repair would alter reported numbers, require retraining or add a schema migration. AGENTS.md reserves shipped-contract, schema and scientific-claim changes for the owner.
- **Options / recommendation (one line each):**
  1. Metric denominators: `retrieval.py` ideal DCG and `abstention.partial_utility` count unsatisfiable slots, so a perfect E9 qualified partial scores nDCG 0.613 and utility 0.5. Recommend satisfiable-slot denominators and re-scoring the immutable ledgers (no model rerun needed), keeping old values as labelled history.
  2. E12 exposure: the published query carries `coverage_state=UNAVAILABLE` and every arm short-circuits to VERIFICATION_UNAVAILABLE before retrieval (`adapters/common.py`, `baseline.py`, `r7.py`), so E12 measures the harness. Recommend the arm observing real projection coverage from the engine and E12 becoming an injected-outage control.
  3. Retraction authority: WRITE may retract any atom while supersession needs ADMIN, and a WRITE-only CONTRADICTS edge from a hypothesis or inference can mark an observation CONFLICT (I2). Recommend ADMIN or own-atom-only retraction and origin-aware contradiction.
  4. B4 parameterisation: `types` and `bias` receive identical gradients, so B4 and the S4 control are not capacity-matched as claimed. Recommend fixing in P05 entry and re-training before any B4 claim; R01 carries the caveat until then.
  5. Binding candidate granularity: scores are per event but limits are per atom, so one many-atom event can fill the candidate list. Recommend event-level ranking with expansion.
  6. Orphan source blobs: `sources.put` precedes validation, so a rejected ingest leaves a blob that no purge selector reaches and backups copy. Recommend a staged publish with reference reconciliation (P12 retention work).
  7. Schema: no secondary indexes exist (graph/scale cost, quadratic deletion walk) and `atom_support` has no recorded time, so support visibility uses the source-version time. Recommend one additive migration 005 with the verified-backup upgrade proof, before P06.
  8. Run-artifact binding: `completion.json` digests are not bound by the manifest, so a rehashed corrupted ledger passes. Recommend binding ledger and final-chain digests in the manifest.
  9. Cost: per-query artifact re-parse, 4-text embedding batches and two ONNX respawns with full re-hash per R3 query are unmeasured. Recommend measuring (P11) before optimising.
  10. Re-measurement: fusion v2 and the clock repair change code that E-P03-003/E-P04-005 froze. Recommend one bounded R0–R3 development re-run (CPU cost, explicit enablement) before P05 reuses those numbers as its baseline.
- **What affects what:** G-RETRIEVAL/G-BINDING/G-SECURITY interpretation, R01/R08/R10/R15 and risks R19–R28, P05–P06 entry, any reuse of P03/P04 numbers.
- **My answer (editable):** Owner answered every item through the question tool on 6 November 2026:
  1. Satisfiable-slot denominators for ideal DCG and partial utility; re-score the immutable P03/P04 ledgers, keep old values as labelled history.
  2. Engine-observed coverage: remove `coverage_state` from the public query; E12 becomes an injected-outage control (published fixtures and digests change, so a new fixture version).
  3. ADMIN (or the atom's own producer) to retract; a CONTRADICTS edge drives CONFLICT only from DIRECT_OBSERVATION, USER_REPORTED or DOCUMENT_ASSERTION sources, never HYPOTHESIS or MODEL_INFERENCE.
  4. Fix B4 now and retrain B3/B4/S3/S4 before P05 (type signal applied so it has a distinct gradient role; S4 re-matched); old B4 results stay caveated history.
  5. Rank events, then expand to their atoms within the candidate limit.
  6. Staged blob publish now (link into the content store only after the transaction commits, sweep stale staging).
  7. Additive migration 005 now, before P05: secondary indexes and `atom_support.recorded_at`, with fresh and populated upgrade, verified backup/restore and installed proofs.
  8. Bind ledger and final-chain digests in the manifest, and re-seal the preserved runs with an external attestation file that does not modify them.
  9. Measure cost first, in P11; no optimisation now.
  10. Bounded local CPU R0-R3 re-run on the repaired source as a new version-scoped run beside the preserved ones, and a bounded re-run of the P04 binding comparison on the corrected B4 and candidate unit (owner follow-up answer). Local pinned models only, no network, no Groq.
  Further owner answers in the same session: remove Python-only dead code (unused enums and `request_id` plumbing) but keep schema and the identity/lineage APIs with named owning phases; close all QA test gaps (collected model-gated wrappers, rerank/r2/ann tests, computed smoke output, specific error matches, deterministic cancel test); dedupe documentation and fix `check_docs.py` lint while keeping history; fix all three audit/statistics findings (sample every twin under a new pack version, require an attestation receipt for human independence, wire Holm and zero-incident bounds); fix all minor retrieval findings including tokenizer, vector validation and OpenMP (R0/R1 numbers change and fall under item 10); fix all engine edge cases with support recording time in migration 005.
- **Authority:** Owner answers above, 6 November 2026. Each execution step still follows AGENTS.md proof, review and publication rules.
- **Verification:** Each item cites a file and a read or hand calculation in E-FIX-001; items 1, 2 and 8 were confirmed by reading the producing and consuming code, items 4–5 and 9 are single-reader static claims. Execution proof (E-FIX-002): 207 tests, Ruff and strict mypy clean; item 4 by a control test and retraining (B4 headline identical to P04-003; S4 capacity ratio verified, not re-shaped); item 8 by sealed and verified attestations for P03-005, P04-003, `p05-pre-r-002` and `p05-pre-b-001`, which prove digest consistency when the attestation is supplied, not mandatory enforcement (ADR-0027 Q-F); item 10 by those two runs.

## ADR-0024 — Audit repair: host-owned recording clock and verified defect fixes

- **Status:** ACCEPTED, scoped to the repairs listed here.
- **Question:** How is canonical recording time made reproducible, and which unambiguous audit defects are repaired now?
- **Why:** On 6 November 2026 `test_missing_source_field_cannot_remove_an_explicit_question_prerequisite` failed (157 passed, 1 failed, against the recorded 158 passing). Ingest stamped `recorded_at` from the machine clock while benchmark queries use the fixed knowledge basis 2026-10-23; once the machine date passed it every fresh write was unknown to those queries (0 eligible). Blueprint 15.5 forbids the current machine clock in a replayed benchmark. The owner then asked for this to be fixed, followed by the remaining bugs, and for everything to be logged.
- **Options:** Request-level `recorded_at` (lets any writer backdate); injectable host clock (chosen); freeze the tests' wall clock (hides the product defect).
- **Recommendation / decision:** `contracts.time.Clock`/`wall_clock`; `Database(clock=)` with `Database.now()` (aware UTC or NAIVE_TIME); `Engine(clock=)`. Event, source, assertion-event, deletion-request, grant and derivation stamps use it; migration and projection-build instants stay on the machine clock as operational data. The benchmark `ReplayClock` stamps each synthetic source with the world's declared `recorded_at`. Repairs in the same unit: exact-channel fusion v2 (rank-one vote, oversized scope returns no exact hits); build budgets sized from the validated corpus (default 256 model calls could not index more than 256 records); failed upgrade no longer leaves the store marked dirty; per-atom relation/control/support appends refused at the read ceilings (ATOM_APPEND_BUDGET); deterministic applicability precedence SUPERSEDED > window > CONFLICT; explicit errors instead of StopIteration; exclusive atomic checkpoint publication; fail-closed import barrier; additive metrics `selective_coverage_itt`, `answerable_unobserved`, `ambiguity_overreach_*`; cwd-independent test paths.
- **What affects what:** `canonical/{database,registry,corrections}`, `governance/{access,deletion}`, `integration/engine`, `projection/{local,binding}`, `retrieval/{fusion,exact,resolve}`, `contracts/{time,budgets}`, `embedding/checkpoint`, benchmark adapters/metrics/publication and their tests. Frozen digests quoted by E-P03-003 and E-P04-005 no longer equal the current source; those results stay valid for the source they name and are not relabelled or promoted. Preserved `.norn` stores keep their old wall-clock `recorded_at`, which is earlier than 2026-10-23, so they remain readable. No schema change, new dependency, provider call or credential read.
- **My answer (editable):** Owner: "Yes, fix clock", then "good continue the clock and finish the rest of the bug" and "log all in docs/development".
- **Authority:** User messages of 6 November 2026. Items that need an answer are in ADR-0025, not here.
- **Verification:** E-FIX-001: 173 tests pass, no failures or skips (95.6 s), Ruff check and format on 150 files and strict mypy on 101 modules pass; negative controls fail on the pre-fix source; independent-reader findings were checked against code before use.

## ADR-0023 — Scoped publication after verified P04 closeout

- **Status:** ACCEPTED, scoped to this closeout.
- **Question:** May the verified local P03/P04 work and final P04 evidence/status commit be pushed to the established main upstream?
- **Why:** The owner explicitly requested, on22October2026: “we got hit by a rate limit please continue and push as well once done”. Earlier implementation mandates did not authorize main publication; this new direct instruction does.
- **Options:** Keep verified commits local; publish the completed current work after final review/checks.
- **Recommendation / decision:** Finish final documentation validation, sole reviewer status resolution, resource/secret/staged checks and descriptive local commit; inspect every outgoing full commit subject/body and upstream/remote head, then push normally to the current main branch's existing origin/main upstream. Verify remote HEAD and clean checkout afterward. No force, history rewrite, tag, PR, remote/credential/config mutation or publication of secrets/bulk artifacts.
- **What affects what:** Current P03 d6f4beb, P04 source59f8021 and final P04 evidence/status closeout; publication only, no P05 mandate or new scientific claim. Old no-push statements in versioned execution history retain their original authority context and are superseded for this scoped publication.
- **My answer (editable):** Direct owner instruction above explicitly authorizes pushing this completed work once verified. No repeat permission question is needed.
- **Authority:** Latest user message,22October2026, following final P04 artifact verification.
- **Verification:** E-P04-005 final docs/staged/reviewer proof, full outgoing messages, normal push exit and exact local/remote HEAD agreement. A rejected/divergent push requires inspection/report, never force.

## ADR-0022 — Preliminary P04 frontier and advancement boundary

**Timing interpretation correction, 22 October:** Static cache metadata incorrectly describes empty-projection first recalls as resident. Existing002 records identify 12 cold starts; first timings mix cold/warm, and rare starts can disappear from per-arm p99. Scoring/ranking do not read the label. E-P04-005 and evidence/binding.md preserve the erratum and exact observed boundaries. Main records the known annotation defect without changing the frozen003 runtime; its own completed immutable ledger independently confirms12 cold first queries, with its own exact timing ranges recorded in E-P04-005. The sole end reviewer confirmed interpretation can be corrected without a new model run. No performance promotion depends on the false annotation.

- **Status:** PRELIMINARY_INCONCLUSIVE; P04 investigation complete, final003/artifact/installed proof and sole end review resolved. This is the preliminary within-Stage1 research interpretation under accepted ADR-0020, not a new owner answer or efficacy promotion.
- **Revisit after the B4 fix (7 November 2026, E-FIX-002):** the owner asked to revisit this interpretation once B4 was repaired. Retraining B3/B4/S3/S4 on the repaired B4 left the comparison unchanged (all four 141/153 complete-set; B3−S3 and B4−S4 0.000 with intervals [0, 0]; B3/B4−B1 +0.103 with an interval including zero), so the interpretation stands: no decomposition or attention benefit is established and the outcome stays INCONCLUSIVE. Only B4 conditional margins moved, and they are not answer or capacity claims.
- **Question:** Does the observed pilot justify added functional decomposition or attention, and which controls should the Stage1 handoff preserve?
- **Why:** Blueprint “Primary selection criterion,” “Proposed acceptance criteria” and Stage1 require resource-normalized evidence and the simpler winner. Learned alignment alone is not evidence that biological naming or extra facets caused a gain.
- **Options:** Promote the most elaborate arm from a positive training curve; retain simpler controls and qualified challengers using actual held-out retrieval, answer errors and costs.
- **Recommendation / preliminary decision:** Preserve B0 as the simplest new binding reference and S3 as the simplest trained capacity control; retain B3 as a cost/structure challenger, since its observed passage-token use is lower than S3 while their evidence quality is equal here. Fixed B1/B2 remain explicit controls. Do not promote B4's extra attention: its CompleteSet/episode results equal B3 and matched wider single controls. This does not prove attention or decomposition generally useless. B5 remains FEATURE_NOT_SUPPORTED without a separate generative hypothesis/budget. Existing R0–R3 serving defaults are unchanged.
- **What affects what:** P04-T09 supplies candidate/checkpoint/control/limitation handoff for the predeclared P05 T0–T7/separation program; it does not authorize P05, a larger architecture, new generator, production deployment or main publication. P05-T09 remains the final Stage1 advancement owner.
- **My answer (editable):** No new owner response is invented. Main's preliminary scientific disposition is INCONCLUSIVE for a decomposition-specific or attention-specific benefit, grounded in completed source-matched003, with prior version002 preserved. All learned arms and matched single-event controls recover47/51 CompleteSets per seed; B0/B1/B2 recover42/41/42. Equal-quality S3/S4 controls prevent attributing the gain to functional decomposition. All arms retain the same6/84 false answers and11/52 false abstentions per exposure. Cost tradeoffs must remain visible rather than calling one universally cheaper. Final003 and the sole artifact review have confirmed the source-matched record, supporting P04-T09 closure without an efficacy claim.
- **Owner ratification (6 November 2026):** Ratified as the handoff into P05, to be revisited once the corrected B4 is retrained (ADR-0025 item 4) and the binding comparison is re-run (item 10). Status changes from preliminary-only to owner-accepted handoff; the INCONCLUSIVE scientific outcome and every efficacy limit are unchanged.
- **Authority:** Blueprint I1–I10, “Shared latent binding,” “Primary selection criterion,” “Proposed acceptance criteria” and Stage1; MDP P04-T09/P05 entry; accepted ADR-0020/0021; RESEARCH_PROTOCOL. Main reread these exact blueprint headings before this interpretation.
- **Verification:** Final003 immutable4140-condition report `f300a03bc20243a310084295270693429fdebcbcdbe3eb04885893ed7ea264b2` and clustered contrasts in E-P04-005/evidence/binding.md; no practical margins/power, locked confirmation, category/template transfer, external agent result or P04 head-to-head R3 comparison exists. No operational advancement criterion is met by this exploratory result alone. Source-matched003 completed with4050OK/90UNSUPPORTED/no runtime ERROR or TIMEOUT; all seven installed standalone/corruption/CLI/native/B5/parity stages pass and sole end-review artifact resolution found no material discrepancy or missing P04 proof. Preserve002/003 as the same fixed development instances, not independent replication.


## ADR-0021 — P04 implementation profile within approved pilot

- **Status:** ACCEPTED implementation detail within ADR-0020; no new dependency or owner exception.
- **Question:** How do the approved views, training and actual reader share existing owners?
- **Why:** Derived helpers without a public persisted consumer cannot prove binding; new arms must retain the shipped eligibility/evidence path.
- **Options:** Extend the existing engine and source/manifest owners with opt-in binding methods; duplicate canonical security/evidence logic in a benchmark-only model.
- **Recommendation / decision:** Engine exposes explicit binding projection/recall methods and CLI commands; existing RecallRequest/R0–R3 behavior stays intact. A common final evidence function serves conventional and binding candidates. Schema4 adds immutable binding manifests/entries/ready records, with artifact/checkpoint/source/version/epoch identities and exact readback; populated upgrade uses existing verified backup discipline. Binding artifacts use the existing UTF-8 CAS; no executable/pickle checkpoint loads. Checkpoints are bounded validated numerical JSON with method/data/config hashes. Backup and pending-purge selectors include actual binding artifacts.
- **What affects what:** T01/T02 add features/{context,actions,semantic,salience,views}; T03/T04 add late_fusion/concatenate and R7; T05/T06 add binding/query/attention/training/checkpoint and R8; T07 adds explicit disabled denoising registry; T08 adds fixture/capture/run/report/public adapters; supporting integration, projection/binding, retrieval/service, schema4/database, CLI and backup/deletion tests belong to the affected cards. No canonical source/origin semantics change.
- **Feature contract:** All views derive from eligible canonical records grouped by occurrence. Context preserves exact/interval/unknown time, actor labels and explicit anchored location. Ordered actions require ACTIVE DIRECT_OBSERVATION atoms with predicate observed_action and anchored action_step, attempted_tool, observed_result and observed_at qualifiers; no causal or task-reward inference. Absent action is NOT_APPLICABLE, S0 is unobserved/masked. Current canonical relation types only, without P06 graph inference. Text embedding never uses opaque event/subject IDs or evaluator labels.
- **Training/comparison profile:** Pinned E5 backbone frozen; learned heads use actual NumPy reverse derivatives checked by finite differences, multi-positive contrastive retrieval, normalized outputs and bounded serial updates. B3 uses typed heads/pooling; B4 typed token self-attention/pooling; cue and memory paths both train. Wider single-event MLP controls match each learned arm within1% parameters. B1/B2 fixed seeded shared orthogonal facet projection uses three128-dimensional slots (context/semantic/actions); B0/B3/B4/single controls use384-dimensional codes. S0 has no fabricated vector. Numeric serving vectors are capped at384 float32 coordinates per event; actual artifact/checkpoint/offline cache bytes and inference operations are separately reported. Same source/eligibility/evidence and512 total backbone-token cap per memory or query input; missing views do not consume fake inference. B5 stays explicitly unsupported.
- **My answer (editable):** Main detail, grounded in P04 cards and the three explicit ADR-0020 approvals. Exact hyperparameters/data/config/checkpoints freeze before measurement; no new owner threshold invented.
- **Authority:** ADR-0020; MDP binding/read-flow and exact P04 cards; blueprint I1–I10, Shared latent binding, Functional operators and Stage1.
- **Verification:** Source-backed features, analytic gradient/shape/mask controls, actual supervised training/held-out query-to-memory lookup, current ACL and source readback, schema4 fresh/populated/interrupted/reopen proof, actual installed CLI, immutable report readback/corruption controls, resources and sole end review remain required. No efficacy claim from training loss or normalized shapes.


**21 October implementation clarification:** The successful version-scoped smoke001 (450 OK rows) does not establish efficacy. Before full measurement, source inspection confirmed underspecified AMBIGUOUS cues were incorrectly training against a single retained gold-slot target. Training now treats every currently eligible compatible captured episode as a positive for that cue, with no gold/public-fixture edits. This is a false-negative fix at target derivation, not result tuning. Query geometry/S0/B5 declarations have actual runtime readers; geometry fingerprints include fixed projection/weight/ranking/model shape settings. Archival backup checks hash/locator integrity without applying current serving geometry to older generations; serving remains strict. Full study records actual operator/build/first/repeated costs, training gradient/parameter/rank receipts, separate published-episode identity and observed wrong-episode denominators, environment and physical-file bytes. All remain within accepted ADR-0020; main owns code/tests and will verify these statements before closure.


**22 October end-review resolution:** The sole reviewer identified copied checkpoint CAS digests missing from pending binding purge selectors. Main confirmed the producer and affected manifest references, then extended the existing bounded selector query with a deduplicating UNION. Checkpoint selectors remain PENDING and require shared-reference reconciliation, as demonstrated by unaffected-event rebuild/recall using the same bytes. No deletion, unlearning or backup-purge guarantee is invented. This is an owning in-scope defect fix under the accepted integration/deletion ownership; final full003 will bind the changed source and002 remains version-scoped evidence. E-P04-005.

## ADR-0020 — P04 mandate and proposed bounded binding pilot

- **Status:** ACCEPTED by owner21 October2026: P04 mandate, bounded frozen-E5 training, matched adapter-capacity study and additive P04 integration.
- **Question:** Which training implementation, comparison envelope and source/consumer extensions may implement all nine P04 cards?
- **Why:** P04 requires actual trained B3/B4 and a capacity control, while ADR-0007 leaves training choices open. Action annotations have no typed observed-sequence contract. Schema3 admits only lexical/dense capabilities; public recall admits R0–R3. These gaps need explicit resolution, without helper-only or untrained substitutes.
- **Options:** Reuse pinned frozen E5 with small CPU-trained heads/attention using existing NumPy; separately approve a framework/backbone and downloads. Compare a wider trainable single-event encoder at matched learned capacity, or approve another larger pretrained backbone. Extend the existing public engine/CLI and immutable projection pattern, or choose a different integration explicitly.
- **Recommendation:** Reuse pinned E5 FP32 inference/tokenizer, frozen; actual analytic-gradient NumPy contrastive training with numerical gradient controls for typed B3 heads/pooling and B4 attention. Include a wider single-event trainable control matched to each learned arm within1% trainable parameters. This tests frozen-backbone adapters, not backbone fine-tuning or a larger pretrained transformer. Three fixed training seeds11/29/47, at most200 optimizer updates per seed/arm, serial CPU work,20-minute per-training-job/2-hour aggregate training deadlines, bounded batches/checkpoints and512MiB additional numerical-array budget excluding the already approved native E5 worker. B5 remains FEATURE_NOT_SUPPORTED without a separate generative hypothesis/approval. No Groq calls or new dependencies proposed.
- **What affects what:** P04-T01–T09; feature/action source contracts, train/query/checkpoint owners, R7/R8 and binding runner/validator, opt-in engine/CLI integration, additive schema4/database/projection/backup/deletion tests. Existing R0–R3/canonical contracts remain default behavior; no schema3 rewrite. Populated upgrades require a verified restorable backup before migration. Extend affected card file ownership before implementation.
- **Proposed comparison:** Fresh disjoint training/tuning/evaluation scenario/entity instances within development, split before paraphrases; calibration/locked inputs untouched. Preserve all14 categories and add explicit fictional authenticated action-observation cases with anchored step/tool/result/time through existing authorized canonical writes and typed qualifiers. Relationship features use only current canonical relation types; no P06 graph semantics. Preserve multiple positives/ambiguity, absent facets, languages and cue-degradation controls; constructed labels remain unaudited. B0–B4 receive the same authorized source information, deterministic eligibility, evidence budget and fixed maximum embedding-byte/backbone-token/work envelopes. Report actual capacity/tokens/operations/cost differences. Paired facet-drop/duplicate-facet and equal-capacity single-event controls test conditional signal. No invented locked efficacy threshold or automatic architecture promotion.
- **Bounded T01 detail:** Context derives only from existing eligible canonical Record tuples for one namespace/event/snapshot/time value; source locators retained, unknown time not filled, explicit source-anchored location qualifiers only. Canonical identity keys stay out of embedded text. This is within current typed contracts and T01 ownership, independent of pending training/action/integration choices.
- **Proposed integration:** Explicit opt-in public binding project/recall interfaces, immutable checkpoint/feature/binding manifests, existing CAS/source-readback/snapshot patterns and additive schema4 tables. Schema3 and canonical records stay immutable. Every candidate re-resolves to original source/current ACL/time before existing evidence assembly; absent/stale/wrong-checkpoint projections fail visibly. No hidden evaluator import into runtime or adapters.
- **My answer (editable):** Owner answered all three question items in call_8d3b1445fdc7475a9b5423b295f8bbe3: “Approve bounded frozen-E5 training (Recommended)”; “Approve matched adapter-capacity study (Recommended)”; “Approve additive P04 integration (Recommended)”. This accepts the stated training/seed/update/time/array envelopes, frozen-backbone comparison interpretation, development-only disjoint-instance protocol, optional disabled B5 and additive schema4/public integration/file ownership. The prior blocked state is superseded; no P05 or main-push authority inferred.
- **Authority:** Current P04 user mandate; universal Rule4/AGENTS escalation; MDP P04/binding/read flow; blueprint I1–I10, Shared latent binding, Deterministic functional operators and Stage1; ADR-0007/0008/0017/0018.
- **Verification:** Main reread full blueprint and phase/design/source bodies. Sole GPT6 Luna Medium start adversary independently read full blueprint and confirmed unresolved training/action/consumer/capacity prerequisites. Required proof remains actual training, held-out public encoder-to-retriever lookup, immutable artifact reopen, installed CLI/adapter source readback, matched comparison and sole end review. No P04 runtime proof or card completion yet. E-P04-001 owns preflight.

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
- **P05 amendment (6 November 2026, ADR-0026):** P05 trains frozen pinned E5-small features with small heads only; compute is local CPU, bounded by a wall-time cap recorded before each study; no GPU, cloud or second backbone. GPT OSS 120B is the only authorized Groq model, for a bounded fixed-generator QA step only. Other backends remain unresolved.
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
