"""Tests for the headless batch CLI."""
from __future__ import annotations

import argparse
import json

import numpy as np
import pytest
from PIL import Image

from Imervue.cli import (
    iter_image_paths,
    load_pipeline,
    main,
    output_path,
    validate_pipeline,
)


def _save(path, size=(200, 100), value=128, mode="RGB"):
    arr = np.full((size[1], size[0], len(mode)), value, dtype=np.uint8)
    Image.fromarray(arr, mode).save(str(path))
    return path


def _noisy(path, size=(128, 128)):
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8), "RGB").save(
        str(path))
    return path


# --- pure helpers ----------------------------------------------------------

def test_iter_image_paths_recursive(tmp_path):
    _save(tmp_path / "a.png")
    (tmp_path / "notes.txt").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    _save(sub / "b.jpg")
    flat = iter_image_paths([str(tmp_path)], recursive=False)
    deep = iter_image_paths([str(tmp_path)], recursive=True)
    assert any(p.name == "a.png" for p in flat)
    assert not any(p.name == "b.jpg" for p in flat)
    assert any(p.name == "b.jpg" for p in deep)


def test_output_path_with_and_without_out_dir(tmp_path):
    src = tmp_path / "pic.jpg"
    assert output_path(src, None, "_resized", None).name == "pic_resized.jpg"
    assert output_path(src, str(tmp_path / "out"), "", ".png").name == "pic.png"


# --- reporters -------------------------------------------------------------

