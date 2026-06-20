"""Output schemas and annotations for the Imervue MCP tools.

Separated from :mod:`Imervue.mcp_server.tools` so the verbose JSON-Schema
output definitions don't push the handler module past the file-length
budget, and so every tool's result contract lives in one obvious place.

Per the MCP 2025-11-25 tools spec, a tool may advertise:

* ``outputSchema`` — a JSON Schema (2020-12 dialect) describing the
  structured result. When declared, the server returns the result in
  ``structuredContent`` (in addition to the text serialisation).
* ``annotations`` — hints the client uses for its UI / safety prompts:
  ``readOnlyHint`` (no side effects), ``destructiveHint`` (may overwrite
  data), ``idempotentHint`` (repeat calls are a no-op) and
  ``openWorldHint`` (talks to external systems). All Imervue tools stay
  in the closed world (no network), so ``openWorldHint`` is always false.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Schema fragment primitives — shared references keep the definitions terse.
# ---------------------------------------------------------------------------
_STR: dict[str, Any] = {"type": "string"}
_INT: dict[str, Any] = {"type": "integer"}
_NUM: dict[str, Any] = {"type": "number"}
_BOOL: dict[str, Any] = {"type": "boolean"}
_STR_OR_NULL: dict[str, Any] = {"type": ["string", "null"]}


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Build an ``object`` schema with the given properties and required keys."""
    return {"type": "object", "properties": properties, "required": required}


def _arr(items: dict[str, Any]) -> dict[str, Any]:
    """Build an ``array`` schema whose items match ``items``."""
    return {"type": "array", "items": items}


_STR_ARRAY = _arr(_STR)
_INT_ARRAY = _arr(_INT)
_STAT = _obj(
    {"mean": _NUM, "min": _NUM, "max": _NUM, "std": _NUM, "median": _NUM},
    ["mean", "min", "max", "std", "median"],
)


