"""Credential-free synthetic harness commands; no native arm or efficacy substitute."""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from benchmark.fixtures.audit import load_attestations, load_judgments, write_audit_pack
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs.manifest import file_digest, write_once
from benchmark.runs.runner import CONTROL_NAMES, run_controls
from benchmark.runs.validate import validate_run
from benchmark.statistics.calibration import fit, proper_scores
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical


def _evidence_status(directory: Path, attestation: Path | None, development_only: bool) -> str:
    """ADR-0027 Q-F for the held-out and factorial run kinds: attest, or label development-only."""
    from benchmark.runs.seal import verify
    from benchmark.runs.validate import require_attestation

    status = require_attestation(attestation, development_only)
    if attestation is not None:
        verify(directory, attestation)
    return status


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run-controls", help="Construct and run declared diagnostic controls")
    run.add_argument("directory", type=Path)
    run.add_argument("--seed", type=int, default=47)
    run.add_argument(
        "--partition", choices=("smoke", "development", "calibration"), default="smoke"
    )
    run.add_argument("--role", choices=("smoke", "trainer", "tuner", "calibrator"), default="smoke")
    run.add_argument(
        "--arms",
        nargs="+",
        choices=(*CONTROL_NAMES, "native:R4", "native:R5", "native:R6"),
        default=["perfect", "empty", "shuffled"],
    )
    run.add_argument("--sample-only", action="store_true")
    run.add_argument("--judgments", type=Path)
    run.add_argument("--attestation", type=Path)
    validate = commands.add_parser("validate", help="Reopen every artifact and planned pair")
    validate.add_argument("directory", type=Path)
    validate.add_argument("--report", type=Path)
    validate.add_argument("--model-root", type=Path)
    validate.add_argument("--attestation", type=Path)
    validate.add_argument("--development-only", action="store_true")
    seal = commands.add_parser(
        "seal", help="Write an external attestation of a finished run (outside the run directory)"
    )
    seal.add_argument("directory", type=Path)
    seal.add_argument("--output", type=Path, required=True)
    verify_seal = commands.add_parser("verify-seal", help="Recompute a run against its attestation")
    verify_seal.add_argument("directory", type=Path)
    verify_seal.add_argument("attestation", type=Path)
    baseline = commands.add_parser(
        "run-baselines", help="Explicit real R0-R3 development experiment"
    )
    baseline.add_argument("directory", type=Path)
    baseline.add_argument("--model-root", type=Path, required=True)
    baseline.add_argument("--enable-models", action="store_true")
    baseline.add_argument("--sample-only", action="store_true")
    baseline.add_argument("--seed", type=int, default=47)
    baseline_report = commands.add_parser(
        "baseline-report", help="Reopen and score real baseline artifacts"
    )
    baseline_report.add_argument("directory", type=Path)
    baseline_report.add_argument("--model-root", type=Path, required=True)
    baseline_report.add_argument("--output", type=Path, required=True)
    baseline_report.add_argument("--attestation", type=Path)
    baseline_report.add_argument("--development-only", action="store_true")
    for operation in ("prepare", "train", "evaluate", "report", "run"):
        binding = commands.add_parser(
            "binding-" + operation, help="Explicit P04 development " + operation
        )
        binding.add_argument("directory", type=Path)
        if operation != "train":
            binding.add_argument("--model-root", type=Path, required=True)
        if operation in ("prepare", "evaluate", "run"):
            binding.add_argument("--enable-models", action="store_true")
        if operation in ("prepare", "run"):
            binding.add_argument("--smoke", action="store_true")
        if operation == "report":
            binding.add_argument("--output", type=Path, required=True)
            binding.add_argument("--attestation", type=Path)
            binding.add_argument("--development-only", action="store_true")
    for operation in ("prepare", "train", "report", "run"):
        factorial = commands.add_parser(
            "factorial-" + operation, help="Explicit P05 loss-factorial " + operation
        )
        factorial.add_argument("directory", type=Path)
        if operation != "train":
            factorial.add_argument("--model-root", type=Path, required=True)
            factorial.add_argument("--enable-models", action="store_true")
        if operation in ("prepare", "run"):
            factorial.add_argument("--wall-cap-seconds", type=float, required=True)
            factorial.add_argument("--smoke", action="store_true")
        if operation == "report":
            factorial.add_argument("--output", type=Path, required=True)
            factorial.add_argument("--attestation", type=Path)
            factorial.add_argument("--development-only", action="store_true")
    diagnostics = commands.add_parser(
        "factorial-diagnostics", help="Explicit P05 gradient-conflict and collapse diagnostics"
    )
    diagnostics.add_argument("directory", type=Path)
    diagnostics.add_argument("--output", type=Path, required=True)
    diagnostics.add_argument("--wall-cap-seconds", type=float, required=True)
    for operation in ("prepare", "score", "select", "report"):
        heldout = commands.add_parser(
            "heldout-" + operation, help="Explicit P05 held-out development retrieval " + operation
        )
        heldout.add_argument("directory", type=Path)
        if operation == "prepare":
            heldout.add_argument("--factorial", type=Path, required=True)
            heldout.add_argument("--source", type=Path, required=True)
            heldout.add_argument("--smoke", action="store_true")
        else:
            heldout.add_argument("--model-root", type=Path, required=True)
        if operation in ("prepare", "score"):
            heldout.add_argument("--wall-cap-seconds", type=float, required=True)
        if operation == "score":
            heldout.add_argument("--role", choices=("tune", "evaluation"), required=True)
            heldout.add_argument("--enable-models", action="store_true")
        if operation == "report":
            heldout.add_argument("--output", type=Path, required=True)
            heldout.add_argument("--attestation", type=Path)
            heldout.add_argument("--development-only", action="store_true")
    separation = commands.add_parser(
        "separation-sweep", help="Explicit P05-T07 offline sparse/dense code sweep (tune role only)"
    )
    separation.add_argument("directory", type=Path)
    separation.add_argument("--output", type=Path, required=True)
    separation.add_argument("--wall-cap-seconds", type=float, required=True)
    cues = commands.add_parser(
        "partial-cues", help="Explicit P05-T08 offline ambiguity/transfer check (tune role only)"
    )
    cues.add_argument("directory", type=Path)
    cues.add_argument("--output", type=Path, required=True)
    cues.add_argument("--wall-cap-seconds", type=float, required=True)
    for toy in ("toy-support", "toy-cues"):
        toy_parser = commands.add_parser(toy, help="Explicit P05 toy-study reproduction")
        toy_parser.add_argument("--output", type=Path, required=True)
    audit = commands.add_parser(
        "audit-pack", help="Render the smoke-tier stratified human review pack"
    )
    audit.add_argument("destination", type=Path)
    audit.add_argument("--seed", type=int, default=47)
    audit.add_argument("--judgments", type=Path)
    audit.add_argument("--attestation", type=Path)
    calibrate = commands.add_parser(
        "calibrate", help="Fit probabilities from a verified calibration run"
    )
    calibrate.add_argument("input_run", type=Path)
    calibrate.add_argument("output", type=Path)
    calibrate.add_argument("--bins", type=int, default=10)
    calibrate.add_argument("--arm", default="confidence")
    calibrate.add_argument("--attestation", type=Path)
    calibrate.add_argument("--development-only", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command.startswith("binding-"):
            from benchmark.runs.binding import evaluate, prepare, train_run

            operation = args.command.removeprefix("binding-")
            if operation == "prepare":
                result = prepare(
                    args.directory, args.model_root, enabled=args.enable_models, smoke=args.smoke
                )
            elif operation == "train":
                result = train_run(args.directory)
            elif operation == "evaluate":
                result = evaluate(args.directory, args.model_root, enabled=args.enable_models)
            else:
                from benchmark.runs.binding_report import report as binding_report

                if operation == "run":
                    prepare(
                        args.directory,
                        args.model_root,
                        enabled=args.enable_models,
                        smoke=args.smoke,
                    )
                    train_run(args.directory)
                    evaluate(args.directory, args.model_root, enabled=args.enable_models)
                # A one-shot run cannot be attested before it exists, so it is never citable.
                report = binding_report(
                    args.directory,
                    args.model_root,
                    None if operation == "run" else args.attestation,
                    development_only=operation == "run" or args.development_only,
                )
                output = args.output if operation == "report" else args.directory / "report.json"
                result = {
                    "pairs": report["pairs"],
                    "outcome": report["scientific_outcome"],
                    "report_digest": write_once(output, report),
                    "arms": report["arms"],
                }
        elif args.command == "toy-support":
            from benchmark.runs import toy_support

            result = toy_support.run(args.output)
        elif args.command == "toy-cues":
            from benchmark.runs import toy_cues

            result = toy_cues.run(args.output)
        elif args.command.startswith("heldout-"):
            from benchmark.runs import loss_heldout

            operation = args.command.removeprefix("heldout-")
            if operation == "prepare":
                result = loss_heldout.prepare(
                    args.directory,
                    args.factorial,
                    args.source,
                    wall_cap_seconds=args.wall_cap_seconds,
                    smoke=args.smoke,
                )
            elif operation == "score":
                result = loss_heldout.score(
                    args.directory,
                    args.model_root,
                    args.role,
                    enabled=args.enable_models,
                    wall_cap_seconds=args.wall_cap_seconds,
                )
            elif operation == "select":
                result = loss_heldout.select(args.directory, args.model_root)
            else:
                status = _evidence_status(args.directory, args.attestation, args.development_only)
                value = loss_heldout.report(args.directory, args.model_root)
                value["evidence_status"] = status
                result = {
                    "report_digest": write_once(args.output, value),
                    "selected": value["selected"],
                    "verdict": value["verdict"],
                }
        elif args.command == "separation-sweep":
            from benchmark.runs import separation

            result = separation.run(
                args.directory, args.output, wall_cap_seconds=args.wall_cap_seconds
            )
        elif args.command == "partial-cues":
            from benchmark.runs import partial_cues

            result = partial_cues.run(
                args.directory, args.output, wall_cap_seconds=args.wall_cap_seconds
            )
        elif args.command == "factorial-diagnostics":
            from benchmark.runs import loss_diagnostics

            result = loss_diagnostics.run(
                args.directory, args.output, wall_cap_seconds=args.wall_cap_seconds
            )
        elif args.command.startswith("factorial-"):
            from benchmark.runs import loss_factorial

            operation = args.command.removeprefix("factorial-")
            if operation in ("prepare", "run"):
                result = loss_factorial.prepare(
                    args.directory,
                    args.model_root,
                    enabled=args.enable_models,
                    wall_cap_seconds=args.wall_cap_seconds,
                    smoke=args.smoke,
                )
            if operation in ("train", "run"):
                result = loss_factorial.train_run(args.directory)
            if operation in ("report", "run"):
                status = (
                    _evidence_status(args.directory, args.attestation, args.development_only)
                    if operation == "report"
                    else "DEVELOPMENT_ONLY_NOT_CITABLE"
                )
                value = loss_factorial.report(
                    args.directory, args.model_root, enabled=args.enable_models
                )
                value["evidence_status"] = status
                output = args.output if operation == "report" else args.directory / "report.json"
                result = {
                    "scope": value["scope"],
                    "report_digest": write_once(output, value),
                    "reload_ok": value["reload"]["all_within_tolerance"],
                }
        elif args.command == "run-controls":
            result = run_controls(
                args.directory,
                seed=args.seed,
                tier=args.partition,
                role=args.role,
                names=tuple(args.arms),
                sample_only=args.sample_only,
                judgments_path=args.judgments,
                attestation_path=args.attestation,
            )
        elif args.command == "run-baselines":
            result = run_controls(
                args.directory,
                seed=args.seed,
                tier="development",
                role="tuner",
                names=("R0", "R1", "R2", "R3"),
                sample_only=args.sample_only,
                model_root=args.model_root,
                enable_models=args.enable_models,
            )
        elif args.command == "baseline-report":
            from benchmark.runs.baselines import report as baseline_report

            report = baseline_report(
                args.directory,
                args.model_root,
                args.attestation,
                development_only=args.development_only,
            )
            result = {
                "report_digest": write_once(args.output, report),
                "pairs": report["pairs"],
                "scope": report["scope"],
                "arms": report["arms"],
            }
        elif args.command == "validate":
            report = validate_run(
                args.directory,
                model_root=args.model_root,
                attestation=args.attestation,
                development_only=args.development_only,
            )
            if args.report:
                write_once(args.report, report)
            result = {key: value for key, value in report.items() if key != "observations"}
        elif args.command == "seal":
            from benchmark.runs.seal import attest

            result = attest(args.directory, args.output)
        elif args.command == "verify-seal":
            from benchmark.runs.seal import verify

            result = verify(args.directory, args.attestation)
        elif args.command == "audit-pack":
            world = build_world(args.seed, partition(args.seed, "smoke"))
            result = {
                "pack_digest": write_audit_pack(
                    scenarios(world),
                    args.destination,
                    load_judgments(args.judgments) if args.judgments else (),
                    load_attestations(args.attestation, args.judgments)
                    if args.attestation and args.judgments
                    else frozenset(),
                ),
                "human_review": "PENDING; PACK_IS_NOT_A_JUDGMENT",
            }
        else:
            report = validate_run(
                args.input_run,
                attestation=args.attestation,
                development_only=args.development_only,
            )
            require(
                report["partition"] == "calibration" and report["partition_role"] == "calibrator",
                "CALIBRATION_PARTITION_REQUIRED",
            )
            require(args.arm in report["arms"], "CALIBRATION_ARM_MISSING")
            values = tuple(
                (r["confidence"], bool(r["answer"]["correct_supported"]))
                for r in report["observations"]
                if r["arm_id"] == args.arm
                and r["answer"]["observed"]
                and r["confidence"] is not None
            )
            require(bool(values), "NO_CONFIDENCE_OBSERVATIONS")
            source_digest = file_digest(args.input_run / "completion.json")
            model = fit(values, report["partition"], source_digest, args.bins)
            artifact = {
                "calibration": asdict(model),
                "uncalibrated_fit_sample_scores": proper_scores(values),
                "calibrated_fit_sample_scores": proper_scores(
                    tuple((model.predict(p), y) for p, y in values)
                ),
                "evaluation": "NOT_RUN; FIT_SAMPLE_IS_NOT_HELD_OUT_EVIDENCE",
                "lineage": {
                    "completion_digest": source_digest,
                    "manifest_digest": report["manifest_digest"],
                    "arm": args.arm,
                    "evidence_status": report["evidence_status"],
                },
            }
            result = {"artifact_digest": write_once(args.output, artifact), **artifact}
        print(canonical(result))
        return 0
    except NornError as error:
        print(canonical(error.envelope()), file=sys.stderr)
    except OSError, ValueError, TypeError, KeyError, IndexError:
        print(
            canonical(NornError("MALFORMED_OR_UNAVAILABLE_RUN_ARTIFACT").envelope()),
            file=sys.stderr,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
