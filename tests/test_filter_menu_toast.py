"""Tests for the filter-menu toast wiring.

When a filter raises ``ValueError`` / ``TypeError`` the artist should
see a non-blocking toast explaining what went wrong, instead of staring
at an unchanged canvas while the failure is buried in the log.
"""
from __future__ import annotations

from Imervue.paint.filter_menu import FilterSpec, _notify_filter_failed


class _ToastSpy:
    """Records every toast call so the test can assert on the surface."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, text, duration_ms=2500):
        self.calls.append(("info", text))

    def success(self, text, duration_ms=2500):
        self.calls.append(("success", text))

    def warning(self, text, duration_ms=4000):
        self.calls.append(("warning", text))

    def error(self, text, duration_ms=4000):
        self.calls.append(("error", text))


class _WorkspaceWithToast:
    def __init__(self):
        self.toast = _ToastSpy()


class _WorkspaceWithoutToast:
    pass


def _spec(label: str = "Box Blur", key: str = "box_blur") -> FilterSpec:
    """Build a minimal FilterSpec — we only need the label / key."""
    return FilterSpec(
        key=key,
        label_key=f"paint_filter_{key}",
        label_fallback=label,
        parameters=(),
        apply_fn=lambda arr, params: arr,
    )


def test_notify_filter_failed_pings_toast():
    ws = _WorkspaceWithToast()
    _notify_filter_failed(ws, _spec(), ValueError("kernel out of range"))
    assert ws.toast.calls
    severity, text = ws.toast.calls[0]
    assert severity == "error"
    # The label is included so the artist knows which filter failed.
    assert "Box Blur" in text
    # The cause is included so it's actionable, not just decorative.
    assert "kernel out of range" in text


def test_notify_filter_failed_no_toast_is_silent():
    """Workspaces built before the toast wiring (legacy embedders /
    minimal test stubs) must not crash when a filter fails — the toast
    surface degrades to a no-op."""
    _notify_filter_failed(
        _WorkspaceWithoutToast(), _spec(), TypeError("bad argument"),
    )


def test_notify_filter_failed_uses_translated_label(monkeypatch):
    """When the language pack ships a translation for the spec's
    label_key, the toast surfaces that translation instead of the
    English fallback."""
    from Imervue.multi_language.language_wrapper import language_wrapper
    monkeypatch.setitem(
        language_wrapper.language_word_dict, "paint_filter_gaussian", "Gaussian Blur (zh)",
    )
    ws = _WorkspaceWithToast()
    _notify_filter_failed(ws, _spec(label="Gaussian", key="gaussian"), ValueError("oops"))
    assert any("Gaussian Blur (zh)" in text for _, text in ws.toast.calls)