def _read_only(title: str) -> dict[str, Any]:
    """Annotations for a tool with no side effects (pure read / analyse)."""
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def _writes_file(title: str) -> dict[str, Any]:
    """Annotations for a tool that writes a destination file (may overwrite)."""
    return {
        "title": title,
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


# ---------------------------------------------------------------------------
# Per-tool metadata. Keys MUST match the tool names in
# ``Imervue.mcp_server.tools._TOOL_DEFINITIONS`` (enforced by tests).
# ---------------------------------------------------------------------------
TOOL_METADATA: dict[str, dict[str, Any]] = {
    "list_images": {
        "annotations": _read_only("List images"),
        "output_schema": _obj(
            {
                "folder": _STR,
                "count": _INT,
                "images": _arr(_obj(
                    {"path": _STR, "size_bytes": _INT, "mtime": _NUM},
                    ["path", "size_bytes", "mtime"],
                )),
            },
            ["folder", "count", "images"],
        ),
    },
    "read_image_metadata": {
        "annotations": _read_only("Read image metadata"),
        "output_schema": _obj(
            {
                "path": _STR,
                "width": _INT,
                "height": _INT,
                "format": _STR_OR_NULL,
                "mode": _STR_OR_NULL,
                "exif": {"type": "object"},
                "xmp": {"type": ["object", "null"]},
                "error": _STR,
            },
            ["path"],
        ),
    },
    "read_xmp_tags": {
        "annotations": _read_only("Read XMP tags"),
        "output_schema": _obj(
            {
                "path": _STR,
                "rating": _INT,
                "title": _STR_OR_NULL,
                "description": _STR_OR_NULL,
                "keywords": _STR_ARRAY,
                "color_label": _STR_OR_NULL,
                "is_empty": _BOOL,
            },
            ["path", "rating", "keywords", "is_empty"],
        ),
    },
    "convert_format": {
        "annotations": _writes_file("Convert image format"),
        "output_schema": _obj(
            {"source": _STR, "destination": _STR, "size_bytes": _INT},
            ["source", "destination", "size_bytes"],
        ),
    },
    "puppet_from_png": {
        "annotations": _writes_file("Build puppet from PNG"),
        "output_schema": _obj(
            {
                "destination": _STR,
                "canvas_size": _INT_ARRAY,
                "vertex_count": _INT,
                "triangle_count": _INT,
                "parameter_count": _INT,
            },
            ["destination", "vertex_count", "triangle_count", "parameter_count"],
        ),
    },
    "puppet_inspect": {
        "annotations": _read_only("Inspect puppet rig"),
        "output_schema": _obj(
            {
                "path": _STR,
                "size": _INT_ARRAY,
                "drawables": _STR_ARRAY,
                "deformers": _arr({"type": "object"}),
                "parameters": _arr({"type": "object"}),
                "motions": _arr({"type": "object"}),
                "expressions": _STR_ARRAY,
                "hit_areas": _STR_ARRAY,
                "parts": _STR_ARRAY,
                "parameter_blends": _STR_ARRAY,
                "physics_rigs": _STR_ARRAY,
            },
            ["path"],
        ),
    },
    "reverse_geocode": {
        "annotations": _read_only("Reverse geocode coordinates"),
        "output_schema": _obj(
            {
                "latitude": _NUM,
                "longitude": _NUM,
                "place": _STR,
                "keywords": _STR_ARRAY,
            },
            ["latitude", "longitude", "place", "keywords"],
        ),
    },
    "extract_video_frame": {
        "annotations": _writes_file("Extract video frame"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "frame_index": _INT,
                "size_bytes": _INT,
            },
            ["source", "destination", "frame_index", "size_bytes"],
        ),
    },
    "sharpness_score": {
        "annotations": _read_only("Score sharpness"),
        "output_schema": _obj(
            {"path": _STR, "score": _NUM, "blurry": _BOOL},
            ["path", "score", "blurry"],
        ),
    },
    "image_statistics": {
        "annotations": _read_only("Image statistics"),
        "output_schema": _obj(
            {
                "path": _STR,
                "statistics": _obj(
                    {"r": _STAT, "g": _STAT, "b": _STAT, "luma": _STAT},
                    ["r", "g", "b", "luma"],
                ),
            },
            ["path", "statistics"],
        ),
    },
    "quality_metrics": {
        "annotations": _read_only("Quality metrics"),
        "output_schema": _obj(
            {
                "path": _STR,
                "metrics": _obj(
                    {
                        "colorfulness": _NUM,
                        "entropy": _NUM,
                        "rms_contrast": _NUM,
                        "edge_density": _NUM,
                        "noise_sigma": _NUM,
                    },
                    ["colorfulness", "entropy", "rms_contrast",
                     "edge_density", "noise_sigma"],
                ),
            },
            ["path", "metrics"],
        ),
    },
    "read_histogram": {
        "annotations": _read_only("Read histogram"),
        "output_schema": _obj(
            {
                "path": _STR,
                "histogram": _obj(
                    {"r": _INT_ARRAY, "g": _INT_ARRAY,
                     "b": _INT_ARRAY, "luma": _INT_ARRAY},
                    ["r", "g", "b", "luma"],
                ),
                "clipping": _obj(
                    {"over_fraction": _NUM, "under_fraction": _NUM},
                    ["over_fraction", "under_fraction"],
                ),
            },
            ["path", "histogram", "clipping"],
        ),
    },
    "ocr_text": {
        "annotations": _read_only("OCR text"),
        "output_schema": _obj(
            {"path": _STR, "available": _BOOL, "text": _STR},
            ["path", "available", "text"],
        ),
    },
    "image_thumbnail": {
        "annotations": _read_only("Image thumbnail"),
        "output_schema": _obj(
            {
                "path": _STR,
                "width": _INT,
                "height": _INT,
                "data_uri": _STR,
            },
            ["path", "width", "height", "data_uri"],
        ),
    },
    "find_similar": {
        "annotations": _read_only("Find similar images"),
        "output_schema": _obj(
            {
                "folder": _STR,
                "threshold": _INT,
                "group_count": _INT,
                "groups": _arr(_STR_ARRAY),
            },
            ["folder", "threshold", "group_count", "groups"],
        ),
    },
}
