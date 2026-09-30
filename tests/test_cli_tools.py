"""Tests for the CLI subcommands generated from the MCP tool definitions."""
from __future__ import annotations

import argparse
import json

import numpy as np
import pytest
from PIL import Image

from Imervue.cli import build_parser, main
from Imervue.cli_tools import (
    BRIDGED,
    COVERED_BY,
    REPORTER,
    SINGLE,
    WRITER,
    ToolError,
    bridged_commands,
    first_sentence,
    option_flag,
    option_kwargs,
    reporter,
    writer,
)
from Imervue.mcp_server.tools import _TOOL_DEFINITIONS

_SCHEMAS = {tool["name"]: tool["input_schema"] for tool in _TOOL_DEFINITIONS}
_WRITERS = sorted(c.command for c in bridged_commands().values() if c.kind == WRITER)
_REPORTERS = sorted(c.command for c in bridged_commands().values() if c.kind == REPORTER)
# Arguments a writer cannot run without.
_REQUIRED_EXTRA = {
    "crop": ["--x", "2", "--y", "2", "--width", "8", "--height", "6"],
    "rotate": ["--operation", "rotate_90"],
}
# Writers whose input is not a still image, tested on their own below.
_NOT_A_STILL = {"video-frame"}


def _photo(path, size=(32, 24)):
    """A noisy RGB image with an opaque subject, so every effect has something to do."""
    rng = np.random.default_rng(3)
    arr = rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8)
    Image.fromarray(arr, "RGB").save(path)
    return path


def _subject_png(path):
    """A transparent PNG with an opaque square, as the puppet importer expects."""
    arr = np.zeros((64, 64, 4), dtype=np.uint8)
    arr[16:48, 16:48] = (200, 80, 40, 255)
    Image.fromarray(arr, "RGBA").save(path)
    return path


def _subparser(command: str) -> argparse.ArgumentParser:
    sub = next(a for a in build_parser()._actions  # noqa: SLF001
               if isinstance(a, argparse._SubParsersAction))  # noqa: SLF001
    return sub.choices[command]


def _options(command: str) -> dict[str, argparse.Action]:
    return {a.dest: a for a in _subparser(command)._actions}  # noqa: SLF001


# --- every MCP tool reaches the CLI ------------------------------------------

def test_every_mcp_tool_is_a_cli_subcommand_exactly_once():
    assert set(COVERED_BY) | set(BRIDGED) == set(_SCHEMAS)
    assert not set(COVERED_BY) & set(BRIDGED)


def test_covered_tools_name_hand_written_subcommands():
    from Imervue.cli import _SUBCOMMANDS
    hand_written = {row[0] for row in _SUBCOMMANDS}
    assert set(COVERED_BY.values()) <= hand_written


def test_generated_names_are_unique_and_clash_with_nothing_hand_written():
    from Imervue.cli import _SUBCOMMANDS
    names = list(BRIDGED.values())
    assert len(names) == len(set(names))
    assert not set(names) & ({row[0] for row in _SUBCOMMANDS} | {"list-ops"})


def test_list_ops_lists_the_generated_subcommands_before_itself(capsys):
    assert main(["list-ops", "--json"]) == 0
    listed = [op["command"] for op in json.loads(capsys.readouterr().out)]
    assert listed[-1] == "list-ops"
    assert listed[-1 - len(BRIDGED):-1] == list(BRIDGED.values())


@pytest.mark.parametrize(("tool", "kind"), [
    ("solarize_image", WRITER), ("crop_image", WRITER), ("puppet_from_png", WRITER),
    ("extract_video_frame", WRITER), ("error_level_analysis", WRITER),
    ("read_histogram", REPORTER), ("puppet_inspect", REPORTER), ("ocr_text", REPORTER),
    ("list_images", SINGLE), ("search_images", SINGLE), ("reverse_geocode", SINGLE),
])
def test_kind_follows_the_schema(tool, kind):
    assert bridged_commands()[BRIDGED[tool]].kind == kind


# --- arguments mirror the schema ----------------------------------------------

