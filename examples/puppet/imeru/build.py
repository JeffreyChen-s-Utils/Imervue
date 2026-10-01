"""Build ``examples/puppet/imeru.puppet``, Imervue's bundled example character, from code.

Run ``py -3 examples/puppet/imeru/build.py`` from anywhere (``--no-render`` reuses the last
render). It models and cel-shades the body, outfit, arms, head and hair in Blender
(``blender/``, through ``render3d.py``; Blender 4.2 or newer, about a minute), paints the
face features (``features.py``, on ``draw.py``), rigs every layer (``rig.py``), adds the
motions and expressions (``motions.py``), saves the file and checks it against the
``.puppet`` format. All of the artwork comes from this code, so the character carries no
third-party rights.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (HERE, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import art  # noqa: E402
import motions  # noqa: E402
import render3d  # noqa: E402
import rig  # noqa: E402
from Imervue.puppet.document import PuppetDocument  # noqa: E402
from Imervue.puppet.document_io import save_puppet  # noqa: E402
from Imervue.puppet.format_schema import check_puppet_file  # noqa: E402

OUTPUT = HERE.parent / "imeru.puppet"
#: Empty canvas above the ahoge, trimmed so a desktop pet window is no taller than she is.
TOP_MARGIN = 200
DISPLAY_NAMES = {
    "ParamHairFront": "Hair front sway",
    "ParamHairSide": "Side locks sway",
    "ParamHairBack": "Back hair sway",
    "ParamArmRA": "Right arm raise",
    "ParamArmRB": "Right forearm bend",
    "ParamArmLA": "Left arm raise",
    "ParamArmLB": "Left forearm bend",
}


def trim_top(doc: PuppetDocument, top: int) -> None:
    """Drop *top* pixels of empty canvas: every vertex and anchor moves up by that much."""
    for drawable in doc.drawables:
        drawable.vertices = [(x, y - top) for x, y in drawable.vertices]
    for deformer in doc.deformers:
        ax, ay = deformer.form["anchor"]
        deformer.form["anchor"] = [ax, ay - top]
    doc.size = (doc.size[0], doc.size[1] - top)


def build(output: Path = OUTPUT, *, render: bool = True) -> dict:
    """Render, rig and save Imeru to *output*; return the format check of the written file.

    With *render* False the layers come from the last render in ``render3d.CACHE``.
    """
    if render:
        render3d.render(render3d.CACHE)
    doc = rig.build(art.all_layers())
    trim_top(doc, TOP_MARGIN)
    doc.motions = motions.motions()
    doc.expressions = motions.expressions()
    doc.display_names = dict(DISPLAY_NAMES)
    save_puppet(doc, output)
    return check_puppet_file(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-render", action="store_true",
                        help="reuse the last Blender render instead of rendering again")
    report = build(render=not parser.parse_args().no_render)
    print(f"{OUTPUT}: valid={report['valid']}, issues={len(report['issues'])}")
    sys.exit(0 if report["valid"] and not report["issues"] else 1)
