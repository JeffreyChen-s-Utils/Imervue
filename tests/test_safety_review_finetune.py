"""Tests for the fine-tune script's pure config helpers.

The training itself needs weights + a GPU and isn't unit-tested; the argument
building, dataset validation, and base-weight resolution are.
"""
from __future__ import annotations

import pytest

from safety_review import finetune


def test_data_yaml_path_returns_existing(tmp_path):
    (tmp_path / "data.yaml").write_text("names: {}", encoding="utf-8")
    assert finetune.data_yaml_path(str(tmp_path)).endswith("data.yaml")


def test_data_yaml_path_missing_raises(tmp_path):
    missing = str(tmp_path)
    with pytest.raises(FileNotFoundError):
        finetune.data_yaml_path(missing)


def test_train_config_builds_expected_kwargs(tmp_path):
    (tmp_path / "data.yaml").write_text("names: {}", encoding="utf-8")
    cfg = finetune.train_config(str(tmp_path), epochs=50, imgsz=512)
    assert cfg["epochs"] == 50
    assert cfg["imgsz"] == 512
    assert cfg["exist_ok"] is True
    assert cfg["name"] == "finetune"
    assert cfg["data"].endswith("data.yaml")
    assert "device" not in cfg          # omitted when not requested


def test_train_config_includes_device_when_given(tmp_path):
    (tmp_path / "data.yaml").write_text("x", encoding="utf-8")
    assert finetune.train_config(str(tmp_path), device="0")["device"] == "0"


def test_resolve_base_weights_passthrough_for_a_path():
    assert finetune.resolve_base_weights("/models/mine.pt") == "/models/mine.pt"


def test_resolve_base_weights_erax_downloads(monkeypatch):
    import huggingface_hub
    calls = {}

    def _fake(repo_id, filename, revision):
        calls.update(repo_id=repo_id, filename=filename, revision=revision)
        return "weights/erax.pt"

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", _fake)
    assert finetune.resolve_base_weights("erax") == "weights/erax.pt"
    assert calls["repo_id"] == finetune._ERAX_REPO
    assert calls["revision"] == finetune._ERAX_REVISION


def test_default_output_is_in_the_dataset_dir(tmp_path):
    assert finetune.default_output(str(tmp_path)).endswith("finetuned.pt")


def test_parse_args_defaults():
    args = finetune._parse_args(["/data/ds"])
    assert args.dataset_dir == "/data/ds"
    assert args.base == "erax"
    assert args.epochs == finetune.DEFAULT_EPOCHS
    assert args.device is None


def test_parse_args_overrides():
    args = finetune._parse_args(
        ["/ds", "--base", "m.pt", "--epochs", "30", "--imgsz", "320",
         "--device", "cpu", "--out", "o.pt"])
    assert (args.base, args.epochs, args.imgsz, args.device, args.out) == (
        "m.pt", 30, 320, "cpu", "o.pt")
