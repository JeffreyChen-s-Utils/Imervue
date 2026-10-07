"""The cancellation benchmark runs actual workers and preserves output on bad arguments."""
import json
import os
import subprocess
import sys
from pathlib import Path


def test_fresh_process_retirement_report_and_invalid_repeat(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "report.json"
    command = [sys.executable, "-X", "utf8", str(root / "scripts/performance_workers.py"),
               "--output", str(output), "--repeats", "1"]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True,
                            timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["measurement"]["blocked_ms"] == 250
    for case in report["measurement"]["cases"].values():
        assert len(case["ui_request"]["samples_ms"]) == 1
        assert case["ui_request"]["p95_ms"] < 50
        assert case["actual_retirement"]["min_ms"] >= 250
        assert case["ui_heartbeat"]["samples_ms"]
    prior = output.read_bytes()
    command[-1] = "0"
    failed = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True,
                            timeout=60, check=False)
    assert failed.returncode != 0 and output.read_bytes() == prior
