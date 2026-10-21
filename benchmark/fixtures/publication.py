"""Strict arm-visible schema and iterative custody checks over actual exported input."""

from __future__ import annotations

import ast
import json
from importlib.util import resolve_name
from pathlib import Path
from typing import TYPE_CHECKING, Any

from benchmark.adapters.common import parse_source
from benchmark.adapters.contracts import PublicInput, PublishedSource, Query
from benchmark.fixtures.observations import Observation

if TYPE_CHECKING:
    from benchmark.fixtures.scenarios import Case
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical
from norn.contracts.time import parse_instant

SOURCE_FIELDS = set(PublishedSource.__dataclass_fields__)
QUERY_FIELDS = set(Query.__dataclass_fields__)


def validate_public(payload: dict[str, Any], private_markers: tuple[str, ...] = ()) -> PublicInput:
    require(type(payload) is dict and set(payload) == {"query", "sources"}, "PUBLIC_SCHEMA")
    require(
        type(payload["query"]) is dict and set(payload["query"]) == QUERY_FIELDS,
        "PUBLIC_QUERY_SCHEMA",
    )
    query_raw = dict(payload["query"])
    query_raw["required_capabilities"] = tuple(query_raw["required_capabilities"])
    query = Query(**query_raw)
    require(type(query.max_candidates) is int and 1 <= query.max_candidates <= 1000)
    require(type(query.max_evidence_tokens) is int and 1 <= query.max_evidence_tokens <= 100_000)
    require(type(payload["sources"]) is list and len(payload["sources"]) <= 10_000)
    encoded = canonical(payload)
    require(len(encoded.encode()) <= 16_777_216, "PUBLIC_INPUT_BUDGET")
    require(
        not any(marker in encoded for marker in ("__GOLD_CANARY__", *private_markers)),
        "PRIVATE_INFORMATION_LEAK",
    )
    result = []
    for raw in payload["sources"]:
        require(type(raw) is dict and set(raw) == SOURCE_FIELDS, "PUBLIC_SOURCE_SCHEMA")
        source_raw = dict(raw)
        require(
            type(source_raw["observation"]) is dict
            and set(source_raw["observation"]) == set(Observation.__dataclass_fields__),
            "PUBLIC_OBSERVATION_SCHEMA",
        )
        source_raw["observation"] = Observation(**source_raw["observation"])
        source_raw["allowed_principals"] = tuple(source_raw["allowed_principals"])
        source = PublishedSource(**source_raw)
        require(
            source.namespace == query.namespace and query.principal in source.allowed_principals,
            "PUBLIC_PERMISSION_LEAK",
        )
        require(
            parse_instant(source.observation.recorded_at) <= parse_instant(query.knowledge_at),
            "PUBLIC_TEMPORAL_LEAK",
        )
        parse_source(source)
        result.append(source)
    require(len({s.source_id for s in result}) == len(result), "DUPLICATE_PUBLISHED_SOURCE")
    return PublicInput(query, tuple(result))


def publish(case: Case, hidden_markers: tuple[str, ...] = ()) -> PublicInput:
    candidate = PublicInput(case.query, case.sources)
    return validate_public(
        json.loads(canonical(candidate.payload())),
        (*hidden_markers, *case.gold.forbidden_sources, *case.gold.forbidden_canaries),
    )


def check_import_barrier(runtime_root: Path, adapter_root: Path) -> None:
    """AST import checks plus dynamic-import denial; no recursive visitor calls."""
    for root in (runtime_root, adapter_root):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            nodes = list(ast.walk(tree))
            unsafe_calls = {"__import__", "import_module", "eval", "exec"}
            # A renamed direct import retains the same forbidden capability.
            for node in nodes:
                if isinstance(node, ast.ImportFrom):
                    unsafe_calls.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name in {"__import__", "import_module", "eval", "exec"}
                    )
            for node in nodes:
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    package = "norn" if root == runtime_root else "benchmark.adapters"
                    subpackage = path.relative_to(root).parent.parts
                    package = ".".join((package, *subpackage))
                    try:
                        module = resolve_name("." * node.level + (node.module or ""), package)
                    except ImportError:
                        raise NornError("INVALID_IMPORT_SCOPE") from None
                    modules.append(module)
                    modules.extend(module + "." + alias.name for alias in node.names)
                if root == runtime_root:
                    require(
                        not any(m == "benchmark" or m.startswith("benchmark.") for m in modules),
                        "RUNTIME_EVALUATOR_IMPORT",
                    )
                else:
                    require(
                        not any(
                            m.startswith(
                                (
                                    "benchmark.fixtures.world",
                                    "benchmark.runs",
                                    "benchmark.fixtures.scenarios",
                                )
                            )
                            for m in modules
                        ),
                        "ADAPTER_GOLD_IMPORT",
                    )
                if isinstance(node, ast.Call):
                    name = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                    )
                    require(
                        name not in unsafe_calls,
                        "DYNAMIC_IMPORT_OR_EXECUTION",
                    )