def test_info_json(tmp_path, capsys):
    _save(tmp_path / "a.png", size=(120, 80))
    code = main(["info", str(tmp_path / "a.png"), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["width"] == 120 and payload[0]["height"] == 80


def test_stats_json(tmp_path, capsys):
    _noisy(tmp_path / "n.png")
    code = main(["stats", str(tmp_path / "n.png"), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "entropy" in payload[0] and "colorfulness" in payload[0]


def test_no_inputs_returns_error(tmp_path, capsys):
    assert main(["info", str(tmp_path / "empty")]) == 1


# --- writers ---------------------------------------------------------------

def test_resize_limits_long_edge(tmp_path):
    _save(tmp_path / "big.png", size=(400, 200))
    out_dir = tmp_path / "out"
    assert main(["resize", str(tmp_path / "big.png"), "--max", "64", "--out", str(out_dir)]) == 0
    with Image.open(out_dir / "big.png") as result:
        assert max(result.size) <= 64


def test_convert_changes_format(tmp_path):
    _save(tmp_path / "src.png")
    out_dir = tmp_path / "out"
    assert main(["convert", str(tmp_path / "src.png"), "--format", "JPEG",
                 "--out", str(out_dir)]) == 0
    target = out_dir / "src.jpg"
    assert target.exists()
    with Image.open(target) as img:
        assert img.format == "JPEG"


def test_watermark_writes_output(tmp_path):
    _save(tmp_path / "p.png")
    out_dir = tmp_path / "out"
    assert main(["watermark", str(tmp_path / "p.png"), "--text", "(c) Me",
                 "--out", str(out_dir)]) == 0
    assert (out_dir / "p.png").exists()


def test_optimize_hits_budget(tmp_path):
    _noisy(tmp_path / "big.png", size=(256, 256))
    out_dir = tmp_path / "out"
    assert main(["optimize", str(tmp_path / "big.png"), "--max-kb", "15",
                 "--format", "JPEG", "--out", str(out_dir)]) == 0
    assert (out_dir / "big.jpg").exists()


def test_dehaze_writes_output(tmp_path):
    _noisy(tmp_path / "h.png")
    out_dir = tmp_path / "out"
    assert main(["dehaze", str(tmp_path / "h.png"), "--strength", "1.0",
                 "--out", str(out_dir)]) == 0
    assert (out_dir / "h.png").exists()


def test_clahe_writes_output(tmp_path):
    _noisy(tmp_path / "c.png")
    out_dir = tmp_path / "out"
    assert main(["clahe", str(tmp_path / "c.png"), "--out", str(out_dir)]) == 0
    assert (out_dir / "c.png").exists()


def test_dither_two_levels_is_black_white(tmp_path):
    _save(tmp_path / "g.png", size=(64, 64), value=128)
    out_dir = tmp_path / "out"
    assert main(["dither", str(tmp_path / "g.png"), "--levels", "2",
                 "--out", str(out_dir)]) == 0
    with Image.open(out_dir / "g.png") as result:
        values = set(np.unique(np.array(result.convert("RGB"))).tolist())
    assert values <= {0, 255}


def test_distort_writes_output(tmp_path):
    _save(tmp_path / "d.png", size=(64, 64))
    out_dir = tmp_path / "out"
    assert main(["distort", str(tmp_path / "d.png"), "--mode", "swirl",
                 "--strength", "0.8", "--out", str(out_dir)]) == 0
    assert (out_dir / "d.png").exists()


def test_strip_keeps_extension(tmp_path):
    _save(tmp_path / "p.jpg")
    out_dir = tmp_path / "out"
    assert main(["strip", str(tmp_path / "p.jpg"), "--out", str(out_dir)]) == 0
    assert (out_dir / "p.jpg").exists()


def test_auto_orient_writes_output(tmp_path):
    _save(tmp_path / "o.png")
    out_dir = tmp_path / "out"
    assert main(["auto-orient", str(tmp_path / "o.png"), "--out", str(out_dir)]) == 0
    assert (out_dir / "o.png").exists()


def test_collage_combines_inputs(tmp_path):
    _save(tmp_path / "a.png", size=(40, 40))
    _save(tmp_path / "b.png", size=(40, 40))
    out = tmp_path / "out" / "grid.png"
    assert main(["collage", str(tmp_path / "a.png"), str(tmp_path / "b.png"),
                 "--columns", "2", "--out", str(out)]) == 0
    assert out.exists()


def test_collage_rejects_traversal_out(tmp_path, capsys):
    _save(tmp_path / "a.png")
    assert main(["collage", str(tmp_path / "a.png"), "--out", "../grid.png"]) == 2
    assert "must not contain '..'" in capsys.readouterr().err


def test_anaglyph_combines_stereo_pair(tmp_path):
    _save(tmp_path / "left.png", size=(40, 40), value=200)
    _save(tmp_path / "right.png", size=(40, 40), value=60)
    out = tmp_path / "out" / "ana.png"
    assert main(["anaglyph", str(tmp_path / "left.png"), str(tmp_path / "right.png"),
                 "--method", "dubois", "--out", str(out)]) == 0
    assert out.exists()


def test_preset_applies_saved_preset(tmp_path):
    from Imervue.image.develop_presets import DevelopPresetStore
    from Imervue.image.recipe import Recipe
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    DevelopPresetStore(user_setting_dict).save("MyPreset", Recipe())
    _save(tmp_path / "p.png")
    out_dir = tmp_path / "out"
    assert main(["preset", "MyPreset", str(tmp_path / "p.png"), "--out", str(out_dir)]) == 0
    # With --out the file keeps its stem + the op extension (no suffix).
    assert (out_dir / "p.png").exists()


def test_preset_unknown_returns_error(tmp_path, capsys):
    _save(tmp_path / "p.png")
    assert main(["preset", "NoSuchPreset", str(tmp_path / "p.png")]) == 1
    assert "unknown preset" in capsys.readouterr().err


def test_load_pipeline_accepts_list_and_object(tmp_path):
    bare = tmp_path / "a.json"
    bare.write_text(json.dumps([{"op": "invert"}]))
    wrapped = tmp_path / "b.json"
    wrapped.write_text(json.dumps({"pipeline": [{"op": "invert"}]}))
    assert load_pipeline(str(bare)) == [{"op": "invert"}]
    assert load_pipeline(str(wrapped)) == [{"op": "invert"}]


def test_validate_pipeline_reports_errors():
    assert validate_pipeline([{"op": "dehaze"}, {"op": "invert"}]) == []
    errors = validate_pipeline([{"op": "bogus"}, {"missing": "op"}])
    assert len(errors) == 2
    assert "unknown op" in errors[0]


def test_pipeline_applies_steps(tmp_path):
    _save(tmp_path / "p.png", size=(64, 64))
    spec = tmp_path / "pipe.json"
    spec.write_text(json.dumps({"pipeline": [{"op": "grayscale"}, {"op": "invert"}]}))
    out_dir = tmp_path / "out"
    assert main(["pipeline", str(spec), str(tmp_path / "p.png"), "--out", str(out_dir)]) == 0
    assert (out_dir / "p.png").exists()


def test_pipeline_unknown_op_is_validation_error(tmp_path, capsys):
    _save(tmp_path / "p.png")
    spec = tmp_path / "pipe.json"
    spec.write_text(json.dumps([{"op": "nope"}]))
    assert main(["pipeline", str(spec), str(tmp_path / "p.png")]) == 2
    assert "unknown op" in capsys.readouterr().err


def test_pipeline_bad_json_is_error(tmp_path):
    spec = tmp_path / "pipe.json"
    spec.write_text("{not valid json")
    _save(tmp_path / "p.png")
    assert main(["pipeline", str(spec), str(tmp_path / "p.png")]) == 2


def test_version_flag(capsys):
    import pytest
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "Imervue CLI" in capsys.readouterr().out


def test_list_ops_lists_subcommands(capsys):
    assert main(["list-ops"]) == 0
    out = capsys.readouterr().out
    assert "resize" in out and "pipeline" in out and "anaglyph" in out


def test_list_ops_json(capsys):
    assert main(["list-ops", "--json"]) == 0
    ops = json.loads(capsys.readouterr().out)
    commands = {o["command"] for o in ops}
    assert {"resize", "pipeline", "list-ops"} <= commands


def test_jobs_parallel_processes_all(tmp_path, capsys):
    for i in range(5):
        _save(tmp_path / f"f{i}.png", size=(40, 40))
    out_dir = tmp_path / "out"
    assert main(["resize", str(tmp_path), "--max", "16", "-j", "4", "--out", str(out_dir)]) == 0
    assert sorted(p.name for p in out_dir.glob("*.png")) == [f"f{i}.png" for i in range(5)]
    assert "5 processed, 0 skipped, 0 errors" in capsys.readouterr().err


def test_jobs_auto_zero(tmp_path):
    for i in range(3):
        _save(tmp_path / f"f{i}.png")
    out_dir = tmp_path / "out"
    assert main(["thumbnail", str(tmp_path), "-j", "0", "--out", str(out_dir)]) == 0
    assert len(list(out_dir.glob("*.png"))) == 3


def test_summary_counts_skips(tmp_path, capsys):
    _save(tmp_path / "a.png")
    out_dir = tmp_path / "out"
    main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir)])
    capsys.readouterr()
    main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir)])  # exists → skip
    assert "0 processed, 1 skipped, 0 errors" in capsys.readouterr().err


