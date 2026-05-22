"""Sound effects for desktop-pet interactions.

Per-event sound playback keyed by stable event names (``"click"``,
``"drag"``, ``"drop"``, ``"notify"``). Each event has an optional
file path; events without a configured path are silent — that's
the default state so users who don't care about audio aren't
ambushed by noise on first install.

The class is structured around :class:`QSoundEffect`, which is the
low-latency audio path in Qt (loads the file once, replays from
memory, suitable for short clicks). One instance per event keeps
overlapping clicks from cutting each other off.

Pure helper :func:`coerce_paths_map` filters the persisted
``{event: path}`` dict against the known event names so a typo or
removed-event entry doesn't sit in settings forever.
"""
from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QUrl

if TYPE_CHECKING:
    pass

logger = logging.getLogger("Imervue.desktop_pet.click_sfx")

EVENT_CLICK: str = "click"
EVENT_DRAG: str = "drag"
EVENT_DROP: str = "drop"
EVENT_NOTIFY: str = "notify"

SFX_EVENTS: tuple[str, ...] = (
    EVENT_CLICK,
    EVENT_DRAG,
    EVENT_DROP,
    EVENT_NOTIFY,
)
"""Canonical event names. The workspace UI iterates this so new
events flow into the editor automatically."""

DEFAULT_VOLUME: float = 0.6
"""Mid-range default — loud enough to confirm a click, soft enough
not to startle on a quiet desktop. Users tune via settings."""


def coerce_paths_map(raw: object) -> dict[str, str]:
    """Filter a persisted ``{event: path}`` dict to known events
    with non-empty string paths. Drops:

    * non-string keys / values
    * keys not in :data:`SFX_EVENTS` (forward-compat: an older
      runtime ignoring a future event name)
    * paths pointing at files that don't exist (so a deleted asset
      doesn't surface as a silent never-firing entry)
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or key not in SFX_EVENTS:
            continue
        if not isinstance(value, str) or not value:
            continue
        if not Path(value).is_file():
            logger.debug("sfx %s missing on disk: %s", key, value)
            continue
        out[key] = value
    return out


class ClickSfxPlayer(QObject):
    """Owns one :class:`QSoundEffect` per event with a configured
    path. The first :meth:`play` for an event lazy-builds its
    effect; subsequent calls reuse it for low-latency replay.

    Constructed cheap — the ``QtMultimedia`` import only lands when
    a path is actually set, so users who never enable SFX don't
    pay for it.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._paths: dict[str, str] = {}
        self._effects: dict[str, object] = {}   # event → QSoundEffect
        self._volume: float = DEFAULT_VOLUME

    # ---- public API -----------------------------------------------

    def set_paths(self, paths: dict[str, str]) -> None:
        """Replace the path mapping. Effects whose path was removed
        are torn down so they release the file handle; effects
        whose path changed get their source URL refreshed on the
        next :meth:`play`."""
        self._paths = coerce_paths_map(paths)
        # Drop effects that no longer have a configured path.
        for event in list(self._effects.keys()):
            if event not in self._paths:
                self._effects.pop(event, None)

    def paths(self) -> dict[str, str]:
        return dict(self._paths)

    def set_volume(self, volume: float) -> None:
        """Volume in ``[0.0, 1.0]``. Applied to every live
        effect immediately so a slider drag is audible."""
        clamped = max(0.0, min(1.0, float(volume)))
        self._volume = clamped
        for effect in self._effects.values():
            # C++ side may already be torn down (Qt shutdown order
            # quirk) — drop the call silently in that case.
            with contextlib.suppress(RuntimeError):
                effect.setVolume(clamped)

    def volume(self) -> float:
        return self._volume

    def play(self, event: str) -> bool:
        """Play the SFX for ``event`` if one is configured.
        Returns ``True`` when playback actually started; ``False``
        means no path / no module / load failure. Callers can ignore
        the return value — every play path is best-effort."""
        if event not in SFX_EVENTS:
            return False
        path = self._paths.get(event, "")
        if not path:
            return False
        effect = self._ensure_effect(event, path)
        if effect is None:
            return False
        try:
            effect.play()
        except RuntimeError as exc:
            logger.debug("sfx play failed: %s", exc)
            return False
        return True

    def shutdown(self) -> None:
        """Drop every cached effect; safe to call multiple times."""
        for effect in self._effects.values():
            with contextlib.suppress(RuntimeError):
                effect.stop()
        self._effects.clear()

    # ---- internal -------------------------------------------------

    def _ensure_effect(self, event: str, path: str):
        """Lazy-build the :class:`QSoundEffect` for ``event``,
        binding it to ``path``. Returns ``None`` when QtMultimedia
        is unavailable (rare; would mean a stripped-down PySide6
        install)."""
        existing = self._effects.get(event)
        if existing is not None:
            return existing
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:
            logger.info(
                "PySide6.QtMultimedia unavailable; click SFX disabled",
            )
            return None
        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(self._volume)
        self._effects[event] = effect
        return effect
