# Norn project instructions

These instructions supplement the user's universal development rules and apply to the whole Norn repository. Keep one root `AGENTS.md`; do not copy the reference projects' separate instruction trees or historical exceptions into Norn.

## Authority and task recovery

1. Read the latest user request, these instructions, and the [MDP task protocol](docs/development/MASTER_DEV_PLAN.md#execution-contract). Confirm the repository, branch, diff, recent commits and worktrees; preserve unrelated work.
2. Read [GOAL](docs/development/GOAL.md), [PROGRESS](docs/development/PROGRESS.md), [PROJECT_MEMORY](docs/development/PROJECT_MEMORY.md), the parent phase, exact atomic card, dependencies, affected ADR owner answers and [risks](docs/development/RISKS_AND_OPEN_QUESTIONS.md).
3. First onboarding reads the complete [blueprint](docs/vision/subcortical_memory_blueprint.md). Every task rereads its affected named headings and I1-I10, plus the owning [gates](docs/development/TESTING_GATES.md), [traceability](docs/development/REQUIREMENTS_TRACEABILITY.md), and actual producer/reader bodies, schema and tests. Benchmark work also reads the [research protocol](docs/development/RESEARCH_PROTOCOL.md).
4. Current user directions govern scope/permission; the blueprint governs intended outcomes; source/schema, executed checks and measurements establish actual behavior. A planned path, illustrative snippet, passing import, comment or old status is not proof. Verify a named producer exists before building its consumer.
5. Before a phase starts, verify its mandate and prerequisites. **Phase 1 remains WAIT_FOR_GO until the user explicitly gives GO.** Documentation publication and an existing environment/key do not authorize implementation, training or live calls. Once a later multi-phase mandate is given, continue within it without repeated permission requests.

## Architecture and source integrity

- The [MDP](docs/development/MASTER_DEV_PLAN.md) owns detailed algorithms, schemas, flows, module ownership and atomic tasks. All durable project plans, memory, map, decisions, progress, learning and evidence belong in `docs/development/`; keep exactly one working memory and map. Root instructions own workflow, not a second architecture specification or live status history.
- Norn studies multiple functional views of one canonical experience. Keep event identity, atomic assertions, typed relationships, source evidence and derived projections distinct. Do not import Palladion's session-only episodic memory, preference classifier, four-tool limit, payment policy or critic architecture.
- Preserve immutable source provenance and append explicit corrections. Reads and derived views may append permitted analytics but cannot silently rewrite facts or promote epistemic origin. Similarity, graph activation, salience, frequency, consolidation and model agreement never grant truth, approval or access.
- Apply current tenant/scope/ACL/erasure controls before candidate ranking and graph traversal and again before returning evidence, including historical snapshots. Denied nodes cannot become intermediaries or leak through counts, paths or context.
- Enforce explicit evaluation clock, event/valid/knowledge-time basis, source/model/projection version and capability snapshot. Similar episodes remain distinct; corrections require scoped relationships, not blanket latest-wins.
- Canonical records own truth; vectors, graph, caches, summaries and bindings are rebuildable with lineage. Local pilot outbox and later external-store guarantees remain distinct. Optional models/backends stay explicitly enabled treatments, not automatic infrastructure.
- Ground changes in existing owners and simplify only within authorized scope. Trace callers, exports, dynamic/configuration paths and consumers before declaring code dead. Broader abstractions, shipped contract changes and destructive operations retain the user's escalation rules.

## Decisions and progress

- Execute one bounded atomic card with exact file ownership, inputs, consumer and proof. MDP owns task state; PROGRESS derives summaries. A parent closes only with its required child work and own exit proof.
- Log material decisions immediately in [ADR_LOG](docs/development/ADR_LOG.md): Question, Why, Options, Recommendation, What affects what, My answer (editable), Status, Authority and Verification. Read the actual owner answer before dependent work. Proposed/empty answers are not approval; preserve prior answers when superseding.
- Keep task state, gate evidence and scientific retain/reject outcome separate. A valid null result can finish an investigation while rejecting its mechanism. Preserve failures, unsupported cases and inconclusive evidence; do not manufacture a favored win.
- Fix directly in-scope unambiguous defects at their owner; document out-of-scope issues with consequence/owner/destination. Retract a mistaken load-bearing claim visibly with its error mechanism and new evidence rather than deleting history.
- Update affected goal/plan/gates/traceability/progress/readiness/map/memory/learning/navigation in the same logical unit. A source or plan change that stales a document must be corrected or explicitly raised for owner judgment.

## Python environment, Groq and secrets

- The user selected uv and already created `.venv/`. Reuse and inspect that environment; do not recreate it or install packages as part of documentation work. Runtime packaging/layout and dependencies remain subject to their ADRs and Phase 1 mandate.
- **Use Groq whenever an authorized task requires generative LLM inference.** Allowed options: **Qwen 3.8 27B**, **GPT OSS 120B**, **GPT OSS 20B**. Select one explicitly per run and record provider/model; no unannounced provider/model fallback or invented default. Verify exact API identifier and account availability before its first authorized integration call. This policy does not select embedding/reranker/training backbones or hardware.
- Credentials stay in the ignored repository-root `.env`. The user supplied a Groq key; its validity and variable name are not presumed verified. Never print, commit, copy to worktrees, place in logs/prompts or dispatch secrets to agents. Read/load credentials only for the specific authorized command that needs them, with explicit live enablement and bounded attempts/time/cost.
- Ordinary tooling/tests use credential-free paths, such as `uv run --no-env-file ...` once their commands exist. Credential presence is capability, not intent to spend. Free-tier intent does not waive quotas, failure accounting or budgets.
- Generative integration proof must exercise the actual approved Groq entry point and downstream consumer. Injected/fake responses can test deterministic guards but cannot substitute for live-provider proof. Do not make live calls merely to update these instructions or test whether a key exists.
- Preserve the owner's `.gitignore`. Verify `.env`, `.venv/` and other local assets stay excluded before each commit; never force-add them. No secrets or bulk generated datasets/checkpoints/run artifacts are committed.

## Evidence and validation

1. Prove producer-to-reader behavior through the actual public engine/CLI/adapter, including persistence reopen/restart and source readback. A helper with no caller or a matching source string does not prove integration.
2. Give guards positive and negative controls that can fail for the intended reason; distinguish rejection from syntax/import/setup failure. Check forbidden canaries are absent from actual outputs, not just that a redaction marker appears.
3. Run the stack's required syntax/type/lint/build/tests and owning gates, then a representative runnable-output smoke. Bind exact commands/resources before execution. Skipped or unavailable checks stay explicit; do not label them PASS.
4. Record exact commands, exits, source/data/model/config hashes, observed counts, actual consumer, failure limits and cleanup in [EVIDENCE_LOG](docs/development/EVIDENCE_LOG.md). Do not truncate away failures, filter to success lines, substitute unconditional success, or claim more than the checked scope.
5. Measure comparable baselines before performance/capacity/optimization claims. Disclose provider/tokenizer, eligible corpus, clock, observed retrieval stage, cache/workload/concurrency and resource budget. A citation proves provenance, not semantic entailment; no hits do not prove unsupplied evidence absent.
6. Bound candidate/token/model/graph unique and repeated work, deadlines/cancellation, queues, connections and retry ownership. Count failed attempts; disclose truncated/degraded capability. Stop task-owned services/watchers/children and verify their ports free; leave pre-existing resources alone.

For documentation-only work, the actual runnable entry point is:

```powershell
.venv/Scripts/python.exe docs/development/check_docs.py
.venv/Scripts/python.exe docs/development/check_docs.py --self-test
git diff --cached --check
```

The checker proves structure and references, not runtime science. Check all new files in the staged diff; an unstaged diff does not cover untracked files.

## Benchmark independence and scientific claims

- Keep hidden world/gold/required evidence slots/evaluator labels separate from runtime and arm-visible sources, IDs, prompts, graph builds, vectors and traces. Benchmark reaches memory or external systems through declared public adapters, never privileged private/gold imports. A Norn in-process public adapter is permitted; Palladion's HTTP-only product constraint is not imposed here.
- Use synthetic fictional data and isolated mock observations until explicitly authorized otherwise. Partition by scenario/entity family before paraphrases; separate development, calibration and locked test. Native/common-input tracks disclose source visibility, model, extraction and budget differences.
- Every metric needs hand-computed and perfect/empty/shuffled controls with explicit applicability denominators. Missing/unsupported/invalid/timeout outcomes remain results with declared failure semantics, never silently dropped or indiscriminately converted into accuracy zero.
- Pilot-derived numeric thresholds are frozen before locked confirmation. A seal break/retest is recorded and limits the result; no quiet test tuning. Distinguish retrieval, fixed-generator QA and native end-to-end effects. Report false answers and false abstentions, severe privacy/fabrication events, paired family-cluster uncertainty and offline/online costs.
- Do not claim hypothesis success, superiority, neural equivalence, semantic accuracy, external validity or production readiness without their scoped required evidence. Zero observed failures are not zero risk. A simpler winning baseline is a valid outcome.

## Reviewer and live-resource boundaries

- Delegate only the start adversary and end reviewer for substantial phases, both **GPT 6 Luna Medium** (`gpt-6-luna`, `medium`); reuse the end reviewer for resolution. Main performs all exploration, implementation, test authoring/execution and intermediate checks. Do not inherit the benchmark reference's historical Haiku rule or extra-auditor exceptions.
- A reviewer brief is self-contained: current user scope, complete blueprint, relevant research protocol/ADRs, phase tasks, exact source/diff/proof inputs, output contract and read-only prohibitions. Strip live-resource credentials; never grant secrets, git/external mutations, broad tests or unbounded resource access. Both reviewers directly read the full blueprint for a substantial phase; a coordinator summary does not replace it. Main verifies material findings and owns decisions/status.
- Treat reachable meaningful state as irreplaceable. Identify destructive tests/commands first. Prefer credential-free suites and disposable synthetic resources. Before drop/reset/truncate/schema rewrite/migration-down or destructive tests against meaningful state, verify a restorable backup and record its location, or obtain the required owner direction. Fresh schema, populated upgrade, interrupted recovery and restore are separate proofs.
- If data is lost, stop and report what is gone, what survives and which backups exist. Do not silently regenerate or paper over loss.

## Closeout and version control

For a substantial authorized phase: start adversary → bounded implementation → stack validation and actual smoke → owning gates → sole end review and resolution → evidence/learning/status/no-stale sweep → owned resource cleanup → deliberate staged diff and secret review → Conventional Commit with descriptive body → continue only within the current mandate.

Stage exact owned paths. Review every outgoing commit's full subject/body. Push only to the current branch's established upstream under applicable approval; current user approval covers this documentation/setup/instructions publication only. It is not standing permission for later main pushes or Phase 1. Main/shared/first-branch pushes, PRs, tags/releases, force/history rewrite, deletion, destructive data and shipped-contract changes retain the universal explicit-approval rules. Rejected/diverged push: no force; inspect/fetch, report and ask. Never change git config, hooks, remotes or stored credentials.
