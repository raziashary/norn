# P05 R09 margin and endpoint proposal (PROPOSED — owner approval required)

Status: **PROPOSED, not approved.** Written 2026-11-07 by main under ADR-0026 ("main proposes, owner approves, then freeze") and ADR-0027 Q-D. Nothing here is frozen. No tune-role or evaluation-role score has been read for P05; the only held-out information used is the already-published P04 development report (`p05-pre-b-001`, 14 clusters per role), which is a pilot for variance, not a preview of any P05 arm.

## 1. What this unlocks

Until the owner answers, P05 reports only **exploratory contrasts** (ADR-0027 Q-C): train-fit diagnostics (T03/T04), the two toy reproductions (T05/T06), and mechanical checks. The first read of the tune role for any P05 arm waits for this answer, after which the values below are frozen in `docs/development/RISKS_AND_OPEN_QUESTIONS.md` R09 and ADR-0027 and cannot be revised after seeing results (a revision is a recorded retest that limits the result).

## 2. Proposed contrasts (family of five; Holm correction)

Unit of analysis is the scenario-family **cluster** (paired, equal-cluster-mean difference, cluster bootstrap, as in the P04 report). Seeds 11/29/47 are averaged within cluster, and seed-wise results are listed beside the pooled one.

| # | Contrast | Metric (existing P04 row field) | Role |
|---|---|---|---|
| C1 | best loss-factorial arm − T0 (frozen E5 single feature) | `episode_top1` over `identity_applicable` queries | benefit |
| C2 | same arm − T1 (retrieval-only) | `episode_top1` | benefit (does separation/reconstruction add anything?) |
| C3 | same arm − T1 | `complete_set` on `cue_missing_fraction == 0` and paraphrase queries | harm (over-separation) |
| C4 | same arm − T1 | `false_answer` rate over its declared denominator | harm |
| C5 | same arm − T1 | `false_abstention` rate over its declared denominator | harm |

"Best arm" is chosen on the **tune** role by a rule fixed before the first read (highest mean C1 point estimate; raw loss values never select, blueprint 9.4) and then scored once on the evaluation role.

## 3. Proposed practical margins

* **Minimum benefit:** C1 and C2 lower 95% bound above 0 **and** point estimate at least **+0.05** absolute. Below that the extra training objectives are not worth their cost.
* **Maximum regression:** C3 lower bound not below **−0.02**; C4 upper bound not above **+0.02**; C5 upper bound not above **+0.02**. Privacy: zero observed incidents, with the 95% upper bound reported, never "zero risk".
* **Simpler winner:** if no arm clears C1 or C2, the simpler arm (T0 or T1) is the retained result; a null result is a valid, recorded outcome.

## 4. Power from the pilot (why the answer to Q-C matters)

P04's paired learned-versus-late-fusion contrasts (`B3−B1`, `B4−B1`) had 14 clusters and an interval of [0.00, 0.26], i.e. a cluster-level standard deviation of about σ ≈ 0.25 (zero-inflated: most clusters tie). For a two-sided test at α = 0.05 with 80% power, n ≈ ((1.96 + 0.84)·σ/Δ)² clusters:

| Δ (minimum benefit) | σ = 0.25 (pilot) | σ = 0.15 | σ = 0.10 |
|---:|---:|---:|---:|
| 0.05 | 196 | 71 | 31 |
| 0.10 | 49 | 18 | 8 |

The development roles hold **14 clusters each**, so a powered confirmatory claim is not available from them at Δ = 0.05. The honest options are: (a) keep P05 development-exploratory and report intervals without a promotion claim (recommended; matches Q-C); (b) grow the number of fictional scenario families before any locked test; (c) raise Δ to 0.10 and accept about 49 clusters at the pilot σ. This proposal does not choose among (b) and (c); it needs the owner.

## 5. What is deliberately not proposed

No threshold for T07 (dimension/sparsity) or T08 is set here; those inherit these margins only if approved. No calibration or locked role is touched. No margin is derived from any P05 arm's result.

## 6. Decision requested

Approve, amend, or reject sections 2–4 (ADR-0027 Q-D), and say whether option (a), (b) or (c) of section 4 applies (ADR-0027 Q-C).
