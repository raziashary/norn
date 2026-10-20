# Testing gates

Updated 20 October 2026 (Asia/Bangkok). Gates are proof contracts, not a list of passing tests. G-DOC is the only immediately runnable scope. All runtime gates start NOT_RUN; paths/commands are planned until their producer is implemented and approved. Gate states are NOT_RUN/PARTIAL/PASS/FAIL/BLOCKED. A phase-local pass does not close later obligations.

## Execution and evidence rules

Use each atomic card's exact owning test paths, actual public entry point and source/config manifest. UNIT requires stack syntax/type/lint checks and focused contract controls; INTEGRATION requires actual producer-to-reader, persistence reopen and installed consumer where relevant. MEASURE requires frozen permitted split, paired manifest, full failure ledger, proper denominators and raw artifact readback. Bind actual commands at P01; do not run imagined modules or download assets by credential presence.

For current docs: `python docs/development/check_docs.py`, `python docs/development/check_docs.py --self-test`, an in-memory syntax compile, and `git diff --check`. Full semantic fidelity is main/end review, not checker output. For future authorized implementation: reuse the owner-created uv environment, exact named pytest paths from cards, project lint/type/build commands and real installed CLI. No broad suite with ambient live credentials; identify destructive tests, use disposable synthetic stores and verify backups before any meaningful-state rewrite. No provider/service/network test is authorized by this document.

Record positive and negative controls, actual reader, versions, command/exit, missing/skipped resources, interpretation limits and cleanup in EVIDENCE_LOG. Reuse end reviewer for resolution. Update phase-local receipts separately from whole-gate status. PASS requires all obligations in declared scope, not merely presence of a helper or reference test.

## G-DOC — Documentation integrity and semantic coverage

- **State:** PASS.
- **Owner phases:** P00.
- **Owning atomic tasks:** P00-T01, P00-T02, P00-T03, P00-T04, P00-T05, P00-T06.
- **Positive / completion contract:** Actual docs CLI validates links IDs metadata dependency DAG coverage and summary counts; main plus sole end reviewer directly audit full blueprint and all anchors.
- **Negative / falsification control:** Independent damaged-suite controls reject missing links IDs fields cycles coverage and false completion; no runtime status from docs proof.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** E-DOC-001 through E-DOC-004; actual structural CLI, 15 intended-failure controls, syntax/diff checks and full main/independent semantic audit. This PASS covers documentation only.

## G-CONTRACT — Typed canonical schema and package contracts

- **State:** NOT_RUN.
- **Owner phases:** P01.
- **Owning atomic tasks:** P01-T01, P01-T02, P01-T07.
- **Positive / completion contract:** Fresh installed producer/reader validate namespace IDs tagged values all epistemic imports time/control axes source locators real migrations and compatible package versions.
- **Negative / falsification control:** Unknown schema/foreign store malformed values and partial upgrade reject; populated backup/restore tested separately from fresh install.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-SOURCE — Exact source provenance and recovery

- **State:** NOT_RUN.
- **Owner phases:** P01,P03,P06.
- **Owning atomic tasks:** P01-T04, P01-T09, P03-T07, P06-T08.
- **Positive / completion contract:** Write/reopen/cite exact original bytes or authenticated observation and every atom/edge/derived lineage under current purpose authority.
- **Negative / falsification control:** Corrupt bytes/hash/range forged approval model-inference promotion and revoked source never become usable evidence.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-IDENTITY — Occurrence delivery and entity identity

- **State:** NOT_RUN.
- **Owner phases:** P01,P05.
- **Owning atomic tasks:** P01-T05.
- **Positive / completion contract:** Same delivery/payload idempotent; similar distinct episodes stay distinct; reviewed scoped identity and additional support preserved.
- **Negative / falsification control:** Changed duplicate payload same-name cross-tenant merge false negative pairs and arbitrary vague-cue target reject.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-ACL — Eligibility before search traversal and return

- **State:** NOT_RUN.
- **Owner phases:** P01,P03,P06,P09,P11,P12.
- **Owning atomic tasks:** P01-T06, P06-T03, P09-T04, P11-T04, P12-T03.
- **Positive / completion contract:** Current host-granted scope applied before candidate windows/ranking/subgraph normalization and at final read; allowed path still works.
- **Negative / falsification control:** Denied text node intermediary existence counts ranks paths and stale-cache/TOCTOU canaries absent across actual outputs.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-INGEST — Atomic commit local outbox and real reader

- **State:** NOT_RUN.
- **Owner phases:** P01,P03.
- **Owning atomic tasks:** P01-T08, P01-T12.
- **Positive / completion contract:** Events/atoms/support/journal commit together with truthful receipt; restarted CLI and projector consume exactly committed versions.
- **Negative / falsification control:** Racing retry/crash/rollback cannot duplicate event or expose partial set; COMMITTED never impersonates fully searchable READY.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-TEMPORAL — Explicit clocks historical scope and corrections

