# Current progress

Updated 12 November 2026 (Asia/Bangkok). P05 is IN_PROGRESS (see Current work). P04 is complete9/9 under ADR-0020/E-P04-005, following verified P00–P03. The synthetic frozen-E5 binding study is INCONCLUSIVE; completion is technical/research execution, not proven efficacy. P02 is published at1b86549; the owner authorizes current P03/P04 publication after final verification (ADR-0023). P05 is mandated in full by ADR-0026 (P06+ have no mandate).

## Derived phase register

MDP atomic checkboxes and states own task status. Counts below must equal that register; they are work accounting, not readiness percentages. Deferred tasks stay unchecked with reason/owner/destination. Final phase receipts: E-DOC-004/005, E-P01-003, E-P02-003, E-P03-003 and E-P04-005; full scoped end reviews resolved. Earlier receipts retain historical evidence.

| Phase | Tasks | Done | Deferred | State | Evidence |
|---|---|---|---|---|---|
| P00 | 6 | 6 | 0 | DONE | E-DOC-001 through E-DOC-004 |
| P01 | 12 | 12 | 0 | DONE | E-P01-001 through E-P01-003 |
| P02 | 11 | 11 | 0 | DONE | E-P02-003; final main/installed proof and review resolved |
| P03 | 12 | 12 | 0 | DONE | E-P03-003; final measurement/installed/end review verified |
| P04 | 9 | 9 | 0 | DONE | E-P04-005; final study/installed/native/guard proof and sole review resolved |
| P05 | 9 | 0 | 0 | IN_PROGRESS | E-P05-001 (T01–T03 train half), E-P05-002 (T04–T06), E-P05-004 (T03 held-out); cards close at the P05 end review |
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

P05 held-out status, 12 November 2026 (E-P05-004, development-exploratory): the R09 margins were approved as written (ADR-0027 Q-D) and frozen, and the owner answered Q-A, Q-B, Q-C, Q-E, Q-F and Q-G (Q-E/Q-F/Q-G code changes still to do). Held-out retrieval of T0–T7 gave a null: the tune role selected T1 by tie-break (four arms tie at identity top-1 1.000) and the single evaluation read gave C1 +0.095 with interval [0.000, 0.262] on 14 clusters, verdict T0_RETAINED_NO_ARM_CLEARS_C1. T07–T09 are not started. Nothing is pushed (owner: keep commits local until the P05 end review is resolved).

Pre-P05 cleanup 6–7 November 2026 (ADR-0024/0025/0026, E-FIX-001/002; no card state changes): the recording clock, owner answers 1–8 and 10 are executed — satisfiable-slot metrics, engine-observed injected-outage E12, ADMIN-or-producer retraction, event-first binding candidates, staged blob publish, schema 5 with 13 indexes, tokenizer v2, external run attestation, B4 type embedding fixed and B3/B4/S3/S4 retrained, dead enums and `request_id` removed, test gaps closed. 207 tests pass; Ruff and strict mypy clean. Bounded local re-runs: R0–R3 `p05-pre-r-002` (R0 complete-set 0.857, R1/R2 0.837, R3 0.898, every contrast interval includes zero) and binding `p05-pre-b-001` (INCONCLUSIVE, headline identical to P04-003). P05 mandate: ADR-0026 (all nine cards after cleanup). Nothing is pushed.

P04 DONE9/9 and parent exit proven (E-P04-005).158 tests/no skips, Ruff/type/build, final4,140conditions (4,050OK/90UNSUPPORTED), twelve200-update frozen-E5 jobs, installed105-file parity/all7 binding consumers, R0–R3 regression, native cancellation/deadline and eight corruption controls pass. Sole GPT6 Luna Medium reviewer resolved source and final artifact proof. B3/B4 match capacity-controlled singles; no decomposition/attention benefit established. B5 explicitly unsupported. Static cache-label defect is disclosed with own-ledger timing correction; no performance promotion. Preserve the earlier missing-pytest setup failure and its successful isolated offline recovery, version002 and other prior attempts.

P03 DONE12/12 and parent exit proven (E-P03-003). Real R0–R3, source-qualified field support, isolated native inference, exact local projections/readback and additive schema3 are verified.131 tests/no skips, Ruff/type/build,540 paired observations (528OK/12UNSUPPORTED),444 same-vector ANN measurements and80-file fresh installed parity pass. Actual installed all-arm source/correction/revoke/deny and native cancel/deadline controls pass. Sole GPT6 Luna Medium reviewer confirmed the public-interpreter prerequisite defect fixed and final artifacts consistent. No superiority: CompleteSet41/49 R0–R2 vs44/49 R3, with an exploratory interval including zero gain. Remaining semantic errors, negative results and previous attempts stay visible.

P02 DONE11/11 and parent exit proven. Final suite97PASS/no skips, Ruff/type/build/docs checks,1,620 paired control observations,405 fresh installed-wheel observations and123 run-bound calibration forecasts are verified. Owner reviewed42 exact sample cases; other cases remain unaudited. Sole GPT6 Luna Medium end reviewer confirmed calibration, qualified-partial, CLI integration and import-alias findings resolved. Final source/artifact receipts and limits: E-P02-003; earlier failures/checkpoints retained in001/002. No efficacy outcome evaluated.

## Next authorized work

P05 implementation is authorized by ADR-0026 (all nine cards, local CPU, frozen pinned E5-small plus small heads, GPT OSS 120B only if a card needs generation). Next in order: the ADR-0027 Q-E, Q-F and Q-G code changes with tests; P05-T07 at 384 dimensions only (Q-A); P05-T08 claiming paraphrase and unseen-identity transfer only (Q-B) with endpoints that do not saturate (R35); P05-T09 and the sole Haiku 5.5 high-effort end review; P06+ have no mandate. ADR-0022 remains a sequencing/evidence handoff. Main publication of P03/P04 was approved in ADR-0023; the owner now holds all further pushes until the P05 end review is resolved. Preserve ignored models, run directories (including the interrupted `p05-t03-heldout-001`), versioned runs and earlier failures. All owned study/verification processes ended; no task listener, credential load or provider call remains. Leave pre-existing unrelated resources alone.
