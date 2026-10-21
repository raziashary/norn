# P03 conventional baseline study

P03 engineering phase complete; final source/artifact review resolved. Scientific outcome INCONCLUSIVE. Authority: MDP P03-T01–T12, ADR-0017/0018/0019 and E-P03-003. Engineering completion and scientific efficacy are separate.

The full development run contains135 paired fictional cases in all14 task categories, three cue variants and EN/ID/mixed text. All four arms receive identical published sources, clocks, principal, candidate cap and2000-token serialized evidence-packet budget. Hidden gold is used only by the evaluator. There is no generator, Groq call, training, locked test or external transfer. The135 constructed cases are unaudited; the owner's earlier42-case P02 review binds a different pack.

R0 uses exact/BM25; R1 uses real pinned E5 embeddings with exhaustive search; R2 fuses exact/BM25/dense via fixed RRF; R3 reranks that same pool with the fixed approved cross-encoder. ANN is measured separately and is not enabled in serving recall. Every arm uses the pinned E5 evidence tokenizer in this comparison. Standalone asset-free R0 uses a different declared Unicode-word budget profile.

## Outcomes and limits

All540 planned observations are retained:528 OK and12 UNSUPPORTED (three per arm). There are no ERROR/TIMEOUT/INVALID/NOT_RUN omissions. Per arm132 responses support status scoring, while129 actual runtime packets support first/repeated timing; three unsupported and three early verification-unavailable responses have no runtime timing. Only final exposed evidence is scored; earlier pipeline stages expose counts, not unobserved retrieval@20.

| Arm | CompleteSet ITT | False-answer status | False abstention | Five-status correct | Qualified partial | Cold p50/p95/p99 (s) | Repeated p50/p95/p99 (s) |
|---|---|---|---|---|---|---|
| R0 | 41/49 | 6/83 | 9/50 | 109/132 | 1/1 | 1.284/1.443/1.526 | 0.122/0.259/0.283 |
| R1 | 41/49 | 6/83 | 9/50 | 109/132 | 1/1 | 4.291/4.542/4.806 | 0.139/0.268/0.299 |
| R2 | 41/49 | 6/83 | 9/50 | 109/132 | 1/1 | 4.287/4.578/4.801 | 0.145/0.284/0.313 |
| R3 | 44/49 | 6/83 | 9/50 | 109/132 | 1/1 | 7.653/8.124/8.513 | 6.575/7.083/7.545 |

All arms have partial usefulness0.5 on its single applicable case, missing-reason accuracy6/82, ambiguity detection30/30, selective coverage47/132 and selective risk8/47. These denominators describe different endpoints. Evidence-status overclaims/refusals are not generated-answer QA accuracy. The frozen public-word interpreter and field-only gate remain limited for arbitrary entailment, authority, causality and typed paths. Similarity/source hashes do not grant truth or action permission.

R3 gains three complete evidence sets over R0 in this cohort. The case-weighted difference is3/49; the equal-cluster mean difference is0.07143, exploratory95% cluster-bootstrap interval[0,0.21429],14 clusters/1000 draws/seed47. R1 andR2 have zero observed CompleteSet difference from R0. No power or practical margin is established; this is inconclusive evidence for superiority. Keep cheap R0 as the reference and R3 as the practical challenger, without promoting a neural or production claim.

The final interpreter-v3 fix preserves absent explicit prerequisites. It corrects the public release/rollback partial case but does not improve every metric: compared with preserved v2, false-answer statuses change7/83 to6/83, five-status accuracy110/132 to109/132, qualified partial0/1 to1/1, selective risk7/47 to8/47. The changed declaration also exposes heuristic limitations. Do not hide these regressions or tune a locked threshold. Earlier incomplete001/002/003 and completed004 remain version-scoped (E-P03-001/002). This reuses development instances; it is not independent replication.

Zero canary/privacy incidents were observed in540 response envelopes, 516 envelopes contain first/repeated runtime pairs (1032 packets). These constructed dependent exposures do not justify a population privacy bound or a zero-risk claim. Exact citation/source checks passed; this establishes provenance, not semantic entailment. Physical purge remains pending.

## Strata

The following tables show final-evidence CompleteSet numerator/applicable denominator. FA/AB are R3 false-answer/false-abstention counts; all four arms have the same two counts within each stratum. A zero denominator is unavailable, not perfect coverage.

### Task category

| Stratum | Planned per arm | R0 | R1 | R2 | R3 | FA / AB |
|---|---|---|---|---|---|---|
| E1 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E2 | 13 | 7/7 | 7/7 | 7/7 | 7/7 | 0 / 0 |
| E3 | 13 | 1/6 | 1/6 | 1/6 | 1/6 | 0 / 6 |
| E4 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E5 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 3 / 0 |
| E6 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E7 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E8 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E9 | 10 | 3/3 | 3/3 | 3/3 | 3/3 | 3 / 0 |
| E10 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E11 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E12 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |
| E13 | 9 | 0/3 | 0/3 | 0/3 | 3/3 | 0 / 3 |
| E14 | 9 | 3/3 | 3/3 | 3/3 | 3/3 | 0 / 0 |

### Language

| Stratum | Planned per arm | R0 | R1 | R2 | R3 | FA / AB |
|---|---|---|---|---|---|---|
| en | 51 | 17/21 | 17/21 | 17/21 | 18/21 | 2 / 5 |
| id | 42 | 12/14 | 12/14 | 12/14 | 13/14 | 2 / 2 |
| mixed | 42 | 12/14 | 12/14 | 12/14 | 13/14 | 2 / 2 |