- **State:** NOT_RUN.
- **Owner phases:** P01,P03,P09.
- **Owning atomic tasks:** P01-T03, P01-T10, P09-T03.
- **Positive / completion contract:** Event/observed/recorded/valid/query clocks distinct; late arrival correction and knowledge-at replay select correct source under current security.
- **Negative / falsification control:** Naive/DST/unknown time not guessed; wrong scope/latest-wins and historical grant resurrection reject.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-DELETION — Serving denial physical purge and restore policy

- **State:** NOT_RUN.
- **Owner phases:** P01,P08,P11,P12.
- **Owning atomic tasks:** P01-T11, P08-T06, P11-T09, P12-T05.
- **Positive / completion contract:** Canonical denial immediate; lineage invalidates aggregate/cache/graph and per-artifact purge acknowledgments reflect declared backup/trace/parameter obligations.
- **Negative / falsification control:** Outage/rebuild/restore cannot resurrect content; tombstone alone not complete erasure; unknown unlearning remains explicit.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-CUSTODY — Hidden world and study information barrier

- **State:** NOT_RUN.
- **Owner phases:** P02,P04,P13.
- **Owning atomic tasks:** P02-T01, P02-T02, P02-T04, P02-T06.
- **Positive / completion contract:** Runtime/adapters receive only authorized rendered input; family/entity split before paraphrases; trainer/dev/calibration/locked roles distinct.
- **Negative / falsification control:** Gold/answers/slots leak in filenames IDs metadata prompts vectors graphs traces imports or tuning makes run invalid.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-REUSE — Audited references and independent adapters

- **State:** NOT_RUN.
- **Owner phases:** P01,P02,P09.
- **Owning atomic tasks:** P02-T07.
- **Positive / completion contract:** Before port record source commit/license/symbol/fork delta and actual Norn reader; evaluator/foreign agent boundary explicit.
- **Negative / falsification control:** No foreign checkout imports hidden labels copied domain authority or reference test count masquerades as Norn proof.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-RETRIEVAL — Strong actual R0-R3 and stage evidence

- **State:** NOT_RUN.
- **Owner phases:** P03.
- **Owning atomic tasks:** P03-T01, P03-T02, P03-T03, P03-T04, P03-T05, P03-T06, P03-T12.
- **Positive / completion contract:** Exact lexical dense/ANN/fusion/reranker source paths use pinned geometry and actual token budgets; exhaustive ANN control and installed source readback.
- **Negative / falsification control:** Wrong IDs/version nonfinite vectors duplicate votes unequal budgets and unobserved retrieval stages cannot claim performance.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-ABSTENTION — Evidence sufficiency ambiguity and selective answers

- **State:** NOT_RUN.
- **Owner phases:** P03,P09.
- **Owning atomic tasks:** P03-T08, P09-T08.
- **Positive / completion contract:** Five statuses plus explicit permitted missing inputs; complete and incomplete evidence twins measure false answer and false abstention.
- **Negative / falsification control:** Runtime gold-slot leakage always-refuse false positive causal promotion and sensitive denied-source explanations fail.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-SNAPSHOT — Exact manifests and declared content snapshot

- **State:** NOT_RUN.
- **Owner phases:** P03,P10,P11.
- **Owning atomic tasks:** P03-T09, P10-T06, P11-T02, P11-T03, P11-T06.
- **Positive / completion contract:** Required index IDs/digests/versions and capability watermarks agree before atomic ready publication; current security checked separately.
- **Negative / falsification control:** Counts-only partial ack mixed geometry stale tombstone or independent partition seq cannot advertise global current snapshot.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-BUDGET — Global costs cancellation retry and cleanup

- **State:** NOT_RUN.
- **Owner phases:** P03,P06,P11,P12.
- **Owning atomic tasks:** P03-T10, P06-T09, P11-T12, P12-T07.
- **Positive / completion contract:** Shared candidate/token/model/graph unique and repeated work/time/retry/queue bounds are actual; normal input succeeds and cancel closes owned resources.
- **Negative / falsification control:** Per-iteration-only cap retry storm timeout-as-complete hidden provider and orphan process fail; old services remain untouched.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-BINDING — Complementary views and aligned cue geometry

- **State:** NOT_RUN.
- **Owner phases:** P04.
- **Owning atomic tasks:** P04-T01, P04-T02, P04-T03, P04-T04, P04-T05, P04-T06, P04-T07, P04-T09.
- **Positive / completion contract:** B0-B4 matched bytes/backbone/input/exposure actual query-to-memory reader; B5 explicit optional capability; conditional signal evaluated.
- **Negative / falsification control:** Attention naming duplicate views extra budget and untrained fusion cannot be credited alignment; masks preserve unknowns.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-LEARNING — Multi-objective training and checkpoints

