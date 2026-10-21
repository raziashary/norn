"""Same-vector HNSW diagnostic on preserved eligible development stores; no graph-memory claim."""

import argparse
import time
from pathlib import Path
from typing import Any

from benchmark.adapters.baseline import host, interpret
from benchmark.fixtures.publication import validate_public
from benchmark.runs.manifest import code_digest, load, write_once
from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.embedding.assets import fingerprint
from norn.embedding.baseline import LocalModels
from norn.integration.engine import Engine
from norn.projection.local import load as load_projection
from norn.retrieval import ann, dense, exact


def measure(root: Path, model_root: Path, *, enabled: bool) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    manifest = load(root / "manifest.json")
    require(
        manifest["run_kind"] == "CONVENTIONAL_RETRIEVAL_DEVELOPMENT"
        and manifest["code_digest"] == code_digest(),
        "ANN_INPUT_RUN_MISMATCH",
    )
    result = []
    omitted = 0
    models = LocalModels(model_root, enabled=enabled)
    try:
        for qid in sorted({pair[0] for pair in manifest["planned_pairs"]}):
            public = validate_public(load(root / "published" / (qid + ".json")))
            request = interpret(public, "R1")
            budget = QueryBudget(120_000)
            with Engine(root / "stores" / qid, host(public)) as engine:
                corpus = exact.eligible(engine, request, budget.checkpoint)
                if not corpus.records:
                    omitted += 1
                    continue
                _snapshot, projection = load_projection(engine, corpus, ("dense",), budget)
                vectors = {
                    key: tuple(value["vector"]) for key, value in projection["dense"].items()
                }
                query = dense.encode((request.text,), models, budget, query=True)[0]
                limit = min(5, len(corpus.records))
                tick = time.perf_counter_ns()
                control = dense.search(corpus, query, vectors, limit)
                exact_ns = time.perf_counter_ns() - tick
                keys = tuple(r.key for r in corpus.records)
                identity = digest(
                    canonical(
                        (fingerprint("encoder"), keys, query, [(key, vectors[key]) for key in keys])
                    ).encode()
                )
                for ef in (16, 32, 64, 128):
                    budget.checkpoint()
                    found, cost = ann.search(
                        corpus, query, vectors, limit, ef_search=ef, expected_keys=keys
                    )
                    result.append(
                        {
                            "query_id": qid,
                            "identity": identity,
                            "k": limit,
                            "exact_ids": [h.record.key for h in control],
                            "ann_ids": [h.record.key for h in found],
                            "recall": len(
                                {h.record.key for h in control} & {h.record.key for h in found}
                            )
                            / limit,
                            "exact_ns": exact_ns,
                            "cost": cost,
                        }
                    )
    finally:
        models.close()
    return {
        "schema": 1,
        "code_digest": code_digest(),
        "encoder": fingerprint("encoder"),
        "measurements": result,
        "empty_eligible_queries": omitted,
        "scope": "SMALL_ELIGIBLE_SYNTHETIC_CORPORA; SAME_VECTOR_APPROXIMATION_ONLY",
        "limits": (
            "Per-query eligible indices; native HNSW measured offline. "
            "Not enabled in serving recall. No semantic superiority, "
            "associative completion or scalability claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--enable-models", action="store_true")
    args = parser.parse_args()
    result = measure(args.run, args.model_root, enabled=args.enable_models)
    print(
        canonical(
            {
                "artifact_digest": write_once(args.output, result),
                "measurements": len(result["measurements"]),
                "empty_eligible_queries": result["empty_eligible_queries"],
            }
        )
    )


if __name__ == "__main__":
    main()
