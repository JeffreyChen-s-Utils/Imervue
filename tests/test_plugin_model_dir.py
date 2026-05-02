"""Tests for the shared plugin model-directory helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from Imervue.plugin.model_dir import discover_models, ensure_model_dir


# ---------------------------------------------------------------------------
# ensure_model_dir
# ---------------------------------------------------------------------------


def test_ensure_creates_missing_directory(tmp_path: Path):
    target = tmp_path / "models"
    assert not target.exists()
    result = ensure_model_dir(target)
    assert target.is_dir()
    assert result == target


def test_ensure_creates_intermediate_parents(tmp_path: Path):
    nested = tmp_path / "plugin" / "subdir" / "models"
    ensure_model_dir(nested)
    assert nested.is_dir()


def test_ensure_idempotent_on_existing_directory(tmp_path: Path):
    target = tmp_path / "already_here"
    target.mkdir()
    sentinel = target / "marker.bin"
    sentinel.write_bytes(b"keep me")
    ensure_model_dir(target)
    assert sentinel.read_bytes() == b"keep me"


def test_ensure_accepts_string_path(tmp_path: Path):
    target = tmp_path / "from_string"
    result = ensure_model_dir(str(target))
    assert isinstance(result, Path)
    assert result.is_dir()


def test_ensure_returns_path_instance(tmp_path: Path):
    """Even when the directory already existed, the return value
    must be a fresh ``Path`` so callers can chain ``.glob`` on it."""
    target = tmp_path / "exists"
    target.mkdir()
    result = ensure_model_dir(target)
    assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# discover_models
# ---------------------------------------------------------------------------


def test_discover_creates_missing_directory(tmp_path: Path):
    target = tmp_path / "missing"
    found = discover_models(target)
    assert found == []
    assert target.is_dir()


def test_discover_returns_matching_files(tmp_path: Path):
    target = tmp_path / "models"
    target.mkdir()
    (target / "a.onnx").write_bytes(b"")
    (target / "b.onnx").write_bytes(b"")
    (target / "readme.txt").write_text("ignore me")
    found = sorted(p.name for p in discover_models(target))
    assert found == ["a.onnx", "b.onnx"]


def test_discover_custom_pattern(tmp_path: Path):
    target = tmp_path / "weights"
    target.mkdir()
    (target / "model.pth").write_bytes(b"")
    (target / "other.onnx").write_bytes(b"")
    found = [p.name for p in discover_models(target, "*.pth")]
    assert found == ["model.pth"]


def test_discover_empty_dir_returns_empty_list(tmp_path: Path):
    target = tmp_path / "empty"
    target.mkdir()
    assert discover_models(target) == []


def test_discover_idempotent_does_not_wipe_existing_models(tmp_path: Path):
    """Calling discover repeatedly must not remove or reset files."""
    target = tmp_path / "models"
    discover_models(target)  # creates dir
    (target / "weights.onnx").write_bytes(b"hello")
    discover_models(target)  # second call must not touch the file
    assert (target / "weights.onnx").read_bytes() == b"hello"


# ---------------------------------------------------------------------------
# Plugin integration — every ONNX-discovering plugin must use the helper.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "ai_denoise.ai_denoise_plugin",
        "ai_colorize.ai_colorize_plugin",
        "ai_motion_deblur.ai_motion_deblur_plugin",
        "ai_portrait_relight.ai_portrait_relight_plugin",
        "ai_style_transfer.ai_style_transfer_plugin",
    ],
)
def test_onnx_plugin_creates_models_dir_on_discover(module_name: str):
    """The module-level _MODELS_DIR must exist after discovery — the
    helper guarantees the folder is on disk so users can drop weights.
    """
    import importlib
    module = importlib.import_module(module_name)
    # Trigger discovery — this is the call that promises to mkdir.
    module._discover_onnx_models()  # noqa: SLF001
    assert module._MODELS_DIR.is_dir()  # noqa: SLF001