@pytest.mark.parametrize("tool", list(BRIDGED))
def test_every_schema_option_is_an_argument_with_its_default_and_choices(tool):
    command = bridged_commands()[BRIDGED[tool]]
    schema = _SCHEMAS[tool]
    options = _options(command.command)
    for name in command.options:
        spec, action = schema["properties"][name], options[name]
        assert option_flag(name) in action.option_strings
        assert action.required == (name in schema.get("required", ()))
        if spec["type"] == "boolean":
            assert action.default == spec.get("default", False)
        else:
            assert action.default == spec.get("default")
        assert action.choices == spec.get("enum")


@pytest.mark.parametrize("tool", list(BRIDGED))
def test_io_properties_come_from_the_shared_inputs(tool):
    command = bridged_commands()[BRIDGED[tool]]
    dests = set(_options(command.command))
    if command.kind == SINGLE:
        assert "inputs" not in dests
    else:
        assert {"inputs", "out", "dry_run", "overwrite", "jobs"} <= dests
        assert not {"source", "destination", "path"} & dests
    assert ("json" in dests) == (command.kind == REPORTER)


def test_a_folder_tool_takes_the_folder_as_a_positional():
    folder = _options("list-images")["folder"]
    assert folder.option_strings == []
    assert bridged_commands()["list-images"].positional == "folder"


def test_option_kwargs_boolean_defaults_to_false_and_offers_the_negation():
    kwargs = option_kwargs({"type": "boolean"}, required=False)
    assert kwargs["action"] is argparse.BooleanOptionalAction
    assert kwargs["default"] is False


def test_option_kwargs_fixed_array_takes_that_many_values():
    spec = {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3}
    assert option_kwargs(spec, required=False)["nargs"] == 3
    assert option_kwargs(spec, required=False)["type"] is int


def test_option_kwargs_open_array_takes_one_or_more():
    spec = {"type": "array", "items": {"type": "number"}, "minItems": 2}
    kwargs = option_kwargs(spec, required=False)
    assert (kwargs["nargs"], kwargs["type"]) == ("+", float)


def test_option_kwargs_enum_required_and_range_help():
    spec = {"type": "string", "enum": ["a", "b"], "description": "Pick one."}
    kwargs = option_kwargs(spec, required=True)
    assert (kwargs["choices"], kwargs["required"], kwargs["help"]) == (["a", "b"], True, "Pick one")
    ranged = option_kwargs({"type": "number", "minimum": 0, "maximum": 1}, required=False)
    assert ranged["help"] == "0..1"
    assert option_kwargs({"type": "integer", "minimum": 1}, required=False)["help"] == "1.."
    assert option_kwargs({"type": "integer"}, required=False)["help"] is None


def test_option_flag_is_kebab_case():
    assert option_flag("zone_gains") == "--zone-gains"
    assert option_flag("k1") == "--k1"


@pytest.mark.parametrize(("description", "expected"), [
    ("Crop a region. The box is clamped.", "crop a region"),
    ("Search with the DSL (e.g. 'ext:png'). More.", "search with the DSL (e.g. 'ext:png')"),
    ("Return stats — a read-out.", "return stats"),
    ("One sentence only.", "one sentence only"),
])
def test_first_sentence(description, expected):
    assert first_sentence(description) == expected


def test_suffix_and_extension():
    commands = bridged_commands()
    assert commands["film-grain"].suffix == "_film_grain"
    assert commands["puppet-from-png"].extension == ".puppet"
    assert commands["solarize"].extension == ".png"


# --- writers -----------------------------------------------------------------

@pytest.mark.parametrize("command", [c for c in _WRITERS if c not in _NOT_A_STILL])
def test_every_writer_writes_an_image_or_rig(tmp_path, command):
    src = (_subject_png(tmp_path / "in.png") if command == "puppet-from-png"
           else _photo(tmp_path / "in.png"))
    out = tmp_path / "out"
    assert main([command, str(src), *_REQUIRED_EXTRA.get(command, []), "--out", str(out)]) == 0
    written = out / f"in{bridged_commands()[command].extension}"
    assert written.is_file()
    if written.suffix == ".png":
        with Image.open(written) as img:
            assert img.width > 0


def test_a_writer_without_out_names_the_copy_after_the_command(tmp_path):
    src = _photo(tmp_path / "in.png")
    assert main(["film-grain", str(src), "--seed", "1"]) == 0
    assert (tmp_path / "in_film_grain.png").is_file()


