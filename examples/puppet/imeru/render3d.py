"""Render Imeru's 3D layers in Blender and load them as canvas-sized RGBA arrays.

``render(out_dir)`` runs ``blender/main.py`` in a headless Blender (4.2 or newer; looked
up in ``$BLENDER_EXE``, on ``PATH``, under ``D:/Tools/blender-*/`` or
``C:/Program Files/Blender Foundation/``); ``load(out_dir)`` reads the renders back,
averages each 2x render down to the 1024 x 1536 canvas with premultiplied alpha, and cuts
``bang_shadow`` / ``neck_shadow`` from the shadow passes.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ENTRY = HERE / "blender" / "main.py"
CACHE = HERE / "render"
SCALE = 2
_CANDIDATES = ("D:/Tools/blender-*/blender.exe",
               "C:/Program Files/Blender Foundation/Blender */blender.exe")
#: How much darker a shadow pass must be before a pixel counts as shadowed (0-255 luma).
SHADOW_STEP = 6.0


def find_blender() -> str:
    """The Blender executable to use; raises ``FileNotFoundError`` when there is none."""
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).is_file():
        return env
    on_path = shutil.which("blender")
    if on_path:
        return on_path
    for pattern in _CANDIDATES:
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    raise FileNotFoundError("Blender not found: install Blender 4.2 or newer, or set BLENDER_EXE")


def render(out_dir: Path = CACHE, layers: tuple[str, ...] = ()) -> None:
    """Render every 3D layer (or just *layers*) into *out_dir*."""
    command = [find_blender(), "-b", "--factory-startup", "--python", str(ENTRY), "--",
               str(out_dir), *layers]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", check=False)
    if result.returncode != 0 or "Traceback" in result.stdout + result.stderr:
        sys.stderr.write(result.stdout[-4000:] + result.stderr[-4000:])
        raise RuntimeError("Blender render failed")
    for line in result.stdout.splitlines():
        if line.startswith(("rendered ", "baked ")):
            print(line)


def _downsample(rgba: np.ndarray) -> np.ndarray:
    """Average SCALE x SCALE blocks with premultiplied alpha (no dark fringes)."""
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    pre = np.concatenate([rgba[..., :3].astype(np.float32) * a, a * 255.0], axis=-1)
    h, w = pre.shape[0] // SCALE, pre.shape[1] // SCALE
    pre = pre.reshape(h, SCALE, w, SCALE, 4).mean(axis=(1, 3))
    alpha = pre[..., 3:4] / 255.0
    rgb = np.where(alpha > 1e-4, pre[..., :3] / np.maximum(alpha, 1e-4), 0.0)
    return np.clip(np.concatenate([rgb, pre[..., 3:4]], axis=-1) + 0.5, 0, 255).astype(np.uint8)


def _luma(rgba: np.ndarray) -> np.ndarray:
    return rgba[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)


def shadow_layer(lit: np.ndarray, shadowed: np.ndarray, *, top: float = 0.0,
                 bottom: float = 1e9, left: float = 0.0, right: float = 1e9) -> np.ndarray:
    """The pixels of *shadowed* that came out darker than *lit*, inside a canvas box."""
    mask = (_luma(lit) - _luma(shadowed) > SHADOW_STEP) & (lit[..., 3] > 0)
    rows = np.arange(lit.shape[0])[:, None]
    cols = np.arange(lit.shape[1])[None, :]
    mask &= (rows >= top) & (rows <= bottom) & (cols >= left) & (cols <= right)
    out = np.zeros_like(lit)
    out[mask] = shadowed[mask]
    out[..., 3] = np.where(mask, lit[..., 3], 0)
    return out


def load(out_dir: Path = CACHE) -> dict[str, np.ndarray]:
    """The rendered layers at canvas size, plus ``bang_shadow`` and ``neck_shadow``."""
    layers = {}
    for path in sorted(out_dir.glob("*.png")):
        with Image.open(path) as image:
            layers[path.stem] = _downsample(np.asarray(image.convert("RGBA")))
    if "face_shadowed" in layers and "face" in layers:
        layers["bang_shadow"] = shadow_layer(layers["face"], layers.pop("face_shadowed"),
                                             bottom=640)
    if "body_shadowed" in layers and "body" in layers:
        layers["neck_shadow"] = shadow_layer(layers["body"], layers.pop("body_shadowed"),
                                             bottom=870, left=440, right=584)
    return layers


if __name__ == "__main__":
    render(CACHE, tuple(sys.argv[1:]))
