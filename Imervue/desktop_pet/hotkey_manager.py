"""Global hotkey manager — system-wide shortcuts for the desktop pet.

The pet is otherwise stuck behind whatever window currently has focus;
global hotkeys let the user toggle visibility / lock / click-through
or trigger a greeting without alt-tabbing first.

``pynput`` is the cross-platform backbone (Win32 keyboard hooks on
Windows, Quartz on macOS, Xlib on Linux). We treat it as an optional
dependency exactly like ``sounddevice`` — the manager imports lazily,
:meth:`GlobalHotkeyManager.start` returns ``False`` when the import
fails, and the workspace surfaces a "needs pynput" message rather
than crashing the pet.

Module-level helpers are pure (no pynput import) so the parsing /
validation logic is testable without the optional dependency:

* :func:`to_pynput_spec` translates user-facing ``"ctrl+shift+p"``
  into the ``"<ctrl>+<shift>+p"`` form pynput expects.
* :func:`is_valid_spec` returns ``True`` when a user-supplied spec
  is parseable; the workspace uses it to gate the "save bindings"
  button.

The manager wraps :class:`pynput.keyboard.GlobalHotKeys` (its own
listener thread) and re-emits hits as Qt signals on the GUI thread —
calling :class:`PetWindow` methods directly from the listener thread
would skip Qt's thread-affinity checks and crash on long-lived
operations like ``setWindowFlags``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    pass

logger = logging.getLogger("Imervue.desktop_pet.hotkey_manager")

ACTION_TOGGLE_VISIBLE: str = "toggle_visible"
ACTION_TOGGLE_LOCK: str = "toggle_lock"
ACTION_TOGGLE_CLICK_THROUGH: str = "toggle_click_through"
ACTION_SPEAK_NOW: str = "speak_now"

HOTKEY_ACTIONS: tuple[str, ...] = (
    ACTION_TOGGLE_VISIBLE,
    ACTION_TOGGLE_LOCK,
    ACTION_TOGGLE_CLICK_THROUGH,
    ACTION_SPEAK_NOW,
)
"""Canonical list of actions a hotkey can fire. Anything outside
this set is dropped at coercion time so a typo in the settings file
doesn't sit as a permanently-disabled binding."""

DEFAULT_HOTKEY_BINDINGS: dict[str, str] = {
    ACTION_TOGGLE_VISIBLE: "ctrl+shift+p",
    ACTION_TOGGLE_LOCK: "ctrl+shift+l",
    ACTION_TOGGLE_CLICK_THROUGH: "ctrl+shift+t",
    ACTION_SPEAK_NOW: "ctrl+shift+space",
}
"""Default bindings. Chosen for low collision risk with common app
shortcuts (Ctrl+Shift+P is mostly used by IDE command palettes — a
user with one of those open will rebind, but the conflict is at
most "the wrong app reacts" rather than data loss)."""

_MODIFIER_TOKENS: frozenset[str] = frozenset({
    "ctrl", "control", "shift", "alt", "meta", "cmd", "super", "win",
})
"""Lower-case modifier names accepted by the parser. ``cmd`` /
``win`` / ``super`` all map to pynput's ``<cmd>``; ``control``
collapses to ``ctrl``."""

_MODIFIER_CANONICAL: dict[str, str] = {
    "control": "ctrl",
    "cmd": "cmd",
    "win": "cmd",
    "super": "cmd",
    "ctrl": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "meta": "cmd",
}


def _normalise_token(token: str) -> str:
    """Lower-case, strip whitespace, collapse modifier aliases."""
    lowered = token.strip().lower()
    return _MODIFIER_CANONICAL.get(lowered, lowered)


def to_pynput_spec(user_spec: str) -> str:
    """Translate ``"ctrl+shift+p"`` (Qt-style) to ``"<ctrl>+<shift>+p"``
    (pynput-style).

    Tokens are split on ``+``, trimmed, lower-cased, and modifier
    aliases collapsed (``Control`` → ``ctrl``, ``Win`` → ``cmd``).
    Modifier tokens are wrapped in angle brackets; the trailing key
    is passed through verbatim (pynput accepts single chars and
    its own ``<f1>`` / ``<space>`` / etc. names).

    Raises :class:`ValueError` for empty / modifier-only specs; the
    workspace's rebind widget gates on :func:`is_valid_spec` so the
    error path here is just a defence in depth.
    """
    parts = [_normalise_token(t) for t in user_spec.split("+") if t.strip()]
    if not parts:
        raise ValueError(f"empty hotkey spec: {user_spec!r}")
    out: list[str] = []
    for token in parts[:-1]:
        if token not in _MODIFIER_TOKENS:
            raise ValueError(
                f"non-modifier token {token!r} before the trailing key in "
                f"{user_spec!r} — modifiers must come first",
            )
        out.append(f"<{token}>")
    final = parts[-1]
    if not final:
        raise ValueError(f"trailing key empty in {user_spec!r}")
    if final in _MODIFIER_TOKENS:
        raise ValueError(
            f"spec {user_spec!r} ends on modifier {final!r} — needs a "
            f"non-modifier key as the final token",
        )
    # pynput uses <f1>..<f12> / <space> / <esc> etc. for named keys.
    out.append(f"<{final}>" if len(final) > 1 else final)
    return "+".join(out)


