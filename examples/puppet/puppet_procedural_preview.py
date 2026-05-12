"""Render preview PNGs of the procedural puppet at neutral plus three
phases per motion. Pure-Pillow software rasteriser — no Qt or OpenGL
required, useful for verifying motion before launching the workspace.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))

from puppet.document_io import load_puppet    # noqa: E402
from puppet.motion_sampler import sample_motion    # noqa: E402
from puppet.runtime import (    # noqa: E402
    compose_all_drawables,
    resolve_drawable_opacity,
)


def render_frame(doc, parameter_values: dict[str, float]) -> Image.Image:
    deformed = compose_all_drawables(doc, parameter_values)
    canvas = Image.new("RGBA", doc.size, (255, 255, 255, 255))
    sorted_drawables = sorted(doc.drawables, key=lambda d: d.draw_order)
    for drawable in sorted_drawables:
        if not drawable.visible:
            continue
        alpha_mul = resolve_drawable_opacity(drawable, parameter_values)
        if alpha_mul <= 0.0:
            continue
        verts = deformed[drawable.id]
        with Image.open(BytesIO(doc.textures[drawable.texture])) as tex_img:
            tex = np.asarray(tex_img.convert("RGBA"), dtype=np.uint8)
        _rasterise(canvas, verts, drawable, tex, alpha_mul)
    return canvas


def _rasterise(
    canvas: Image.Image,
    verts: np.ndarray,
    drawable,
    tex: np.ndarray,
    alpha_mul: float = 1.0,
) -> None:
    canvas_arr = np.asarray(canvas, dtype=np.uint8).copy()
    h, w = canvas_arr.shape[:2]
    th, tw = tex.shape[:2]
    indices = drawable.indices
    uvs = np.asarray(drawable.uvs, dtype=np.float64)
    for ti in range(0, len(indices), 3):
        ia, ib, ic = indices[ti], indices[ti + 1], indices[ti + 2]
        va, vb, vc = verts[ia], verts[ib], verts[ic]
        ua, ub, uc = uvs[ia], uvs[ib], uvs[ic]
        x_lo = max(0, int(min(va[0], vb[0], vc[0])))
        x_hi = min(w - 1, int(max(va[0], vb[0], vc[0])) + 1)
        y_lo = max(0, int(min(va[1], vb[1], vc[1])))
        y_hi = min(h - 1, int(max(va[1], vb[1], vc[1])) + 1)
        if x_hi <= x_lo or y_hi <= y_lo:
            continue
        xs, ys = np.meshgrid(
            np.arange(x_lo, x_hi + 1) + 0.5,
            np.arange(y_lo, y_hi + 1) + 0.5,
        )
        denom = (vb[1] - vc[1]) * (va[0] - vc[0]) + (vc[0] - vb[0]) * (va[1] - vc[1])
        if denom == 0:
            continue
        u = ((vb[1] - vc[1]) * (xs - vc[0]) + (vc[0] - vb[0]) * (ys - vc[1])) / denom
        v = ((vc[1] - va[1]) * (xs - vc[0]) + (va[0] - vc[0]) * (ys - vc[1])) / denom
        w_bary = 1.0 - u - v
        mask = (u >= 0) & (v >= 0) & (w_bary >= 0)
        if not mask.any():
            continue
        uv_x = u * ua[0] + v * ub[0] + w_bary * uc[0]
        uv_y = u * ua[1] + v * ub[1] + w_bary * uc[1]
        tex_x = np.clip((uv_x * tw).astype(np.int64), 0, tw - 1)
        tex_y = np.clip((uv_y * th).astype(np.int64), 0, th - 1)
        sampled = tex[tex_y, tex_x]
        alpha = sampled[..., 3:4].astype(np.float32) / 255.0 * float(alpha_mul)
        rows = ys.astype(np.int64)
        cols = xs.astype(np.int64)
        canvas_pixels = canvas_arr[rows, cols].astype(np.float32)
        out = sampled.astype(np.float32) * alpha + canvas_pixels * (1.0 - alpha)
        out_pixels = out.astype(np.uint8)
        mask_flat = mask.reshape(-1)
        rows_flat = rows.reshape(-1)[mask_flat]
        cols_flat = cols.reshape(-1)[mask_flat]
        canvas_arr[rows_flat, cols_flat] = out_pixels.reshape(-1, 4)[mask_flat]
    canvas.frombytes(canvas_arr.tobytes())


def main() -> None:
    here = Path(__file__).parent
    doc = load_puppet(here / "puppet_procedural.puppet")
    out_dir = here / "puppet_procedural_previews"
    out_dir.mkdir(exist_ok=True)
    snapshots = [("neutral", {p.id: p.default for p in doc.parameters})]
    for motion in doc.motions:
        for label, frac in (("p25", 0.25), ("p50", 0.5), ("p75", 0.75)):
            params = {p.id: p.default for p in doc.parameters}
            params.update(sample_motion(motion, motion.duration * frac))
            snapshots.append((f"{motion.name}-{label}", params))
    for label, params in snapshots:
        img = render_frame(doc, params)
        path = out_dir / f"{label}.png"
        img.save(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
