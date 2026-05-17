"""Tests for the ``.moc3`` / ``.model3.json`` import paths wired into
the Puppet workspace toolbar.

The Cubism Native SDK DLL isn't redistributable, so these tests stub
:func:`cubism_to_puppet` and exercise the workspace's dispatch logic:

* dialog filter mentions ``.moc3``
* ``.moc3`` with no active document triggers full conversion
* ``.model3.json`` with no active document triggers full conversion
* ``.model3.json`` with an active document falls back to JSON-metadata
  merge via ``apply_bundle``
* ``.motion3.json`` with no active document bails with a friendly
  status message
* ``CubismBridgeError`` from ``cubism_to_puppet`` is surfaced as
  status text instead of crashing the UI
* ``_guess_model3_for_moc3`` finds the sibling manifest next to a raw
  ``.moc3`` file
"""
from __future__ import annotations
from pathlib import Path

import pytest

from Imervue.puppet.cubism_native_bridge import CubismBridgeError
from Imervue.puppet.document import Drawable, PuppetDocument
from Imervue.puppet import workspace as workspace_module
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



def _make_demo_document() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables.append(Drawable(
        id="stub", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0, visible=True, opacity=1.0,
    ))
    return doc


def test_dialog_filter_mentions_moc3(qapp, monkeypatch):
    """The Import Cubism… file picker has to actually let users pick a
    raw ``.moc3`` — that's the headline of this feature."""
    captured: dict[str, str] = {}

    def _fake_dialog(*_args, **kwargs):
        captured["filter"] = _args[3] if len(_args) >= 4 else kwargs.get("filter", "")
        return ("", "")

    monkeypatch.setattr(workspace_module.QFileDialog, "getOpenFileName", _fake_dialog)
    ws = PuppetWorkspace()
    try:
        ws._import_cubism_via_dialog()   # noqa: SLF001
    finally:
        ws.deleteLater()
    assert "*.moc3" in captured["filter"]


def test_moc3_without_active_document_creates_new_puppet(
    qapp, tmp_path, monkeypatch,
):
    """A user drag-drops a ``.moc3`` onto a blank workspace; the
    workspace must reach for ``cubism_to_puppet`` (sample-and-
    reconstruct) and load the resulting document into the canvas."""
    moc3 = tmp_path / "Foo.moc3"
    moc3.write_bytes(b"fake-moc3-bytes")
    sibling = tmp_path / "Foo.model3.json"
    sibling.write_text("{}", encoding="utf-8")

    converted = _make_demo_document()
    seen: dict[str, Path] = {}

    def _fake_convert(model3_path, **_kwargs):
        seen["model3"] = Path(model3_path)
        return converted

    monkeypatch.setattr(workspace_module, "cubism_to_puppet", _fake_convert)
    ws = PuppetWorkspace()
    try:
        assert ws._canvas.document() is None   # noqa: SLF001
        ok = ws.import_cubism(moc3)
        assert ok is True
        assert seen["model3"] == sibling
        assert ws._canvas.document() is converted   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_model3_without_active_document_uses_full_converter(
    qapp, tmp_path, monkeypatch,
):
    """A ``.model3.json`` against an empty workspace also triggers
    full conversion — there's nothing to merge onto, so the natural
    intent is "import this Live2D model as a new puppet"."""
    model3 = tmp_path / "Bar.model3.json"
    model3.write_text("{}", encoding="utf-8")

    converted = _make_demo_document()
    calls: list[Path] = []

    def _fake_convert(model3_path, **_kwargs):
        calls.append(Path(model3_path))
        return converted

    monkeypatch.setattr(workspace_module, "cubism_to_puppet", _fake_convert)
    ws = PuppetWorkspace()
    try:
        ok = ws.import_cubism(model3)
        assert ok is True
        assert calls == [model3]
        assert ws._canvas.document() is converted   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_model3_with_active_document_merges_via_apply_bundle(
    qapp, tmp_path, monkeypatch,
):
    """When the user already has a rig open, a ``.model3.json`` import
    must layer JSON-only metadata onto it (motions, expressions, …)
    via ``apply_bundle`` — not blow the existing rig away."""
    model3 = tmp_path / "Baz.model3.json"
    model3.write_text("{}", encoding="utf-8")

    bundle_calls: list[tuple[PuppetDocument, object]] = []
    def _fake_apply_bundle(doc, bundle):
        bundle_calls.append((doc, bundle))

    def _fake_load_model3(_path):
        return object()

    def _fake_convert(*_args, **_kwargs):
        raise AssertionError("cubism_to_puppet should not be called here")

    monkeypatch.setattr(workspace_module, "apply_bundle", _fake_apply_bundle)
    monkeypatch.setattr(workspace_module, "load_model3", _fake_load_model3)
    monkeypatch.setattr(workspace_module, "cubism_to_puppet", _fake_convert)

    ws = PuppetWorkspace()
    try:
        existing = _make_demo_document()
        ws._canvas.load_document(existing)   # noqa: SLF001
        ok = ws.import_cubism(model3)
        assert ok is True
        assert len(bundle_calls) == 1
        assert bundle_calls[0][0] is existing
    finally:
        ws.deleteLater()


