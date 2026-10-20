# Norn development suite

Updated 20 October 2026 (Asia/Bangkok). This suite translates the [research blueprint](../vision/subcortical_memory_blueprint.md) into an implementation and experimental program. Runtime components are **planned**, not implemented. Current mandate includes the owner setup/instructions amendment and scoped publication; Phase 1 remains **WAIT_FOR_GO**.

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

Owner setup: existing uv `.venv/`, ignored root `.env` and `.gitignore`. Future authorized generative inference uses Groq with explicit Qwen 3.8 27B, GPT OSS 120B or GPT OSS 20B selection (ADR-0010); key/API availability are not tested now. Package layout/dependencies and other runtime decisions remain separate.

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
