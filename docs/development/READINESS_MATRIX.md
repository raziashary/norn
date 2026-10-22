# Readiness matrix

Updated 22 October 2026 (Asia/Bangkok). Readiness is evidence of usable behavior, not card count or percentage. The actual repository contains vision, documentation, P01 local canonical implementation (E-P01-003) and P02 synthetic harness (E-P02-003), plus verified local P03 retrieval and P04 binding investigation (E-P03-003/E-P04-005). Source present, tested, installed-consumer proven, measured, and externally transferred are different evidence levels. Algorithm outcome is also separate from engineering completion.

| Capability | Implementation | Behavioral proof | Efficacy outcome | Evidence / blocker |
|---|---|---|---|---|
| Development suite | VERIFIED_DOCUMENTATION | DOC_CLI_AND_REVIEW_PASS | NOT_APPLICABLE | P00 complete; E-DOC-001 through E-DOC-004; no runtime capability implied |
| Canonical contracts and durable source memory | IMPLEMENTED | INSTALLED_SYNTHETIC_CONSUMER_PASS | NOT_EVALUATED | P01 DONE; E-P01-003;63 tests/installed source+CLI/full review; source/graph/worker consumers remain later tasks |
| Hidden world and evaluation harness | IMPLEMENTED | INSTALLED_SYNTHETIC_CONTROLS_PASS | NOT_EVALUATED | P02 DONE; E-P02-003;135 cases/1,620 main pairs/405 installed pairs,42 reviewed sample,97 tests/end review resolved; no actual retrieval/study efficacy |
| Strong R0-R3 and qualified recall | IMPLEMENTED | INSTALLED_SOURCE_NATIVE_AND_MEASUREMENT_PASS | INCONCLUSIVE | P03 DONE12/12; E-P03-003;131 tests,540 pairs/444 tiny-corpus ANN measurements,80-file installed parity, actual CLI/native controls and end review resolved. Field support only; broader semantics/agent/production proof absent |
| Functional views/shared binding | IMPLEMENTED | INSTALLED_SOURCE_NATIVE_MEASUREMENT_AND_REVIEW_PASS | INCONCLUSIVE | P04 DONE9/9; E-P04-005;158 tests, final4,140conditions/12trained jobs, all7 installed binding arms plus R0–R3/native/B5 controls, eight corruption controls and105-file parity. Matched singles erase decomposition-specific gain; annotation defect R15 disclosed; no locked/external/production claim |
| Loss/separation frontier | PLANNED | NOT_RUN | NOT_EVALUATED | P05; T0-T7/toys/real embedding studies absent |
| Typed graph activation | PLANNED | NOT_RUN | NOT_EVALUATED | P06; G0-G7/source path proof absent |
| CDZ and salience | PLANNED | NOT_RUN | NOT_EVALUATED | P04 provides only neutral unobserved S0 masks; P07 CDZ and S1/S2 mechanisms/studies remain absent |
| Consolidation and exception retention | PLANNED | NOT_RUN | NOT_EVALUATED | P08; C0-C3/lineage invalidation absent |
| Next-turn consumer/external transfer | PLANNED | NOT_RUN | NOT_EVALUATED | P09; no host/dataset adapter or real next-turn reader |
| Quantization | PLANNED | NOT_RUN | NOT_EVALUATED | P10; no float32 exact/compression comparison |
| Operational projection/restore | PLANNED | NOT_RUN | NOT_EVALUATED | P11; no real external-store delivery/fault proof |
| Expanded privacy/security envelope | PLANNED | NOT_RUN | NOT_EVALUATED | P12; P01 direct canonical controls proven, expanded privacy envelope remains unexecuted |
| Sealed reproducible study | PLANNED | NOT_RUN | NOT_EVALUATED | P13; no frozen numeric threshold or locked result |

## Promotion rules

A capability advances only with the exact owning test/consumer and declared scope. A successful experiment can conclude REJECT or INCONCLUSIVE and retain a simpler implementation. Efficacy cannot become RETAIN because a source file compiles. An unsupported optional branch gets explicit capability/error/disposition, never a fake test score. Required comparator absence limits the final claim even if supported arms finish. P01-owning gates have phase-local evidence; cross-phase gates remain PARTIAL and other runtime gates NOT_RUN.

Cross-store durability, deletion completion, general semantic correctness, external validity and neural equivalence remain unproven. P03/P04 have descriptive CPU-serial latency/resource observations; saturation, tail SLO and production capacity remain unmeasured. Future negative results and scoped failures remain visible alongside positive results. See MDP phase exits and TESTING_GATES for actual proof contracts.

Owner setup exists, not runtime capability: ignored `.env`/`.venv/` and owner `.gitignore`; venv interpreter3.14.7 verified. Groq generative provider and allowed Qwen3.8 27B/GPT OSS120B/GPT OSS20B options accepted. No key validity/API availability/live inference proof; approved P01 runtime/tooling installation and installed consumer are proven. Explicit P01 GO is recorded in ADR-0012. See ADR-0010/0011 and E-DOC-005.
