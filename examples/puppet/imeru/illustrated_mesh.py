"""Texture-preserving meshes over authored regions of the illustration plates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from Imervue.puppet.auto_mesh import triangulate_alpha_grid
from Imervue.puppet.document import Drawable

SIZE = (1024, 1536)
ARTWORK = Path(__file__).parent / "artwork"


def plate(name: str) -> np.ndarray:
    with Image.open(ARTWORK / f"{name}.png") as source:
        if source.size != SIZE:
            raise ValueError(f"{name}: expected {SIZE}, got {source.size}")
        return np.asarray(source.convert("RGBA"))


def region(
    name: str,
    source: str,
    bounds: tuple[int, int, int, int],
    *,
    step: int = 8,
    order: int = 0,
    polygon=None,
) -> Drawable:
    rgba = plate(source)
    x0, y0, x1, y1 = bounds
    topology = np.array(rgba[y0:y1, x0:x1], copy=True)
    if polygon:
        mask = Image.new("L", (x1 - x0, y1 - y0))
        ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in polygon], fill=255)
        topology[..., 3] = np.minimum(topology[..., 3], np.asarray(mask))
    vertices, indices, _ = triangulate_alpha_grid(topology, cell_size=step)
    vertices = [(x + x0, y + y0) for x, y in vertices]
    return Drawable(
        id=name,
        texture=f"textures/{source}.png",
        vertices=vertices,
        indices=indices,
        uvs=[(x / SIZE[0], y / SIZE[1]) for x, y in vertices],
        draw_order=order,
    )


def patch(name: str, source: str, bounds: tuple[int, int, int, int], order=20) -> Drawable:
    return region(name, source, bounds, step=2, order=order)


def ellipse(name, centre, radius, order=22):
    angles = np.linspace(0, 2 * np.pi, 41)[:-1]
    x, y = centre
    rx, ry = radius
    vertices = [(x, y)] + [(x + rx * np.cos(a), y + ry * np.sin(a)) for a in angles]
    indices = [j for i in range(40) for j in (0, i + 1, (i + 1) % 40 + 1)]
    return Drawable(
        id=name,
        texture="textures/master.png",
        vertices=vertices,
        indices=indices,
        uvs=[(px / SIZE[0], py / SIZE[1]) for px, py in vertices],
        draw_order=order,
    )


def opacity(drawable: Drawable, parameter: str, stops: list[tuple[float, float]]) -> None:
    if drawable.opacity_keys is None:
        drawable.opacity_keys = []
    drawable.opacity_keys.append(
        {"parameter": parameter, "stops": [{"value": v, "alpha": a} for v, a in stops]}
    )


def morph(drawable: Drawable, parameter: str, low: np.ndarray, high: np.ndarray) -> None:
    if drawable.vertex_morphs is None:
        drawable.vertex_morphs = []
    drawable.vertex_morphs.append(
        {"parameter": parameter, "delta_at_min": low.tolist(), "delta_at_max": high.tolist()}
    )
