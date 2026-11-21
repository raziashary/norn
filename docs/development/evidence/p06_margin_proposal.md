# P06 endpoint, margin and cluster-count proposal (APPROVED as written by the owner on 20 November 2026; frozen)

Status: **APPROVED AS WRITTEN** by the owner (question-tool answers of 20 November 2026, ADR-0029 P06-Q5, recorded in `ADR_LOG.md`): margins as in section 6, cluster option (a) of section 7, G1 to G4 frozen as run (section 8 decision 3) and the false-association bound kept (decision 4). Frozen in `benchmark/runs/graph_pilot.py` (`MARGINS`, `CLUSTERS`, `verdict`) and R09; a margin changed after a result invalidates promotion. Sections 1 and 2 were written **before** the pilot run and are hashed into the run's manifest; sections 3 onward were written after the pilot results and never changed section 2. The pilot is a measurement, never a benefit claim; no tune or evaluation role has been read.

## 1. What this unlocks

Until the owner answered, P06 reported only the pilot measurement and mechanical controls. With the answer the margins below are frozen in `docs/development/RISKS_AND_OPEN_QUESTIONS.md` R09 and ADR-0029, and a margin changed after a result invalidates promotion. The pilot is a measurement, never a benefit claim (ADR-0029 P06-Q5).

## 2. Preregistered analysis (written before the pilot run)

**Data.** The `public-v2` pilot role only: 24 clusters (20 primary clusters M1 to M4, 4 clusters M5 and M6), two variants per cluster, four renderings (TEMPLATE, NOISY_V1 en, id and mixed), 192 queries. The tune and evaluation roles are not read. The stores are copies of the attested T20 pilot stores (`run_attestation_p06-t20-run-001.json`), so G0 is the attested R2 and a control checks it query by query.

**Arms** (internal and non-public; no published arm vocabulary, capability or CLI contract changes, which wait for the M2 decision). G0 is the conventional control: exact union, BM25 and pinned dense fused by RRF over a candidate pool of 60, packaged to 10 sources and 2,000 evidence tokens by the recall owner. G1 to G4 add a graph channel walked from one fixed seed (the exact, BM25 and dense channel votes of T03, computed once per query) and fused with G0's ranked pool by the same RRF rule (owner answer, 20 November 2026), then packaged by the same owner, so output size, token budget and sufficiency logic equal G0's. G1 is the bounded BFS, G2 the damped best paths, G3 seeded PPR, G4 the heat kernel, each at its owner-set defaults (T04 to T06) with no pilot tuning and no sensitivity sweep. G5, G6 and G7 belong to M2; R10 is dropped (ADR-0029 P06-Q6).

**Topologies.** Primary: the text reader's REQUIRES edges (producer revision `NOISY_TEXT`) on every rendering. Descriptive controls on TEMPLATE only: the read-back edges (zero extraction error by construction) and the oracle edges written from the hidden gold graph, labelled unequal and never an arm of a contrast family. Each topology lives in its own throw-away store, and the same seed is used for all of them.

**Endpoints and denominators.**

| Endpoint | Denominator | Counts as |
|---|---|---|
| Slot recall (complete evidence set) | gold SUPPORTED queries | a failed or missing observation counts 0 (intent to treat) |
| False answer | queries whose gold status is not SUPPORTED | an accepted answer that is wrong |
| False abstention | gold SUPPORTED queries | any non-accepted answer; an unobserved one counts 1 |
| False association | M3 and M5 queries | at least one decoy (M3) or same-name-twin (M5) source in the returned evidence |
| Privacy incidents | every observed query with a forbidden canary | any occurrence of a forbidden source or canary; zero tolerance, reported with its 95% upper bound |
| Cost | every walk | visited nodes and edges, transitions, wall time, proposed sources, budget flags, gold slots gained over and lost against G0, useful extra gold slots per 1,000 visited nodes |

Sufficiency status correctness is reported separately and never combined with recall. On the chain families the question interpreter clears the requested fields, so status is unchanged by the evidence by construction (E-P06-001); no status gain is credited to the graph.

