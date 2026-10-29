"""CLI argument declarations and ordered parser construction."""
from __future__ import annotations

import argparse
from Imervue import cli_tools
from Imervue.cli_native import _FORMAT_EXT, _RGB_MAX


_CONVERT_EXT = {**_FORMAT_EXT, "TIFF": ".tif", "BMP": ".bmp", "AVIF": ".avif", "HEIC": ".heic",
                "JXL": ".jxl"}


_WHITE = (_RGB_MAX, _RGB_MAX, _RGB_MAX)


_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")


_CLI_VERSION = "1.0"


_EMIT_JSON = "emit JSON"


def _add_common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("inputs", nargs="+", help="image files or folders")
    sub.add_argument("--out", default=None, help="output directory")
    sub.add_argument("--recursive", action="store_true", help="recurse into folders")
    sub.add_argument("--dry-run", action="store_true", help="list actions, write nothing")
    sub.add_argument("--overwrite", action="store_true", help="overwrite existing outputs")
    sub.add_argument("-j", "--jobs", type=int, default=1,
                     help="parallel workers (1=inline, 0=auto/all cores)")
    sub.add_argument("--output-conflict", choices=("rename", "skip", "replace"),
                     help="output conflict policy (default: skip, or replace with --overwrite)")
    sub.add_argument("--export-metadata", choices=("all", "no_location", "none"),
                     help="explicit metadata policy (may re-encode; strip always removes metadata)")
    sub.add_argument("--result-report",
                     help="write atomic JSON results with committed output links")


_COMMON = None


_JSON_FLAG = (("--json",), {"action": "store_true", "help": _EMIT_JSON})


def _rgb_option(flag: str, default: tuple[int, int, int], help_text: str) -> tuple:
    return ((flag,), {"type": int, "nargs": 3, "default": list(default),
                      "metavar": ("R", "G", "B"), "help": help_text})


