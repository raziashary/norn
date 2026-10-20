"""Local synthetic operator CLI; caller identity comes from the trusted host options."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from norn import __version__
from norn.canonical.corrections import CorrectionRequest, retract
from norn.canonical.registry import WriteRequest
from norn.contracts.errors import NornError, require
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
from norn.contracts.identity import Namespace, ObjectRef
from norn.contracts.time import QueryClock, TimeKind, TimeValue, parse_instant
from norn.extraction.atoms import FixtureAtom
from norn.governance.access import HostIdentity
from norn.governance.deletion import purge_status
from norn.governance.temporal import yesterday
from norn.integration.engine import Engine


def fields(data: object, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    require(
        type(data) is dict
        and required <= data.keys()
        and data.keys() <= required | (optional or set()),
        "INVALID_FIELDS",
    )
    return data  # type: ignore[return-value]


def parse_time(raw: object) -> TimeValue:
    data = fields(raw, {"kind"}, {"start", "end", "source_timezone", "precision", "reason"})
    return TimeValue(
        TimeKind(data["kind"]),
        parse_instant(data["start"]) if data.get("start") is not None else None,
        parse_instant(data["end"]) if data.get("end") is not None else None,
        data.get("source_timezone", "UTC"),
        data.get("precision", "microsecond"),
        data.get("reason"),
    )


def parse_value(raw: object, namespace: Namespace) -> TaggedValue:
    data = fields(raw, {"tag", "value"})
    value = data["value"]
    if data["tag"] == "TIME":
        value = parse_time(value)
    elif data["tag"] == "ENTITY_REF":
        ref = fields(value, {"object_id", "kind"})
        value = ObjectRef(namespace, ref["kind"], ref["object_id"])
    return TaggedValue(data["tag"], value)


def parse_write(raw: object, host: HostIdentity) -> tuple[WriteRequest, CorrectionRequest | None]:
    data = fields(
        raw,
        {
            "request_id",
            "delivery",
            "occurrence",
            "content",
            "event_time",
            "observed_at",
            "atoms",
            "schema_version",
        },
        {"correction"},
    )
    require(type(data["content"]) is str and type(data["atoms"]) is list, "INVALID_FIELDS")
    require(len(data["atoms"]) <= 64, "ATOM_BUDGET")
    atoms = []
    for raw_atom in data["atoms"]:
        atom = fields(
            raw_atom,
            {"subject", "predicate", "value", "start", "end", "epistemic"},
            {"original_origin", "qualifiers", "unresolved"},
        )
        qualifiers = atom.get("qualifiers", {})
        require(type(qualifiers) is dict and len(qualifiers) <= 16, "INVALID_QUALIFIERS")
        atoms.append(
            FixtureAtom(
                atom["subject"],
                atom["predicate"],
                parse_value(atom["value"], host.namespace),
                atom["start"],
                atom["end"],
                EpistemicState(
                    Epistemic(atom["epistemic"]),
                    Epistemic(atom["original_origin"]) if atom.get("original_origin") else None,
                ),
                tuple(sorted(qualifiers.items())),
                atom.get("unresolved", False),
            )
        )
    correction = None
    if "correction" in data:
        entry = fields(
            data["correction"],
            {"prior_atom", "classification", "scope", "valid_from", "valid_to", "reason"},
        )
        correction = CorrectionRequest(
            entry["prior_atom"],
            entry["classification"],
            entry["scope"],
            parse_instant(entry["valid_from"]),
            parse_instant(entry["valid_to"]) if entry["valid_to"] else None,
            entry["reason"],
        )
    return (
        WriteRequest(
            data["request_id"],
            host.principal,
            data["delivery"],
            data["occurrence"],
            data["content"].encode(),
            parse_time(data["event_time"]),
            parse_instant(data["observed_at"]),
            tuple(atoms),
            data["schema_version"],
        ),
        correction,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--store", type=Path)
    result.add_argument("--tenant", default="synthetic")
    result.add_argument("--workspace", default="pilot")
    result.add_argument("--partition", default="local")
    result.add_argument("--principal", default="operator")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    relative = commands.add_parser("resolve-time")
    relative.add_argument("relative")
    relative.add_argument("--evaluation-time", required=True)
    relative.add_argument("--timezone", required=True)
    commands.add_parser("init")
    write = commands.add_parser("write")
    write.add_argument("--input", type=Path, required=True)
    read = commands.add_parser("read")
    read.add_argument("event_id")
    read.add_argument("--evaluation-time", required=True)
    read.add_argument("--timezone", required=True)
    read.add_argument(
        "--basis", required=True, choices=["EVENT_TIME", "VALID_TIME", "KNOWLEDGE_AT"]
    )
    read.add_argument("--valid-at", required=True)
    read.add_argument("--knowledge-at", required=True)
    read.add_argument("--snapshot", type=int)
    journal = commands.add_parser("journal")
    journal.add_argument("--after", type=int, default=0)
    journal.add_argument("--limit", type=int, default=100)
    for operation in ("grant", "revoke"):
        command = commands.add_parser(operation)
        command.add_argument("target_principal")
        command.add_argument("operation", choices=["READ", "WRITE", "ADMIN"])
    deny = commands.add_parser("deny")
    deny.add_argument("selector")
    deny.add_argument("--request-id", required=True)
    deny.add_argument("--reason", required=True)
    purge = commands.add_parser("purge-status")
    purge.add_argument("request_id")
    retraction = commands.add_parser("retract")
    retraction.add_argument("atom_id")
    retraction.add_argument("--valid-from", required=True)
    retraction.add_argument("--valid-to")
    retraction.add_argument("--reason", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    return result


def execute(args: argparse.Namespace) -> object:
    if args.command == "resolve-time":
        require(args.relative == "yesterday", "FEATURE_NOT_SUPPORTED")
        evaluation = parse_instant(args.evaluation_time)
        clock = QueryClock(evaluation, args.timezone, "EVENT_TIME", evaluation, evaluation)
        return {
            "evaluation_time": args.evaluation_time,
            "timezone": args.timezone,
            "resolved": yesterday(clock).payload(),
        }
    if args.command == "capabilities":
        return {
            "version": __version__,
            "profile": "synthetic-local-canonical-v1",
            "generative_llm": "DISABLED",
            "providers_loaded": [],
            "models_loaded": [],
            "search": "FEATURE_NOT_SUPPORTED",
            "external_workers": "FEATURE_NOT_SUPPORTED",
            "physical_purge": "PENDING_ONLY",
            "runtime_schema": 2,
        }
    require(args.store is not None, "STORE_REQUIRED")
    host = HostIdentity(Namespace(args.tenant, args.workspace, args.partition), args.principal)
    with Engine(args.store, host, create=args.command == "init") as engine:
        match args.command:
            case "init":
                engine.access.bootstrap()
                return {"initialized": True, "namespace": host.namespace.key}
            case "write":
                with args.input.open("rb") as stream:
                    raw = stream.read(2_097_153)
                require(len(raw) <= 2_097_152, "REQUEST_BUDGET")
                request, correction = parse_write(json.loads(raw), host)
                return engine.write(request, correction=correction)
            case "read":
                clock = QueryClock(
                    parse_instant(args.evaluation_time),
                    args.timezone,
                    args.basis,
                    parse_instant(args.valid_at),
                    parse_instant(args.knowledge_at),
                    args.snapshot,
                )
                return engine.read(args.event_id, clock).serialize()
            case "journal":
                return engine.journal(args.after, args.limit)
            case "grant" | "revoke":
                engine.access.grant(
                    args.target_principal, args.operation, revoke=args.command == "revoke"
                )
                return {"updated": True}
            case "deny":
                return engine.deny(args.selector, args.request_id, args.reason)
            case "purge-status":
                return purge_status(engine.registry, args.request_id)
            case "retract":
                seq = retract(
                    engine.registry,
                    args.atom_id,
                    parse_instant(args.valid_from),
                    parse_instant(args.valid_to) if args.valid_to else None,
                    args.reason,
                )
                return {"commit_seq": seq, "status": "RETRACTED"}
            case "backup":
                return engine.backup(args.destination)
    raise NornError("FEATURE_NOT_SUPPORTED")


def main() -> int:
    args = parser().parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True))
        return 0
    except NornError as error:
        print(json.dumps(error.envelope(), sort_keys=True))
        return 2
    except ValueError, TypeError, KeyError, UnicodeError, RecursionError:
        print(json.dumps(NornError("INVALID_REQUEST").envelope(), sort_keys=True))
        return 2
    except sqlite3.Error, OSError:
        print(json.dumps(NornError("STORAGE_UNAVAILABLE", "storage").envelope(), sort_keys=True))
        return 3


if __name__ == "__main__":
    sys.exit(main())