**Contrasts.** Holm family of five on slot recall over the primary families M1 to M4 and all four renderings, text topology: G3 minus G0 (primary), G3 minus G1 (does diffusion beat bounded BFS), G2 minus G3, G4 minus G3, G1 minus G0. Descriptive and outside the family: G3 minus G0 on the read-back and oracle topologies (TEMPLATE only); and the harm contrasts G3 minus G0 on false answer, false abstention and false association.

**Estimator.** Equal cluster-mean paired difference (strata pooled inside a cluster, variants averaged), cluster bootstrap with seed 47, 1,000 samples and a 95% percentile interval, Holm-adjusted p reported beside each. Query-level rates carry a Wilson interval and are labelled as ignoring cluster correlation. The endpoint variance is the standard deviation of the cluster means of each paired difference, with its bootstrap 95th percentile as a conservative planning value. Power uses the normal approximation, two-sided alpha 0.05 and power 0.80; the number of clusters is `((1.960 + 0.842) * sigma / delta)^2` and the detectable margin for n clusters is `(1.960 + 0.842) * sigma / sqrt(n)`.

**Rules for the proposal, fixed now so no number is chosen after seeing a result.** (a) Benefit margin: the smallest delta in {0.05, 0.10, 0.15} that the evaluation role (200 primary clusters) detects at 80% power at the pilot's upper-95 cluster SD of G3 minus G0; if none, 0.15 is proposed and flagged as underpowered. (b) The benefit condition is the one of the approved R09: the lower 95% bound above 0 and the point estimate at least delta. (c) Regression margins carry over unchanged from R09: false answer, false abstention and false association upper bound not above +0.02, privacy zero observed with its upper bound reported. (d) An endpoint whose pilot arms are identical or whose denominator cannot move is labelled non-discriminating (ADR-0028 Q-I) and is not cited as a regression bound. (e) If the pilot shows no gain of G3 over G0 or G1, the proposal still states the margins, and a simpler winner (G0, then G1) is the recorded outcome for a null result. (f) Cluster counts: the tune role keeps 40 primary clusters and the evaluation role 200 (owner split of 13 November 2026), their detectable margins are reported at the pilot SD values, and options (a) exploratory only, (b) more clusters, (c) a larger delta are put to the owner as in R09.

**Not done by the pilot.** No walk setting, scale, damping or merge rule is tuned or selected on pilot results. G5, G6, G7 and the paired seed-channel contrasts are M2. The pilot sources are synthetic fictional data; no model other than the pinned local encoder and tokenizer runs, and no network or provider call is made.

## 3. The pilot run (facts)

- Run `p06-t21-run-001` (local, ignored `.norn/`), attestation `run_attestation_p06-t21-run-001.json` (layout `conventional`, final chain `6ce2ac98...`), report `p06_graph_pilot_report.json` (sha256 `b1571752...`, status `ATTESTED`). Command: `norn-benchmark run-graph-pilot .norn/p06-t21-run-001 --source-run .norn/p06-t20-run-001 --source-attestation docs/development/evidence/run_attestation_p06-t20-run-001.json --model-root .norn/models --enable-models --wall-cap-seconds 4880 ...`, serial, CPU, no network, no provider call.
- Wall-time cap 4,880 s written in the manifest before the run (1.5 x 16.94 s per query measured on a 24-query smoke run x 192); elapsed 2,997 s, the cap did not trigger. 1,344 ledger rows (192 G0, 192 x 4 text-topology rows, 48 x 4 read-back, 48 x 4 oracle), all `OK`.
- Control: G0's evidence equals the attested T20 R2 evidence on 192 of 192 queries, source for source and in order. Pilot role only; the tune and evaluation roles were not read. The preregistered section 2 is unchanged (manifest digest `84ac9ecc...`, rechecked on reload).
- Walk cost is small: the walks take about 20 ms (p50, p95 about 40 ms); a graph arm's 1.0 s p50 is the evidence packaging that G0 also pays (G0 2.2 s p50 including the pool, plus 4.5 s p50 for the seed channels). Visited nodes p50 32, p95 56, max 60 (the namespaces hold 20 to 60 sources, so a walk reaches most of the corpus); transitions p50 16 (G1), 260 (G3), 208 (G4), max 1,408; no budget bound; the only flagged walks are the empty-seed M6 queries. A scale test at 5,000 events is not part of the pilot (corpora are tiny).