def test_writer_options_reach_the_handler(tmp_path):
    src = _photo(tmp_path / "in.png", size=(40, 20))
    out = tmp_path / "out"
    assert main(["crop", str(src), "--x", "0", "--y", "0", "--width", "10", "--height", "5",
                 "--out", str(out)]) == 0
    with Image.open(out / "in.png") as img:
        assert img.size == (10, 5)
    assert main(["rotate", str(src), "--operation", "rotate_90", "--out", str(out),
                 "--overwrite"]) == 0
    with Image.open(out / "in.png") as img:
        assert img.size == (20, 40)


def test_list_and_boolean_options_reach_the_handler(tmp_path):
    src = _photo(tmp_path / "in.png")
    out = tmp_path / "out"
    assert main(["channel-mixer", str(src), "--red", "0", "0", "1", "--green", "0", "1", "0",
                 "--blue", "1", "0", "0", "--out", str(out)]) == 0
    with Image.open(src) as original, Image.open(out / "in.png") as swapped:
        before, after = np.asarray(original.convert("RGB")), np.asarray(swapped.convert("RGB"))
    assert np.array_equal(after[..., 0], before[..., 2])
    assert main(["emboss", str(src), "--no-grayscale", "--out", str(out)]) == 0


def test_an_enum_option_rejects_an_unknown_value(tmp_path, capsys):
    src = _photo(tmp_path / "in.png")
    with pytest.raises(SystemExit) as exit_info:
        main(["colormap", str(src), "--name", "rainbow"])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_a_required_option_is_required(tmp_path, capsys):
    src = _photo(tmp_path / "in.png")
    with pytest.raises(SystemExit):
        main(["crop", str(src), "--x", "0"])
    assert "required" in capsys.readouterr().err


def test_a_rejected_value_is_one_files_error(tmp_path, capsys):
    src = _photo(tmp_path / "in.png")
    assert main(["crop", str(src), "--x", "999", "--y", "0", "--width", "4", "--height", "4",
                 "--out", str(tmp_path / "out")]) == 1
    assert "1 errors" in capsys.readouterr().err


def test_a_writer_skips_an_unreadable_file_and_goes_on(tmp_path, capsys):
    (tmp_path / "bad.png").write_bytes(b"not a png")
    _photo(tmp_path / "good.png")
    out = tmp_path / "out"
    assert main(["solarize", str(tmp_path), "--out", str(out)]) == 1
    assert (out / "good.png").is_file()
    assert "1 processed, 0 skipped, 1 errors" in capsys.readouterr().err


def test_writer_dry_run_writes_nothing(tmp_path, capsys):
    src = _photo(tmp_path / "in.png")
    assert main(["glow", str(src), "--out", str(tmp_path / "out"), "--dry-run"]) == 0
    assert "would write" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_ela_writes_the_map_as_a_png(tmp_path):
    src = _photo(tmp_path / "in.png", size=(20, 12))
    out = tmp_path / "out"
    assert main(["ela", str(src), "--quality", "80", "--out", str(out)]) == 0
    with Image.open(out / "in.png") as img:
        assert (img.format, img.size) == ("PNG", (20, 12))


def test_video_frame_extracts_a_frame(tmp_path):
    imageio = pytest.importorskip("imageio.v2")
    pytest.importorskip("imageio_ffmpeg")
    video = tmp_path / "clip.mp4"
    with imageio.get_writer(str(video), fps=5, format="ffmpeg") as out:   # type: ignore[attr-defined]
        for value in (0, 255):
            out.append_data(np.full((16, 16, 3), value, dtype=np.uint8))
    assert main(["video-frame", str(video), "--frame-index", "1",
                 "--out", str(tmp_path / "out")]) == 0
    with Image.open(tmp_path / "out" / "clip.png") as frame:
        assert np.asarray(frame.convert("L")).mean() > 200


def test_a_backend_failure_is_a_tool_error(tmp_path):
    from Imervue.image.video_frames import VideoBackendError

    def broken(**_kwargs):
        raise VideoBackendError("no ffmpeg")

    command = bridged_commands()["video-frame"]
    object.__setattr__(command, "handler", broken)
    args = argparse.Namespace(frame_index=0)
    with pytest.raises(ToolError, match="no ffmpeg"):
        writer(command)(tmp_path / "a.mp4", tmp_path / "a.png", args)
    assert issubclass(ToolError, ValueError)   # counted as one file's error by the CLI