def test_parallel_output_is_input_ordered(tmp_path, capsys):
    for i in range(4):
        _save(tmp_path / f"{i}.png")
    out_dir = tmp_path / "out"
    main(["resize", str(tmp_path), "-j", "4", "--out", str(out_dir)])
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "->" in ln]
    names = [ln.split("->")[0].strip().rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for ln in lines]
    assert names == sorted(names)   # deterministic, input order


def test_dry_run_writes_nothing(tmp_path, capsys):
    _save(tmp_path / "a.png")
    out_dir = tmp_path / "out"
    assert main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir), "--dry-run"]) == 0
    assert "would write" in capsys.readouterr().out
    assert not out_dir.exists()


def test_rejects_parent_traversal_out_dir(tmp_path, capsys):
    _save(tmp_path / "a.png")
    code = main(["resize", str(tmp_path / "a.png"), "--out", "../escape"])
    assert code == 2
    assert "must not contain '..'" in capsys.readouterr().err


def test_skip_existing_without_overwrite(tmp_path, capsys):
    _save(tmp_path / "a.png")
    out_dir = tmp_path / "out"
    main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir)])
    capsys.readouterr()
    main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir)])
    assert "skip (exists)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Parser shape. ``py -m Imervue.cli`` is a public interface (architecture.md),
