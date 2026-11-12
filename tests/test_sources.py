import os
import subprocess

import pytest

from norn.canonical.sources import SourceSpan, SourceStore
from norn.contracts.errors import NornError


def test_source_reopen_exact_utf8_half_open_and_corruption(tmp_path):
    store = SourceStore(tmp_path / "blobs")
    raw = "Alex café 🚲".encode()
    version = store.put(raw)
    assert store.put(raw) == version
    span = store.span(version, 5, len(raw))
    assert SourceStore(store.root).resolve(span) == "café 🚲".encode()
    with pytest.raises(NornError, match="INVALID_UTF8_BOUNDARY"):
        store.span(version, 5, 9)
    with pytest.raises(NornError, match="INVALID_DIGEST"):
        store.read("../escape")
    with pytest.raises(NornError, match="SPAN_INTEGRITY"):
        store.resolve(SourceSpan(version, span.start, span.end, "0" * 64))
    (store.root / version).write_bytes(b"corrupted")
    with pytest.raises(NornError, match="SOURCE_INTEGRITY"):
        store.read(version)
    with pytest.raises(NornError, match="SOURCE_UNAVAILABLE"):
        store.read("0" * 64)


def test_source_symlink_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        assert os.name == "nt"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert created.returncode == 0, created.stderr
        assert link.is_junction()
    with pytest.raises(NornError, match="UNSAFE_SOURCE_PATH"):
        SourceStore(link)
    from conftest import HOST

    from norn.integration.engine import Engine

    with pytest.raises(NornError, match="UNSAFE_SOURCE_PATH"):
        Engine(link, HOST, create=True)
    assert not (outside / "canonical.sqlite3").exists()
    store = SourceStore(tmp_path / "blobs")
    nested = store.root / ("0" * 64)
    if os.name == "nt":
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(nested), str(outside)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert created.returncode == 0, created.stderr
    else:
        nested.symlink_to(outside / "missing")
    with pytest.raises(NornError, match="UNSAFE_SOURCE_PATH"):
        store.read("0" * 64)


def test_sweep_survives_a_staging_file_discarded_by_a_live_writer(tmp_path, monkeypatch):
    # Opening an engine sweeps staging files while other writers stage and discard theirs. A file
    # that vanishes between the listing and the age check must be skipped, not crash the open.
    from pathlib import Path

    store = SourceStore(tmp_path / "blobs")
    vanishing = store.stage(b"live writer")
    stale = store.stage(b"abandoned by a crash")
    os.utime(stale.path, (0, 0))
    real_stat = Path.stat

    def stat(self, *args, **kwargs):
        if self.name == vanishing.path.name and self.exists():
            vanishing.path.unlink()  # the writer discards it right before the check
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    assert store.sweep_staging() == 1  # only the genuinely stale file is counted
    assert not stale.path.exists() and not vanishing.path.exists()
    # Negative control: a fresh live file is left alone when it is still there.
    monkeypatch.undo()
    fresh = store.stage(b"fresh")
    assert store.sweep_staging() == 0 and fresh.path.exists()
