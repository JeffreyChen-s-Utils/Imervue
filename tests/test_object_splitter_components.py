"""Connected-component labelling shared by the object splitter and its runner."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from object_splitter import _components, _runner
from object_splitter import object_splitter as plugin

_PLUGIN_DIR = Path(_components.__file__).resolve().parent
_rng = np.random.default_rng(seed=0xB10B)


def _masks():
    for _ in range(60):
        h, w = _rng.integers(1, 30, 2)
        yield _rng.random((h, w)) < _rng.uniform(0.1, 0.9)


def test_scipy_labels_match_the_bfs_fallback():
    for mask in _masks():
        labels, count = _components._connected_components(mask)
        bfs_labels, bfs_count = _components._bfs_components(mask)
        assert count == bfs_count
        assert labels.dtype == np.int32
        np.testing.assert_array_equal(labels, bfs_labels)


def test_labels_are_four_connected_in_raster_order():
    mask = np.array([
        [1, 1, 0, 1],
        [0, 1, 0, 1],
        [1, 0, 0, 0],
    ], dtype=bool)
    labels, count = _components._connected_components(mask)
    assert count == 3   # the diagonal (1,1)-(2,0) does not connect
    np.testing.assert_array_equal(labels, [[1, 1, 0, 2], [0, 1, 0, 2], [3, 0, 0, 0]])


def test_falls_back_to_bfs_without_scipy(monkeypatch):
    monkeypatch.setitem(sys.modules, "scipy", None)
    mask = np.array([[1, 0, 1]], dtype=bool)
    labels, count = _components._connected_components(mask)
    assert count == 2
    np.testing.assert_array_equal(labels, [[1, 0, 2]])


def test_plugin_and_runner_share_the_helper():
    assert plugin._connected_components is _components._connected_components
    assert _runner._connected_components is _components._connected_components


def _run_isolated(tmp_path, *code_or_script: str):
    for name in ("_runner.py", "_components.py"):
        shutil.copy(_PLUGIN_DIR / name, tmp_path / name)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(  # noqa: S603 - fixed argv: this interpreter in a scratch directory
        [sys.executable, *code_or_script],
        capture_output=True, text=True, cwd=tmp_path, env=env, timeout=60, check=False,
    )


def test_runner_runs_as_a_script_with_its_sibling(tmp_path):
    result = _run_isolated(tmp_path, str(tmp_path / "_runner.py"))
    assert result.stdout.startswith("ERROR:"), result.stderr   # no arguments given
    assert result.returncode == 1


@pytest.mark.parametrize("module", ["_components", "_runner"])
def test_loading_needs_no_numpy_before_site_packages_are_added(tmp_path, module):
    # The runner puts the environment's site-packages on sys.path only in its
    # __main__ block, so neither module may import NumPy at load time.
    code = f"import sys; sys.modules['numpy'] = None; import {module}; print('ok')"
    result = _run_isolated(tmp_path, "-c", code)
    assert result.stdout.strip() == "ok", result.stderr
