# Norn research execution protocol

Version 1.1 execution protocol, status updated 22 October 2026 (Asia/Bangkok). Source: blueprint “Research hypotheses,” “Datasets and benchmark alignment,” “Metrics, statistical protocol, and cost,” and “Experiment execution sequence.” The MDP owns implementation algorithms/schema/flows; this file owns experimental conduct and interpretation. P02 harness/math controls and P03 exploratory conventional-retrieval measurements have run. P04 frozen-backbone exploratory measurement completed under ADR-0020/E-P04-005:4,140conditions, matched single-event controls and an INCONCLUSIVE decomposition/attention result. The conduct protocol is unchanged; no promotion margin/power or sealed confirmation is inferred. No sealed study has run and no numeric efficacy threshold is accepted.

## Questions and controlled alternatives

| Hypothesis | Main contrast | Failure / limiting result | Owner |
|---|---|---|---|
| H1: complementary views improve partial-cue recall | B0 vs B1/B2 and matched-capacity single encoder | Repeated heads add no conditional information or cost dominates | P04 |
| H2: aligned shared code beats simple fusion | B3/B4 vs B1/B2 | Shared code loses details or alignment does not generalize | P04 |
| H3: separation helps interference without harming cues | dense/random/sparse/learned/margin controls | Better inter-event spacing loses correct partial-cue/paraphrase recall | P05 |
| H4: activation adds complete evidence chains | G3 vs G0/G1 with same graph/seeds/budgets; G2/G4 alternatives | Extra neighbors/false associations cost more than useful support | P06 |
| H5: reconstruction helps useful recall | CDZ-A exact versus B decoder/C hybrid | Fidelity distortion or no downstream gain | P07 |
| H6: salience adds task utility | S0 vs S1/S2 same candidate set | Irrelevant dramatic signals displace required neutral evidence | P07 |
| H7: gates reduce unsupported recall | Governed versus carefully matched gate ablation in isolated evaluator | Strong governed hybrid matches candidate; false abstention erases gain | P03/P09 |
| H8: consolidation helps long-run updates | C0 vs C1/C2; C3 separately eligible | Lost rare exceptions, false generalization, stale revoked support | P08 |
| H9: projections remain coherent under faults | Local then approved external stores with fixed algorithm | Index lag, erased-source exposure, retry/rebuild inconsistency | P11/P12 |
| H10: compression has useful quality/resource frontier | Float32 exact vs fp16/int8/binary/PQ/residual; ANN cross-control | Rescore/update overhead or recall loss dominates savings | P10 |

Gate-ablation experiments never disable live user security. Use isolated synthetic published input with evaluator-observable consequences. All supported arms preserve the declared trust/permission floor; any intentional unsafe diagnostic is separately named and cannot become serving behavior.

## Stage and axis control

Preserve Stage0 foundation/harness/strong baselines → Stage1 views/loss/separation → Stage2 graph → Stage3 CDZ/salience/consolidation → Stage4 longitudinal/external → Stage5 operational/fault track → Stage6 locked confirmation. MDP P00-P13 supplies executable-sized phase groups. Compression is an orthogonal later axis after retrieval geometry stabilizes. Numeric dimensions, sparsity, graph damping/scale/iteration/hops and source-world sizes in the blueprint are illustrative search points, not known optima or mandatory production limits.

Do not run every theoretical combination. Establish individual mechanisms, freeze conditional follow-ups on development, then study justified interactions. B5 denoising, G7 recurrent completion, generated C2 and learned C3 have explicit eligibility/compute/privacy gates and honest unsupported states. Absence is recorded rather than replaced with an unrelated mechanism. A no-benefit conclusion can complete its investigation and preserve the simpler winner; it does not satisfy an efficacy prerequisite for larger dependent models.

## Required comparator capability ledger

R0 exact/BM25; R1 dense ANN plus exhaustive diagnostic; R2 hybrid RRF; R3 hybrid plus fixed reranker; R4 multi-vector late interaction where feasible; R5 official HippoRAG2 pipeline; R6 graph retrieval in common-input and native-ingestion conditions; R7 naive view fusion; R8 shared binding without graph; R9 fixed-hybrid seeds plus graph; R10 shared binding plus controlled graph plus evidence gate.

Before running each comparator record source repository/release/commit, license, installation digest, actual public entry point, encoder/model/tokenizer pins, native extraction/indexing inputs/cost, capabilities, data visibility, safe synthetic smoke and unsupported features. Verify current official source during implementation; blueprint citations are leads, not proof that a version runs today. Optional GraphRAG Local, LightRAG and memory-system native comparisons have their own rows and disclosed differences.

Common-input track controls source snapshot, principal, question, evaluation clock, explicit metadata, query budget, evidence token budget and downstream generator. Native-system track allows authentic ingestion/extraction while recording feature/cost differences. Equal final K is not equal tokens or information. Do not force graph-native systems into a crippled pipeline and call the result a fair native comparison. R10-vs-R3 is a system comparison; graph contribution requires G3-vs-G0/G1, and improved seeding needs its own fixed-topology comparison.

