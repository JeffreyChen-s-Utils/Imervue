"""Failure-path regressions from the full-program review."""
import io
import json
from threading import Event, Timer
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit
from html.parser import HTMLParser

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QWidget

from Imervue.paint.animation import Animation, AnimationFrame
from Imervue.paint.animation_export import export_apng, export_gif, export_webp
from Imervue.paint.document import PaintDocument
from Imervue.paint.document_files import DocumentFiles
from Imervue.paint import document_io, paint_project_export
from Imervue.paint.paint_project import PaintProject, ProjectPage
from Imervue.export.web_gallery import generate_web_gallery
from Imervue.gui.auto_tag_dialog import AutoTagDialog
from Imervue.library import auto_tag


def _document():
    doc = PaintDocument()
    doc.load_image(np.full((3, 4, 4), 255, dtype=np.uint8))
    return doc


@pytest.mark.parametrize(('writer', 'fmt', 'suffix'), [
    (export_gif, 'GIF', '.gif'), (export_webp, 'WEBP', '.webp'),
    (export_apng, 'PNG', '.png'),
])
def test_animation_failure_preserves_previous_output(tmp_path, monkeypatch, writer, fmt, suffix):
    target = tmp_path / ('saved' + suffix)
    target.write_bytes(b'previous successful export')
    animation = Animation(frames=[AnimationFrame(_document())])
    Image.init()

    def fail(_image, stream, _name):
        stream.write(b'partial')
        raise OSError('encoder failed')

    monkeypatch.setitem(Image.SAVE_ALL, fmt, fail)
    with pytest.raises(OSError, match='encoder failed'):
        writer(animation, target)
    assert target.read_bytes() == b'previous successful export'
    assert list(tmp_path.iterdir()) == [target]


def test_cbz_composite_failure_preserves_previous_output(tmp_path, monkeypatch):
    target = tmp_path / 'saved.cbz'
    target.write_bytes(b'previous successful export')
    project = PaintProject(pages=[ProjectPage(document=_document())])

    def fail(_page):
        raise MemoryError('composite failed')

    monkeypatch.setattr(paint_project_export, '_composite_or_default', fail)
    with pytest.raises(MemoryError, match='composite failed'):
        paint_project_export.export_project_cbz(project, target)
    assert target.read_bytes() == b'previous successful export'
    assert list(tmp_path.iterdir()) == [target]


def test_pdf_encoder_failure_preserves_previous_output(tmp_path, monkeypatch):
    target = tmp_path / 'saved.pdf'
    target.write_bytes(b'previous successful export')
    project = PaintProject(pages=[ProjectPage(document=_document())])
    Image.init()

    def fail(_image, stream, _name):
        stream.write(b'partial')
        raise OSError('encoder failed')

    monkeypatch.setitem(Image.SAVE, 'PDF', fail)
    with pytest.raises(OSError, match='encoder failed'):
        paint_project_export.export_project_pdf(project, target)
    assert target.read_bytes() == b'previous successful export'
    assert list(tmp_path.iterdir()) == [target]


class _ImageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, _tag, attrs):
        self.links.extend(value for key, value in attrs if key in ('src', 'data-full'))


@pytest.mark.parametrize('name', ['a#b.png', '100%20real.png', '中文 空白.png'])
def test_gallery_urls_resolve_to_written_files(tmp_path, name):
    source = tmp_path / name
    Image.new('RGB', (8, 8)).save(source)
    output = generate_web_gallery([str(source)], tmp_path / 'gallery')
    parsed = _ImageLinks()
    parsed.feed(output.read_text(encoding='utf-8'))
    assert len(parsed.links) == 2
    for link in parsed.links:
        url = urlsplit(link)
        assert not url.fragment and not url.query
        assert (output.parent / unquote(url.path)).is_file()


