"""Headless batch command-line interface.

Runs the app's pure image operations from the shell without starting the Qt
GUI, e.g.::

    py -m Imervue.cli resize photos/ --max 1600 --out web/
    py -m Imervue.cli watermark a.jpg --text "© Me" --corner bottom-right
    py -m Imervue.cli info *.png --json

Only pure NumPy / Pillow code is imported here — never ``Imervue.gui`` or any
Qt/OpenGL module — so the CLI stays usable on a headless server. Input
collection, output-path resolution and each operation are small testable units;
``main`` only wires argparse to them.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from Imervue import cli_tools
from Imervue.cli_batch import _process_one, _write
from Imervue.cli_composites import cmd_anaglyph, cmd_collage
from Imervue.cli_native import (
    _FORMAT_EXT, _RGB_MAX, _resize_to, _rgb, op_autoorient, op_clahe, op_convert, op_dehaze,
    op_distort, op_dither, op_optimize, op_painterly, op_resize, op_strip, op_thumbnail,
    op_watermark,
)
from Imervue.cli_parser import (
    _CLI_VERSION, _COMMON, _CONVERT_EXT, _CORNERS, _EMIT_JSON, _JSON_FLAG, _LIST_OPS,
    _SUBCOMMANDS, _WHITE, _add_bridged, _add_common, _add_row, _rgb_option, build_parser,
)
from Imervue.cli_paths import (
    _NO_INPUTS, _checked_path, _ensure_parent, _kept_extension, _validated_out_dir,
    iter_image_paths, output_path,
)
from Imervue.cli_pipeline import (
    _MAX_PIPELINE_STEPS, cmd_pipeline, load_pipeline, op_pipeline, validate_pipeline,
)
from Imervue.cli_pipeline_steps import (
    _LUMA, _PIPELINE_OPS, _step_clahe, _step_clarity, _step_dehaze, _step_distort,
    _step_dither, _step_grayscale, _step_invert, _step_texture, _step_watermark,
)
from Imervue.cli_presets import cmd_preset, op_preset
from Imervue.cli_reports import _BYTES_PER_KB, _REPORTERS, _report, op_info, op_stats
from Imervue.cli_workers import _resolve_workers, _run_outputs


__all__ = [
    '_BYTES_PER_KB',
    '_CLI_VERSION',
    '_COMMON',
    '_CONVERT_EXT',
    '_CORNERS',
    '_EMIT_JSON',
    '_FORMAT_EXT',
    '_JSON_FLAG',
    '_LIST_OPS',
    '_LUMA',
    '_MAX_PIPELINE_STEPS',
    '_MULTI_COMMANDS',
    '_NO_INPUTS',
    '_PIPELINE_OPS',
    '_REPORTERS',
    '_RGB_MAX',
    '_SUBCOMMANDS',
    '_WHITE',
    '_WRITE_SPEC',
    '_add_bridged',
    '_add_common',
    '_add_row',
    '_checked_path',
    '_ensure_parent',
    '_kept_extension',
    '_process_one',
    '_report',
    '_resize_to',
    '_resolve_workers',
    '_rgb',
    '_rgb_option',
    '_run_bridged',
    '_run_outputs',
    '_step_clahe',
    '_step_clarity',
    '_step_dehaze',
    '_step_distort',
    '_step_dither',
    '_step_grayscale',
    '_step_invert',
    '_step_texture',
    '_step_watermark',
    '_validated_out_dir',
    '_write',
    'build_parser',
    'cmd_anaglyph',
    'cmd_collage',
    'cmd_list_ops',
    'cmd_pipeline',
    'cmd_preset',
    'iter_image_paths',
    'load_pipeline',
    'main',
    'op_autoorient',
    'op_clahe',
    'op_convert',
    'op_dehaze',
    'op_distort',
    'op_dither',
    'op_info',
    'op_optimize',
    'op_painterly',
    'op_pipeline',
    'op_preset',
    'op_resize',
    'op_stats',
    'op_strip',
    'op_thumbnail',
    'op_watermark',
    'output_path',
    'run',
    'validate_pipeline',
]


_WRITE_SPEC = {
    "convert": (op_convert, "_converted", lambda a: _CONVERT_EXT[a.format.upper()]),
    "resize": (op_resize, "_resized", lambda _a: None),
    "thumbnail": (op_thumbnail, "_thumb", lambda _a: ".png"),
    "watermark": (op_watermark, "_wm", lambda _a: ".png"),
    "optimize": (op_optimize, "_opt", lambda a: _FORMAT_EXT.get(a.format.upper(), ".jpg")),
    "dehaze": (op_dehaze, "_dehaze", lambda _a: ".png"),
    "clahe": (op_clahe, "_clahe", lambda _a: ".png"),
    "dither": (op_dither, "_dither", lambda _a: ".png"),
    "distort": (op_distort, "_distort", lambda _a: ".png"),
    "painterly": (op_painterly, "_painterly", lambda _a: ".png"),
    "auto-orient": (op_autoorient, "_oriented", lambda _a: ".png"),
    "strip": (op_strip, "_clean", lambda _a: None),
}


def run(args) -> int:
    """Execute the parsed *args*; return a process exit code."""
    if args.command in _MULTI_COMMANDS:
        return _MULTI_COMMANDS[args.command](args)
    bridged = cli_tools.bridged_commands().get(args.command)
    if bridged is not None and bridged.kind == cli_tools.SINGLE:
        return cli_tools.run_single(bridged, args)
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print(_NO_INPUTS, file=sys.stderr)
        return 1
    if bridged is not None:
        return _run_bridged(args, paths, bridged)
    if args.command in _REPORTERS:
        return _report(args, paths, _REPORTERS[args.command])
    return _write(args, paths, *_WRITE_SPEC[args.command])


def _run_bridged(args, paths: Sequence[Path], bridged: cli_tools.BridgedCommand) -> int:
    """Run a subcommand generated from an MCP tool over *paths*."""
    if bridged.kind == cli_tools.REPORTER:
        return _report(args, paths, cli_tools.reporter(bridged))
    extension = bridged.extension
    return _write(args, paths, cli_tools.writer(bridged), bridged.suffix, lambda _a: extension)


def cmd_list_ops(args) -> int:
    """List the available subcommands and their one-line help."""
    ops: list[dict] = []
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            ops = [{"command": a.dest, "help": a.help or ""}
                   for a in action._choices_actions]
            break
    if getattr(args, "json", False):
        print(json.dumps(ops, indent=2))
    else:
        for op in ops:
            print(f"{op['command']:14} {op['help']}")
    return 0


_MULTI_COMMANDS = {
    "collage": cmd_collage, "anaglyph": cmd_anaglyph,
    "preset": cmd_preset, "pipeline": cmd_pipeline, "list-ops": cmd_list_ops,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Parse *argv* and run the requested sub-command."""
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    from Imervue.system.pillow_setup import configure_pillow
    configure_pillow()
    sys.exit(main())
