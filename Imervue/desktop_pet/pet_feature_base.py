"""Feature-controller scaffolding for the desktop-pet overlay.

The :class:`~Imervue.desktop_pet.pet_window.PetWindow` used to carry
every "feature hook" (OBS, Twitch, webhook, Windows notifications,
global hotkeys, …) as a pair of ``set_*_enabled`` / ``*_enabled``
methods plus a lazily-created client attribute, all inlined on one
god-object class.

These features share a near-identical lifecycle:

1. Lazy-create a worker / client object on first enable so users who
   never touch the feature don't pay its import / thread / socket
   cost.
2. (Re)configure it from the persisted settings dict every enable so
   a workspace edit takes effect without restarting the pet.
3. ``start()`` it; the worker reports whether the requested state was
   actually reached (a missing optional dependency, a refused socket
   bind, or a denied OS permission yields ``False``).
4. Persist the *actual* resulting flag so a failed enable doesn't
   leave settings claiming the feature is on.

This module captures that lifecycle once. Concrete controllers live
in :mod:`Imervue.desktop_pet.pet_features` and only override the
small, feature-specific pieces (which client class, how to wire its
signals, how to configure it). Composition over inheritance: the
window *owns* a registry of these controllers and delegates to them;
it does not inherit their behaviour.
"""
from __future__ import annotations

from typing import Protocol


class FeatureHost(Protocol):
    """The slice of :class:`PetWindow` a feature controller needs.

    Declared as a :class:`~typing.Protocol` so controllers depend on
    a narrow capability surface rather than the whole window — keeps
    the coupling explicit and the controllers unit-testable against a
    tiny fake host instead of a real Qt widget.
    """

    def persist(self, **fields: object) -> None:
        """Write ``fields`` through to this pet's settings slot."""

    def persist_driver(self, key: str, value: bool) -> None:
        """Write a single slot inside the persisted ``drivers`` dict."""

    def setting(self, key: str, default: object) -> object:
        """Read a persisted setting value with a fallback default."""

    def canvas(self) -> object:
        """The puppet canvas a canvas-driver binds to."""

    def play_group(self, group: str) -> bool:
        """Play a random motion from ``group`` (silent no-op miss)."""

    def speak(self, line: str) -> None:
        """Surface ``line`` in the speech bubble if speech is on."""

    @property
    def speech_on(self) -> bool:
        """Whether the speech bubble subsystem is currently enabled."""


class IntegrationController:
    """Base for lazy worker / client feature hooks.

    Subclasses implement :meth:`_build_client` (construct + wire the
    worker, called once) and :meth:`_configure` (push the current
    settings into the worker, called every enable). The base owns the
    enable / disable / persist lifecycle so each concrete controller
    stays a few lines.

    The controller stores no enabled flag of its own — the worker's
    ``is_running()`` is the single source of truth, mirroring the
    original inline methods exactly.
    """

    #: Settings key the persisted enable flag round-trips through.
    persist_key: str = ""

    def __init__(self, host: FeatureHost) -> None:
        self._host = host
        self._client: object | None = None

    def _build_client(self) -> object:
        """Construct and wire the worker. Called once, lazily."""
        raise NotImplementedError

    def _configure(self, client: object) -> None:
        """Push current settings into ``client`` before each start.

        Default is a no-op for workers that take no configuration.
        """

    def _ensure_client(self) -> object:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def set_enabled(self, enabled: bool) -> bool:
        """Start or stop the worker and persist the resulting flag.

        Returns ``True`` when the requested state was reached;
        ``False`` when an enable failed (missing dep, refused bind,
        denied permission). Disabling always reports ``True``.
        """
        if enabled:
            client = self._ensure_client()
            self._configure(client)
            ok = bool(client.start())   # type: ignore[attr-defined]
            self._host.persist(**{self.persist_key: ok})
            return ok
        if self._client is not None:
            self._client.stop()   # type: ignore[attr-defined]
        self._host.persist(**{self.persist_key: False})
        return True

    def is_enabled(self) -> bool:
        """Whether the worker exists and reports itself running."""
        return (
            self._client is not None
            and bool(self._client.is_running())   # type: ignore[attr-defined]
        )


def merge_bindings(
    defaults: dict[str, str], persisted: object,
) -> dict[str, str]:
    """Overlay persisted hotkey overrides on top of ``defaults``.

    A user who saved only one custom binding keeps the module
    defaults for every other action. Non-dict / non-string-spec
    persisted values are ignored defensively — the settings file is
    user-editable and may be malformed.

    Pure helper so the merge logic is unit-tested without a window.
    """
    merged = dict(defaults)
    if isinstance(persisted, dict):
        for action, spec in persisted.items():
            if isinstance(spec, str) and spec:
                merged[action] = spec
    return merged


def sanitize_app_ids(ignored: object) -> tuple[str, ...]:
    """Coerce a persisted "ignored app ids" value into a clean tuple.

    Accepts only a list of non-empty strings; anything else yields an
    empty tuple. Pure helper so the notification controller's input
    validation is testable without WinRT.
    """
    if not isinstance(ignored, list):
        return ()
    return tuple(item for item in ignored if isinstance(item, str) and item)
