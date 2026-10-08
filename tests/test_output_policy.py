"""Output reservations prevent cross-window collisions and never commit failed/cancelled stages."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from Imervue.image.output_policy import OutputPolicy, free_output_path, write_output


def test_rename_same_name_sources_and_skip_or_replace_existing(tmp_path):
    first = tmp_path / "one.jpg"
    first.write_bytes(b"original")
    result = write_output(first, first, lambda p: p.write_bytes(b"copy"))
    assert result.status == "succeeded" and result.path.endswith("one_1.jpg")
    assert first.read_bytes() == b"original"
    assert write_output(first, first, lambda _: pytest.fail("skip wrote"),
                        OutputPolicy("skip")).status == "skipped"
    with pytest.raises(ValueError, match="consent"):
        write_output(first, first, lambda p: p.write_bytes(b"bad"), OutputPolicy("replace"))
    replaced = write_output(first, first, lambda p: p.write_bytes(b"new"),
                            OutputPolicy("replace", allow_source=True))
    assert replaced.status == "succeeded" and first.read_bytes() == b"new"


@pytest.mark.parametrize("error", [OSError("disk full"), PermissionError("read only"),
                                 ValueError("encoder"), MemoryError("memory")])
def test_write_failure_preserves_target_and_releases_all_temporary_state(tmp_path, error):
    target = tmp_path / "copy.png"
    target.write_bytes(b"old")

    def fail(path):
        assert path.suffix == ".png"
        path.write_bytes(b"partial")
        raise error

    with pytest.raises(type(error)):
        write_output(tmp_path / "source.png", target, fail, OutputPolicy("replace"))
    assert target.read_bytes() == b"old" and list(tmp_path.iterdir()) == [target]
    assert free_output_path(target).name == "copy_1.png"
    assert write_output(tmp_path / "source.png", target, lambda p: p.write_bytes(b"ok"),
                        OutputPolicy("replace")).status == "succeeded"


@pytest.mark.parametrize("when", ["before", "during"])
def test_cancel_never_installs_late_output_over_existing_file(tmp_path, when):
    target = tmp_path / "copy.png"
    target.write_bytes(b"old")
    cancelled = Event()
    if when == "before":
        cancelled.set()

    def write(path):
        path.write_bytes(b"late")
        cancelled.set()

    result = write_output(tmp_path / "source.png", target, write, OutputPolicy("replace"),
                          cancelled=cancelled.is_set)
    assert result.status == "cancelled" and not result.path
    assert target.read_bytes() == b"old" and list(tmp_path.iterdir()) == [target]


def test_parallel_writers_reserve_distinct_names_and_reject_busy_replace(tmp_path):
    target = tmp_path / "same.png"
    entered, release = Event(), Event()

    def blocked(path):
        entered.set()
        if not release.wait(5):
            raise TimeoutError("writer not released")
        path.write_bytes(b"first")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write_output, tmp_path / "source-a.png", target, blocked)
        try:
            assert entered.wait(5)
            second = write_output(tmp_path / "source-b.png", target,
                                  lambda p: p.write_bytes(b"second"))
            assert second.path.endswith("same_1.png")
            assert write_output(tmp_path / "source-c.png", target, blocked,
                                OutputPolicy("skip")).status == "skipped"
            with pytest.raises(FileExistsError, match="currently"):
                write_output(tmp_path / "source-c.png", target, blocked, OutputPolicy("replace"))
        finally:
            release.set()
        assert future.result().path == str(target)
    assert target.read_bytes() == b"first"
    assert (tmp_path / "same_1.png").read_bytes() == b"second"
    assert len(list(tmp_path.iterdir())) == 2


def test_external_file_appearing_during_encode_is_preserved(tmp_path):
    target = tmp_path / "copy.png"

    def write(path):
        path.write_bytes(b"ours")
        target.write_bytes(b"outside writer")

    with pytest.raises(FileExistsError, match="appeared"):
        write_output(tmp_path / "source.png", target, write)
    assert target.read_bytes() == b"outside writer" and len(list(tmp_path.iterdir())) == 1


def test_missing_parent_empty_writer_invalid_policy_and_long_basename(tmp_path):
    with pytest.raises(ValueError, match="invalid"):
        OutputPolicy("bad")
    target = tmp_path / "nested" / ("x" * 220 + ".png")
    with pytest.raises(ValueError, match="empty"):
        write_output(tmp_path / "source.png", target, lambda _: None)
    assert not target.exists() and not list(target.parent.iterdir())
    assert write_output(tmp_path / "source.png", target,
                        lambda p: p.write_bytes(b"long-name")).status == "succeeded"
