"""Edit an existing animated image (GIF / APNG / animated WebP).

Complements the stills→GIF maker: load an animation's frames and per-frame
durations, transform the frame list (reverse, boomerang, change speed, drop
duplicate frames), then re-save. The list transforms are pure and unit-tested;
only load/save touch Pillow IO.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

REVERSE = "reverse"
BOOMERANG = "boomerang"
SPEED = "speed"
OPTIMIZE = "optimize"
OPERATIONS = (REVERSE, BOOMERANG, SPEED, OPTIMIZE)

_DEFAULT_DURATION = 100
_MIN_DURATION = 10
_MIN_FRAMES_FOR_BOOMERANG = 2


def load_frames(path: str) -> tuple[list[Image.Image], list[int]]:
    """Return ``(frames, durations_ms)`` for the animation at *path* (RGBA frames)."""
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(path) as anim:
        for frame in ImageSequence.Iterator(anim):
            frames.append(frame.convert("RGBA").copy())
            durations.append(int(frame.info.get("duration", _DEFAULT_DURATION)))
    return frames, durations


def reverse(frames: list, durations: list[int]) -> tuple[list, list[int]]:
    """Play the animation backwards."""
    return list(reversed(frames)), list(reversed(durations))


def boomerang(frames: list, durations: list[int]) -> tuple[list, list[int]]:
    """Append the reversed middle frames so the clip plays forward then back."""
    if len(frames) < _MIN_FRAMES_FOR_BOOMERANG:
        return list(frames), list(durations)
    return frames + frames[-2:0:-1], durations + durations[-2:0:-1]


def set_speed(durations: list[int], factor: float) -> list[int]:
    """Scale playback speed: ``factor`` > 1 speeds up (shorter durations)."""
    factor = max(0.05, float(factor))
    return [max(_MIN_DURATION, int(round(d / factor))) for d in durations]


def drop_duplicate_frames(frames: list, durations: list[int]) -> tuple[list, list[int]]:
    """Merge runs of identical consecutive frames, folding their durations."""
    if not frames:
        return [], []
    kept_frames = [frames[0]]
    kept_durations = [durations[0]]
    for frame, duration in zip(frames[1:], durations[1:], strict=True):
        if np.array_equal(np.asarray(frame), np.asarray(kept_frames[-1])):
            kept_durations[-1] += duration
        else:
            kept_frames.append(frame)
            kept_durations.append(duration)
    return kept_frames, kept_durations


def save_animation(frames: list, durations: list[int], out_path: str, *, loop: int = 0) -> None:
    """Save *frames* as an animation, format inferred from the extension."""
    if not frames:
        raise ValueError("no frames to save")
    fmt = "WEBP" if Path(out_path).suffix.lower() == ".webp" else "GIF"
    frames[0].save(
        out_path, format=fmt, save_all=True, append_images=frames[1:],
        duration=durations, loop=loop, disposal=2, optimize=True,
    )


def edit_animation(path: str, operation: str, out_path: str, *, speed: float = 1.0) -> int:
    """Apply *operation* to the animation at *path*, save to *out_path*, return frame count."""
    frames, durations = load_frames(path)
    if operation == REVERSE:
        frames, durations = reverse(frames, durations)
    elif operation == BOOMERANG:
        frames, durations = boomerang(frames, durations)
    elif operation == SPEED:
        durations = set_speed(durations, speed)
    elif operation == OPTIMIZE:
        frames, durations = drop_duplicate_frames(frames, durations)
    else:
        raise ValueError(f"unknown operation {operation!r}; expected one of {OPERATIONS}")
    save_animation(frames, durations, out_path)
    return len(frames)
