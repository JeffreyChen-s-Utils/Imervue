"""Directory replacement rollback, resource reservations and retained model files."""
from pathlib import Path

import pytest

from Imervue.plugin import installation as mod


def test_reinstall_preserves_models_assets_and_replaces_code(tmp_path):
    final = tmp_path / "plugin"
    (final / "models").mkdir(parents=True)
    (final / "assets").mkdir()
    (final / "models" / "model.onnx").write_bytes(b"weights")
    (final / "assets" / "user.png").write_bytes(b"asset")
    (final / "__init__.py").write_text("old", encoding="utf-8")
    with mod.installation_stage(final) as stage:
        (stage / "__init__.py").write_text("new", encoding="utf-8")
        mod.commit_installation(stage, final)
    assert (final / "__init__.py").read_text(encoding="utf-8") == "new"
    assert (final / "models" / "model.onnx").read_bytes() == b"weights"
    assert (final / "assets" / "user.png").read_bytes() == b"asset"
    assert list(tmp_path.iterdir()) == [final]


def test_swap_failure_rolls_back_and_releases_reservation(tmp_path, monkeypatch):
    final = tmp_path / "plugin"
    final.mkdir()
    (final / "old").write_bytes(b"working")
    real = mod.os.replace
    def fail_stage(source, destination):
        if Path(source).name.startswith(".imervue-plugin-"):
            raise PermissionError("locked")
        return real(source, destination)
    monkeypatch.setattr(mod.os, "replace", fail_stage)
    with pytest.raises(PermissionError, match="locked"), mod.installation_stage(final) as stage:
        (stage / "new").write_bytes(b"new")
        mod.commit_installation(stage, final)
    assert (final / "old").read_bytes() == b"working"
    assert list(tmp_path.iterdir()) == [final]
    with mod.installation_stage(final) as stage:
        assert stage.is_dir()


def test_duplicate_reservation_and_cancel_before_commit(tmp_path):
    final = tmp_path / "plugin"
    final.mkdir()
    (final / "old").write_bytes(b"old")
    def cancel():
        raise InterruptedError("cancelled")
    with mod.installation_stage(final) as stage:
        with pytest.raises(FileExistsError, match="in progress"), mod.installation_stage(final):
            pass
        with pytest.raises(InterruptedError):
            mod.commit_installation(stage, final, before_commit=cancel)
    assert (final / "old").read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [final]


def test_backup_cleanup_failure_keeps_committed_install(tmp_path, monkeypatch, caplog):
    final = tmp_path / "plugin"
    final.mkdir()
    (final / "old").write_bytes(b"old")
    real = mod.shutil.rmtree
    def locked_backup(path, *args, **kwargs):
        if Path(path).name.startswith(".imervue-backup-"):
            raise PermissionError("backup locked")
        return real(path, *args, **kwargs)
    monkeypatch.setattr(mod.shutil, "rmtree", locked_backup)
    with mod.installation_stage(final) as stage:
        (stage / "new").write_bytes(b"new")
        mod.commit_installation(stage, final)
    assert (final / "new").read_bytes() == b"new"
    assert "could not remove backup" in caplog.text
    assert len(list(tmp_path.glob(".imervue-backup-*"))) == 1


def test_model_copy_failure_preserves_previous_install(tmp_path, monkeypatch):
    final = tmp_path / "plugin"
    (final / "models").mkdir(parents=True)
    (final / "models" / "model.onnx").write_bytes(b"weights")
    def fail(*_args, **_kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(mod.shutil, "copytree", fail)
    with pytest.raises(OSError, match="disk full"), mod.installation_stage(final) as stage:
        mod.commit_installation(stage, final)
    assert (final / "models" / "model.onnx").read_bytes() == b"weights"
    assert list(tmp_path.iterdir()) == [final]
