"""CLI subcommands generated from the MCP tool definitions.

Every MCP tool is also a ``py -m Imervue.cli`` subcommand. The ten a
hand-written subcommand already covers are listed in :data:`COVERED_BY`; the
rest are built here from the tool's JSON input schema and call the same MCP
handler, so the two surfaces share one implementation and one validation:

* a tool with ``source`` + ``destination`` becomes a batch **writer**: it takes
  the shared ``inputs`` / ``--out`` / ``--dry-run`` / ``-j`` arguments and
  writes ``<stem>_<name>.png`` (``.puppet`` for ``puppet-from-png``);
* a tool with ``path`` becomes a per-image **reporter** (``--json`` or
  ``key=value`` lines, like ``info``);
* any other tool (a ``folder`` or GPS coordinates) runs **once** and prints its
  JSON result.

Every other schema property becomes an option: ``snake_case`` → ``--kebab-case``,
the schema's type, default and ``enum`` choices kept, a boolean as
``--flag`` / ``--no-flag`` and a fixed-length array as that many values. No Qt is
imported, like the rest of the CLI.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: MCP tool → the hand-written ``Imervue.cli`` subcommand that does the same job.
COVERED_BY: dict[str, str] = {
    "convert_format": "convert", "resize_image": "resize", "image_thumbnail": "thumbnail",
    "apply_watermark": "watermark", "build_collage": "collage", "quality_metrics": "stats",
    "dehaze_image": "dehaze", "clahe_image": "clahe", "dither_image": "dither",
    "distort_image": "distort",
}

#: MCP tool → generated subcommand, in the order the CLI lists them.
BRIDGED: dict[str, str] = {
    "list_images": "list-images",
    "read_image_metadata": "metadata",
    "read_xmp_tags": "xmp",
    "extract_gps": "gps",
    "dominant_colors": "dominant-colors",
    "error_level_analysis": "ela",
    "search_images": "search",
    "puppet_from_png": "puppet-from-png",
    "puppet_inspect": "puppet-inspect",
    "reverse_geocode": "reverse-geocode",
    "extract_video_frame": "video-frame",
    "sharpness_score": "sharpness",
    "image_statistics": "statistics",
    "read_histogram": "histogram",
    "ocr_text": "ocr",
    "find_similar": "similar",
    "collection_stats": "collection-stats",
    "apply_frame": "frame",
    "crop_image": "crop",
    "rotate_image": "rotate",
    "solarize_image": "solarize",
    "glow_image": "glow",
    "velvia_image": "velvia",
    "emboss_image": "emboss",
    "film_negative_image": "film-negative",
    "defringe_image": "defringe",
    "graduated_density_image": "graduated-density",
    "filmic_tonemap_image": "filmic-tonemap",
    "tone_equalizer_image": "tone-equalizer",
    "detail_equalizer_image": "detail-equalizer",
    "colormap_image": "colormap",
    "false_color_image": "false-color",
    "split_toning_image": "split-toning",
    "pixel_sort_image": "pixel-sort",
    "polar_image": "polar",
    "kaleidoscope_image": "kaleidoscope",
    "frosted_glass_image": "frosted-glass",
    "local_contrast_image": "local-contrast",
    "posterize_image": "posterize",
    "gradient_map_image": "gradient-map",
    "film_grain_image": "film-grain",
    "levels_image": "levels",
    "auto_color_balance_image": "auto-color-balance",
    "channel_mixer_image": "channel-mixer",
    "curve_image": "curve",
    "lens_correction_image": "lens-correction",
}

WRITER, REPORTER, SINGLE = "writer", "reporter", "single"
#: Schema properties the shared ``inputs`` / ``--out`` arguments supply.
_IO_PROPERTIES = frozenset({"source", "destination", "path"})
#: A single-run tool's property taken as a positional argument.
_POSITIONAL = "folder"
#: Writers whose output is not a PNG.
_WRITER_EXTENSIONS = {"puppet_from_png": ".puppet"}
#: Reporters whose result is an image, written to a file instead of printed.
_DATA_URI_WRITERS = frozenset({"error_level_analysis"})
_PY_TYPES: dict[str, type] = {"string": str, "number": float, "integer": int}
#: Subcommand help where the MCP description does not fit the CLI.
_HELP_OVERRIDES = {
    "error_level_analysis": "write a JPEG-recompression Error-Level-Analysis map as a PNG",
}
# End of a description's first sentence: a full stop (not the one in "e.g.") or a dash.
_SENTENCE_END = re.compile(r"(?<!e\.g)\.\s|\s[\u2014\u2013]\s")


class ToolError(ValueError):
    """A backend a tool needs failed (no ffmpeg, no Tesseract): one file's error, not a crash."""


@dataclass(frozen=True)
class BridgedCommand:
    """One generated subcommand: its MCP tool, kind, options and output naming."""

    command: str
    tool: str
    kind: str
    help: str
    handler: Callable[..., Any]
    options: tuple[str, ...]
    positional: str | None = None
    extension: str = ".png"

    @property
    def suffix(self) -> str:
        """Output-name suffix of a writer (``_film_grain`` for ``film-grain``)."""
        return "_" + self.command.replace("-", "_")


def _tool_definitions() -> dict[str, dict[str, Any]]:
    from Imervue.mcp_server.tools import _TOOL_DEFINITIONS
    return {tool["name"]: tool for tool in _TOOL_DEFINITIONS}


