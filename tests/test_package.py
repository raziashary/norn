import json
import subprocess
import sys


def test_capability_profile_has_no_optional_assets_or_provider_calls():
    code = """import json,sys
from norn.cli import execute
from argparse import Namespace
r=execute(Namespace(command='capabilities'))
assert not any(m in sys.modules for m in ('groq','torch','transformers','qdrant_client'))
print(json.dumps(r))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
    capabilities = json.loads(result.stdout)
    assert capabilities["models_loaded"] == [] and capabilities["providers_loaded"] == []
    assert capabilities["generative_llm"] == "DISABLED"