def test_a_missing_ocr_backend_is_a_tool_error(tmp_path):
    from Imervue.image.ocr import OcrUnavailableError

    def broken(**_kwargs):
        raise OcrUnavailableError("no tesseract")

    command = bridged_commands()["ocr"]
    object.__setattr__(command, "handler", broken)
    with pytest.raises(ToolError, match="no tesseract"):
        reporter(command)(tmp_path / "a.png", argparse.Namespace(min_confidence=0.0))


# --- reporters ---------------------------------------------------------------

@pytest.mark.parametrize(("command", "key"), [
    ("metadata", "width"), ("xmp", "path"), ("gps", "path"), ("dominant-colors", "colors"),
    ("sharpness", "path"), ("statistics", "path"), ("histogram", "path"), ("ocr", "available"),
])
def test_reporters_print_one_json_object_per_image(tmp_path, capsys, command, key):
    _photo(tmp_path / "a.png")
    _photo(tmp_path / "b.png")
    assert main([command, str(tmp_path), "--json"]) == 0
    results = json.loads(capsys.readouterr().out)
    assert len(results) == 2
    assert all(key in item for item in results)


def test_reporter_options_reach_the_handler(tmp_path, capsys):
    src = _photo(tmp_path / "a.png")
    assert main(["dominant-colors", str(src), "--n-colors", "2", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["color_count"] <= 2


def test_reporter_without_json_prints_key_value_lines(tmp_path, capsys):
    src = _photo(tmp_path / "a.png")
    assert main(["sharpness", str(src)]) == 0
    assert f"path={src}" in capsys.readouterr().out


def test_puppet_round_trip_through_the_cli(tmp_path, capsys):
    src = _subject_png(tmp_path / "rig.png")
    assert main(["puppet-from-png", str(src), "--cell-size", "16",
                 "--out", str(tmp_path / "out")]) == 0
    rig = tmp_path / "out" / "rig.puppet"
    capsys.readouterr()
    assert main(["puppet-inspect", str(rig), "--json"]) == 0
    inventory = json.loads(capsys.readouterr().out)[0]
    assert inventory["drawables"]


def test_puppet_inspect_reports_a_file_that_is_no_rig(tmp_path, capsys):
    bogus = tmp_path / "bogus.puppet"
    bogus.write_bytes(b"not a zip")
    assert main(["puppet-inspect", str(bogus)]) == 1
    assert "error:" in capsys.readouterr().err


# --- single-run tools ----------------------------------------------------------

def test_list_images_prints_the_folder_listing(tmp_path, capsys):
    _photo(tmp_path / "a.png")
    sub = tmp_path / "sub"
    sub.mkdir()
    _photo(sub / "b.png")
    assert main(["list-images", str(tmp_path)]) == 0
    assert len(json.loads(capsys.readouterr().out)["images"]) == 1
    assert main(["list-images", str(tmp_path), "--recursive"]) == 0
    assert len(json.loads(capsys.readouterr().out)["images"]) == 2


def test_search_filters_with_the_query(tmp_path, capsys):
    _photo(tmp_path / "sunset.png")
    _photo(tmp_path / "beach.png")
    assert main(["search", str(tmp_path), "--query", "name:sunset"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["count"] == 1


def test_search_rejects_a_query_the_standalone_cli_cannot_answer(tmp_path, capsys):
    assert main(["search", str(tmp_path), "--query", "rating:>3"]) == 1
    assert "error:" in capsys.readouterr().err


def test_similar_groups_duplicates(tmp_path, capsys):
    _photo(tmp_path / "a.png")
    _photo(tmp_path / "b.png")
    assert main(["similar", str(tmp_path), "--threshold", "0"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["groups"]


def test_collection_stats_counts_the_folder(tmp_path, capsys):
    _photo(tmp_path / "a.png")
    assert main(["collection-stats", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 1


def test_reverse_geocode_takes_negative_coordinates(capsys):
    assert main(["reverse-geocode", "--latitude", "-33.87", "--longitude", "151.21"]) == 0
    assert "Sydney" in json.loads(capsys.readouterr().out)["place"]


def test_a_single_run_tool_reports_a_missing_folder(tmp_path, capsys):
    assert main(["list-images", str(tmp_path / "missing")]) == 1
    assert "does not exist" in capsys.readouterr().err
