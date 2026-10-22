# P04 functional views and binding evidence

Updated 22 October 2026 (Asia/Bangkok). **IN_PROGRESS.** E-P04-005 owns the current execution receipt. This document separates implemented controls from the full comparison, which is still running. No P04 card or research gate is closed by this draft.

## Scope and authority

The owner approved ADR-0020's bounded frozen-E5 study, matched adapter capacity and additive public integration. The blueprint's “Shared latent binding” and I1–I10 remain the outcome constraints. This is a synthetic, exploratory development study. It does not test a larger pretrained transformer, neural equivalence, locked superiority, general entailment, an external agent task or production capacity.

The final runtime/evaluator digest is `db64157733bfcfc73bf00f3dba1f5a1f78c2d3c000d62c8141f35329edadd17c`. The full command is `uv run --locked --no-env-file --extra retrieval norn-benchmark binding-run .norn/p04-development-003 --model-root .norn/models --enable-models`. Its ignored command receipt and whole stdout/stderr sit beside the run directory. Runtime/evaluator source stays frozen while it executes; any later source change needs its own version-scoped proof.

## Inputs, custody and treatments

- Development-only identities are assigned before wording: 276 training queries from 28 entity clusters, 138 tuning queries from 14 other clusters and 138 evaluation queries from 14 further clusters. All E1–E14 task categories occur in every role. This tests disjoint instances; category/template transfer is untested. Labels are constructed and unaudited. The owner's earlier 42-case P02 audit is a different pack.
- Public adapters receive published sources, principal, clocks and budgets. Source IDs are mapped only after actual canonical byte/hash readback. Hidden labels supply training targets only in the trainer's train role, and scoring targets only in the evaluator. Tuning/evaluation labels do not feed optimization; fixed configuration makes no model selection. No calibration or locked partition is opened.
- B0 embeds one canonical event representation. B1 retrieves independently normalized context/semantic/action facets with weighted RRF; B2 uses weighted normalized concatenation. Their shared fixed 384-to-128 orthogonal projection is not trained alignment. B3 trains typed heads, pooled memory projection and a cue head. B4 adds typed facet self-attention and uses actual retrieval gradients on both cue and memory paths.
- All use the same pinned frozen multilingual E5-small backbone and source/evidence limits. There is at most 512 backbone tokens per event or query, shared across present facets; the numeric stored code is 384 FP32 values, 1,536 bytes per event per generation. Actual model calls/tokens, JSON/source/checkpoint/cache/SQL bytes and work are separate costs. S0 is unobserved and absent from numeric geometry. Missing action remains NOT_APPLICABLE.
- S3/S4 are wider single-event trainable MLP controls on that same frozen backbone. Trainable parameters: B3 61,952 versus S3 61,904; B4 66,144 versus S4 66,518, each within 1%. These are adapter-capacity comparisons, not bigger-transformer comparisons.
- Seeds 11/29/47; at most 200 updates per seed/learned arm, 20 minutes per job, two hours aggregate training, 512 MiB conservative additional-array ceiling. CPU inference is serial with one resident native model worker; head BLAS thread settings are explicitly 1. B5 returns FEATURE_NOT_SUPPORTED because no separate generative hypothesis/compute is approved. Groq/provider calls remain zero.

## Observation and metric boundaries

The planned full ledger has 4,140 tune/evaluation conditions: B0/B1/B2 once and B3/B4/S3/S4 at each of three seeds. Each condition projects through the public engine, runs a first and repeated public recall, and retains failures. The reader reopens original canonical stores and immutable manifests/checkpoints, recomputes geometry and candidate ranks from persisted actual E5 features, and reassembles exact evidence packets. Correctness requires current access, source locators, clocks, snapshot, method and checkpoint agreement.

Candidate identity is measured at BINDING_CANDIDATES with the actual public limit of 10; evidence completeness is measured at FINAL_EVIDENCE under the E5-tokenized 2,000-token packet cap. Source top-1 and published-event top-1 are distinct. Published-event identity is applicable only to sufficiently specified SUPPORTED cases; observed wrong returned episodes exclude empty/failure responses. Planned applicability and observed denominators remain visible. False answers, false abstentions and five-status classification use the existing qualified P02 metrics; citation validity does not establish semantic entailment.

Per-facet diagnostics remove context, semantic or action input, and duplicate the semantic facet under fixed weights. They recompute rankings on frozen features and disclose target-versus-decoy margins. B1's margin is an RRF rank-score difference; other arms use cosine. These diagnostics do not measure a new serving answer, an information-theoretic conditional mutual information or a model-cost saving. Identical-facet controls must not create a novelty claim.

