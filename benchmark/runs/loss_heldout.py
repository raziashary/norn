"""P05-T03 held-out development retrieval of the T0-T7 checkpoints through the engine reader.

The five contrasts, margins, selection rule and arm set below are the owner-approved R09 proposal
(ADR-0027 Q-D, approved 7 November 2026) frozen in code before the first tune-role read. Tune
selects one arm by the declared rule; the evaluation role is then scored once, for that arm and its
two comparators only. Every outcome is development-exploratory (ADR-0027 Q-C option a): the
evaluation role was already reported in P04 and 14 clusters cannot power a +0.05 effect.
"""

import json
import shutil
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from benchmark.runs.binding import Condition, environment, ledger_digest, score_conditions
from benchmark.runs.binding_report import observe
from benchmark.runs.loss_diagnostics import verified_manifest
from benchmark.runs.manifest import code_digest, file_digest, hardware, load, write_once
from benchmark.statistics.paired import PairedValue, adjust_family, paired_difference
from norn.contracts.errors import require
from norn.contracts.identity import canonical, digest
from norn.embedding import checkpoint
from norn.embedding.assets import METHODS, MODELS
from norn.embedding.binding import BindingModel
from norn.retrieval.rerank import EvidenceTokenizer

TRAINED = ("T1", "T2", "T3", "T4", "T5", "T6", "T7")
ROLES = ("tune", "evaluation")
SMOKE_QUERIES = 2
CONFIG: dict[str, Any] = {
    "revision": "loss-heldout-v1",
    "status": "DEVELOPMENT_EXPLORATORY_ADR_0027_Q_C_OPTION_A",
    "baseline_arm": "T0",
    "baseline_condition": "B0_FROZEN_E5_SINGLE_FEATURE",
    "trained_arms": list(TRAINED),
    "variant": "B3",
    "seeds": [11, 29, 47],
    "selection": "HIGHEST_TUNE_C1_POINT_ESTIMATE_TIE_EARLIER_ARM_RAW_LOSS_NEVER_SELECTS",
    "evaluation_arms": "SELECTED_PLUS_T0_PLUS_T1_SCORED_ONCE",
    "bootstrap": {"seed": 47, "samples": 1000, "level": 0.95, "unit": "SCENARIO_FAMILY_CLUSTER"},
    "margins": {"minimum_benefit": 0.05, "maximum_regression": 0.02},
    "metrics": {
        "identity": "episode_top1 True over identity_applicable queries; non-OK counts 0",
        "complete": "complete_set True over full_answerable, cue_missing_fraction 0, cue_variant "
        "positive queries",
        "false_answer": "false_answer True over insufficient_for_full queries; unobserved 0",
        "false_abstention": "false_abstention True over answerable queries; unobserved counts 1",
    },
    "contrasts": {
        "C1": ["identity", "T0", "benefit"],
        "C2": ["identity", "T1", "benefit"],
        "C3": ["complete", "T1", "harm_lower"],
        "C4": ["false_answer", "T1", "harm_upper"],
        "C5": ["false_abstention", "T1", "harm_upper"],
    },
}


def identity(row: dict[str, Any]) -> float | None:
    return float(row["episode_top1"] is True) if row["identity_applicable"] else None


def complete(row: dict[str, Any]) -> float | None:
    if (
        row["answer"]["full_answerable"]
        and row["cue_missing_fraction"] == 0
        and row["cue_variant"] == "positive"
    ):
        return float(row["complete_set"] is True)
    return None


def false_answer(row: dict[str, Any]) -> float | None:
    answer = row["answer"]
    return float(answer["false_answer"] is True) if answer["insufficient_for_full"] else None


def false_abstention(row: dict[str, Any]) -> float | None:
    answer = row["answer"]
    if not answer["answerable"]:
        return None
    return float(answer["false_abstention"] is True or not answer["observed"])


METRICS: dict[str, Callable[[dict[str, Any]], float | None]] = {
    "identity": identity,
    "complete": complete,
    "false_answer": false_answer,
    "false_abstention": false_abstention,
}


