"""Tests for ``python_finder``: where a frozen build looks for a Python with pip, in order."""
from __future__ import annotations

import sys

import pytest

from Imervue.plugin import python_finder as mod


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """A frozen build where no candidate exists unless a test adds one."""
    monkeypatch.setattr(mod, "_is_frozen", lambda: True)
    monkeypatch.setattr(mod, "_embedded_python_dir_path", lambda: tmp_path / "embed")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr(mod, "_find_python_from_registry", lambda: None)
    monkeypatch.setattr(mod, "_find_python_windows_install_paths", lambda: None)
    monkeypatch.setattr(mod, "_find_python_unix_paths", lambda: None)
    verified: list[str] = []
    monkeypatch.setattr(mod, "_verify_python", lambda p: verified.append(p) or True)
    return tmp_path, verified


def test_not_frozen_uses_the_running_interpreter(monkeypatch):
    monkeypatch.setattr(mod, "_is_frozen", lambda: False)
    assert mod._find_python() == sys.executable  # noqa: SLF001


def test_path_hit_wins(frozen, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"C:/bin/{name}.exe" if name == "python3" else None)
    assert mod._find_python() == "C:/bin/python3.exe"  # noqa: SLF001


def test_path_candidate_without_pip_is_skipped(frozen, monkeypatch):
    _tmp, _verified = frozen
    monkeypatch.setattr("shutil.which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(mod, "_verify_python", lambda p: p.endswith("py.exe"))
    assert mod._find_python() == "C:/bin/py.exe"  # noqa: SLF001


def test_platform_search_then_embedded(frozen, monkeypatch):
    tmp_path, _verified = frozen
    if sys.platform == "win32":
        monkeypatch.setattr(mod, "_find_python_windows_install_paths", lambda: "C:/Py/python.exe")
        assert mod._find_python() == "C:/Py/python.exe"  # noqa: SLF001
        monkeypatch.setattr(mod, "_find_python_from_registry", lambda: "C:/Reg/python.exe")
        assert mod._find_python() == "C:/Reg/python.exe"  # noqa: SLF001
        monkeypatch.setattr(mod, "_find_python_from_registry", lambda: None)
        monkeypatch.setattr(mod, "_find_python_windows_install_paths", lambda: None)
    else:
        monkeypatch.setattr(mod, "_find_python_unix_paths", lambda: "/usr/bin/python3")
        assert mod._find_python() == "/usr/bin/python3"  # noqa: SLF001
        monkeypatch.setattr(mod, "_find_python_unix_paths", lambda: None)
    assert mod._find_python() is None  # noqa: SLF001  (no embedded Python yet)
    embed = tmp_path / "embed"
    embed.mkdir()
    (embed / "python.exe").write_bytes(b"")
    assert mod._find_python() == str(embed / "python.exe")  # noqa: SLF001


def test_embedded_python_without_pip_is_rejected(frozen, monkeypatch):
    tmp_path, _verified = frozen
    (tmp_path / "embed").mkdir()
    (tmp_path / "embed" / "python.exe").write_bytes(b"")
    monkeypatch.setattr(mod, "_verify_python", lambda _p: False)
    assert mod._find_python() is None  # noqa: SLF001


def test_subprocess_kwargs_never_wait_on_stdin():
    kwargs = mod._subprocess_kwargs()  # noqa: SLF001
    assert kwargs["stdin"] is mod.subprocess.DEVNULL
    assert (kwargs["encoding"], kwargs["errors"]) == ("utf-8", "replace")
    assert ("creationflags" in kwargs) is (sys.platform == "win32")


def test_plugins_can_still_import_the_finder_from_pip_installer():
    """Imervue_Plugins imports ``_find_python`` from pip_installer (architecture.md §6)."""
    from Imervue.plugin import pip_installer
    for name in ("_find_python", "_verify_python", "_VERIFY_TIMEOUT_S", "_embedded_python_dir",
                 "_embedded_python_exe", "_subprocess_kwargs"):
        assert getattr(pip_installer, name) is getattr(mod, name), name
