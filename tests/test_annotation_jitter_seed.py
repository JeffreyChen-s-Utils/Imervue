"""Brush jitter must not depend on the process's string-hash seed.

Spray, charcoal and crayon strokes scatter their marks from a per-annotation
RNG. It used to be seeded with ``hash(ann.id)``, and Python randomises ``str``
hashes per process, so a saved project baked or previewed differently every
time it was reopened.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from Imervue.gui import annotation_models as models

_REPO = Path(__file__).resolve().parents[1]

_BAKE_SCRIPT = """
import hashlib
from PIL import Image
from Imervue.gui.annotation_models import Annotation, bake

pts = [(10 + i * 7, 40 + (i % 4) * 9) for i in range(20)]
anns = [
    Annotation(kind="freehand", points=pts, color=(255, 0, 0, 255), stroke_width=4,
               brush_type=brush, id="fixed-" + brush)
    for brush in ("spray", "charcoal", "crayon", "pencil")
]
out = bake(Image.new("RGBA", (180, 100), (255, 255, 255, 255)), anns)
print(hashlib.sha256(out.tobytes()).hexdigest())
"""


def _bake_digest(hash_seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONPATH=str(_REPO))
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", _BAKE_SCRIPT], capture_output=True, text=True,
        env=env, cwd=_REPO, check=True, timeout=120,
    )
    return result.stdout.strip()


def test_jitter_seed_is_stable_and_32_bit():
    seed = models.jitter_seed("abc123")
    assert seed == models.jitter_seed("abc123")
    assert 0 <= seed <= 0xFFFFFFFF


def test_jitter_seed_matches_crc32():
    import zlib
    assert models.jitter_seed("probe-7") == zlib.crc32(b"probe-7")


def test_different_ids_get_different_seeds():
    seeds = {models.jitter_seed(f"id-{i}") for i in range(50)}
    assert len(seeds) == 50


@pytest.mark.parametrize("seeds", [("0", "1"), ("12345", "999")])
def test_bake_is_identical_across_processes(seeds):
    first, second = (_bake_digest(s) for s in seeds)
    assert first == second


def test_bake_in_process_matches_a_subprocess():
    from PIL import Image
    from Imervue.gui.annotation_models import Annotation, bake
    pts = [(10 + i * 7, 40 + (i % 4) * 9) for i in range(20)]
    anns = [
        Annotation(kind="freehand", points=pts, color=(255, 0, 0, 255), stroke_width=4,
                   brush_type=brush, id="fixed-" + brush)
        for brush in ("spray", "charcoal", "crayon", "pencil")
    ]
    out = bake(Image.new("RGBA", (180, 100), (255, 255, 255, 255)), anns)
    assert hashlib.sha256(out.tobytes()).hexdigest() == _bake_digest("7")
