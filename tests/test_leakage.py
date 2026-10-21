import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmark.fixtures.partitions import partition
from benchmark.fixtures.publication import check_import_barrier, publish, validate_public
from benchmark.fixtures.scenarios import scenarios
from benchmark.fixtures.world import build_world
from norn.contracts.errors import NornError
from norn.contracts.identity import canonical


def test_actual_publication_guards_nested_metadata_canary_scope_and_source_hash():
    world = build_world(47, partition(47, "smoke"))
    for case in scenarios(world):
        public = publish(case, (world.gold_canary,))
        assert "acceptable_sets" not in canonical(public.payload())
        assert "true_cause" not in canonical(public.payload())
    raw = json.loads(canonical(public.payload()))
    raw["graph"] = {"required_slot": "hidden"}
    with pytest.raises(NornError, match="PUBLIC_SCHEMA"):
        validate_public(raw)
    raw = json.loads(canonical(public.payload()))
    raw["query"]["text"] = world.gold_canary
    with pytest.raises(NornError, match="PRIVATE_INFORMATION_LEAK"):
        validate_public(raw, (world.gold_canary,))
    raw = json.loads(canonical(public.payload()))
    raw["sources"][0]["namespace"] = "other/w/p"
    with pytest.raises(NornError, match="PUBLIC_PERMISSION_LEAK"):
        validate_public(raw)


def test_structural_and_actual_import_barrier(tmp_path):
    check_import_barrier(Path("src/norn"), Path("benchmark/adapters"))
    fake = tmp_path / "runtime"
    fake.mkdir()
    (fake / "consumer.py").write_text("from benchmark.fixtures import world\n")
    with pytest.raises(NornError, match="RUNTIME_EVALUATOR_IMPORT"):
        check_import_barrier(fake, Path("benchmark/adapters"))
    code = (
        "import sys; import benchmark.adapters.common; "
        "assert 'benchmark.fixtures.world' not in sys.modules; "
        "assert 'benchmark.fixtures.scenarios' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "statement",
    [
        "from benchmark.fixtures import world",
        "from ..fixtures import scenarios",
        "from benchmark import runs",
    ],
)
def test_adapter_from_import_aliases_cannot_bypass_custody(tmp_path, statement):
    adapter = tmp_path / "adapters"
    adapter.mkdir()
    (adapter / "consumer.py").write_text(statement + "\n")
    with pytest.raises(NornError, match="ADAPTER_GOLD_IMPORT"):
        check_import_barrier(Path("src/norn"), adapter)


@pytest.mark.parametrize(
    "statement",
    [
        "from importlib import import_module as load; load('benchmark.fixtures.world')",
        "from builtins import __import__ as load; load('benchmark.fixtures.world')",
        "from builtins import eval as run; run('1+1')",
        "from builtins import exec as run; run('x=1')",
    ],
)
def test_aliased_dynamic_import_and_execution_functions_are_rejected(tmp_path, statement):
    adapter = tmp_path / "adapters"
    adapter.mkdir()
    (adapter / "consumer.py").write_text(statement + "\n")
    with pytest.raises(NornError, match="DYNAMIC_IMPORT_OR_EXECUTION"):
        check_import_barrier(Path("src/norn"), adapter)
