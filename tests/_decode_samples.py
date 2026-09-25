"""Sample files for the "decode like the viewer" regression tests of the exporters."""
from __future__ import annotations

from PIL import Image

from _icc_profiles import DISPLAY_P3


def tagged_portrait(path, size=(40, 20)):
    """Stored *size* pixels tagged orientation 6: shown with its sides swapped."""
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", size, (90, 120, 150)).save(path, exif=exif)
    return path


def p3_green(path):
    """A pure Display P3 green, which lies outside sRGB: converted, it clips to (0, 255, …)."""
    Image.new("RGB", (8, 8), (0, 255, 0)).save(path, icc_profile=DISPLAY_P3)
    return path


def upright_and_tagged_copies(folder):
    """The same shot twice: stored upright, and stored on its side with a turn tag."""
    import numpy as np
    rng = np.random.default_rng(1)
    upright = Image.fromarray(rng.integers(0, 255, (60, 40, 3), dtype=np.uint8)).resize((200, 300))
    exif = Image.Exif()
    exif[0x0112] = 6
    tagged = folder / "tagged.jpg"
    upright.transpose(Image.Transpose.ROTATE_90).save(tagged, exif=exif, quality=95)
    plain = folder / "upright.jpg"
    upright.save(plain, quality=95)
    return str(plain), str(tagged)
