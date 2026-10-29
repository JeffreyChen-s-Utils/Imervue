"""Behavioral regressions for full-review Puppet findings."""
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtGui import QImage

from Imervue.puppet.batch_export import BatchMotionExporter
from Imervue.puppet.vts_api import VTubeStudioHandler, VTubeStudioServer


class Canvas:
    def __init__(self, names=()):
        self.doc = SimpleNamespace(size=(16, 16), motions=[
            SimpleNamespace(name=name, duration=0.1) for name in names])
        self.color = 'red'

    def document(self):
        return self.doc

    def render_offscreen_puppet(self, width, height, **kwargs):
        image = QImage(width, height, QImage.Format.Format_RGB888)
        image.fill(self.color)
        return image


class Player:
    def __init__(self, canvas):
        self.canvas = canvas
        self.names = []

    def set_motion(self, motion):
        self.names.append(motion.name)
        self.canvas.color = 'red' if len(self.names) == 1 else 'blue'

    def seek(self, _time):
        pass

    def play(self):
        pass

    def pause(self):
        pass


@pytest.mark.parametrize('names', [['idle/01', 'idle:01', '中文', '另一段'], ['Idle', 'idle']])
def test_colliding_batch_names_keep_every_clip_and_existing_file(qapp, tmp_path, monkeypatch, names):
    from Imervue.puppet import batch_export
    monkeypatch.setattr(batch_export.os.path, 'normcase', lambda path: path)
    canvas = Canvas(names)
    player = Player(canvas)
    existing = tmp_path / 'idle_01.gif'
    existing.write_bytes(b'previous export')
    exporter = BatchMotionExporter(canvas, player)
    completed = []
    exporter.finished.connect(completed.append)
    try:
        assert exporter.start(tmp_path, extension='.gif')
        while exporter.is_running():
            exporter._recorder._on_tick()
            exporter._recorder.stop()
        assert len(completed) == 1
        paths = completed[0]
        assert len({path.casefold() for path in paths}) == len(names)
        assert existing.read_bytes() == b'previous export'
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                assert image.size == (16, 16)
                assert image.convert('RGB').getpixel((0, 0)) == (
                    (255, 0, 0) if index == 0 else (0, 0, 255))
    finally:
        exporter.stop()
        exporter.deleteLater()


@pytest.mark.parametrize('failure', ['close', 'append'])
def test_record_failure_never_emits_success_or_advances_batch(qapp, tmp_path, monkeypatch, failure):
    import imageio

    class Writer:
        def append_data(self, _frame):
            if failure == 'append':
                raise OSError('encoder append failed')

        def close(self):
            if failure == 'close':
                raise OSError('encoder close failed')

    monkeypatch.setattr(imageio, 'get_writer', lambda *args, **kwargs: Writer())
    canvas = Canvas(['first', 'second'])
    player = Player(canvas)
    exporter = BatchMotionExporter(canvas, player)
    completed, failed, recorded = [], [], []
    exporter.finished.connect(completed.append)
    exporter.failed.connect(failed.append)
    exporter._recorder.finished.connect(recorded.append)
    try:
        assert exporter.start(tmp_path, extension='.gif')
        if failure == 'append':
            exporter._recorder._on_tick()
        else:
            assert exporter._recorder.stop() is None
        assert not exporter.is_running()
        assert not exporter._recorder.is_recording()
        assert completed == recorded == []
        assert len(failed) == 1 and failure in failed[0]
        assert player.names == ['first']
        assert exporter._recorder.stop() is None
    finally:
        exporter.stop()
        exporter.deleteLater()


@pytest.mark.parametrize('message', [
    {'messageType': []}, {'messageType': {}},
    {'messageType': 'AuthenticationTokenRequest', 'data': ['bad']},
    {'messageType': 'AuthenticationTokenRequest', 'data': 42},
    {'messageType': 'AuthenticationTokenRequest', 'data': ''},
])
def test_vts_invalid_shapes_return_error_through_callback(qapp, message):
    import json
    sent = []
    handler = VTubeStudioHandler(Canvas())
    class Socket:
        def sendTextMessage(self, value):
            sent.append(value)
    socket = Socket()
    server = SimpleNamespace(_sessions={socket: handler})
    VTubeStudioServer._on_text(server, socket, json.dumps(message))
    response = json.loads(sent[0])
    assert response['messageType'] == 'APIError'
    assert 'InvalidRequest' in response['data']['message']
    assert not handler.is_authenticated()


def test_workspace_shutdown_covers_services_recorders_and_player():
    from Imervue.puppet.workspace import PuppetWorkspace
    calls = []
    def owned(name):
        return SimpleNamespace(shutdown=lambda: calls.append(name), stop=lambda: calls.append(name))
    names = ['_webcam', '_input_engine', '_virtual_camera', '_ndi_output',
             '_vts_server', '_idle_driver', '_idle_motion_cycler', '_batch_exporter',
             '_recorder', '_motion_recorder']
    ws = SimpleNamespace(**{name: owned(name) for name in names})
    ws._motion_dock = SimpleNamespace(player=lambda: owned('player'))
    ws._shutdown_drivers = lambda: PuppetWorkspace._shutdown_drivers(ws)
    PuppetWorkspace.shutdown(ws)
    PuppetWorkspace.shutdown(ws)
    assert sorted(calls) == sorted([*names, 'player'])


