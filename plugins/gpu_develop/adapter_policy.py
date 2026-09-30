"""Which graphics adapter renders: a discrete GPU, never an integrated one or a software one.

Pure policy over the ``info`` dicts ``wgpu`` reports for each adapter
(``adapter_type`` is ``DiscreteGPU``, ``IntegratedGPU``, ``CPU``, ``VirtualGPU`` or
``Unknown``). On a hybrid laptop the integrated GPU shares the CPU's memory and
power budget and is slower than the CPU path for large images, so it is not used.
"""
from __future__ import annotations

import sys
from collections.abc import Sequence

DISCRETE = "DiscreteGPU"
# Vulkan before D3D12 on Windows: wgpu compiles D3D12 shaders with FXC, which reorders
# floating-point maths, so its results stray further from the CPU renderer's at the
# same speed. OpenGL is never used (wgpu reports its adapter type as Unknown anyway).
_BACKEND_ORDER = {
    "win32": ("Vulkan", "D3D12"),
    "darwin": ("Metal",),
}
_DEFAULT_ORDER = ("Vulkan",)


def backend_order(platform: str = sys.platform) -> tuple[str, ...]:
    """The graphics APIs tried on *platform*, preferred first."""
    return _BACKEND_ORDER.get(platform, _DEFAULT_ORDER)


def choose_adapter(infos: Sequence[dict], platform: str = sys.platform) -> int | None:
    """Index of the adapter to use: a discrete GPU on the preferred API; ``None`` if there is none."""
    order = backend_order(platform)
    candidates = [(i, info) for i, info in enumerate(infos)
                  if info.get("adapter_type") == DISCRETE and info.get("backend_type") in order]
    if not candidates:
        return None
    return min(candidates, key=lambda pair: order.index(pair[1]["backend_type"]))[0]


def describe(info: dict) -> str:
    """``"NVIDIA GeForce RTX 5060 Laptop GPU (Vulkan)"``."""
    name = str(info.get("device") or "GPU").strip()
    backend = info.get("backend_type")
    return f"{name} ({backend})" if backend else name
