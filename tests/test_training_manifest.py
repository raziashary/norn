import json
from pathlib import Path

import numpy as np
import pytest

from benchmark.fixtures.binding_cases import cases
from benchmark.fixtures.training_pairs import _content, pair_from_case
from benchmark.runs import loss_factorial as lf
from norn.contracts.errors import NornError
from norn.embedding.checkpoint import load as load_checkpoint
from norn.embedding.losses import arm_weights

SEED = 20261021
MODELS = Path(__file__).resolve().parents[1] / ".norn" / "models"


def train_pair(family="E1", variant="positive"):
    case = next(
        c
        for c in cases("train", seed=SEED)
        if c.gold.family == family
        and c.gold.variant == variant
        and c.gold.language == "en"
        and c.gold.cue_missing_fraction == 0.0
        and c.gold.reason != "MENTION_IS_NOT_REQUIREMENT"
    )
    pair, _ = pair_from_case(case, seed=SEED)
    assert pair is not None
    return case, pair


def item(pair, rows, positive, allowed, triples=(), seed=0):
    rng = np.random.default_rng(seed)
    return lf.Item(
        pair,
        tuple(f"s{seed}-{i}" for i in range(rows)),
        rng.normal(size=384),
        rng.normal(size=(rows, 3, 384)),
        rng.normal(size=(rows, 384)),
        np.ones((rows, 3)),
        np.array(positive, dtype=bool),
        np.array(allowed, dtype=bool),
        np.array(triples, dtype=np.int64).reshape(-1, 3),
    )


def test_a_raw_objective_value_can_never_order_the_arms():
    summary = {
        "T1": {"fit_top1": 0.9, "loss": 0.1},
        "T2": {"fit_top1": 0.3, "loss": 0.05},
    }
    assert lf.order_arms(summary, "fit_top1") == ["T1", "T2"]  # comparable diagnostic
    for key in ("loss", "loss_last", "total_loss"):
        with pytest.raises(NornError, match="LOSS_NOT_COMPARABLE"):
            lf.order_arms(summary, key)  # T2's lower raw loss cannot make it the winner


def test_the_factorial_owns_train_artifacts_only():
    lf.train_only({"pairs.json": "x", "published/train/a.json": "x", "captures/train/a.json": "x"})
    for leaked in ("captures/tune/a.json", "published/evaluation/a.json", "evaluator/train/a.json"):
        with pytest.raises(NornError, match="FACTORIAL_HELDOUT_ARTIFACT"):
            lf.train_only({"pairs.json": "x", leaked: "x"})


def test_triples_are_hand_counted_for_the_paraphrase_pair():
    case, pair = train_pair()
    chosen, paraphrase = pair.positives
    contents = {s.source_id: _content(s.observation) for s in case.sources}
    contents.update(
        {n.source_id: _content(n.source.observation) for n in pair.negatives if n.source}
    )
    assert contents[chosen] == contents[paraphrase]  # same event, other language
    ids = (*(s.source_id for s in case.sources), *(n.source_id for n in pair.negatives if n.source))
    rows = lf._triples(pair, ids, contents)
    where = {source_id: i for i, source_id in enumerate(ids)}
    # One corpus near-miss (two fields differ) and three one-field negatives, none unrelated.
    assert len(rows) == 4 and all(r[:2] == [where[chosen], where[paraphrase]] for r in rows)
    assert {r[2] for r in rows} == {where[n.source_id] for n in pair.negatives}
    # Without the paraphrase in memory there is no same-episode pair, hence no separation target.
    assert lf._triples(pair, tuple(i for i in ids if i != paraphrase), contents) == []


