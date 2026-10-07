"""The supplied-image RAM benchmark rejects failures and records real decoded buffers."""
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


def test_real_child_admission_and_isolated_profile(tmp_path):
    image = tmp_path / "tiny.png"
    Image.new("RGBA", (8, 6), (1, 2, 3, 255)).save(image)
    output = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/performance_ram.py", str(image),
         "--limit-mib", "1", "--repeats", "1", "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    run = report["runs"][0]
    assert run["results"] == [{"path": str(image), "decoded": True, "actual_bytes": 192}]
    assert run["accounted_bytes_after"] == run["retained_array_bytes"] == 192
    assert run["peak_accounted_bytes"] == 1024**2
    assert report["source_sha256"]["scripts/performance_ram.py"]
    assert len(report["fixtures"][str(image)]) == 64
    assert report["metrics"]["rss_peak_bytes"] > 0


def test_bad_input_preserves_existing_report(tmp_path):
    image = tmp_path / "damaged.png"
    image.write_bytes(b"damaged raster")
    output = tmp_path / "report.json"
    output.write_text("previous valid report", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/performance_ram.py", str(image),
         "--repeats", "1", "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=False,
    )
    assert result.returncode != 0
    assert "RuntimeError" in result.stderr
    assert output.read_text(encoding="utf-8") == "previous valid report"
