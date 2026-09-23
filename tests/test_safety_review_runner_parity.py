"""The frozen-build runner censors with the same code as the in-app detection path.

``_runner.py`` runs in an external Python (the frozen build cannot import
torch), so it cannot import the Qt plugin package. It used to carry its own
copies of the geometry and rendering helpers, and they drifted: its ellipse
filled the whole box instead of the inset one, a 1-px box stayed clear, and its
colour count still looped over ``Image.getdata()``, which Pillow 14 removes.
Both paths now use ``_censor_core``; the runner loads it, and ``_constants``,
as sibling files when it runs as a script.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from safety_review import _censor_core, _detection, _runner
from safety_review._constants import SHAPE_ELLIPSE, SHAPE_PRECISE, STYLE_BLACK

_PLUGIN_DIR = Path(_runner.__file__).resolve().parent

SHARED = ["_censor_region", "_detect_image_mode", "_ensure_parent", "_expand_box",
          "_junction_bridges", "_merge_gap", "_shrink_box_center"]


@pytest.mark.parametrize("name", SHARED)
def test_runner_and_detection_use_the_same_helper(name):
    helper = getattr(_censor_core, name)
    assert getattr(_runner, name) is helper
    assert getattr(_detection, name) is helper


@pytest.mark.parametrize("shape", [SHAPE_ELLIPSE, SHAPE_PRECISE])
def test_runner_censors_a_one_pixel_box(shape):
    img = Image.new("RGB", (4, 4), (255, 255, 255))
    _runner._censor_region(img, 1, 1, 2, 2, 6, style=STYLE_BLACK, shape=shape)
    assert img.getpixel((1, 1)) == (0, 0, 0)


def test_runner_ellipse_is_the_inset_one():
    # The inset ellipse spares a point the full inscribed one would cover.
    img = Image.new("RGB", (40, 40), (255, 255, 255))
    _runner._censor_region(img, 0, 0, 40, 40, 6, style=STYLE_BLACK, shape=SHAPE_ELLIPSE)
    assert img.getpixel((20, 20)) == (0, 0, 0)
    assert img.getpixel((20, 1)) == (255, 255, 255)


def _run_isolated(tmp_path, files, *args):
    """Run the first of *files* as a script, alone with its siblings in *tmp_path*.

    With the plugin package off ``sys.path``, only the copied siblings can
    satisfy the script's imports.
    """
    for name in files:
        shutil.copy(_PLUGIN_DIR / name, tmp_path / name)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(  # noqa: S603 - fixed argv: this interpreter and a copied script
        [sys.executable, str(tmp_path / files[0]), *args],
        capture_output=True, text=True, cwd=tmp_path, env=env, timeout=60, check=False,
    )


def test_runner_runs_as_a_script_with_sibling_imports(tmp_path):
    result = _run_isolated(tmp_path, ("_runner.py", "_censor_core.py", "_constants.py"),
                           "", "no-such-mode")
    assert result.stdout.strip() == "ERROR:Unknown mode: no-such-mode"
    assert result.returncode == 1


def test_finetune_runs_as_a_script_with_sibling_imports(tmp_path):
    result = _run_isolated(tmp_path, ("finetune.py", "_constants.py"), "--help")
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()
