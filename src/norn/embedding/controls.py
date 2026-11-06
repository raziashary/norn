"""Operator check of the pinned model workers: positive controls plus real cancel/deadline.

Run with ``python -m norn.embedding.controls <model-root> --enable-models [--check-controls]``.
Kept apart from ``baseline`` so the production worker module carries no command-line harness.
"""

import json
import multiprocessing
import time
from pathlib import Path

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical
from norn.embedding.baseline import LocalModels, ModelWorker, vector


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--enable-models", action="store_true")
    parser.add_argument("--check-controls", action="store_true")
    args = parser.parse_args()
    deadline = time.monotonic() + 120

    def checkpoint() -> None:
        require(time.monotonic() < deadline, "MODEL_CHECK_DEADLINE")

    with ModelWorker(
        args.root, "encoder", enabled=args.enable_models, checkpoint=checkpoint
    ) as worker:
        result = worker.call(
            ("query: where did Alex park?", "passage: Alex parked in ZoneA."), checkpoint=checkpoint
        )
        values = [vector(v) for v in result["values"]]
        print(
            canonical(
                {
                    "encoder": worker.metadata,
                    "dimension": len(values[0]),
                    "input_tokens": result["input_tokens"],
                    "finite_normalized": True,
                }
            )
        )
    if args.check_controls:
        from threading import Event, Timer

        for mode in ("cancel", "deadline"):
            models = LocalModels(args.root, enabled=args.enable_models)
            models.infer("encoder", ("query: warmup",), QueryBudget(120_000))
            require(models.worker is not None)
            pid = models.worker.process.pid if models.worker is not None else None
            cancel = Event()
            budget = QueryBudget(50 if mode == "deadline" else 120_000, cancel)
            timer = Timer(0.05, cancel.set) if mode == "cancel" else None
            if timer is not None:
                timer.start()
            try:
                models.infer(
                    "encoder", tuple("passage: " + "parking " * 4000 for _ in range(8)), budget
                )
                raise AssertionError("native control did not interrupt")
            except NornError as error:
                require(
                    error.code == ("QUERY_CANCELLED" if mode == "cancel" else "QUERY_DEADLINE"),
                    "WRONG_NATIVE_CONTROL_FAILURE",
                )
                require(
                    models.worker is None
                    and pid not in {p.pid for p in multiprocessing.active_children()},
                    "ORPHAN_MODEL_WORKER",
                )
                print(
                    canonical(
                        {
                            "control": mode,
                            "reason": error.code,
                            "owned_worker_exited": True,
                            "attempts": budget.model_calls,
                            "reserved_tokens": budget.model_tokens,
                        }
                    )
                )
            finally:
                models.close()
                if timer is not None:
                    timer.cancel()
                    timer.join(1)
    with ModelWorker(
        args.root, "reranker", enabled=args.enable_models, checkpoint=checkpoint
    ) as worker:
        result = worker.call(
            ("Alex parked in ZoneA.", "A cat is sleeping."),
            query="Where did Alex park?",
            checkpoint=checkpoint,
        )
        require(result["values"][0] > result["values"][1], "RERANK_POSITIVE_CONTROL")
        print(
            json.dumps(
                {
                    "reranker": worker.metadata,
                    "scores": result["values"],
                    "input_tokens": result["input_tokens"],
                }
            )
        )


if __name__ == "__main__":
    main()
