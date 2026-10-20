# Risks and open questions

Updated 20 October 2026 (Asia/Bangkok). Owners are roles, not invented named assignees. A pending decision blocks dependent work only; document creation can complete without pretending runtime choices accepted.

| ID | Mechanism / consequence | Owner and decision point | Mitigation / proof | State |
|---|---|---|---|---|
| Q01 | Python/uv setup accepted, package/layout/dependencies still proposed | User; Phase 1 GO and ADR-0002 | Reuse existing venv; resolve remaining package decisions before binding actual commands | PARTIALLY_RESOLVED |
| Q02 | RETRACTED as epistemic value conflicts with independent origin/status | User; before P01-T02, ADR-0003 | Preserve all external values and original provenance; approve internal mapping explicitly | OPEN |
| Q03 | Immutable evidence versus physical erasure/audit/backups/model parameters | User; before retention/private data, ADR-0004 | Synthetic-only pilot, serving denial first, policy-specific purge receipts and restore tests | OPEN |
| Q04 | Timezone/precision/as-of basis and snapshot security ambiguity | User; before P01 temporal freeze, ADR-0005 | Explicit clocks, intervals/unknowns, current security on old content | OPEN |
| Q05 | Copying tightly coupled or changing Palladion code imports foreign contracts/licenses | Main plus user; before any port, ADR-0006 | Pin verified source, license/fork delta and real Norn consumer proof; no foreign checkout import | OPEN |
| Q06 | Groq/options accepted; API availability, embedding/training/backends/hardware/budgets unknown | User; authorized implementation and ADR-0007/0010 | Explicit model selection, verify IDs/account at first authorized call, pins and bounded compute | PARTIALLY_RESOLVED |
| Q07 | Local outbox versus delayed distributed track could confuse pilot guarantees | User; before schema, ADR-0009 | Local atomic journal early, external delivery/leases/recovery measured P11 | OPEN |
| R01 | Facets duplicate signal; larger backbone explains gains | Main; P04 | Same-capacity single encoder and conditional view ablations | UNMEASURED |
| R02 | Shared code/separation destroys partial-cue generalization | Main; P04/P05 | Multi-positive ambiguity, same-event positives, held-out identity and cue curves | UNMEASURED |
| R03 | Graph extraction/hubs/wrong seeds create spurious identity or causal chains | Main; P06 | Gold/derived tracks, edge quality, typed/current eligibility, fixed-seed BFS/PPR controls | UNMEASURED |
| R04 | Generative reconstruction makes plausible false facets | Main; P07 | Exact CDZ-A control; categorical/source distortion and downstream checks | UNMEASURED |
| R05 | Salience proxy introduces language bias, intrusive inference or irrelevant priority | Main; P07 | S0/S2 controls, neutral tasks, explicit scope, bounded features, no diagnosis | UNMEASURED |
| R06 | Consolidation launders copied poison, loses exceptions or survives source deletion | Main; P08/P12 | Dependence groups, preserved raw episodes, gate/revoke lineage and rare-event replay | UNMEASURED |
| R07 | Hidden truth leaks into IDs/prompts/graph or random paraphrase splits | Main/evaluator; P02 onward | Custody barriers, canaries, family/entity split before paraphrases, sealed manifest | UNMEASURED |
| R08 | Required comparator unavailable or has unequal native source visibility | Main; P02/P13 | Capability/unsupported records, common-input versus native tracks, honest claim limitation | UNMEASURED |
| R09 | Numeric promotion targets invented or changed after results | User/evaluator; before locked seal | Pilot power/practical-effect estimates then freeze, preserve retest/seal history | OPEN |
| R10 | Post-filter-only search or stale permissions leak via traversal/count/rank/context | Main; P01/P03/P06/P12 | Presearch eligible set, current recheck and full-output canaries; no ACL waiver | UNMEASURED |
| R11 | Projection lag/dual writes/worker retry falsely advertise current snapshot | Main; P03/P11 | Atomic journal, exact manifests, fencing, contiguous watermarks, crash/replay | UNMEASURED |
| R12 | Replica/shard/cache architecture adds operational burden without algorithm benefit | Main/user; P11 | Fixed-algorithm single-node control; workload-locality/lag/cost measurement | UNMEASURED |
| R13 | Synthetic/public QA results do not transfer to agent experience | Main; P09 | Reviewed source-compatible external and trajectory tracks; separate scope statements | UNMEASURED |
| R14 | Documentation checker passes despite semantic plan omission | Main/end reviewer; P00 and all closeouts | Full blueprint requirement-by-requirement manual review independent of structural CLI | ACTIVE |

For a new finding, record source/mechanism/consequence, exact affected task/consumer, severity, evidence, options, recommendation, owner answer and disposition. A substantive unresolved issue keeps its affected capability/gate open; do not hide it under a green aggregate. Retain false/refuted claims as struck history with correction mechanism and new evidence.
