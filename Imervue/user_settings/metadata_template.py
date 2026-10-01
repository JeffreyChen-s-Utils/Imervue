"""Metadata template — a stationery pad for IPTC/XMP fields.

Photo Mechanic's *IPTC Stationery Pad* / Lightroom's import metadata preset:
define one set of fields (creator, copyright, usage terms, a caption with
``{token}`` placeholders) and stamp it across a whole ingest. String values are
token-expanded from each photo's metadata; scalar fields can either fill only
the blanks or overwrite, and keyword lists merge instead of clobbering.

Pure dict transformation reusing the ``code_replacements`` variable expander —
no I/O, no optional deps. **Extra Tools > Library & Metadata > Metadata
Template** applies it to a selection's title, description and keywords (which
the XMP sidecar export then writes), with :func:`photo_tokens` for the tokens.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from Imervue.user_settings.code_replacements import expand_variables

TOKENS = ("filename", "name", "folder", "date", "year")


def apply_template(
    base: dict[str, object],
    template: dict[str, object],
    meta: dict[str, object] | None = None,
    *,
    fill_empty_only: bool = True,
) -> dict[str, object]:
    """Return *base* with *template* fields applied, expanding ``{token}``s.

    *meta* supplies token values. When *fill_empty_only* is True, scalar fields
    already holding a value are kept and keyword lists are merged; when False,
    template values overwrite scalars and replace lists outright.
    """
    meta = meta or {}
    result = dict(base)
    for key, raw_value in template.items():
        value = _expand_value(raw_value, meta)
        result[key] = _merge_field(result.get(key), value, fill_empty_only)
    return result



def photo_tokens(path: str | Path, captured: datetime | None) -> dict[str, str]:
    """The ``{token}`` values of one photo: file stem, file name, folder, capture date and year.

    ``date`` (``YYYY-MM-DD``) and ``year`` are empty when the capture time is unknown.
    """
    p = Path(path)
    return {
        "filename": p.stem,
        "name": p.name,
        "folder": p.parent.name,
        "date": captured.strftime("%Y-%m-%d") if captured else "",
        "year": captured.strftime("%Y") if captured else "",
    }


def _expand_value(value: object, meta: dict[str, object]) -> object:
    if isinstance(value, str):
        return expand_variables(value, meta)
    if isinstance(value, list):
        return [expand_variables(item, meta) if isinstance(item, str) else item
                for item in value]
    return value


def _merge_field(existing: object, value: object, fill_empty_only: bool) -> object:
    if isinstance(value, list):
        if fill_empty_only and isinstance(existing, list):
            return _merge_unique(existing, value)
        return list(value)
    if fill_empty_only and _has_value(existing):
        return existing
    return value


def _merge_unique(existing: list, incoming: list) -> list:
    merged = list(existing)
    seen = set(existing)
    for item in incoming:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str | list | tuple | dict):
        return len(value) > 0
    return True