- **State:** NOT_RUN.
- **Owner phases:** P05.
- **Owning atomic tasks:** P05-T01, P05-T02, P05-T03, P05-T04.
- **Positive / completion contract:** T0-T7 single/pair/triple objectives plus fixed exposure/seeds diagnostics reload into real retrieval; multi-positive pairs screened.
- **Negative / falsification control:** Raw incomparable loss winner false negatives test-data training collapse and dropped no-query-alignment arms invalidate results.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-SEPARATION — Discrimination-generalization frontier

- **State:** NOT_RUN.
- **Owner phases:** P05.
- **Owning atomic tasks:** P05-T05, P05-T06, P05-T07, P05-T08.
- **Positive / completion contract:** Both toy studies exact reproducibility scope plus real sparse/dense/learned/random sweeps measure specific/ambiguous/paraphrase/held-out recall.
- **Negative / falsification control:** Support overlap not weighted cosine or task score; ties not correct; universal orthogonality/JL40dims/c-to-power claims unsupported.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-GRAPH — Typed topology seeds source paths and integration

- **State:** NOT_RUN.
- **Owner phases:** P06.
- **Owning atomic tasks:** P06-T01, P06-T02, P06-T04, P06-T11.
- **Positive / completion contract:** Gold/derived topology split, extraction quality, grounded seeds, BFS/path fixed controls and actual canonical path consumer.
- **Negative / falsification control:** Unreviewed identity hypothesis-as-cause hub/private bridge or opaque index payload cannot authorize support.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-DIFFUSION — PPR heat and associative completion

- **State:** NOT_RUN.
- **Owner phases:** P06.
- **Owning atomic tasks:** P06-T05, P06-T06, P06-T07, P06-T12.
- **Positive / completion contract:** Hand graph dense/numerical oracles verify restart transpose dangling mass residual global unique/repeated work/cancel; same-seed ablations.
- **Negative / falsification control:** Budget-truncated/nonconverged results flagged; unsupported recurrent arm not fake attractor; extra topology/seeds not diffusion credit.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-CDZ — Address decoder and hybrid fidelity

- **State:** NOT_RUN.
- **Owner phases:** P07.
- **Owning atomic tasks:** P07-T01, P07-T02, P07-T03, P07-T04.
- **Positive / completion contract:** CDZ-A exact control versus eligible B/C with explicit shapes fixed-ID fidelity and downstream benefit/cost/OOD.
- **Negative / falsification control:** Wrong entity/time/quantity/source and hallucinated facet errors retained even when canonical fallback corrects answer; no decode-as-truth.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-SALIENCE — Hypothetical and task priority controls

- **State:** NOT_RUN.
- **Owner phases:** P07.
- **Owning atomic tasks:** P07-T05, P07-T06, P07-T07.
- **Positive / completion contract:** S0/S1/S2 same candidates/budgets; bounded inputs neutral/language/distractor and separate ranking/retention evaluation.
- **Negative / falsification control:** No measured neurotransmitter/diagnosis claim or authority/ACL/expiry override; increased storage not ranking gain.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-CONSOLIDATION — Independent supports rare exceptions and invalidation

- **State:** NOT_RUN.
- **Owner phases:** P08,P09.
- **Owning atomic tasks:** P08-T01, P08-T02, P08-T03, P08-T04, P08-T05, P08-T07.
- **Positive / completion contract:** C0-C3 eligibility, true source-dependence groups, typed denominators review lineage and rare-event replay; supports drill down.
- **Negative / falsification control:** Copied poison not corroboration correlation not causation exception lost or revoked aggregate still served fails.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-INTEGRATION — Real agent memory and next-turn consumer

- **State:** NOT_RUN.
- **Owner phases:** P01,P09.
- **Owning atomic tasks:** P09-T01, P09-T02.
- **Positive / completion contract:** Installed facade write/reopen then actual new host request consumes bounded attributed context/gaps/handles under explicit scope.
- **Negative / falsification control:** Context not authority or implicit session restriction; old answer/source cannot substitute fresh required observation.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-TRANSFER — Source-compatible external memory tracks

- **State:** NOT_RUN.
- **Owner phases:** P09.
- **Owning atomic tasks:** P09-T05, P09-T06, P09-T09.
- **Positive / completion contract:** Verify dataset availability/version/license and map reviewed history/action sources to canonical locators; retrieval/fixed-generator/native tracks separate.
- **Negative / falsification control:** Unavailable dataset explicit; public QA/synthetic score cannot prove long-horizon external validity or untested language generalization.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-QUANTIZATION — Compression and search quality resource frontier

