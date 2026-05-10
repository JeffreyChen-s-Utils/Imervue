"""Render preview PNGs of the anime-girl puppet at neutral plus three
phases per motion. Reuses ``preview_tpose``'s software rasteriser so
no Qt or OpenGL is required."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))
sys.path.insert(0, str(Path(__file__).parent))

from preview_tpose import render_frame    # noqa: E402
from puppet.document_io import load_puppet    # noqa: E402
from puppet.motion_sampler import sample_motion    # noqa: E402


def main() -> None:
    here = Path(__file__).parent
    doc = load_puppet(here / "demo_anime_girl.puppet")
    out_dir = here / "anime_girl_previews"
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
