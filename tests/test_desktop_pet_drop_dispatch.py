"""Tests for the desktop-pet file-drop dispatcher.

Covers:

* the pure ``classify_drop_paths`` helper, including mixed payloads
  and case-insensitive extension matching
* the ``handle_dropped_paths`` wiring on :class:`PetWindow` — this
  is the public path-based entry point the Qt ``dropEvent`` delegates
  to. Constructing a real ``QDropEvent`` proved unstable across
  PySide versions, so the test surface is the path list instead.
"""
from __future__ import annotations

from pathlib import Path

from Imervue.desktop_pet.pet_window import (
    DROP_MOTION_GROUP,
    PetWindow,
    classify_drop_paths,
)
from Imervue.puppet.document import (
    Motion,
    MotionSegment,
    MotionTrack,
    PuppetDocument,
)

from _qt_skip import pytestmark  # noqa: E402,F401


# ---------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------


def test_classify_empty_payload():
    assert classify_drop_paths([]) == ("none", None)


def test_classify_single_puppet():
    p = Path("foo.puppet")
    assert classify_drop_paths([p]) == ("puppet", p)


def test_classify_other_file_returns_first():
    """A drop of one non-puppet file → caller still gets the path
    so logs / status surface show "X was dropped" rather than a
    bare "other"."""
    p = Path("image.png")
    assert classify_drop_paths([p]) == ("other", p)


def test_classify_mixed_picks_first_puppet():
    """If the user drops a mix, the rig swap wins over the
    "react to a file" path — most useful UX."""
    a = Path("image.png")
    b = Path("rig.puppet")
    c = Path("notes.txt")
    assert classify_drop_paths([a, b, c]) == ("puppet", b)


def test_classify_extension_is_case_insensitive():
    """Windows file pickers preserve user-typed extension case,
    so a ``Foo.PUPPET`` drop must work the same as ``foo.puppet``."""
    p = Path("Foo.PUPPET")
    kind, picked = classify_drop_paths([p])
    assert kind == "puppet"
    assert picked == p


# ---------------------------------------------------------------
# Qt wiring on PetWindow
# ---------------------------------------------------------------


def _attach_doc_with_drop_motion(window: PetWindow) -> Motion:
    drop = Motion(
        name="react", duration=1.0, loop=False, group=DROP_MOTION_GROUP,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(
                type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0),
            )],
        )],
    )
    doc = PuppetDocument(size=(32, 32))
    doc.motions = [drop]
    window._canvas.load_document(doc)   # noqa: SLF001
    return drop


def test_pet_accepts_drops(qapp):
    """Without ``setAcceptDrops(True)`` the OS would reject the drop
    target before our handler runs. Catches regressions in the
    constructor."""
    window = PetWindow()
    try:
        assert window.acceptDrops() is True
    finally:
        window.deleteLater()


def test_drop_puppet_triggers_load(qapp, monkeypatch):
    """Happy path — a ``.puppet`` drop calls ``load_puppet_file``
    with the dropped path. Monkey-patch the loader so we don't
    actually need a real archive on disk."""
    window = PetWindow()
    try:
        called: list[Path] = []
        monkeypatch.setattr(
            window, "load_puppet_file",
            lambda path: (called.append(Path(path)), True)[1],
        )
        kind = window.handle_dropped_paths([Path("rig.puppet")])
        assert kind == "puppet"
        assert called == [Path("rig.puppet")]
    finally:
        window.deleteLater()


def test_drop_other_plays_drop_motion(qapp):
    """Dropping a non-puppet file → Drop motion group plays."""
    window = PetWindow()
    try:
        drop = _attach_doc_with_drop_motion(window)
        kind = window.handle_dropped_paths([Path("photo.png")])
        assert kind == "other"
        assert window._motion_player.motion() is drop   # noqa: SLF001
    finally:
        window.deleteLater()


def test_drop_empty_list_is_noop(qapp):
    """An empty payload (caller filtered everything out) must be a
    silent no-op."""
    window = PetWindow()
    try:
        kind = window.handle_dropped_paths([])
        assert kind == "none"
    finally:
        window.deleteLater()


def test_drop_other_without_drop_group_is_silent(qapp):
    """Rig without a Drop group → still accepted, just no motion.
    Anything else would lock out users with simpler rigs."""
    window = PetWindow()
    try:
        doc = PuppetDocument(size=(32, 32))   # no motions
        window._canvas.load_document(doc)   # noqa: SLF001
        kind = window.handle_dropped_paths([Path("photo.png")])
        assert kind == "other"
        assert window._motion_player.motion() is None   # noqa: SLF001
    finally:
        window.deleteLater()


def test_drop_puppet_wins_over_drop_motion(qapp, monkeypatch):
    """Mixed payload — the rig swap must take precedence over the
    "react to a file" path so users can hot-swap rigs by dragging
    them in alongside other files."""
    window = PetWindow()
    try:
        drop = _attach_doc_with_drop_motion(window)
        loaded: list[Path] = []
        monkeypatch.setattr(
            window, "load_puppet_file",
            lambda path: (loaded.append(Path(path)), True)[1],
        )
        window.handle_dropped_paths([
            Path("photo.png"),
            Path("rig.puppet"),
        ])
        assert loaded == [Path("rig.puppet")]
        # Drop motion must NOT fire when a puppet was loaded.
        assert window._motion_player.motion() is not drop   # noqa: SLF001
    finally:
        window.deleteLater()