If R4/R5/R6 or an external dataset cannot run, retain FEATURE_NOT_SUPPORTED/NOT_RUN with exact reason and limit the supported claim. Do not drop the arm, score a fake implementation, declare missing capability zero accuracy without the estimand, or report universal superiority from a reduced comparator set.

## Dataset construction and custody

1. Build a deterministic evaluator-only typed hidden world of events, assertions, identity namespaces, time/authority states, relationships, source independence and causal truth.
2. Render published documents/messages/observations/action histories. Source text/versions/locators have digest manifests independent of labels.
3. Define E1-E14 pairs: near-duplicate episodes, partial cues, multi-hop support, hubs/false paths, corrections, authority conflicts, late-arrival/as-of time, salience distractors, missing-evidence twins, forbidden neighboring source, prompt poisoning, projection faults, rare-exception consolidation and EN/ID/code-mixed cues.
4. Build multiple acceptable minimal evidence sets where alternatives are valid. Distinguish insufficient ambiguity from a disambiguated unique target. Do not assign a convenient sole gold when the source supports several events.
5. Split by scenario family and entity cluster before creating paraphrases. For P02, the owner explicitly approved disjoint scenario/entity instances within every E1–E14 task category (ADR-0015); task-category and template-level transfer are separate, unmeasured questions. Smoke validates machinery, development chooses hyperparameters, calibration fits probabilities/abstention thresholds, locked test supports final confirmation. Blueprint illustrative split proportions require a power/strata review before selection.
6. Preserve custody by filesystem/import/publication boundaries. Runtime/model input contains no expected answer, required evidence slots, hidden fact ID, stratum label, gold causal graph or outcome through text, names, aliases, metadata, embeddings, graph construction, prompt or trace. Runtime prerequisite inference is independent of evaluator gold.
7. Audit a stratified sample, include difficult disputed cases and double annotation/adjudication. Preserve annotator identity/role, independence, source/gold hash and changes. Model/coordinator labels are explicitly non-independent unless independently adjudicated.

Canary and damaged-publication tests must demonstrate that the barrier can fail for the intended reason. A missing signal is not proof of no leakage beyond the inspected scope. Gold-graph diagnostics estimate the topology upper bound; source-derived graphs measure realistic extraction errors. Never silently mix their scores.

## Measurement tracks and controls

Retrieval-only stops before answer generation and scores exact canonical identity/support. Controlled QA uses the same approved fixed generator, prompt, evidence budget and response schema. Native end-to-end allows real agent behavior with extra calls/tools/ingestion disclosed. Host continuity and live-observation freshness are tested through actual restarted consumers, not simulated context strings alone.

Every metric passes hand-computed positive/negative cases plus perfect, empty and shuffled controls. Perfect evidence can still be ambiguous/insufficient under gold; “perfect” does not mean always answer. Empty evidence should abstain when appropriate and lose answerable coverage. Shuffling must damage identity/support while leaving failure accounting valid. Corrupt manifest, changed gold, missing ledger row and unobserved-stage labels must invalidate scoring rather than silently return numbers.

## Metric definitions and denominators

- Ranking K refers to a named observed stage, canonical unit (event/atom/source), and dedup policy. Report candidate depth, final depth, distinct events/atoms and token budget separately. Recall/Precision/MRR/nDCG/Success use declared eligible gold units and alternate valid sources.
- SlotCoverage is fraction of applicable satisfiable evidence slots covered; CompleteSet is whether a valid minimal support set is present. Live/uncitable/unsatisfiable slots get explicit applicability rules; no applicable denominator returns unavailable, not a misleading perfect score.
- Episode identity accuracy is conditional on sufficient cue. Ambiguity detection, same-event paraphrase recall, wrong-episode confusion and partial-cue degradation curve prevent discrimination from hiding lost generalization.
- Graph metrics include extraction/identity precision, verified path provenance, false association, wrong causal promotion, hub exposure and useful complete evidence per visited work. Work counts include repeated transitions, not just unique nodes.
- Answer metrics separate five-status classification, material claim/support correctness, citation/span validity, wrong vintage, missing-reason accuracy and partial utility. A citation hash proves provenance, not semantic entailment.
- False-Answer Rate uses the specified insufficient/conflicted population. False-Abstention Rate uses sufficiently answerable cases. Selective risk/coverage/AURC retain the chosen accepted-set denominator. Both sides and counts must appear.
- If confidence exists, declare target as all material claims correct and supported. Fit only on calibration; use proper scores/Brier/logloss/ECE and reliability/risk–coverage. Similarity, activation, RRF and self-reported confidence are not probabilities.
- Report each privacy leak, fabricated source and unsupported operational directive separately from means. Zero observed incidents includes exposure count and uncertainty bound; it is not zero population risk.

## Failure and resource accounting

