# P06-T13: E3 sufficiency mechanism on the existing baseline

Status: **DONE (read-only replay, development fixture).** Authority: ADR-0029 P06-Q5 (the mechanism is confirmed before any margin is proposed), MDP P06-T13. Reader: `benchmark/runs/e3_mechanism.py`; tests: `tests/test_e3_mechanism.py`. Run replayed: `.norn/p05-pre-r-002` (R0 to R3, 135 queries, 540 observations; manifest `84939fb304b1a20f5583d38ac19f83f519b842ffb63389671a694abf3f212f5d`, ledger `89c4eae25b5efed7d5cec6f3a1ca689b5a44630ba2ed62826e68563a9c1b802c`, both re-hashed by the reader against `completion.json` before use). No retrieval, model call, network call or credential was used; the run directory was not written.

## 1. Question

The start adversary of ADR-0029 suspected the E3 chain failures came from the sufficiency gate (`AMBIGUOUS` when one requested field has several distinct values) rather than from retrieval. If so, a graph arm's chain gain could be a changed gate, not a better traversal. T13 asks which false abstentions come from which mechanism.

## 2. Method

For every E3 observation of every arm, the reader rebuilds the exposed `Record` objects from the stored packet, re-derives the request with the benchmark's own `interpret()` (public query and sources only), and calls `norn.governance.sufficiency.decide` twice: once as observed (fidelity check) and once with the requested fields set to the predicates of the exposed records (the input the adapter withholds). Gold is joined only afterwards, in `classify`, to score slot coverage and the complete set. Slots are scored on published source ids taken from the result candidates, exactly as the evaluator does (the packet's own source ids are engine-internal and never match; the first version of the reader used them and was corrected before any number was recorded).

## 3. Result

| Quantity | Value |
|---|---|
| E3 observations replayed | 52 (13 queries, 4 arms), 0 not replayable, 0 not reproduced |
| Applicable positives (expected SUPPORTED) | 24 (6 per arm) |
| False abstentions | 24, 6 per arm |
| Observed reason of all 24 | `MISSING_CASE_INPUT` (none `AMBIGUOUS`) |
| Rule that would fire if the fields were supplied | `AMBIGUOUS` in all 24 |
| Complete evidence sets | R0 2, R1 1, R2 1, R3 1 (equal to the stored report) |
| Mechanism classes | `ADAPTER_AND_GATE_RULE` 5 (evidence complete); `RECALL_ADAPTER_AND_GATE_RULE` 19 (evidence incomplete) |

**Confirmed mechanism.** The six false abstentions per arm are not produced by the `AMBIGUOUS` rule. `interpret()` clears the subject and the requested fields for any query containing chain, links, rantai or tautan (`benchmark/adapters/baseline.py`, with the comment that field-only sufficiency cannot adjudicate a typed path), so the gate returns `MISSING_CASE_INPUT` before any value comparison. The adversary's hypothesis was therefore wrong about the observed cause and right about a latent second barrier: with the fields supplied, `AMBIGUOUS` fires on all 24 because a chain has several subjects with distinct values at one time. Recall is a third, separate limit: only 5 of 24 arm-cases expose a complete set, and 19 expose two of four slots or fewer.

**A field-only gate cannot tell chain completeness.** With the fields supplied, a single exposed link, which is incomplete or ambiguous by construction, returns `SUPPORTED` / `SUFFICIENT` (the E3 ambiguous variant, and one missing variant for R0). Supplying the fields to the existing gate would therefore trade false abstentions for false answers. A chain-aware status needs a typed-path check, which is a different treatment from a graph traversal.

## 4. Consequences for later cards

- **T21 margin proposal and T10 reporting:** the primary endpoint stays slot recall (complete evidence set), reported separately from status. A graph arm that raises chain recall on the unchanged adapter and gate will still be scored as abstaining on every chain query; that is expected, not a regression. Any arm that changes `interpret()` or the gate is a different treatment and its status gain must not be credited to the traversal.
- **Pools and chains:** the existing E3 has one entity cluster and four-link chains over three languages, so it cannot support a power claim; the `public-v2` families (T18) replace it.
- A later chain status contrast must be paired with a typed-path completeness control that fails on a single link.

## 5. Proof and limits

- Positive: a four-link chain with all slots exposed reproduces `MISSING_CASE_INPUT`, shows counterfactual `AMBIGUOUS`, and is classified `ADAPTER_AND_GATE_RULE` with complete set true (not a retrieval failure); a two-link exposure is `RECALL_ADAPTER_AND_GATE_RULE`; the stored run reproduces the report's complete-set and false-abstention counts for every arm and all 52 rows reproduce their observed status and reason. Hand check on the single-slot positive (R0): two exposed `requires` atoms, two subjects, two values, one event time, so `decide` returns `NOT_ESTABLISHED` / `AMBIGUOUS` by the rule in `governance/sufficiency.py`, matching the table row.
- Negative: failed or unsupported rows are retained with their reason, an unknown record key is a schema failure, a changed ledger is `LEDGER_CHANGED`, the replay function has no gold input (AST check) and unrelated gold changes nothing on the gate side.
- Limits: the replay input is the exposed record set after packet truncation, not the full pre-packet set (which is not stored), so a gate decision on the larger set can differ (all 52 reproduced here); the run's code digest differs from current source by design, so the reader checks the artifact digests, not the code digest; the fixture is a single-cluster synthetic corpus and the result is descriptive, not a statistic.
