"""Guards of the offline ANN recall measurement and the R2 arm specification."""

from pathlib import Path

import pytest

from benchmark.adapters.r2 import SPEC
from benchmark.runs import ann_recall
from benchmark.runs.manifest import write_once
from norn.contracts.errors import NornError
from norn.embedding.assets import fingerprint

MODELS = Path(__file__).resolve().parents[1] / ".norn" / "models"


def test_measurement_requires_explicit_model_enablement_before_reading_anything(tmp_path):
    with pytest.raises(NornError, match="LOCAL_MODELS_NOT_ENABLED"):
        ann_recall.measure(tmp_path / "missing-run", MODELS, enabled=False)


def test_measurement_refuses_a_run_of_another_kind_or_code_revision(tmp_path):
    manifest = {"run_kind": "BINDING_DEVELOPMENT", "code_digest": "x", "planned_pairs": []}
    write_once(tmp_path / "manifest.json", manifest)
    with pytest.raises(NornError, match="ANN_INPUT_RUN_MISMATCH"):
        ann_recall.measure(tmp_path, MODELS, enabled=True)


def test_measurement_refuses_a_missing_manifest(tmp_path):
    with pytest.raises(NornError, match="ARTIFACT_MISSING_OR_BUDGET"):
        ann_recall.measure(tmp_path, MODELS, enabled=True)


def test_r2_spec_binds_the_pinned_encoder_and_published_source_records_only():
    assert SPEC.arm_id == "R2" and SPEC.track == "COMMON_INPUT"
    assert SPEC.model == fingerprint("encoder")
    assert SPEC.source_visibility == "PUBLISHED_SOURCE_RECORDS_ONLY"
    assert SPEC.capabilities == ("source_read",) and SPEC.tokenizer.startswith("e5-small")
