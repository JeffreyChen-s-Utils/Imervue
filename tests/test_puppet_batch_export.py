"""Tests for the batch motion exporter.

We don't exercise the actual imageio writer in CI (it'd need a real
GL context to grab frames). Instead the tests cover the state
machine: rejection paths, queue building, and the safe-filename
sanitiser.
"""
from __future__ import annotations
import pytest

from Imervue.puppet.batch_export import (
    SUPPORTED_EXTENSIONS,
    BatchMotionExporter,
    _safe_filename,
)
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from Imervue.puppet.motion_player import MotionPlayer


# QOpenGLWidget construction segfaults on the headless GitHub
# Actions Windows runner once the offscreen-GL pool is exhausted
# (see tests/conftest.py::skip_on_headless_ci). All tests in this
# file touch a real PuppetCanvas / PuppetWorkspace, so the whole
# module skips on CI; local runs cover them.
import os as _os_for_skip  # noqa: E402
import pytest as _pytest_for_skip  # noqa: E402

pytestmark = _pytest_for_skip.mark.skipif(
    _os_for_skip.environ.get("CI") == "true"
    or _os_for_skip.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QOpenGLWidget construction segfaults on headless CI runner",
)



def _motion(name: str) -> Motion:
    return Motion(
        name=name, duration=0.5,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0))],
        )],
    )


def _doc_with(*motions: Motion) -> PuppetDocument:
    doc = PuppetDocument(size=(16, 16))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [Parameter(id="ParamX", min=-1, max=1, default=0)]
    doc.motions = list(motions)
    return doc


# ---------------------------------------------------------------------------
# Filename sanitiser
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,expected", [
    ("idle_01", "idle_01"),
    ("idle/01", "idle_01"),
    ("idle 01", "idle_01"),
    ("idle:01", "idle_01"),
    # Every CJK char gets stripped, so the helper falls back to its
    # "empty-after-clean" sentinel — exercises the fallback branch.
    ("私の/絵", "motion"),
])
def test_safe_filename_strips_unfriendly_chars(name, expected):
    # The parametrize hack above keeps the unicode case in the table
    # but uses the "motion" fallback because every CJK char gets
    # stripped — exercises the empty-after-clean fallback path.
    assert _safe_filename(name) == expected


def test_safe_filename_empty_input_falls_back():
    assert _safe_filename("") == "motion"


def test_safe_filename_all_unfriendly_falls_back():
    assert _safe_filename("///") == "motion"


# ---------------------------------------------------------------------------
# Exporter — rejection paths
# ---------------------------------------------------------------------------


def test_start_rejects_unsupported_extension(qapp, tmp_path):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("idle")))
    player = MotionPlayer(canvas)
    exporter = BatchMotionExporter(canvas, player)
    try:
        failures: list[str] = []
        exporter.failed.connect(failures.append)
        ok = exporter.start(tmp_path, extension=".xyz")
        assert ok is False
        assert failures and ".xyz" in failures[0]
    finally:
        exporter.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_start_rejects_missing_directory(qapp, tmp_path):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("idle")))
    player = MotionPlayer(canvas)
    exporter = BatchMotionExporter(canvas, player)
    try:
        failures: list[str] = []
        exporter.failed.connect(failures.append)
        ok = exporter.start(tmp_path / "no_such_dir", extension=".mp4")
        assert ok is False
        assert failures and "does not exist" in failures[0]
    finally:
        exporter.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_start_rejects_doc_without_motions(qapp, tmp_path):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with())   # no motions
    player = MotionPlayer(canvas)
    exporter = BatchMotionExporter(canvas, player)
    try:
        failures: list[str] = []
        exporter.failed.connect(failures.append)
        ok = exporter.start(tmp_path, extension=".mp4")
        assert ok is False
        assert failures
    finally:
        exporter.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_supported_extensions_lists_mp4_gif_webm():
    assert set(SUPPORTED_EXTENSIONS) == {".mp4", ".gif", ".webm"}


def test_exporter_not_running_by_default(qapp):
    canvas = PuppetCanvas()
    player = MotionPlayer(canvas)
    exporter = BatchMotionExporter(canvas, player)
    try:
        assert exporter.is_running() is False
    finally:
        exporter.deleteLater()
        player.deleteLater()
        canvas.deleteLater()
