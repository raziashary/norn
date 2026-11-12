# P05 loss, separation and retained-code decision (P05-T09)

Status: **DEVELOPMENT-EXPLORATORY, descriptive** (ADR-0027 Q-C, owner answer 12 November 2026). This is the P05 scorecard for the T0–T7 arms, the T07 separation sweep and the T08 ambiguity/transfer check. Nothing in it is a production, superiority or semantic-accuracy claim. Authority: ADR-0026 (mandate), ADR-0027 Q-A to Q-G (owner answers), ADR-0028 (this decision). The evidence entries are E-P05-001, E-P05-004, E-P05-006 and E-P05-007 in `EVIDENCE_LOG.md`.

## 1. Decision

- **Retained code for the P06 graph study: T0**, the frozen pinned E5-small single-feature dense 384-coordinate cosine (condition B0). Rule: the owner-approved R09 proposal §3, "if no arm clears C1 or C2, the simpler arm (T0 or T1) is the retained result". The held-out verdict is `T0_RETAINED_NO_ARM_CLEARS_C1`: the selected arm T1 gave C1 = +0.095 (95% cluster-bootstrap interval [0.000, 0.262], 14 clusters, p 0.1998); the point estimate is above the +0.05 minimum benefit, the lower bound is not above zero. Not shown to be better, not shown to be harmful.
- **T1–T7 are not retained** as an identity or retrieval index. Their 21 checkpoints stay as development artifacts. T4, T5 and T7 were not scored on the evaluation role (the selection rule chose T1 by tie-break), so separation benefit on held-out data remains untested by design.
- **No sparse or binary code is adopted.** In the T07 sweep (T0, pooled events) weighted top-k was at or below a dense random projection of equal stored bytes at 1, 5 and 10% and above it at 2% (0.196 versus 0.098, a noise-level difference at 51 queries), it never collided but lost most identity against full dense, and binary support overlap was below the matched dense code at every level and tied or collided (§4).
- **A simpler winner is a valid outcome.** The graph study (P06) starts from T0 as its semantic baseline; any learned head enters only as a separately enabled, separately measured treatment (§7).
- The owner may override this decision in ADR-0028 "My answer"; no later phase has a mandate yet.

## 2. T0–T7 scorecard (held-out development retrieval, run `p05-t03-heldout-002`)

Metrics are the frozen R09 definitions (`benchmark/runs/loss_heldout.py` `CONFIG`): identity = strict episode top-1 over identity-applicable queries (non-OK counts 0); complete-set over fully answerable queries with a complete positive cue; false-answer and false-abstention over their declared denominators (unobserved rows count as the declared failure semantics). Learned arms are B3 checkpoints at seeds 11/29/47, so their denominators are 3x those of T0 (rows are query x seed pairs); raw per-seed training facts are in §3.

**Tune role (14 clusters; selected arm T1 by the declared rule, tie-break to the earlier arm):**

| arm | identity top-1 | C1 = arm minus T0 [95% interval] | complete-set (n) | false-answer (n) | false-abstention (n) | UNSUPPORTED / rows |
|---|---|---|---|---|---|---|
| T0 | 47/51 = 0.922 | — | 0.800 (45) | 0.069 (87) | 0.212 (52) | 3/138 |
| T1 | 153/153 = 1.000 | +0.0833 [0.000, 0.238] | 0.859 (135) | 0.069 (261) | 0.212 (156) | 9/414 |
| T2 | 141/153 = 0.922 | +0.0251 [-0.044, 0.155] | 0.837 (135) | 0.069 (261) | 0.212 (156) | 9/414 |
| T3 | 144/153 = 0.941 | +0.0516 [-0.048, 0.214] | 0.859 (135) | 0.069 (261) | 0.212 (156) | 9/414 |
| T4 | 153/153 = 1.000 | +0.0833 [0.000, 0.238] | 0.859 (135) | 0.069 (261) | 0.212 (156) | 9/414 |
| T5 | 153/153 = 1.000 | +0.0833 [0.000, 0.238] | 0.867 (135) | 0.069 (261) | 0.212 (156) | 9/414 |
| T6 | 139/153 = 0.908 | +0.0172 [-0.057, 0.143] | 0.837 (135) | 0.069 (261) | 0.212 (156) | 9/414 |
| T7 | 153/153 = 1.000 | +0.0833 [0.000, 0.238] | 0.889 (135) | 0.069 (261) | 0.212 (156) | 9/414 |