## 4. Preregistered results (pilot, exploratory, not a benefit claim)

Primary families M1 to M4, text topology, 20 clusters, 80 supported queries per arm (denominators in each cell):

| Arm | Slot recall | Wilson 95% (query level) | False abstention | False answer | Status correct |
|---|---:|---|---:|---:|---:|
| G0 | 0/80 = 0.000 | [0.000, 0.046] | 80/80 | 0/80 | 80/160 |
| G1 BFS | 0/80 = 0.000 | [0.000, 0.046] | 80/80 | 0/80 | 80/160 |
| G2 damped paths | 0/80 = 0.000 | [0.000, 0.046] | 80/80 | 0/80 | 80/160 |
| G3 PPR | 9/80 = 0.113 | [0.060, 0.200] | 80/80 | 0/80 | 80/160 |
| G4 heat | 9/80 = 0.113 | [0.060, 0.200] | 80/80 | 0/80 | 80/160 |

Slot recall by rendering for G3 (G0 is 0/20 in each): TEMPLATE 1/20, NOISY_V1 en 4/20, id 0/20, mixed 4/20. By family, G3 completes M1 7/20 and M3 1/20, M4 1/20, M2 0/20; M5 2/8 against G0's 0/8; M6 stays at ceiling (8/8) for every arm and is not in the primary pool. Sufficiency status is identical to G0 on every query: the question interpreter clears the requested fields on chain questions, so false abstention stays 80/80 whatever the evidence (E-P06-001 stands: no status gain is credited to the graph). Mean share of gold slots covered is lower for G3 (0.487) and G1/G2 (0.350) than for G0 (0.600): the graph arms re-rank a pool that already holds most of the corpus, so they complete a few chains while giving up partial coverage elsewhere (over all families, G3 gains 32 gold slots over G0 and loses 5; G1 and G2 gain 1 and lose none).

Preregistered contrasts (equal cluster mean, cluster bootstrap seed 47, 1,000 samples; Holm family of five):

| Contrast | Difference | 95% interval | p | Holm p | Cluster SD | SD upper 95% | Clusters with a difference |
|---|---:|---|---:|---:|---:|---:|---:|
| G3 - G0 (primary) | +0.113 | [0.037, 0.212] | 0.002 | 0.010 | 0.206 | 0.276 | 6 of 20 |
| G3 - G1 | +0.113 | [0.037, 0.212] | 0.002 | 0.010 | 0.206 | 0.276 | 6 of 20 |
| G2 - G3 | -0.113 | [-0.212, -0.037] | 0.002 | 0.010 | 0.206 | 0.276 | 6 of 20 |
| G4 - G3 | 0.000 | [0.000, 0.000] | 1.000 | 1.000 | 0.000 | 0.000 | 0 of 20 |
| G1 - G0 | 0.000 | [0.000, 0.000] | 1.000 | 1.000 | 0.000 | 0.000 | 0 of 20 |

Controls (descriptive, template rendering only, 20 clusters): G3 minus G0 is +0.050 [0.000, 0.150] on the read-back topology and on the oracle topology, the same as the text-derived topology on this rendering; the oracle is an unequal upper bound, not an arm. Harm contrasts, G3 minus G0: false answer 0.000 and false abstention 0.000 (96 pairs, 24 clusters, the arms are identical by the interpreter: non-discriminating); **false association +0.107 [0.018, 0.214]** (56 pairs, 7 clusters: M3 and M5; G3 returns a decoy or same-name-twin source in 1 of 40 M3 queries and 3 to 4 of 4 M5 queries per rendering, G0 in 0 of 40 and 2 of 4); privacy 0 incidents in 280 ledger rows (not independent trials: 40 distinct queries; see section 10 for the bound and what it does not show), by construction for the runtime store plus the denied-bridge walk control of T06.