# so every subcommand and argument is pinned exactly; generated from the parser
# before ``build_parser`` was split.
# ---------------------------------------------------------------------------

# subcommand: (help, [(flags, dest, default, type, required, nargs, help, action) ...])
_EXPECTED = {'info': ('print image dimensions / format',
          [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
           (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
           (('--recursive',),
            'recursive',
            False,
            None,
            False,
            0,
            'recurse into folders',
            '_StoreTrueAction'),
           (('--dry-run',),
            'dry_run',
            False,
            None,
            False,
            0,
            'list actions, write nothing',
            '_StoreTrueAction'),
           (('--overwrite',),
            'overwrite',
            False,
            None,
            False,
            0,
            'overwrite existing outputs',
            '_StoreTrueAction'),
           (('-j', '--jobs'),
            'jobs',
            1,
            'int',
            False,
            None,
            'parallel workers (1=inline, 0=auto/all cores)',
            '_StoreAction'),
           (('--json',), 'json', False, None, False, 0, 'emit JSON', '_StoreTrueAction')]),
 'stats': ('print no-reference quality metrics',
           [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
            (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
            (('--recursive',),
             'recursive',
             False,
             None,
             False,
             0,
             'recurse into folders',
             '_StoreTrueAction'),
            (('--dry-run',),
             'dry_run',
             False,
             None,
             False,
             0,
             'list actions, write nothing',
             '_StoreTrueAction'),
            (('--overwrite',),
             'overwrite',
             False,
             None,
             False,
             0,
             'overwrite existing outputs',
             '_StoreTrueAction'),
            (('-j', '--jobs'),
             'jobs',
             1,
             'int',
             False,
             None,
             'parallel workers (1=inline, 0=auto/all cores)',
             '_StoreAction'),
            (('--json',), 'json', False, None, False, 0, 'emit JSON', '_StoreTrueAction')]),
 'convert': ('convert format',
             [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
              (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
              (('--recursive',),
               'recursive',
               False,
               None,
               False,
               0,
               'recurse into folders',
               '_StoreTrueAction'),
              (('--dry-run',),
               'dry_run',
               False,
               None,
               False,
               0,
               'list actions, write nothing',
               '_StoreTrueAction'),
              (('--overwrite',),
               'overwrite',
               False,
               None,
               False,
               0,
               'overwrite existing outputs',
               '_StoreTrueAction'),
              (('-j', '--jobs'),
               'jobs',
               1,
               'int',
               False,
               None,
               'parallel workers (1=inline, 0=auto/all cores)',
               '_StoreAction'),
              (('--format',),
               'format',
               'PNG',
               None,
               False,
               None,
               'JPEG / PNG / WEBP',
               '_StoreAction'),
              (('--quality',),
               'quality',
               90,
               'int',
               False,
               None,
               '1-100 for lossy formats',
               '_StoreAction')]),
 'resize': ('resize to a maximum long edge',
            [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
             (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
             (('--recursive',),
              'recursive',
              False,
              None,
              False,
              0,
              'recurse into folders',
              '_StoreTrueAction'),
             (('--dry-run',),
              'dry_run',
              False,
              None,
              False,
              0,
              'list actions, write nothing',
              '_StoreTrueAction'),
             (('--overwrite',),
              'overwrite',
              False,
              None,
              False,
              0,
              'overwrite existing outputs',
              '_StoreTrueAction'),
             (('-j', '--jobs'),
              'jobs',
              1,
              'int',
              False,
              None,
              'parallel workers (1=inline, 0=auto/all cores)',
              '_StoreAction'),
             (('--max',), 'max', 1600, 'int', False, None, 'max long edge in px', '_StoreAction')]),
 'thumbnail': ('make thumbnails',
               [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
                (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
                (('--recursive',),
                 'recursive',
                 False,
                 None,
                 False,
                 0,
                 'recurse into folders',
                 '_StoreTrueAction'),
                (('--dry-run',),
                 'dry_run',
                 False,
                 None,
                 False,
                 0,
                 'list actions, write nothing',
                 '_StoreTrueAction'),
                (('--overwrite',),
                 'overwrite',
                 False,
                 None,
                 False,
                 0,
                 'overwrite existing outputs',
                 '_StoreTrueAction'),
                (('-j', '--jobs'),
                 'jobs',
                 1,
                 'int',
                 False,
                 None,
                 'parallel workers (1=inline, 0=auto/all cores)',
                 '_StoreAction'),
                (('--size',),
                 'size',
                 256,
                 'int',
                 False,
                 None,
                 'thumbnail box in px',
                 '_StoreAction')]),
 'watermark': ('apply a text watermark',
               [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
                (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
                (('--recursive',),
                 'recursive',
                 False,
                 None,
                 False,
                 0,
                 'recurse into folders',
                 '_StoreTrueAction'),
                (('--dry-run',),
                 'dry_run',
                 False,
                 None,
                 False,
                 0,
                 'list actions, write nothing',
                 '_StoreTrueAction'),
                (('--overwrite',),
                 'overwrite',
                 False,
                 None,
                 False,
                 0,
                 'overwrite existing outputs',
                 '_StoreTrueAction'),
                (('-j', '--jobs'),
                 'jobs',
                 1,
                 'int',
                 False,
                 None,
                 'parallel workers (1=inline, 0=auto/all cores)',
                 '_StoreAction'),
                (('--text',), 'text', None, None, True, None, 'watermark text', '_StoreAction'),
                (('--corner',),
                 'corner',
                 'bottom-right',
                 None,
                 False,
                 None,
                 'placement corner',
                 '_StoreAction'),
                (('--opacity',), 'opacity', 0.6, 'float', False, None, '0..1', '_StoreAction')]),
 'optimize': ('encode under a target file size',
              [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
               (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
               (('--recursive',),
                'recursive',
                False,
                None,
                False,
                0,
                'recurse into folders',
                '_StoreTrueAction'),
               (('--dry-run',),
                'dry_run',
                False,
                None,
                False,
                0,
                'list actions, write nothing',
                '_StoreTrueAction'),
               (('--overwrite',),
                'overwrite',
                False,
                None,
                False,
                0,
                'overwrite existing outputs',
                '_StoreTrueAction'),
               (('-j', '--jobs'),
                'jobs',
                1,
                'int',
                False,
                None,
                'parallel workers (1=inline, 0=auto/all cores)',
                '_StoreAction'),
               (('--max-kb',), 'max_kb', None, 'float', True, None, None, '_StoreAction'),
               (('--format',),
                'format',
                'JPEG',
                None,
                False,
                None,
                'JPEG / WEBP',
                '_StoreAction')]),
 'dehaze': ('dark-channel-prior haze removal',
            [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
             (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
             (('--recursive',),
              'recursive',
              False,
              None,
              False,
              0,
              'recurse into folders',
              '_StoreTrueAction'),
             (('--dry-run',),
              'dry_run',
              False,
              None,
              False,
              0,
              'list actions, write nothing',
              '_StoreTrueAction'),
             (('--overwrite',),
              'overwrite',
              False,
              None,
              False,
              0,
              'overwrite existing outputs',
              '_StoreTrueAction'),
             (('-j', '--jobs'),
              'jobs',
              1,
              'int',
              False,
              None,
              'parallel workers (1=inline, 0=auto/all cores)',
              '_StoreAction'),
             (('--strength',), 'strength', 1.0, 'float', False, None, '0..1', '_StoreAction')]),
 'clahe': ('contrast-limited adaptive equalization',
           [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
            (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
            (('--recursive',),
             'recursive',
             False,
             None,
             False,
             0,
             'recurse into folders',
             '_StoreTrueAction'),
            (('--dry-run',),
             'dry_run',
             False,
             None,
             False,
             0,
             'list actions, write nothing',
             '_StoreTrueAction'),
            (('--overwrite',),
             'overwrite',
             False,
             None,
             False,
             0,
             'overwrite existing outputs',
             '_StoreTrueAction'),
            (('-j', '--jobs'),
             'jobs',
             1,
             'int',
             False,
             None,
             'parallel workers (1=inline, 0=auto/all cores)',
             '_StoreAction'),
            (('--clip',), 'clip', 2.0, 'float', False, None, 'clip limit', '_StoreAction'),
            (('--tiles',), 'tiles', 8, 'int', False, None, 'tile grid size', '_StoreAction')]),
 'dither': ('ordered (Bayer) dithering',
            [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
             (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
             (('--recursive',),
              'recursive',
              False,
              None,
              False,
              0,
              'recurse into folders',
              '_StoreTrueAction'),
             (('--dry-run',),
              'dry_run',
              False,
              None,
              False,
              0,
              'list actions, write nothing',
              '_StoreTrueAction'),
             (('--overwrite',),
              'overwrite',
              False,
              None,
              False,
              0,
              'overwrite existing outputs',
              '_StoreTrueAction'),
             (('-j', '--jobs'),
              'jobs',
              1,
              'int',
              False,
              None,
              'parallel workers (1=inline, 0=auto/all cores)',
              '_StoreAction'),
             (('--levels',),
              'levels',
              2,
              'int',
              False,
              None,
              'levels per channel (2-8)',
              '_StoreAction')]),
 'distort': ('swirl / pinch / ripple',
             [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
              (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
              (('--recursive',),
               'recursive',
               False,
               None,
               False,
               0,
               'recurse into folders',
               '_StoreTrueAction'),
              (('--dry-run',),
               'dry_run',
               False,
               None,
               False,
               0,
               'list actions, write nothing',
               '_StoreTrueAction'),
              (('--overwrite',),
               'overwrite',
               False,
               None,
               False,
               0,
               'overwrite existing outputs',
               '_StoreTrueAction'),
              (('-j', '--jobs'),
               'jobs',
               1,
               'int',
               False,
               None,
               'parallel workers (1=inline, 0=auto/all cores)',
               '_StoreAction'),
              (('--mode',),
               'mode',
               'swirl',
               None,
               False,
               None,
               'swirl / pinch / ripple',
               '_StoreAction'),
              (('--strength',), 'strength', 0.5, 'float', False, None, '-1..1', '_StoreAction')]),
 'auto-orient': ('bake EXIF orientation into pixels',
                 [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
                  (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
                  (('--recursive',),
                   'recursive',
                   False,
                   None,
                   False,
                   0,
                   'recurse into folders',
                   '_StoreTrueAction'),
                  (('--dry-run',),
                   'dry_run',
                   False,
                   None,
                   False,
                   0,
                   'list actions, write nothing',
                   '_StoreTrueAction'),
                  (('--overwrite',),
                   'overwrite',
                   False,
                   None,
                   False,
                   0,
                   'overwrite existing outputs',
                   '_StoreTrueAction'),
                  (('-j', '--jobs'),
                   'jobs',
                   1,
                   'int',
                   False,
                   None,
                   'parallel workers (1=inline, 0=auto/all cores)',
                   '_StoreAction')]),
 'strip': ('re-save without metadata (EXIF/XMP/ICC)',
           [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
            (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
            (('--recursive',),
             'recursive',
             False,
             None,
             False,
             0,
             'recurse into folders',
             '_StoreTrueAction'),
            (('--dry-run',),
             'dry_run',
             False,
             None,
             False,
             0,
             'list actions, write nothing',
             '_StoreTrueAction'),
            (('--overwrite',),
             'overwrite',
             False,
             None,
             False,
             0,
             'overwrite existing outputs',
             '_StoreTrueAction'),
            (('-j', '--jobs'),
             'jobs',
             1,
             'int',
             False,
             None,
             'parallel workers (1=inline, 0=auto/all cores)',
             '_StoreAction')]),
 'collage': ('composite many images into one grid',
             [((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
              (('--recursive',), 'recursive', False, None, False, 0, None, '_StoreTrueAction'),
              (('--columns',), 'columns', 3, 'int', False, None, 'grid columns', '_StoreAction'),
              (('--out',),
               'out',
               'collage.png',
               None,
               False,
               None,
               'output image file',
               '_StoreAction')]),
 'anaglyph': ('red-cyan 3D from a stereo pair',
              [((), 'left', None, None, True, None, 'left-eye image', '_StoreAction'),
               ((), 'right', None, None, True, None, 'right-eye image', '_StoreAction'),
               (('--method',),
                'method',
                'dubois',
                None,
                False,
                None,
                'dubois / color / gray / true',
                '_StoreAction'),
               (('--out',), 'out', None, None, False, None, 'output image file', '_StoreAction')]),
 'preset': ('apply a saved develop preset by name',
            [((), 'name', None, None, True, None, 'develop preset name', '_StoreAction'),
             ((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
             (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
             (('--recursive',),
              'recursive',
              False,
              None,
              False,
              0,
              'recurse into folders',
              '_StoreTrueAction'),
             (('--dry-run',),
              'dry_run',
              False,
              None,
              False,
              0,
              'list actions, write nothing',
              '_StoreTrueAction'),
             (('--overwrite',),
              'overwrite',
              False,
              None,
              False,
              0,
              'overwrite existing outputs',
              '_StoreTrueAction'),
             (('-j', '--jobs'),
              'jobs',
              1,
              'int',
              False,
              None,
              'parallel workers (1=inline, 0=auto/all cores)',
              '_StoreAction')]),
 'pipeline': ('apply an ordered JSON pipeline of ops',
              [((),
                'file',
                None,
                None,
                True,
                None,
                'pipeline JSON file ([{op, ...}] or {pipeline: [...]})',
                '_StoreAction'),
               ((), 'inputs', None, None, True, '+', 'image files or folders', '_StoreAction'),
               (('--out',), 'out', None, None, False, None, 'output directory', '_StoreAction'),
               (('--recursive',),
                'recursive',
                False,
                None,
                False,
                0,
                'recurse into folders',
                '_StoreTrueAction'),
               (('--dry-run',),
                'dry_run',
                False,
                None,
                False,
                0,
                'list actions, write nothing',
                '_StoreTrueAction'),
               (('--overwrite',),
                'overwrite',
                False,
                None,
                False,
                0,
                'overwrite existing outputs',
                '_StoreTrueAction'),
               (('-j', '--jobs'),
                'jobs',
                1,
                'int',
                False,
                None,
                'parallel workers (1=inline, 0=auto/all cores)',
                '_StoreAction')]),
 'list-ops': ('list available subcommands',
              [(('--json',), 'json', False, None, False, 0, 'emit JSON', '_StoreTrueAction')])}


# --- decode like the viewer: upright, sRGB, every format it opens ----------

def _portrait_jpeg(path):
    """40x20 stored, EXIF orientation 6: shown 20x40, marker in the shown top-right."""
    arr = np.zeros((20, 40, 3), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0)                      # stored top-left
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.fromarray(arr).save(path, exif=exif, quality=100, subsampling=0)
    return path


@pytest.mark.parametrize(("command", "extra", "name"), [
    ("convert", ["--format", "PNG"], "p.png"),
    ("resize", ["--max", "400"], "p.jpg"),
    ("thumbnail", ["--size", "400"], "p.png"),
    ("watermark", ["--text", "x"], "p.png"),
    ("strip", [], "p.jpg"),
    ("auto-orient", [], "p.png"),
    ("dehaze", [], "p.png"),
])
def test_tagged_photo_comes_out_upright(tmp_path, command, extra, name):
    """The outputs carry no EXIF, so a portrait phone photo came out sideways."""
    src = _portrait_jpeg(tmp_path / "p.jpg")
    out_dir = tmp_path / "out"
    assert main([command, str(src), *extra, "--out", str(out_dir)]) == 0
    with Image.open(out_dir / name) as out:
        assert out.size == (20, 40)
        assert 0x0112 not in out.getexif()


def test_colour_profile_is_converted_to_srgb(tmp_path):
    """Dropping a Display P3 profile without converting washed the colours out."""
    from _icc_profiles import DISPLAY_P3
    src = tmp_path / "p3.png"
    Image.new("RGB", (4, 4), (0, 255, 0)).save(src, icc_profile=DISPLAY_P3)
    out_dir = tmp_path / "out"
    assert main(["convert", str(src), "--format", "PNG", "--out", str(out_dir)]) == 0
    with Image.open(out_dir / "p3.png") as out:
        red, green, _blue, _alpha = out.getpixel((0, 0))
        assert "icc_profile" not in out.info
        assert red == 0 and green == 255      # P3 green is outside sRGB: clipped, not faded


def test_heic_input_is_opened(tmp_path, capsys):
    """HEIC was listed as an input but its opener never registered, so info crashed."""
    pytest.importorskip("pillow_heif")
    from Imervue.image.heif_support import ensure_heif_opener
    ensure_heif_opener()
    src = tmp_path / "a.heic"
    Image.new("RGB", (64, 32)).save(src)
    assert main(["info", str(src), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["width"] == 64


def test_info_reports_the_upright_size(tmp_path, capsys):
    src = _portrait_jpeg(tmp_path / "p.jpg")
    assert main(["info", str(src), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)[0]
    assert (payload["width"], payload["height"]) == (20, 40)


def test_an_unreadable_file_is_reported_and_the_rest_still_run(tmp_path, capsys):
    good = _save(tmp_path / "a.png", size=(10, 10))
    (tmp_path / "b.png").write_bytes(b"not a png")
    assert main(["info", str(good), str(tmp_path / "b.png"), "--json"]) == 1
    captured = capsys.readouterr()
    assert [item["width"] for item in json.loads(captured.out)] == [10]
    assert "b.png" in captured.err


def test_a_writer_counts_an_unreadable_file_as_an_error(tmp_path, capsys):
    (tmp_path / "bad.png").write_bytes(b"not a png")
    assert main(["convert", str(tmp_path / "bad.png"), "--format", "PNG",
                 "--out", str(tmp_path / "out")]) == 1
    assert "1 errors" in capsys.readouterr().err


def _describe(parser: argparse.ArgumentParser) -> dict:
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))  # noqa: SLF001
    helps = {choice.dest: choice.help for choice in sub._choices_actions}  # noqa: SLF001
    return {
        name: (helps[name], [
            (tuple(a.option_strings), a.dest, a.default, getattr(a.type, "__name__", None),
             a.required, a.nargs, a.help, type(a).__name__)
            for a in p._actions if not isinstance(a, argparse._HelpAction)  # noqa: SLF001
        ])
        for name, p in sub.choices.items()
    }


def test_subcommands_and_arguments_are_unchanged():
    from Imervue.cli import build_parser
    actual = _describe(build_parser())
    assert list(actual) == list(_EXPECTED)
    for name, expected in _EXPECTED.items():
        assert actual[name] == expected, name


def test_top_level_parser():
    from Imervue.cli import _CLI_VERSION, build_parser
    parser = build_parser()
    assert (parser.prog, parser.description) == ("Imervue.cli", "Imervue headless image CLI")
    version = next(a for a in parser._actions if isinstance(a, argparse._VersionAction))  # noqa: SLF001
    assert version.version == f"Imervue CLI {_CLI_VERSION}"
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))  # noqa: SLF001
    assert (sub.dest, sub.required) == ("command", True)


def test_load_pipeline_reads_a_file_saved_with_a_bom(tmp_path):
    f = tmp_path / "pipeline.json"
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps([{"op": "invert"}]).encode("utf-8"))
    assert load_pipeline(str(f)) == [{"op": "invert"}]
