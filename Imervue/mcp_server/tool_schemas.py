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
_NUM_OR_NULL: dict[str, Any] = {"type": ["number", "null"]}


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Build an ``object`` schema with the given properties and required keys."""
    return {"type": "object", "properties": properties, "required": required}


def _arr(items: dict[str, Any]) -> dict[str, Any]:
    """Build an ``array`` schema whose items match ``items``."""
    return {"type": "array", "items": items}


_STR_ARRAY = _arr(_STR)
_INT_ARRAY = _arr(_INT)
# An object whose values are integers (e.g. a label / cull tally).
_INT_MAP: dict[str, Any] = {"type": "object", "additionalProperties": _INT}
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


def _image_save_output() -> dict[str, Any]:
    """Output schema shared by every "apply one effect and save a copy" tool."""
    return _obj(
        {
            "source": _STR,
            "destination": _STR,
            "width": _INT,
            "height": _INT,
            "size_bytes": _INT,
        },
        ["source", "destination", "width", "height", "size_bytes"],
    )


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
    "extract_gps": {
        "annotations": _read_only("Extract GPS"),
        "output_schema": _obj(
            {
                "path": _STR,
                "has_gps": _BOOL,
                "latitude": _NUM_OR_NULL,
                "longitude": _NUM_OR_NULL,
            },
            ["path", "has_gps", "latitude", "longitude"],
        ),
    },
    "dominant_colors": {
        "annotations": _read_only("Dominant colors"),
        "output_schema": _obj(
            {
                "path": _STR,
                "color_count": _INT,
                "colors": _arr(_obj(
                    {"rgb": _INT_ARRAY, "hex": _STR, "pixel_count": _INT},
                    ["rgb", "hex", "pixel_count"],
                )),
            },
            ["path", "color_count", "colors"],
        ),
    },
    "error_level_analysis": {
        "annotations": _read_only("Error level analysis"),
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
    "search_images": {
        "annotations": _read_only("Search images"),
        "output_schema": _obj(
            {
                "folder": _STR,
                "query": _STR,
                "count": _INT,
                "matches": _STR_ARRAY,
            },
            ["folder", "query", "count", "matches"],
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
    "collection_stats": {
        "annotations": _read_only("Collection stats"),
        "output_schema": _obj(
            {
                "folder": _STR,
                "total": _INT,
                "rated": _INT,
                "unrated": _INT,
                "average_rating": _NUM,
                "rating_distribution": _INT_MAP,
                "favorites": _INT,
                "color_labels": _INT_MAP,
                "cull": _INT_MAP,
            },
            ["folder", "total", "rated", "unrated", "average_rating",
             "rating_distribution", "favorites", "color_labels", "cull"],
        ),
    },
    "apply_watermark": {
        "annotations": _writes_file("Apply watermark"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "size_bytes": _INT,
                "corner": _STR,
            },
            ["source", "destination", "size_bytes", "corner"],
        ),
    },
    "apply_frame": {
        "annotations": _writes_file("Apply photo frame"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "size_bytes": _INT,
                "width": _INT,
                "height": _INT,
            },
            ["source", "destination", "size_bytes", "width", "height"],
        ),
    },
    "build_collage": {
        "annotations": _writes_file("Build collage"),
        "output_schema": _obj(
            {
                "destination": _STR,
                "image_count": _INT,
                "columns": _INT,
                "width": _INT,
                "height": _INT,
                "size_bytes": _INT,
            },
            ["destination", "image_count", "columns",
             "width", "height", "size_bytes"],
        ),
    },
    "crop_image": {
        "annotations": _writes_file("Crop image"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "width": _INT,
                "height": _INT,
                "size_bytes": _INT,
            },
            ["source", "destination", "width", "height", "size_bytes"],
        ),
    },
    "resize_image": {
        "annotations": _writes_file("Resize image"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "width": _INT,
                "height": _INT,
                "size_bytes": _INT,
            },
            ["source", "destination", "width", "height", "size_bytes"],
        ),
    },
    "rotate_image": {
        "annotations": _writes_file("Rotate image"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "operation": _STR,
                "width": _INT,
                "height": _INT,
                "size_bytes": _INT,
            },
            ["source", "destination", "operation",
             "width", "height", "size_bytes"],
        ),
    },
    "solarize_image": {
        "annotations": _writes_file("Solarize image"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "width": _INT,
                "height": _INT,
                "size_bytes": _INT,
            },
            ["source", "destination", "width", "height", "size_bytes"],
        ),
    },
    "glow_image": {
        "annotations": _writes_file("Glow image"),
        "output_schema": _obj(
            {
                "source": _STR,
                "destination": _STR,
                "width": _INT,
                "height": _INT,
                "size_bytes": _INT,
            },
            ["source", "destination", "width", "height", "size_bytes"],
        ),
    },
    "velvia_image": {
        "annotations": _writes_file("Velvia boost"),
        "output_schema": _image_save_output(),
    },
    "emboss_image": {
        "annotations": _writes_file("Emboss image"),
        "output_schema": _image_save_output(),
    },
    "film_negative_image": {
        "annotations": _writes_file("Film negative"),
        "output_schema": _image_save_output(),
    },
    "defringe_image": {
        "annotations": _writes_file("Defringe image"),
        "output_schema": _image_save_output(),
    },
    "graduated_density_image": {
        "annotations": _writes_file("Graduated density"),
        "output_schema": _image_save_output(),
    },
    "filmic_tonemap_image": {
        "annotations": _writes_file("Filmic tone map"),
        "output_schema": _image_save_output(),
    },
    "tone_equalizer_image": {
        "annotations": _writes_file("Tone equalizer"),
        "output_schema": _image_save_output(),
    },
    "detail_equalizer_image": {
        "annotations": _writes_file("Detail equalizer"),
        "output_schema": _image_save_output(),
    },
    "colormap_image": {
        "annotations": _writes_file("Colour map"),
        "output_schema": _image_save_output(),
    },
    "false_color_image": {
        "annotations": _writes_file("False colour"),
        "output_schema": _image_save_output(),
    },
    "dither_image": {
        "annotations": _writes_file("Dither image"),
        "output_schema": _image_save_output(),
    },
    "split_toning_image": {
        "annotations": _writes_file("Split toning"),
        "output_schema": _image_save_output(),
    },
    "pixel_sort_image": {
        "annotations": _writes_file("Pixel sort"),
        "output_schema": _image_save_output(),
    },
}