def _kind(tool: str, properties: dict[str, Any]) -> str:
    if tool in _DATA_URI_WRITERS or {"source", "destination"} <= properties.keys():
        return WRITER
    return REPORTER if "path" in properties else SINGLE


def first_sentence(description: str) -> str:
    """The description up to its first full stop or dash, lower-cased, as argparse help."""
    sentence = _SENTENCE_END.split(description, maxsplit=1)[0].strip()
    return sentence[:1].lower() + sentence[1:].rstrip(".")


def _bridged(tool: str, command: str, definition: dict[str, Any]) -> BridgedCommand:
    properties = definition["input_schema"]["properties"]
    kind = _kind(tool, properties)
    positional = _POSITIONAL if kind == SINGLE and _POSITIONAL in properties else None
    options = tuple(name for name in properties
                    if name not in _IO_PROPERTIES and name != positional)
    return BridgedCommand(
        command=command, tool=tool, kind=kind,
        help=_HELP_OVERRIDES.get(tool) or first_sentence(definition["description"]),
        handler=definition["handler"], options=options, positional=positional,
        extension=_WRITER_EXTENSIONS.get(tool, ".png"),
    )


def bridged_commands() -> dict[str, BridgedCommand]:
    """Every generated subcommand keyed by its CLI name, in :data:`BRIDGED` order."""
    definitions = _tool_definitions()
    return {command: _bridged(tool, command, definitions[tool])
            for tool, command in BRIDGED.items()}


def option_flag(name: str) -> str:
    """``zone_gains`` → ``--zone-gains``."""
    return "--" + name.replace("_", "-")


def _option_help(spec: dict[str, Any]) -> str | None:
    parts = [spec["description"].rstrip(".")] if "description" in spec else []
    low, high = spec.get("minimum"), spec.get("maximum")
    if low is not None or high is not None:
        parts.append(f"{'' if low is None else low}..{'' if high is None else high}")
    return "; ".join(parts) or None


def option_kwargs(spec: dict[str, Any], *, required: bool) -> dict[str, Any]:
    """``add_argument`` keyword arguments mirroring one JSON-schema property."""
    kwargs: dict[str, Any] = {"help": _option_help(spec), "default": spec.get("default")}
    kind = spec["type"]
    if kind == "boolean":
        kwargs["action"] = argparse.BooleanOptionalAction
        kwargs["default"] = spec.get("default", False)
    elif kind == "array":
        kwargs["type"] = _PY_TYPES[spec["items"]["type"]]
        fixed = spec.get("minItems") is not None and spec.get("minItems") == spec.get("maxItems")
        kwargs["nargs"] = spec["minItems"] if fixed else "+"
    else:
        kwargs["type"] = _PY_TYPES[kind]
        if "enum" in spec:
            kwargs["choices"] = spec["enum"]
    if required:
        kwargs["required"] = True
    return kwargs


def add_bridged_arguments(sub: argparse.ArgumentParser, command: BridgedCommand) -> None:
    """Add *command*'s schema-derived arguments (not the shared ``inputs`` ones)."""
    schema = _tool_definitions()[command.tool]["input_schema"]
    properties, required = schema["properties"], set(schema.get("required", ()))
    if command.positional:
        sub.add_argument(command.positional, help=properties[command.positional].get(
            "description", command.positional))
    for name in command.options:
        sub.add_argument(option_flag(name), dest=name,
                         **option_kwargs(properties[name], required=name in required))


def _params(command: BridgedCommand, args: argparse.Namespace) -> dict[str, Any]:
    """The handler's keyword arguments: every option the user set or that has a default."""
    values = {name: getattr(args, name) for name in command.options}
    if command.positional:
        values[command.positional] = getattr(args, command.positional)
    return {name: value for name, value in values.items() if value is not None}


def _call(command: BridgedCommand, **kwargs: Any) -> Any:
    """Run the handler; a missing video or OCR backend becomes a :class:`ToolError`."""
    try:
        return command.handler(**kwargs)
    except RuntimeError as exc:   # VideoBackendError, OcrUnavailableError
        raise ToolError(str(exc)) from exc


def writer(command: BridgedCommand) -> Callable[[Path, Path, argparse.Namespace], None]:
    """``op(src, target, args)`` for ``cli._write``: run the handler into *target*."""
    def write(src: Path, target: Path, args: argparse.Namespace) -> None:
        params = _params(command, args)
        if command.tool in _DATA_URI_WRITERS:
            result = _call(command, path=str(src), **params)
            target.write_bytes(base64.b64decode(result["data_uri"].split(",", 1)[1]))
        else:
            _call(command, source=str(src), destination=str(target), **params)
    return write


def reporter(command: BridgedCommand) -> Callable[[Path, argparse.Namespace], dict]:
    """``op(path, args) -> dict`` for ``cli._report``."""
    def report(path: Path, args: argparse.Namespace) -> dict:
        return _call(command, path=str(path), **_params(command, args))
    return report


def run_single(command: BridgedCommand, args: argparse.Namespace) -> int:
    """Run a single-call tool once and print its JSON result; 1 on a rejected argument."""
    try:
        result = _call(command, **_params(command, args))
    except (OSError, ValueError) as exc:   # a missing folder or bad query, not a crash
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