- **State:** NOT_RUN.
- **Owner phases:** P10.
- **Owning atomic tasks:** P10-T01, P10-T02, P10-T03, P10-T04, P10-T05, P10-T07.
- **Positive / completion contract:** Float32 exact control versus fp16/int8/binary/PQ/residual real reload/update/footprint/cost and ANN-cross controls.
- **Negative / falsification control:** Different backbone codebook leakage hidden rescoring storage/cost and ternary-weight analogy cannot justify gains.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-OPS — Operational coherence recovery and fault envelope

- **State:** NOT_RUN.
- **Owner phases:** P11,P12.
- **Owning atomic tasks:** P11-T01, P11-T05, P11-T07, P11-T08, P11-T10, P11-T11, P11-T13, P11-T14, P12-T06.
- **Positive / completion contract:** Approved real isolated backend delivery/fence/retry/readback/shadow/backup/restore/shutdown with measured convergence/purge/RPO/RTO.
- **Negative / falsification control:** Pre-existing meaningful state never destructively tested without backup/authority; lost data not regenerated silently; no unmeasured durability/SLO.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-SECURITY — Actual trust boundaries and poisoned memory

- **State:** NOT_RUN.
- **Owner phases:** P01,P03,P06,P08,P12.
- **Owning atomic tasks:** P12-T01, P12-T02, P12-T04, P12-T08, P12-T09.
- **Positive / completion contract:** Positive legitimate path plus injected/forged/malformed/resource/telemetry/private-history controls through actual host and source readers.
- **Negative / falsification control:** Canary absence checked not just redaction marker; poison repetition/model agreement cannot promote authority; zero observed not zero risk.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-CONFIRMATORY — Sealed fair study and qualified conclusions

- **State:** NOT_RUN.
- **Owner phases:** P13.
- **Owning atomic tasks:** P13-T01, P13-T02, P13-T03, P13-T04, P13-T05, P13-T06, P13-T07.
- **Positive / completion contract:** Owner-sealed pilot-derived endpoints/margins/power code/data/model/resource/custody manifest; full paired failures and predeclared statistics/costs.
- **Negative / falsification control:** Post-result thresholds dropped arms hidden fallback test peeking dirty/mismatched seal or unsupported claim invalidates confirmation.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-RESEARCH — Controlled measurement and honest inference

- **State:** NOT_RUN.
- **Owner phases:** P02-P13.
- **Owning atomic tasks:** P02-T03, P02-T05, P02-T08, P02-T09, P02-T10, P02-T11, P03-T11, P04-T08, P05-T09, P06-T10, P07-T08, P08-T08, P09-T07, P09-T10, P09-T11, P09-T12, P09-T13.
- **Positive / completion contract:** Paired published inputs, source/model/budget/clock manifests, hand-calculated and perfect/empty/shuffled scorer controls, observed retrieval stages, full attempt/failure accounting, family-cluster uncertainty and pilot-frozen decision criteria. Actual report reopens exact raw artifacts and declares inference scope.
- **Negative / falsification control:** Dropped errors, hidden label access, unequal resources, unobserved-stage metrics, model/coordinator labels called independent human truth, test tuning and post-result changed thresholds invalidate the affected claim. Null and unsupported outcomes remain visible.
- **Phase-local boundary:** P02 proves harness/scorer mechanics; later phases prove specific mechanism experiments. Neither establishes P13 locked superiority. Whole-gate PASS requires declared multi-phase scope and evidence, not a successful control alone.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## G-REPRODUCIBLE — Clean consumer and complete final evidence

- **State:** NOT_RUN.
- **Owner phases:** P13.
- **Owning atomic tasks:** P13-T08, P13-T09.
- **Positive / completion contract:** Fresh approved package/install/source/backup/projection/report reproduction plus full requirement and independent review audit.
- **Negative / falsification control:** Missing artifacts/provider/model cannot be silently substituted; seal-breaking retest recorded; unresolved material proof keeps outcome open.
- **Phase-local boundary:** Early producer checks do not prove later integration, longitudinal, multi-store or sealed efficacy consumers. Preserve PARTIAL until the whole declared contract is observed.
- **Evidence:** NOT_RUN; exact command/artifact/reader and scope receipt required.

## Owner setup and generative integration boundary

Existing `.venv/` and ignored `.env` do not close G-CONTRACT, G-INTEGRATION or any live-provider gate. Docs validation can use `.venv/Scripts/python.exe` now without credentials. Once an authorized feature uses generation, its real entry point must exercise Groq and one explicitly selected owner-permitted model through the actual downstream consumer; injected tests cover guards only. Provider/model identifiers and account availability are verified then, not inferred from key presence. Phase 1 remains WAIT_FOR_GO; this publication performs no runtime/provider test.
