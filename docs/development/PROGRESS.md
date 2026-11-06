# Current progress

Updated 22 October 2026 (Asia/Bangkok). P04 is complete9/9 under ADR-0020/E-P04-005, following verified P00–P03. The synthetic frozen-E5 binding study is INCONCLUSIVE; completion is technical/research execution, not proven efficacy. P02 is published at1b86549; the owner authorizes current P03/P04 publication after final verification (ADR-0023). P05+ have no mandate.

## Derived phase register

MDP atomic checkboxes and states own task status. Counts below must equal that register; they are work accounting, not readiness percentages. Deferred tasks stay unchecked with reason/owner/destination. Final phase receipts: E-DOC-004/005, E-P01-003, E-P02-003, E-P03-003 and E-P04-005; full scoped end reviews resolved. Earlier receipts retain historical evidence.

| Phase | Tasks | Done | Deferred | State | Evidence |
|---|---|---|---|---|---|
| P00 | 6 | 6 | 0 | DONE | E-DOC-001 through E-DOC-004 |
| P01 | 12 | 12 | 0 | DONE | E-P01-001 through E-P01-003 |
| P02 | 11 | 11 | 0 | DONE | E-P02-003; final main/installed proof and review resolved |
| P03 | 12 | 12 | 0 | DONE | E-P03-003; final measurement/installed/end review verified |
| P04 | 9 | 9 | 0 | DONE | E-P04-005; final study/installed/native/guard proof and sole review resolved |
| P05 | 9 | 0 | 0 | IN_PROGRESS | E-P05-001 (T01–T03 train half), E-P05-002 (T04–T06); cards close at the P05 end review |
| P06 | 12 | 0 | 0 | PLANNED | NOT_RUN |
| P07 | 8 | 0 | 0 | PLANNED | NOT_RUN |
| P08 | 8 | 0 | 0 | PLANNED | NOT_RUN |
| P09 | 13 | 0 | 0 | PLANNED | NOT_RUN |
| P10 | 7 | 0 | 0 | PLANNED | NOT_RUN |
| P11 | 14 | 0 | 0 | PLANNED | NOT_RUN |
| P12 | 9 | 0 | 0 | PLANNED | NOT_RUN |
| P13 | 9 | 0 | 0 | PLANNED | NOT_RUN |

Total atomic tasks: 139. Total completed: 50. Runtime tasks completed: 44. R0–R3 and P04 synthetic development outcomes INCONCLUSIVE; no confirmatory efficacy claim.

## Current work

Pre-P05 cleanup 6–7 November 2026 (ADR-0024/0025/0026, E-FIX-001/002; no card state changes): the recording clock, owner answers 1–8 and 10 are executed — satisfiable-slot metrics, engine-observed injected-outage E12, ADMIN-or-producer retraction, event-first binding candidates, staged blob publish, schema 5 with 13 indexes, tokenizer v2, external run attestation, B4 type embedding fixed and B3/B4/S3/S4 retrained, dead enums and `request_id` removed, test gaps closed. 207 tests pass; Ruff and strict mypy clean. Bounded local re-runs: R0–R3 `p05-pre-r-002` (R0 complete-set 0.857, R1/R2 0.837, R3 0.898, every contrast interval includes zero) and binding `p05-pre-b-001` (INCONCLUSIVE, headline identical to P04-003). P05 mandate: ADR-0026 (all nine cards after cleanup). Nothing is pushed.

P04 DONE9/9 and parent exit proven (E-P04-005).158 tests/no skips, Ruff/type/build, final4,140conditions (4,050OK/90UNSUPPORTED), twelve200-update frozen-E5 jobs, installed105-file parity/all7 binding consumers, R0–R3 regression, native cancellation/deadline and eight corruption controls pass. Sole GPT6 Luna Medium reviewer resolved source and final artifact proof. B3/B4 match capacity-controlled singles; no decomposition/attention benefit established. B5 explicitly unsupported. Static cache-label defect is disclosed with own-ledger timing correction; no performance promotion. Preserve the earlier missing-pytest setup failure and its successful isolated offline recovery, version002 and other prior attempts.

P03 DONE12/12 and parent exit proven (E-P03-003). Real R0–R3, source-qualified field support, isolated native inference, exact local projections/readback and additive schema3 are verified.131 tests/no skips, Ruff/type/build,540 paired observations (528OK/12UNSUPPORTED),444 same-vector ANN measurements and80-file fresh installed parity pass. Actual installed all-arm source/correction/revoke/deny and native cancel/deadline controls pass. Sole GPT6 Luna Medium reviewer confirmed the public-interpreter prerequisite defect fixed and final artifacts consistent. No superiority: CompleteSet41/49 R0–R2 vs44/49 R3, with an exploratory interval including zero gain. Remaining semantic errors, negative results and previous attempts stay visible.

P02 DONE11/11 and parent exit proven. Final suite97PASS/no skips, Ruff/type/build/docs checks,1,620 paired control observations,405 fresh installed-wheel observations and123 run-bound calibration forecasts are verified. Owner reviewed42 exact sample cases; other cases remain unaudited. Sole GPT6 Luna Medium end reviewer confirmed calibration, qualified-partial, CLI integration and import-alias findings resolved. Final source/artifact receipts and limits: E-P02-003; earlier failures/checkpoints retained in001/002. No efficacy outcome evaluated.

## Next authorized work

P05 implementation is authorized by ADR-0026 (all nine cards, local CPU, frozen pinned E5-small plus small heads, GPT OSS 120B only if a card needs generation); T01–T06 are IN_PROGRESS (E-P05-001: pairs, objectives, 21 trained and reloaded checkpoints on the train role; E-P05-002: gradient-conflict/collapse diagnostics and both toy reproductions); held-out scoring waits for ADR-0027 Q-D (margin proposal in `docs/development/evidence/p05_r09_margin_proposal.md`), T07 for Q-A, and P06+ have no mandate. ADR-0022 remains a sequencing/evidence handoff. Current main publication is explicitly approved in ADR-0023; future publication needs its own authority. Source implementation59f8021 is locally committed; final documentation/status closeout forms a separate verified local commit. Preserve ignored models, original final003 artifacts, versioned002 and earlier failures/wheels. All owned study/verification/model processes ended; no task listener, credential load, provider call or foreign change. Leave pre-existing unrelated resources alone.
