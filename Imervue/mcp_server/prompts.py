"""MCP prompt templates for the image assistant.

Self-contained: each prompt takes a path argument and builds a ``messages``
list by reusing the pure tool functions, so no server-side "current folder"
state is needed. Exposed through ``prompts/list`` and ``prompts/get``.
"""
from __future__ import annotations

from typing import Any

_PATH_ARG_DESC = "Absolute path to the image."

_PROMPTS: list[dict[str, Any]] = [
    {
        "name": "caption_image",
        "description": "Embed an image thumbnail and ask for a concise caption / alt-text.",
        "arguments": [
            {"name": "path", "description": _PATH_ARG_DESC, "required": True},
        ],
    },
    {
        "name": "suggest_edits",
        "description": "Provide the histogram + quality metrics and ask for concrete edits.",
        "arguments": [
            {"name": "path", "description": _PATH_ARG_DESC, "required": True},
            {"name": "style", "description": "Optional look, e.g. 'portrait'.",
             "required": False},
        ],
    },
    {
        "name": "analyze_composition",
        "description": (
            "Embed the image plus a saliency-derived subject-placement hint and "
            "ask for a composition critique (rule-of-thirds, balance, framing)."
        ),
        "arguments": [
            {"name": "path", "description": _PATH_ARG_DESC, "required": True},
            {"name": "focus", "description": "Optional aspect to emphasise, e.g. 'balance'.",
             "required": False},
        ],
    },
    {
        "name": "flag_issues",
        "description": (
            "Provide sharpness, quality metrics and exposure clipping and ask for "
            "a triaged list of technical issues with severities and fixes."
        ),
        "arguments": [
            {"name": "path", "description": _PATH_ARG_DESC, "required": True},
        ],
    },
]


def list_prompts() -> list[dict[str, Any]]:
    """Return the available prompt definitions."""
    return [dict(prompt) for prompt in _PROMPTS]


def get_prompt(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Build the messages for prompt *name* with *arguments*."""
    args = arguments or {}
    if name == "caption_image":
        return _caption_image(args)
    if name == "suggest_edits":
        return _suggest_edits(args)
    if name == "analyze_composition":
        return _analyze_composition(args)
    if name == "flag_issues":
        return _flag_issues(args)
    raise ValueError(f"unknown prompt {name!r}")


def _require(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not value:
        raise ValueError(f"argument {key!r} is required")
    return str(value)


def _caption_image(args: dict[str, Any]) -> dict[str, Any]:
    from Imervue.mcp_server.tools import image_thumbnail
    path = _require(args, "path")
    thumb = image_thumbnail(path)
    base64_png = thumb["data_uri"].split(",", 1)[1]
    return {
        "description": "Caption an image",
        "messages": [
            {"role": "user", "content": {
                "type": "text",
                "text": "Write a concise, factual caption and a short alt-text for this image.",
            }},
            {"role": "user", "content": {
                "type": "image", "data": base64_png, "mimeType": "image/png",
            }},
        ],
    }


def _suggest_edits(args: dict[str, Any]) -> dict[str, Any]:
    from Imervue.mcp_server.tools import quality_metrics, read_histogram
    path = _require(args, "path")
    style = str(args.get("style") or "general")
    metrics = quality_metrics(path)["metrics"]
    clipping = read_histogram(path)["clipping"]
    text = (
        f"Quality metrics: {metrics}. Exposure clipping: {clipping}. "
        f"Suggest concrete {style} edits (exposure, white balance, contrast, crop) "
        f"as a short prioritised list."
    )
    return {
        "description": "Suggest edits for an image",
        "messages": [
            {"role": "user", "content": {"type": "text", "text": text}},
        ],
    }


# Boundaries (fraction of the long edge) splitting the frame into thirds.
_THIRD_LOW = 0.4
_THIRD_HIGH = 0.6
_CENTRE_TERMS = frozenset({"centre", "middle"})


def _band(value: float, low: str, mid: str, high: str) -> str:
    """Bucket a normalised ``[0, 1]`` coordinate into a thirds label."""
    if value < _THIRD_LOW:
        return low
    if value > _THIRD_HIGH:
        return high
    return mid


def _third_label(nx: float, ny: float) -> str:
    """Map a normalised centre-of-mass to a human rule-of-thirds region."""
    horiz = _band(nx, "left", "centre", "right")
    vert = _band(ny, "upper", "middle", "lower")
    parts = [p for p in (vert, horiz) if p not in _CENTRE_TERMS]
    if not parts:
        return "the centre of the frame"
    return "the " + "-".join(parts) + " region"


def _salient_placement(rgba: Any) -> str:
    """Describe where the saliency centre-of-mass sits as a thirds region."""
    import numpy as np
    from Imervue.image.saliency import saliency_field
    field = saliency_field(rgba)
    total = float(field.sum())
    if total <= 0.0:
        return "the centre of the frame"
    rows, cols = np.indices(field.shape)
    ny = float((rows * field).sum() / total) / field.shape[0]
    nx = float((cols * field).sum() / total) / field.shape[1]
    return _third_label(nx, ny)


def _decode_png_rgba(base64_png: str) -> Any:
    """Decode a base64 PNG back into an HxWx4 uint8 RGBA array."""
    import base64
    import io

    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(base64.b64decode(base64_png))) as opened:
        return np.asarray(opened.convert("RGBA"), dtype=np.uint8)


def _aspect_word(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    if height > width:
        return "portrait"
    return "square"


def _analyze_composition(args: dict[str, Any]) -> dict[str, Any]:
    from Imervue.mcp_server.tools import image_thumbnail, quality_metrics
    path = _require(args, "path")
    focus = str(args.get("focus") or "all")
    thumb = image_thumbnail(path)
    base64_png = thumb["data_uri"].split(",", 1)[1]
    metrics = quality_metrics(path)["metrics"]
    placement = _salient_placement(_decode_png_rgba(base64_png))
    aspect = _aspect_word(thumb["width"], thumb["height"])
    focus_clause = "" if focus == "all" else f", focusing on {focus.replace('_', ' ')}"
    text = (
        f"Critique the composition of this {aspect} image{focus_clause}. The "
        f"strongest visual weight sits in {placement}; edge density is "
        f"{metrics['edge_density']} and colourfulness is {metrics['colorfulness']}. "
        f"Comment on rule-of-thirds, balance, subject placement and framing, then "
        f"suggest one concrete improvement."
    )
    return {
        "description": "Analyse image composition",
        "messages": [
            {"role": "user", "content": {"type": "text", "text": text}},
            {"role": "user", "content": {
                "type": "image", "data": base64_png, "mimeType": "image/png",
            }},
        ],
    }


def _flag_issues(args: dict[str, Any]) -> dict[str, Any]:
    from Imervue.mcp_server.tools import (
        quality_metrics,
        read_histogram,
        sharpness_score,
    )
    path = _require(args, "path")
    sharp = sharpness_score(path)
    metrics = quality_metrics(path)["metrics"]
    clipping = read_histogram(path)["clipping"]
    text = (
        f"Technical QA for one image. Sharpness score {sharp['score']} "
        f"(flagged blurry={sharp['blurry']}). Quality metrics: {metrics}. "
        f"Exposure clipping: {clipping}. List the concrete technical issues "
        f"(blur, over/under-exposure, noise, low contrast, dull colour), each with "
        f"a severity (low / medium / high) and a one-line fix. If nothing is wrong, "
        f"say the image is technically clean."
    )
    return {
        "description": "Flag technical issues in an image",
        "messages": [
            {"role": "user", "content": {"type": "text", "text": text}},
        ],
    }