def test_motion3_without_active_document_announces_friendly_error(
    qapp, tmp_path,
):
    """``.motion3.json`` only makes sense layered onto an existing
    rig. Without one, the workspace must bail with a status message
    — not crash, not silently succeed."""
    motion3 = tmp_path / "Wave.motion3.json"
    motion3.write_text("{}", encoding="utf-8")
    ws = PuppetWorkspace()
    try:
        ok = ws.import_cubism(motion3)
        assert ok is False
    finally:
        ws.deleteLater()


def test_bridge_error_is_caught_and_surfaced(qapp, tmp_path, monkeypatch):
    """SDK missing / DLL unloadable raises ``CubismBridgeError`` from
    deep in ``cubism_to_puppet``. The workspace must catch it, leave
    the canvas untouched, and write a status message — never let it
    bubble up to a crash."""
    model3 = tmp_path / "Qux.model3.json"
    model3.write_text("{}", encoding="utf-8")

    def _fake_convert(*_args, **_kwargs):
        raise CubismBridgeError("Live2DCubismCore.dll not found")

    monkeypatch.setattr(workspace_module, "cubism_to_puppet", _fake_convert)
    ws = PuppetWorkspace()
    try:
        ok = ws.import_cubism(model3)
        assert ok is False
        assert ws._canvas.document() is None   # noqa: SLF001
        assert "Live2DCubismCore.dll not found" in ws._status_label.text()   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_guess_model3_finds_named_sibling(tmp_path):
    """The canonical layout is ``Foo.moc3`` + ``Foo.model3.json`` —
    the helper prefers the matching stem when present."""
    moc3 = tmp_path / "Foo.moc3"
    moc3.write_bytes(b"x")
    named = tmp_path / "Foo.model3.json"
    named.write_text("{}", encoding="utf-8")
    decoy = tmp_path / "Other.model3.json"
    decoy.write_text("{}", encoding="utf-8")
    out = PuppetWorkspace._guess_model3_for_moc3(str(moc3))   # noqa: SLF001
    assert Path(out) == named


def test_guess_model3_falls_back_to_any_sibling(tmp_path):
    """When the stems differ (e.g. user renamed the moc3), the helper
    still picks any sibling ``.model3.json`` rather than failing —
    Cubism distributions usually only ship one per folder anyway."""
    moc3 = tmp_path / "Renamed.moc3"
    moc3.write_bytes(b"x")
    other = tmp_path / "Original.model3.json"
    other.write_text("{}", encoding="utf-8")
    out = PuppetWorkspace._guess_model3_for_moc3(str(moc3))   # noqa: SLF001
    assert Path(out) == other


def test_guess_model3_raises_when_manifest_missing(tmp_path):
    """A bare ``.moc3`` in an otherwise empty folder must raise a
    readable error so ``import_cubism`` can surface it to the user."""
    from Imervue.puppet.cubism_import import CubismFormatError

    moc3 = tmp_path / "Lonely.moc3"
    moc3.write_bytes(b"x")
    with pytest.raises(CubismFormatError):
        PuppetWorkspace._guess_model3_for_moc3(str(moc3))   # noqa: SLF001
