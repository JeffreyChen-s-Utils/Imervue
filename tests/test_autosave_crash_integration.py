"""Two documents survive an actual process exit between native bundle and metadata commits."""
import json
import os
import subprocess
import sys
from pathlib import Path

from Imervue.paint.auto_save import list_snapshots, recover_snapshot


def test_background_crash_then_fresh_process_recovery(tmp_path):
    child = Path(__file__).parent / "helpers" / "autosave_crash_child.py"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    command = [sys.executable, "-X", "utf8", str(child)]
    crashed = subprocess.run([*command, "write", str(tmp_path)], env=env,
                             capture_output=True, text=True, timeout=60, check=False)
    assert crashed.returncode == 23, crashed.stderr
    directory = tmp_path / "snapshots"
    snapshots = list_snapshots(directory)
    assert len(snapshots) == 2 and len({s.document_id for s in snapshots}) == 2
    assert sorted(int(recover_snapshot(s).layer_at(0).image[0, 0, 0])
                  for s in snapshots) == [17, 64]
    assert len(list(directory.glob("*.imervue"))) == 3  # incomplete commit is ignored
    restarted = subprocess.run([*command, "recover", str(tmp_path)], env=env,
                               capture_output=True, text=True, timeout=60, check=False)
    assert restarted.returncode == 0, restarted.stderr
    result = json.loads((tmp_path / "recovered.json").read_text(encoding="utf-8"))
    assert result == {"restored": 2, "values": [17, 64], "dirty": True, "repeat": 0}
