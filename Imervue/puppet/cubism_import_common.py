"""Shared pieces of the Cubism v3 JSON importers: the format error every
loader raises and the BOM-tolerant JSON reader that maps bad JSON onto it."""
from __future__ import annotations

import json
from pathlib import Path


class CubismFormatError(ValueError):
    """Raised when a Cubism JSON file doesn't conform to the v3 schema
    or carries values we can't translate."""


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        # utf-8-sig: exports and hand edits that start with a BOM are still Cubism JSON.
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:   # bad JSON, or bytes that aren't UTF-8
        raise CubismFormatError(f"{path}: malformed JSON ({exc})") from exc
