"""Tests for the constraints every plugin dependency install runs under."""
from __future__ import annotations

from pathlib import Path

from Imervue.plugin import pip_constraints as pc


def test_every_opencv_distribution_stays_below_5():
    assert set(pc.PIP_CONSTRAINTS) == {f"{d}<5" for d in pc.OPENCV_DISTRIBUTIONS}
    assert "opencv-python-headless<5" in pc.PIP_CONSTRAINTS  # what nudenet pulls


def test_write_constraints_file_one_requirement_per_line(tmp_path):
    path = pc.write_constraints_file(tmp_path)
    assert path == tmp_path / pc.CONSTRAINTS_FILENAME
    assert path.read_text(encoding="utf-8").splitlines() == list(pc.PIP_CONSTRAINTS)


def test_write_constraints_file_overwrites(tmp_path):
    (tmp_path / pc.CONSTRAINTS_FILENAME).write_text("stale<1\n", encoding="utf-8")
    path = pc.write_constraints_file(tmp_path)
    assert "stale" not in path.read_text(encoding="utf-8")


def test_install_command_passes_the_constraints_file():
    cmd = pc.install_command("py.exe", "nudenet", Path("c.txt"))
    assert cmd == [
        "py.exe", "-m", "pip", "install", "--no-input",
        "--disable-pip-version-check", "-c", "c.txt", "nudenet",
    ]


def test_install_command_appends_extra_args():
    cmd = pc.install_command("py", "rembg", Path("c.txt"), ["--target", "site"])
    assert cmd[-3:] == ["rembg", "--target", "site"]


def test_install_command_empty_extra_args_is_not_mutated():
    extra: list[str] = []
    pc.install_command("py", "x", Path("c.txt"), extra)
    assert extra == []
