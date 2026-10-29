"""Copy, interpolate, and overlay partial deformer forms."""
from __future__ import annotations

from typing import Any

from Imervue.puppet.deformers import blend_forms


def _copy_forms(forms: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {k: dict(v) for k, v in forms.items()}


def _blend_forms_dicts(
    a: dict[str, dict[str, Any]],
    b: dict[str, dict[str, Any]],
    t: float,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for def_id, form_a in a.items():
        form_b = b.get(def_id)
        if form_b is None:
            out[def_id] = dict(form_a)
        else:
            out[def_id] = blend_forms(form_a, form_b, t)
    for def_id, form_b in b.items():
        if def_id not in out:
            out[def_id] = dict(form_b)
    return out


def _merge_form_dicts_into(
    target: dict[str, dict[str, Any]],
    additions: dict[str, dict[str, Any]],
) -> None:
    for def_id, form in additions.items():
        existing = target.get(def_id)
        if existing is None:
            target[def_id] = dict(form)
        else:
            existing.update(form)
