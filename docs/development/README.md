# Norn development suite

Updated 20 October 2026 (Asia/Bangkok). This suite translates the [research blueprint](../vision/subcortical_memory_blueprint.md) into an implementation and experimental program. P01 canonical runtime is implemented and verified (E-P01-003); later research components remain planned. Current mandate includes the owner setup/instructions amendment and scoped publication; Phase 1 is **DONE** under ADR-0012, with proof E-P01-003.

Read the root [project instructions](../../AGENTS.md), then start with [current progress](PROGRESS.md), [goal](GOAL.md), and [working memory](PROJECT_MEMORY.md), then read the relevant parent phase and exact atomic card in the [master development plan](MASTER_DEV_PLAN.md). First-time contributors read the complete blueprint. The MDP contains the technical design: contracts, schema, algorithms, flows, ownership, execution order, and task-level proof.

| Document | Owns | Read when |
|---|---|---|
| [MASTER_DEV_PLAN.md](MASTER_DEV_PLAN.md) | Detailed proposed engineering design and authoritative atomic task register | Implementing or reviewing any capability |
| [GOAL.md](GOAL.md) | Checkable documentation and system outcomes | Establishing scope and completion |
| [ADR_LOG.md](ADR_LOG.md) | Decisions, alternatives, owner answers, and supersession | A choice affects architecture, contracts, or experiments |
| [TESTING_GATES.md](TESTING_GATES.md) | Durable verification contracts and phase-local obligations | Designing/running proof or closing a phase |
| [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) | Blueprint requirements to tasks, gates, and design sections | Checking coverage and missing consumers |
| [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md) | Comparison fairness, dataset custody, statistics, and promotion rules | Generating data, training, selecting, or measuring an arm |
| [PROGRESS.md](PROGRESS.md) | Current checkpoint and derived phase summary | Recovering an active session |
| [READINESS_MATRIX.md](READINESS_MATRIX.md) | Capability evidence and explicit limits | Assessing what can actually be used |
| [PROJECT_MEMORY.md](PROJECT_MEMORY.md) | Concise navigation and stable facts | Resuming work |
| [PROJECT_MAP.md](PROJECT_MAP.md) | Actual repository plus explicitly proposed module/dependency map | Finding owners and data paths |
| [RISKS_AND_OPEN_QUESTIONS.md](RISKS_AND_OPEN_QUESTIONS.md) | Unresolved choices, failure mechanisms, and owners | Before dependent work |
| [PROJECT_LEARNING.md](PROJECT_LEARNING.md) | Evidence-backed lessons and retractions | Avoiding repeated mistakes |
| [EVIDENCE_LOG.md](EVIDENCE_LOG.md) | Commands, review receipts, findings, and proof boundaries | Verifying a completion claim |
| [check_docs.py](check_docs.py) | Structural checker and adversarial self-tests | Editing or closing the suite |

## Authority

Current user instructions and applicable AGENTS govern work. The vision owns intended scope. Implemented source/schema and executed checks own actual behavior. The MDP is the proposed implementation translation; a conflict with the vision must be surfaced, not silently resolved by changing the vision. ADR recommendations are not owner approval. Task checkboxes are status, not evidence. Memory/map/readiness summarize their authorities rather than introducing competing requirements.

All durable agent-created project work records belong in this folder. Do not add parallel plans or duplicate working memories. Large run outputs/checkpoints will live in an explicitly configured artifact root, with redacted manifests and receipts linked here; they are not committed by default.

## Validation now

Owner setup: existing uv `.venv/`, ignored root `.env` and `.gitignore`. Future authorized generative inference uses Groq with explicit Qwen 3.8 27B, GPT OSS 120B or GPT OSS 20B selection (ADR-0010); key/API availability are not tested now. P01 layout/tooling/timezone data are approved and locked; later models/backends remain separate decisions.

From the repository root, using the existing environment:

```powershell
.venv/Scripts/python.exe docs/development/check_docs.py
.venv/Scripts/python.exe docs/development/check_docs.py --self-test
.venv/Scripts/python.exe -c "from pathlib import Path; p=Path('docs/development/check_docs.py'); compile(p.read_text(encoding='utf-8'),str(p),'exec')"
git diff --check
```