### Cue variant

| Stratum | Planned per arm | R0 | R1 | R2 | R3 | FA / AB |
|---|---|---|---|---|---|---|
| ambiguous | 42 | 0/0 | 0/0 | 0/0 | 0/0 | 0 / 0 |
| missing | 43 | 0/0 | 0/0 | 0/0 | 0/0 | 6 / 0 |
| positive | 50 | 41/49 | 41/49 | 41/49 | 44/49 | 0 / 9 |

## Resources and approximation

CPU: Ryzen3 4300U,4 logical CPUs,7.4GB RAM, integrated Radeon unused. Initial free RAM was about0.7GB. ONNX uses CPUExecutionProvider,2 intra-op/1 inter-op threads, sequential inference; only one resident model worker is kept. Model inputs are capped512 tokens, batches bounded, no provider retry/fallback. All516 first/repeated query pairs were stable; no input truncation or repeated-query unavailability was observed. Timing is descriptive for129 queries per arm, not a tail-latency guarantee or saturation/capacity study. Cold includes engine/model/tokenizer verification and setup; repeated R3 switches model processes. Desktop/cache effects remain uncontrolled.

| Arm | First model attempts/tokens | Repeated attempts/tokens |
|---|---|---|
| R0 | 0/0 | 0/0 |
| R1 | 129/3502 | 129/3502 |
| R2 | 129/3502 | 129/3502 |
| R3 | 246/50434 | 246/50434 |

Sum of independent per-case offline builds: 626.770s; 455 model attempts/63346 input tokens. This includes repeated per-store preparation, not amortized production indexing. Each arm retains three unsupported rows without runtime usage records. No API billing occurred; local CPU/memory costs are not free.

ANN: actual FAISS HNSW, M16/efConstruction40, CPU1, normalized FP32 geometry and native serialization/reopen. There are111 nonempty eligible corpora (N1–7),24 empty exclusions, k=min(5,N); only9 queries have k<N. All settings match the exhaustive neighbors. This tiny-corpus diagnostic cannot establish useful approximation, scale or semantic benefit. Raw native search and Python exhaustive timing have different boundaries; no speedup is inferred.

| efSearch | Queries | Mean/min recall | Native search p50 (us) | Build+serialize+reopen p50 (us) | Serialized index bytes | Max whole-process working set (bytes) |
|---|---|---|---|---|---|---|
| 16 | 111 | 1.000/1.000 | 39.8 | 162.8 | 1926–11982 | 60809216 |
| 32 | 111 | 1.000/1.000 | 34.3 | 113.8 | 1926–11982 | 60809216 |
| 64 | 111 | 1.000/1.000 | 34.1 | 113.9 | 1926–11982 | 60809216 |
| 128 | 111 | 1.000/1.000 | 33.1 | 108.3 | 1926–11982 | 60809216 |

ANN whole-process observations include original/reopened indices and serialized copies; vector matrix bytes are1,536–10,752. These are neither isolated FAISS allocations nor total machine RAM. Baseline parent and model-worker lifetime peaks are separate observations; native workers peak around1.19GB. Windows pagefile counters are not measured swapped-byte volume.

## Reproduction and integrity

Source digest: `dbf116ad26b6633a6ad61da922716743b2f0fa63aa1734f6aad2e5cb859835ba`. Encoder revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`; reranker `1427fd652930e4ba29e8149678df786c240d8825`. Asset/method fingerprints, four exact file hashes, libraries and hardware are in the manifest and asset owner. NumPy2.5.4/tokenizers0.23.3/ONNX Runtime1.31.0/FAISS1.15.1; no quantization or training.

| Artifact under .norn | SHA256 |
|---|---|
| p03-development-005/manifest.json | `51bb8446f566303f281023d1e82184fe6e3f0cb4e7645037b4f9084a2d44c5cd` |
| p03-development-005/ledger.jsonl | `45955c7e61eeed6052fd3c4381ae954687a040f7bc197fac8e2b155842fcdbb1` |
| p03-development-005/completion.json | `ba0fd6328fa1055072e527ace9b28a1c4feacc9b8ed7705153fafa8d8e5f84b3` |
| p03-baseline-report-005.json | `76230c105cdeee6c15ee4079dccbe8f6e8746c5de166c85a2d703cde3000f971` |
| p03-ann-005.json | `c3f43e907ac79ca189188fb5c9d382320b7e956ee54c07aba788ebb4f4c96266` |
| p03-dist-007/norn_memory-0.1.0-py3-none-any.whl | `20890926278863fc0a4f0ecd097a786464ab9f15b3a05a393ae606888d1c09f3` |

Actual commands, all exits,131-test source/SQL/backup/crash controls, six rehashed corruption controls,80-file installed parity and actual installed recall/correction/revoke/deny/native cancellation proof are recorded in E-P03-003. Full outputs remain under .norn/p03-post-005.* and each stage output; bulk artifacts are not committed. No key was read, provider contacted, or task listener started.

Preserve the original stores: actual recorded clocks are evidence. Recreating them after the fixed synthetic knowledge cutoff changes the profile; do not backdate. Reopen the frozen wheel/code and artifacts with the documented benchmark CLI. Code/input/model/ledger mismatches reject; this development study is not a sealed protocol or external transfer.
