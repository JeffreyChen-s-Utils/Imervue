"""Developer measurements must be repeatable, isolated and honest about failures."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from scripts import performance_benchmark as benchmark
from scripts import performance_support as support
from _qt_skip import pytestmark as real_gl_mark


@pytest.mark.parametrize("samples", [[], [-1], [math.inf], [math.nan]])
def test_invalid_samples_rejected(samples):
    with pytest.raises(ValueError):
        support.summarize(samples)


def test_nearest_rank_and_raw_measurements():
    samples = list(range(20))
    summary = support.summarize(samples)
    assert summary["median_ms"] == 9.5
    assert summary["p95_ms"] == 18
    assert summary["samples_ms"] == samples
    assert support.summarize([7])["p95_ms"] == 7


def test_rss_counters_and_repeat_count():
    current, peak = support.working_set()
    assert 0 < current <= peak
    seen = []
    result = support.measure(lambda: seen.append(1), repeats=3)
    assert len(seen) == len(result["samples_ms"]) == 3
    assert result["rss_peak_bytes"] >= result["rss_before_bytes"] > 0
    assert result["rss_growth_bytes"] >= 0
    with pytest.raises(ValueError):
        support.measure(lambda: None, repeats=0)


def test_sampler_stops_after_failure():
    def fail():
        raise OSError("disk full")
    with patch.object(support.threading.Thread, "join", autospec=True) as join:
        with pytest.raises(OSError, match="disk full"):
            support.measure(fail)
        join.assert_called_once()


def test_gradient_repeatable_and_non_square():
    image = support.gradient(31, 13, 5)
    assert image.shape == (13, 31, 4)
    assert image.dtype == np.uint8
    np.testing.assert_array_equal(image, support.gradient(31, 13, 5))
    assert np.all(image[..., 3] == 255)
    assert not np.array_equal(image, support.gradient(31, 13, 6))


def test_fixture_ownership_and_repeatability(tmp_path):
    root = tmp_path / "fixtures"
    first = support.prepare_fixtures(root, quick=True)
    second = support.prepare_fixtures(root, quick=True)
    assert first == second
    assert first["libraries"] == [100, 1000]
    assert len(list((root / "library-1000").rglob("*.jpg"))) == 1000
    assert len(list((root / "large-cache").glob("*.png"))) == 1000
    assert json.loads((root / "manifest.json").read_text()) == first
    with pytest.raises(ValueError, match="differs"):
        support.prepare_fixtures(root, quick=False)
    unowned = tmp_path / "photos"
    unowned.mkdir()
    photo = unowned / "original.jpg"
    photo.write_bytes(b"keep me")
    with pytest.raises(ValueError, match="ownership"):
        support.prepare_fixtures(unowned, quick=True)
    assert photo.read_bytes() == b"keep me"
    (root / "24mp.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="content changed"):
        support.prepare_fixtures(root, quick=True)


def test_hard_link_fallback_and_existing_file(tmp_path):
    seed = tmp_path / "seed.jpg"
    seed.write_bytes(b"seed")
    target = tmp_path / "nested" / "copy.jpg"
    with patch.object(support.os, "link", side_effect=OSError("unsupported")):
        support._link(seed, target)
    assert target.read_bytes() == b"seed"
    target.write_bytes(b"owned but already present")
    support._link(seed, target)
    assert target.read_bytes() == b"owned but already present"


def test_json_replace_keeps_previous_result_if_write_fails(tmp_path):
    output = tmp_path / "result.json"
    support.write_json(output, {"value": 1})
    with patch.object(Path, "write_text", side_effect=PermissionError("read-only")), \
            pytest.raises(PermissionError):
        support.write_json(output, {"value": 2})
    assert json.loads(output.read_text()) == {"value": 1}
    support.write_json(output, {"value": 3})
    assert json.loads(output.read_text()) == {"value": 3}
    assert not output.with_suffix(".json.tmp").exists()


def test_isolated_profile_restores_paths_even_after_exception(tmp_path):
    from Imervue.system import app_paths
    home = Path.home()
    setting_path = app_paths.user_settings_path()
    plugins = app_paths.plugins_dir()
    local = os.environ.get("LOCALAPPDATA")
    profile = tmp_path / "profile"
    with pytest.raises(RuntimeError, match="stop"), support.isolated_profile(profile):
        assert Path.home() == profile / "home"
        assert app_paths.user_settings_path() == profile / "settings.json"
        assert app_paths.plugins_dir() == profile / "empty-plugins"
        assert os.environ["LOCALAPPDATA"] == str(profile / "local")
        raise RuntimeError("stop")
    assert Path.home() == home
    assert app_paths.user_settings_path() == setting_path
    assert app_paths.plugins_dir() == plugins
    assert os.environ.get("LOCALAPPDATA") == local
    with pytest.raises(FileExistsError), support.isolated_profile(profile):
        pytest.fail("reused profile")


def test_unknown_scenario_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        benchmark.dispatch("unknown", tmp_path, tmp_path, 1)


def test_parent_records_partial_failure_and_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "prepare_fixtures", lambda *a, **k: {"quick": True})
    monkeypatch.setattr(benchmark, "environment", lambda: {})
    calls = []

    def run(command, **_kwargs):
        calls.append(command[-1])
        if command[-1] == "startup":
            raise benchmark.subprocess.TimeoutExpired(command, 1800)
        output = Path(command[command.index("--output") + 1])
        support.write_json(output, {"passed": True})

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    output = tmp_path / "report.json"
    monkeypatch.setattr(benchmark.sys, "argv", ["benchmark", "--fixtures", str(tmp_path / "owned"),
                       "--output", str(output), "--quick", "--only", "startup", "paint"])
    with pytest.raises(SystemExit, match="failed"):
        benchmark.main()
    report = json.loads(output.read_text())
    assert calls == ["startup", "paint"]
    assert list(report["failures"]) == ["startup"]
    assert report["scenarios"]["paint"] == {"passed": True}


def test_real_child_index_history_cache_report(tmp_path):
    report = tmp_path / "report.json"
    subprocess.run([sys.executable, "-X", "utf8", str(benchmark.ROOT / "scripts"
                    / "performance_benchmark.py"), "--fixtures", str(tmp_path / "fixture"),
                    "--output", str(report), "--quick", "--only", "library-small", "paint", "cache"],
                   check=True, capture_output=True, text=True, timeout=90)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["failures"] == {}
    assert result["scenarios"]["library-small"]["count"] == 100
    assert result["scenarios"]["paint"]["layer_bytes"] == 384 * 216 * 4 * 6
    assert result["scenarios"]["cache"]["entries"] == 1000
    assert result["environment"]["tool_sha256"]["performance_gl.py"]


class TestActualFrames:
    pytestmark = real_gl_mark

    def test_full_resolution_upload_has_source_pixel(self, qapp, tmp_path):
        from PIL import Image
        from scripts.performance_gl import first_image_frames
        path = tmp_path / "image.png"
        Image.new("RGBA", (64, 48), (31, 63, 127, 255)).save(path)
        result = first_image_frames(str(path), 3)
        assert result["sample_rgba"] == [31, 63, 127, 255]
        assert len(result["warm_full_texture_frame"]["samples_ms"]) == 3

    def test_wall_uses_real_frame_and_expected_pixel(self, qapp, tmp_path):
        support.write_json(tmp_path / "manifest.json", {"libraries": [100, 1000]})
        result = benchmark.wall(tmp_path, tmp_path, 3, large=True)
        assert result["count"] == 1000
        assert result["pixel_rgba"] == [255, 255, 255, 255]
        assert 0 < result["visible_rects"] < 1000
        assert result["vram_bytes"] > 0
        assert len(result["steady_gl_frame"]["samples_ms"]) == 30