Ledger records every planned pair, attempt, error origin, timeout, invalid/unsupported/not-run outcome, consumed budget, artifacts and safe reason. Candidate, provider, harness and unavailable-feature faults are distinct. Intention-to-treat benefit analysis includes eligible planned failed cases according to a preregistered scoring rule; conditional-completed tables show exclusions and counts. Safety metrics use declared observation denominators; unobserved safety is unknown, not safe. Never delete a failed arm or use best-of-N silently.

Record offline parsing, atom/relation extraction, model training, indexing, graph build, codebook fitting, storage, migration/rebuild and amortization. Online record query encoding, exact/ANN, transitions, reranking, source verification and generation. Include cold/warm/hot conditions, hardware/threads/VRAM, concurrency, queue backlog, source/model revisions, raw tokens/calls and known/unknown failed billing. Provider presence does not authorize calls; exact explicit per-command enablement and bounded spend/attempt/time are required.

Quantiles and throughput claims require adequate samples, workload and saturation context. Report p50/p90/p95/p99 only with sample counts/uncertainty and failures. No invented latency SLO, free cost, production capacity or RPO/RTO before actual measurement. Changing database vendors is a separate operational comparison at fixed algorithm settings.

## Pilot selection and sealed confirmation

Primary blueprint-proposed endpoints: R10 versus R3 partial-cue CompleteSet@10; G3 versus G0/G1 evidence-complete multi-hop retrieval under matched resources. Before locked use, owner-approved protocol records which supported contrasts actually apply, practical minimum benefit, maximum false-association/coverage/privacy regressions, family/cluster sample count, power/effect estimate and analysis plan. Current values remain **UNSET**; suite completion does not require pretending they are known.

Pair identical questions and resample scenario-family clusters, not paraphrases independently. Record training seeds and use hierarchical analysis or seed-aware reporting. Declare primary/secondary/exploratory comparisons and correction family (FWER/FDR method as approved); report effect sizes/CIs per stratum, corpus scale, language, degree/cue corruption and external track. Insufficient clusters/power produce descriptive or inconclusive evidence. Quality/cost/latency/footprint/selective-risk Pareto frontiers retain simpler winners.

Seal code revision, configuration, model/checkpoint/tokenizer, source/test/gold hashes, hardware, prices, hyperparameters and run order. A dirty or mismatched input cannot claim a sealed run. Locked test executes once under that protocol. A bug, invalid run or retest is recorded, seal broken and results exploratory or governed by a new explicitly sealed protocol; no quiet retuning. Reproduction uses a separate nonlocked profile unless a declared custody policy permits a specific confirmatory replication.

## Research acceptance and reporting

Promotion to more complex operational integration requires prespecified practical gain or documented new capability at cost, acceptable regression bounds, passing scoped source/permission/deletion/time integrity, external transfer or explicit synthetic-only limitation, and justified indexing/training/storage/query resources. A missing comparator/dataset, unsupported semantic label, unexecuted optional arm or unresolved material review finding limits the conclusion.

Report technical design, data/annotation custody, exact manifests, controls, all successes/failures, per-stratum estimates, cost/fault envelope, native differences, negative results and threats to internal/external validity. Preserve source register and verify attributed claims against official primary sources during implementation/reporting. Do not infer neural equivalence, brain-level cognition, causal truth or universal RAG superiority. Archive reproducible qualified conclusions, including rejection of favored mechanisms.

## Owner-selected generative provider

ADR-0010 selects Groq whenever an authorized task needs generative inference, with explicit per-run Qwen 3.8 27B, GPT OSS 120B or GPT OSS 20B. Verify actual API identifiers/account availability at first authorized integration and retain provider/model in manifests. No default or silent fallback; controlled tracks fix the selected generator, while an explicitly changed model is a distinct recorded condition. This policy does not choose retrieval embeddings/reranker/training backbones. Credentials load only for the particular enabled bounded command; ordinary tooling/tests stay credential-free. P01–P03 are complete and P04 is authorized (ADR-0020); deterministic/local-model work makes no provider call. Later generative integration still requires its explicit enabled task.

## P04 exploratory interpretation

Final003 uses disjoint276/138/138 development-role instances before wording and no tuning-label selection. Reusing the same instances as preserved002 after an integrity fix is not independent replication. Constructed labels remain unaudited. B3/B4 and matched S3/S4 have equal observed CompleteSet; attention/decomposition benefit beyond adapter capacity is not established. Conditional removal/duplicate diagnostics are frozen-feature ranking checks, not conditional mutual information; five nonzero cue-missing points each contain one unique case. First-query timings mix cold/warm states despite a disclosed static resident label, so rare starts may be absent from per-arm p99. Preserve actual elapsed/attempt records, source/operator/model/offline/storage boundaries, false answers/refusals and INCONCLUSIVE outcome (evidence/binding.md, ADR-0022, E-P04-005). P05 is a separate unmandated Stage1 investigation; locked/external/general entailment/production claims remain unavailable.
