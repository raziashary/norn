# Subcortical Memory Blueprint
## A neuroscience-inspired, evidence-governed research architecture and experimental protocol for AI memory

**Version:** 1.0 (research blueprint; no measured end-to-end performance claims)  
**Date:** 19 October 2026  
**Status:** Design hypotheses specified; implementation and confirmatory testing pending  
**Related experimental protocol:** *Palladion — Retrieval and Evidence-Reliability Benchmark*, 18 October 2026 (methodological companion, not the same product)  
**Scope:** Episodic and semantic agent memory; functional decomposition; shared latent binding; graph activation diffusion; interference control; provenance; consolidation; selective abstention; systems reliability.

> **Research question.** Can a memory architecture combining distinct, task-relevant functional views, a shared query–memory binding space, evidence-grounded atomic relationships, and controlled activation propagation retrieve the *right* experience from incomplete cues more reliably than strong hybrid, multi-vector, and graph-based systems—without compromising epistemic integrity, privacy, costs, or later recall?

> **Epistemic contract.** Published neuroscience motivates mechanisms, **not** a proof that a corresponding AI component works. Equations below are proposed engineering models unless stated as established mathematics. Proposed thresholds and model sizes are experiment settings, **not observed optima**. The architecture should lose to a simpler baseline if the data support that conclusion.

---

## Contents

1. Purpose, lineage, and claims that can be falsified
2. Research context: what existing memory mechanisms miss
3. Neuroscience: findings, caveats, and computational translations
4. What a memory is: immutable event, atomic facts, views, and graph
5. Core design principles and system invariants
6. System-level architecture
7. Encoding and write pipeline
8. Shared latent binding: learned space and multimodal-transformer alternatives
9. Training objectives and experimental loss matrix
10. Pattern separation: mathematics, fresh simulation, and trade-offs
11. Pattern completion through physics-inspired graph activation
12. Convergence–Divergence Zone: indexing versus reconstruction
13. Emotional salience: monoamine-inspired versus task-derived models
14. Deterministic regional operators, gates, and policy rules
15. Temporal identity, contradiction, updates, and provenance
16. Complementary learning systems and consolidation
17. Retrieval, verification, and selective abstention
18. Polyglot storage, replication, sharding, and index coherence
19. Failure containment, security, privacy, and operational testing
20. Data contracts and illustrative pseudocode
21. Research hypotheses, experimental arms, and ablations
22. Dataset construction, negative controls, and benchmark alignment
23. Metrics, statistics, costs, and decision criteria
24. Experiment execution sequence and implementation milestones
25. Open questions, threat model, and research limitations
26. Sources and further readings
27. Decision log mapping every requested architectural revision

---

# 1. Purpose, lineage, and falsifiable claims

This document replaces a prior research discussion with an executable **study design**, not a fixed claim of brain-equivalent cognition. The original intellectual journey is preserved: a three-part memory system (episodic lexical recall, semantic dense recall, procedural rule retrieval) raised the question of whether one memory should be represented across several *functional* operators instead of being assigned to one semantic region. Investigations of distributed engrams, hippocampal pattern completion and separation, emotional modulation, complementary learning systems, and Damasio's convergence–divergence framework motivated a proposal containing regional representations, a shared binding code, sparse separation, and reconstructive recall.

Several claims in that proposal were too strong: exact biological neuron counts do not dictate software dimensions; random sparsity does not guarantee a specified cosine transformation; cross-attention does not create retrieval alignment without supervision; a nearest-neighbor index is not an attractor network; and the original read path did not specify how incomplete natural-language cues entered the *same* representation space as stored memories. The revisions here expose these assumptions as separate tests.

**Primary practical claim (P1):** functional facets, perhaps learned into a shared query–memory latent space, improve robust evidence retrieval under interference at matched resources.  
**Associative claim (P2):** seeded, damped traversal of atomic fact–event graphs improves missing-link and multi-hop retrieval beyond similarity search, while remaining safe against false associations.  
**Cognitive claim (P3):** carefully constrained complementary learning and episodic/semantic separation improve long-term correctness under updates, without silent factual rewriting.  
**Optional biological claims (P4):** sparse pattern separation, monoamine-inspired salience, and reconstructive CDZ decoding each provide *incremental* performance beyond simpler approximations.

**Failure conditions are meaningful.** If hybrid retrieval plus temporal metadata matches the proposed system on retrieval, answer quality, selective risk, and cost, that is evidence against the added mechanism **for the tested workload**. This does not experimentally refute biological neuroscience; it refutes an engineering benefit claim under specified conditions.

# 2. Research context: the problem being solved

An AI memory must solve more than approximate semantic search. It must distinguish similar events with changed details; retrieve from partial or indirect cues; retain facts, actors, scope, temporal context, and uncertainty; maintain relations between people and events; reconcile corrections without overwriting history; forget authorized content; and tell the truth when evidence is unavailable.

### Example: near-identical episodes

- Monday 08:50: `PERSON-17` parks at `GARAGE-B2/ZONE-A`; recorded from a message.
- Tuesday 09:10: the same person parks at `GARAGE-B2/ZONE-C`; recorded from another message.
- Wednesday 11:30: "Where was I parked yesterday?"

A coarse embedding may overemphasize shared entities, location, and action. A naive novelty gate may suppress Tuesday. A sparse code may distinguish them but make Tuesday inaccessible to the short query. A graph walk may follow a highly connected `GARAGE-B2` node to Monday. A wrong time resolver may interpret “yesterday” from ingestion time instead of the query clock. The correct system must combine **episode identity + as-of resolution + cue retrieval + evidence validation**.

### Example: associative recall

- `EVENT-42`: an agent changed a retry configuration.
- `EVENT-47`: a service began timing out following a deployment.
- `OBS-48`: logs show a previously unseen error code.
- `HYP-49`: someone speculated that the retry change caused the timeouts.

A query “What might explain the service timeout?” should discover linked events and candidate hypotheses while **not upgrading** the causal hypothesis to a verified fact. Here graph traversal could outperform text similarity, but only if edge identities and epistemic states survive every step.

### Existing comparative landscape

Single-vector RAG is only a weak baseline. Relevant competitors include BM25, dense embeddings, hybrid RRF, learned rerankers, multi-vector late interaction (ColBERT-style), graph/PageRank retrieval (HippoRAG 2), graph-based document retrieval, and memory systems designed for temporal updates. The research target is therefore specific **failure patterns** not a blanket claim of superiority over all retrieval systems [R9–R12].

# 3. Neuroscience: findings, caveats, and computational translations

## 3.1 Regions as functional operators, not semantic buckets

In the original hypothesis, “emotional memory” went to an emotional store, “spatial memory” to a spatial store, etc. The improved hypothesis treats a memory as an experience whose **multiple features** can be transformed by different specialized computations. This is attractive because one event may simultaneously contain time, a goal, an emotional implication, a skill, and several relationships.

**Caveat:** the brain does not implement a clean engineering bus that necessarily broadcasts every experience to every region with four uniform encoders. Neural loops are heterogeneous, have feedback, differ by task and learning phase, and are not equivalent to microservices. “Region” names below label **functional design hypotheses** rather than anatomical reconstructions.

## 3.2 Distributed engram participation

Roy and colleagues measured encoding-related ensembles in 247 surveyed mouse brain regions during contextual fear conditioning and found 117 regions with high-probability engram candidates. Coordinated reactivation enhanced recall [R1]. This provides evidence for distributed participation in one particular memory paradigm; it does **not** imply (a) every human memory occupies those regions, (b) one software memory must be saved N times, or (c) region-count determines retrieval dimensionality.

**Translation:** one canonical event can have several derived functional views, joined through a stable identity. Redundant views are not independent copies of truth.

## 3.3 Tri-synaptic circuit and the separation/completion tension

The canonical hippocampal tri-synaptic pathway is entorhinal cortex → dentate gyrus → CA3 → CA1, embedded in a richer network of direct entorhinal inputs, return projections, and modulation. The dentate gyrus is associated with discriminating similar inputs; CA3's recurrent circuitry motivates autoassociative or attractor accounts; CA1 contributes comparison, integration, and downstream signaling. Claims that *all* cues must take one serial path or that every function uniquely belongs to one anatomical node should be avoided.

**Translation:** distinguish (i) creating separate event identities, (ii) recovering candidates from incomplete cues, (iii) checking contextual consistency and novelty, and (iv) integrating sufficient evidence. These need not literally be placed in an identical network to the brain.

## 3.4 Amygdala, affect, and neuromodulation

Emotionally salient experiences can influence consolidation and recall. But dopamine, serotonin, and norepinephrine do not map one-to-one onto a three-dimensional text-inferred emotional truth. Lövheim's 2012 cube is explicitly a hypothesis; 2025 human recordings find context-, region-, and valence-specific patterns rather than a fixed emotion/transmitter rule [R4–R5].

**Translation:** preserve the original monoamine-inspired approximation as **one experimental arm** and compare with task-observable arousal/valence/importance features. Neither arm is entitled to override provenance or retrieval eligibility.

## 3.5 Basal ganglia, reinforcement, procedure, and action history

Reward-prediction error and habit learning are valid conceptual references. A memory system nevertheless needs observations of actions, consequences, success criteria, and delayed outcomes before it can learn procedural usefulness. A narrative containing the word “reward” does not constitute a verified reinforcement signal. A deliberately simple operator should extract or index structured action–outcome sequences and keep assumptions distinct from observed rewards.

**Translation:** memory of *what happened* and learned policies for *what to do next* should be separately authorized. Procedural recommendations never inherit authority solely from frequency or vector similarity.

## 3.6 Prefrontal control and the dangers of rigid neural mappings

Top-down attention and goal-conditioned retrieval are useful models, but the prefrontal cortex also participates in long-term memory representations; it is inaccurate to declare it exclusively a query preprocessor. Implement *goal conditioning* as a measurable functional module and avoid dogmatic regional exclusivity.

## 3.7 Complementary learning systems

McClelland, McNaughton, and O'Reilly's CLS theory contrasts fast hippocampal encoding with gradual cortical integration across experiences [R2]. An AI analog might retain immutable event records while slowly publishing evidence-supported generalizations. A periodic consolidation job is a convenient engineering schedule, **not** proof that the system replicates sleep-dependent neural replay.

## 3.8 Convergence–divergence zones

Meyer and Damasio describe a neural account in which associative/disposition representations support reinstatement of content representations [R3]. This motivates *binding pointers* and *reconstruction* as distinct possibilities. It does not entail a VAE, a certain latent size, cross-attention, or generative regeneration of ground-truth text. Both alternatives remain experiments.

## 3.9 Scientific-to-engineering map

| Biological inspiration | Engineering hypothesis | Biological certainty | Independent experiment |
|---|---|---|---|
| Distributed engram participation | Multi-view derived representations | Evidence in studied paradigms | Single-view vs multi-view |
| DG pattern separation | Learned discriminative episode codes | Function supported; implementation open | Sparse vs dense vs supervised margin |
| CA3 recurrent completion | Recovery from partial cues | Influential models and empirical support | ANN vs graph propagation vs associative net |
| CA1 context integration | Consistency/error and context integration | Broad functional evidence | Context validation on/off |
| Amygdala modulation | Importance/salience score | Affect modulates memory; mapping uncertain | Monoamine proxy vs task proxy vs none |
| Basal ganglia sequence learning | Action–outcome episode modeling | Functional analogy | Procedural features on/off |
| Prefrontal top-down selection | Goal/identity/time-conditioned gating | Functional analogy | With/without task-context gate |
| CLS | Episodic events + slow validated abstraction | Established computational framework | Consolidation vs no consolidation |
| CDZ | Shared binding index and/or reconstructive decoder | Conceptual neural framework | Direct facets vs decoded facets |

# 4. Memory ontology: event, atom, relationship, and evidence

The term “atom” is useful **only if its identity and provenance are explicit**. An atom is not a mystical neural particle or necessarily a single token. It is a smallest *independently addressable and provenance-bearing unit* chosen for the experiment, often a qualified proposition or observation.

**Four distinct objects must never be conflated:**

1. **Event:** a specific occurrence with event time, actors, scope, origin and immutable source reference. Events remain distinct even when text similarity is near 1.
2. **Atomic assertion:** `(subject, predicate, object, qualifiers)` with its own ID, assertion type, recorded/valid time and source evidence. Examples: `EVENT-TUE -> HAS_ZONE -> ZONE-C`, `HYP-49 -> CLAIMS_CAUSATION -> EVENT-47`.
3. **Typed relationship:** a first-class, sourced edge between assertions/events/entities. `MENTIONS`, `OCCURRED_BEFORE`, `SUPERSEDES`, `DERIVED_FROM`, `CAUSED_BY`, `HYPOTHESIZES_CAUSE`, and `CONTRADICTS` have very different meanings.
4. **Derived view:** embedding, symbolic feature vector, sparse index code, salience score, graph projection, or summary. This is rebuildable material and **never the sole authoritative content**.

Every atomic assertion has `atom_id`, stable `event_id`, source (`document_id`, version, span/hash or authenticated tool observation), tenant/scope, actor/ingester, validation status, belief type, temporal attributes, content, schema version, and transformation lineage. Nodes that share a display name do not merge unless identity keys and scope agree. An immutable source can support more than one atom; an atom can be linked to multiple sources without losing the origin of each claim.

### Epistemic types (orthogonal to lifecycle state)

- `DIRECT_OBSERVATION`: grounded in supplied authenticated sensor, API, or trusted instrumentation.
- `USER_REPORTED`: attributed to a particular user, not independently verified.
- `DOCUMENT_ASSERTION`: grounded in a source, with separate approval/authority status.
- `MODEL_INFERENCE`: a derived claim with input provenance and model version.
- `HYPOTHESIS`: proposed, explicitly not verified.
- `DERIVED_AGGREGATE`: a summary/statistic with all contributing source IDs.
- `RETRACTED`: retained for audit but invalid for affirmative answers.