def paired_values(rows: list[dict[str, Any]], arm: str, metric: str) -> tuple[PairedValue, ...]:
    """One value per applicable (query, training seed); the untrained T0 has seed ``None``."""
    values = []
    for row in rows:
        value = METRICS[metric](row) if row["arm"] == arm else None
        if value is not None:
            values.append(PairedValue(row["query"], row["cluster"], row["seed"], value))
    return tuple(values)


def _expand(values: tuple[PairedValue, ...], seeds: list[int]) -> tuple[PairedValue, ...]:
    """Repeat a seedless (T0) value once per trained seed so the pairing is balanced."""
    return tuple(
        PairedValue(v.query_id, v.cluster_id, seed, v.value)
        for v in values
        for seed in (seeds if v.training_seed is None else [v.training_seed])
    )


def contrast(
    rows: list[dict[str, Any]], left: str, right: str, metric: str, seeds: list[int]
) -> dict[str, Any]:
    pair = [_expand(paired_values(rows, arm, metric), seeds) for arm in (left, right)]
    require(bool(pair[0]) and bool(pair[1]), "HELDOUT_CONTRAST_EMPTY")
    return {
        "left": left,
        "right": right,
        "metric": metric,
        **paired_difference(pair[0], pair[1], seed=CONFIG["bootstrap"]["seed"]),
    }


def select_arm(tune_c1: dict[str, dict[str, Any]]) -> str:
    """Highest tune C1 point estimate; a tie goes to the earlier (simpler-numbered) arm."""
    require(set(tune_c1) == set(TRAINED), "HELDOUT_SELECTION_ARMS")
    return min(TRAINED, key=lambda arm: (-tune_c1[arm]["difference"], arm))


def benefit(item: dict[str, Any]) -> bool:
    low = (item.get("confidence_interval") or [None])[0]
    return bool(
        low is not None and low > 0 and item["difference"] >= CONFIG["margins"]["minimum_benefit"]
    )


def regression(name: str, item: dict[str, Any]) -> bool | None:
    """Whether a harm contrast stays inside the maximum regression; None if no interval."""
    interval = item.get("confidence_interval")
    if interval is None:
        return None
    bound = CONFIG["margins"]["maximum_regression"]
    if CONFIG["contrasts"][name][2] == "harm_lower":
        return bool(interval[0] >= -bound)
    return bool(interval[1] <= bound)