Seeds: the exact channel is empty (degraded) on every query (chain questions name a display name, not a governed key), so the seed is the BM25 and dense votes, spread over 25 to 60 anchors with a median top weight of about 0.03 (no query seeds above 0.08) in M1 to M5, and empty for the M6 date question. This is why the walks reach most of the corpus.

## 5. Post-hoc diagnostics (labelled; they do not change section 2 or any contrast above)

Run after the results from the ledger's recorded proposals, primary families, text topology, supported queries: the graph channel alone, before the fusion with G0, completes the gold evidence in its first 3 / 10 / 20 proposals for G1 in 0 / 10 / 25 of 80, G2 in 0 / 22 / 35, G3 in 48 / 61 / 65 and G4 in 53 / 66 / 68. Fusing that list with a G0 pool that holds the chain nowhere near the top (G0 completes 0 of 80) by equal-weight RRF keeps about one in seven of those G3 completions (9 of 61). The preregistered merge therefore measures a floor for what the graph channel carries, and the walk ranking of a few sources into the top ranks is a property of these small synthetic namespaces (chains are the connected, linked parts of 20 to 60 sources), not an external-validity result. This is a mechanism observation for the owner's decision in section 8; no arm, margin or rule is changed by it.

## 6. Proposed margins (computed by the section 2 rules)

| Item | Proposal | Computed from |
|---|---|---|
| Benefit margin delta | **+0.10** absolute on slot recall, G3 minus G0 | rule (a): the evaluation role (200 clusters) detects 0.055 at the upper-95 cluster SD 0.276, so 0.05 is not detectable and 0.10 is; at the observed SD 0.206 it would detect 0.041 |
| Benefit condition | lower 95% bound above 0 and point estimate at least +0.10 | rule (b) as R09; the pilot point (+0.113, lower bound 0.037) would clear it, which is not evidence about any later role |
| Regression bounds | false answer, false abstention and false association: upper 95% bound not above +0.02; privacy: zero observed, 95% upper bound reported | rule (c), R09 unchanged |
| Non-discriminating endpoints | false answer and false abstention are not cited as regression bounds while the interpreter clears fields (the arms are identical, 96 of 96 pairs) | rule (d), ADR-0028 Q-I |
| Pilot false association | +0.107 [0.018, 0.214] exceeds the +0.02 bound; regression is **not excluded** | the verdict the margins would give on the pilot, for the owner's information |
| Simpler winner | G0, then G1; if G3 does not clear the benefit condition or breaches a bound, G0 is retained | rule (e) |

## 7. Cluster counts and power (primary clusters; pilot SD values)

| Role | Primary clusters | Detectable margin at observed SD 0.206 | at upper-95 SD 0.276 | at assumed SD 0.25 |
|---|---:|---:|---:|---:|
| pilot | 20 | 0.129 | 0.173 | 0.157 |
| tune | 40 | 0.091 | 0.122 | 0.111 |
| evaluation | 200 | 0.041 | 0.055 | 0.050 |

Clusters needed at 80% power: delta 0.05 needs 134 (observed SD), 240 (upper-95) or 197 (assumed 0.25); delta 0.10 needs 34, 60 or 50; delta 0.15 needs 15, 27 or 22. The evaluation role (200) is powered for +0.10 at every SD value and for +0.05 at the observed and assumed SD but 40 short at the upper-95 SD; the tune role (40) cannot detect +0.10 at the upper-95 SD (needs 60) and is a selection role, not a confirmatory one. The options, as in R09, are (a) keep the 40 / 200 split and report the tune role as development-exploratory, (b) generate 20 more tune clusters (60) before the tune read, (c) keep +0.10 as the only claimed margin and treat +0.05 as unpowered. The pilot's SD rests on 20 clusters of which 6 show any difference (a zero-inflated outcome), so it is itself uncertain. **The 80% power above is the power of the lower-bound test only; the joint benefit rule is weaker (section 10).**

