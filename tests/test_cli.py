"""Tests for the headless batch CLI."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image

from Imervue.cli import iter_image_paths, main, output_path


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


def test_dry_run_writes_nothing(tmp_path, capsys):
    _save(tmp_path / "a.png")
    out_dir = tmp_path / "out"
    assert main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir), "--dry-run"]) == 0
    assert "would write" in capsys.readouterr().out
    assert not out_dir.exists()


def test_skip_existing_without_overwrite(tmp_path, capsys):
    _save(tmp_path / "a.png")
    out_dir = tmp_path / "out"
    main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir)])
    capsys.readouterr()
    main(["resize", str(tmp_path / "a.png"), "--out", str(out_dir)])
    assert "skip (exists)" in capsys.readouterr().out