@pytest.mark.parametrize('changes', [
    {'width': None}, {'height': []}, {'width': 'not a number'}, {'active_layer': []},
    {'layers': [{'opacity': {}}]}, {'width': -1},
])
def test_malformed_paint_metadata_is_value_error(changes, tmp_path):
    metadata = {'format_version': 1, 'width': 4, 'height': 3, 'layers': [{}]}
    metadata.update(changes)
    data = io.BytesIO()
    np.savez(data, _metadata=json.dumps(metadata), layer_0_image=np.zeros((3, 4, 4), dtype=np.uint8))
    target = tmp_path / 'broken.imervue'
    target.write_bytes(data.getvalue())
    with pytest.raises(ValueError):
        document_io.load_document(target)
    with pytest.raises(ValueError):
        document_io.load_document_from_buffer(data.getvalue())


def test_missing_dimension_uses_open_failure_notice(qapp, tmp_path):
    target = tmp_path / 'broken.imervue'
    with target.open('wb') as stream:
        np.savez(stream, _metadata=json.dumps({'format_version': 1, 'height': 1, 'layers': [{}]}))
    warnings = []
    host = QWidget()
    files = DocumentFiles(SimpleNamespace(_workspace=host, _warn=lambda _key, error: warnings.append(error)))
    try:
        assert not files.open(str(target))
        assert warnings
    finally:
        host.deleteLater()


@pytest.mark.parametrize('close_method', ['reject', 'close', 'escape', 'button'])
def test_auto_tag_close_keeps_events_running_and_stops_batch(qapp, monkeypatch, close_method):
    started, release, fallback = Event(), Event(), Event()
    tagged = []

    def tag(path):
        tagged.append(path)
        started.set()
        assert release.wait(3)
        return ['auto/test']

    monkeypatch.setattr(auto_tag, 'auto_tag_image', tag)
    ui = QWidget()
    ui.viewer = SimpleNamespace(selected_tiles=set(), model=SimpleNamespace(images=['a', 'b', 'c']))
    dialog = AutoTagDialog(ui)
    dialog._run()
    assert started.wait(2)
    thread = getattr(dialog, '_thread', None) or dialog._worker

    def emergency_release():
        fallback.set()
        release.set()

    watchdog = Timer(1, emergency_release)
    watchdog.start()
    pulse = []
    QTimer.singleShot(0, lambda: (pulse.append(True), release.set()))
    try:
        if close_method == 'escape':
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        elif close_method == 'button':
            buttons = dialog.findChildren(QPushButton)
            close_button = next(button for button in buttons if button is not dialog._run_btn)
            close_button.click()
        else:
            getattr(dialog, close_method)()
        qapp.processEvents()
        assert pulse and not fallback.is_set(), 'closing waited for the worker on the GUI thread'
        assert thread.wait(2000)
        qapp.processEvents()
        assert tagged == ['a']
    finally:
        release.set()
        watchdog.cancel()
        thread.wait(3000)
        qapp.processEvents()
        dialog.deleteLater()
        ui.deleteLater()

@pytest.mark.parametrize('failure', [False, True])
def test_auto_tag_completion_releases_worker_and_allows_rerun(qapp, monkeypatch, failure):
    from PySide6.QtCore import QEventLoop

    def tag(_path):
        if failure:
            raise OSError('database unavailable')
        return ['auto/test']

    monkeypatch.setattr(auto_tag, 'auto_tag_image', tag)
    ui = QWidget()
    ui.viewer = SimpleNamespace(selected_tiles=set(), model=SimpleNamespace(images=['a']))
    dialog = AutoTagDialog(ui)
    try:
        for _ in range(2):
            loop = QEventLoop()
            poll = QTimer()
            poll.setInterval(1)
            poll.timeout.connect(lambda loop=loop: loop.quit() if dialog._worker is None
                                 and not getattr(dialog, '_worker_retiring', False) else None)
            timeout = QTimer()
            timeout.setSingleShot(True)
            timeout.timeout.connect(loop.quit)
            dialog._run()
            poll.start()
            timeout.start(2000)
            loop.exec()
            poll.stop()
            timeout.stop()
            assert dialog._worker is None
            assert not getattr(dialog, '_worker_retiring', False)
            assert dialog.isEnabled() and dialog._run_btn.isEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()
        ui.deleteLater()