_SUBCOMMANDS: tuple[tuple[str, str, tuple], ...] = (
    ("info", "print image dimensions / format", (_COMMON, _JSON_FLAG)),
    ("stats", "print no-reference quality metrics", (_COMMON, _JSON_FLAG)),
    ("convert", "convert format", (
        _COMMON,
        (("--format",), {"type": str.upper, "choices": list(_CONVERT_EXT), "default": "PNG",
                         "help": "output format"}),
        (("--quality",), {"type": int, "default": 90, "help": "1-100 for lossy formats"}),
    )),
    ("resize", "resize to a maximum long edge, or to an exact width / height", (
        _COMMON, (("--max",), {"type": int, "default": 1600, "help": "max long edge in px"}),
        (("--width",), {"type": int, "default": None,
                        "help": "exact width in px (with no --height, height keeps the aspect)"}),
        (("--height",), {"type": int, "default": None,
                         "help": "exact height in px (with no --width, width keeps the aspect)"}),
    )),
    ("thumbnail", "make thumbnails", (
        _COMMON, (("--size",), {"type": int, "default": 256, "help": "thumbnail box in px"}),
    )),
    ("watermark", "apply a text watermark", (
        _COMMON,
        (("--text",), {"required": True, "help": "watermark text"}),
        (("--corner",), {"default": "bottom-right", "choices": _CORNERS,
                         "help": "placement corner"}),
        (("--opacity",), {"type": float, "default": 0.6, "help": "0..1"}),
        (("--font-fraction",), {"type": float, "default": 0.035, "dest": "font_fraction",
                                "help": "text height as a fraction of the image, 0.005..0.2"}),
        _rgb_option("--color", _WHITE, "text colour"),
        (("--shadow",), {"action": argparse.BooleanOptionalAction, "default": True,
                         "help": "drop shadow behind the text"}),
    )),
    ("optimize", "encode under a target file size", (
        _COMMON,
        (("--max-kb",), {"type": float, "required": True, "dest": "max_kb"}),
        (("--format",), {"default": "JPEG", "help": "JPEG / WEBP"}),
    )),
    ("dehaze", "dark-channel-prior haze removal", (
        _COMMON, (("--strength",), {"type": float, "default": 1.0, "help": "0..1"}),
    )),
    ("clahe", "contrast-limited adaptive equalization", (
        _COMMON,
        (("--clip",), {"type": float, "default": 2.0, "help": "clip limit"}),
        (("--tiles",), {"type": int, "default": 8, "help": "tile grid size"}),
    )),
    ("dither", "ordered (Bayer) dithering", (
        _COMMON, (("--levels",), {"type": int, "default": 2, "help": "levels per channel (2-8)"}),
    )),
    ("distort", "swirl / pinch / ripple", (
        _COMMON,
        (("--mode",), {"default": "swirl", "help": "swirl / pinch / ripple"}),
        (("--strength",), {"type": float, "default": 0.5, "help": "-1..1"}),
    )),
    ("painterly", "repaint in oil-paint brush strokes", (
        _COMMON, (("--seed",), {"type": int, "default": 0, "help": "stroke placement seed"}),
    )),
    ("auto-orient", "bake EXIF orientation into pixels", (_COMMON,)),
    ("strip", "re-save without metadata (EXIF/XMP/ICC)", (_COMMON,)),
    ("collage", "composite many images into one grid", (
        (("inputs",), {"nargs": "+", "help": "image files or folders"}),
        (("--recursive",), {"action": "store_true"}),
        (("--columns",), {"type": int, "default": 3, "help": "grid columns"}),
        (("--cell-width",), {"type": int, "default": 400, "dest": "cell_width",
                             "help": "cell width in px"}),
        (("--cell-height",), {"type": int, "default": 400, "dest": "cell_height",
                              "help": "cell height in px"}),
        (("--gap",), {"type": int, "default": 12, "help": "gap between cells in px"}),
        (("--margin",), {"type": int, "default": 20, "help": "outer margin in px"}),
        _rgb_option("--background", _WHITE, "background colour"),
        (("--out",), {"default": "collage.png", "help": "output image file"}),
    )),
    ("anaglyph", "red-cyan 3D from a stereo pair", (
        (("left",), {"help": "left-eye image"}),
        (("right",), {"help": "right-eye image"}),
        (("--method",), {"default": "dubois", "help": "dubois / color / gray / true"}),
        (("--out",), {"default": None, "help": "output image file"}),
    )),
    ("preset", "apply a saved develop preset by name", (
        (("name",), {"help": "develop preset name"}), _COMMON,
    )),
    ("pipeline", "apply an ordered JSON pipeline of ops", (
        (("file",), {"help": "pipeline JSON file ([{op, ...}] or {pipeline: [...]})"}), _COMMON,
    )),
)


_LIST_OPS = ("list-ops", "list available subcommands", (_JSON_FLAG,))


def _add_row(subs, name: str, help_text: str, arguments: tuple) -> None:
    sub = subs.add_parser(name, help=help_text)
    for argument in arguments:
        if argument is _COMMON:
            _add_common(sub)
        else:
            flags, kwargs = argument
            cli_tools.add_argument_as_written(sub, *flags, **kwargs)


def _add_bridged(subs, bridged: cli_tools.BridgedCommand) -> None:
    """A subcommand generated from an MCP tool: shared inputs unless it runs once."""
    sub = subs.add_parser(bridged.command, help=bridged.help)
    if bridged.kind != cli_tools.SINGLE:
        _add_common(sub)
    cli_tools.add_bridged_arguments(sub, bridged)
    if bridged.kind == cli_tools.REPORTER:
        sub.add_argument(*_JSON_FLAG[0], **_JSON_FLAG[1])


def build_parser() -> argparse.ArgumentParser:
    """The ``Imervue.cli`` parser: the ``_SUBCOMMANDS`` rows, the MCP tools, then ``list-ops``."""
    parser = argparse.ArgumentParser(prog="Imervue.cli", description="Imervue headless image CLI")
    parser.add_argument("--version", action="version", version=f"Imervue CLI {_CLI_VERSION}")
    subs = parser.add_subparsers(dest="command", required=True)
    for row in _SUBCOMMANDS:
        _add_row(subs, *row)
    for bridged in cli_tools.bridged_commands().values():
        _add_bridged(subs, bridged)
    _add_row(subs, *_LIST_OPS)
    return parser
