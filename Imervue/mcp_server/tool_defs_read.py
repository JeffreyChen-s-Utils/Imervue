"""Name, description, input schema and handler of each read-side MCP tool.

Order is the order ``tools/list`` reports; output schemas live in ``tool_schemas``.
"""
from __future__ import annotations

from typing import Any

from Imervue.mcp_server.tools_read import (
    collection_stats,
    convert_format,
    dominant_colors,
    error_level_analysis,
    extract_gps,
    extract_video_frame,
    find_similar,
    image_statistics,
    image_thumbnail,
    list_images,
    ocr_text,
    puppet_from_png,
    puppet_inspect,
    quality_metrics,
    read_histogram,
    read_image_metadata,
    read_xmp_tags,
    reverse_geocode,
    search_images,
    sharpness_score,
)

READ_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_images",
        "description": (
            "List image files in a folder. Returns each entry's path, "
            "size in bytes, and mtime. Pass recursive=true to walk subfolders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Directory to list."},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder"],
        },
        "handler": list_images,
    },
    {
        "name": "read_image_metadata",
        "description": (
            "Read dimensions, format, EXIF, and XMP sidecar fields for one image."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the image."},
            },
            "required": ["path"],
        },
        "handler": read_image_metadata,
    },
    {
        "name": "read_xmp_tags",
        "description": "Return only the XMP sidecar tags / rating / label for an image.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": read_xmp_tags,
    },
    {
        "name": "extract_gps",
        "description": (
            "Read GPS latitude/longitude from an image's EXIF. Returns has_gps "
            "and signed decimal coordinates (null when absent); chain into "
            "reverse_geocode for a place name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": extract_gps,
    },
    {
        "name": "dominant_colors",
        "description": (
            "Extract the dominant colour palette (median-cut), dominant first. "
            "Each colour carries rgb, hex and pixel_count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "n_colors": {
                    "type": "integer", "minimum": 1, "maximum": 64, "default": 8,
                },
            },
            "required": ["path"],
        },
        "handler": dominant_colors,
    },
    {
        "name": "error_level_analysis",
        "description": (
            "Return a JPEG-recompression Error-Level-Analysis map as a PNG data "
            "URI — regions edited after the last save light up against the rest."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "quality": {
                    "type": "integer", "minimum": 1, "maximum": 100, "default": 90,
                },
                "scale": {
                    "type": "integer", "minimum": 1, "maximum": 100, "default": 15,
                },
            },
            "required": ["path"],
        },
        "handler": error_level_analysis,
    },
    {
        "name": "search_images",
        "description": (
            "Search a folder with the smart-album query DSL (e.g. "
            "'ext:png name:sunset width:>1920 aspect:>1.5 size:>2mb camera:canon'). "
            "Returns matching paths. Path/name/size/dimension/EXIF filters work; "
            "rating/favourite/colour/tag/cull fields are rejected as they need "
            "the running app's database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Directory to search."},
                "query": {"type": "string", "description": "Smart-album query DSL."},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder", "query"],
        },
        "handler": search_images,
    },
    {
        "name": "convert_format",
        "description": (
            "Convert one image to another format. Destination format is taken from "
            "the destination suffix (png / jpg / jpeg / webp / tiff / bmp, plus "
            "heic / avif / jxl when their optional backends are installed)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "quality": {"type": "integer", "minimum": 1, "maximum": 100, "default": 90},
            },
            "required": ["source", "destination"],
        },
        "handler": convert_format,
    },
    {
        "name": "puppet_from_png",
        "description": (
            "Build a .puppet rig from a PNG using the built-in puppet auto-mesh. "
            "Seeds the Cubism-standard parameter catalogue so the rig is "
            "immediately drivable by the puppet input drivers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "cell_size": {"type": "integer", "minimum": 4, "maximum": 1024, "default": 64},
            },
            "required": ["source", "destination"],
        },
        "handler": puppet_from_png,
    },
    {
        "name": "puppet_inspect",
        "description": (
            "Open a .puppet archive and return a structured inventory: "
            "drawables, deformers, parameters, motions, expressions, hit areas, "
            "parts, parameter blends and physics rigs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": puppet_inspect,
    },
    {
        "name": "reverse_geocode",
        "description": (
            "Resolve GPS latitude/longitude to the nearest major city (offline). "
            "Returns a 'City, Country' place name and [city, country] keywords."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
        "handler": reverse_geocode,
    },
    {
        "name": "extract_video_frame",
        "description": (
            "Decode one frame of a video file and save it as an image. The "
            "destination suffix picks the still format. frame_index defaults to 0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "frame_index": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["source", "destination"],
        },
        "handler": extract_video_frame,
    },
    {
        "name": "sharpness_score",
        "description": (
            "Score an image's sharpness via Laplacian variance and flag whether "
            "it is likely blurry. Higher score means sharper."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": sharpness_score,
    },
    {
        "name": "image_statistics",
        "description": (
            "Return per-channel (r/g/b/luma) mean, min, max, std and median for "
            "one image — a quantitative read-out for inspection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": image_statistics,
    },
    {
        "name": "quality_metrics",
        "description": (
            "Return no-reference quality metrics for one image: colourfulness, "
            "tonal entropy, RMS contrast, edge density and a noise-sigma estimate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": quality_metrics,
    },
    {
        "name": "read_histogram",
        "description": (
            "Return the 256-bin per-channel (r/g/b/luma) histogram and the "
            "over/under exposure-clipping fractions for one image."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": read_histogram,
    },
    {
        "name": "ocr_text",
        "description": (
            "Extract text from an image via Tesseract OCR. Returns available=false "
            "(not an error) when the optional backend is missing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "min_confidence": {"type": "number", "default": 0.0},
            },
            "required": ["path"],
        },
        "handler": ocr_text,
    },
    {
        "name": "image_thumbnail",
        "description": (
            "Return a downscaled PNG preview of an image as a base64 data URI. "
            "max_size bounds the long edge (default 256, capped at 512)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_size": {"type": "integer", "minimum": 16, "maximum": 512, "default": 256},
            },
            "required": ["path"],
        },
        "handler": image_thumbnail,
    },
    {
        "name": "find_similar",
        "description": (
            "Group near-duplicate images in a folder by perceptual (dHash) "
            "similarity. threshold is the max Hamming distance (default 5); set "
            "recursive=true to walk subfolders. Returns groups of size > 1."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "threshold": {"type": "integer", "minimum": 0, "maximum": 32, "default": 5},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder"],
        },
        "handler": find_similar,
    },
    {
        "name": "collection_stats",
        "description": (
            "Summarise a folder's images: total / rated / unrated counts, a 0-5 "
            "star distribution and average, favourite count, a colour-label "
            "tally and a pick/reject/unflagged cull tally. Set recursive=true to "
            "walk subfolders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder"],
        },
        "handler": collection_stats,
    },
]
