"""Phase 5 workspace authoring tests — toolbar actions for adding
deformers / parameters / keys + Save Puppet As… end-to-end.
"""
from __future__ import annotations
import pytest

from Imervue.puppet.auto_mesh import puppet_from_png
from Imervue.puppet.document_io import load_puppet
from Imervue.puppet.workspace import PuppetWorkspace


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



def _import_demo_puppet(ws: PuppetWorkspace) -> bool:
    import io

    import numpy as np
    from PIL import Image

    arr = np.zeros((64, 64, 4), dtype=np.uint8)
    arr[..., :3] = 200
    arr[..., 3] = 255
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return ws._canvas.load_document(   # noqa: SLF001
        puppet_from_png(buf.getvalue(), cell_size=32),
    ) is None or True


# ---------------------------------------------------------------------------
# Add deformers / parameters
# ---------------------------------------------------------------------------


def test_add_rotation_deformer_updates_document(qapp):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_rotation_deformer()   # noqa: SLF001
        doc = ws._canvas.document()   # noqa: SLF001
        assert any(d.type == "rotation" for d in doc.deformers)
    finally:
        ws.deleteLater()


def test_add_warp_deformer_updates_document(qapp):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_warp_deformer()   # noqa: SLF001
        doc = ws._canvas.document()   # noqa: SLF001
        assert any(d.type == "warp" for d in doc.deformers)
    finally:
        ws.deleteLater()


def test_add_deformer_id_collision_increments_suffix(qapp):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_rotation_deformer()   # rotation_1
        ws._add_rotation_deformer()   # rotation_2
        ids = [d.id for d in ws._canvas.document().deformers]   # noqa: SLF001
        assert ids == ["rotation_1", "rotation_2"]
    finally:
        ws.deleteLater()


def test_add_parameter_creates_slider_in_dock(qapp):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_parameter()   # noqa: SLF001
        # Param1 — auto-named — exists in the dock
        sliders = ws._parameter_dock._sliders   # noqa: SLF001
        assert "Param1" in sliders
    finally:
        ws.deleteLater()


def test_add_actions_silent_when_no_document(qapp):
    ws = PuppetWorkspace()
    try:
        # Should not raise even with no document
        ws._add_rotation_deformer()   # noqa: SLF001
        ws._add_warp_deformer()   # noqa: SLF001
        ws._add_parameter()   # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Set key
# ---------------------------------------------------------------------------


def test_set_key_at_current_slider_records_form_snapshot(qapp):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_rotation_deformer()   # noqa: SLF001
        ws._add_parameter()   # noqa: SLF001
        # Slider currently sits at default (0.0) → set key there
        assert ws.set_key_at_current_slider("Param1") is True
        param = ws._canvas.document().parameter("Param1")   # noqa: SLF001
        assert len(param.keys) == 1
        assert param.keys[0].value == pytest.approx(0.0)
        assert "rotation_1" in param.keys[0].forms
    finally:
        ws.deleteLater()


def test_set_key_with_no_document_returns_false(qapp):
    ws = PuppetWorkspace()
    try:
        assert ws.set_key_at_current_slider("Param1") is False
    finally:
        ws.deleteLater()


def test_remove_key_at_current_slider(qapp):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_rotation_deformer()   # noqa: SLF001
        ws._add_parameter()   # noqa: SLF001
        ws.set_key_at_current_slider("Param1")
        assert ws.remove_key_at_current_slider("Param1") is True
        assert ws._canvas.document().parameter("Param1").keys == []   # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Save round-trip
# ---------------------------------------------------------------------------


def test_save_puppet_round_trips_authored_content(qapp, tmp_path):
    ws = PuppetWorkspace()
    try:
        _import_demo_puppet(ws)
        ws._add_rotation_deformer()   # noqa: SLF001
        ws._add_parameter()   # noqa: SLF001
        ws.set_key_at_current_slider("Param1")
        out = tmp_path / "authored.puppet"
        assert ws.save_puppet(out) is True
        loaded = load_puppet(out)
        assert any(d.type == "rotation" for d in loaded.deformers)
        assert loaded.parameter("Param1") is not None
        assert len(loaded.parameter("Param1").keys) == 1
    finally:
        ws.deleteLater()


def test_save_puppet_with_no_document_returns_false(qapp, tmp_path):
    ws = PuppetWorkspace()
    try:
        assert ws.save_puppet(tmp_path / "x.puppet") is False
    finally:
        ws.deleteLater()
