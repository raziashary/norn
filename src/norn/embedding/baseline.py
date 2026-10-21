"""Pinned FP32 ONNX inference in owned, bounded, explicitly enabled local workers."""

import json
import math
import multiprocessing
import os
import threading
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Protocol, Self, cast

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError, require
from norn.contracts.identity import canonical
from norn.embedding.assets import METHODS, fingerprint, verified
from norn.telemetry.resources import memory


class Transport(Protocol):
    def send_bytes(self, buffer: bytes) -> None: ...
    def recv_bytes(self, maxlength: int) -> bytes: ...


def _send(connection: Transport, message: dict[str, Any]) -> None:
    payload = canonical(message).encode()
    require(len(payload) <= 1_048_576, "MODEL_MESSAGE_BUDGET")
    connection.send_bytes(payload)


def _message(connection: Transport) -> dict[str, Any]:
    value = json.loads(connection.recv_bytes(maxlength=1_048_576))
    require(type(value) is dict, "MODEL_WORKER_PROTOCOL")
    return cast(dict[str, Any], value)


def _worker(connection: Connection, directory: str, kind: str) -> None:
    """Only trusted parent messages enter this private process; never accepts remote IPC."""
    try:
        for name in tuple(os.environ):
            if name.upper() not in {
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "PATH",
                "NUMBER_OF_PROCESSORS",
            }:
                del os.environ[name]
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        import numpy as np
        import onnxruntime as ort  # type: ignore[import-untyped]
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(Path(directory) / "tokenizer.json"))
        method = METHODS[kind]
        tokenizer.enable_truncation(max_length=method["max_length"], strategy="longest_first")
        tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(
            str(Path(directory) / "onnx/model.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        require(session.get_providers() == ["CPUExecutionProvider"], "MODEL_PROVIDER_MISMATCH")
        inputs = tuple(value.name for value in session.get_inputs())
        require(
            set(inputs) <= {"input_ids", "attention_mask", "token_type_ids"}
            and {"input_ids", "attention_mask"} <= set(inputs),
            "MODEL_INPUT_SCHEMA",
        )
        _send(
            connection,
            {
                "ready": True,
                "inputs": inputs,
                "runtime": ort.__version__,
                "fingerprint": fingerprint(kind),
                "provider": "CPUExecutionProvider",
                "memory": memory(),
            },
        )
        while True:
            message = _message(connection)
            require(type(message) is dict and set(message) == {"texts", "query"}, "MODEL_MESSAGE")
            texts = message["texts"]
            require(type(texts) is list and 1 <= len(texts) <= 8, "MODEL_BATCH_BUDGET")
            require(
                all(type(text) is str and 0 < len(text.encode()) <= 65536 for text in texts),
                "MODEL_INPUT_BUDGET",
            )
            if kind == "encoder":
                encoded = tokenizer.encode_batch(texts)
            else:
                query = message["query"]
                require(
                    type(query) is str and 0 < len(query.encode()) <= 65536, "MODEL_INPUT_BUDGET"
                )
                encoded = tokenizer.encode_batch([(query, text) for text in texts])
            arrays = {
                "input_ids": np.asarray([entry.ids for entry in encoded], dtype=np.int64),
                "attention_mask": np.asarray(
                    [entry.attention_mask for entry in encoded], dtype=np.int64
                ),
                "token_type_ids": np.asarray([entry.type_ids for entry in encoded], dtype=np.int64),
            }
            raw = session.run(None, {name: arrays[name] for name in inputs})[0]
            require(raw.dtype == np.float32, "MODEL_DTYPE_SCHEMA")
            if kind == "encoder":
                require(
                    raw.ndim == 3
                    and raw.shape[0] == len(texts)
                    and raw.shape[2] == method["dimension"],
                    "MODEL_OUTPUT_SCHEMA",
                )
                mask = arrays["attention_mask"][:, :, None]
                pooled = (raw * mask).sum(axis=1) / mask.sum(axis=1)
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
                require(
                    bool(np.isfinite(pooled).all()) and bool((norms > 0).all()),
                    "INVALID_MODEL_VECTOR",
                )
                output = (pooled / norms).astype(np.float32).tolist()
            else:
                require(raw.shape == (len(texts), 1), "MODEL_OUTPUT_SCHEMA")
                require(bool(np.isfinite(raw).all()), "NONFINITE_RERANK_SCORE")
                output = raw[:, 0].astype(np.float32).tolist()
            _send(
                connection,
                {
                    "values": output,
                    "input_tokens": sum(sum(e.attention_mask) for e in encoded),
                    "max_length": method["max_length"],
                    "possibly_truncated": any(
                        sum(e.attention_mask) == method["max_length"] for e in encoded
                    ),
                    "memory": memory(),
                },
            )
    except NornError as error:
        _send(connection, {"error": error.code})
    except EOFError, BrokenPipeError:
        pass  # Parent shutdown owns termination; no success is returned.
    except Exception:
        try:
            _send(connection, {"error": "LOCAL_MODEL_FAILURE"})
        except EOFError, BrokenPipeError, OSError:
            pass
    finally:
        connection.close()


class ModelWorker:
    def __init__(
        self,
        root: Path,
        kind: str,
        *,
        enabled: bool,
        checkpoint: Callable[[], None],
        startup_seconds: float = 60,
    ):
        require(enabled is True, "LOCAL_MODELS_NOT_ENABLED")
        require(kind in {"encoder", "reranker"})
        require(0 < startup_seconds <= 120)
        directory = verified(root, kind, checkpoint)
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe(duplex=True)
        self.process = context.Process(
            target=_worker, args=(child, str(directory), kind), daemon=True
        )
        self.kind = kind
        self.closed = False
        try:
            self.process.start()
            child.close()
            self.metadata = self._receive(checkpoint, time.monotonic() + startup_seconds)
            require(
                self.metadata.get("ready") is True
                and self.metadata.get("fingerprint") == fingerprint(kind),
                "MODEL_NOT_READY",
            )
        except BaseException:
            child.close()
            self.close()
            raise

    def _receive(self, checkpoint: Callable[[], None], deadline: float) -> dict[str, Any]:
        while True:
            checkpoint()
            require(time.monotonic() < deadline, "MODEL_DEADLINE")
            require(self.process.is_alive() or self.connection.poll(), "MODEL_WORKER_EXITED")
            if self.connection.poll(0.02):
                try:
                    message = _message(self.connection)
                except EOFError, OSError, ValueError:
                    raise NornError("MODEL_WORKER_PROTOCOL") from None
                require(type(message) is dict, "MODEL_WORKER_PROTOCOL")
                if "error" in message:
                    raise NornError(message["error"], "model")
                return message

    def call(
        self,
        texts: tuple[str, ...],
        *,
        query: str | None = None,
        checkpoint: Callable[[], None],
        seconds: float = 30,
    ) -> dict[str, Any]:
        require(not self.closed and 0 < seconds <= 600, "MODEL_WORKER_CLOSED_OR_BUDGET")
        message = {"texts": list(texts), "query": query}
        require(len(canonical(message).encode()) <= 600_000, "MODEL_MESSAGE_BUDGET")
        deadline = time.monotonic() + seconds
        failures: list[Exception] = []

        def send() -> None:
            try:
                _send(self.connection, message)
            except Exception as error:
                failures.append(error)

        sender = threading.Thread(target=send, name="norn-model-send", daemon=True)
        try:
            checkpoint()
            sender.start()
            while sender.is_alive():
                checkpoint()
                require(time.monotonic() < deadline, "MODEL_DEADLINE")
                sender.join(0.02)
            require(not failures, "MODEL_WORKER_PROTOCOL")
            return self._receive(checkpoint, deadline)
        except BaseException:
            self.close()
            raise
        finally:
            if sender.ident is not None:
                sender.join(2)
                require(not sender.is_alive(), "MODEL_SENDER_CLEANUP")

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(2)
            require(not self.process.is_alive(), "MODEL_WORKER_CLEANUP")
        finally:
            self.connection.close()
            self.process.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class LocalModels:
    """Serial, reusable native inference; switching models releases the old worker."""

    def __init__(self, root: Path, *, enabled: bool):
        self.root = root
        self.enabled = enabled
        self.worker: ModelWorker | None = None
        self.peak_worker_bytes = 0

    def infer(
        self, kind: str, texts: tuple[str, ...], budget: QueryBudget, *, query: str | None = None
    ) -> list[Any]:
        require(1 <= len(texts) <= 8, "MODEL_BATCH_BUDGET")
        reserved = len(texts) * METHODS[kind]["max_length"]
        budget.attempt(reserved)
        if self.worker is not None and self.worker.kind != kind:
            self.close()
        try:
            if self.worker is None:
                self.worker = ModelWorker(
                    self.root, kind, enabled=self.enabled, checkpoint=budget.checkpoint
                )
            result = self.worker.call(
                texts,
                query=query,
                checkpoint=budget.checkpoint,
                seconds=min(600, budget.deadline_ms / 1000),
            )
            budget.complete(reserved, result["input_tokens"])
            budget.model_truncated |= result["possibly_truncated"]
            observed_peak = result["memory"]["peak_working_set_bytes"]
            if observed_peak is not None:
                self.peak_worker_bytes = max(self.peak_worker_bytes, observed_peak)
            require(type(result["values"]) is list, "MODEL_OUTPUT_SCHEMA")
            return cast(list[Any], result["values"])
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.worker is not None:
            self.worker.close()
            self.worker = None


def vector(values: list[float], dimension: int = 384) -> tuple[float, ...]:
    require(
        len(values) == dimension
        and all(type(v) in (float, int) and math.isfinite(v) for v in values),
        "INVALID_VECTOR_GEOMETRY",
    )
    norm = math.sqrt(sum(v * v for v in values))
    require(norm > 0 and abs(norm - 1) <= 1e-4, "INVALID_VECTOR_NORM")
    return tuple(float(v) for v in values)


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
