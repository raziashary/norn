# Evidence log

Updated 20 October 2026 (Asia/Bangkok). Append observations, exact commands, source/artifact versions, exit/result, consumer readback, limits, review findings and cleanup. Evidence is not task status; MDP owns task checkboxes.

## E-DOC-001 — Baseline and source grounding

- Date: 20 October 2026 (Asia/Bangkok).
- Commands: `git status --short --branch`, `git worktree list`, `git log -1 --format='%h %s'`, `git ls-files`, selective `rg --files` and `Get-Content` reads.
- Observed baseline: clean main tracking origin/main, single checkout, `81badbd` initial commit, only blueprint tracked. No Norn runtime/package/schema/tests/data/models existed.
- Vision: complete 27-section blueprint read during the preceding investigation and affected full technical sections revisited for suite authoring. Current file is preserved unchanged.
- References: Palladion development anchors/atomic-card structure and current memory/retrieval/graph/benchmark source inspected read-only; Arcana historical development plan inspected for contract/schema/flow/module/task depth and explicit supersession notice. No foreign file edited or source ported.
- Tools: Python3.14.7 available for docs-only standard-library checker; this does not select the future runtime.
- Scope: source/documentation evidence only. No application, provider, model download, database or listener started.

## E-DOC-002 — Start adversary

- Reviewer: `/root/suite_adversary`, GPT6 Luna, Medium, fresh self-contained context, read-only; no credential access, git changes, runtime tests, providers or extra agents.
- Inputs: complete Norn blueprint, planned suite scope, Palladion MDP format and historical Arcana MDP format.
- Findings: preserve seven epistemic values while resolving retraction/origin; define source/identity/ACL/time contracts; separate immutable history and purge; isolate evaluator gold/splits; distinguish mechanism/composite comparisons and valid negative exits; keep external infrastructure later; enforce PPR global unique and repeated-work/time budgets; checker proves structure not semantics; separate task/gate/efficacy states.
- Main disposition: confirmed obligations incorporated into MDP contracts/schema/flows/algorithms, ADR-0003/0004/0005/0009, custody/research/gate design and readiness semantics. No finding grants runtime approval. Full end review still required.

## E-DOC-003 — Documentation validation and resolution

Validation observed in this checkout:

- `python docs/development/check_docs.py`: exit0; 15 Markdown files (14 suite files plus parent navigation), 139 atomic tasks, 30 gates and 137 coverage rows pass structural checks. P00 tasks were initially unchecked until the full semantic end review; final scope closure is recorded in E-DOC-004.
- `python docs/development/check_docs.py --self-test`: exit0; 15/15 deliberately damaged independent temporary suites rejected for their intended categories: missing document/local target/anchor, duplicate task, missing consumer, missing negative proof, false completed task, undefined/cyclic dependency, undefined gate, missing coverage, stale count, false runtime gate, unknown ADR and duplicate authority.
- In-memory Python `compile` of `check_docs.py`: PASS, no repository bytecode produced. The real documentation CLI is the runnable-output smoke; it needs no runtime/model/service.
- `git diff --check`: exit0. `git diff --exit-code -- docs/vision/subcortical_memory_blueprint.md`: exit0; vision unchanged.
- The first checker run exposed a missing G-RESEARCH gate definition. The actual gate was added rather than weakening checks. Explicit R4/R5/R6 comparator implementation/eligibility cards and capability reconciliation were added; dependent progress/traceability/gate rows were updated and revalidated.
- Validation repeatedly parsed the same large MDP anchors. Measured before optimization: 3.709s per validation; per-validation local anchor reuse measured0.306s afterward with the same valid/invalid controls. This measures only this checker run, not memory-engine performance.
- Independent end review: COMPLETE under `/root/suite_end_review`, GPT6 Luna Medium, fresh context, complete blueprint and all suite/source inputs, read-only, no runtime/provider/credential or git mutation. Verdict: no confirmed remaining material findings after the P04/P05 exact-card resolution; final coverage and closure recorded below.
- Main semantic audit covers blueprint section/invariant/hypothesis/task-family/revision/arm mappings, actual/proposed status, contract/state/clock/erasure ambiguities, scientific custody, consumer/dependency order, optional/negative outcomes, and current mandate. Stage1 preliminary binding versus final loss-study advancement was clarified without claiming a win.
- No server, listener, watcher, database, provider or model download was started. Temporary checker controls use isolated automatically cleaned directories. No runtime gate is marked PASS.