def test_main_release_closes_both_owned_workspaces_even_after_one_fails(monkeypatch):
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.images import image_loader
    calls = []
    def broken():
        calls.append('puppet')
        raise RuntimeError('already gone')
    main = SimpleNamespace(
        puppet_workspace=SimpleNamespace(shutdown=broken),
        pet_workspace=SimpleNamespace(shutdown=lambda: calls.append('pet')),
    )
    monkeypatch.setattr(image_loader, 'cancel_folder_scan', lambda _viewer: None)
    ImervueMainWindow._release_for_close(main)
    assert calls == ['puppet', 'pet']


def test_webcam_shutdown_detaches_gui_without_waiting_for_blocked_capture(qapp):
    from threading import Event, Thread
    from PySide6.QtCore import QTimer
    from Imervue.puppet.webcam_tracker import WebcamTracker
    release = Event()
    tracker = WebcamTracker(Canvas())
    worker = Thread(target=release.wait, daemon=True)
    tracker._thread = worker
    tracker._enabled = True
    tracker._pump_timer.start()
    worker.start()
    fired = []
    try:
        tracker.shutdown()
        assert tracker._thread is worker and worker.is_alive()
        assert tracker._stop_evt.is_set()
        assert not tracker.is_enabled() and not tracker._pump_timer.isActive()
        QTimer.singleShot(0, lambda: fired.append(True))
        qapp.processEvents()
        assert fired == [True]
        assert worker.is_alive()
    finally:
        release.set()
        worker.join(2)
        tracker.deleteLater()


def test_pet_workspace_shutdown_releases_overlay_once_without_creating_one():
    from Imervue.desktop_pet.pet_workspace import PetWorkspace
    calls = []
    pet = SimpleNamespace(shutdown=lambda: calls.append('shutdown'),
                          close=lambda: calls.append('close'),
                          deleteLater=lambda: calls.append('delete'))
    workspace = SimpleNamespace(_pet_window=pet, _tray=None)
    PetWorkspace.shutdown(workspace)
    PetWorkspace.shutdown(workspace)
    assert calls == ['shutdown', 'close', 'delete']
    assert workspace._pet_window is None


def test_pet_canvas_shutdown_stops_always_present_input_and_player():
    from Imervue.desktop_pet.pet_canvas_drivers import PetCanvasDrivers
    calls = []
    drivers = SimpleNamespace(
        webcam_tracker=None, virtual_camera=None, idle_driver=None,
        idle_cycler=None, mouse_gaze=None,
        input_engine=SimpleNamespace(shutdown=lambda: calls.append('input')),
        motion_player=SimpleNamespace(stop=lambda: calls.append('player')))
    PetCanvasDrivers.shutdown(drivers)
    assert calls == ['input', 'player']


def test_mic_shutdown_discards_late_callbacks_before_touching_canvas(qapp):
    import numpy as np
    from Imervue.puppet.input_engine import InputEngine
    canvas = Canvas()
    canvas.cursor_moved = SimpleNamespace(connect=lambda _slot: None)
    engine = InputEngine(canvas)
    engine._lipsync_enabled = True
    try:
        engine.shutdown()
        def deleted():
            raise AssertionError('late callback touched deleted canvas')
        canvas.document = deleted
        engine._on_audio_block(np.zeros((16, 1)), 16, None, None)
        engine._apply_viseme({'mouth': 1.0})
    finally:
        engine.deleteLater()


@pytest.mark.parametrize('data', [{'parameterValues': 42}, {'parameterValues': {}}])
def test_authenticated_vts_rejects_non_array_injection(data):
    handler = VTubeStudioHandler(Canvas())
    handler._authenticated = True
    reply = handler.handle_message({'messageType': 'InjectParameterDataRequest', 'data': data})
    assert reply['messageType'] == 'APIError'


def test_vts_invalid_request_does_not_break_authenticated_session():
    handler = VTubeStudioHandler(Canvas())
    token = handler.handle_message({'messageType': 'AuthenticationTokenRequest'})
    auth = handler.handle_message({'messageType': 'AuthenticationRequest', 'data': token['data']})
    assert auth['data']['authenticated']
    invalid = handler.handle_message({'messageType': [], 'data': {}})
    assert invalid['messageType'] == 'APIError'
    state = handler.handle_message({'messageType': 'APIStateRequest', 'requestID': 'next'})
    assert state['requestID'] == 'next'
    assert state['data']['currentSessionAuthenticated']


def test_pet_window_shutdown_stops_overlay_timers_and_audio_once():
    from Imervue.desktop_pet.pet_window import PetWindow
    calls = []
    def stop(name):
        return lambda: calls.append(name)
    window = SimpleNamespace(
        _tick=SimpleNamespace(stop=stop('paint')),
        _script_tick=SimpleNamespace(stop=stop('script')),
        _fullscreen_detector=SimpleNamespace(stop=stop('fullscreen')),
        _click_sfx_ctl=SimpleNamespace(shutdown=stop('click audio')),
        _idle_minigame=SimpleNamespace(shutdown=stop('minigame')),
        _speech=SimpleNamespace(close_bubble=stop('speech')),
        _features={}, _music_rhythm=SimpleNamespace(shutdown=stop('music')),
        _canvas_drivers=SimpleNamespace(shutdown=stop('canvas')),
        _llm=SimpleNamespace(shutdown=stop('llm')))
    PetWindow.shutdown(window)
    PetWindow.shutdown(window)
    assert calls == ['paint', 'script', 'fullscreen', 'click audio', 'minigame',
                     'speech', 'music', 'canvas', 'llm']
