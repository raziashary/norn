# Requirements traceability

Updated 22 October 2026 (Asia/Bangkok). Each row maps intended source scope to detailed MDP design, real plan IDs and proof contracts. Coverage is not implementation evidence. SEC01-SEC27 cover every blueprint section; REV01-REV14 preserve its revision register. I/H/E and arm identifiers retain the blueprint meaning; they are not development phase numbers.

P01–P04 rows have phase-local proof in E-P01-003/E-P02-003/E-P03-003/E-P04-005. P04 DONE9/9 has158 tests, final4,140conditions,105 installed matching files/all7 source consumers, native/guard controls and resolved source/artifact review. Scientific outcome INCONCLUSIVE; matched singles erase decomposition-specific gain, B5 explicitly unsupported and known cache annotation corrected in interpretation. P05+ remain PLANNED/NOT_RUN. Local contract completion does not establish later graph/learning/locked/external efficacy. Documentation review checks meaningful mappings; the checker proves structural references/coverage only. Source headings use names rather than fragile line numbers.

| Requirement | Source / obligation | MDP design | Tasks | Gates | Evidence state |
|---|---|---|---|---|---|
| SEC01 | Purpose, lineage, and falsifiable claims | [design](MASTER_DEV_PLAN.md#scope) | P00-T02,P13-T07 | G-DOC,G-CONFIRMATORY | PLANNED / NOT_RUN |
| SEC02 | Research context: the problem being solved | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P00-T02,P02-T03 | G-DOC,G-RESEARCH | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| SEC03 | Neuroscience: findings caveats and computational translations | [design](MASTER_DEV_PLAN.md#scope) | P00-T02,P04-T08,P13-T07 | G-DOC,G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| SEC04 | Memory ontology: event atom relationship and evidence | [design](MASTER_DEV_PLAN.md#contracts) | P01-T02,P01-T07 | G-CONTRACT | P01 PASS E-P01-003; later ownership NOT_RUN |
| SEC05 | Principles and non-negotiable invariants | [design](MASTER_DEV_PLAN.md#scope) | P00-T03,P13-T01 | G-DOC,G-CONFIRMATORY | PLANNED / NOT_RUN |
| SEC06 | High-level architecture | [design](MASTER_DEV_PLAN.md#architecture) | P00-T02,P01-T12,P09-T01 | G-DOC,G-INTEGRATION | P01 PASS E-P01-003; later ownership NOT_RUN |
| SEC07 | Encoding and write pipeline | [design](MASTER_DEV_PLAN.md#write-flow) | P01-T08,P01-T09,P03-T09 | G-INGEST,G-SNAPSHOT | P01 PASS E-P01-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| SEC08 | Shared latent binding | [design](MASTER_DEV_PLAN.md#binding) | P04-T01,P04-T05,P04-T08 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| SEC09 | Training objectives and experimental loss design | [design](MASTER_DEV_PLAN.md#learning) | P05-T01,P05-T02,P05-T03,P05-T04 | G-LEARNING | PLANNED / NOT_RUN |
| SEC10 | Pattern separation | [design](MASTER_DEV_PLAN.md#learning) | P05-T05,P05-T06,P05-T07,P05-T08 | G-SEPARATION | PLANNED / NOT_RUN |
| SEC11 | Pattern completion via graph activation diffusion | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T01,P06-T05,P06-T06,P06-T10 | G-GRAPH,G-DIFFUSION | PLANNED / NOT_RUN |
| SEC12 | CDZ binding as address versus reconstruction | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T01,P07-T02,P07-T03,P07-T04 | G-CDZ | PLANNED / NOT_RUN |
| SEC13 | Emotion and salience | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T05,P07-T06,P07-T07 | G-SALIENCE | PLANNED / NOT_RUN |
| SEC14 | Deterministic functional operators and gated policies | [design](MASTER_DEV_PLAN.md#binding) | P01-T06,P04-T01,P04-T02 | G-ACL,G-BINDING | P01 PASS E-P01-003; P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| SEC15 | Temporal identity contradictions corrections and provenance | [design](MASTER_DEV_PLAN.md#identity-time) | P01-T03,P01-T10,P09-T03 | G-TEMPORAL | P01 PASS E-P01-003; later ownership NOT_RUN |
| SEC16 | Complementary learning systems and consolidation | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P08-T01,P08-T02,P08-T04,P08-T06,P08-T07 | G-CONSOLIDATION,G-DELETION | PLANNED / NOT_RUN |
| SEC17 | Read pipeline evidence verification and abstention | [design](MASTER_DEV_PLAN.md#read-flow) | P03-T07,P03-T08,P09-T08 | G-SOURCE,G-ABSTENTION | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| SEC18 | Storage design polyglot stores replication sharding coherence | [design](MASTER_DEV_PLAN.md#operations) | P03-T09,P11-T05,P11-T06,P11-T11 | G-SNAPSHOT,G-OPS | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| SEC19 | Failure containment security privacy and operations | [design](MASTER_DEV_PLAN.md#security) | P11-T10,P12-T02,P12-T03,P12-T06,P12-T08 | G-SECURITY,G-OPS | PLANNED / NOT_RUN |
| SEC20 | Data contracts and reference pseudocode | [design](MASTER_DEV_PLAN.md#contracts) | P01-T02,P01-T07,P06-T05,P03-T10 | G-CONTRACT,G-DIFFUSION,G-BUDGET | P01 PASS E-P01-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| SEC21 | Research hypotheses baselines and ablation matrix | [design](MASTER_DEV_PLAN.md#evaluation) | P02-T07,P04-T08,P06-T10,P13-T01 | G-RESEARCH,G-CONFIRMATORY | P02 mechanics PASS E-P02-003; P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| SEC22 | Datasets and benchmark alignment | [design](MASTER_DEV_PLAN.md#evaluation) | P02-T01,P02-T04,P02-T06,P09-T05,P09-T06 | G-CUSTODY,G-TRANSFER | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| SEC23 | Metrics statistics costs and decision criteria | [design](MASTER_DEV_PLAN.md#evaluation) | P02-T09,P02-T10,P13-T02,P13-T05,P13-T06 | G-RESEARCH,G-CONFIRMATORY | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| SEC24 | Experiment execution sequence | [design](MASTER_DEV_PLAN.md#phase-plan) | P00-T03,P13-T09 | G-DOC,G-REPRODUCIBLE | PLANNED / NOT_RUN |
| SEC25 | Open questions and threats to validity | [design](MASTER_DEV_PLAN.md#evaluation) | P00-T02,P12-T01,P13-T07 | G-DOC,G-SECURITY,G-CONFIRMATORY | PLANNED / NOT_RUN |
| SEC26 | Sources and annotated reference register | [design](MASTER_DEV_PLAN.md#reference-reuse) | P00-T01,P02-T07,P09-T05,P13-T07 | G-REUSE,G-CONFIRMATORY | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| SEC27 | Design decision log all requested revisions | [design](MASTER_DEV_PLAN.md#execution-contract) | P00-T02,P00-T03,P13-T01 | G-DOC,G-CONFIRMATORY | PLANNED / NOT_RUN |
| I1 | Immutable evidence | [design](MASTER_DEV_PLAN.md#scope) | P01-T08,P01-T10 | G-INGEST | P01 PASS E-P01-003; later ownership NOT_RUN |
| I2 | Authority external to similarity | [design](MASTER_DEV_PLAN.md#scope) | P01-T02,P03-T08 | G-SOURCE | P01 PASS E-P01-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| I3 | Stable identity | [design](MASTER_DEV_PLAN.md#scope) | P01-T05,P06-T01 | G-IDENTITY | P01 PASS E-P01-003; later ownership NOT_RUN |
| I4 | Read derive separation | [design](MASTER_DEV_PLAN.md#scope) | P01-T12,P09-T02 | G-INTEGRATION | P01 PASS E-P01-003; later ownership NOT_RUN |
| I5 | Rebuildability | [design](MASTER_DEV_PLAN.md#scope) | P03-T09,P11-T07,P11-T10 | G-SNAPSHOT | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| I6 | ACL before ranking and traversal | [design](MASTER_DEV_PLAN.md#scope) | P01-T06,P06-T03,P12-T03 | G-ACL | P01 PASS E-P01-003; later ownership NOT_RUN |
| I7 | Explicit snapshot correctness | [design](MASTER_DEV_PLAN.md#scope) | P03-T09,P11-T06 | G-SNAPSHOT | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| I8 | Bounded work and compute | [design](MASTER_DEV_PLAN.md#scope) | P03-T10,P06-T09,P12-T07 | G-BUDGET | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| I9 | Two-sided abstention | [design](MASTER_DEV_PLAN.md#scope) | P02-T09,P03-T08,P09-T08 | G-ABSTENTION | P02 mechanics PASS E-P02-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| I10 | Empirical minimalism | [design](MASTER_DEV_PLAN.md#scope) | P04-T09,P06-T12,P13-T07 | G-RESEARCH | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| H1 | Multi-view partial-cue recall | [design](MASTER_DEV_PLAN.md#evaluation) | P04-T08 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| H2 | Shared binding versus simple fusion | [design](MASTER_DEV_PLAN.md#evaluation) | P04-T05,P04-T08 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| H3 | Separation without recall regression | [design](MASTER_DEV_PLAN.md#evaluation) | P05-T07,P05-T08 | G-SEPARATION | PLANNED / NOT_RUN |
| H4 | Diffusion complete evidence and false paths | [design](MASTER_DEV_PLAN.md#evaluation) | P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| H5 | Reconstruction downstream value | [design](MASTER_DEV_PLAN.md#evaluation) | P07-T04 | G-CDZ | PLANNED / NOT_RUN |
| H6 | Salience utility without substitution | [design](MASTER_DEV_PLAN.md#evaluation) | P07-T07 | G-SALIENCE | PLANNED / NOT_RUN |
| H7 | Evidence identity temporal gate value | [design](MASTER_DEV_PLAN.md#evaluation) | P03-T08,P09-T03 | G-ABSTENTION | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| H8 | Consolidation long-horizon correctness | [design](MASTER_DEV_PLAN.md#evaluation) | P08-T08 | G-CONSOLIDATION | PLANNED / NOT_RUN |
| H9 | Projection coherence and revocation | [design](MASTER_DEV_PLAN.md#evaluation) | P11-T06,P11-T09,P11-T10 | G-OPS | PLANNED / NOT_RUN |
| H10 | Compression quality resource frontier | [design](MASTER_DEV_PLAN.md#evaluation) | P10-T07 | G-QUANTIZATION | PLANNED / NOT_RUN |
| E1 | Near-duplicate episode | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P01-T05,P05-T08 | G-IDENTITY | P01 PASS E-P01-003; later ownership NOT_RUN |
| E2 | Partial cue | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P04-T08,P05-T08 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| E3 | Multi-hop | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| E4 | False association hubs | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P06-T09 | G-GRAPH | PLANNED / NOT_RUN |
| E5 | User corrections | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P01-T10,P09-T03 | G-TEMPORAL | P01 PASS E-P01-003; later ownership NOT_RUN |
| E6 | Conflicting authorities | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P03-T08 | G-ABSTENTION | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| E7 | Temporal late arrivals | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P01-T03,P09-T03 | G-TEMPORAL | P01 PASS E-P01-003; later ownership NOT_RUN |
| E8 | Salience dramatic distractors | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P07-T07 | G-SALIENCE | PLANNED / NOT_RUN |
| E9 | Unanswerable twins | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P02-T03,P03-T08 | G-ABSTENTION | P02 mechanics PASS E-P02-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| E10 | ACL neighbor privacy | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P06-T09,P12-T03 | G-ACL | PLANNED / NOT_RUN |
| E11 | Memory poisoning | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P12-T02 | G-SECURITY | PLANNED / NOT_RUN |
| E12 | Storage failure | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P11-T06,P12-T06 | G-OPS | PLANNED / NOT_RUN |
| E13 | Long-run consolidation exceptions | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P08-T07,P08-T08 | G-CONSOLIDATION | PLANNED / NOT_RUN |
| E14 | Cross-language cues | [design](MASTER_DEV_PLAN.md#worked-scenarios) | P04-T08,P09-T04 | G-TRANSFER | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| REV01 | Explicit learning objectives | [design](MASTER_DEV_PLAN.md#execution-contract) | P05-T02,P05-T03 | G-LEARNING | PLANNED / NOT_RUN |
| REV02 | Shared binding versus actual diffusion generation | [design](MASTER_DEV_PLAN.md#execution-contract) | P04-T05,P04-T06,P04-T07 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| REV03 | Separation tradeoff and toy math | [design](MASTER_DEV_PLAN.md#execution-contract) | P05-T05,P05-T06,P05-T07 | G-SEPARATION | PLANNED / NOT_RUN |
| REV04 | Bounded graph activation | [design](MASTER_DEV_PLAN.md#execution-contract) | P06-T05,P06-T06,P06-T09 | G-DIFFUSION | PLANNED / NOT_RUN |
| REV05 | CDZ alternatives | [design](MASTER_DEV_PLAN.md#execution-contract) | P07-T01,P07-T02,P07-T03 | G-CDZ | PLANNED / NOT_RUN |
| REV06 | Emotion versus task salience | [design](MASTER_DEV_PLAN.md#execution-contract) | P07-T05,P07-T06,P07-T07 | G-SALIENCE | PLANNED / NOT_RUN |
| REV07 | Functional neural mapping caveats | [design](MASTER_DEV_PLAN.md#execution-contract) | P04-T01,P13-T07 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| REV08 | Deterministic rules no heavy hypernetwork core | [design](MASTER_DEV_PLAN.md#execution-contract) | P01-T06,P04-T02 | G-BINDING | P01 PASS E-P01-003; P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| REV09 | Atom identity and provenance | [design](MASTER_DEV_PLAN.md#execution-contract) | P01-T02,P01-T05,P01-T09 | G-SOURCE | P01 PASS E-P01-003; later ownership NOT_RUN |
| REV10 | Authority storage and replication | [design](MASTER_DEV_PLAN.md#execution-contract) | P11-T01,P11-T06,P11-T11 | G-OPS | PLANNED / NOT_RUN |
| REV11 | No factual read-time mutation | [design](MASTER_DEV_PLAN.md#execution-contract) | P01-T12,P09-T02 | G-INTEGRATION | P01 PASS E-P01-003; later ownership NOT_RUN |
| REV12 | Five statuses and abstention | [design](MASTER_DEV_PLAN.md#execution-contract) | P03-T08,P09-T08 | G-ABSTENTION | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| REV13 | Replace ternary analogy with retrieval quantization | [design](MASTER_DEV_PLAN.md#execution-contract) | P10-T01,P10-T02,P10-T03,P10-T04 | G-QUANTIZATION | PLANNED / NOT_RUN |
| REV14 | Failures security and operations | [design](MASTER_DEV_PLAN.md#execution-contract) | P11-T10,P12-T06,P12-T09 | G-SECURITY | PLANNED / NOT_RUN |
| B0 | Shared latent binding variants | [design](MASTER_DEV_PLAN.md#binding) | P03-T03 | G-BINDING | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| B1 | Shared latent binding variants | [design](MASTER_DEV_PLAN.md#binding) | P04-T03 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| B2 | Shared latent binding variants | [design](MASTER_DEV_PLAN.md#binding) | P04-T04 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| B3 | Shared latent binding variants | [design](MASTER_DEV_PLAN.md#binding) | P04-T05 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| B4 | Shared latent binding variants | [design](MASTER_DEV_PLAN.md#binding) | P04-T06 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| B5 | Shared latent binding variants | [design](MASTER_DEV_PLAN.md#binding) | P04-T07 | G-BINDING | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; B5 explicitly FEATURE_NOT_SUPPORTED |
| T0 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T1 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T2 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T3 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T4 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T5 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T6 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| T7 | Loss factorial T0-T7 | [design](MASTER_DEV_PLAN.md#learning) | P05-T02,P05-T03,P05-T09 | G-LEARNING | PLANNED / NOT_RUN |
| G0 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P03-T05,P06-T10 | G-DIFFUSION | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE; later ownership NOT_RUN |
| G1 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T04,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| G2 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T04,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| G3 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T05,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| G4 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T06,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| G5 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T07,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| G6 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T07,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| G7 | Graph completion arms | [design](MASTER_DEV_PLAN.md#graph-algorithms) | P06-T07,P06-T10 | G-DIFFUSION | PLANNED / NOT_RUN |
| CDZ-A | CDZ interpretations | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T01,P07-T04 | G-CDZ | PLANNED / NOT_RUN |
| CDZ-B | CDZ interpretations | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T02,P07-T04 | G-CDZ | PLANNED / NOT_RUN |
| CDZ-C | CDZ interpretations | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T03,P07-T04 | G-CDZ | PLANNED / NOT_RUN |
| S0 | Salience controls | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P04-T02,P07-T07 | G-SALIENCE | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE; later ownership NOT_RUN |
| S1 | Salience controls | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T05,P07-T07 | G-SALIENCE | PLANNED / NOT_RUN |
| S2 | Salience controls | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P07-T06,P07-T07 | G-SALIENCE | PLANNED / NOT_RUN |
| C0 | Consolidation variants | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P08-T07,P08-T08 | G-CONSOLIDATION | PLANNED / NOT_RUN |
| C1 | Consolidation variants | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P08-T02,P08-T08 | G-CONSOLIDATION | PLANNED / NOT_RUN |
| C2 | Consolidation variants | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P08-T03,P08-T08 | G-CONSOLIDATION | PLANNED / NOT_RUN |
| C3 | Consolidation variants | [design](MASTER_DEV_PLAN.md#optional-mechanisms) | P08-T05,P08-T08 | G-CONSOLIDATION | PLANNED / NOT_RUN |
| R0 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P03-T02,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| R1 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P03-T03,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| R2 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P03-T05,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| R3 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P03-T06,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| R4 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P09-T10,P09-T13,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| R5 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P09-T11,P09-T13,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| R6 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P09-T12,P09-T13,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| R7 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P04-T03,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| R8 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P04-T05,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| R9 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P06-T05,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| R10 | Required comparator families; R4-R6 version/native deployment verified before study | [design](MASTER_DEV_PLAN.md#evaluation) | P06-T11,P02-T07 | G-RESEARCH | P02 mechanics PASS E-P02-003; later ownership NOT_RUN |
| ST0 | Blueprint experimental Stage0 | [design](MASTER_DEV_PLAN.md#phase-plan) | P03-T12 | G-RESEARCH | P03 local contract PASS E-P03-003; scientific outcome INCONCLUSIVE |
| ST1 | Blueprint experimental Stage1 | [design](MASTER_DEV_PLAN.md#phase-plan) | P05-T09 | G-RESEARCH | PLANNED / NOT_RUN |
| ST2 | Blueprint experimental Stage2 | [design](MASTER_DEV_PLAN.md#phase-plan) | P06-T12 | G-RESEARCH | PLANNED / NOT_RUN |
| ST3 | Blueprint experimental Stage3 | [design](MASTER_DEV_PLAN.md#phase-plan) | P08-T08 | G-RESEARCH | PLANNED / NOT_RUN |
| ST4 | Blueprint experimental Stage4 | [design](MASTER_DEV_PLAN.md#phase-plan) | P09-T09 | G-RESEARCH | PLANNED / NOT_RUN |
| ST5 | Blueprint experimental Stage5 | [design](MASTER_DEV_PLAN.md#phase-plan) | P12-T09 | G-RESEARCH | PLANNED / NOT_RUN |
| ST6 | Blueprint experimental Stage6 | [design](MASTER_DEV_PLAN.md#phase-plan) | P13-T09 | G-REPRODUCIBLE | PLANNED / NOT_RUN |
| OQ01 | Facet complementary signal | [design](MASTER_DEV_PLAN.md#evaluation) | P04-T08 | G-RESEARCH | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| OQ02 | Shared code information loss | [design](MASTER_DEV_PLAN.md#evaluation) | P04-T08 | G-RESEARCH | P04 local investigation PASS E-P04-005; scientific INCONCLUSIVE |
| OQ03 | Graph extraction artifacts | [design](MASTER_DEV_PLAN.md#evaluation) | P06-T02 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ04 | Activation locality | [design](MASTER_DEV_PLAN.md#evaluation) | P06-T10 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ05 | Cue ambiguity | [design](MASTER_DEV_PLAN.md#evaluation) | P05-T08 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ06 | Loss gradient conflict | [design](MASTER_DEV_PLAN.md#evaluation) | P05-T04 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ07 | Rare exception retention | [design](MASTER_DEV_PLAN.md#evaluation) | P08-T07 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ08 | Graph engine choice | [design](MASTER_DEV_PLAN.md#evaluation) | P11-T01 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ09 | Model geometry upgrades | [design](MASTER_DEV_PLAN.md#evaluation) | P11-T07 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ10 | Source independence | [design](MASTER_DEV_PLAN.md#evaluation) | P08-T01 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ11 | Emotion privacy/fairness | [design](MASTER_DEV_PLAN.md#evaluation) | P07-T07 | G-RESEARCH | PLANNED / NOT_RUN |
| OQ12 | Parameter erasure | [design](MASTER_DEV_PLAN.md#evaluation) | P08-T05,P12-T05 | G-RESEARCH | PLANNED / NOT_RUN |