First/repeated timings follow projection with a resident encoder, and condition rotation balances the first model exposure. Projection and capture timings are separate. Parent lifetime working-set peaks and separate native-worker peaks are not simultaneous total RAM, isolated adapter allocations or measured swapping. Unknown failure costs are disclosed; available attempted work is retained. Baseline predictions reused in seed-aware clustered contrasts are not independent new exposures.

## Executed mechanical controls

- Smoke001 completed 450 conditions, all OK, at the older digest `618f53fbacc31263962de4cd17d823098c7202b007cc408ee7d7bf64a29fffb0`. Its immutable report digest is `700cbe2c9e48705c75b85bf7e5e53a4e63142606c405116a9204ff59497091ea`. Twelve jobs ran 16 updates each; summed recorded job time was 1.1874227999942377 seconds. This sampled integration proof predates the target/custody/reporting fixes and is not efficacy evidence for current source.
- Current full suite: **158 passed, no skips**, 127.23 seconds. Ruff, 149-file format check and strict mypy on 101 modules pass. Numerical finite differences exercise every parameter owner, and actual small-pair training/reloaded query-to-memory lookup exercises both learned paths.
- Actual E5 public projection/reopen/source, current serving denial, schema3-to4 verified backup/restore, interrupted publication before READY/replay, incompatible legacy-generation archival backup/restore and poisoned-CAS rejection pass. Native binding cancellation records a real attempted call, terminates the owned worker, returns no evidence, and permits normal recovery; deadline refusal also passes.
- Build003 succeeds. A fresh isolated offline installation has **105 byte-identical Python/SQL files**, imports from its site-packages and runs the installed capabilities entry point. Actual installed003 all-arm/source/correction/stale/revocation/denial CLI proof passes with compatible completed002 checkpoints; final003 checkpoints will be exercised by the bound post-driver.

## Full comparison and preliminary decision

**PENDING:** final source-matched003 completion, standalone/corruption controls and sole end-review artifact resolution. Completed002 is valid only for frozen37bcf405... source; a subsequent deletion-selector correction requires this new003 run. The same fixed development identities/configuration are reused; this is no independent replication. The reviewer confirmed the checkpoint-selector fix resolved the sole material source finding, with no remaining material source issue. Practical promotion margins/power remain unset; the eventual preliminary scientific disposition must retain that limitation, preserve failures and allow the simpler control to win. P05 remains outside the current mandate, and main publication needs explicit approval.

### Preserved full002 observations before the deletion-selector fix

All4,140 conditions completed:4,050OK/90UNSUPPORTED. No ERROR/TIMEOUT/missing condition. Evaluation-only results below; learned rows pool three seeds on the same138 queries, not independent query sets.

| Arm | CompleteSet | Published-episode top1 | Wrong returned episode |
|---|---|---|---|
| B0 |42/51|46/51|6/51|
| B1 |41/51|44/51|7/51|
| B2 |42/51|45/51|6/51|
| B3 |141/153|153/153|3/153|
| B4 |141/153|153/153|3/153|
| S3 |141/153|153/153|3/153|
| S4 |141/153|153/153|3/153|

Each arm still had6/84 false answers,11/52 false abstentions and110/135 correct five-status classifications per seed exposure. Better evidence completeness did not establish better answer-status accuracy. B3/B4 versus matched singles had zero CompleteSet difference; B3/B4 minusB1 equal-cluster difference.10317 had exploratory95% interval[0,.26190] over14 clusters. The outcome remains INCONCLUSIVE; decomposition and attention have no demonstrated advantage beyond matched adapter capacity here. No operational default is promoted.

The trainer used178 queries with eligible positive targets and explicitly recorded98 skipped no-positive cases. All12jobs ran200 updates with101–106 nonzero-gradient steps and nonzero parameter deltas; total recorded training time7.8350s. Conservative numerical-array bounds were108.08–108.79MiB, below512MiB. Source operators on1,204 captured events used2,432 selective invocations/91.0551ms versus3,612 full invocations/164.7184ms; these are operator-only observations, not model fanout speedups.

Measured physical bytes:4,168,960 global checkpoint;36,142,383 private capture;1,274,150,412 projection CAS (including copied checkpoints/text/JSON);526,232 source CAS;199,327,744 whole SQLite. Numeric codes alone understate storage. All model calls/tokens, first/repeated/projection times and per-family/language/cue/seed/conditional observations remain in the immutable002 report, hash `2d1ca0c22f7b41f14b4193a4672f30dc443cdcf40e2931519e794a4797f22068`. Final003 must be reported separately.