**Evaluation role (read once; T0, the selected arm and the T1 comparator; T1 is both):**

| arm | identity top-1 | complete-set (n) | false-answer (n) | false-abstention (n) | UNSUPPORTED / rows |
|---|---|---|---|---|---|
| T0 | 46/51 = 0.902 | 0.800 (45) | 0.069 (87) | 0.212 (52) | 3/138 |
| T1 | 153/153 = 1.000 | 0.867 (135) | 0.069 (261) | 0.212 (156) | 9/414 |

- C1 (T1 minus T0, identity) = **+0.0952**, interval [0.000, 0.2619], bootstrap seed 47, 1,000 samples, 14 clusters, 153 pairs; Holm family of one (C2–C5 are undefined when T1 is selected), adjusted p 0.1998. Verdict: `T0_RETAINED_NO_ARM_CLEARS_C1`.
- **The identity endpoint is saturated on tune**: four arms tie at 1.000, so the selection among them was a tie-break, not evidence (R35). False-answer (0.069) and false-abstention (0.212) are identical for every arm on both roles; the mechanism was not investigated, so these harm contrasts could not discriminate between arms. Zero privacy incidents.
- **Cost, confusion, abstention and completeness frontier:** on false-answer and false-abstention the frontier is flat (identical across arms). On complete-set the tune ordering is T7 0.889, T5 0.867, T1/T3/T4 0.859, T2/T6 0.837, T0 0.800, descriptive and not the selection key. Cost: every arm has 61,952 parameters and a 0.34–0.36 MB checkpoint, trains in 4.6–9.7 s per job on CPU (165.0 s for all 21), and stores a 384-coordinate float32 code (1,536 B) per event exactly like T0; the learned arms add a write-time facet projection and a read-time query head. No isolated online-latency comparison between T0 and a learned arm was measured (ledger timings include validation and repeated diagnostics).

## 3. Raw failures, seeds and superseded records preserved

- Per-seed training record of the 21 jobs (T1–T7 x seeds 11/29/47), 0 failures, 200 updates each; T3 (separation only) has fewer nonzero-gradient steps because its hinge is inactive on already-separated batches:

| arm | seed | parameters | updates | nonzero-gradient steps | seconds | checkpoint bytes | sha256 (first 12) |
|---|---|---|---|---|---|---|---|
| T1 | 11 | 61,952 | 200 | 200 | 4.7 | 342,859 | `c40ab477723d` |
| T1 | 29 | 61,952 | 200 | 200 | 4.7 | 342,814 | `8d4242115eae` |
| T1 | 47 | 61,952 | 200 | 200 | 4.7 | 342,840 | `2f3f91849df1` |
| T2 | 11 | 61,952 | 200 | 200 | 9.6 | 344,054 | `0b56af4351db` |
| T2 | 29 | 61,952 | 200 | 200 | 9.6 | 344,070 | `de302a3892a4` |
| T2 | 47 | 61,952 | 200 | 200 | 9.4 | 344,066 | `d99ac171b419` |
| T3 | 11 | 61,952 | 200 | 170 | 4.6 | 342,050 | `1574f4187e31` |
| T3 | 29 | 61,952 | 200 | 174 | 4.6 | 342,156 | `1a9f1a3afe7d` |
| T3 | 47 | 61,952 | 200 | 168 | 4.6 | 341,960 | `0d0312bf1442` |
| T4 | 11 | 61,952 | 200 | 200 | 9.4 | 350,238 | `4c5b61f351a4` |
| T4 | 29 | 61,952 | 200 | 200 | 9.7 | 350,247 | `1a5946be65e8` |
| T4 | 47 | 61,952 | 200 | 200 | 9.4 | 350,247 | `9fffba11d4ad` |
| T5 | 11 | 61,952 | 200 | 200 | 4.7 | 349,159 | `856054e31ef5` |
| T5 | 29 | 61,952 | 200 | 200 | 4.7 | 348,982 | `0041b6a48b27` |
| T5 | 47 | 61,952 | 200 | 200 | 4.7 | 349,010 | `69eaf510adab` |
| T6 | 11 | 61,952 | 200 | 200 | 9.4 | 350,147 | `16f7083214a1` |
| T6 | 29 | 61,952 | 200 | 200 | 9.7 | 350,213 | `65d9d849106c` |
| T6 | 47 | 61,952 | 200 | 200 | 9.4 | 350,258 | `1a1c7d14b6fc` |
| T7 | 11 | 61,952 | 200 | 200 | 9.6 | 356,391 | `a3c620e7c020` |
| T7 | 29 | 61,952 | 200 | 200 | 9.7 | 356,528 | `ffc7d6ebe0e5` |
| T7 | 47 | 61,952 | 200 | 200 | 9.5 | 356,367 | `6163942b4dde` |