## 8. Decisions requested (all answered 20 November 2026 as recommended: 1 approve as written, 2 option (a), 3 freeze as run, 4 keep the bound)

1. **Margins:** approve, amend or reject section 6 (benefit +0.10 with a lower bound above 0; regression bounds 0.02; privacy zero; simpler-winner rule).
2. **Cluster counts:** choose option (a), (b) or (c) of section 7.
3. **Merge rule:** the preregistered RRF merge is what the margins would apply to. Section 5 shows the graph channel carries more than that merge delivers. The options are to freeze G1 to G4 as run (a null or small result is then a valid recorded outcome), or to add one further merge arm (for example reserving the first slots for the graph channel) as a separately named, separately preregistered treatment whose first measurement is the tune role under the same margins, or to run a second pilot of that arm first (about one hour) so its SD is known before freezing.
4. **Harm signal:** the pilot's false-association increase (+0.107) is a regression under the proposed bound; say whether the bound stands as written (so G3 would fail it unless a later arm removes the twin and decoy returns) or an arm guard is to be designed first.

## 9. What this proposal does not do

No margin is derived from a tune or evaluation result; none exists. No walk setting, scale or merge rule was tuned on the pilot. G5, G6 and G7 and the seed-channel contrasts wait for M2. The E3 mechanism stays as recorded in E-P06-001 and `p06_e3_mechanism.md`: recall can rise while status stays withheld by the interpreter, so slot recall and status remain separate endpoints.

## 10. Corrections after the M1 end review (21 November 2026; sections 1 to 2 and every pilot number above are unchanged)

The sole end reviewer (Claude Haiku 5.5, high effort) read the proposal against the code. Main verified the following in source and corrects the proposal here, not in the preregistered section 2.

1. **Power of the joint benefit rule.** The cluster counts of section 7 give 80% power for the lower 95% bound to clear 0. The frozen rule also needs the point estimate to be at least +0.10. At a true effect of exactly +0.10 the point estimate clears the margin about half the time whatever the cluster count, so the joint rule has about 50% power at +0.10. With 200 clusters it has 80% power at a true effect near +0.116 (upper-95 SD 0.276; about +0.112 at the observed SD 0.206). The owner kept the rule as frozen and corrected this claim (answer of 21 November 2026, ADR-0029). No tune-role read has happened.
2. **The pilot privacy endpoint is a construction check, not a measured exposure rate.** The private M4 sources are never published to the runtime store (`benchmark/fixtures/multihop.py`: they go to `private`, not `published`), so no arm can return one in this pilot. The 280 figure counts ledger rows (40 M4 queries x 5 arms, plus 10 template queries x 8 further arm and topology rows), which are 40 distinct queries (10 per rendering; the 10 template queries are among them and carry the extra control rows); treating the rows as independent made the earlier bound of 0.0106 too small. Over 40 distinct queries the exact one-sided 95% upper bound for 0 observed is about 0.072 (two-sided Wilson 0.088). The saved report JSON still carries the 0.0106 figure; this paragraph supersedes it. The pilot has no positive canary control; the leak evidence is the denied-bridge walk control of T06 (`tests/test_diffusion_privacy.py`), which publishes the private source and shows the walks do not use it. A promotion claim needs a store where a denied source exists and a control that can see it leak.
3. **Seed degradation label.** `EXACT_CHANNEL_DEGRADED` is set for any empty exact channel (no match, no exact cue or over limit), not only the over-limit case of the design. The reason is recorded beside it. "Degraded on every chain query" therefore means "the exact channel returned nothing", not a budget overrun.
4. **Reporting limits, disclosed.** Graph-arm elapsed time covers the merge and the walk only (the shared pool and seed are not charged, and topology construction time is not summed). The verdict label is recomputed from the saved contrasts by `verdict()` and is not stored in the report. G0 versus the attested R2 mismatches are counted (0 of 192) but a mismatch would not fail the run. The "SD upper-95" is the 95th percentile of the bootstrap SD, a planning value rather than a confidence bound on sigma. The regression intervals for false association rest on 7 clusters.
