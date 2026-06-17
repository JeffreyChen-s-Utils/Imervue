"""Tests for audio-file lip-sync (pure numpy + stdlib wave, no Qt/GL)."""
from __future__ import annotations

import wave

import numpy as np
import pytest

from Imervue.puppet.audio_lipsync import (
    load_wav_mono,
    mouth_open_curve,
    mouth_open_curve_from_wav,
    normalize_envelope,
    rms_envelope,
    samples_per_frame,
)


def _write_wav(path, data, rate, *, channels=1, width=2):
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        writer.writeframes(np.asarray(data, dtype=dtype).tobytes())


class TestSamplesPerFrame:
    def test_typical_rate(self):
        assert samples_per_frame(48000, 30) == 1600

    def test_non_positive_inputs_floor_at_one(self):
        assert samples_per_frame(0, 30) == 1
        assert samples_per_frame(48000, 0) == 1


class TestRmsEnvelope:
    def test_empty_samples(self):
        assert rms_envelope(np.zeros(0), 1000, 10).size == 0

    def test_constant_amplitude(self):
        env = rms_envelope(np.full(4, 0.5), sample_rate=10, fps=5)  # window 2
        assert env.shape == (2,)
        assert env == pytest.approx([0.5, 0.5])

    def test_silence_is_zero(self):
        assert np.allclose(rms_envelope(np.zeros(100), 1000, 10), 0.0)


class TestNormalizeEnvelope:
    def test_scales_to_peak(self):
        assert normalize_envelope(np.array([0.25, 0.5]), gate=0.0) == pytest.approx([0.5, 1.0])

    def test_gate_zeroes_near_silence(self):
        out = normalize_envelope(np.array([0.01, 1.0]), gate=0.04)
        assert out[0] == pytest.approx(0.0)
        assert out[1] == pytest.approx(1.0)

    def test_all_silence_returns_zeros(self):
        assert np.allclose(normalize_envelope(np.zeros(5)), 0.0)

    def test_empty(self):
        assert normalize_envelope(np.zeros(0)).size == 0


class TestMouthOpenCurve:
    def test_loud_frame_opens_silent_frame_closes(self):
        samples = np.concatenate([np.full(10, 0.8), np.zeros(10)])
        curve = mouth_open_curve(samples, sample_rate=10, fps=10, gate=0.04)
        assert curve[0] == pytest.approx(1.0)
        assert curve[-1] == pytest.approx(0.0)


class TestWavIo:
    def test_load_wav_mono_round_trip(self, tmp_path):
        path = tmp_path / "c.wav"
        _write_wav(path, np.full(8, 16384), rate=8000)
        data, rate = load_wav_mono(path)
        assert rate == 8000
        assert data.shape == (8,)
        assert data == pytest.approx(16384 / 32768)

    def test_stereo_is_averaged_to_mono(self, tmp_path):
        path = tmp_path / "s.wav"
        # L=10000, R=0 interleaved → mono mean 5000.
        interleaved = np.array([10000, 0] * 4, dtype=np.int16)
        _write_wav(path, interleaved, rate=8000, channels=2)
        data, _ = load_wav_mono(path)
        assert data.shape == (4,)
        assert data == pytest.approx(5000 / 32768)

    def test_unsupported_width_raises(self, tmp_path):
        path = tmp_path / "w24.wav"
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(3)
            writer.setframerate(8000)
            writer.writeframes(b"\x00\x00\x00" * 4)
        with pytest.raises(ValueError, match="unsupported WAV sample width"):
            load_wav_mono(path)

    def test_curve_from_wav_loud_then_silent(self, tmp_path):
        rate = 1000
        data = np.concatenate([
            np.full(rate, 10000, dtype=np.int16),   # 1 s loud
            np.zeros(rate, dtype=np.int16),          # 1 s silent
        ])
        path = tmp_path / "clip.wav"
        _write_wav(path, data, rate)
        curve = mouth_open_curve_from_wav(path, fps=10)  # window 100 → 20 frames
        assert len(curve) == 20
        assert curve[0] == pytest.approx(1.0, abs=1e-6)
        assert curve[-1] == pytest.approx(0.0)