- UNSUPPORTED rows are results, not drops: tune 66 of 3,036 scored rows, evaluation 12 of 552; they are inside the denominators above.
- Retained non-citable or superseded records: interrupted tune attempt `p05-t03-heldout-001` (E-P05-003, stopped by the owner at 1,354 rows); T07 sweep runs `001` (event-level scoring defect) and `002` (before the hub metric); `p05-t03-smoke-001/-002` (failed) and `-003`.
- Train-fit numbers in E-P05-001 are memorisation of 178 queries by 62k-parameter adapters, not held-out evidence.

## 4. Separation sweep (T07, E-P05-006): geometry versus approximation

Tune-role captures, 384 dimensions, 1,858 cells, no threshold, nothing selected. 51 identity-applicable queries; only 8 eligible pools hold a non-gold episode.

| question | observation |
|---|---|
| Does a learned code beat frozen E5 inside an eligible pool? | Yes on 8 contested queries: strict contested top-1 0.50 (T0) versus 1.000 (T1, T4, T5, T7); the eligible scope cannot tell geometry from approximation (a 4-coordinate random projection of a learned code also scores 1.000). |
| Does it carry identity across pools? | No. Over 301 pooled events (31 episodes, chance 0.044) T0 scores 0.549; learned arms 0.000–0.078; T1/T4/T7 lead with one episode for 98–100% of queries (R37). |
| Is sparse better than a random dense code of equal bytes? | Not consistently (T0 pooled, 1/2/5/10%): weighted top-k at 16–152 B 0.137 / 0.196 / 0.176 / 0.157 versus a Gaussian dense projection at the same bytes 0.137 / 0.098 / 0.203 / 0.281, versus 0.549 for full dense (1,536 B); binary support overlap 0.059 / 0.020 / 0.078 / 0.059 versus 0.111 / 0.137 / 0.157 / 0.203 at its byte budget. |
| Collisions between distinct episodes (465 pairs) | Weighted 0 at every sparsity; binary 58 / 12 / 6 / 4 pairs at 1 / 2 / 5 / 10%; full-width binary 465 (control). |
| Fusion with a learned code | Eligible 0.96–1.000 from 10% up; pooled falls below T0 (T1 dense 0.222 / 0.190 / 0.105 versus 0.549). |
| Partial-cue strata | T0 pooled COMPLETE_CUE 0.522 (24/46), PARTIAL_CUE 0.800 (4/5); 5 queries support no inference. |

Negative proof kept: no universal orthogonalization, c-to-c^k or Johnson–Lindenstrauss claim; no approximate-nearest-neighbour index; the model and dimension were not changed (frozen E5, 384).

## 5. Ambiguity, over-separation and transfer (T08, E-P05-007)

Same frozen codes over all 138 tune queries (51 sufficient, 86 insufficient-cue, 1 other). Claims stay inside ADR-0027 Q-B: same-target rewording and unseen identity (entity-disjoint roles by construction); the rewordings differ in language and carry no paraphrase label, so **no language-transfer claim is made**.

