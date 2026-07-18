"""WebcamTracker parameter-pump + start/stop thread-lifetime tests.

Driven with a fake canvas and fake threads — no PuppetCanvas (QOpenGLWidget) is
constructed, so unlike the smoke tests these run on headless CI.
"""
from __future__ import annotations

from Imervue.puppet.webcam_tracker import WebcamTracker


class _FakeCanvas:
    def __init__(self, has_doc: bool = True):
        self._doc = object() if has_doc else None
        self.batch_calls: list[dict] = []
        self.single_calls: list = []

    def document(self):
        return self._doc

    def set_parameter_values(self, values):
        self.batch_calls.append(dict(values))

    def set_parameter_value(self, param_id, value):
        self.single_calls.append((param_id, value))


class _FakeThread:
    def __init__(self, alive: bool):
        self._alive = alive
        self.joined = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout=None):
        # Simulate a join that returns without the thread actually stopping
        # (a stuck cap.read on a disconnected camera).
        self.joined = True


class TestPump:
    def test_pushes_all_params_in_one_batch(self, qapp):
        canvas = _FakeCanvas()
        tracker = WebcamTracker(canvas)
        try:
            tracker._enabled = True                          # noqa: SLF001
            tracker._latest_params = {                        # noqa: SLF001
                "ParamA": 0.5, "ParamB": -0.2, "ParamC": 1.0}
            tracker._pump_to_canvas()                        # noqa: SLF001
            assert canvas.batch_calls == [
                {"ParamA": 0.5, "ParamB": -0.2, "ParamC": 1.0}]
            assert canvas.single_calls == []                 # not one-at-a-time
        finally:
            tracker.deleteLater()

    def test_noop_when_disabled(self, qapp):
        canvas = _FakeCanvas()
        tracker = WebcamTracker(canvas)
        try:
            tracker._enabled = False                         # noqa: SLF001
            tracker._latest_params = {"P": 1.0}              # noqa: SLF001
            tracker._pump_to_canvas()                        # noqa: SLF001
            assert canvas.batch_calls == []
        finally:
            tracker.deleteLater()

    def test_noop_when_no_document(self, qapp):
        canvas = _FakeCanvas(has_doc=False)
        tracker = WebcamTracker(canvas)
        try:
            tracker._enabled = True                          # noqa: SLF001
            tracker._latest_params = {"P": 1.0}              # noqa: SLF001
            tracker._pump_to_canvas()                        # noqa: SLF001
            assert canvas.batch_calls == []
        finally:
            tracker.deleteLater()

    def test_noop_when_no_params(self, qapp):
        canvas = _FakeCanvas()
        tracker = WebcamTracker(canvas)
        try:
            tracker._enabled = True                          # noqa: SLF001
            tracker._latest_params = {}                      # noqa: SLF001
            tracker._pump_to_canvas()                        # noqa: SLF001
            assert canvas.batch_calls == []
        finally:
            tracker.deleteLater()


class TestThreadLifetime:
    def test_stop_retains_reference_when_join_times_out(self, qapp):
        tracker = WebcamTracker(_FakeCanvas())
        try:
            zombie = _FakeThread(alive=True)     # still alive after join
            tracker._thread = zombie                         # noqa: SLF001
            tracker._stop()                                  # noqa: SLF001
            assert zombie.joined is True
            assert tracker._thread is zombie                 # noqa: SLF001
            assert tracker._stop_evt.is_set()                # noqa: SLF001
        finally:
            tracker._thread = None                           # noqa: SLF001
            tracker.deleteLater()

    def test_stop_drops_reference_when_thread_exited(self, qapp):
        tracker = WebcamTracker(_FakeCanvas())
        try:
            tracker._thread = _FakeThread(alive=False)       # noqa: SLF001
            tracker._stop()                                  # noqa: SLF001
            assert tracker._thread is None                   # noqa: SLF001
        finally:
            tracker.deleteLater()

    def test_start_refuses_while_previous_thread_alive(self, qapp):
        tracker = WebcamTracker(_FakeCanvas())
        try:
            tracker._stop_evt.set()                          # noqa: SLF001
            tracker._thread = _FakeThread(alive=True)        # noqa: SLF001
            assert tracker._start() is False                 # noqa: SLF001
            assert tracker._stop_evt.is_set()                # noqa: SLF001 - not cleared
        finally:
            tracker._thread = None                           # noqa: SLF001
            tracker.deleteLater()
