"""Tests for TimelineModel transient-failure thumbnail retry.

A timeline thumbnail that fails to decode (file mid-move/delete or briefly
locked) must retry instead of caching a permanent dark placeholder. A fake
pool captures re-queues so no real worker runs.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def timeline_model(qapp):
    from Imervue.gui.timeline_view import TimelineModel
    return TimelineModel


def _image():
    # The worker now hands the model a QImage (QPixmap is GUI-thread-only).
    from PySide6.QtGui import QImage
    return QImage(96, 96, QImage.Format.Format_RGBA8888)


def _build(model_cls, path, monkeypatch):
    m = model_cls([path])
    started: list = []
    monkeypatch.setattr(m._pool, "start", started.append)  # noqa: SLF001
    return m, started


class TestTimelineThumbRetry:
    def test_success_caches_and_clears_state(self, timeline_model, tmp_path, monkeypatch):
        p = str(tmp_path / "a.png")
        m, _started = _build(timeline_model, p, monkeypatch)
        m._on_thumb(p, _image(), True)  # noqa: SLF001
        _, entry = m._entry_index(p)  # noqa: SLF001
        assert entry.fetched is True
        assert entry.icon is not None
        assert p not in m._in_flight  # noqa: SLF001
        assert p not in m._retry  # noqa: SLF001

    def test_transient_failure_requeues_without_caching(self, timeline_model, tmp_path, monkeypatch):
        p = str(tmp_path / "a.png")
        m, started = _build(timeline_model, p, monkeypatch)
        m._on_thumb(p, _image(), False)  # noqa: SLF001
        _, entry = m._entry_index(p)  # noqa: SLF001
        assert entry.fetched is False
        assert m._retry[p] == 1  # noqa: SLF001
        assert p in m._in_flight  # noqa: SLF001
        assert len(started) == 1

    def test_failure_caps_then_falls_back_to_placeholder(self, timeline_model, tmp_path, monkeypatch):
        from Imervue.gui.timeline_view import _MAX_THUMB_RETRIES
        p = str(tmp_path / "a.png")
        m, _started = _build(timeline_model, p, monkeypatch)
        for _ in range(_MAX_THUMB_RETRIES):
            m._on_thumb(p, _image(), False)  # noqa: SLF001
        assert m._entry_index(p)[1].fetched is False  # noqa: SLF001
        m._on_thumb(p, _image(), False)  # noqa: SLF001
        _, entry = m._entry_index(p)  # noqa: SLF001
        assert entry.fetched is True
        assert p not in m._retry  # noqa: SLF001

    def test_late_callback_for_removed_path_is_ignored(self, timeline_model, tmp_path, monkeypatch):
        p = str(tmp_path / "a.png")
        m, _started = _build(timeline_model, p, monkeypatch)
        m._on_thumb(str(tmp_path / "gone.png"), _image(), True)  # noqa: SLF001
        assert m._entry_index(p)[1].fetched is False  # noqa: SLF001


# ---------------------------------------------------------------------------
# EXIF date scan moved off the GUI thread (two-phase grouping)
# ---------------------------------------------------------------------------


class TestTwoPhaseGrouping:
    def test_extract_date_fast_uses_mtime_without_opening_file(self, tmp_path, monkeypatch):
        from datetime import datetime

        from PIL import Image as PILImage

        from Imervue.gui import timeline_view as tv

        p = tmp_path / "photo.png"
        PILImage.new("RGB", (4, 4)).save(str(p))
        import os
        stamp = datetime(2021, 6, 15, 12, 0, 0).timestamp()
        os.utime(str(p), (stamp, stamp))

        # Guard that the fast path never opens the image (that is the freeze).
        def _boom(*a, **k):
            raise AssertionError("_extract_date_fast must not open the file")

        monkeypatch.setattr(tv.Image, "open", _boom)
        assert tv._extract_date_fast(str(p)) == datetime.fromtimestamp(stamp)

    def test_group_entries_respects_custom_date_fn(self, tmp_path):
        from datetime import datetime

        from Imervue.gui import timeline_view as tv

        paths = [str(tmp_path / f"{i}.png") for i in range(3)]
        dates = {
            paths[0]: datetime(2020, 1, 1),
            paths[1]: datetime(2021, 5, 1),
            paths[2]: datetime(2021, 5, 20),
        }
        entries = tv._group_entries(paths, "month", lambda p: dates[p])
        # 2021-05 has two images (one separator + two rows), 2020-01 one.
        labels = [e.label for e in entries if e.path is None]
        assert labels == ["2021-05", "2020-01"]   # newest group first

    def test_model_groups_synchronously_on_construction(self, timeline_model, tmp_path, qapp):
        from PIL import Image as PILImage
        paths = []
        for name in ("a.png", "b.png"):
            p = tmp_path / name
            PILImage.new("RGB", (4, 4)).save(str(p))
            paths.append(str(p))
        m = timeline_model(paths)
        # Entries are populated immediately (mtime grouping) — no waiting on the
        # background EXIF refine.
        assert m.rowCount() >= len(paths)

    def test_apply_refined_entries_carries_over_loaded_thumbnails(self, timeline_model, tmp_path, qapp):
        from datetime import datetime

        from PySide6.QtGui import QIcon, QPixmap

        from Imervue.gui import timeline_view as tv

        path = str(tmp_path / "a.png")
        m = timeline_model([path])
        # Simulate a loaded thumbnail on the current (mtime-grouped) entry.
        for entry in m._entries:
            if entry.path == path:
                entry.icon = QIcon(QPixmap(8, 8))
                entry.fetched = True

        refined = [
            tv._TimelineEntry(path=None, label="2021-05", when=datetime(2021, 5, 1)),
            tv._TimelineEntry(path=path, label="a.png", when=datetime(2021, 5, 1)),
        ]
        m._apply_refined_entries(refined)

        applied = next(e for e in m._entries if e.path == path)
        assert applied.fetched is True          # not re-decoded after the regroup
        assert applied.icon is not None


def test_extract_date_falls_back_to_mtime_for_a_corrupt_webp(tmp_path):
    import os
    from datetime import datetime

    from test_read_errors import corrupt_exif_webp

    from Imervue.gui import timeline_view as tv

    p = tmp_path / "bad.webp"
    p.write_bytes(corrupt_exif_webp())
    stamp = datetime(2015, 6, 7, 8, 9, 10).timestamp()
    os.utime(p, (stamp, stamp))
    assert tv._extract_date(str(p)) == datetime.fromtimestamp(stamp)


def test_extract_date_propagates_an_unexpected_reader_error(tmp_path, monkeypatch):
    from Imervue.gui import timeline_view as tv

    def broken(*_args, **_kwargs):
        raise RuntimeError("reader bug")

    monkeypatch.setattr(tv.Image, "open", broken)
    with pytest.raises(RuntimeError, match="reader bug"):
        tv._extract_date(str(tmp_path / "a.png"))


def _run_timeline_thumb(path):
    from Imervue.gui.timeline_view import _TimelineThumbWorker

    worker = _TimelineThumbWorker(path)
    emitted: list = []
    worker.signals.done.connect(lambda *args: emitted.append(args))
    worker.run()   # the QRunnable body, inline
    return emitted


def test_timeline_thumb_missing_file_emits_failure_quietly(qapp, tmp_path, caplog):
    with caplog.at_level("DEBUG", logger="Imervue"):
        (args,) = _run_timeline_thumb(str(tmp_path / "gone.png"))
    assert args[-1] is False
    assert caplog.records == []


def test_timeline_thumb_bug_is_logged_and_still_emits(qapp, tmp_path, monkeypatch, caplog):
    from Imervue.gui import timeline_view

    path = tmp_path / "a.png"
    path.write_bytes(b"x")

    def broken(*_args, **_kwargs):
        raise RuntimeError("decoder bug")

    monkeypatch.setattr(timeline_view.Image, "open", broken)
    with caplog.at_level("DEBUG", logger="Imervue"):
        (args,) = _run_timeline_thumb(str(path))
    assert args[-1] is False
    (record,) = caplog.records
    assert record.exc_info[0] is RuntimeError


def test_extract_date_reads_date_time_original_from_the_exif_sub_ifd(tmp_path):
    from datetime import datetime

    from PIL import Image

    import Imervue.gui.timeline_view as tv
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = "2019:05:06 07:08:09"
    path = tmp_path / "a.jpg"
    Image.new("RGB", (4, 4)).save(path, exif=exif)
    assert tv._extract_date(str(path)) == datetime(2019, 5, 6, 7, 8, 9)


def test_extract_date_of_a_missing_file_is_the_epoch(tmp_path):
    from datetime import datetime

    import Imervue.gui.timeline_view as tv
    assert tv._extract_date(str(tmp_path / "gone.jpg")) == datetime.fromtimestamp(0)
