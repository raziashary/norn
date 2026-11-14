# P06-T20: conventional arms R0 to R3 on `public-v2` (pilot role)

Status: development measurement on the pilot role, attested. It is not a confirmatory result and
carries no hypothesis claim. No public-v1, P03 or P05 number is reused here.

## What was run

- Command: `norn-benchmark run-multihop-baselines` (see EVIDENCE_LOG E-P06-007 for the exact
  arguments), role `pilot`, seed 47, strata `TEMPLATE`, `NOISY_V1:en`, `NOISY_V1:id`,
  `NOISY_V1:mixed`, 48 pilot cases per stratum, 192 queries, arms R0 to R3 (R0 exact union and BM25, R1
  exhaustive pinned dense, R2 exact/BM25/dense RRF, R3 the R2 pool plus the pinned reranker), serial, CPU only, 768 arm-query pairs, all `OK`.
- Wall-time cap: 18,800 s = 1.5 x (65.26 s per query measured on 18 pilot probe queries x 192).
  Elapsed 10,673.6 s. The cap did not trigger.
- Input boundary: arms read the published `public-v2` input only. `search_budget` (60) sets the
  candidate pool and `max_candidates` (10) the output limit; the old `public-v1` limits are
  unchanged.
- Attestation: `docs/development/evidence/run_attestation_p06-t20-run-001.json` (layout
  conventional). `multihop-report` reloads the ledger, verifies the seal and the code digest and
  labels the report `ATTESTED`; without an attestation it refuses unless `--development-only`.

## Definitions

- Slot recall: among queries whose gold status is SUPPORTED, the share where every gold slot has
  an acceptable source in the returned evidence (complete set). A failed or missing observation
  counts zero (intent to treat); insufficient queries never enter the denominator.
- Sufficiency status: `status_correct`, false answers and false abstentions, reported separately
  and never combined with recall.
- Saturation per family, stratum and arm: CEILING at recall >= 0.95, FLOOR at <= 0.05, else OPEN.
  A cell is non-discriminating when the spread across arms is under 0.05.

## Slot recall by family (all four strata pooled, complete set / supported queries)

| Family | R0 | R1 | R2 | R3 | Saturation |
|---|---|---|---|---|---|
| M1 two-hop chain | 0/20 | 0/20 | 0/20 | 0/20 | FLOOR, non-discriminating |
| M2 3-4 hop chain with alias | 0/20 | 0/20 | 0/20 | 0/20 | FLOOR, non-discriminating |
| M3 hub with decoys | 0/20 | 0/20 | 0/20 | 0/20 | FLOOR, non-discriminating |
| M4 public detour, private shortcut | 0/20 | 1/20 | 0/20 | 0/20 | FLOOR (one OPEN cell: `NOISY_V1:mixed`, R1, 1/5) |
| M5 same-name entities | 0/8 | 0/8 | 0/8 | 0/8 | FLOOR, non-discriminating |
| M6 near-duplicate episodes | 8/8 | 8/8 | 8/8 | 8/8 | CEILING, non-discriminating |

Primary endpoint pool (M1 to M4, 80 supported queries per arm): R0 0/80, R1 1/80, R2 0/80,
R3 0/80, all FLOOR. R1 minus R0 is +0.0125 (95% cluster bootstrap [0, 0.0375], two-sided p
0.727, Holm family of 3 adjusted p 1.0, power not established, exploratory). R2 and R3 minus R0
are 0.0.

Per-query partial coverage (mean share of gold slots covered, supported queries, not a reported
endpoint) is above zero for the chain families (for example M1 R0 0.15 and R3 0.47), so the arms
do find some links; they do not assemble complete chains.

## Sufficiency status (reported separately)

- Status correct, the same on every arm: M1 to M4 20 of 40 each (80 of 160 pooled), M5 8 of 16,
  M6 13 of 16. Every supported M1 to M5 query is a false abstention (20 of 20 per family for M1
  to M4, 8 of 8 for M5), the missing and ambiguous variants abstain correctly, and M6 has no false
  answer and no false abstention (the 3 other M6 status mismatches were not analysed). False
  answers: 0 in every family.
- Observed mechanism (R0 diagnostic on a positive M1 query): the packet status is
  `NOT_ESTABLISHED` with reason `MISSING_CASE_INPUT` and two evidence items. The question-schema
  interpreter clears subject and fields for chain questions, so field-only sufficiency cannot
  adjudicate a typed path. The floor is therefore partly a property of this interpreter and the
  two-item packet, not only of the retrievers. That is the headroom a graph arm can use; it is
  not evidence that a graph arm works.
- Privacy incidents: 0. The private M4 sources are never published, so this is true by
  construction and is not a tested denial. The privacy control belongs to T04 to T06.

## Costs (serial, CPU, p50 over 192 queries)

| Arm | cold p50 | elapsed p50 | elapsed p95 |
|---|---|---|---|
| R0 | 2.6 s | 4.2 s | 6.5 s |
| R1 | 6.0 s | 8.2 s | 9.9 s |
| R2 | 6.1 s | 8.3 s | 10.1 s |
| R3 | 13.3 s | 25.7 s | 31.0 s |

Offline build total 1,951 s. No provider prices apply (no provider call).

## Limits

- Pilot role only (24 clusters, 192 queries); the tune and evaluation roles were not read.
- Single run, single seed (47), single attempt; no variance across seeds or models.
- Development label; thresholds and margins are not frozen (T21).
- The capture still carries the clean fact in every NOISY_V1 source; the arms read the message,
  but this measures robustness to this noise family only.
- No graph arm exists yet; T10 and T21 compare graph arms against these numbers.
- Zero observed false answers and zero privacy incidents are not zero risk.
