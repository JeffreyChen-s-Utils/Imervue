"""Tests for the viseme audio → (ParamMouthOpenY, ParamMouthForm)
helper.

Pure-Python — synthesise sine waves at known frequencies and verify
the spectral classifier puts them in the expected half of the
form axis. We don't try to verify exact mouth-form values because
the band-energy ratio is sensitive to FFT bin alignment.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.puppet.input_drivers import (
    DEFAULT_MOUTH_FORM_PARAM,
    DEFAULT_MOUTH_PARAM,
    audio_to_viseme,
)


_SAMPLE_RATE: int = 22050


def _sine_block(freq_hz: float, *, duration_s: float = 0.05,
                amplitude: float = 0.4) -> np.ndarray:
    n = int(_SAMPLE_RATE * duration_s)
    t = np.arange(n, dtype=np.float32) / float(_SAMPLE_RATE)
    return (amplitude * np.sin(2.0 * np.pi * freq_hz * t)).astype(np.float32)


def test_silence_returns_zero_for_both_params():
    out = audio_to_viseme(np.zeros(512, dtype=np.float32), sample_rate=_SAMPLE_RATE)
    assert out[DEFAULT_MOUTH_PARAM] == pytest.approx(0.0)
    assert out[DEFAULT_MOUTH_FORM_PARAM] == pytest.approx(0.0)


def test_empty_array_returns_zeros():
    out = audio_to_viseme(np.empty((0,), dtype=np.float32), sample_rate=_SAMPLE_RATE)
    assert out[DEFAULT_MOUTH_PARAM] == pytest.approx(0.0)
    assert out[DEFAULT_MOUTH_FORM_PARAM] == pytest.approx(0.0)


def test_low_frequency_tone_skews_form_negative():
    """A ~400 Hz sine sits inside the low formant band (round-mouth
    vowels). ParamMouthForm should be clearly negative."""
    block = _sine_block(400.0)
    out = audio_to_viseme(block, sample_rate=_SAMPLE_RATE)
    assert out[DEFAULT_MOUTH_PARAM] > 0.5
    assert out[DEFAULT_MOUTH_FORM_PARAM] < -0.5


def test_high_frequency_tone_skews_form_positive():
    """A ~2500 Hz sine sits inside the high formant band (wide-mouth
    vowels). ParamMouthForm should be clearly positive."""
    block = _sine_block(2500.0)
    out = audio_to_viseme(block, sample_rate=_SAMPLE_RATE)
    assert out[DEFAULT_MOUTH_PARAM] > 0.5
    assert out[DEFAULT_MOUTH_FORM_PARAM] > 0.5


def test_out_of_band_tone_leaves_form_neutral():
    """A frequency far above the high band (e.g. 6 kHz) has no energy
    in either viseme band, so form stays near zero — silence-like
    rather than randomly polarised."""
    block = _sine_block(6000.0)
    out = audio_to_viseme(block, sample_rate=_SAMPLE_RATE)
    assert abs(out[DEFAULT_MOUTH_FORM_PARAM]) <= 0.1


def test_loud_block_saturates_mouth_open():
    block = _sine_block(400.0, amplitude=1.5)
    out = audio_to_viseme(block, sample_rate=_SAMPLE_RATE)
    assert out[DEFAULT_MOUTH_PARAM] == pytest.approx(1.0)


def test_very_quiet_block_does_not_drive_form_either():
    block = _sine_block(400.0, amplitude=0.001)
    out = audio_to_viseme(block, sample_rate=_SAMPLE_RATE)
    assert out[DEFAULT_MOUTH_PARAM] == pytest.approx(0.0)
    assert out[DEFAULT_MOUTH_FORM_PARAM] == pytest.approx(0.0)