def is_valid_spec(user_spec: str) -> bool:
    """Cheap parseability check — used by UI rebind widgets to gate
    save buttons. ``False`` on empty / modifier-only specs."""
    try:
        to_pynput_spec(user_spec)
    except ValueError:
        return False
    return True


def coerce_bindings(raw: object) -> dict[str, str]:
    """Filter ``raw`` to a clean ``{action: spec}`` dict. Unknown
    actions are dropped (forward-compat: a future schema may add
    actions, an older runtime should ignore them rather than error);
    invalid specs are dropped with a debug log so the user's typo
    isn't silently propagated to the listener."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for action, spec in raw.items():
        if action not in HOTKEY_ACTIONS:
            continue
        if not isinstance(spec, str) or not is_valid_spec(spec):
            logger.debug("dropping invalid hotkey for %s: %r", action, spec)
            continue
        out[str(action)] = spec
    return out


class GlobalHotkeyManager(QObject):
    """QObject wrapping a pynput global-hotkey listener.

    Construct, call :meth:`set_bindings` to install a mapping, then
    :meth:`start`; subscribers receive :attr:`action_triggered` on
    the Qt GUI thread (pynput's own thread is *not* Qt-affine).
    Calling :meth:`set_bindings` while running rebuilds the listener.
    """

    action_triggered = Signal(str)
    """Emitted with the action name (one of :data:`HOTKEY_ACTIONS`)
    each time the user presses the bound combo."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bindings: dict[str, str] = {}
        self._listener = None   # pynput.keyboard.GlobalHotKeys | None

    # ---- public API ------------------------------------------------

    def bindings(self) -> dict[str, str]:
        return dict(self._bindings)

    def set_bindings(self, bindings: dict[str, str]) -> None:
        """Replace the entire binding set. If the listener is running
        it's stopped + restarted so the new map takes effect; if not,
        the bindings are just stored for the next :meth:`start`."""
        self._bindings = coerce_bindings(bindings)
        if self._listener is not None:
            self.stop()
            self.start()

    def is_running(self) -> bool:
        return self._listener is not None

    def start(self) -> bool:
        """Start listening. Returns ``True`` on success, ``False``
        when pynput is missing or the listener can't be created
        (e.g. macOS accessibility prompt declined). Idempotent —
        calling start on an already-running manager is a no-op."""
        if self._listener is not None:
            return True
        try:
            from pynput import keyboard
        except ImportError:
            logger.info("pynput not installed; global hotkeys unavailable")
            return False
        if not self._bindings:
            logger.debug("no bindings configured; hotkey listener not started")
            return False
        pynput_map: dict[str, object] = {}
        for action, spec in self._bindings.items():
            try:
                pynput_map[to_pynput_spec(spec)] = self._make_emitter(action)
            except ValueError as exc:
                logger.warning("skipping invalid hotkey %r: %s", spec, exc)
        if not pynput_map:
            return False
        try:
            self._listener = keyboard.GlobalHotKeys(pynput_map)
            self._listener.start()
        except Exception as exc:   # noqa: BLE001 - pynput surfaces OS-specific errors
            logger.warning("global hotkey listener failed to start: %s", exc)
            self._listener = None
            return False
        return True

    def stop(self) -> None:
        """Stop the listener and release the OS keyboard hook. Safe
        to call when the listener isn't running."""
        if self._listener is None:
            return
        try:
            self._listener.stop()
        except Exception as exc:   # noqa: BLE001 - pynput surfaces OS-specific errors
            logger.warning("stopping hotkey listener: %s", exc)
        self._listener = None

    def shutdown(self) -> None:
        """Alias for :meth:`stop` — matches the lifecycle method
        every other desktop-pet driver exposes."""
        self.stop()

    # ---- internal --------------------------------------------------

    def _make_emitter(self, action: str):
        """Build a thread-safe emitter closure. Qt signals are safe
        to ``emit`` from any thread (the slot delivery is queued
        when the receiver lives on a different thread), so we just
        capture the action name and call ``emit`` from inside
        pynput's listener thread."""
        def emitter() -> None:
            self.action_triggered.emit(action)
        return emitter
