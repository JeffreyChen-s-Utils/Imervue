"""Build ``examples/puppet/imeru.puppet``, Imervue's bundled example character, from code.

Run ``py -3 examples/puppet/imeru/build.py`` from anywhere. It draws every layer
(``art.py`` with ``body_arms.py`` and ``refine.py``, on ``draw.py``; about 25 s),
rigs them (``rig.py``), adds the motions and expressions (``motions.py``), saves
the file and checks it against the ``.puppet`` format. The artwork is drawn
entirely by this code, so the character carries no third-party rights.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (HERE, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import art  # noqa: E402
import motions  # noqa: E402
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


def build(output: Path = OUTPUT) -> dict:
    """Draw, rig and save Imeru to *output*; return the format check of the written file."""
    doc = rig.build(art.all_layers())
    trim_top(doc, TOP_MARGIN)
    doc.motions = motions.motions()
    doc.expressions = motions.expressions()
    doc.display_names = dict(DISPLAY_NAMES)
    save_puppet(doc, output)
    return check_puppet_file(output)


if __name__ == "__main__":
    report = build()
    print(f"{OUTPUT}: valid={report['valid']}, issues={len(report['issues'])}")
    sys.exit(0 if report["valid"] and not report["issues"] else 1)
