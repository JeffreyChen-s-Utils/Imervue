"""Real boundary regressions for the full-program runtime review."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread, current_thread

import pytest
from PySide6.QtCore import Qt

from Imervue.plugin import pip_install_workers, pip_installer
from Imervue.plugin.subprocess_util import terminate_process
from Imervue.system import file_transfer
from Imervue.user_settings import user_setting_dict as settings
from cloud_share import uploaders


@pytest.mark.parametrize("cancel", ["after-launch", "during-launch", "deadline"])
def test_pip_reaps_silent_child_on_cancel_or_deadline(qapp, monkeypatch, cancel):
    worker = pip_installer._InstallWorker([], sys.executable)
    started = Event()
    children = []
    real_popen = subprocess.Popen
    command = [sys.executable, "-c", "import time; time.sleep(30)"]

    def launch(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        children.append(proc)
        if cancel == "during-launch":
            worker.stop()
        started.set()
        return proc

    def install(*_args):
        code = worker._run_with_live_output(command, timeout=0.1 if cancel == "deadline" else 30)
        return code == 0, str(code)

    monkeypatch.setattr(pip_install_workers.subprocess, "Popen", launch)
    monkeypatch.setattr(worker, "_install_all", install)
    results = []
    worker.result_ready.connect(lambda *args: results.append(args), Qt.ConnectionType.DirectConnection)
    worker.start()
    try:
        assert started.wait(3)
        if cancel == "after-launch":
            worker.stop()
        assert worker.wait(2000), "pip child remains blocked despite cancel/deadline"
        assert children[0].poll() is not None
        assert len(results) == 1 and results[0][0] is False
    finally:
        for proc in children:
            terminate_process(proc)
        worker.wait(5000)
        worker.deleteLater()


@pytest.mark.parametrize("action", ["create", "rename", "delete", "switch"])
def test_inflight_save_cannot_undo_profile_operation(tmp_path, monkeypatch, action):
    settings.cancel_pending_save()
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_user_settings_path", lambda: path)
    settings._profile_state.update(current="default", available=["default"])
    settings.user_setting_dict.clear()
    settings.user_setting_dict["sentinel"] = "default value"
    settings.write_user_setting()
    assert settings.create_profile("client")
    read = Event()
    release = Event()
    entered = Event()
    real_save = settings._save_settings
    result = []

    def held_save(source, payload):
        if current_thread().name == "inflight-save":
            read.set()
            assert release.wait(5)
        return real_save(source, payload)

    def change():
        entered.set()
        operations = {
            "create": lambda: settings.create_profile("new", copy_from_current=True),
            "rename": lambda: settings.rename_profile("client", "renamed"),
            "delete": lambda: settings.delete_profile("client"),
            "switch": lambda: settings.switch_profile("client"),
        }
        result.append(operations[action]())

    monkeypatch.setattr(settings, "_save_settings", held_save)
    saver = Thread(target=settings._flush_save, name="inflight-save")
    changer = Thread(target=change)
    saver.start()
    try:
        assert read.wait(3)
        changer.start()
        assert entered.wait(3)
        changer.join(0.1)
    finally:
        release.set()
        saver.join(5)
        if changer.ident is not None:
            changer.join(5)
    assert not saver.is_alive() and not changer.is_alive()
    assert result == [True]
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {"create": {"default", "client", "new"}, "rename": {"default", "renamed"},
                "delete": {"default"}, "switch": {"default", "client"}}[action]
    assert set(payload["profiles"]) == expected
    assert payload["current_profile"] == ("client" if action == "switch" else "default")
    assert payload["profiles"]["default"]["sentinel"] == "default value"


@pytest.mark.parametrize("directory", [True, False])
@pytest.mark.parametrize("move", [True, False])
def test_external_target_appearing_at_transfer_is_preserved(tmp_path, monkeypatch, directory, move):
    source = tmp_path / "source" / "photo"
    source.parent.mkdir()
    if directory:
        source.mkdir()
        (source / "image").write_text("mine")
    else:
        source.write_text("mine")
    dest = tmp_path / "dest"
    dest.mkdir()
    real_transfer = file_transfer._transfer_one

    def race(src, target, *, move):
        if directory:
            target.mkdir()
            (target / "external").write_text("theirs")
        else:
            target.write_text("theirs")
        real_transfer(src, target, move=move)

    monkeypatch.setattr(file_transfer, "_transfer_one", race)
    result = file_transfer.transfer_into([str(source)], dest, move=move)
    assert result.done == [] and result.failed == [str(source)]
    assert source.exists()
    if directory:
        assert sorted(p.name for p in (dest / source.name).iterdir()) == ["external"]
    else:
        assert (dest / source.name).read_text() == "theirs"


@pytest.mark.parametrize("name", ["photo 1.png", "照片.png", "photo#1.png", "photo%20.png"])
def test_webdav_filename_is_a_single_encoded_path_segment(tmp_path, name):
    from urllib.parse import unquote, urlsplit
    source = tmp_path / name
    source.write_bytes(b"image")
    request = uploaders.build_webdav_request("https://example.test/photos/?token=abc", str(source))
    parts = urlsplit(request.full_url)
    assert unquote(parts.path) == "/photos/" + name
    assert parts.query == "token=abc" and parts.fragment == ""
    assert " " not in request.selector and request.selector.isascii()

@pytest.mark.parametrize("move", [True, False])
def test_transfer_without_hardlink_support_keeps_existing_and_copies(tmp_path, monkeypatch, move):
    import errno
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"original")
    dest = tmp_path / "dest"
    dest.mkdir()

    def unsupported(*_args, **_kwargs):
        raise OSError(errno.ENOTSUP, "filesystem has no hard links")

    monkeypatch.setattr(file_transfer.os, "rename", unsupported_rename)
    monkeypatch.setattr(file_transfer.os, "link", unsupported)
    result = file_transfer.transfer_into([str(source)], dest, move=move)
    assert result.failed == []
    assert (dest / source.name).read_bytes() == b"original"
    assert source.exists() is (not move)


def test_transfer_link_fallback_loses_race_without_truncating_target(tmp_path, monkeypatch):
    import errno
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"original")
    dest = tmp_path / "dest"
    dest.mkdir()

    def unsupported_with_new_target(_staged, target):
        target.write_bytes(b"other writer")
        raise OSError(errno.ENOTSUP, "filesystem has no hard links")

    monkeypatch.setattr(file_transfer.os, "rename", unsupported_rename)
    monkeypatch.setattr(file_transfer.os, "link", unsupported_with_new_target)
    result = file_transfer.transfer_into([str(source)], dest, move=True)
    assert result.failed == [str(source)]
    assert source.read_bytes() == b"original"
    assert (dest / source.name).read_bytes() == b"other writer"


def test_failed_directory_copy_retains_all_sources(tmp_path, monkeypatch):
    source = tmp_path / "shoot"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"a")
    (source / "b.jpg").write_bytes(b"b")
    dest = tmp_path / "dest"
    dest.mkdir()
    real_copy = file_transfer.shutil.copyfile

    def failure(src, dst, **kwargs):
        if Path(src).name == "b.jpg":
            raise OSError("disk full")
        return real_copy(src, dst, **kwargs)

    monkeypatch.setattr(file_transfer.os, "rename", unsupported_rename)
    monkeypatch.setattr(file_transfer.shutil, "copyfile", failure)
    result = file_transfer.transfer_into([str(source)], dest, move=True)
    assert result.failed == [str(source)]
    assert (source / "a.jpg").read_bytes() == b"a"
    assert (source / "b.jpg").read_bytes() == b"b"


def test_sidecar_publication_cannot_overwrite_an_external_writer(tmp_path, monkeypatch):
    source = tmp_path / "photo.xmp"
    source.write_bytes(b"my edits")
    target = tmp_path / "new.xmp"
    real_link = file_transfer.os.link

    def race(staged, destination):
        destination.write_bytes(b"other edits")
        real_link(staged, destination)

    monkeypatch.setattr(file_transfer.os, "rename", unsupported_rename)
    monkeypatch.setattr(file_transfer.os, "link", race)
    with pytest.raises(FileExistsError):
        file_transfer._carry_sidecar(source, target, move=True)
    assert source.read_bytes() == b"my edits"
    assert target.read_bytes() == b"other edits"


@pytest.mark.parametrize("operation", ["create", "rename", "delete", "switch"])
def test_profile_write_failure_keeps_memory_and_disk_agreeing(tmp_path, monkeypatch, operation):
    settings.cancel_pending_save()
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_user_settings_path", lambda: path)
    settings._profile_state.update(current="default", available=["default"])
    settings.user_setting_dict.clear()
    settings.user_setting_dict["sentinel"] = "current"
    settings.write_user_setting()
    settings.create_profile("client")
    before = path.read_bytes()
    real_save = settings._save_settings
    calls = 0

    def fail_transition(target, payload):
        nonlocal calls
        calls += 1
        return real_save(target, payload) if calls == 1 else False

    monkeypatch.setattr(settings, "_save_settings", fail_transition)
    operations = {
        "create": lambda: settings.create_profile("new"),
        "rename": lambda: settings.rename_profile("default", "renamed"),
        "delete": lambda: settings.delete_profile("client"),
        "switch": lambda: settings.switch_profile("client"),
    }
    assert operations[operation]() is False
    assert path.read_bytes() == before
    assert settings.current_profile() == "default"
    assert settings.list_profiles() == ["default", "client"]
    assert settings.user_setting_dict == {"sentinel": "current"}


def test_pip_stdout_failure_reaps_child(qapp, monkeypatch):
    real_popen = subprocess.Popen
    children = []
    worker = pip_installer._InstallWorker([], sys.executable)

    class BrokenOutput:
        def __iter__(self):
            raise OSError("stdout unavailable")

        def close(self):
            pass

    def launch(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        children.append(proc)
        proc.stdout.close()
        proc.stdout = BrokenOutput()
        return proc

    monkeypatch.setattr(pip_install_workers.subprocess, "Popen", launch)
    try:
        with pytest.raises(OSError, match="stdout unavailable"):
            worker._run_with_live_output([sys.executable, "-c", "import time; time.sleep(30)"])
        assert children[0].poll() is not None
        assert worker._proc is None
    finally:
        for child in children:
            terminate_process(child)
        worker.deleteLater()


def unsupported_rename(*_args, **_kwargs):
    import errno
    raise OSError(errno.EXDEV, "different volume")

@pytest.mark.parametrize("cross_volume", [False, True])
def test_two_process_moves_preserve_both_photos(tmp_path, cross_volume):
    import os
    from time import monotonic, sleep
    script = '''
import errno, sys, time
from pathlib import Path
from Imervue.system import file_transfer as f
source,target,ready,go,cross = map(Path,sys.argv[1:])
ready.write_text('ready')
while not go.exists(): time.sleep(0.01)
if str(cross)=='yes':
    def different_volume(*args,**kwargs): raise OSError(errno.EXDEV,'different volume')
    f.os.rename=different_volume
try:
    f._transfer_one(str(source),target,move=True)
except FileExistsError:
    sys.exit(17)
'''
    sources = [tmp_path / "a.jpg", tmp_path / "b.jpg"]
    sources[0].write_bytes(b"A")
    sources[1].write_bytes(b"B")
    target = tmp_path / "output.jpg"
    go = tmp_path / "go"
    ready = [tmp_path / "ready-a", tmp_path / "ready-b"]
    processes = []
    try:
        for source, flag in zip(sources, ready, strict=True):
            processes.append(subprocess.Popen(
                [sys.executable, "-c", script, str(source), str(target), str(flag), str(go),
                 "yes" if cross_volume else "no"],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ))
        until = monotonic() + 5
        while not all(path.exists() for path in ready) and monotonic() < until:
            sleep(0.01)
        assert all(path.exists() for path in ready)
        go.write_text("go")
        assert sorted(proc.wait(timeout=5) for proc in processes) == [0, 17]
        survivors = [path for path in sources if path.exists()]
        assert len(survivors) == 1
        assert {survivors[0].read_bytes(), target.read_bytes()} == {b"A", b"B"}
    finally:
        for process in processes:
            terminate_process(process)


@pytest.mark.parametrize("move", [False, True])
def test_read_only_photo_transfer_preserves_content_and_mode(tmp_path, move):
    import stat
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"photo")
    source.chmod(stat.S_IREAD)
    dest = tmp_path / "dest"
    dest.mkdir()
    target = dest / source.name
    try:
        result = file_transfer.transfer_into([str(source)], dest, move=move)
        assert result.failed == []
        assert target.read_bytes() == b"photo"
        assert not target.stat().st_mode & stat.S_IWRITE
        assert source.exists() is (not move)
    finally:
        for path in (source, target):
            if path.exists():
                path.chmod(stat.S_IWRITE | stat.S_IREAD)
