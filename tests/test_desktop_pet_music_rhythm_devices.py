"""Loopback capture-device selection for the music-rhythm driver.

Split out from ``test_desktop_pet_music_rhythm.py`` because that module
builds a ``PuppetCanvas`` and therefore skips wholesale on headless CI.
Nothing here touches GL: the pure selection helpers take plain device
dicts, and the ``_open_stream`` tests drive the driver against a stub
``sounddevice`` module, so the path that used to be the only untested
one in the driver now runs everywhere.

Regression cover: ``_open_stream`` used to build
``sd.WasapiSettings(loopback=True)`` and open an ``InputStream`` on the
default *output* device. No released ``sounddevice`` accepts a
``loopback`` keyword, so the call raised ``TypeError`` into the broad
handler and the feature could never start on any machine. The stub
module here deliberately exposes no ``WasapiSettings`` at all, so a
return to that shape fails these tests instead of silently logging a
warning again.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from Imervue.desktop_pet.music_rhythm import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_SAMPLE_RATE,
    MAX_CAPTURE_CHANNELS,
    MusicRhythmDriver,
    _strip_loopback_marker,
    capture_channel_count,
    capture_sample_rate,
    find_loopback_device,
)

WASAPI = {"name": "Windows WASAPI"}
MME = {"name": "MME"}
HOSTAPIS = [MME, WASAPI]
MME_INDEX = 0
WASAPI_INDEX = 1


def _device(name, *, hostapi=WASAPI_INDEX, inputs=0, rate=48000.0):
    return {
        "name": name,
        "hostapi": hostapi,
        "max_input_channels": inputs,
        "max_output_channels": 0 if inputs else 2,
        "default_samplerate": rate,
    }


# ---------------------------------------------------------------
# _strip_loopback_marker
# ---------------------------------------------------------------


def test_strip_marker_removes_bracketed_tag():
    assert _strip_loopback_marker(
        "Speakers (Realtek(R) Audio) [Loopback]") == "Speakers (Realtek(R) Audio)"


def test_strip_marker_removes_bare_tag():
    assert _strip_loopback_marker("Speakers Loopback") == "Speakers"


def test_strip_marker_is_case_insensitive():
    assert _strip_loopback_marker("Speakers (LOOPBACK)") == "Speakers"


def test_strip_marker_leaves_untagged_name_alone():
    assert _strip_loopback_marker("  Speakers (Realtek) ") == "Speakers (Realtek)"


def test_strip_marker_on_tag_only_name_is_empty():
    """Degenerate name that is nothing but the tag — must not raise."""
    assert _strip_loopback_marker("[Loopback]") == ""


# ---------------------------------------------------------------
# find_loopback_device
# ---------------------------------------------------------------


def test_find_loopback_on_empty_device_list_is_none():
    assert find_loopback_device([], HOSTAPIS) is None


def test_find_loopback_without_any_tagged_device_is_none():
    """A build with no loopback support must report "none" rather than
    hand back the microphone — the pet would sway to room noise and
    look like the feature works."""
    devices = [
        _device("Speakers (Realtek)"),
        _device("Microphone (Razer)", inputs=1),
    ]
    assert find_loopback_device(devices, HOSTAPIS) is None


def test_find_loopback_skips_output_only_tagged_device():
    """The exact shape of the original bug: a render endpoint has zero
    input channels, so an InputStream on it fails outright."""
    devices = [_device("Speakers (Realtek) [Loopback]", inputs=0)]
    assert find_loopback_device(devices, HOSTAPIS) is None


def test_find_loopback_returns_the_only_candidate():
    devices = [
        _device("Microphone (Razer)", inputs=1),
        _device("Speakers (Realtek) [Loopback]", inputs=2),
    ]
    assert find_loopback_device(devices, HOSTAPIS) == 1


def test_find_loopback_prefers_the_default_output_endpoint():
    """Two loopbacks, both WASAPI — follow the one the user is hearing."""
    devices = [
        _device("Speakers (Realtek)"),
        _device("Headphones (Razer)"),
        _device("Speakers (Realtek) [Loopback]", inputs=2),
        _device("Headphones (Razer) [Loopback]", inputs=2),
    ]
    assert find_loopback_device(devices, HOSTAPIS, default_output=1) == 3
    assert find_loopback_device(devices, HOSTAPIS, default_output=0) == 2


def test_find_loopback_default_match_beats_wasapi_tiebreak():
    """A name match on another host API still outranks a non-matching
    WASAPI device — following the right endpoint matters more."""
    devices = [
        _device("Headphones (Razer)"),
        _device("Speakers (Realtek) [Loopback]", inputs=2),
        _device("Headphones (Razer) [Loopback]",
                hostapi=MME_INDEX, inputs=2),
    ]
    assert find_loopback_device(devices, HOSTAPIS, default_output=0) == 2


def test_find_loopback_prefers_wasapi_when_nothing_matches():
    devices = [
        _device("Cable Output [Loopback]", hostapi=MME_INDEX, inputs=2),
        _device("Speakers (Realtek) [Loopback]", inputs=2),
    ]
    assert find_loopback_device(devices, HOSTAPIS) == 1


def test_find_loopback_accepts_non_wasapi_when_it_is_all_there_is():
    devices = [_device("Cable Output [Loopback]", hostapi=MME_INDEX, inputs=2)]
    assert find_loopback_device(devices, HOSTAPIS) == 0


def test_find_loopback_survives_out_of_range_hostapi():
    """PortAudio has handed back stale indices after a device change;
    an unresolvable host API just loses the tiebreak."""
    devices = [_device("Speakers [Loopback]", hostapi=99, inputs=2)]
    assert find_loopback_device(devices, HOSTAPIS) == 0


@pytest.mark.parametrize("default_output", [None, -1, 99, "default", 1.5])
def test_find_loopback_survives_unusable_default_output(default_output):
    """``sd.default.device`` reports -1 / None when nothing is
    configured; the tiebreak must degrade, not raise."""
    devices = [_device("Speakers [Loopback]", inputs=2)]
    assert find_loopback_device(
        devices, HOSTAPIS, default_output=default_output) == 0


def test_find_loopback_survives_garbage_channel_count():
    devices = [
        _device("Speakers [Loopback]", inputs="two"),
        _device("Headphones [Loopback]", inputs=2),
    ]
    assert find_loopback_device(devices, HOSTAPIS) == 1


# ---------------------------------------------------------------
# capture_channel_count / capture_sample_rate
# ---------------------------------------------------------------


@pytest.mark.parametrize(("reported", "expected"), [
    (1, 1),
    (2, 2),
    (8, MAX_CAPTURE_CHANNELS),
    (0, 1),
    (-4, 1),
    (None, 1),
    ("stereo", 1),
])
def test_capture_channel_count_clamps(reported, expected):
    assert capture_channel_count(reported) == expected


@pytest.mark.parametrize(("reported", "expected"), [
    (48000.0, 48000),
    (44100, 44100),
    (192000, 192000),
    (0, DEFAULT_SAMPLE_RATE),
    (-1, DEFAULT_SAMPLE_RATE),
    (None, DEFAULT_SAMPLE_RATE),
    ("48k", DEFAULT_SAMPLE_RATE),
])
def test_capture_sample_rate_falls_back_when_unusable(reported, expected):
    assert capture_sample_rate(reported) == expected


# ---------------------------------------------------------------
# MusicRhythmDriver._open_stream
# ---------------------------------------------------------------


class _FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        pass


def _fake_sounddevice(devices, *, default_device=(0, 0), raises=None):
    """Stub with no ``WasapiSettings`` — see the module docstring."""
    calls = []

    def input_stream(**kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return _FakeStream(**kwargs)

    return SimpleNamespace(
        query_devices=lambda: devices,
        query_hostapis=lambda: HOSTAPIS,
        default=SimpleNamespace(device=default_device),
        InputStream=input_stream,
        calls=calls,
    )


class _StubCanvas:
    """Just enough canvas surface for the enable / disable paths.

    A real ``PuppetCanvas`` is a GL widget, and constructing those is
    what crashes headless CI — the stream-open path never needs one.
    """

    @staticmethod
    def document():
        return None


@pytest.fixture
def driver(qapp):
    obj = MusicRhythmDriver(_StubCanvas())
    yield obj
    obj.deleteLater()


def _force_windows(monkeypatch):
    monkeypatch.setattr(
        "Imervue.desktop_pet.music_rhythm.platform.system", lambda: "Windows")


def test_open_stream_off_windows_reports_failure(driver, monkeypatch):
    monkeypatch.setattr(
        "Imervue.desktop_pet.music_rhythm.platform.system", lambda: "Linux")
    assert driver._open_stream() is False   # noqa: SLF001


def test_open_stream_without_sounddevice_reports_failure(driver, monkeypatch):
    _force_windows(monkeypatch)
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    assert driver._open_stream() is False   # noqa: SLF001


def test_open_stream_opens_the_loopback_endpoint(driver, monkeypatch):
    """Happy path. The stub exposes no ``WasapiSettings``, so the old
    ``loopback=True`` construction would fail this outright."""
    devices = [
        _device("Speakers (Realtek)"),
        _device("Microphone (Razer)", inputs=1, rate=44100.0),
        _device("Speakers (Realtek) [Loopback]", inputs=2, rate=48000.0),
    ]
    fake = _fake_sounddevice(devices, default_device=(1, 0))
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    _force_windows(monkeypatch)

    assert driver._open_stream() is True   # noqa: SLF001
    assert len(fake.calls) == 1
    kwargs = fake.calls[0]
    assert kwargs["device"] == 2
    assert kwargs["samplerate"] == 48000
    assert kwargs["channels"] == 2
    assert kwargs["blocksize"] == DEFAULT_BLOCK_SIZE
    assert "extra_settings" not in kwargs
    assert driver._stream.started is True   # noqa: SLF001


def test_open_stream_clamps_a_surround_endpoint(driver, monkeypatch):
    devices = [_device("Speakers [Loopback]", inputs=8, rate=96000.0)]
    fake = _fake_sounddevice(devices)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    _force_windows(monkeypatch)

    assert driver._open_stream() is True   # noqa: SLF001
    assert fake.calls[0]["channels"] == MAX_CAPTURE_CHANNELS
    assert fake.calls[0]["samplerate"] == 96000


def test_open_stream_without_loopback_device_opens_nothing(driver, monkeypatch):
    """No loopback endpoint → report failure without falling back to the
    microphone that sits right next to it in the device list."""
    devices = [
        _device("Speakers (Realtek)"),
        _device("Microphone (Razer)", inputs=1),
    ]
    fake = _fake_sounddevice(devices)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    _force_windows(monkeypatch)

    assert driver._open_stream() is False   # noqa: SLF001
    assert fake.calls == []
    assert driver._stream is None   # noqa: SLF001


def test_open_stream_survives_a_failing_device_query(driver, monkeypatch):
    def boom():
        raise OSError("PortAudio device enumeration failed")

    fake = _fake_sounddevice([])
    fake.query_devices = boom
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    _force_windows(monkeypatch)

    assert driver._open_stream() is False   # noqa: SLF001
    assert driver._stream is None   # noqa: SLF001


def test_open_stream_clears_the_stream_when_open_fails(driver, monkeypatch):
    """A refused endpoint must leave ``_stream`` None so teardown and a
    later retry don't touch a half-built object."""
    devices = [_device("Speakers [Loopback]", inputs=2)]
    fake = _fake_sounddevice(devices, raises=OSError("device in use"))
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    _force_windows(monkeypatch)

    assert driver._open_stream() is False   # noqa: SLF001
    assert driver._stream is None   # noqa: SLF001


def test_set_enabled_reaches_the_real_open_path(driver, monkeypatch):
    """End-to-end through the public toggle, without the usual
    ``_open_stream`` stub — the wiring itself is what regressed."""
    devices = [_device("Speakers [Loopback]", inputs=2)]
    fake = _fake_sounddevice(devices)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    _force_windows(monkeypatch)

    assert driver.set_enabled(True) is True
    assert driver.is_enabled() is True
    driver.set_enabled(False)
    assert driver.is_enabled() is False