def verdict(selected: str, contrasts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Margins from the approved proposal; a null result is a valid, recorded outcome."""
    c1 = benefit(contrasts["C1"])
    if selected == "T1":
        outcome = "T1_SELECTED_C1_ONLY" if c1 else "T0_RETAINED_NO_ARM_CLEARS_C1"
        return {"outcome": outcome, "c1_benefit": c1, "regressions": {}}
    c2 = benefit(contrasts["C2"])
    regressions = {name: regression(name, contrasts[name]) for name in ("C3", "C4", "C5")}
    if not c1:
        outcome = "T0_RETAINED_NO_ARM_CLEARS_C1"
    elif not c2:
        outcome = "T1_RETAINED_SELECTED_DOES_NOT_CLEAR_C2"
    elif all(v is True for v in regressions.values()):
        outcome = "MARGINS_MET_DEVELOPMENT_EXPLORATORY"
    else:
        outcome = "BENEFIT_BUT_REGRESSION_NOT_EXCLUDED"
    return {
        "outcome": outcome,
        "c1_benefit": c1,
        "c2_benefit": c2,
        "regressions": regressions,
        "scope": CONFIG["status"],
    }


def _stack(environment: dict[str, Any]) -> dict[str, Any]:
    """Library, provider and thread-count identity; BLAS thread variables differ per run."""
    return {k: v for k, v in environment.items() if k != "head_threads"}


def checkpoint_name(arm: str, seed: int) -> str:
    return f"checkpoints/{arm}-{seed}.json"


def prepare(
    root: Path, factorial: Path, source: Path, *, wall_cap_seconds: float, smoke: bool = False
) -> dict[str, Any]:
    """Copy the held-out roles of a finished P04 development run and bind the T0-T7 checkpoints."""
    require(0 < wall_cap_seconds <= 3600, "HELDOUT_WALL_CAP")
    require(not root.exists(), "RUN_DIRECTORY_EXISTS")
    trained = verified_manifest(factorial)
    training = load(factorial / "training.json")
    origin = load(source / "manifest.json")
    require(
        origin.get("kind") == "P04_BINDING_DEVELOPMENT" and origin["smoke"] is False,
        "HELDOUT_SOURCE_PROFILE",
    )
    require(
        origin["models"] == trained["models"]
        and origin["methods"] == trained["methods"]
        and _stack(origin["environment"]) == _stack(trained["environment"])
        and trained["models"] == json.loads(canonical(MODELS))
        and trained["methods"] == json.loads(canonical(METHODS)),
        "HELDOUT_SUBSTRATE_MISMATCH",
    )
    started = time.monotonic()
    root.mkdir(parents=True)
    planned = {
        role: origin["planned"][role][:SMOKE_QUERIES] if smoke else origin["planned"][role]
        for role in ROLES
    }
    artifacts: dict[str, str] = {}
    for role in ROLES:
        for qid in planned[role]:
            for folder in ("published", "evaluator", "captures"):
                relative = f"{folder}/{role}/{qid}.json"
                require(
                    file_digest(source / relative) == origin["artifacts"][relative],
                    "HELDOUT_SOURCE_CHANGED",
                )
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, target)
                artifacts[relative] = origin["artifacts"][relative]
            shutil.copytree(source / "stores" / role / qid, root / "stores" / role / qid)
    jobs = {(j["arm"], j["seed"]): j for j in training["jobs"]}
    require(set(jobs) == {(a, s) for a in TRAINED for s in CONFIG["seeds"]}, "HELDOUT_JOBS_MISSING")
    checkpoints = {}
    for (arm, seed), job in sorted(jobs.items()):
        require(file_digest(factorial / job["path"]) == job["sha256"], "CHECKPOINT_SOURCE_CHANGED")
        relative = checkpoint_name(arm, seed)
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(factorial / job["path"], root / relative)
        require(file_digest(root / relative) == job["sha256"], "CHECKPOINT_COPY_CHANGED")
        loaded = checkpoint.load(root / relative)
        require(
            loaded.model.variant == CONFIG["variant"]
            and loaded.payload["training"]["seed"] == seed,
            "CHECKPOINT_VARIANT_MISMATCH",
        )
        checkpoints[f"{arm}/{seed}"] = job["sha256"]
    manifest = {
        "schema": 1,
        "kind": "P05_LOSS_HELDOUT",
        "sealed": False,
        "smoke": smoke,
        "code_digest": code_digest(),
        "config": CONFIG,
        "planned": planned,
        "artifacts": artifacts,
        "checkpoints": checkpoints,
        "factorial_run": factorial.name,
        "factorial_manifest_digest": file_digest(factorial / "manifest.json"),
        "factorial_training_digest": file_digest(factorial / "training.json"),
        "source_run": source.name,
        "source_head_threads": origin["environment"]["head_threads"],
        "factorial_head_threads": trained["environment"]["head_threads"],
        "source_manifest_digest": file_digest(source / "manifest.json"),
        "prepare_wall_cap_seconds": wall_cap_seconds,
        "prepare_seconds": time.monotonic() - started,
        "models": MODELS,
        "methods": METHODS,
        "hardware": hardware(),
        "environment": environment(),
        "labels": "CONSTRUCTED_UNAUDITED",
        "visibility": "DEVELOPMENT_ROLES_ONLY; CALIBRATION_AND_LOCKED_NOT_COPIED",
    }
    write_once(root / "manifest.json", manifest)
    return {
        "planned": {k: len(v) for k, v in planned.items()},
        "code_digest": manifest["code_digest"],
    }


def checked(root: Path) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    require(
        manifest.get("schema") == 1
        and manifest.get("kind") == "P05_LOSS_HELDOUT"
        and manifest.get("sealed") is False
        and type(manifest.get("smoke")) is bool,
        "HELDOUT_MANIFEST_PROFILE",
    )
    require(manifest["code_digest"] == code_digest(), "HELDOUT_RUN_CODE_MISMATCH")
    require(manifest["config"] == json.loads(canonical(CONFIG)), "HELDOUT_CONFIG_CHANGED")
    require(manifest["environment"] == environment(), "HELDOUT_ENVIRONMENT_CHANGED")
    for name, sha in manifest["artifacts"].items():
        require(not Path(name).anchor and ".." not in Path(name).parts, "UNSAFE_ARTIFACT_PATH")
        require(file_digest(root / name) == sha, "HELDOUT_ARTIFACT_CHANGED")
    for key, sha in manifest["checkpoints"].items():
        arm, seed = key.split("/")
        require(file_digest(root / checkpoint_name(arm, int(seed))) == sha, "CHECKPOINT_CHANGED")
    return cast(dict[str, Any], manifest)


def conditions(root: Path, role: str) -> list[Condition]:
    """T0 plus the seven trained arms on tune; only T0, T1 and the selected arm afterwards."""
    require(role in ROLES, "HELDOUT_ROLE")
    arms = list(TRAINED)
    if role == "evaluation":
        chosen = load(root / "selection.json")["selected"]
        require(chosen in TRAINED, "HELDOUT_SELECTION_INVALID")
        arms = sorted({"T1", chosen})
    result = [Condition("B0", None, None, {"arm": "T0"})]
    for arm in arms:
        for seed in CONFIG["seeds"]:
            result.append(Condition("B3", seed, root / checkpoint_name(arm, seed), {"arm": arm}))
    return result


def score(
    root: Path, model_root: Path, role: str, *, enabled: bool, wall_cap_seconds: float
) -> dict[str, Any]:
    require(enabled, "LOCAL_MODELS_NOT_ENABLED")
    require(0 < wall_cap_seconds <= 14_400, "HELDOUT_WALL_CAP")
    manifest = checked(root)
    ledger, completion = root / f"ledger-{role}.jsonl", root / f"completion-{role}.json"
    require(not ledger.exists() and not completion.exists(), "HELDOUT_ROLE_ALREADY_SCORED")
    if role == "evaluation":
        # The evaluation role is read once, after the arm was selected on tune and frozen.
        require(
            (root / "selection.json").is_file()
            and load(root / "selection.json")["tune_ledger_digest"]
            == ledger_digest(root / "ledger-tune.jsonl"),
            "HELDOUT_SELECTION_MISSING",
        )
    started = time.monotonic()
    planned, counts, chain = score_conditions(
        root,
        manifest,
        model_root,
        {role: manifest["planned"][role]},
        conditions(root, role),
        ledger,
        deadline=started + wall_cap_seconds,
    )
    value = {
        "role": role,
        "planned": planned,
        "counts": counts,
        "last_digest": chain,
        "ledger_digest": ledger_digest(ledger),
        "manifest_digest": file_digest(root / "manifest.json"),
        "wall_cap_seconds": wall_cap_seconds,
        "elapsed_seconds": time.monotonic() - started,
    }
    write_once(completion, value)
    return {"role": role, "pairs": len(planned), "counts": counts}


def observations(root: Path, model_root: Path, role: str) -> list[dict[str, Any]]:
    """Re-open every ledger row of one role against its sources and score it."""
    manifest = checked(root)
    done = load(root / f"completion-{role}.json")
    ledger = root / f"ledger-{role}.jsonl"
    require(
        done["manifest_digest"] == file_digest(root / "manifest.json")
        and done["ledger_digest"] == ledger_digest(ledger),
        "HELDOUT_COMPLETION_CHANGED",
    )
    models = {}
    for key in manifest["checkpoints"]:
        arm, seed = key.split("/")
        models[arm, int(seed)] = checkpoint.load(root / checkpoint_name(arm, int(seed))).model
    expected = {tuple(p) for p in done["planned"]}
    tokenizer = EvidenceTokenizer(model_root)
    chain, seen, rows = file_digest(root / "manifest.json"), set(), []
    with ledger.open("rb") as stream:
        while raw := stream.readline(262_145):
            require(len(raw) <= 262_144, "HELDOUT_ROW_BUDGET")
            row = json.loads(raw)
            claimed = row.pop("row_digest")
            require(
                row["previous_digest"] == chain and digest(canonical(row).encode()) == claimed,
                "HELDOUT_LEDGER_CHAIN_CHANGED",
            )
            chain = claimed
            key = (row["role"], row["query"], row["variant"], row["seed"], row["arm"])
            require(row["role"] == role and key in expected and key not in seen, "HELDOUT_PAIR")
            seen.add(key)
            model: BindingModel | None = models.get((row["arm"], row["seed"]))
            observation = observe(root, row, model, tokenizer)
            observation["arm"] = row["arm"]
            rows.append(observation)
    require(seen == expected and chain == done["last_digest"], "HELDOUT_PAIR_MISSING")
    return rows


def arm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-arm counts for every declared metric (applicable denominators and failure counts)."""
    result: dict[str, Any] = {}
    for arm in sorted({r["arm"] for r in rows}):
        mine = [r for r in rows if r["arm"] == arm]
        entry: dict[str, Any] = {
            "rows": len(mine),
            "dispositions": dict(Counter(r["disposition"] for r in mine)),
        }
        for name, metric in METRICS.items():
            values = [v for v in (metric(r) for r in mine) if v is not None]
            entry[name] = {
                "applicable": len(values),
                "positive": sum(values),
                "rate": sum(values) / len(values) if values else None,
            }
        entry["privacy_incidents"] = sum(r["answer"]["privacy_incidents"] for r in mine)
        entry["episode_top1_not_observed"] = sum(
            1 for r in mine if r["identity_applicable"] and r["episode_top1"] is None
        )
        result[arm] = entry
    return result


def select(root: Path, model_root: Path) -> dict[str, Any]:
    """Read the tune ledger, report every arm against T0, and freeze the selected arm."""
    rows = observations(root, model_root, "tune")
    seeds = CONFIG["seeds"]
    tune_c1 = {arm: contrast(rows, arm, "T0", "identity", seeds) for arm in TRAINED}
    selected = select_arm(tune_c1)
    value = {
        "role": "tune",
        "selected": selected,
        "rule": CONFIG["selection"],
        "tune_c1_by_arm": tune_c1,
        "summaries": arm_summary(rows),
        "tune_ledger_digest": ledger_digest(root / "ledger-tune.jsonl"),
        "scope": CONFIG["status"],
    }
    return {"digest": write_once(root / "selection.json", value), "selected": selected}


def report(root: Path, model_root: Path) -> dict[str, Any]:
    chosen = load(root / "selection.json")
    selected = chosen["selected"]
    rows = observations(root, model_root, "evaluation")
    seeds = CONFIG["seeds"]
    contrasts = {}
    for name, (metric, right, _kind) in CONFIG["contrasts"].items():
        if selected == "T1" and right == "T1":
            continue
        contrasts[name] = contrast(rows, selected, right, metric, seeds)
    adjusted = adjust_family(contrasts)
    return {
        "schema": 1,
        "scope": CONFIG["status"],
        "selected": selected,
        "selection_digest": file_digest(root / "selection.json"),
        "contrasts": adjusted,
        "verdict": verdict(selected, adjusted),
        "summaries": arm_summary(rows),
        "tune_summaries": chosen["summaries"],
        "tune_c1_by_arm": chosen["tune_c1_by_arm"],
        "config": CONFIG,
        "limits": [
            "Evaluation role was already reported in P04; 14 clusters per role (R33, ADR-0027 Q-C)",
            "Synthetic constructed labels, unaudited; one selection among seven arms",
            "Margins and contrasts are the approved R09 proposal; Holm p reported, not required",
            "Template/category transfer and language transfer not tested (ADR-0027 Q-B)",
            "Reconstruction decoder is training-only and not part of the stored checkpoints",
        ],
    }
