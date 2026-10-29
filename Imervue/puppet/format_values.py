"""Shared scalar validation and JSON encoding for the puppet format."""
from __future__ import annotations

import json
from typing import Any


class PuppetFormatError(ValueError):
    """Raised when a ``.puppet`` archive doesn't conform to the v1 schema."""


def _require_keys(raw: dict, keys: tuple[str, ...], label: str) -> None:
    missing = [k for k in keys if k not in raw]
    if missing:
        raise PuppetFormatError(f"{label} missing required keys: {missing}")


def _require_list(manifest: dict, key: str) -> list:
    val = manifest.get(key)
    if not isinstance(val, list):
        raise PuppetFormatError(f"manifest key {key!r} must be a list")
    return val


def _xy(raw: Any) -> tuple[float, float]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise PuppetFormatError(f"expected [x, y] pair, got {raw!r}")
    return (float(raw[0]), float(raw[1]))


def _dumps(payload: dict) -> bytes:
    """Stable, human-readable JSON for git diffs."""
    return json.dumps(
        payload, indent=2, sort_keys=False, ensure_ascii=False,
    ).encode("utf-8")


def _parameter_name(entry: Any, label: str) -> str:
    if not isinstance(entry, dict):
        raise PuppetFormatError(f"{label} must be a dict")
    param = entry.get("parameter")
    if not isinstance(param, str) or not param:
        raise PuppetFormatError(f"{label} missing 'parameter'")
    return param


def _parse_size(raw: Any) -> tuple[int, int]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise PuppetFormatError(f"size must be [w, h], got {raw!r}")
    return (int(raw[0]), int(raw[1]))
