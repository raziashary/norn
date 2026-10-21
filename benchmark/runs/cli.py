"""Credential-free synthetic harness commands; no native arm or efficacy substitute."""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from benchmark.fixtures.audit import write_audit_pack
from benchmark.fixtures.partitions import partition
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from benchmark.runs.manifest import file_digest, write_once
from benchmark.runs.runner import CONTROL_NAMES, run_controls
from benchmark.runs.validate import validate_run
from benchmark.statistics.calibration import fit, proper_scores
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical


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
    validate = commands.add_parser("validate", help="Reopen every artifact and planned pair")
    validate.add_argument("directory", type=Path)
    validate.add_argument("--report", type=Path)
    audit = commands.add_parser(
        "audit-pack", help="Render the smoke-tier stratified human review pack"
    )
    audit.add_argument("destination", type=Path)
    audit.add_argument("--seed", type=int, default=47)
    calibrate = commands.add_parser(
        "calibrate", help="Fit probabilities from a verified calibration run"
    )
    calibrate.add_argument("input_run", type=Path)
    calibrate.add_argument("output", type=Path)
    calibrate.add_argument("--bins", type=int, default=10)
    calibrate.add_argument("--arm", default="confidence")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "run-controls":
            result = run_controls(
                args.directory,
                seed=args.seed,
                tier=args.partition,
                role=args.role,
                names=tuple(args.arms),
                sample_only=args.sample_only,
                judgments_path=args.judgments,
            )
        elif args.command == "validate":
            report = validate_run(args.directory)
            if args.report:
                write_once(args.report, report)
            result = {key: value for key, value in report.items() if key != "observations"}
        elif args.command == "audit-pack":
            world = build_world(args.seed, partition(args.seed, "smoke"))
            result = {
                "pack_digest": write_audit_pack(scenarios(world), args.destination),
                "human_review": "PENDING; PACK_IS_NOT_A_JUDGMENT",
            }
        else:
            report = validate_run(args.input_run)
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