def test_batches_put_a_triple_in_every_batch_and_keep_labels_inside_their_query():
    _, pair = train_pair()
    items = tuple(
        item(
            pair,
            5,
            [1, 0, 0, 0, 0],
            [1, 1, 1, 0, 1],
            [[0, 1, 2]] if k % 3 == 0 else [],
            seed=k,
        )
        for k in range(10)
    )
    batches = lf.build_batches(items)
    assert [len(b.queries) for b in batches] == [5, 5]
    for batch in batches:
        assert len(batch.triples) >= 1 and len(batch.facets) == 25
        block = np.arange(len(batch.facets)) // 5
        for q in range(len(batch.queries)):
            # Labels live only in the query's own rows; other queries' rows are not negatives.
            assert (
                not batch.allowed[q][block != q].any() and not batch.positive[q][block != q].any()
            )
        assert all(len({r // 5 for r in row}) == 1 for row in batch.triples.tolist())
    again = lf.build_batches(items)
    assert all(np.array_equal(a.triples, b.triples) for a, b in zip(batches, again, strict=True))
    scarce = tuple(
        item(pair, 3, [1, 0, 0], [1, 1, 1], [[0, 1, 2]] if k < 2 else [], seed=k) for k in range(17)
    )
    with pytest.raises(NornError, match="FACTORIAL_TRIPLES_SCARCE"):
        lf.build_batches(scarce)


def hand_item(pair):
    return item(pair, 4, [1, 0, 0, 0], [1, 1, 1, 0], [[0, 1, 2]], seed=1)


def codes_of(rows):
    def codes(_item):
        return np.array([1.0, 0.0]), np.array(rows)

    return codes


def test_fit_metrics_hand_computed_with_perfect_and_reversed_controls():
    _, pair = train_pair()
    fit = hand_item(pair)
    # Row 3 is excluded from the allowed set and would win if it were counted.
    perfect = [[0.8, 0.6], [0.0, 1.0], [-1.0, 0.0], [1.0, 0.0]]
    good = lf.fit_metrics((fit,), codes_of(perfect), 0.2)
    assert good["fit_top1"] == 1.0 and good["fit_mrr"] == 1.0
    assert good["fit_margin"] == pytest.approx(0.8)  # 0.8 positive vs best negative 0.0
    assert good["triple_order"] == 1.0 and good["triple_gap"] == pytest.approx(1.4)
    assert good["triple_margin_met"] == 1.0 and good["triple_denominator"] == 1
    reversed_codes = [[-1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    bad = lf.fit_metrics((fit,), codes_of(reversed_codes), 0.2)
    assert bad["fit_top1"] == 0.0 and bad["fit_mrr"] == pytest.approx(1 / 3)
    assert bad["fit_margin"] == pytest.approx(-2.0) and bad["triple_order"] == 0.0
    # No negative and no triple: the metric is inapplicable, not zero.
    solo = item(pair, 2, [1, 0], [1, 0], seed=2)
    empty = lf.fit_metrics((solo,), codes_of([[1.0, 0.0], [0.0, 1.0]]), 0.2)
    assert empty["fit_top1"] is None and empty["fit_top1_denominator"] == 0
    assert empty["triple_order"] is None and empty["triple_denominator"] == 0
    assert empty["fit_mrr"] == 1.0 and empty["fit_mrr_denominator"] == 1


@pytest.mark.skipif(not MODELS.is_dir(), reason="pinned local models are absent")
def test_smoke_run_binds_lineage_reloads_every_checkpoint_and_reads_no_heldout_role(tmp_path):
    root = tmp_path / "run"
    lf.prepare(root, MODELS, enabled=True, wall_cap_seconds=1800, smoke=True)
    assert sorted(p.name for p in (root / "captures").iterdir()) == ["train"]
    manifest = lf.checked(root)
    assert (
        manifest["wall_time_cap_seconds"] == 1800 and manifest["labels"] == "CONSTRUCTED_UNAUDITED"
    )
    lf.train_run(root)
    training = json.loads((root / "training.json").read_text(encoding="utf-8"))
    assert training["failures"] == [] and len(training["jobs"]) == 7 * 3
    assert all(n >= 1 for n in training["batches"]["triples"])
    for job in training["jobs"]:
        checkpoint = load_checkpoint(root / job["path"])
        receipt = checkpoint.payload["training"]
        assert checkpoint.sha256 == job["sha256"] and receipt["arm"] == job["arm"]
        assert checkpoint.payload["data_digest"] == training["training_digest"]
        assert receipt["weights"] == dict(arm_weights(job["arm"]).__dict__)
        assert (
            receipt["pairs_sha256"] == manifest["pairs_sha256"] and receipt["backbone"] == "FROZEN"
        )
        assert receipt["decoder_stored"] == "NO_TRAINING_TIME_ONLY"
        assert receipt["nonzero_gradient_steps"] == receipt["updates"] == 16
    result = lf.report(root, MODELS, enabled=True, reload_sample=1)
    reload = result["reload"]
    assert len(reload["rows"]) == 21 and reload["all_checkpoints_match"]
    assert reload["all_within_tolerance"] and all(
        r["compared_sources"] >= 2 for r in reload["rows"]
    )
    assert set(result["summary_mean_over_seeds"]) == set(
        lf.ARMS
    )  # T2/T3/T6 are reported, not dropped
    assert result["selection"].startswith("NONE") and result["held_out"].startswith("NOT_READ")
    # A one-character change to a checkpoint is caught before any score is read.
    target = root / training["jobs"][0]["path"]
    target.write_bytes(target.read_bytes().replace(b"FROZEN", b"FROZEX", 1))
    with pytest.raises(NornError, match="CHECKPOINT_SOURCE_CHANGED"):
        lf.report(root, MODELS, enabled=True, reload_sample=1)
