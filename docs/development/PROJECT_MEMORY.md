# Norn project working memory

Updated 20 October 2026 (Asia/Bangkok). This is the single concise navigation memory; vision/source/MDP/ADRs remain authoritative.

## Stable baseline

- Repository: Norn; initial suite baseline `81badbd`, main, one worktree, vision only.
- Vision: [Subcortical Memory Blueprint v1.0](../vision/subcortical_memory_blueprint.md), 19 October 2026, 27 sections. It proposes research, not measured superiority.
- Current mandate: publish the verified suite plus owner setup/model policy and one tailored root AGENTS. Phase 1 is **WAIT_FOR_GO**; no runtime implementation or foreign-project edits.
- [MDP](MASTER_DEV_PLAN.md) owns technical contracts/schema/algorithms/flows and stable atomic cards. [README](README.md) assigns every supporting document's role.
- Actual runtime: absent. Proposed `src/norn/`, benchmark and test layout is conditional on [ADR-0002](ADR_LOG.md#adr-0002--runtime-and-package-layout). Owner-selected Python/uv environment exists at `.venv/`. Groq and three allowed generative options are accepted; runtime dependencies, embedding/reranker/training models, package layout and backends are not yet selected/installed.

## Architecture to preserve

One source-backed event can have multiple functional views. Event identity, atomic assertions, typed relationships and rebuildable projections are distinct. Similarity, activation, salience and model agreement never create authority. Current ACL/erasure applies before candidate ranking/traversal and again at return, even for historical content snapshots. Query evaluation clock and temporal basis are explicit. Read/derive may append permitted analytics, never edit facts silently.

Pilot proposal is local canonical SQL/blobs, transactional local outbox and in-process projections. External stores, distributed delivery, caches/replicas/shards are later measured operational treatments. Binding, loss, separation, graph, reconstruction, salience and consolidation are independent experiments with simpler winners retained when justified.

## Verified documentation checkpoint

P00 complete: MDP technical design plus 14 phases/139 atomic tasks, 30 gates and 137 traceability rows. Actual docs CLI checks all 15 Markdown files and passes 15 deliberate failure controls; main/full-blueprint end review resolved. Only six P00 cards and G-DOC are complete; 133 runtime/research cards and 29 runtime gates remain unexecuted. No model/data/provider/backend installed or called. Evidence: E-DOC-001 through E-DOC-004.

## Decisions and next work

Read [PROGRESS](PROGRESS.md) for the current task, [GOAL](GOAL.md) for checkable outcomes, [ADRs](ADR_LOG.md) for owner answers, [gates](TESTING_GATES.md) for proof, and [evidence](EVIDENCE_LOG.md) for observations. Pending runtime choices include package layout/dependencies, RETRACTED origin/status interpretation, retention/purge/parameter erasure, time/snapshot semantics, code reuse, embedding/reranker/training models/compute/backends and local-outbox translation. Recommendations are not accepted answers.

Only start/end reviewers may be delegated; current standing model is GPT6 Luna Medium. Main owns research, implementation and tests. No credentials/provider access goes to reviewers. End reviewer is reused for resolution. The current user separately authorized this scoped suite/setup/instructions push to main; it does not grant future main publication or Phase 1 GO.

## Reference limits and evidence

Palladion provides governed memory, source/provenance/reconciliation and independent benchmark examples, but its categories/session boundaries/payment policy are not Norn's multi-view memory. Source-checkpoint/license/consumer review precedes any port. Arcana's referenced old development plan is explicitly partly superseded and is format/depth guidance only. References were inspected read-only.

Documentation checker commands are in [README](README.md#validation-now). Runtime commands/tests in task cards are planned profiles only. No listener or provider is needed for suite validation. Update this memory at verified checkpoints without copying the full plan or status history.

## Owner setup amendment

ADR-0010/0011 record Groq options (Qwen 3.8 27B; GPT OSS 120B; GPT OSS 20B), explicit per-run selection without silent fallback, ignored root `.env`, owner `.gitignore`, existing uv `.venv/` and one root `AGENTS.md`. Interpreter metadata confirms CPython3.14.7. Key contents/validity and API model availability remain unverified; no live call occurred. Current amendment evidence is E-DOC-005.
