"""Render the GPU develop test cases in a process of their own and save the results.

``tests/test_gpu_develop_renderer.py`` runs this as a subprocess: creating a
wgpu instance in a pytest worker that has already run OpenGL tests crashed
the worker (an access violation in ``get_wgpu_instance``) or hung it. Usage:
``python _gpu_render_worker.py OUT.npz``. The archive holds one array per
case of :data:`CASES` plus ``adapter`` (its name) and ``sliced_contrast``;
without wgpu or an adapter it holds only ``skip`` with the reason.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for _path in (_ROOT, _ROOT / "plugins"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from Imervue.image.recipe import Recipe  # noqa: E402

CASES: dict[str, Recipe] = {
    "white balance": Recipe(temperature=0.3, tint=-0.2),
    "exposure": Recipe(exposure=0.7),
    "highlights and shadows": Recipe(highlights=-0.5, shadows=0.4),
    "whites and blacks": Recipe(whites=0.3, blacks=-0.4),
    "brightness": Recipe(brightness=0.25),
    "contrast": Recipe(contrast=0.4),
    "less contrast": Recipe(contrast=-0.6),
    "vibrance": Recipe(vibrance=0.6),
    "less vibrance": Recipe(vibrance=-0.5),
    "saturation": Recipe(saturation=-0.3),
    "tone curve": Recipe(tone_curve_rgb=[(0, 0), (0.25, 0.2), (0.75, 0.85), (1, 1)],
                         tone_curve_g=[(0, 0.05), (1, 0.95)]),
}
SINGLE_STAGES = tuple(CASES)
CASES["everything"] = Recipe(
    rotate_steps=1, flip_h=True, temperature=0.2, tint=0.1, exposure=0.3, highlights=-0.3,
    shadows=0.3, whites=0.2, blacks=-0.1, brightness=0.1, contrast=0.3, vibrance=0.4,
    saturation=0.2, tone_curve_rgb=[(0, 0), (0.5, 0.55), (1, 1)],
    extra={"levels": {"enabled": True, "black": 10, "white": 240, "gamma": 1.1}},
)
CASES["geometry and levels"] = Recipe(
    rotate_steps=1, crop=(10, 20, 100, 50),
    extra={"levels": {"enabled": True, "black": 20, "white": 200, "gamma": 1.0}},
)
SLICED = Recipe(brightness=0.1, contrast=0.5, vibrance=0.3)
PIXEL_RECIPE = Recipe(exposure=0.4, contrast=0.3, saturation=0.5)


def photo() -> np.ndarray:
    """The test image: 240 x 320 random RGBA with random alpha."""
    rng = np.random.default_rng(7)
    image = rng.integers(0, 256, size=(240, 320, 4), dtype=np.uint8)
    image[..., 3] = rng.integers(0, 256, size=(240, 320), dtype=np.uint8)
    return image


def one_pixel() -> np.ndarray:
    return np.array([[[10, 200, 90, 128]]], dtype=np.uint8)


def _adapter():
    """The discrete GPU when there is one, else any adapter but OpenGL; ``None`` without one."""
    import wgpu

    from gpu_develop.adapter_policy import choose_adapter
    from gpu_develop.renderer import limit_backends
    limit_backends()
    adapters = [a for a in wgpu.gpu.enumerate_adapters_sync() if a.info["adapter_type"] != "Unknown"]
    if not adapters:
        return None
    index = choose_adapter([dict(a.info) for a in adapters])
    return adapters[0 if index is None else index]


def render_all() -> dict[str, np.ndarray]:
    """Every case rendered on the GPU, or ``{"skip": reason}``."""
    try:
        adapter = _adapter()
    except ImportError:
        return {"skip": np.array("wgpu is not installed")}
    if adapter is None:
        return {"skip": np.array("wgpu found no graphics adapter")}
    from gpu_develop.renderer import GpuDevelopRenderer
    renderer = GpuDevelopRenderer(adapter)
    try:
        image = photo()
        out = {name: renderer.render(image, recipe) for name, recipe in CASES.items()}
        out["one pixel"] = renderer.render(one_pixel(), PIXEL_RECIPE)
        out["whole contrast"] = renderer.render(image, SLICED)
        renderer._slice_pixels = 5000  # noqa: SLF001  # force several slices
        out["sliced contrast"] = renderer.render(image, SLICED)
        out["adapter"] = np.array(renderer.label)
        return out
    finally:
        renderer.close()


if __name__ == "__main__":
    np.savez(sys.argv[1], **render_all())
