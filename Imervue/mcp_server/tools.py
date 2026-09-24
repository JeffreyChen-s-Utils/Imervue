"""Tool handlers exposed by the Imervue MCP server.

Each function is a self-contained piece of Imervue's pure-logic
surface — image metadata, XMP tags, format conversion, puppet rig
inspection — that's useful to an AI client. Qt-free so the server
can run as a subprocess.

This module is the public face of the tool set: it re-exports every
handler and registers them. The code lives in

* ``tools_read`` (listing, metadata, analysis, search, conversion) and
  ``tools_edit`` (overlays, geometry, effects written to a destination),
  with the helpers both share in ``tool_support``;
* ``tool_defs_read`` / ``tool_defs_edit``, the name, description, input
  schema and handler of each tool, in ``tools/list`` order.

Tests import handlers from here and assert on return values without
serialising through JSON-RPC. :func:`register_default_tools` is the one
place that decides which tools the server offers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from Imervue.mcp_server.tool_defs_edit import EDIT_TOOL_DEFINITIONS
from Imervue.mcp_server.tool_defs_read import READ_TOOL_DEFINITIONS
from Imervue.mcp_server.tools_edit import (
    apply_frame,
    apply_watermark,
    auto_color_balance_image,
    build_collage,
    channel_mixer_image,
    clahe_image,
    colormap_image,
    crop_image,
    curve_image,
    defringe_image,
    dehaze_image,
    detail_equalizer_image,
    distort_image,
    dither_image,
    emboss_image,
    false_color_image,
    film_grain_image,
    film_negative_image,
    filmic_tonemap_image,
    frosted_glass_image,
    glow_image,
    gradient_map_image,
    graduated_density_image,
    kaleidoscope_image,
    lens_correction_image,
    levels_image,
    local_contrast_image,
    pixel_sort_image,
    polar_image,
    posterize_image,
    resize_image,
    rotate_image,
    solarize_image,
    split_toning_image,
    tone_equalizer_image,
    velvia_image,
)
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

if TYPE_CHECKING:
    from Imervue.mcp_server.server import MCPServer

__all__ = [
    "list_images",
    "read_image_metadata",
    "read_xmp_tags",
    "extract_gps",
    "dominant_colors",
    "error_level_analysis",
    "search_images",
    "convert_format",
    "puppet_from_png",
    "puppet_inspect",
    "reverse_geocode",
    "extract_video_frame",
    "sharpness_score",
    "image_statistics",
    "quality_metrics",
    "read_histogram",
    "ocr_text",
    "image_thumbnail",
    "find_similar",
    "collection_stats",
    "apply_watermark",
    "apply_frame",
    "build_collage",
    "crop_image",
    "resize_image",
    "rotate_image",
    "solarize_image",
    "glow_image",
    "velvia_image",
    "emboss_image",
    "film_negative_image",
    "defringe_image",
    "graduated_density_image",
    "filmic_tonemap_image",
    "tone_equalizer_image",
    "detail_equalizer_image",
    "colormap_image",
    "false_color_image",
    "dither_image",
    "split_toning_image",
    "pixel_sort_image",
    "polar_image",
    "kaleidoscope_image",
    "frosted_glass_image",
    "clahe_image",
    "local_contrast_image",
    "posterize_image",
    "gradient_map_image",
    "film_grain_image",
    "dehaze_image",
    "distort_image",
    "levels_image",
    "auto_color_balance_image",
    "channel_mixer_image",
    "curve_image",
    "lens_correction_image",
    "register_default_tools",
]

_TOOL_DEFINITIONS: list[dict[str, Any]] = [*READ_TOOL_DEFINITIONS, *EDIT_TOOL_DEFINITIONS]


def register_default_tools(server: MCPServer) -> None:
    """Register every tool in :data:`_TOOL_DEFINITIONS` onto ``server``.

    Called once from :func:`Imervue.mcp_server.server.run` and from
    tests that want the default tool set. Tests that want to register
    a custom subset should drop straight into ``server.register``
    instead of using this helper. Output schemas and annotations are
    pulled from :data:`Imervue.mcp_server.tool_schemas.TOOL_METADATA`."""
    from Imervue.mcp_server.tool_schemas import TOOL_METADATA
    for entry in _TOOL_DEFINITIONS:
        meta = TOOL_METADATA.get(entry["name"], {})
        server.register(
            name=entry["name"],
            description=entry["description"],
            input_schema=entry["input_schema"],
            handler=entry["handler"],
            output_schema=meta.get("output_schema"),
            annotations=meta.get("annotations"),
        )
