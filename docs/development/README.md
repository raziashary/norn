# Norn development suite

Updated 21 October 2026 (Asia/Bangkok). This suite translates the [research blueprint](../vision/subcortical_memory_blueprint.md) into an implementation and experimental program. P01 canonical runtime and P02 synthetic harness are verified (E-P01-003/E-P02-003). P03 is complete under ADR-0017/0018, with actual local R0–R3,540 development observations, installed source/native controls and sole end review resolved (E-P03-003; [baseline report](evidence/baselines.md)). Scientific superiority remains INCONCLUSIVE. P04 is active under approved ADR-0020/0021 with focused source/real-E5 controls E-P04-002; P05+ remain planned. No sealed efficacy study has run.

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

Owner setup: existing uv `.venv/`, ignored root `.env` and `.gitignore`. Future authorized generative inference uses Groq with explicit Qwen 3.8 27B, GPT OSS 120B or GPT OSS 20B selection (ADR-0010); key/API availability are not tested now. P01 layout/tooling/timezone data are approved and locked; P03 local models are separately approved in ADR-0017/0018; later training/backends remain separate decisions.

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
uv sync --locked --extra retrieval
uv run --no-env-file norn capabilities
uv run --no-env-file norn --store .norn init
uv run --no-env-file --extra retrieval pytest -q
uv run --no-env-file ruff check src benchmark tests
uv run --no-env-file ruff format --check src benchmark tests
uv run --no-env-file mypy
uv build
uv run --no-env-file python tests/test_foundation_cli.py
```

`uv sync` installs approved locked tooling and tzdata; it does not load `.env`. The retrieval extra adds the owner-approved pinned local runtime and is needed for the full current test suite. Asset-free R0 itself uses the base package. The foundation smoke creates/cleans an isolated synthetic store and invokes separate CLI processes for write, restart/read, duplicate delivery, correction, historical snapshot, revoke and deny. It also runs against a fresh installed wheel in the P01 closeout evidence. No Groq use or service is needed. `norn --help` lists operations; `capabilities` distinguishes available paths from explicitly enabled local models.

For a manual write, save this synthetic request as a local JSON file, then run `norn --store .norn write --input <file>` using the uv prefix above:

```json
{"request_id":"parking-1","delivery":"delivery-1","occurrence":"tuesday-1","content":"Alex parked in ZoneA.","event_time":{"kind":"EXACT","start":"2026-10-20T09:00:00+00:00","source_timezone":"UTC"},"observed_at":"2026-10-20T09:01:00+00:00","schema_version":1,"atoms":[{"subject":"Alex","predicate":"parked_in","value":{"tag":"TEXT","value":"ZoneA"},"start":0,"end":21,"epistemic":"USER_REPORTED","qualifiers":{"scope":"parking"}}]}
```

Use the returned event ID with `read <event_id> --evaluation-time 2030-01-01T00:00:00+00:00 --timezone UTC --basis VALID_TIME --valid-at 2026-10-20T09:00:00+00:00 --knowledge-at 2030-01-01T00:00:00+00:00`. Clocks are explicit; the example's future query evaluation is synthetic. `resolve-time yesterday --evaluation-time 2026-03-09T16:00:00+00:00 --timezone America/New_York` resolves a request-clock interval without opening a store. `journal --after <commit_seq> --limit 100` reads stable publication pages and does not claim indexing. Identical bytes at different occurrences remain different events. Source paths, approval and principal fields are rejected in write JSON.

The CLI trusts its local OS operator and store-directory permissions. `--principal`/namespace options configure the trusted host; they are not authentication for an untrusted network caller. Embedding hosts supply `HostIdentity` after their own authentication. Current grants are READ/WRITE/ADMIN across the declared namespace. A reader's revoked grant or source tombstone blocks even historical content and held evidence views. Preserve that host boundary before exposing an API.

Fixture annotations are explicit span checks, not general semantic extraction. SUPPORTED means eligible anchored fixture evidence; it does not establish normative authority or real-world truth. Inference/hypothesis/aggregate alone do not support that outcome. Corrections require matching subject, predicate and qualifiers, an explicit validity window and ADMIN for supersession. Reads never rewrite facts. Exact canonical reads report CANONICAL_FALLBACK/INDEX_PENDING and do not promise lexical/dense/graph coverage.

`deny` applies immediate serving denial and returns a metadata-only pending purge manifest, including actual blob and projection artifact digest selectors. Shared selectors remain pending until reference/retention reconciliation; they do not authorize erasing unrelated occurrences. SQL/blobs/derived representations/traces/backups remain explicit PENDING obligations; no full erasure or parameter unlearning is implemented. `backup <new-directory>` verifies a single-namespace local SQL/blob/projection copy, including existing tombstones and exact projection readback. Reconciliation of older backups against later deletions, distributed workers, purpose-specific normative approval, arbitrary NLP and research efficacy belong to later phases. No power-cut or production-readiness claim follows from local process-crash tests.

## Conventional retrieval — P03 verified local pilot

`norn --store <store> project` explicitly consumes the local journal, builds the lexical
projection, verifies exact artifacts and publishes a ready snapshot. A subsequent
write/control change requires a new projection; missing or corrupt readiness yields
VERIFICATION_UNAVAILABLE. Original canonical `read` remains an exact fallback.
For `recall --input <JSON>`, the question's requested fields are explicit host inputs:

```json
{"text":"Alex parking","subject":"Alex","requested_fields":["parked_in"],"arm":"R0","clock":{"evaluation_time":"2030-01-01T00:00:00+00:00","timezone":"UTC","basis":"VALID_TIME","valid_at":"2026-10-20T09:00:00+00:00","knowledge_at":"2030-01-01T00:00:00+00:00"},"event_start":"2026-10-20T00:00:00+00:00","event_end":"2026-10-21T00:00:00+00:00"}
```

Fields are a prerequisite schema, never hidden evaluator slots. Unsupported natural-language
adjudication stays unknown. Cited facts retain original origin, applicability and UNVERIFIED
authority; a supported source assertion never authorizes an action. All five answer statuses,
coverage, content snapshot, current security epoch, tokenizer and bounded usage are explicit.
Asset-free R0 counts Unicode words in the full evidence packet; model-enabled comparisons
count the same pinned E5 tokenizer for every arm, including status and locators.

ADR-0017 pins multilingual E5-small, the mMARCO MiniLM reranker and the optional packages.
Model acquisition is separately enabled and verifies publisher byte lengths/SHA256s:

```powershell
uv run --locked --no-env-file --extra retrieval python -m norn.embedding.assets .norn/models --enable-download
uv run --locked --no-env-file --extra retrieval python -m norn.embedding.baseline .norn/models --enable-models --check-controls
uv run --locked --no-env-file --extra retrieval norn --store <store> --model-root .norn/models --enable-models project
uv run --locked --no-env-file --extra retrieval norn --store <store> --model-root .norn/models --enable-models recall --input <JSON>
```

R1 uses compatible normalized384-dimensional vectors with exhaustive dot products; R2
adds exact/BM25/dense RRF; R3 reranks the same bounded pool. One CPU model worker is resident
at a time, with serial inference,512-token input truncation disclosed, bounded JSON IPC and
owned-process shutdown on deadline/cancellation. No automatic model/provider fallback or
Groq call occurs. Missing assets or explicit enablement cannot produce fake vectors.
Optional FAISS HNSW is an offline same-vector approximation diagnostic, not graph memory.

The actual development runner and reopened report are:

```powershell
uv run --locked --no-env-file --extra retrieval norn-benchmark run-baselines <new-run> --model-root .norn/models --enable-models
uv run --locked --no-env-file --extra retrieval norn-benchmark baseline-report <run> --model-root .norn/models --output <new-report.json>
uv run --locked --no-env-file --extra retrieval python -m benchmark.runs.ann_recall <run> <new-ann.json> --model-root .norn/models --enable-models
uv run --locked --no-env-file --extra retrieval python tests/test_recall_cli.py --model-root .norn/models
```

The four-arm run uses all135 development cases and distinct canonical occurrences for
published source records. It preserves public-ID mappings only after original source
readback; source aliases do not merge identity. Artifacts retain full failures, exact
pins, offline build/online cold/repeated costs and observed stage counts. Only final
evidence is scored; counts do not establish upstream retrieval@K. The public question
interpreter is a frozen pilot schema vocabulary, not general semantic extraction. Its v3
prerequisites combine the declared public schema and question cues independently of
available evidence. Chain handling preserves neighboring source eligibility and explicitly
leaves typed-path sufficiency unestablished; field support alone does not prove a chain.
These disjoint synthetic instances do not establish template/category transfer, real-world
entailment, production capacity or locked superiority. Preserve original stores for replay:
their actual canonical ingestion clocks are part of the evidence. Recreating a store after
the fixed synthetic knowledge cutoff is a different profile, not an invitation to backdate.
## Synthetic benchmark harness

P02 uses deterministic fictional structured capture records, not arbitrary-language extraction
or a production retrieval system. From the repository root:

```powershell
uv run --no-env-file norn-benchmark run-controls .norn/my-controls --judgments docs/development/evidence/label_judgments.json --arms perfect empty shuffled extractive error timeout unsupported invalid not_run native:R4 native:R5 native:R6
uv run --no-env-file norn-benchmark validate .norn/my-controls --report .norn/my-scorecard.json
uv run --no-env-file norn-benchmark --help
```

Choose a new run/report path; artifacts are created exclusively and cannot be overwritten.
Reopening verifies code/source/gold/audit/input digests, declared pairs, every ledger row,
attempts, raw/normalized results, exact source locators, stages and budgets. Code changes
invalidate old runs. Artifacts stay ignored under `.norn/`; preserve the manifest and
completion digests in an evidence receipt before using a report.

The `perfect` arm is an evaluator-gold oracle diagnostic. Common controls receive only
strict published captures; `extractive` is a lexical-overlap mechanics control, not BM25/R0.
Native R4/R5/R6 entries report UNSUPPORTED and ingestion/model differences explicitly.
Fault controls inject envelopes rather than exercising real backend failures. Results
measure harness mechanics, not memory quality, security against hostile plugins or
research efficacy. P03 owns actual retrieval; later phases own real graph/fault/transfer studies.

The owner personally reviewed the exact42-case [audit pack](evidence/label_audit.md);
[judgments](evidence/label_judgments.json) bind each reviewed source/gold pair. No disputes
were reported. The remaining cases are constructed and unaudited. Changing reviewed
sources/gold invalidates bindings. Omit `--judgments` only for an explicitly unaudited
mechanics run; its report remains PENDING_OR_DISPUTED. Role/partition options separate
smoke, development and calibration; locked confirmation is deliberately unavailable here.

`calibrate <run-directory> <new-output.json> --arm confidence` reopens a verified
calibration/calibrator run and fits actual probability/correctness rows. Generate its
math-only forecasts with `run-controls <new-directory> --partition calibration --role
calibrator --arms confidence`; this explicitly named control emits constant0.5 forecasts.
The artifact binds manifest/completion/arm lineage, bins/counts and raw/calibrated
fit-sample scores. Self-labeled JSON or relabeled smoke runs cannot supply calibration.
These scores are not held-out performance. Confidence-free controls cannot be fitted.
Cluster/bootstrap controls are exploratory, training seeds remain null when no learning
occurs, and small samples produce no interval. No practical margins/power or locked
protocol has been selected. No Groq call, model download, database or listener is needed.

Qualified partial cases carry source-supported claim subsets and explicit unknown fields.
Their full CompleteSet remains unavailable when a required source is missing, while
partial correctness/usefulness are reported separately. A full answer on that incomplete
snapshot counts as an overclaim. Five-status classification, ambiguity/missing-reason
accuracy and both answer/refusal failures retain their applicability denominators.

## Opt-in functional views and binding

P04 source and focused controls are implemented under ADR-0020; final full comparison, installed trained-checkpoint smoke and end review remain pending. See the current [binding evidence](evidence/binding.md) and E-P04-004 for exact source/version boundaries. Existing R0–R3 defaults are preserved. With an existing synthetic store and already acquired approved local model assets:

```powershell
uv run --locked --no-env-file --extra retrieval norn --store .norn/my-store --model-root .norn/models --enable-models binding-project --variant B1
uv run --locked --no-env-file --extra retrieval norn --store .norn/my-store --model-root .norn/models --enable-models binding-recall --variant B1 --input .norn/my-recall.json
```

The input uses the same explicit clock/prerequisite RecallRequest JSON as conventional recall. B0/B1/B2 need no learned checkpoint. B3/B4/S3/S4 require `--checkpoint` from a completed, version-compatible bounded training run on both project and recall; a random or wrong-method checkpoint cannot stand in. Projection readback is immutable and source-qualified; a canonical write or security change requires a new current projection. All candidates still pass current access, scoped temporal/source resolution and the existing evidence assembly. B5 explicitly refuses with FEATURE_NOT_SUPPORTED.

The separate explicit `binding-prepare`, `binding-train`, `binding-evaluate` and `binding-report` benchmark commands support immutable stage receipts. `binding-run <new-directory> --model-root .norn/models --enable-models` performs those stages; `--smoke` chooses only a mechanical15-case-per-role profile/16 updates, not the full276/138/138-case study. These commands consume approved local CPU work and cannot overwrite a prior run. No live generator, source reward inference, graph mechanism or provider call is implied.
