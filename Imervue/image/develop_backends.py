"""Other renderers of the develop recipe, which plugins register (a GPU one, for instance).

``Recipe.apply`` is the reference renderer and runs on the CPU. A plugin
registers a :class:`BackendProvider` — a key, and a ``probe`` that says whether
the backend can run here and with what — and batch export offers it next to
the CPU. A renderer must produce what ``Recipe.apply`` does; it may run the
stages it implements itself and hand the rest to ``Recipe.apply_stages``.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from Imervue.image.recipe import Recipe
from Imervue.plugin.status import status_registry

logger = logging.getLogger("Imervue.image.develop_backends")

#: The key of the built-in renderer, ``Recipe.apply`` on the CPU.
CPU = "cpu"


class DevelopRenderer(Protocol):
    """Renders a recipe onto an HxWx4 uint8 array, like ``Recipe.apply``."""

    label: str

    def render(self, arr: np.ndarray, recipe: Recipe) -> np.ndarray:
        """Return *arr* with *recipe* applied (a new array or *arr* itself when nothing changes)."""

    def close(self) -> None:
        """Release the device; the renderer is not used afterwards."""


@dataclass(frozen=True)
class BackendProvider:
    """A registered backend: its key, a probe and a way to open a renderer.

    ``probe()`` returns the label to offer (e.g. the GPU's name), or ``None``
    when the backend cannot run on this machine. ``open()`` builds a renderer
    and may raise ``RuntimeError`` or ``OSError`` when the device fails.
    """

    key: str
    probe: Callable[[], str | None]
    open: Callable[[], DevelopRenderer]


_providers: dict[str, BackendProvider] = {}
_registrations: dict[str, dict[int, BackendProvider]] = {}


def register(provider: BackendProvider) -> None:
    """Offer *provider*; a provider already under its key is replaced."""
    if provider.key == CPU:
        raise ValueError(f"{CPU!r} is the built-in renderer")
    if provider.key not in _providers:
        _registrations.pop(provider.key, None)
    _registrations.setdefault(provider.key, {})[id(provider)] = provider
    _providers[provider.key] = provider


def unregister(key: str, *, provider: BackendProvider | None = None) -> None:
    """Remove all registrations, or only one provider generation during multi-window reload."""
    registrations = _registrations.get(key, {})
    if provider is not None:
        registrations.pop(id(provider), None)
        if registrations:
            _providers[key] = next(reversed(registrations.values()))
            status_registry.publish("backend:" + key, key, "checking",
                                    "Another loaded window still provides this backend")
            return
    _registrations.pop(key, None)
    _providers.pop(key, None)
    status_registry.publish("backend:" + key, key, "unloaded")


def available() -> list[tuple[str, str]]:
    """``(key, label)`` for every registered backend that can run here, CPU first excluded."""
    found = []
    for provider in list(_providers.values()):
        try:
            label = provider.probe()
        except (RuntimeError, OSError, ImportError) as exc:   # a broken driver or package
            status_registry.publish("backend:" + provider.key, provider.key, "failed",
                                    f"CPU fallback: {exc}")
            logger.warning("Develop backend %r cannot run: %s", provider.key, exc)
            continue
        status_registry.publish("backend:" + provider.key, provider.key,
                                "available" if label else "missing",
                                label or "Device/dependencies unavailable; CPU remains available")
        if label:
            found.append((provider.key, label))
    return found


def open_renderer(key: str) -> DevelopRenderer | None:
    """A renderer for *key*; ``None`` for the CPU, an unknown key or a backend failing to open."""
    provider = _providers.get(key)
    if key == CPU or provider is None:
        return None
    try:
        renderer = provider.open()
        status_registry.publish("backend:" + key, key, "available", renderer.label)
        return renderer
    except (RuntimeError, OSError, ImportError) as exc:
        status_registry.publish("backend:" + key, key, "failed", f"CPU fallback: {exc}")
        logger.warning("Develop backend %r failed to open, rendering on the CPU: %s", key, exc)
        return None


def render(arr: np.ndarray, recipe: Recipe, renderer: DevelopRenderer | None = None) -> np.ndarray:
    """Apply *recipe* to *arr* with *renderer*, or on the CPU when there is none.

    A renderer that raises ``RuntimeError`` (a lost device, an out-of-memory
    buffer) makes this image fall back to the CPU, so one failure costs speed,
    not the export.
    """
    if renderer is None or recipe.is_identity():
        return recipe.apply(arr)
    try:
        return renderer.render(arr, recipe)
    except RuntimeError as exc:
        status_registry.publish("renderer:" + renderer.label, renderer.label, "failed",
                                f"CPU fallback: {exc}")
        logger.warning("%s failed on an image, rendering it on the CPU: %s", renderer.label, exc)
        return recipe.apply(arr)
