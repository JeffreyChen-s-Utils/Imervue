"""Opacity and tint parameter curves in the puppet format."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from Imervue.puppet.format_values import PuppetFormatError, _parameter_name


def _validate_key_entry(
    entry: Any,
    *, drawable_id: str, key_label: str, idx: int,
) -> tuple[str, list]:
    """Shared validation for opacity_keys / multiply_color_keys entries.
    Returns ``(parameter, stops)`` after checking entry shape, the
    presence of a non-empty ``parameter`` string, and that ``stops``
    is a list of >= 2."""
    label = f"drawable {drawable_id!r} {key_label}[{idx}]"
    param = _parameter_name(entry, label)
    stops = entry.get("stops")
    if not isinstance(stops, list) or len(stops) < 2:
        raise PuppetFormatError(
            f"drawable {drawable_id!r} {key_label}[{idx}] needs >=2 stops",
        )
    return param, stops


def _parse_keys(
    raw: Any, drawable_id: str, key_label: str,
    parse_stop: Callable[[Any, str, int, int], dict],
) -> list[dict] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        detail = f", got {type(raw).__name__}" if key_label == "opacity_keys" else ""
        raise PuppetFormatError(
            f"drawable {drawable_id!r} {key_label} must be a list{detail}",
        )
    out: list[dict] = []
    for idx, entry in enumerate(raw):
        param, stops = _validate_key_entry(
            entry, drawable_id=drawable_id, key_label=key_label, idx=idx,
        )
        parsed_stops = [
            parse_stop(stop, drawable_id, idx, s_idx)
            for s_idx, stop in enumerate(stops)
        ]
        out.append({"parameter": param, "stops": parsed_stops})
    return out


def _parse_stop(
    stop: Any, drawable_id: str, idx: int, s_idx: int,
    *, key_label: str, value_key: str, decode: Callable[[Any], Any],
) -> dict:
    if not isinstance(stop, dict) or "value" not in stop or value_key not in stop:
        raise PuppetFormatError(
            f"drawable {drawable_id!r} {key_label}[{idx}].stops[{s_idx}] "
            f"must have 'value' and '{value_key}'",
        )
    return {"value": float(stop["value"]), value_key: decode(stop[value_key])}


def _parse_color3(
    raw: Any, *, default: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tuple[float, float, float]:
    if raw is None:
        return default
    if not isinstance(raw, list) or len(raw) != 3:
        raise PuppetFormatError(f"color must be [r, g, b], got {raw!r}")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


_parse_alpha_stop = partial(_parse_stop, key_label="opacity_keys", value_key="alpha", decode=float)


_parse_color_stop = partial(
    _parse_stop, key_label="multiply_color_keys", value_key="color", decode=_parse_color3,
)


def _keys_to_json(
    keys: list[dict], value_key: str, encode_value: Callable[[Any], Any],
) -> list[dict]:
    return [
        {
            "parameter": entry["parameter"],
            "stops": [
                {"value": float(stop["value"]), value_key: encode_value(stop[value_key])}
                for stop in entry["stops"]
            ],
        }
        for entry in keys
    ]
