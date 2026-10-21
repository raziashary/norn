# Risks and open questions

Updated 21 October 2026 (Asia/Bangkok). Owners are roles, not invented named assignees. A pending decision blocks dependent work only; document creation can complete without pretending runtime choices accepted.

| ID | Mechanism / consequence | Owner and decision point | Mitigation / proof | State |
|---|---|---|---|---|
| Q01 | P01 Python/src/tooling/tzdata choices accepted; later model dependencies pending | User; Phase 1 GO and ADR-0002 | Reuse existing venv; ADR-0012 resolves P01 setup; verify installed consumers | PARTIALLY_RESOLVED |
| Q02 | RETRACTED as epistemic value conflicts with independent origin/status | User; before P01-T02, ADR-0003 | Owner approved origin/status mapping; all seven persisted round trips tested | RESOLVED_P01 |
| Q03 | Immutable evidence versus physical erasure/audit/backups/model parameters | User; before retention/private data, ADR-0004 | Synthetic pilot accepted; pending per-artifact purge/backups remain explicit; production policy unresolved | RESOLVED_P01_ONLY |
| Q04 | Timezone/precision/as-of basis and snapshot security ambiguity | User; before P01 temporal freeze, ADR-0005 | Owner approved explicit clocks/current security; deterministic controls pass | RESOLVED_P01 |
| Q05 | Copying tightly coupled or changing Palladion code imports foreign contracts/licenses | Main plus user; before any port, ADR-0006 | Owner approved original implementation without copying; no foreign runtime dependency | RESOLVED_P01 |
| Q06 | Groq/options accepted; API availability, embedding/training/backends/hardware/budgets unknown | User; authorized implementation and ADR-0007/0010 | Explicit model selection, verify IDs/account at first authorized call, pins and bounded compute | PARTIALLY_RESOLVED |
| Q07 | Local outbox versus delayed distributed track could confuse pilot guarantees | User; before schema, ADR-0009 | Owner approved atomic local journal; replay tested; distributed guarantees remain P11 | RESOLVED_P01 |
| Q08 | Scenario-family split could mean category transfer versus held-out instances | User; P02-T04, ADR-0015 | Explicitly approved disjoint instances within every category; template/category transfer not claimed | RESOLVED_P02_ONLY |
| Q09 | Constructed or model-reviewed labels could impersonate human annotation | Owner/evaluator; P02-T05 | Owner personally reviewed42 unchanged hash-bound sample cases; no disputes; remaining cases unaudited | RESOLVED_SAMPLE_ONLY |
| R01 | Facets duplicate signal; larger backbone explains gains | Main; P04 | Same-capacity single encoder and conditional view ablations | UNMEASURED |
| R02 | Shared code/separation destroys partial-cue generalization | Main; P04/P05 | Multi-positive ambiguity, same-event positives, held-out identity and cue curves | UNMEASURED |
| R03 | Graph extraction/hubs/wrong seeds create spurious identity or causal chains | Main; P06 | Gold/derived tracks, edge quality, typed/current eligibility, fixed-seed BFS/PPR controls | UNMEASURED |
| R04 | Generative reconstruction makes plausible false facets | Main; P07 | Exact CDZ-A control; categorical/source distortion and downstream checks | UNMEASURED |
| R05 | Salience proxy introduces language bias, intrusive inference or irrelevant priority | Main; P07 | S0/S2 controls, neutral tasks, explicit scope, bounded features, no diagnosis | UNMEASURED |
| R06 | Consolidation launders copied poison, loses exceptions or survives source deletion | Main; P08/P12 | Dependence groups, preserved raw episodes, gate/revoke lineage and rare-event replay | UNMEASURED |
| R07 | Hidden truth leaks into IDs/prompts/graph or random paraphrase splits | Main/evaluator; P02 onward | P02 tested publication/import/alias/lineage guards and disjoint instances; trusted-process scope, no hostile sandbox or sealed study | PARTIAL_P02_EVIDENCE |
| R08 | Required comparator unavailable or has unequal native source visibility | Main; P02/P13 | P02 contracts/unsupported ledger verified; R0-R10 actual algorithms/native ingestion remain later work | PARTIAL_P02_EVIDENCE |
| R09 | Numeric promotion targets invented or changed after results | User/evaluator; before locked seal | Pilot power/practical-effect estimates then freeze, preserve retest/seal history | OPEN |
| R10 | Post-filter-only search or stale permissions leak via traversal/count/rank/context | Main; P01/P03/P06/P12 | Presearch eligible set, current recheck and full-output canaries; no ACL waiver | UNMEASURED |
| R11 | Projection lag/dual writes/worker retry falsely advertise current snapshot | Main; P03/P11 | Atomic journal, exact manifests, fencing, contiguous watermarks, crash/replay | UNMEASURED |
| R12 | Replica/shard/cache architecture adds operational burden without algorithm benefit | Main/user; P11 | Fixed-algorithm single-node control; workload-locality/lag/cost measurement | UNMEASURED |
| R13 | Synthetic/public QA results do not transfer to agent experience | Main; P09 | Reviewed source-compatible external and trajectory tracks; separate scope statements | UNMEASURED |
| R14 | Documentation checker passes despite semantic plan omission | Main/end reviewer; P00 and all closeouts | Full blueprint requirement-by-requirement manual review independent of structural CLI | ACTIVE |

For a new finding, record source/mechanism/consequence, exact affected task/consumer, severity, evidence, options, recommendation, owner answer and disposition. A substantive unresolved issue keeps its affected capability/gate open; do not hide it under a green aggregate. Retain false/refuted claims as struck history with correction mechanism and new evidence.
