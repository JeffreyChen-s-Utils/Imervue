"""Combine images into a multi-page PDF/TIFF and split such files back out.

Combining uses Pillow's ``save_all`` / ``append_images``; splitting walks the
frames of a raster multi-page file (TIFF/GIF/APNG) via ``seek``. Splitting a
PDF back into images needs a PDF renderer (poppler / PyMuPDF) and is out of
scope here — ``split_multipage`` handles the raster formats Pillow can read.

The format mapping and page-naming are pure and unit-tested; the combine/split
round-trip is verified on TIFF (native to Pillow, no extra dependency).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from Imervue.system.atomic_write import replace_atomically
from Imervue.system.free_names import free_names

_FORMAT_BY_EXT: dict[str, str] = {".pdf": "PDF", ".tif": "TIFF", ".tiff": "TIFF"}
_PAGE_NUMBER_WIDTH = 3
# Formats that cannot carry alpha / palette — flatten to RGB before saving.
_RGB_ONLY = frozenset({"PDF"})
# Pillow counts a PSD's layers as its frames (numbered from 1): layers of one
# picture, not pages, and seeking frame 0 raises EOFError.
_SINGLE_PICTURE_FORMATS = frozenset({"PSD"})
# The MPF index of an MPO (a JPEG carrying more pictures), and the prefix of the
# picture types that are frames of their own: stereo pairs, multi-angle, panorama.
_MP_ENTRIES = 0xB002
_MP_FRAME_TYPE = "Multi-Frame"


def multipage_format(ext: str) -> str | None:
    """Return the Pillow save format for a multi-page extension, or None."""
    return _FORMAT_BY_EXT.get(ext.lower())


def page_count(img: Image.Image) -> int:
    """The pages *img* holds: its frames, except those that belong to one picture.

    A PSD's frames are its layers. An MPO is a JPEG whose MPF index lists more
    pictures, and a camera writes its large preview (or a depth or gain map)
    there: only an MPF of stereo, multi-angle or panorama frames has pages.
    """
    if img.format in _SINGLE_PICTURE_FORMATS:
        return 1
    if img.format == "MPO" and not _has_mp_frames(img):
        return 1
    return getattr(img, "n_frames", 1)


def _has_mp_frames(img: Image.Image) -> bool:
    entries = getattr(img, "mpinfo", {}).get(_MP_ENTRIES, [])
    return any(str(entry.get("Attribute", {}).get("MPType", "")).startswith(_MP_FRAME_TYPE)
               for entry in entries)


def split_page_stem(source: str, index: int) -> str:
    """Name of one split page without its extension: ``doc_page002`` (zero-padded index)."""
    return f"{Path(source).stem}_page{index:0{_PAGE_NUMBER_WIDTH}d}"


def _suffix(ext: str) -> str:
    return (ext if ext.startswith(".") else f".{ext}").lower()


def _prepare(img: Image.Image, fmt: str) -> Image.Image:
    if fmt in _RGB_ONLY and img.mode not in ("RGB", "L"):
        return img.convert("RGB")
    if img.mode == "P":
        return img.convert("RGB")
    return img


def combine_to_multipage(paths: list[str], destination: str) -> dict:
    """Combine *paths* into one multi-page file at *destination* (.pdf/.tif).

    Each page is the viewer's decode: upright, sRGB, a camera RAW developed.
    A page keeps no EXIF or colour profile (a PDF page can't), so anything
    else would lie on its side or show the wrong colours. *destination* is
    replaced in one step: a failed save leaves an existing file whole, even
    when it is one of the pages.
    """
    from Imervue.gpu_image_view.images.image_loader import decode_image
    fmt = multipage_format(Path(destination).suffix)
    if fmt is None:
        raise ValueError(f"destination must be .pdf/.tif/.tiff, got {destination!r}")
    if not paths:
        raise ValueError("no input images to combine")
    pages = [_prepare(decode_image(path), fmt) for path in paths]
    replace_atomically(destination, lambda tmp: pages[0].save(
        tmp, format=fmt, save_all=True, append_images=pages[1:]))
    return {"destination": str(destination), "format": fmt, "pages": len(paths)}


def split_multipage(source: str, out_dir: str, ext: str = ".png") -> list[Path]:
    """Split a raster multi-page file (TIFF/GIF/APNG) into one image per page.

    The pages are ``doc_page000.png`` … in *out_dir*; when any of those names
    is taken (an earlier split, perhaps retouched since) the whole set moves
    to ``doc_page000_1.png`` … instead of replacing it.
    """
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    suffix = _suffix(ext)
    mode = "RGBA" if suffix == ".png" else "RGB"
    saved: list[Path] = []
    with Image.open(source) as img:
        frames = page_count(img)
        stems = [split_page_stem(source, index) for index in range(frames)]
        for index, out_path in enumerate(free_names(out_root, stems, suffix)):
            if frames > 1:   # a PSD's frame 0 can't be sought: its picture is already loaded
                img.seek(index)
            img.convert(mode).save(str(out_path))
            saved.append(out_path)
    return saved
