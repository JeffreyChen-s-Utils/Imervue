"""The colour-blindness preview actions must pass their mode, not the checked bool.

Each CVD entry connected ``lambda _kind=kind: _set_cvd_mode(ui, _kind)`` to
``QAction.triggered``. triggered emits a ``checked`` bool, which PySide6 fed into
the lambda's single parameter -- so ``_kind`` became ``False`` and every mode but
"Off" was ignored as an unknown mode. The lambda now takes ``checked`` first.

The test captures the callbacks ``_build_cvd_submenu`` wires (by stubbing
``_add_action``) and invokes each the way Qt does -- passing the checked bool to
the multi-arg kind callbacks -- so no real QMenu/QAction is constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.menu import extra_tools_menu


def _capture_cvd_callbacks(ui, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        extra_tools_menu, "_add_action",
        lambda menu, lang, key, fallback, cb: captured.__setitem__(key, cb),
    )
    parent = SimpleNamespace(addMenu=lambda _title: SimpleNamespace())
    extra_tools_menu._build_cvd_submenu(parent, ui, {})
    return captured


def test_cvd_kind_actions_pass_the_mode_not_the_checked_bool(monkeypatch):
    received: list = []
    ui = SimpleNamespace(viewer=SimpleNamespace(set_cvd_view_mode=received.append))
    callbacks = _capture_cvd_callbacks(ui, monkeypatch)

    for kind in ("protanopia", "deuteranopia", "tritanopia", "achromatopsia"):
        received.clear()
        callbacks[f"cvd_view_{kind}"](False)   # Qt delivers triggered(checked=False)
        assert received == [kind]              # not [False]


def test_cvd_off_action_clears_the_mode(monkeypatch):
    received: list = []
    ui = SimpleNamespace(viewer=SimpleNamespace(set_cvd_view_mode=received.append))
    callbacks = _capture_cvd_callbacks(ui, monkeypatch)
    callbacks["cvd_view_off"]()               # zero-arg callback, like Qt calls it
    assert received == [None]
