"""``GPUImageView.run_shortcut_action`` runs a Shortcut Settings action through the key dispatcher."""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def test_the_action_goes_to_the_key_dispatcher_without_modifiers():
    calls = []
    view = SimpleNamespace(_key_dispatch=SimpleNamespace(
        dispatch=lambda action, modifiers: calls.append((action, modifiers))))
    GPUImageView.run_shortcut_action(view, "undo")
    assert calls == [("undo", Qt.KeyboardModifier.NoModifier)]