These are **not** five evidence outcomes from the benchmark protocol. Evidence outcomes (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONFLICT`, `NOT_ESTABLISHED`, `VERIFICATION_UNAVAILABLE`) describe a **query/answer**; epistemic types describe stored facts. Do not collapse them.

### Temporal dimensions

- `event_time`: when something occurred.
- `observed_at`: when source first perceived it.
- `recorded_at`: when registry recorded it.
- `valid_from` / `valid_to`: period the assertion applies, if meaningful.
- `as_of_basis`: domain-specific time context chosen for the question.
- `supersedes_id`: explicitly related prior assertion/version; neither physical deletion nor blanket “latest wins.”

A correction creates a new assertion that invalidates or supersedes an earlier assertion **within a defined scope**; it does not overwrite the original audit trail. A genuinely new parking event is a different event, not a correction to yesterday's event. An unverified report is never silently promoted to normative authority.

# 5. Principles and non-negotiable invariants

**I1. Immutable evidence:** canonical original events and source handles cannot be changed by retrieval. Corrections are new versioned records with explicit edges.  
**I2. Authority is external to similarity:** cosine, graph activation and salience never confer approval, identity, permission or factual truth.  
**I3. Stable identity:** every event, atom, edge, embedding version and source span has an independently resolvable ID.  
**I4. Read/derive separation:** queries may update access counters but never silently revise source assertions.  
**I5. Rebuildability:** vector indices, graph projections and caches are derived from the canonical committed log/registry and have reconstruction manifests.  
**I6. Tenant/ACL enforcement before search and traversal:** an unauthorized node cannot become a traversal intermediary and must not leak through counts or path descriptions.  
**I7. Explicit snapshot correctness:** answers declare the canonical snapshot they read. A partially committed index cannot be advertised as fully current.  
**I8. Bounded propagation and compute:** depth, visited nodes, edge types, activation mass, wall time, token budget, retries and write queue size are explicit.  
**I9. Two-sided abstention:** measure both unsupported answers and unnecessary refusals.  
**I10. Empirical minimalism:** every complexity-increasing mechanism needs an ablation and a resource-normalized benefit.

# 6. High-level architecture

```text
TRUSTED/UNTRUSTED INPUTS
  conversation | docs | tool observations | agent actions
              |
      [schema and security validation]
              |
   [entity/event identity + atomic parsing]
              |
    [canonical transaction + outbox]
              |
    +-------------+-----------------------+
    |             |                       |
  events       provenance              source blobs
 (SQL)         and ACL (SQL)           (object store)
    |             |                       |
    +-------------------+-----------------+
                        |
          idempotent index workers
                        |
       +----------------+--------------+
       |                |              |
  feature views    text/vector      typed graph
  and binding      retrieval        projection
       |                |              |
       +---------+------+--------------+
                 |
               READ
     [identity/time/ACL query gate]
                 |
       [query seeds + latent cue]
                 |
   +-------------+-----------------+
   |             |                 |
 hybrid text   shared latent    graph spreading
   |             |                 |
   +-------------+-----------------+
                 |
  [union, provenance validation, dedup]
                 |
 [evidence-set sufficiency + status gate]
                 |
     [memory context / grounded reply]
                 |
      [traces only; no factual edits]
```

**Canonical transactions commit first.** Derived stores are not independently authoritative. The graph and vector retrieval are complementary channels, not redundant replicas of the same rows. Redis may accelerate expensive hot reads but is not an acceptable sole canonical evidence store.

## 6.1 Fast read and slower learning are separate mechanisms

A high-priority recent event goes into the canonical event ledger immediately; a worker computes derived views. Consolidation may later produce a validated semantic assertion linked to supporting episodes. Queries can prefer current event records or stable generalized assertions depending on the user's time scope and goal. No scheduled consolidation operation may delete the only copy of an event without a retention policy and an auditable deletion process.

## 6.2 Write fan-out is conditional, not an all-or-nothing neural dogma

A cheap deterministic normalizer extracts universal fields. Context, semantic, action/outcome and salience projections may execute in parallel *when their inputs are present*. An absent action sequence should produce `NOT_APPLICABLE` rather than hallucinated procedural coordinates. For a fair test, preserve a full fan-out experimental arm but also test selective feature computation for efficiency.

# 7. Encoding and write pipeline

The objective is a *reproducible causal record*, not a theatrically biological collection of microservices.

1. **Receive** input with a source descriptor, authenticated principal, namespace, event time (if supplied), and idempotency key.
2. **Validate trust boundaries:** authenticate producer, reject unsupported schema, tag external text as untrusted data, enforce retention policy, reject unauthorized writes.
3. **Identify event versus assertion:** exact duplicate? new episode? correction? claim conflicting with earlier assertion? add explicit relation; never rely on semantic-neighbor threshold alone.
4. **Atomize** into source-anchored propositions and typed links. For ambiguous extraction mark `UNRESOLVED` and preserve source text without asserting a definitive atomic interpretation.
5. **Commit** canonical event, atoms, provenance/ACL, and outbox event in one SQL transaction; version and hash content. Return durable commit ID, not a false “fully searchable” promise.
6. **Derive deterministic functional features:** timestamp/context features, entity identity, action sequences, task relevance and one of the experimental salience features.
7. **Embed and bind:** generate region projections, shared z, optional sparse/quantized variants; include model revisions.
8. **Build/update graph:** identity-constrained typed edges, provenance and lifecycle, no probabilistic merging on names.
9. **Publish only ready projections:** verify manifest counts/checksums and required indexes, then atomically advance a `ready_snapshot` pointer. If optional projection fails, declare which capabilities are degraded.
10. **Schedule possible consolidation** as a separate workflow with explicit support and write authorization.

### Identity outcomes at ingestion

| Input relationship to existing record | Correct behavior | Incorrect behavior |
|---|---|---|
| Byte-identical repeated event delivery | Idempotent same event ID | Store duplicate repeatedly |
| Similar text, new time/location | New event ID, relation if relevant | Suppress as “not novel” |
| New authoritative correction | New atomic assertion + `SUPERSEDES` | Edit original evidence in place |
| User says “I think X caused Y” | New `HYPOTHESIS` | Create verified `CAUSED_BY` edge |
| Approved source supersedes earlier rule | Versioned authority relationship | Prefer newest document by timestamp alone |
| Model extracts wrong entity | Mark unresolved/repair derived extraction | Merge two same-name people silently |

For the first implementation, extraction can use deterministic fixtures or a constrained extraction model. **The downstream decisions about approval, lifecycle and traversal must be deterministic even if text parsing is probabilistic.** Log parsing uncertainty.

# 8. Shared latent binding: the memory–query alignment problem

## 8.1 Why a “shared latent space” is not simply a VAE or DiT

Let a complete stored memory be `m=(content, context, atoms, relationships, observed action sequence, metadata)`. Let a query `q` be a partial cue such as “the deployment before the timeout.” The output of a memory encoder and the output of a cue encoder must be *comparable under a retrieval objective*, even though the cue omits parts of the original episode.

A shared latent space means we learn functions

\[
 z_m = \operatorname{norm}(E_m(m)), \qquad
 z_q = \operatorname{norm}(E_q(q, c)),
\]

such that relevant `(q,m)` pairs score higher than irrelevant pairs by a chosen similarity function. `E_m` and `E_q` may share a backbone or only a terminal projection; they need not be identical. **Shared target geometry is the essential property; identical weights are not.**

A diffusion transformer is a *network and training paradigm*: DiT denoises latent image representations; Stable Diffusion 3's MMDiT uses modality-specific weights with joint text–image information exchange while training a generative rectified flow [R6–R7]. This provides a useful architectural analogy—distinct streams can interact inside shared attention—but **does not provide a trained retrieval objective or prove that denoising text-memory cues is needed.**

A shared latent embedding space is the recommended main line of research; *actual iterative generative diffusion* is an exploratory arm requiring a separate hypothesis and higher cost budget.

## 8.2 Baseline embedding and fusion variants

- **B0, standard embedding:** one pretrained text embedding for event content + normalized metadata filters.
- **B1, late fusion:** separately retrieve semantic, temporal/contextual, and relational candidates; weighted rank fusion. This is not a learned CDZ.
- **B2, concatenation:** normalize and concatenate facet vectors with prespecified weights and a fixed metric. Rescale each facet to avoid one dominating by dimension.
- **B3, shared-backbone multi-head:** backbone encodes text, small heads project contextual/semantic/behavioral/salience views; MLP attention/linear projection creates memory z; cue encoder maps question into the same z-space.
- **B4, joint-attention binding:** treat facet representations as typed tokens with type IDs and cross-attention; produce pooled normalized z and train it for retrieval. Use *shared attention* inspired by multimodal fusion, not an untrained diffusion process.
- **B5, denoising cue-to-code:** deliberately corrupt or mask memory cues during training, train a conditional denoiser to predict an existing memory representation, and test iterative versus one-shot reconstruction. Optional and compute-capped.

### Distinguish two types of “denoising”

**Cue corruption training** masks, truncates or perturbs relevant question details and trains the encoder to locate the right episode. This can be done with ordinary supervised contrastive learning; no diffusion model is required.

**Diffusion/flow matching** trains a model to reverse a controlled noise process on continuous latent variables. It could help approximate a distribution of valid candidates given highly incomplete cues, but conditional generative uncertainty may amplify false recall; samples must be mapped to canonical event IDs and independently validated. No generated latent is a source document.

## 8.3 Mainline architecture candidate

```text
Memory m → shared text/context backbone ─┬→ E_context(m)
                                          ├→ E_semantic(m)
                                          ├→ E_action(m)
                                          └→ E_salience(m)
                                            ↓ typed-token fusion
                                      z_m ∈ R^d, normalized

Query q + scope/time/goals → cue encoder → z_q ∈ R^d, normalized
                                                ↓
                                contrastive alignment s(z_q,z_m)
                                                ↓
                              eligible candidate record IDs only
```

A query's `entity IDs`, time predicates, and ACL constraints should also feed *deterministic filtering*. Do not expect the latent space to reliably encode exact UUID equality, an authorization rule, or “yesterday” without explicit time resolution.

## 8.4 Train/test split and alignment challenges

**Positive pairs:** `(query, evidence-bearing event)` generated from a verified hidden world or human-judged question–event pairs.  
**Hard negatives:** same actor/action but different date/location; same named entity in different tenants; hypothesis versus verified observation; superseded version; similarly worded event with wrong numerical value.  
**Counterexamples:** sufficiently vague cues for which several memory events are equally plausible; do not force a single positive.  
**Noise:** partial clauses, typos, paraphrases, multilingual/code-mixed cues, incorrect contextual hint.

Train held-out identities and *scenario families*, not random paraphrases of the same event. Freeze encoder/version IDs. Log cue coverage and calibration. Use development data only for threshold choice.

# 9. Training objectives and experimental loss design

## 9.1 Do not hardcode a triple loss before examining individual objectives

The original proposal left hypernetwork training unspecified. This blueprint tests three losses **alone and in combinations**, rather than assuming the sum is universally better. Raw loss magnitudes are not comparable and “lowest numerical loss” across different objectives is not a meaningful model selection criterion. Choose by held-out retrieval/robustness and cost; report optimization curves only within identical objectives.

### L1 — Retrieval contrastive objective

For query `q`, one relevant memory `m+`, and an eligible set of negative examples `N(q)`:

\[
 L_{\mathrm{ret}}=-\log
 \frac{\exp(s(z_q,z_{m^+})/\tau)}
 {\exp(s(z_q,z_{m^+})/\tau)+\sum_{m^-\in N(q)}\exp(s(z_q,z_{m^-})/\tau)}.
\]

If multiple memory units are acceptable, use a multi-positive formulation and do not mark alternative valid evidence as negative. Temperature `τ` and sampling mixture are tuned on development only. In-batch negatives require screening for false negatives (same episode, genuinely applicable alternatives).

### L2 — Representation reconstruction objective

For facet features `h_r` and decoder `D_r(z)`:

\[
 L_{\mathrm{rec}} =\sum_{r=1}^{R} \lambda_r
 \|D_r(z_m)-\operatorname{stopgrad}(h_r)\|_2^2.
\]

Use calibrated scales for facets. Reconstruction can preserve information that is *irrelevant* for retrieval; it is not itself evidence that query alignment works. Evaluate exact retrieved-facet substitution as a separate control.

### L3 — Controlled episode separation objective

Given one episode `m`, a positive augmentation `m+` of the *same* episode, and a deliberately confusable different episode `m-`:

\[
 L_{\mathrm{sep}}=\max\{0,\mu+s(z_m,z_{m^-})-s(z_m,z_{m^+})\}.
\]

Margin `μ` is a development hyperparameter. This is a ranking separation *between identity-labeled episodes*, not universal orthogonalization of all semantically related experiences. The model must retain closeness for same-event paraphrases and generalizable schema relations.

### Alternative regularizers (exploratory)

`L_sparse = ||z||_1` is meaningful only when constrained against trivial collapse, e.g. appropriate reconstruction/retrieval signal and normalization. Other options: top-k activations, sparsemax, contrastive whitening, covariance regularization, binary hashing with a suitable objective. Avoid claiming `c → c^k` without deriving and validating the actual projection law.

## 9.2 Loss factorial experiment

| Arm | Retrieval | Reconstruction | Separation | Interpretation |
|---|---:|---:|---:|---|
| T0 | — | — | — | Frozen encoder baseline |
| T1 | ✓ | — | — | Direct retrieval alignment |
| T2 | — | ✓ | — | Information retention alone |
| T3 | — | — | ✓ | Discrimination alone |
| T4 | ✓ | ✓ | — | Alignment + retention |
| T5 | ✓ | — | ✓ | Alignment + discrimination |
| T6 | — | ✓ | ✓ | Retention + discrimination |
| T7 | ✓ | ✓ | ✓ | Full multi-objective |

All arms must use comparable data, backbone capacity, training exposure and inference budget; reconstruction/separation-only arms may lack meaningful query training, and this is a **diagnostic result**, not grounds to remove their failures from the report. Optional loss-weight sweeps on development include `λ_rec` and `λ_sep` in `{0,0.05,0.2,1}` **after normalizing the loss scales**; these are illustrative search points, not recommended true weights. Also compare sequential training, e.g. contrastive warm-start followed by modest reconstruction/separation, because gradients can conflict.

## 9.3 Gradient conflict and representation collapse

Log gradient cosine between objectives during training and the effective rank of the learned code. Reconstruction might improve decodability but hurt retrieval discrimination; separation might overfit episode IDs and break generalization; contrastive objectives may collapse different valid events when queries underspecify identity. Test systematic query ambiguity and do not train on held-out test scenarios.

## 9.4 Primary selection criterion

Choose the lightest variant on the Pareto frontier of `CorrectEvidence@K` / `CompleteSet@K`, false-association rate, partial-cue recall, false answer/false abstention rates, p95 query time, training compute and index memory. Do **not** select the winner by whichever mixture has the numerically smallest sum of dissimilar loss terms.

# 10. Pattern separation: theory, controlled experiment, new calculations

## 10.1 Separate *identity discrimination* from semantic retrieval

The earlier architecture sought almost orthogonal representations for events with similar content. This can prevent collisions, but if an incomplete query resembles only their shared content, hard orthogonalization can make both harder to find. Use a two-level representation when necessary:

- **Semantic/contextual projection** captures shared concepts, useful for discovering candidates.
- **Episode identity projection** captures discriminating time, actor, sequence, and source-specific details.

Let

\[
 s(q,m)=\lambda\,s_{\mathrm{semantic}}(q,m)
 +(1-\lambda)\,s_{\mathrm{episode}}(q,m)
\]

or fuse ranks rather than scores. `λ` may be a deterministic function of *observable* query features (e.g. explicit date/entity vs general thematic request), chosen/tuned on development. The query must not silently infer a missing event identity.

## 10.2 The sparse overlap derivation

For independently sampled binary supports with `d` coordinates and exactly `k` active positions, the expected intersection size is `k²/d`; the expected intersection as a fraction of active coordinates is `k/d`. For `d=2048, k=41`, this is about **0.0200**, or 2%. This calculation applies to **independent** supports. It does *not* imply that correlated vectors, after a common random projection and top-k, become independent.

For correlated approximately Gaussian coordinates `X_i, Y_i` with correlation `ρ`, top-k selection approximates a common upper-tail threshold `u` with `P(X>u)=p=k/d`. Then

\[
 E[\mathrm{overlap\ fraction}]\ \approx\
 \frac{P(X>u,Y>u)}{p},
\]

which **depends on `ρ`**, not just `p`. Positive correlation increases shared active positions. Therefore the old illustrative assertion “0.7 cosine becomes 0.05 cosine” is **not a general theorem**. Nor is `sim_out≈sim_in^k` established by the sparse projection implementation.

## 10.3 Re-test: toy Monte Carlo (computed for this document)

The following is an actual small **synthetic simulation**, not a memory-benchmark result. With fixed RNG seed `20261019`, generate 1,200 pairs of `d=2048` standard Gaussian vectors, impose coordinate correlation `ρ` by `Y=ρX+sqrt(1-ρ²)ε`, and retain the highest `k` coordinates in each vector. Measure `(number of shared active indices)/k`. This assesses **support overlap**, not cosine similarity of the retained weighted vectors or retrieval Recall@K.

| Input correlation `ρ` | Mean support overlap, `k=41` (~2%) | Mean support overlap, `k=205` (~10%) |
|---:|---:|---:|
| 0.0 | 0.0200 | 0.0996 |
| 0.3 | 0.0836 | 0.2163 |
| 0.7 | 0.3153 | 0.4698 |
| 0.9 | 0.5775 | 0.6875 |

**Interpretation:** sparsity strongly changes the overlap geometry, but significant overlap remains for strongly correlated input. A result of 0.05 is not justified by the stated mechanism. Binary support-overlap ratios and post-projection cosine are distinct metrics. A learned projection may behave differently and must be tested independently. Standard error for the 2%-sparse `ρ=0.7` estimate was about `0.0019` under this synthetic sampling; these are not confidence intervals for real text embeddings.

**Reproducibility sketch:** NumPy `default_rng(20261019)`; for each `k in (41,205)` and `ρ in (0,.3,.7,.9)`, generate 1200 pairs of 2048-dimensional Gaussian vectors as above; `argpartition` to select each top-k support; calculate pairwise intersection fraction; average. Use the same seed and iteration order if reproducing the exact numbers. Preserve source and fixed output in experiment code, and test across multiple seeds before making theoretical claims.

### Additional toy stress test: weak cue versus a highly similar competing episode

A second seeded synthetic stress test specifically evaluates the feared trade-off. Draw 3,000 independent target memories as `d=2048` Gaussian vectors; for each target construct a *different* episode with coordinate correlation `0.9`. Construct a partially informative query with correlation `ρ_q` to the correct target and compare the target against its correlated competitor. A dense baseline chooses the higher cosine; the sparse-code baseline chooses whichever memory has the greater overlap with the query's top-k binary support (ties are **not** credited as correct). Use NumPy generator seed `73319` and sample in the order specified. This is not a trained retrieval model; it isolates geometric information loss and therefore must not be generalized to real embeddings without the later task experiment.

| Query-to-target correlation | Dense cosine correct | 2%-sparse strict correct | 2%-sparse ties | 10%-sparse strict correct | 10%-sparse ties |
|---:|---:|---:|---:|---:|---:|
| 0.20 | 98.6% | 37.2% | 35.3% | 60.7% | 9.0% |
| 0.35 | 100.0% | 49.1% | 26.0% | 76.5% | 6.3% |
| 0.60 | 100.0% | 70.6% | 14.5% | 94.7% | 1.7% |

**What this demonstrates:** a *particular* aggressive binary top-k support representation can throw away features that disambiguate highly similar alternatives even while it separates representations. This does not prove sparse learned codes are inferior in general; it motivates measuring **query-to-target alignment** and **top-1 ambiguity/ties** alongside inter-memory separation. It also shows why blindly maximizing orthogonality is not a complete design objective. Report the comparison's representational mismatch openly: dense cosine retains vector magnitudes and directions whereas binary support overlap retains only positions of top activations.

## 10.4 Johnson–Lindenstrauss does not justify an “optimal 40 dimensions” claim

The JL lemma bounds distortion for random embeddings of finite point sets with dimensionality scaling as `O(log N / ε²)` under suitable constructions and constants. It is not a guarantee of event identity recovery, near-orthogonal outputs, or 2% top-k sparsity performance. It cannot set a useful absolute dimension for a million memory events without the distortion tolerance, similarity structure and retrieval error budget.

## 10.5 Discrimination–generalization frontier experiments

- Sweep dense dimensions `d ∈ {256,512,1024,2048}`; sparsity `p ∈ {1%,2%,5%,10%,100%}`; projection type `random / learned / identity`.
- Sweep separation margin and semantic-vs-episodic weighting only on development split.
- Generate adversarially similar events with exactly one varying field; test retrieving the correct event when that field is present in the cue and safe abstention when absent.
- Measure collision rate, conditional nearest-neighbor margins, same-episode recall, different-episode confusion, generalization to unseen actors/locations, and recall after time-dependent updates.
- Compare ANN recall against exhaustive exact search to isolate approximation failure from representation failure.

A sparse projection is retained **only** if it improves the relevant interference metric without a prespecified unacceptable loss in partial-cue recall or excessive index overhead.

# 11. Pattern completion via graph activation diffusion

## 11.1 The proposed physics analogy, precisely delimited

A drop in water generates a propagating disturbance with a diminishing amplitude. As inspiration for memory, a partial cue might activate certain atoms, which propagate relevance along evidence-grounded connections. This is a powerful analogy, but graph activation is **not literally a physical wave**. Different mathematical operations capture different meanings:

- **Decaying breadth-first expansion:** traverses edges with per-hop attenuation; path-local, inexpensive, easy to explain.
- **Random walk with restart / Personalized PageRank (PPR):** repeatedly moves activation according to transition probabilities but regularly restarts at original cue nodes; steady-state relevance near seeds.
- **Heat-kernel diffusion:** spreads a distribution according to a graph diffusion operator and a scale/time parameter; emphasizes locality at short diffusion times.
- **Recurrent associative/Hopfield retrieval:** updates a state under an energy/attention rule; may retrieve stored attractors but is a materially different algorithm, not implicitly reproduced by PPR.

All four can be evaluated. **The main research alternative to nearest-neighbor search is PPR seeded by explicitly grounded query evidence, not arbitrary unconstrained traversal.** PPR is not novel by itself: it is used in HippoRAG-family systems [R9], and its sourced variant is supported by Neo4j's graph algorithms [R13]. The novelty must be in the *atomic provenance + query-seed + evidence-constrained integration* and in demonstrated gains.

## 11.2 The memory graph

Let `G=(V,E)` have typed nodes:

- `Event`: original occurrence; immutable identity.
- `Atom`: assertion about event/entity with epistemic state.
- `Entity`: person, project, service, location, object, process; tenant-scoped ID.
- `Source`: immutable document version and span, message or authenticated observation.
- `EpisodeCluster` or `DerivedSchema`: optional derived abstractions with supporting membership edges.

Typed edges include `MENTIONS`, `PART_OF_EVENT`, `OBSERVED_IN`, `OCCURRED_BEFORE`, `RELATED_TO`, `REQUIRES`, `CONTRADICTS`, `SUPERSEDES`, `DERIVED_FROM`, `HYPOTHESIZES_CAUSE`, and `VERIFIED_CAUSE`. An edge carries `edge_id`, source handle, scope, temporal interval, producer version, epistemic status, and validity. Do not treat `HYPOTHESIZES_CAUSE` as interchangeable with `VERIFIED_CAUSE`.

### Important distinction: graph projection versus graph truth

Graph databases organize evidence-linked relationships; the canonical atom and source registry validates each path. Low-confidence inferred edges may be stored in an experimental projection, but are filtered or tagged and **cannot create factual authority**. Nodes with identical natural-language names remain separate absent verified identity resolution. A graph projection can be rebuilt from its source manifest.

## 11.3 Seed activation

The difficult step is getting from the cue to trustworthy **seed nodes**. Graph diffusion cannot find a target if the cue has no anchors and no mechanism proposes them.

Produce seeds using a controlled union of:

1. Exact identifiers, entity IDs, dates, and scoped structured matches.
2. BM25 lexical candidates and their source-grounded atom/entity links.
3. Dense/shared-latent semantic top-k candidates, mapped to canonical record IDs.
4. Optional task goal and recent relevant event context, but only when scope and time are explicit.

Assign an initial seed distribution `s(v) ≥ 0` with `sum_v s(v)=1` after eligibility filtering. Seed weights are **retrieval proposal scores**, not factual probabilities. Query seeds must retain which retrieval channel proposed them and the model/source version. Test seed quality separately, including the failure mode of seeding only the wrong same-name entity.

## 11.4 Personalized PageRank as controlled activation

Let `W` be nonnegative allowed edge weights, `P` a row-stochastic transition matrix after filtering and normalization, and `s` the seed vector. Write activation as a column vector:

\[
 a^{(t+1)}=(1-\alpha)s + \alpha P^{\top}a^{(t)}, \qquad 0\leq\alpha<1.
\]

At equilibrium (when it exists),

\[
 a^*=(1-\alpha)(I-\alpha P^\top)^{-1}s.
\]

**Intuition:** each step passes a fraction `α` of current activation to neighbors according to edge strengths and returns `1−α` to the original evidence-based seeds. A far-away hub cannot steal all relevance if restarts and traversal budgets constrain propagation. A query with weak seed evidence still cannot create certainty from a high stationary score.

**Starting development values (not optimized facts):** `α ∈ {0.5,0.7,0.85}`, at most `2–4` typed hops for explicit path outputs, at most `1k/5k/20k` visited nodes depending on corpus scale, max `20–40` power iterations or tolerance, and a fixed per-query time budget. Cap seed count, fan-out per edge class, and eligible graph size. Tune on development only. If high-degree nodes repeatedly dominate, use type-aware normalization, degree correction, edge-specific capping, or bounded personalized push, and report exactly what changed.

### Important mathematical detail

`α` is the fraction propagated forward; `1−α` is the restart fraction in the equation above. Do not interchange this convention when comparing Neo4j/PageRank implementations. For dangling nodes choose and declare a policy (restart to seeds or redistribute); otherwise the probability mass may leak and the results are not comparable.

## 11.5 Heat-kernel alternative

For a random-walk generator `L_rw = I−P^T`, an illustrative continuous-time propagation is

\[
 a(t)=\exp(-tL_{rw})s = \exp(t(P^T-I))s.
\]

A small `t` keeps activation close to original cues, while larger `t` allows broader spreading. The heat-kernel PageRank literature supplies a principled mathematical basis [R14]. But `t` is a mathematical scale, not physical seconds or neural oscillation frequency. On directed typed graphs the generator and normalization details must be carefully specified.

Compare PPR and heat kernel under the same seed, eligible subgraph, visited-node and wall-clock budgets. A mathematically elegant diffusion process is not necessarily a better retriever.

## 11.6 Path-score alternative and explanation fidelity

For a particular path `π=(v0,...,vh)` with edge-normalized probabilities `p_e` and a decay factor `γ`, an *explanatory path contribution* may be scored

\[
 C(\pi)=s(v_0)\,\gamma^{h}\prod_{e\in\pi}p_e.
\]

This is a diagnostic **path score**, not automatically equivalent to full PPR, which aggregates many walks. A high path contribution does not certify that a causal relationship is true. Every returned explanatory path must resolve to edge provenance and pass authorization/time checks.

## 11.7 Preventing false association

A graph node like `SERVICE-PAYMENTS` or `PERSON-17` may be connected to thousands of events. Naive diffusion treats high degree as evidence and can return irrelevant memory clusters. Explicit protections:

- Filter tenant/ACL and applicable time scope **before constructing the propagation graph**.
- Restrict traversable edge types per question: a chronology question differs from a causal one.
- Restrict `INFERRED` or `HYPOTHESIS` edges from being represented as verified chains.
- Penalize/cap noisy `MENTIONS` hubs without blindly deleting valuable high-degree nodes.
- Do not traverse through revoked/deleted sources; invalidate derived paths after updates.
- Require candidate **source recovery**: activation finds record IDs, then canonical source spans are fetched.
- Verify the exact question-relevant atomic assertions after propagation and before answering.
- Detect and abstain on multiple incompatible high-scoring event candidates when the cue omits disambiguating context.

## 11.8 Worked path example

Cue: “Which rollback followed the deployment that introduced timeout `E-503`?”

1. Exact code `E-503` seeds one observed incident atom.
2. A supported `OBSERVED_IN` edge points to incident `INC-32`.
3. `OCCURRED_AFTER` / `SAME_RELEASE` edges connect to deployment `DEP-19`.
4. An authenticated operations log contains event `ROLLBACK-20` with a verified temporal relation to `DEP-19`.
5. Activation proposes `ROLLBACK-20` as a candidate.
6. Canonical verification checks ID, time order, same service/release, supporting log and ACL.
7. Result returns a source-linked answer; if the edge was only `HYPOTHESIZES_CAUSE`, the answer says the relationship is not established.

The *value* of diffusion is connecting evidence that a single embedding retrieval might not co-locate. Its failure mode is indiscriminately treating associative paths as logical proof.

## 11.9 Graph-completion experimental arms

| Arm | Candidate mechanism | Isolates |
|---|---|---|
| G0 | Exact/BM25 + dense ANN | Conventional baseline |
| G1 | G0 + bounded BFS | Benefits of neighborhood expansion |
| G2 | G0 + damped path scoring | Simple physics-inspired attenuation |
| G3 | G0 + seeded PPR | Multi-path stochastic activation |
| G4 | G0 + heat-kernel propagation | Diffusion-scale alternative |
| G5 | Shared-latent cue + PPR | Whether better seeds unlock better graph recall |
| G6 | Pure graph seeds and diffusion (diagnostic) | How often semantic retrieval is essential |
| G7 | Optional associative recurrent model | Whether learned completion beats graph diffusion |

Keep graph construction, ACL, evidence budget, and source text comparable; graph-native baselines such as HippoRAG 2 should be permitted their official implementations under a separately labeled **native system comparison**. Record edge construction cost, not just query latency.

# 12. CDZ: binding as address versus reconstructive process

Two interpretations are retained deliberately, with no predetermined winner.

## CDZ-A: Address-based binding (preferred implementation control)

`z_m` indexes the *identity and relations* of a canonical event; retrieving `z_m` yields the original exact event/atom/facet records. The code acts as an address or candidate-retrieval key. Any recovered emotional, procedural, temporal or semantic attribute is **read from stored evidence-backed views**. Benefits: provenance fidelity, no lossy generation on the critical path, direct debugging. Disadvantage: still needs stored facets and a metadata/graph lookup; might add no benefit over multi-view hybrid retrieval.

## CDZ-B: Reconstruction-based binding

`z_m` is deliberately compressed and decoders predict a multi-facet representation:

\[
 z_m=C(h_1,...,h_R),\qquad \widehat{h}_r=D_r(z_m).
\]

To make the original flow well typed, define **the full representation chain**, e.g. `h_r(256) → z_dense(512) → z_sparse(2048)`. A decoder trained on `z_dense` cannot be handed `z_sparse` without an explicit inverse or retrained decoder. Choose one: (i) index dense z and decode dense z; (ii) sparse z with a separate `D_sparse`; or (iii) look up stored z_dense by record ID after sparse ANN. These are different experimental systems.

**Decoder output is derived hypothesis, not canonical fact.** If it predicts “Zone B” while source data says “Zone C,” exact source wins and the reconstruction is counted as an error. A generative textual decoder is especially risky; initially decode only continuous facet representations and score feature fidelity.

## CDZ-C: Hybrid address plus reconstruction

Use reconstruction to propose likely missing facets or rank secondary candidates, but retrieve and validate the source record before returning facts. This tests whether latent reconstruction offers *candidate recall benefits* without allowing source mutation or hallucinated citations.

### Tests

- Exact facet read versus reconstruction at fixed candidate IDs.
- Reconstruction MSE/cosine per facet **and** preservation of categorical entities, timestamps, quantities and source identity.
- Downstream retrieval/answer benefit rather than reconstruction-only score.
- Compression ratio, inference latency, failure under corrupted or partial cues.
- Calibration when decoder encounters an out-of-distribution episode.
- Reconstruction hallucination/false-association frequency.

**Decision rule:** if CDZ-B/C does not improve downstream retrieval or answer quality at acceptable fidelity/cost, keep CDZ-A only. Cross-attention itself must beat simple concatenation or late fusion before being retained.

# 13. Emotion and salience: original hypothesis versus interpretable alternatives

The original research pursued a monoamine-inspired vector inspired by Lövheim's emotion cube. We preserve its calculation as a deliberately *hypothetical model of text-derived signals* rather than implying neurotransmitters were measured.

## 13.1 S1 — Monoamine-proxy experimental arm

Let

\[
 E_{\mathrm{proxy}}(x)=(\widehat{NE},\widehat{DA},\widehat{5HT}),
\]

where these names denote **NLP proxies**, not chemical concentrations. `NE` is inferred urgency/arousal, `DA` predicted reward/outcome polarity, and `5HT` inferred social/relational context. Proposed gain:

\[
 g_{mono}(x)=1+\alpha\widehat{NE}
 +\beta|\widehat{DA}|+\gamma(1-\widehat{5HT}).
\]

The historical proposed starting weights `(.5,.3,.2)` are retained *only as one preregistered initial configuration*, not evidence-backed constants. Thresholding to eight Lövheim corners is a secondary descriptive experiment, not a diagnosis of a user's emotional state. Measure robustness across languages and neutral technical statements; verify that formula output is finite and bounded before use.

## 13.2 S2 — Task/observability derived arm

Define an interpretable salience feature vector

\[
 E_{task}(x)=\big[\text{urgency},\text{task relevance},\text{novelty},
 \text{verified consequence},\text{explicit user priority},\text{actionability}\big].
\]

Use deterministic, auditable rules with evidence inputs. Example: an authenticated production-outage observation receives a higher `verified_consequence` than a speculative complaint; an explicit user reminder can increase task priority but not factual authority. Avoid treating exclamation count as a sufficient measure of importance.

## 13.3 S0 — No salience weighting

Run all models with salience disabled. This is essential because salience can degrade accuracy by displacing mundane but necessary evidence.

## 13.4 Controlled experiment

Use the *same* underlying candidate set and record budget for S0/S1/S2; compare reranking and retention policy separately. Metrics: right-event recall, fact correctness, stable performance for emotionally neutral engineering tasks, excessive-priority rate, group/language fairness, over-retention of noisy dramatic events, cost, privacy risk, and downstream utility. Never let high salience bypass approval, ACL, validity or explicit correction.

# 14. Deterministic functional operators and gated policies

The initial proposal used separately trained 50–100M parameter hypernetworks to generate dynamic per-memory formulas. This is **removed from the core architecture**. The first experiment uses fixed interpretable functions, typed features, bounded configurable parameters and deterministic policies; small learned projections exist only where indispensable for the *representation learning experiment*.

### Operator table

| Functional operator | Input | Deterministic output | Gate |
|---|---|---|---|
| Contextual binder | authenticated event ID, time, entity, location | context keys, time predicates, known episode grouping | require source-anchored identity |
| Semantic view | canonical text + language | normalized embedding, lexical tokens | source content available |
| Pattern separator | candidate episode IDs and distinguishing fields | discrimination features; optional learned sparse code | preserve distinct event ID on high similarity |
| Procedure learner | observed action/outcome sequence | typed action chain, observed result | no procedure without verified sequence |
| Salience modulator | S0/S1/S2 feature set | bounded numeric priority feature | never changes authority/eligibility |
| Goal/context selector | task goal, cue, scope/as-of | allowed relation types and ranking context | ACL/time must pass first |
| Consolidation gate | repeated independent validated events | candidate generalized assertion | explicit evidence and approval required |
| Evidence gate | retrieved record IDs, source spans, policy | output status + missing prerequisites | hard constraints, not latent confidence |

### Why deterministic does not mean non-learning

Policies decide *what is allowed*; learned encoders may decide *which eligible items are relevant*. Hardcoded scoring rules are testable and reproducible but not guaranteed accurate. The experiment should include a small learned gating network arm only after fixed rules establish a trustworthy control. Avoid hand-coding ad hoc formulas that indirectly learn the test set.

### Representative policy examples

- If an event ID is new and temporal details differ, create a new episode even when semantic cosine is >0.99.
- If a query requests current policy, restrict to applicable approved policy versions *using the policy-specific as-of basis*; if conflict unresolved, emit `CONFLICT`.
- If a claim is `HYPOTHESIS`, it may be surfaced as such but cannot be rewritten as `DIRECT_OBSERVATION`.
- If any referenced record is unauthorized, exclude it **before candidate ranking and graph traversal**.
- If multiple events match but a defining field is absent, return an ambiguous result or request a disambiguating field rather than arbitrarily completing to one.
- If a derived index is behind its declared snapshot, either use a verified older consistent snapshot (when permitted) or return `VERIFICATION_UNAVAILABLE` for freshness-dependent questions.

# 15. Temporal identity, contradictions, corrections, and provenance

## 15.1 Three orthogonal kinds of state

**Lifecycle state** describes how the record moves through the infrastructure:

`RECEIVED → VALIDATED → COMMITTED → INDEX_PENDING → READY`

Exception transitions: `VALIDATION_REJECTED`, `INDEX_DEGRADED`, `REINDEX_PENDING`, `REVOKED`, `TOMBSTONED`. A tombstone means “excluded from serving and scheduled for physical purge according to retention and legal constraints,” not “all replicas definitely erased at this instant.” Maintain independent per-index status rather than pretending that `READY` is an atomic property across three databases.

**Epistemic state** describes *what is being asserted and how reliable the assertion is*: `USER_REPORTED`, `DIRECT_OBSERVATION`, `HYPOTHESIS`, `MODEL_INFERENCE`, `DOCUMENT_ASSERTION`, `DERIVED_AGGREGATE`, `RETRACTED`. Do not confuse this with the lifecycle state. A `READY` record may still be an unverified hypothesis.

**Temporal/applicability state** describes whether a record applies for a particular as-of query: `CURRENT`, `HISTORICAL`, `SUPERSEDED`, `FUTURE`, `EXPIRED`, `UNKNOWN`, or `CONFLICT` *relative to the target domain rule*. A superseded policy may be the correct historical evidence for a query about the earlier period.

## 15.2 Provenance as a first-class contract

Each atom is backed by at least one source span or authenticated observation; each edge is backed by a source or explicitly declared inferred transformation. An answer claim should retain a path:

`answer_claim → evidence_atom → event/source_span → immutable source_version/hash`.

For derived abstractions, add `derived_from_atom_ids`, algorithm/model version, transformation timestamp and validation outcome. For graph diffusion, return edge-by-edge provenance as a *candidate explanation*, not as a fabricated proof. If any required link cannot be resolved or permitted, the supporting chain is invalid.

## 15.3 Names, identities, same-event links, and collision resistance

Identity must use namespace/tenant + stable source identifier, or a governed composite identity policy. Display names are aliases. Two same-name merchants or persons must not merge because of high cosine or shared lexical features. A deliberate identity resolution process can create `SAME_AS` links with explicit review/verification, not overwrite IDs. Ambiguous names produce multiple candidates until scope resolves them.

## 15.4 Revision versus new episode

For each proposed assertion, deterministic checks decide among `new_occurrence`, `same_event_additional_evidence`, `duplicate_delivery`, `user_correction`, `authoritative_revision`, `contradictory_evidence`, or `derived_claim`. These classes have different data behaviors. An event about today's parking does not supersede yesterday's; a correction of yesterday's stated zone does.

## 15.5 Bitemporal reasoning and user questions

Use valid time and system-recorded time separately. A late-arriving observation can have an earlier event time. Queries like “What did we know last Tuesday?” use a *knowledge-at-time* basis; “What happened last Tuesday?” uses *event-time* basis; “Which policy applied to the transaction?” uses its domain-declared applicability rule. Store explicit timezone and resolve “yesterday” using the query's evaluation clock, not the current machine wall clock in a replayed benchmark.

## 15.6 Deletion, revocation, and retention

Revocation must close the serving path rapidly and trigger invalidation of vector payloads, graph nodes/edges, caches, summaries, consolidated representations, backup retention policy and query traces as allowed. Derived information may reveal deleted content indirectly; every derived artifact must maintain source lineage so that revocations can find affected downstream objects. Redis TTL is **not** a complete deletion strategy. A public benchmark should include deletion propagating during index outages.

# 16. Complementary learning systems and consolidation

**Fast episodic lane:** append event/atom and source immediately with high fidelity. Distinct episodes remain distinct even when semantically redundant.

**Slow semantic lane:** periodically propose generalizations from a set of sufficiently independent, compatible and authorized events. Proposals are derived hypotheses until their evidence and scope are validated; they never retroactively modify the source events.

### Example

Source events record five authenticated incidents where a retry parameter correlated with elevated latency. A consolidation process may propose: “Changing this parameter frequently coincided with latency regressions in these five deployments.” It must not upgrade this to “the parameter caused outages” without a causal design or stronger evidence.

### Candidate algorithm

1. Select candidate episodes by evidence-supported common entities/relations and stated aggregation window.
2. Group duplicates to avoid counting one copied report as multiple independent observations.
3. Generate candidate abstraction with supporting event IDs and validity scope.
4. Check contradictions, sampling and evidence sufficiency, and detect whether the claim generalizes beyond observed settings.
5. Gate publication through deterministic thresholds and/or explicit human review, with an audit record.
6. Index semantic abstraction in the slow store and preserve links to all source events.
7. Recompute/invalidate if a supporting event is revoked or corrected.

### Experimental variants

- C0: episodic retrieval only.
- C1: periodic deterministic aggregates; no generative model.
- C2: evidence-constrained generated summaries, reviewed and source-linked.
- C3: slow learned representation updates (exploratory, separate from canonical source).

Track memory growth, preservation of exceptional cases, false generalization, source diversity, correction propagation, retrievability of rare episodes, and consistency under replay. A consolidation system that increases average answer accuracy but hides outlier events may be inappropriate for operational reliability.

# 17. Read pipeline, evidence verification, and abstention

## 17.1 Read pipeline

```text
User cue + authenticated principal + task goal + as-of context
     |
[deterministic scope/time/policy/ACL gate]
     |
[cue normalization, lexical tokens, exact IDs, embedding]
     |
[candidate union]
  ├─ exact structured lookup
  ├─ BM25/dense hybrid
  ├─ shared latent query-memory similarity
  └─ seeded typed graph activation/diffusion
     |
[eligibility recheck → dedup → rerank → evidence-slot assembly]
     |
[verify source lineage, contradictions, time, sufficiency]
     |
[SUPPORTED | PARTIALLY_SUPPORTED | CONFLICT |
 NOT_ESTABLISHED | VERIFICATION_UNAVAILABLE]
     |
[answer with citations OR qualified partial answer / abstention]
```

Each candidate carries `event_id/atom_id`, `source_id`, source version/span, relationship path (if any), inference model revision, index snapshot, channel and ranking signals. Similarity scores are *not* probabilities of correctness. Prevent a partial match from becoming a fully supported answer by checking **required evidence slots**, not simply checking that at least one memory was returned.

## 17.2 Borrowed evidence statuses and abstention discipline

The companion benchmark protocol supplies five **answer-level** statuses:

- `SUPPORTED`: all material claims have sufficient eligible evidence.
- `PARTIALLY_SUPPORTED`: some material claims supported, clearly indicate unknown fields.
- `CONFLICT`: authoritative evidence conflicts, unresolved at current scope/time.
- `NOT_ESTABLISHED`: no sufficient authorized evidence in the supplied snapshot.
- `VERIFICATION_UNAVAILABLE`: required live/derived verification cannot currently be completed (outage, degraded index, unauthorized tool, stale observation).

For internal labeling, distinguish `NO_KNOWN_SUPPORT`, `UNINDEXED_SOURCE`, `UNAUTHORIZED_SOURCE`, `MISSING_CASE_INPUT`, and `REQUIRED_LIVE_CHECK_UNAVAILABLE`. Never reveal even the existence of an unauthorized source when policy forbids that disclosure. An absent indexed result and a fact that never existed are not equivalent.

### Decision example

Query: “Did the Tuesday rollback definitely fix the production problem?”

- Event source: rollback was performed.
- Observation: the incident error rate fell shortly afterward.
- Hypothesis: rollback caused the improvement.
- No controlled causal confirmation.

A correct answer may be `PARTIALLY_SUPPORTED`: “The rollback happened and the error rate decreased afterward, but causation is not established from the stored evidence.” Graph activation helps *find* events; it does not license causal certainty.

## 17.3 Confidence and selective risk

If confidence is predicted, define precisely:

\[
 \Pr(\text{all material answer claims are correct and supported}\mid
 \text{observed retrieval/evidence features}).
\]

Calibrate on a separate dataset split and assess Brier score, log loss, ECE, and risk–coverage curves. Use evidence completeness, source validity, disagreement, retrieval consensus, and index health as input features. **LLM self-reported confidence, cosine similarity, PPR activation and rank-fusion score are not calibrated correctness probabilities.** Numerical confidence need not be shown to the user if it offers no decision value.

## 17.4 Two-sided abstention metrics

Measure both `False-Answer Rate` on insufficient/conflicted cases **and** `False-Abstention Rate` on sufficiently supported cases. Report selective coverage, selective risk, AURC, missing-reason classification accuracy, partial-answer utility, and how often the response asks for the correct missing fact. A system that always refuses must not score as a superior trustworthy memory.

## 17.5 Evidence sufficiency versus retrieval diversity

For a question requiring multiple independent pieces of evidence, score `SlotCoverage@K` and `CompleteSet@K`. A candidate set with many relevant but redundant passages may fail to include a required exception. Support multiple acceptable minimal evidence sets, not one overfitted gold chunk ID. The evaluation should compare normalized source spans rather than proprietary chunk identifiers, preserving genuine method differences.

# 18. Storage design: polyglot stores, replication, and sharding

## 18.1 Fundamental distinction

**Polyglot persistence** uses different engines for different representations; **replication** creates additional copies of a logical dataset; **sharding** partitions a dataset by key/range; **indexing** creates derived searchable structures. Using SQLite, Redis, a vector engine, and Neo4j is *not by itself replication or sharding*. The stores hold distinct data models, so cross-store writes require consistency rules.

## 18.2 Recommended research deployment

| Component | Role | Canonical? | Replication/sharding approach |
|---|---|---|---|
| SQLite (pilot) | event/atom/source registry, provenance, ACL, outbox, snapshot manifests | **Yes** within single-writer pilot | WAL, backups, deliberate app-level partitioning only |
| Object/blob store | original source bytes and signed immutable versions | **Yes** for raw source content | storage backend versioning/replication and checksums |
| Redis | hot cache, recent episodic retrieval cache, rate limit/queues when appropriate | **No** | optional Redis replication/Cluster by workload |
| BM25/full-text | lexical derived index, perhaps SQLite FTS5 or search service | No | rebuilt from canonical event/source log |
| Qdrant or alternative vector index | semantic, facet, shared binding vectors | No | collections/tenant filters; provider-supported replicas/shards if justified |
| Neo4j / typed adjacency service | derived atom/event/entity graph and traversal | No for evidence truth | chosen deployment semantics; snapshot/rebuild from event/edge log |
| Tracing system | run metrics, failures, access audit | Audit logs have own integrity requirements | secured retention, sampling and access controls |

**Pilot simplification:** a single SQLite WAL file + blob directory + in-process exact/BM25/vector indexes + an in-process typed graph can produce a valid controlled experiment before introducing distributed infrastructure. This isolates algorithmic value. Add Redis, Qdrant and Neo4j in a *separate operational scalability track*, rather than confusing algorithm improvements with different database performance.

**Production concern:** SQLite permits concurrent readers but only one writer at a time in WAL mode, and WAL is unsuitable for normal concurrent access across a network filesystem [R16]. If the workload requires many concurrent independent writers, multi-region transactional control, or mature online replication, a server database (e.g. PostgreSQL with an explicit high-availability design) may be more appropriate as the canonical registry. Using SQLite does not automatically grant a distributed transaction protocol.

## 18.3 Redis replication is not authoritative durability

Redis replication is asynchronous by default. Redis Cluster shards across hash slots and can provide availability, but under some failures acknowledged writes can be lost; it is **not strongly consistent** [R17–R18]. Therefore Redis holds only rebuildable caches or appropriately managed operational queue state, and critical memory commits are durably acknowledged by the canonical transaction first. Never use stale cached ACLs to authorize access.

## 18.4 Transactional outbox and idempotent projection

Because SQLite/PostgreSQL, vector DB, cache and graph DB cannot participate in one ordinary ACID transaction, avoid the dangerous pattern “commit SQL, then directly write every other store and assume success.”

Use a transactional outbox:

1. Commit canonical event and an `OUTBOX_EVENT` in the same transaction.
2. A worker reads the durable outbox and deterministically computes projections.
3. Write each projection idempotently keyed by `(event_id, projection_version, source_hash)`.
4. Record per-index checksum, count, readiness status and last processed event sequence.
5. Retry failed projections with bounded exponential backoff and jitter; dead-letter poison items with reasons.
6. Publish a new **ready snapshot** only when all required projections for that snapshot meet invariants.
7. Rebuild from canonical event/outbox log after data loss, migration or corrupted index.

The outbox pattern is documented for cross-service consistency by Debezium [R19]. An outbox does not magically make cross-store writes atomic; it makes discrepancies observable and replayable.

## 18.5 Snapshot/read consistency

Each canonical commit has monotonically ordered `commit_seq` (within a declared namespace/partition). Each derived index advertises `index_high_watermark`, source-manifest hash, and projection version. A read request declares `minimum_snapshot` and freshness requirement:

- `CONSISTENT_READY`: all required indexes match an allowed watermark; safe to serve.
- `CANONICAL_FALLBACK`: derived index unavailable but exact source lookup can satisfy the request.
- `DEGRADED`: some retrieval channels unavailable; disclose reduced recall confidence, avoid claiming exhaustive absence.
- `UNAVAILABLE`: required evidence cannot be verified at the requested freshness.

This prevents a query from interpreting an index lag as “the event does not exist.” A stale Redis cache never outranks a newer canonical tombstone or ACL revision.

## 18.6 Real replication and sharding plan

Start with tenant-scoped IDs, stable partition keys, event log ordering and data residency rules. If scale requires shards, partition by tenant/workspace or stable entity namespace **when this preserves locality**; quantify cross-shard graph queries and recall loss. Replicas improve read availability but create read-lag and cache-invalidations. Sharding introduces hard cross-partition graph edges. No default partition choice is guaranteed optimal; experimentally measure skew, hot entities, merge operations, and cross-tenant isolation.

**Crucial:** Neo4j data, Qdrant vectors and SQLite rows are projections of the *same canonical events*, but **not replicas of the same logical database record**. Cross-store parity means every referenced derived object resolves to a legitimate canonical record, not identical physical schema.

## 18.7 Recovery and migration

Require snapshot backups, integrity hashes, restore tests, replay of outbox, index re-creation with pinned model/embedding revisions, atomic pointer switch on full reindex, cache generation/version keys, and garbage collection of obsolete projections. Measure RPO/RTO only after recovery drills; do not invent durability guarantees or production latency SLAs before measurement.

# 19. Failure containment, security, privacy, and operations

## 19.1 Failure matrix

| Fault | Expected containment behavior | Experiment |
|---|---|---|
| Vector index unavailable | Fall back to authorized exact/BM25/graph subset when sufficient; otherwise `VERIFICATION_UNAVAILABLE` | Kill vector process under load |
| Graph unavailable | Continue hybrid/latent retrieval and disclose missing association coverage | Crash graph service during multi-hop query |
| SQLite lock/contention | Bounded retry, no double insert, do not claim commit success before durable ack | Concurrent writer stress |
| Redis lost/stale | Rebuild cache from authoritative registry; never use stale revocation | Crash cache after ACL revoke |
| Outbox worker crashes after one index write | Idempotent replay; prevent partially ready snapshot | Crash at each commit boundary |
| Index worker receives malformed record | Quarantine and dead-letter, preserve source; other records proceed | Corrupt injected event |
| Encoder version changes | Shadow index/version pinning and compatibility check, swap atomically | Mixed old/new embeddings |
| Partial cue seeds wrong identity | Candidate ambiguity, bounded multi-seed test, never false identity merge | Same-name/different-tenant cases |
| Diffusion graph hub dominates | Typed degree constraints and relevance verification | High-degree decoy nodes |
| Causal hypothesis incorrectly propagated | Preserve hypothesis edge type; output cautious conditional inference | Injection of false `CAUSED_BY` path |
| User deletes memory | Tombstone canonical record and block serving immediately, invalidate all projections | Deletion during graph outage |
| Permission revoked during read | Final authorization revalidation before returning evidence | TOCTOU race |
| Retry storms | Exponential backoff, jitter, circuit breakers, per-tenant quotas | Synthetic outage/failure burst |
| Poisoned document instructs assistant | Treat retrieved instructions as untrusted data; output gate rejects tool-policy override | Memory prompt injection suite |
| Multi-store split/partition | Consistent snapshot or clear degraded status; no invented fully current answer | Network partition fault injection |

## 19.2 Threat model

Threat actors may control user text, external documents, some retrieved source content, maliciously crafted query strings, or a compromised low-trust producer. They may attempt to insert prompt instructions, spoof privileged source approval, poison graph edges, exploit same-name identity merges, force sensitive cross-tenant retrieval, or contaminate slow semantic consolidation.

AgentPoison demonstrates that poisoning memory/knowledge bases can induce malicious downstream agent behavior [R20]. OWASP's 2025 LLM risk model explicitly covers prompt injection, sensitive information disclosure, data/model poisoning, excessive agency and vector/embedding weaknesses [R21]. The blueprint therefore assumes **retrieved memory is data**, not an instruction authority.

### Minimum controls

- Authenticate who can submit observations; separate trusted instrumentation from user reports and retrieved web text.
- Hard-enforce ACL and tenant boundaries at source selection and traversal, not only in a generated prompt.
- Treat source approval metadata as cryptographically/auditably supplied by trusted registry, not a field extracted from untrusted text.
- Validate tools and SQL/graph parameters using allowlists; never execute arbitrary executable content from memory.
- Reject embedded “ignore your instructions” payloads as instructions; preserve quoted content as evidence when relevant.
- Keep source-content hashes and derivation lineage for incident reconstruction.
- Encrypt sensitive stores where appropriate, use secrets management and least-privilege identities.
- Rate-limit write/retrieval/traversal costs; enforce query budgets, cancellation and bounded recursive traversal.
- Redact traces; do not log full private source bodies by default.
- Provide audit trails for access, moderation, correction, deletion and failed authorization attempts.
- Defend against **retrieval-time indirect leakage** via forbidden node paths, counts, activation statistics and generated summaries.

## 19.3 Memory poisoning and trust promotion

A model-written reflection like “It appears deployment X caused incident Y” is an inference, not an observed causal link. Its later retrieval cannot upgrade it. Multiple repeated unverified claims do not become corroborating independent sources. Slow consolidation must check source independence and provenance; otherwise one poisoned document can be amplified into a stable false “learned” memory.

## 19.4 Reliability observability

Emit structured traces for `ingest.validate`, `sql.commit`, `outbox.enqueue`, `projection.embed`, `projection.graph`, `snapshot.publish`, `query.seed`, `query.hybrid`, `query.latent`, `query.diffuse`, `candidate.verify`, `abstention.gate`, `answer.cite`. Capture p50/p90/p95/p99 where sample sizes justify it, queue backlog, retries, stale high-watermarks, cache hit rates, wrong-version retrieval, false association, unauthorized attempts, token/compute cost, and graceful degradation. Tracing is for operations and benchmark reproducibility, not a substitute for correctness evaluation.

## 19.5 Chaos and recovery research program

For each storage component and pipeline boundary, inject process kills, network delay/partition, repeated delivery, corrupted payloads, disk full, stale replicas, concurrent mutations, ACL revocations, deletions, model-version skew, and index rebuild races. Test restoration from a clean canonical snapshot and assert:

1. No missing **durably committed** event after a successful canonical database recovery within its stated durability assumptions.
2. Derived indices eventually converge to declared manifest/checksum under healthy conditions.
3. Unauthorized or tombstoned content is never returned after the revocation is observed by the authoritative read path.
4. A read in degraded mode never claims complete verification when relevant channels are missing.
5. Concurrent retry does not create duplicate events or unbounded graph-edge multiplicity.

When exact cross-store convergence cannot be proved by the tests, report the residual failure window and improve the protocol; do not assert “strong consistency” from replication alone.

# 20. Data contracts and reference pseudocode

The schemas below are **illustrative contracts**, not a complete production-ready ORM/migration or a claim that all storage engines support identical transaction semantics. In real code, use typed validation, limits and tenant-aware queries throughout.

## 20.1 Canonical SQL-oriented event and atom records

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Epistemic = Literal[
    "DIRECT_OBSERVATION", "USER_REPORTED", "DOCUMENT_ASSERTION",
    "MODEL_INFERENCE", "HYPOTHESIS", "DERIVED_AGGREGATE", "RETRACTED",
]

@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    tenant_id: str
    source_id: str
    source_version: str
    source_hash: str
    event_time: datetime | None
    recorded_at: datetime
    event_type: str
    raw_content_uri: str
    schema_version: int
    commit_seq: int

@dataclass(frozen=True)
class MemoryAtom:
    atom_id: str
    event_id: str
    tenant_id: str
    subject_id: str
    predicate: str
    object_value: str
    qualifiers: dict
    epistemic_type: Epistemic
    evidence_locator: str
    valid_from: datetime | None
    valid_to: datetime | None
    supersedes_atom_id: str | None
    extraction_version: str

@dataclass(frozen=True)
class MemoryEdge:
    edge_id: str
    tenant_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    evidence_atom_ids: tuple[str, ...]
    provenance_status: str
    valid_from: datetime | None
    valid_to: datetime | None
    projection_version: str
```

Entity, principal, ACL, legal retention, physical deletion, source version/span, and approval should be normalized into associated tables rather than crammed into a huge JSON field. Every public reference requires authenticated scope.

## 20.2 Derived projection records

```python
@dataclass(frozen=True)
class MemoryProjection:
    event_id: str
    tenant_id: str
    projection_version: str
    encoder_revision: str
    source_hash: str
    contextual_vec_ref: str | None
    semantic_vec_ref: str | None
    procedural_vec_ref: str | None
    salience_features: dict
    binding_vec_ref: str | None
    sparse_code_ref: str | None
    graph_projection_version: str | None
    index_commit_seq: int
    projection_state: str  # PENDING / READY / DEGRADED / REVOKED
```

`MemoryProjection` contains only references or derived representations. It cannot be used to reconstruct factual source text without following the canonical source record and its permission check.

## 20.3 Query context contract

```python
@dataclass(frozen=True)
class RecallRequest:
    query_id: str
    principal_id: str
    tenant_id: str
    cue_text: str
    task_goal: str | None
    evaluation_time: datetime
    event_time_filter: tuple[datetime, datetime] | None
    requested_snapshot: int | None
    required_freshness: str
    permitted_edge_types: tuple[str, ...]
    max_candidates: int
    max_evidence_tokens: int
    max_visited_graph_nodes: int
    max_graph_hops: int
    max_wall_ms: int

@dataclass(frozen=True)
class EvidenceCandidate:
    atom_ids: tuple[str, ...]
    event_id: str
    source_id: str
    source_version: str
    evidence_locator: str
    channel: str
    score: float | None     # ranking feature, NOT a truth probability
    graph_path_edge_ids: tuple[str, ...]
    validated_at_snapshot: int
```

## 20.4 Damped graph propagation pseudocode

```python
def diffuse_ppr(seed, neighbors, eligible, damping=0.7,
                max_steps=25, tolerance=1e-6, max_nodes=5000):
    # seed: {node_id: nonnegative normalized weight}
    # neighbors(v): list[(target, allowed_edge_weight)]
    # eligible(v): tenant/ACL/time/source validity gate
    # This illustrative local implementation requires bounded traversal.
    import collections

    seed = {v: p for v, p in seed.items() if eligible(v) and p > 0}
    total = sum(seed.values())
    if not total:
        return {}
    seed = {v: p / total for v, p in seed.items()}
    current = dict(seed)

    for _ in range(max_steps):
        nxt = collections.defaultdict(float)
        for v, p in seed.items():
            nxt[v] += (1.0 - damping) * p
        visited = 0
        for src, mass in current.items():
            if not eligible(src):
                continue
            edges = [(dst, w) for dst, w in neighbors(src)
                     if eligible(dst) and w > 0]
            denom = sum(w for _, w in edges)
            if denom == 0:
                # Return dangling mass to original valid seeds.
                for v, p in seed.items():
                    nxt[v] += damping * mass * p
                continue
            for dst, w in edges:
                nxt[dst] += damping * mass * w / denom
                visited += 1
                if visited > max_nodes:
                    raise RuntimeError("graph budget exceeded")
        delta = sum(abs(nxt.get(v, 0) - current.get(v, 0))
                    for v in set(nxt) | set(current))
        current = dict(nxt)
        if delta < tolerance:
            break
    return current
```

**Important:** this pedagogical routine does not enforce a *global distinct-node budget* or wall-clock cancellation. In a real implementation, track total unique nodes/edges across iterations and fail or return a truncated/invalid status when over budget; implement type-aware edge rules and reverse/forward direction policies; reconcile probability mass with dangling nodes; inspect numerical convergence; and never serve these activation values as confidence probabilities.

## 20.5 Read pipeline pseudocode

```python
async def recall_memory(request):
    principal = authorize_request(request.principal_id, request.tenant_id)
    snapshot = resolve_serving_snapshot(request, principal)
    if not snapshot.satisfies_required_freshness:
        return evidence_status("VERIFICATION_UNAVAILABLE", snapshot=snapshot)

    query_constraints = parse_exact_time_identity_constraints(request)
    # Every retriever sees only eligible candidates.
    seed_candidates = await exact_bm25_dense_and_latent_search(
        request, query_constraints, snapshot, principal
    )
    seed_atoms = verify_eligible_source_anchors(seed_candidates, principal, snapshot)

    graph_candidates = []
    if graph_index_ready(snapshot) and seed_atoms:
        graph_candidates = await bounded_typed_diffusion(
            seed_atoms, request.permitted_edge_types, request.max_graph_hops,
            request.max_visited_graph_nodes, request.max_wall_ms,
            principal=principal, snapshot=snapshot
        )

    merged = merge_ranked_candidates(seed_candidates, graph_candidates)
    evidence = reload_authorized_canonical_spans(merged, principal, snapshot)
    evidence = validate_time_identity_edges_and_conflicts(evidence, request)
    status = evidence_sufficiency_gate(evidence, request)
    return make_cited_context_or_qualified_abstention(status, evidence, request)
```

A query should never directly inject an unsupported `edge_type` string into the graph engine. The policy-gated allowed relation set is computed on the server and is at least as strict as the request field.

## 20.6 Feedback and reconciliation

Read access may append a **separate analytic event** recording usage, latency, and feedback. Retrieving an event never edits its source, epistemic type, source hash or event time. If a user corrects a previous memory, run the *write pipeline* to create a new source-anchored correction and regenerate affected projections. Feedback-derived ranking weights must be isolated from factual content and versioned with reproducibility metadata.

# 21. Research hypotheses, baselines, and ablation matrix

## 21.1 Preregistered research hypotheses

| ID | Hypothesis | Main alternative/null |
|---|---|---|
| H1 | Functional multi-view encodings improve partial-cue recall over a single-embedding control | No improvement at same model/index budget |
| H2 | A shared query–memory binding space outperforms untrained concatenation or late fusion | Simple fusion matches or exceeds learned binding |
| H3 | Supervised separation helps near-duplicate episode discrimination without damaging genuine generalization | Gains in discrimination are offset by recall loss |
| H4 | Typed graph activation diffusion recovers additional complete evidence chains compared with ANN/BFS | Diffusion adds cost and false edges without useful new evidence |
| H5 | CDZ reconstruction improves retrieval/useful recall beyond reading exact stored facets | Reconstruction is redundant or hallucinatory |
| H6 | Task-derived salience or monoamine-proxy salience improves end-to-end utility | No salience or cheap task ranking performs as well |
| H7 | Deterministic evidence, identity, and temporal gates reduce unsupported recalled facts | Properly governed hybrid RAG matches them |
| H8 | Evidence-constrained consolidation improves long-horizon abstraction and updates | Consolidation loses exceptions or adds no benefit |
| H9 | Polyglot derived indexes can be kept coherent and revocable under faults | Index lag, dual-write failure or leaks undermine usability |
| H10 | Compressed vector representations retain sufficient retrieval geometry with meaningful storage wins | Full-precision or simpler quantization dominates |

## 21.2 Retrieval comparator families

**Required comparators (same authorized corpus and answer budget):**

- `R0`: BM25 / exact-key control.
- `R1`: dense ANN control.
- `R2`: hybrid BM25 + dense RRF.
- `R3`: hybrid + fixed reranker (**principal practical challenger**).
- `R4`: multi-vector late interaction (ColBERTv2 where deployment feasible).
- `R5`: HippoRAG 2 official retrieval pipeline.
- `R6`: graph-based retrieval in a matched and a native-ingestion condition.
- `R7`: context/semantic/action/salience views with naive late fusion.
- `R8`: shared-latent binding without graph.
- `R9`: graph activation from fixed hybrid seeds without shared latent.
- `R10`: shared-latent + controlled graph diffusion + evidence gate.

**Optional native system comparators:** Microsoft GraphRAG Local, LightRAG, mature long-term agent-memory pipelines. They may need their own extraction/indexing; report their true feature/cost differences rather than asserting artificial same-embedding equivalence. Do not call LangChain or an agent framework an algorithm in itself. Where source-code/version pinning is impossible, label the arm exploratory.

## 21.3 Orthogonal experimental axes

The complete factorial product would be enormous; run a **staged and hierarchical design**, not every theoretical combination:

| Axis | Main variants | First research stage |
|---|---|---|
| Binding | single, late fusion, concat, shared, joint-attention, denoising | compare first five; denoising exploratory |
| Losses | none, each single, each pair, all three | factorial T0–T7 |
| Separation | none, random sparse, learned sparse, margin | pilot + controlled dimension sweep |
| Completion | ANN, BFS, PPR, heat kernel, recurrent associative | ANN/BFS/PPR first |
| CDZ | direct read, decode, hybrid | after binding alignment works |
| Salience | off, monoamine proxy, task-derived | after relevance/identity baseline |
| Consolidation | none, rule aggregates, generated reviewed, slow learned | later longitudinal track |
| Storage | in-process, SQLite-led multi-store, failure-injected | algorithms first; ops track later |
| Quantization | float32, float16, scalar 8-bit, product, binary | after index quality stable |

Avoid one-shot “full brain architecture beats BM25” comparisons as causal evidence; they confound representations, graph, gates and compute.

# 22. Datasets and benchmark alignment

## 22.1 Synthetic hidden world for controlled tests

Construct a canonical *hidden* set of source events, assertions, temporal relations, identity scopes, confidence states and true causal relations. This hidden world creates ground truth; the retriever receives only rendered source material, authorized tool observations and indexing rules. Prevent training/inference contamination by keeping hidden labels, required evidence slots and exact answers out of published indexes.

A practical small pilot might use `5,000` atomic events, `15,000–30,000` assertions and `40,000–100,000` typed edges, **illustrative values only**; adapt based on engineering resources. Include repeated actor/action/location templates with one changed attribute, sparse cross-document chains, source errors and deliberate contradictory claims. Scale by fixed factors to determine whether graph density—not merely event count—controls runtime.

### Controlled task families

| Family | What is manipulated | Required gold behavior |
|---|---|---|
| E1: Near-duplicate episode | Same actors/action, differing date/location/quantity | Correct event ID or qualified ambiguity |
| E2: Partial-cue reconstruction | Mask 10/30/50/70% of cue details | Recover sufficient evidence without invented facts |
| E3: Multi-hop chain | Required support distributed over 1–4 edges | Complete verified evidence path |
| E4: False association | High-degree hub and plausible unsupported edge | Reject spurious associations |
| E5: User corrections | Same case corrected mid-conversation | Respect newest applicable *verified correction* |
| E6: Conflicting authorities | Two valid but contradictory sources | `CONFLICT`, not automatic newest wins |
| E7: Temporal query | Late arrivals, recorded/event-time divergence | Correct as-of reasoning |
| E8: Salience stress | Dramatic irrelevant messages versus dull crucial facts | Do not substitute emotion for relevance |
| E9: Unanswerable near-twins | Identical query, one missing required source | Correct abstention and correct answering |
| E10: ACL/privacy | Answer-bearing forbidden neighboring graph node | No exposure through traversal or final text |
| E11: Memory poisoning | Malicious instructions/counterfeit approvals | No trust promotion or tool override |
| E12: Storage failure | Missing projections, stale cache, partial commit | Accurate degraded status or safe fallback |
| E13: Long-run consolidation | Repeated events, exceptions, later reversals | Retain exception and traceable source support |
| E14: Cross-language cue | Indonesian/English/code mix across same episodes | Stable valid source retrieval |

### Essential paired counterfactuals

- `m_A` and `m_B` have identical common attributes but different event times and locations.
- One query specifies time (answerable), the otherwise identical query omits time (ambiguous).
- One graph contains a verified `REQUIRES` edge, its twin only `MENTIONS` (mere co-occurrence).
- One evidence snapshot contains the needed exception, its twin omits it (abstention control).
- One source is `DIRECT_OBSERVATION`, the matched twin contains only `HYPOTHESIS`.
- One result exists but is outside tenant ACL; do not leak either text or sensitive existence.
- One derived vector index is current, the twin is stale while canonical SQL contains the correct event.

## 22.2 External benchmarks

- **LongMemEval (ICLR 2025):** 500 curated memory questions across extraction, multi-session reasoning, temporal reasoning, knowledge updates and abstention [R10].
- **LongMemEval-V2 (2026):** 451 curated questions in agentic web/enterprise trajectory histories, useful for action/state memory at larger history scale [R22].
- **Palladion retrieval/evidence protocol:** supplies useful synthetic evidence-world methodology, complete evidence set scoring, explicit authority/time/ACL controls and selective prediction; **reuse its evaluation ideas**, not its domain-specific product assumptions.
- **Additional external track:** public multi-hop/retrieval datasets when compatible and fully documented. Do not pretend ordinary fact QA directly validates remembered agent experience.

The primary synthetic event world must test tasks not already trivially solvable by memorized public knowledge. External benchmarks validate transfer; report their different answerability assumptions and source formats separately.

## 22.3 Data partitions and review

Split by *scenario family and entity cluster* before creating paraphrases; use development, calibration and locked test partitions. An illustrative initial allocation is `10% smoke`, `30% development`, `10% calibration`, `50% locked test`, but ensure each failure stratum has enough held-out cases. Use deterministic generator seeds, source manifests, human review of a stratified sample, double annotation for disputed cases, and frozen evaluation scripts. Do not write an “ideal” graph from oracle truth while forcing baseline systems to extract imperfect edges without reporting the disparity: include both **gold-graph diagnostic** and **derived-graph realistic** tracks.

## 22.4 Fairness and leakage controls

Hold constant, whenever the method allows: authorized source snapshot, principal, query wording, required evidence token budget, generator model, answer instruction, evaluation clock, test cases, training exposure, and exact source hashes. Native graph systems may have distinct indexing pipelines; record indexing cost and run separate **controlled common-input** and **native product** comparisons. Hold K and token budget visibly separate: equal top-10 counts do not imply equal source information or context tokens.

# 23. Metrics, statistical protocol, and cost

## 23.1 Retrieval/association quality

- `Recall@K`, `Precision@K`, `MRR`, `nDCG@K`, `Success@K` with ground-truth relevant units normalized to source/atom IDs.
- `SlotCoverage@K` and `CompleteSet@K` for multi-evidence questions.
- **Episode identity accuracy** conditional on sufficient disambiguating cues.
- **Ambiguity detection rate** when multiple true episodes satisfy the cue.
- **Partial-cue degradation curve:** recall versus fraction/types of missing cues.
- **Wrong-episode confusion rate** and **same-episode paraphrase recall** (separation/generalization pair).
- **Graph false-association rate**, edge/path provenance validity, verified path length, useful extra evidence per visited 1,000 nodes.
- **Hub leakage**, wrong-entity merge rate, unauthorized traversal exposure and unsupported causal relation promotion.
- `ANNRecall@K` compared with exhaustive nearest-neighbor search on a tractable subset.
- **Decoder feature fidelity** and fact/identity distortion, where CDZ reconstruction is enabled.

## 23.2 Reliability, freshness and abstention

- `SUPPORTED` / `PARTIALLY_SUPPORTED` / `CONFLICT` / `NOT_ESTABLISHED` / `VERIFICATION_UNAVAILABLE` classification accuracy.
- False-Answer Rate, False-Abstention Rate, selective risk, selective coverage, AURC.
- Brier score, log loss and ECE for calibrated correctness probability, if used.
- Citation/source-span precision and recall, version applicability, ACL leakage incidents, wrong-vintage answer rate.
- Cross-store serving consistency, stale-index exposure, time-to-ready, recovery after a correction, memory-deletion lag.
- Misleadingly confident answers when graph/latent retrieval was degraded.

## 23.3 Resource and scalability measurements

Track **offline** parsing, extraction, embedding, training, graph construction, indexing, migration, rebuild and storage, as well as **online** query embedding, exact lookup, ANN, PPR iterations, graph edge visits, reranking, verification and generation. Report p50/p90/p95/p99 latencies and time-to-first-answer only with adequate samples, warm/cold cache, concurrency, failure-mode behavior, peak RAM/disk/GPU, queue backlogs and amortized cost.

### Compression alternatives replacing the old ternary-weight analogy

Benchmark: float32 full precision; float16; scalar quantization (e.g., int8), binary quantization where embedding distributions permit; product quantization; and possibly residual quantization with exact-vector rescoring. Faiss and Qdrant document these as vector-storage/search trade-offs [R15, R23]. **Do not assume** benefits from unrelated ternary neural weight formats. For each method measure Recall@K versus exact float32, index size, build time, p95 search, source ID stability, update costs, rerank overhead, and effect on sparse/latent similarity.

## 23.4 Statistical analysis and honesty

- Preregister one or two **primary** comparisons: `R10 vs R3` on partial-cue `CompleteSet@10`, and `G3 vs G0/G1` on evidence-complete multi-hop retrieval under matched tokens/visited nodes. Other tests are secondary/exploratory.
- Pair results on the same query; bootstrap **scenario-family clustered** differences with confidence intervals.
- Run multiple model-training seeds where learning is present; include seeds in bootstrap reporting or use hierarchical analysis.
- Report per-task stratum, language, corpus scale, graph-degree distribution and cue-corruption level.
- Handle multiple hypotheses with a declared family-wise or FDR correction where applicable; exploratory plots are not confirmatory wins.
- Select parameters on development, assess calibration on calibration split, and evaluate locked test once after the design is frozen.
- Report outright severe events (privacy leaks, fabricated sources, unsupported operational directives) separately from aggregate scores.
- Report **Pareto** frontiers: quality versus p95 latency; quality versus per-query cost; selective risk versus correct coverage; recall versus memory footprint.

## 23.5 Proposed acceptance criteria, not measured conclusions

A candidate advances from algorithmic pilot to operational integration only if:

1. It improves the preregistered challenging-task endpoint over R3 with a confidence interval excluding trivial/no benefit **or** establishes a previously unavailable capability at a documented cost.
2. It does not exceed predeclared false-association or correct-answer-coverage regression limits.
3. It passes source provenance, ACL, deletion and temporal consistency unit/security tests under the defined scope.
4. The result persists on an external memory benchmark or is explicitly scoped to the synthetic task family.
5. The benefit justifies measured indexing/training/storage and p95 time; otherwise keep the simpler arm.

Concrete numeric pass/fail thresholds must be frozen *after pilot power/effect-size estimation and before locked testing*. Zero observed incidents is not proof of zero population risk. Never invent benchmark numbers or production SLOs in advance.

# 24. Experiment execution sequence

## Stage 0 — Scientific and harness preflight

Freeze terminology, research questions, evidence ontology, source/version semantics, datasets and success criteria. Build a small synthetic world with code-first ground truth. Validate hard identity, temporal, ACL and source-reconstruction constraints. Implement exact BM25/dense/RRF/reranker baselines before experimenting with biology-inspired components. Publish manifest schema and human annotation procedure.

**Gate:** every known positive/negative fixture can be reproduced and every output points to a real source ID or declares insufficiency.

## Stage 1 — Representation and loss studies

Evaluate single embedding, late fusion, concatenation and learned shared latent. Train T0–T7 with controlled positive/hard-negative pairs. Run toy separation simulations and actual embedding sweep independently; quantify cue alignment and episode collisions. Compare outputs to normalized canonical event identities.

**Gate:** binding must beat simpler fusion in at least one preregistered target without material regression to pursue larger architectures. If it fails, preserve the winner, not the favored metaphor.

## Stage 2 — Graph activation experiments

Create a deterministic evidence-linked atom graph. First test with **gold graph** to estimate upper-bound possible graph benefit; then with derived graph to measure extraction errors. Compare ANN/BFS/attenuation/PPR/heat kernel with matched seeds and candidate/time budgets. Add shared latent only after independent performance is measured. Capture actual verified path evidence and false-path rates.

**Gate:** diffusion adds complete evidence rather than merely more high-scoring neighbors or narrative plausibility.

## Stage 3 — CDZ, salience, and consolidation ablations

Run exact stored facets versus decoder and hybrid reconstruction. Test no salience versus monoamine-proxy versus task-derived features. Then test episodic-only versus rule-based and evidence-reviewed consolidation. Do **not** multiply every branch into one giant factorial; investigate conditional winners and document choices before proceeding.

## Stage 4 — Longitudinal interactive agent memory

Use many episodes with corrections, as-of references, source revocations, case switching, cross-language queries and incomplete cues. Test selective abstention and evidence status outputs. Run LongMemEval and agentic trajectory benchmarks using source-compatible adapters. Separate memory retrieval from downstream generator error by evaluating retrieval-only and fixed-generator tracks.

## Stage 5 — Polyglot and reliability track

Move from in-process research harness to canonical SQL + replayable vector/graph projections, optional Redis cache, and outbox. Inject failures, migrations, permission changes, source deletion, queue backlog and partial index rebuild. Measure p95/p99, throughput, index lag, recovery, source leakage and operational effort. Do not use this stage to retroactively claim algorithmic gains caused by changing database vendors.

## Stage 6 — Locked confirmatory experiment and technical report

Freeze code commit, model revisions, source/test/gold hashes, hardware, pricing snapshot, hyperparameters, trained checkpoints and run order. Execute blinded locked evaluation. Report per-stratum scores, effect sizes and CIs, failed runs, missing-feature limitations, resource costs, security failures and negative results. Publish a methodological limitations section and reproduction instructions.

## Suggested project organization (illustrative)

```text
subcortical-memory/
  research/
    protocol.md
    hypotheses.yaml
    source_register.md
  fixtures/
    hidden_world/          # evaluator-only; never index as memory
    published_corpus/
    questions/
    validation/
  memory/
    canonical/             # IDs, transactions, outbox, provenance
    extraction/            # event and atomic assertion parsers
    features/              # deterministic contextual/semantic/action features
    embedding/             # baseline, shared latent, training
    graph/                 # typed projection and diffusion
    retrieval/             # seeds, candidates, rank fusion
    governance/            # ACL, temporal, evidence status, abstention
    consolidation/         # evidence-derived generalization
    projection/            # worker state, snapshots, migrations
  benchmark/
    adapters/
    runs/
    metrics/
    statistics/
    failure_injection/
  reports/
    preregistration.md
    study-results.md
    negative-results.md
```

**Dependencies:** build canonical evidence and basic baselines before training shared latent; validate graph quality before traversal; implement refusal/ACL before exposing graph to user-facing agents. Do not confuse the file organization with a mandate to introduce microservices prematurely.

# 25. Open questions and threats to validity

## 25.1 Open technical questions

**Q1. What is the actual additional signal in functional facets?** If separate “hippocampal/contextual” and “semantic” heads receive identical input and training labels, the decomposition may be cosmetic. Test whether facet representations contribute complementary conditional information beyond a single larger backbone.

**Q2. Is one shared code too lossy?** Some queries care about exact time; others about high-level relationships. A code optimized for both may underperform typed late fusion. Test shared code, multiple codes per event, and per-task rank fusion at matched total bytes.

**Q3. Do graph edges represent useful memory structure or extraction artifacts?** A large automatic graph can reproduce the biases of its extractor. Test typed identity precision, relation precision, confidence calibration and provenance resolution before running diffusion.

**Q4. What is the optimal activation locality?** Restart probability, edge relation weights and number of hops jointly determine whether memory recall is narrow or associative. Plot recovered evidence and false associations versus diffusion scale and visited nodes, not just final answer accuracy.

**Q5. How do we handle ambiguous cues?** If two events are equally compatible with a query, a forced nearest-neighbor or attractor completion is *wrongly overconfident*. Keep multiple hypotheses or ask for disambiguation; this is not an algorithm failure when evidence is genuinely insufficient.

**Q6. How do we know when learned loss functions conflict?** Measure training stability, gradient interference, representation rank, hard-negative contamination, and generalization to unseen event entities. Weighted sums can hide dominated loss terms.

**Q7. Can consolidation respect rare exception cases?** A generalization system may learn the common pattern and discard important exceptions. Require source-addressable rare event recall and contradiction sensitivity after every consolidation cycle.

**Q8. How do we choose a graph store?** An in-memory graph, SQLite adjacency tables, Neo4j and other graph systems differ in traversal APIs, durability and operational overhead. Benchmark at fixed graph content; do not choose on branding.

**Q9. What if encoding models are upgraded?** A new projection invalidates old geometry. Use versioned shadow indexes and explicit migration, with mixed-version query failure tests. Avoid continuous unversioned online updates.

**Q10. When are two sources truly independent?** Reposted documents, copied incident reports and paraphrased user messages can look like corroboration but all originate from one observation. Source lineage must support independence checks to prevent amplification.

**Q11. Does emotional proxy extraction create unfair or intrusive inference?** Text-derived “neurochemical” variables may be misleading and sensitive. Do not diagnose people, infer hidden mental-health facts, or make consequential decisions based on these features. Prefer limited, task-grounded features unless a controlled test demonstrates value.

**Q12. Can deletion be complete in all derived representations?** Learned parameter updates may encode information from deleted records. If experimental online training on personal data is permitted, define retraining/unlearning policy and what deletion guarantees are and are not possible.

## 25.2 Internal-validity threats

- An oracle graph is used for the candidate system but baselines receive extracted graphs or no equivalent source visibility.
- Query templates leak exact event keys used in hidden truth generation.
- One arm receives a stronger embedding backbone, more training pairs or bigger context than another without reporting the difference.
- A generative decoder is rewarded for convincing prose rather than reconstructing authenticated facts.
- Severe wrong-identity/ACL failures are hidden by high mean Recall@K.
- Training negatives accidentally include another acceptable source; model “learns” to suppress valid evidence.
- Development thresholds are repeatedly tuned against the supposedly locked test.
- Sparse-overlap statistics are falsely presented as *semantic cosine after projection* or as real-world benchmark results.
- The new graph retrieval is effectively HippoRAG/PPR with different branding; novelty must be measured through evidence constraints or other demonstrable mechanisms.

## 25.3 External-validity threats

Synthetic data may be cleaner than human memory or more templated than noisy agent trajectories. Retrieval improvements on one topical domain need not transfer to code debugging, personalized assistance, multilingual logs or long-horizon action history. Memory provenance and permission constraints differ by application. Run at least one independent external benchmark and characterize out-of-distribution examples and privacy assumptions.

## 25.4 What would change our scientific conclusion?

- **Reject or narrow functional decomposition** if multi-view models fail to beat single-vector or ColBERT-style controls at matched cost.
- **Reject shared CDZ binding** if late fusion/concatenation is reliably better on partial-cue recall and temporal identity.
- **Reject aggressive separation** if it improves near-duplicate discrimination but severely reduces answerable ambiguous/partial-cue recall.
- **Reject diffusion completion** if PPR/heat kernels are dominated by BFS or hybrid ANN in complete evidence, latency and false association.
- **Reject reconstructive CDZ** if exact stored facets beat it on source fidelity and downstream accuracy.
- **Reject biological salience proxy** if task features or no salience dominates across languages and workloads.
- **Reject consolidation complexity** if a simple retained event log plus evidence-backed aggregates works as well.
- **Reject multi-store deployment** for the prototype if its failure modes and operational costs dominate gains. This is compatible with still studying the memory *algorithm*.

# 26. Sources and annotated reference register

The preceding document distinguishes three origins: **[Original research synthesis]** for the supplied architecture's neuroscience themes; **[Companion benchmark]** for the attached evidence-reliability, abstention and fairness protocol; **[Externally checked]** for publicly verifiable research and system documentation cited below. The toy sparse-support simulation in §10.3 was computed specifically for this revision and is not externally published performance evidence. Exact web links are provided for further verification. A listed source validates the claims actually attributed to it, not the entire proposed software translation.

## 26.1 Neuroscience and theory

**[R1]** Roy, D. S. et al. (2022). “Brain-wide mapping reveals that engrams for a single memory are distributed across multiple brain regions.” *Nature Communications* 13, 1799. Studies mouse contextual-fear memory and identifies 117 regions with high-probability engram candidates among 247 surveyed, with functional tests of coordinated reactivation. https://www.nature.com/articles/s41467-022-29384-4

**[R2]** McClelland, J. L., McNaughton, B. L., O'Reilly, R. C. (1995). “Why there are complementary learning systems in the hippocampus and neocortex.” *Psychological Review* 102(3):419–457. Foundational CLS computational theory; not a mandate for a particular database topology. https://pubmed.ncbi.nlm.nih.gov/7624455/

**[R3]** Meyer, K., Damasio, A. (2009). “Convergence and divergence in a neural architecture for recognition and memory.” *Trends in Neurosciences* 32(7):376–382. Reconstruction/disposition framework; does not specify a VAE or shared retrieval code. https://pubmed.ncbi.nlm.nih.gov/19520438/

**[R4]** Lövheim, H. (2012). “A new three-dimensional model for emotions and monoamine neurotransmitters.” *Medical Hypotheses* 78(2):341–348. Proposes a cube of emotions, expressly calls for empirical validation. https://pubmed.ncbi.nlm.nih.gov/22153577/

**[R5]** Batten, S. R. et al. (2025). “Emotional words evoke region- and valence-specific patterns of concurrent neuromodulator release in human thalamus and cortex.” *Cell Reports* 44(1):115162. Region/context-dependent human observations; not a one-emotion-one-transmitter mapping. https://pmc.ncbi.nlm.nih.gov/articles/PMC11893175/

**[R8]** Yassa, M. A. and Stark, C. E. L. (2011). “Pattern separation in the hippocampus.” *Trends in Neurosciences*. Theoretical and empirical review of pattern separation; specific software mappings require independent validation. https://pmc.ncbi.nlm.nih.gov/articles/PMC3183227/

## 26.2 Modern representation and retrieval

**[R6]** Esser, P. et al. (2024). “Scaling Rectified Flow Transformers for High-Resolution Image Synthesis.” *ICML/PMLR* 235. Stable Diffusion 3 / multimodal-transformer architecture with separate modality weights and bidirectional interactions; trains image synthesis, not retrieval. https://proceedings.mlr.press/v235/esser24a.html

**[R7]** Peebles, W., Xie, S. (2023). “Scalable Diffusion Models with Transformers.” *ICCV*. Transformer-based latent image denoising. Motivation for latent fusion mechanisms, not proof of retrieval gains. https://openaccess.thecvf.com/content/ICCV2023/html/Peebles_Scalable_Diffusion_Models_with_Transformers_ICCV_2023_paper.html

**[R9]** Gutiérrez, B. J. et al. (2025). “From RAG to Memory: Non-Parametric Continual Learning for Large Language Models.” *ICML/PMLR* 267. HippoRAG 2; includes graph/PPR-based memory retrieval and passage integration. https://proceedings.mlr.press/v267/gutierrez25a.html

**[R10]** Wu, D. et al. (2025). “LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.” *ICLR*. Source code and benchmark, 500 curated questions with update, temporal and abstention cases. https://proceedings.iclr.cc/paper_files/paper/2025/hash/d813d324dbf0598bbdc9c8e79740ed01-Abstract-Conference.html

**[R11]** Santhanam, K. et al. (2022). “ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction.” *NAACL*. Multi-vector late interaction and residual compression; strong challenge to the claim that memory retrieval is only single-vector cosine. https://aclanthology.org/2022.naacl-main.272/

**[R12]** Microsoft Research (2024). “GraphRAG: Improving global search via dynamic community selection.” Describes local/global graph retrieval and indexing trade-offs; not a universal replacement for exact event lookup. https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/

**[R22]** LongMemEval-V2 official repository (2026). Agentic memory for web/enterprise trajectories, 451 manually curated questions, memory abilities and latency evaluation. https://github.com/xiaowu0162/LongMemEval-V2

## 26.3 Graph diffusion and vector indexing

**[R13]** Neo4j Graph Data Science documentation, “PageRank,” including personalized PageRank with source nodes, weighted relationships, damping and iteration control. https://neo4j.com/docs/graph-data-science/current/algorithms/page-rank/

**[R14]** Chung, F. (2007). “The heat kernel as the pagerank of a graph.” Graph diffusion/random-walk theoretical formulation; the parameters are mathematical scales rather than physical neural time. https://pmc.ncbi.nlm.nih.gov/articles/PMC2148367/

**[R15]** Qdrant documentation, “Quantization.” Lists scalar, binary, product and additional quantization variants with recall/memory/speed trade-offs that depend on embedding distribution and configuration. https://qdrant.tech/documentation/manage-data/quantization/

**[R23]** Faiss project, “Faiss indexes.” Reference for exhaustive, HNSW, scalar quantization, product quantization, and indexing trade-offs. https://github.com/facebookresearch/faiss/wiki/Faiss-indexes

## 26.4 Database consistency, fault tolerance, and security

**[R16]** SQLite documentation, “Write-Ahead Logging.” Readers can coexist with one writer in WAL, with local-filesystem/shared-memory constraints. https://www.sqlite.org/wal.html

**[R17]** Redis documentation, “Redis replication.” Asynchronous replica semantics, failover risks, and limits of `WAIT` for strong consistency. https://redis.io/docs/latest/operate/oss_and_stack/management/replication/

**[R18]** Redis documentation, “Scale with Redis Cluster” / Cluster specification. Sharding and availability are distinct from strong transactional guarantees. https://redis.io/docs/latest/management/scaling/ and https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/

**[R19]** Debezium documentation, “Outbox Event Router.” Transactional outbox pattern supporting consistent publishing of committed DB events to downstream consumers. https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html

**[R20]** Chen, Z. et al. (2024). “AgentPoison: Red-teaming LLM Agents via Poisoning Memory or Knowledge Bases.” *NeurIPS*. Empirical security motivation for preventing retrieval-time trust promotion. https://papers.nips.cc/paper_files/paper/2024/hash/eb113910e9c3f6242541c1652e30dfd6-Abstract-Conference.html

**[R21]** OWASP GenAI Security Project, *Top 10 for LLM Applications (2025)*. Prompt injection, sensitive data leakage, poisoning, excessive agency and vector/embedding weaknesses. https://genai.owasp.org/llm-top-10/

## 26.5 Methodological source

**[M1]** *Palladion — Retrieval and Evidence-Reliability Benchmark*, 18 October 2026, user-provided research protocol. Consult especially its sections on comparative fairness, hidden synthetic worlds, evidence ontology, provenance/temporal applicability, abstention and selective prediction, and cross-store fault testing. This blueprint reuses the **methodology**, not its customer-service-specific product or claims of benchmark success.

---

# 27. Design decision log: all requested revisions

| Gap / request | Decision implemented here | Experiment or proof still required |
|---|---|---|
| **1: Learning objective** | Contrastive retrieval, reconstruction, separation defined individually and as pair/triple combinations | T0–T7 ablation; gradient conflicts, downstream score |
| **2: Shared binding, diffusion transformer** | Shared query–memory latent space; modality-style shared attention; optional denoising/flow experiment distinct from retrieval loss | B0–B5 comparison and query alignment |
| **3: Pattern separation trade-off** | No unconditional orthogonalization; exact overlap math and seeded toy simulation; sweep sparsity/generalization | Real embeddings, partial cues, hard negatives |
| **4: Physics-inspired activation diffusion** | Bounded typed graph, seed methods, PPR, heat kernel, path attenuation and false-path controls | G0–G7 with gold vs derived graph |
| **5: CDZ alternatives** | Address/direct read versus decoder versus hybrid proposal | Source fidelity, useful recall, cost |
| **6: Original emotion idea versus proposed alternative** | Monoamine proxy (labeled hypothesis), task-derived importance, and off condition | S0–S2 matched candidates and neutral-task safety |
| **7: Brain region mapping** | Functional operators with explicit neural-model caveats | Operator ablations without biological overclaim |
| **8: Deterministic rules** | Fixed/gated features and allowlists; independent heavy hypernetworks removed from core | Test learned lightweight gate only if useful |
| **9: Atom-level identity and provenance** | Stable event/atom/edge/source IDs, temporal and epistemic states | Identity/correction/duplicate benchmarks |
| **10: Data stores, authority, and replication** | Canonical SQL + raw source, Redis cache, vector and typed graph projections, outbox/snapshots; replication vs sharding distinguished | Multi-store recovery, latency and coherence |
| **11: No read-time mutation of facts** | Immutable events, append-only corrections, separate usage analytics | Factual contamination regression tests |
| **12: Abstention from companion protocol** | Five evidence statuses, selective risk, two-sided abstention, missing-reason taxonomy | Answerable/unanswerable twin pairs and calibration |
| **13: Drop ternary-weight analogy** | Compare float32/float16/int8 scalar, binary, PQ, residual/other quantization as retrieval storage methods | Recall/memory/latency trade-off after retrieval works |
| **14: Failures/security/ops research** | Fault matrix, chaos drills, ACL-before-traversal, prompt-injection/poisoning, outbox, snapshots, deletion, recovery | Stage 5 operational and adversarial suite |

## Final scientific position

The architecture is **plausible as a family of experiments**, not yet validated as a single superior memory system. The strongest immediate experiment is **shared query–memory binding plus identity-preserving episodic retrieval**, followed by **bounded, provenance-aware graph diffusion**. The riskiest optional mechanisms—heavy decoding, diffuse emotional salience, online formula generation, and forced sparse orthogonalization—must justify themselves against simple alternatives. The system's essential advance should be *retrieving supportable memories without confusing their identities, meanings, times or authority*, not reproducing the brain's vocabulary in software.

**No unmeasured benchmark improvement, runtime latency, production-scale durability guarantee, or neural equivalence is claimed in this document.**