The checker validates links, IDs, task metadata/dependencies, coverage, and status consistency. It cannot prove the science, runtime algorithms, SQL migrations, ACL enforcement, or research outcomes. Those remain separate gates. No provider call, model download, database, or listener is required for documentation validation.

## Reference use

Palladion supplied a useful anchor/atomic-card format. Arcana's historical development plan supplied the desired technical depth. Neither transfers product architecture, permissions, measured results, or old implementation claims to Norn. The [reuse boundary](MASTER_DEV_PLAN.md#reference-reuse) records the selected candidates and their adaptation costs.

## Local foundation

P01 implements a **synthetic-only canonical store**. Reuse the existing environment:

```powershell
uv sync --locked
uv run --no-env-file norn capabilities
uv run --no-env-file norn --store .norn init
uv run --no-env-file pytest -q
uv run --no-env-file ruff check src tests
uv run --no-env-file ruff format --check src tests
uv run --no-env-file mypy
uv build
uv run --no-env-file python tests/test_foundation_cli.py
```

`uv sync` installs approved locked tooling and tzdata; it does not load `.env`. The smoke script creates/cleans an isolated synthetic store and invokes separate CLI processes for write, restart/read, duplicate delivery, correction, historical snapshot, revoke and deny. It also runs against a fresh installed wheel in the P01 closeout evidence. No Groq use or service is needed. `norn --help` lists operations; `capabilities` reports disabled optional features explicitly.

For a manual write, save this synthetic request as a local JSON file, then run `norn --store .norn write --input <file>` using the uv prefix above:

```json
{"request_id":"parking-1","delivery":"delivery-1","occurrence":"tuesday-1","content":"Alex parked in ZoneA.","event_time":{"kind":"EXACT","start":"2026-10-20T09:00:00+00:00","source_timezone":"UTC"},"observed_at":"2026-10-20T09:01:00+00:00","schema_version":1,"atoms":[{"subject":"Alex","predicate":"parked_in","value":{"tag":"TEXT","value":"ZoneA"},"start":0,"end":21,"epistemic":"USER_REPORTED","qualifiers":{"scope":"parking"}}]}
```

Use the returned event ID with `read <event_id> --evaluation-time 2030-01-01T00:00:00+00:00 --timezone UTC --basis VALID_TIME --valid-at 2026-10-20T09:00:00+00:00 --knowledge-at 2030-01-01T00:00:00+00:00`. Clocks are explicit; the example's future query evaluation is synthetic. `resolve-time yesterday --evaluation-time 2026-03-09T16:00:00+00:00 --timezone America/New_York` resolves a request-clock interval without opening a store. `journal --after <commit_seq> --limit 100` reads stable publication pages and does not claim indexing. Identical bytes at different occurrences remain different events. Source paths, approval and principal fields are rejected in write JSON.

The CLI trusts its local OS operator and store-directory permissions. `--principal`/namespace options configure the trusted host; they are not authentication for an untrusted network caller. Embedding hosts supply `HostIdentity` after their own authentication. Current grants are READ/WRITE/ADMIN across the declared namespace. A reader's revoked grant or source tombstone blocks even historical content and held evidence views. Preserve that host boundary before exposing an API.

Fixture annotations are explicit span checks, not general semantic extraction. SUPPORTED means eligible anchored fixture evidence; it does not establish normative authority or real-world truth. Inference/hypothesis/aggregate alone do not support that outcome. Corrections require matching subject, predicate and qualifiers, an explicit validity window and ADMIN for supersession. Reads never rewrite facts. Exact canonical reads report CANONICAL_FALLBACK/INDEX_PENDING and do not promise lexical/dense/graph coverage.

`deny` applies immediate serving denial and returns a metadata-only pending purge manifest, including actual blob digest selectors. Shared blob selectors remain pending until reference/retention reconciliation; they do not authorize erasing unrelated occurrences. SQL/blobs/derived representations/traces/backups remain explicit PENDING obligations; no full erasure or parameter unlearning is implemented. `backup <new-directory>` verifies a single-namespace local SQL/blob copy, including existing tombstones. Reconciliation of older backups against later deletions, distributed workers, purpose-specific normative approval, arbitrary NLP and research efficacy belong to later phases. No power-cut or production-readiness claim follows from local process-crash tests.
