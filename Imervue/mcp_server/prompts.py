"""MCP prompt templates for the image assistant.

Self-contained: each prompt takes a path argument and builds a ``messages``
list by reusing the pure tool functions, so no server-side "current folder"
state is needed. Exposed through ``prompts/list`` and ``prompts/get``.
"""
from __future__ import annotations

from typing import Any

_PROMPTS: list[dict[str, Any]] = [
    {
        "name": "caption_image",
        "description": "Embed an image thumbnail and ask for a concise caption / alt-text.",
        "arguments": [
            {"name": "path", "description": "Absolute path to the image.", "required": True},
        ],
    },
    {
        "name": "suggest_edits",
        "description": "Provide the histogram + quality metrics and ask for concrete edits.",
        "arguments": [
            {"name": "path", "description": "Absolute path to the image.", "required": True},
            {"name": "style", "description": "Optional look, e.g. 'portrait'.",
             "required": False},
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