| question | observation |
|---|---|
| Specific cue picks the right episode? | Inside a pool, set recall 0.250 (T0) versus 0.583 / 0.583 / 0.625 / 0.750 (T1 / T4 / T5 / T7); same-target rewording consistency 14/15 (T0) versus 15/15; no cluster worse for those four arms. |
| Vague cue keeps a plausible set or asks? | The top-1/top-2 gap does not mark sufficiency: gap AUROC 0.20–0.54 (T0 0.331; learned arms widen the gap more on insufficient cues, e.g. T1 median 0.210 sufficient versus 0.397 insufficient), so a separation-margin clarification rule would be backwards or uninformative (R38). Over-separation on ambiguous cues is harm, not benefit. |
| Cross-pool transfer harm | Pooled top-1 0.549 (T0) versus 0.000–0.078; set recall 0.510 versus 0.000–0.078; learned arms worse than T0 in 9–10 of 14 clusters. |

## 6. Margins, custody and what would invalidate this

- Frozen before the first tune-role read (source commit `e47bf6f`): minimum benefit **+0.05** with a lower bound above zero; maximum regression **0.02** for the harm contrasts (C3 lower bound not below −0.02; C4 and C5 upper bounds not above +0.02); selection by highest tune C1 point estimate with ties to the earlier arm; raw loss never selects. These are the same values as `loss_heldout.CONFIG["margins"]` and the proposal `p05_r09_margin_proposal.md`.
- T07 and T08 had no approved margins; they are descriptive and cannot promote or reject an arm.
- Calibration and locked-test roles were not copied or read; the evaluation role was read once for the selected arm and two comparators, after selection was frozen.
- **A post-result margin revision, tuning on calibration or test data, or promotion from the T07/T08 descriptive numbers invalidates promotion of any learned arm.** A learned arm may be reconsidered only with new owner-approved margins fixed before the first read and a role not already reported.

## 7. Consumers and limits

- **P06 graph study** reads: T0 as the retained semantic code; the limits R33 (tiny development data, 14 clusters), R35 (saturated identity endpoint, eligible pools rarely contain a distractor), R37 (learned codes collapse onto a hub over pooled events: never a global identity index) and R38 (separation margins do not mark cue sufficiency: abstention must come from evidence-sufficiency checks).
- Not tested: language transfer (Q-B), template/category transfer, any dimension above 384 (Q-A), any approximate-nearest-neighbour index, human-audited gold, larger candidate pools, the reconstruction decoder at stored checkpoints (training-only).

## 8. Provenance

| artifact | sha256 |
|---|---|
| held-out manifest `p05-t03-heldout-002` | `c2a3f834c4def91ecfb318750d64644ec61eae52339cd29b6edae76e286d2cc9` |
| held-out run code digest | `eb7486da6b121c60ca239f1fed94353b1e3fbb2b8a1f9751257611276cad2ca6` |
| selection | `cb0ea3de70d4b626caac73529a9e9909d011832c0d139a5bde3bfc6d7321812c` |
| held-out report | `e8b82db509c372fd3d7c3818ab5952412f96622ef77c44056b83bd542a3e22b1` |
| factorial training digest (`p05-t03-001`) | `2e0fc9567dc2144caf3ee933566eb7c150a47a2d0ae5951c378424688401b0f6` |
| T07 sweep report (run 003; rerun 004 after the loader fix reproduces every cell, sha `a081e67cf46d02219332d044afc6c33d39b7bbf1c14c3e95f3cdcb89cd71a655`) | `f6f26498df72828721eaade1e071fbb1844671c34648ecc34717e663a56d9013` |
| T08 partial-cues report (run 001; rerun 002 after the loader fix reproduces every cell, sha `68d81ba1597f0913c5e99ce1981960666cebccafbade38d5e7322811c1770365`) | `4a61282947212d58eb8a7893470280bba5c1db90b604c9ca8eb88f2b4b8023e4` |
