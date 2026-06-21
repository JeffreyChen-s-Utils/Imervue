"""Detect duplicate / conflicting pet hotkey bindings.

A binding map (``{action: spec}``) can accidentally bind two actions to the
same chord — even when the specs *look* different (``"Ctrl+Shift+P"`` vs
``"shift+ctrl+p"``). These pure helpers canonicalise a spec order- and
case-independently (reusing :func:`hotkey_manager.to_pynput_spec`) and report
the clashes so the rebind UI can warn before saving.
"""
from __future__ import annotations

from Imervue.desktop_pet.hotkey_manager import to_pynput_spec


def canonical_spec(user_spec: str) -> str | None:
    """Return an order-independent canonical form of *user_spec*, or None.

    Modifiers are alias-collapsed (``Control`` → ``ctrl``), lower-cased and
    sorted, so ``"Ctrl+Shift+P"`` and ``"shift+ctrl+p"`` canonicalise to the
    same string. Returns ``None`` for an unparseable spec.
    """
    try:
        spec = to_pynput_spec(user_spec)
    except ValueError:
        return None
    *modifiers, final = spec.split("+")
    return "+".join(sorted(modifiers) + [final])


def find_conflicts(bindings: dict[str, str]) -> dict[str, list[str]]:
    """Return ``{canonical_spec: [actions]}`` for every chord bound 2+ times.

    Unparseable specs are ignored. Each action list is in binding-iteration
    order so the caller can report "X and Y both use Ctrl+Shift+P".
    """
    by_spec: dict[str, list[str]] = {}
    for action, spec in bindings.items():
        canon = canonical_spec(spec)
        if canon is None:
            continue
        by_spec.setdefault(canon, []).append(action)
    return {spec: actions for spec, actions in by_spec.items() if len(actions) > 1}


def has_conflicts(bindings: dict[str, str]) -> bool:
    """True when any chord in *bindings* is bound by more than one action."""
    return bool(find_conflicts(bindings))
