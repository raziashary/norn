# Norn project working memory

Updated 20 October 2026 (Asia/Bangkok). One navigation memory; source/vision/MDP/ADRs remain authoritative.

## Current mandate and state

Complete P01 under explicit owner GO and question-tool approvals (ADR-0012). P00 is complete. P01 source/schema/tests/CLI and all12 cards are DONE, final proof E-P01-003; 18/139 tasks complete overall. Later research phases remain planned. No authority for another main push; earlier scoped docs publication is fulfilled. Baseline for this phase: clean main at 5c06dd9, one checkout.

## Actual foundation

- src/norn/contracts: frozen namespace/IDs, tagged values, all seven external epistemic values, independent origin/status, aware clock/precision/interval/unknown contracts.
- canonical: immutable digest-addressed UTF-8 source/spans, original occurrence/entity identity, schema1 evidence/control/journal tables, additive schema2 derivation lineage, atomic write/correction/outbox and versioned backup/upgrade safeguards.
- governance: trusted-host namespace-wide current READ/WRITE/ADMIN grants and epoch, explicit request-time interpretation, current tombstones with bounded downstream purge selectors. Physical purge remains pending.
- extraction: explicit deterministic source-anchored fixture annotations and uncertainty; no arbitrary NLP or approval inference.
- integration/CLI: local operator facade, source-backed read, knowledge/valid/snapshot replay, retraction/correction, journal replay, deny, backup. Held evidence serialization rechecks current access. No model/provider/index/worker loaded; INDEX_PENDING is not searchable.
- pyproject.toml/uv.lock: owner environment reused, Python3.14, Hatchling1.32.4, pytest/Ruff/mypy/build, tzdata for Windows IANA zones. .env remains ignored/unread. Approved future generative policy remains Groq with explicit allowed model choice; IDs/availability not verified and no call occurred.

## Architecture and boundaries

Canonical events, atoms, typed relationships, sources and rebuildable derived data remain separate. Similarity/name/activation/model agreement never grant identity, truth or access. Current security overrides historical content. Canonical SUPPORT is anchored fixture evidence, not normative approval or measured semantic accuracy. Future P03 retrieval/approval/source gates and P11 worker/backup reconciliation keep their own obligations. External host authentication is the embedding host's responsibility; local CLI principal options are trusted operator configuration.

Read PROGRESS, GOAL, MDP exact card/dependencies, ADR owner answers, TESTING_GATES and EVIDENCE_LOG before continuing. Start adversary and end reviewer only, GPT6 Luna Medium; main performs all exploration/code/tests. Reviewers receive no credentials, runtime execution or git mutation.

## Evidence and remaining work

E-P01-001/002 retain approvals, environment failure, earlier artifacts and meaningful failures/fixes; E-P01-003 owns final closure. Final main suite63 passed/no skips, format/lint/type/build/docs controls pass. Final wheel installed scenario and24-file byte parity pass; sole independent full-blueprint end review and resolutions pass. All tests use disposable synthetic temporary stores, no existing meaningful state or listeners. No task processes remain; policy blocked deletion of the static wheel-test environment in Windows Temp (E-P01-003). Schema upgrade makes a verified backup first. Source bytes may remain unreferenced after rollback; automatic garbage collection/physical purge is outside this foundation.

Palladion/Arcana were read-only design/format references. Owner approved original Norn code without copying either checkout. No foreign runtime dependency. Pending decisions concern later embedding/training/compute/backends, production retention and experimental thresholds, not the accepted P01 pilot.