## Runtime evidence boundary

All runtime gates are NOT_RUN. Commands/test paths in the MDP are planned profiles conditional on accepted toolchain and implementation. No source code, SQL migration, trained model, external benchmark result, performance improvement, complete erasure guarantee or production readiness is evidenced by this suite.

## E-DOC-004 — Full completion audit and independent resolution

- Main requirement audit: D01-D08, all27 numbered vision sections, I1-I10, H1-H10, E1-E14, all14 revision rows, B0-B5/T0-T7/G0-G7/CDZ-A-B-C/S0-S2/C0-C3/R0-R10/Stage0-6 and open scientific questions have meaningful task/gate/design mappings. Actual baseline/source and proposed runtime remain distinct.
- Independent sole end reviewer `/root/suite_end_review`, GPT6 Luna Medium, directly read the full1557-line blueprint, all14 development Markdown files plus parent navigation, full MDP/card register, gate catalog and checker source. Verdict: no confirmed material findings. Reviewer made no edits and executed no runtime/tests/provider calls.
- Confirmed finding and resolution: P04 preliminary binding decision could ambiguously appear to block P05 after a negative result. Exact P04-T09 Change/Consumer/Positive proof and P05 Entry now state sequencing/evidence handoff only; predeclared T0-T7/separation remains eligible. P05-T09 owns final Stage1 advancement. Same reviewer verified the correction. L004 preserves mechanism/history.
- Detailed MDP includes typed contracts, normalized canonical/derived schema, event/source/identity/time/ACL controls, write/read/correct/delete/consolidate/recover flows, binding/loss/separation/PPR/heat/CDZ/salience/compression algorithms, module ownership, actual-consumer proofs and 139 exact-file task cards in14 phases. No padding quota or runtime scaffolding was introduced.
- Final status closure: six P00 documentation cards and D01-D08 DONE; G-DOC PASS. Other133 cards PLANNED, other29 gates NOT_RUN, all efficacy outcomes NOT_EVALUATED. Pending ADR owner answers remain pending; they do not block delivery of the planning suite.
- Final validation is repeated against these final status records before local commit: structural CLI,15/15 intended-rejection controls, syntax compile, actual CLI smoke, unchanged vision and diff whitespace. Exact observations are retained in the command output and final verification paragraph below.
- Scope/cleanup:16 new intended files (14 development Markdown, checker, parent docs navigation); no application/runtime dependencies, live data, model assets, provider calls or listeners. No foreign checkout changed. Main push/publication is not authorized.

Final verification observed after status closure: `python docs/development/check_docs.py` exit0 (15 Markdown,139 cards,6 DONE,30 gates,137 rows); `--self-test` exit0 (15/15 intended rejections); in-memory syntax compile PASS; `git diff --exit-code -- docs/vision/subcortical_memory_blueprint.md` exit0; `git diff --check` exit0. The actual documentation entry point and negative controls were exercised; no skipped/runtime check is represented as PASS. Same-reviewer final status resolution is part of this checkpoint's review receipt.

Staged-diff correction: earlier unstaged diff checks did not include new untracked files. The first staged `git diff --cached --check` exposed an extra blank line at the gate catalog EOF; it was removed and the full staged check rerun. The final staged check, rather than the earlier empty tracked diff, is the whitespace proof for the delivered files. Exact16-file scope and staged secret-pattern scan passed; vision is not staged.
