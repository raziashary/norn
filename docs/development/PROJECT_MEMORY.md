# Norn project working memory

Updated 21 October 2026 (Asia/Bangkok). Navigation only; blueprint, current source, MDP and ADR owner answers remain authoritative.

## Current state and authority

P00–P03 are complete:41/139 atomic tasks, including P03 DONE12/12. P01/P02 are published at4618156/1b86549. P03 is verified locally under ADR-0017/0018, with final proof E-P03-003 and report [baselines](evidence/baselines.md). P04+ have no mandate. P03 main publication needs separate owner approval; the prior P02 push authority is fulfilled. Current checkout is C:/norn on main, one worktree. Preserve owner BasedPyright settings and ignored setup.

## Actual architecture and boundaries

- contracts: immutable identity, tagged values, separate epistemic origin/status, explicit aware clocks, intervals, query budgets and snapshots.
- canonical: digest-addressed UTF-8 sources/spans, distinct occurrences/entities, immutable assertions and scoped corrections, atomic journal/outbox. Schema1 plus additive schema2 lineage and schema3 projection manifests/readbacks/readiness. Populated upgrades verify a restorable backup first.
- governance: trusted-host current namespace READ/WRITE/ADMIN, epoch/tombstones before search and return; scoped temporal reads and field sufficiency. Denial is immediate; physical purge/backup reconciliation remain pending. Source evidence and model agreement never authorize an action.
- extraction: explicit source-anchored fixture annotations; arbitrary NLP/causal or normative adjudication is absent.
- retrieval/projection: pre-window eligibility and canonical readback, exact/BM25 R0, real normalized384-dimensional exhaustive E5 R1, canonical RRF R2, actual MiniLM reranker R3; full-packet tokens and five qualified field-support statuses. Local immutable artifacts/readbacks, contiguous replay and ready snapshots are rebuildable from canonical truth. Current security overrides historical content. FAISS ANN is a separate same-vector diagnostic.
- embedding/telemetry: explicitly enabled pinned FP32 local CPU models, bounded JSON worker IPC, one resident model at a time, one query-budget owner, native cancel/deadline termination and redacted observed stage/cost traces. No fake fallback or automatic provider call.
- integration/CLI: actual write/read/project/recall/correct/revoke/deny/backup consumers; held reply serialization rechecks current security. Canonical fallback remains INDEX_PENDING. Host authenticates principals; local CLI configuration is trusted operator input.
- benchmark: separate hidden world/gold and published inputs, immutable full failure ledger, public-only baseline adapter, reopened source/cost validation and clustered exploratory reports. Runtime has no hidden-label edge. Public interpreter v3 preserves explicit schema/cue prerequisites even when evidence is missing; typed-path/general entailment remains unestablished.

## Final P03 proof and interpretation

Frozen runtime/evaluator digest `dbf116ad26b6633a6ad61da922716743b2f0fa63aa1734f6aad2e5cb859835ba`; source/tool/test manifest120 files `ca3b396cbef1be09bf79e58381378e1a37b4085ac6d69f01593178635abca24a`. Ruff/format/strict mypy77 modules pass;131 tests/no skips pass. Build007 and fresh isolated installed wheel have80 byte-identical Python/SQL files, outside-checkout imports, actual all-arm source/correction/revoke smoke and native cancellation/deadline proof.

`.norn/p03-development-005` completed540 pairs:528OK/12UNSUPPORTED, no errors/timeouts/invalid/missing pairs. All six post-driver stages exit0: report, standalone readback, six semantic corruption controls, ANN,007 installed parity and actual installed CLI/native controls. Artifacts/hashes/commands are in E-P03-003; full raw logs/models/runs are ignored under .norn. No model command or post-driver remains active. Sole end reviewer `/root/p03_end_review` (GPT6 Luna Medium) directly read full blueprint/source and final artifacts; material findings resolved. Reuse that reviewer if a resolution check becomes necessary.

Scientific outcome INCONCLUSIVE: CompleteSet41/49 R0–R2 versus44/49 R3; equal-cluster gain .07143 with exploratory95% interval[0,.21429]. False answers6/83 and false abstentions9/50 remain in every arm; five-status109/132. All135 development cases unaudited, reused after a documented interpreter defect repair; the owner's earlier42-case P02 audit is a different pack. ANN444 measurements have N1–7, only9 queries k<N, no useful-scale/speedup claim. Costs measured CPU-serial on a memory-constrained desktop, not SLO/capacity evidence. Keep cheap R0 reference and R3 challenger, without superiority/neural/production claims. Cross-phase gates remain partial.

Earlier001/002/003 incomplete attempts, completed004/v2, failed source-mutation guard and prior wheels remain preserved and version-scoped in E-P03-001/002. V3 repaired release-only evidence incorrectly losing an explicitly requested rollback prerequisite; actual EN/ID public consumer and independent review confirm the fix, while other measured errors remain visible.

## Environment and recovery

Owner uv environment/Python3.14.7, Hatchling, pytest/Ruff/mypy/build and tzdata are reused. Optional retrieval dependencies and model pins are owner-approved in ADR-0017; isolated workers in ADR-0018. Use `uv run --locked --no-env-file --extra retrieval ...` for model/test commands; default uv profiles can remove optional dependencies. No .env read/load, Groq call, training, foreign checkout mutation or network listener occurred. Future authorized generation must use Groq and an explicit allowed model; account identifiers/availability remain unverified.

Read latest user scope, PROGRESS/GOAL, exact MDP card/dependencies, ADR answers, relevant blueprint headings/I1–I10, gates/risks and actual producer/reader bodies before new work. Main owns exploration/code/tests; start adversary and sole end reviewer only, GPT6 Luna Medium, credential-free/read-only. P04+ need their own mandate and decisions. Physical purge, external delivery/restore, broader graph/security, independent labels, locked confirmation and external agent transfer remain future obligations.
