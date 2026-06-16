"""Drive a mouth-open parameter from a pre-recorded audio file.

The live input engine already lip-syncs from the microphone; this computes the
same kind of mouth-open envelope from an audio *file* so a puppet can mime to a
recorded clip. The envelope math is pure numpy and the WAV reader uses only the
standard library, so the whole pipeline is unit-testable without extra deps. A
workspace timer can then step the returned curve into ``ParamMouthOpenY``.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

# RMS below this fraction of the loudest frame reads as silence (mouth closed),
# so room tone / breaths don't keep the mouth flapping.
DEFAULT_GATE = 0.04
_INT_DTYPES = {1: np.uint8, 2: np.int16, 4: np.int32}


def samples_per_frame(sample_rate: int, fps: float) -> int:
    """Audio samples that map to one animation frame (at least 1)."""
    if sample_rate <= 0 or fps <= 0:
        return 1
    return max(1, round(sample_rate / fps))


def rms_envelope(samples: np.ndarray, sample_rate: int, fps: float) -> np.ndarray:
    """Per-frame RMS amplitude of mono *samples* chunked at the frame rate."""
    window = samples_per_frame(sample_rate, fps)
    if samples.size == 0:
        return np.zeros(0, dtype=np.float64)
    frame_count = -(-samples.size // window)  # ceil
    data = samples.astype(np.float64)
    out = np.zeros(frame_count, dtype=np.float64)
    for index in range(frame_count):
        chunk = data[index * window:(index + 1) * window]
        if chunk.size:
            out[index] = float(np.sqrt(np.mean(chunk * chunk)))
    return out


def normalize_envelope(envelope: np.ndarray, *, gate: float = DEFAULT_GATE) -> np.ndarray:
    """Scale an RMS envelope to ``[0, 1]`` by its peak, gating out near-silence."""
    if envelope.size == 0:
        return envelope
    peak = float(envelope.max())
    if peak <= 0.0:
        return np.zeros_like(envelope)
    normalized = envelope / peak
    normalized[normalized < gate] = 0.0
    return np.clip(normalized, 0.0, 1.0)


def mouth_open_curve(
    samples: np.ndarray,
    sample_rate: int,
    fps: float,
    *,
    gate: float = DEFAULT_GATE,
) -> list[float]:
    """Per-frame mouth-open values in ``[0, 1]`` for mono *samples*."""
    return normalize_envelope(
        rms_envelope(samples, sample_rate, fps), gate=gate).tolist()


def load_wav_mono(path: str | Path) -> tuple[np.ndarray, int]:
    """Read a WAV file as mono float64 samples in ``[-1, 1]`` and its rate.

    Stereo (or more) is averaged to mono. Only 8/16/32-bit integer PCM is
    supported (what ``wave`` exposes); anything else raises ``ValueError``.
    """
    with wave.open(str(path), "rb") as reader:
        rate = reader.getframerate()
        channels = reader.getnchannels()
        width = reader.getsampwidth()
        raw = reader.readframes(reader.getnframes())
    dtype = _INT_DTYPES.get(width)
    if dtype is None:
        raise ValueError(f"unsupported WAV sample width: {width} bytes")
    data = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    # 8-bit PCM is unsigned (centred on 128); wider widths are signed.
    data = ((data - 128.0) / 128.0 if width == 1
            else data / float(2 ** (8 * width - 1)))
    return data, rate


def mouth_open_curve_from_wav(
    path: str | Path,
    fps: float,
    *,
    gate: float = DEFAULT_GATE,
) -> list[float]:
    """Convenience: load a WAV and return its per-frame mouth-open curve."""
    samples, rate = load_wav_mono(path)
    return mouth_open_curve(samples, rate, fps, gate=gate)
