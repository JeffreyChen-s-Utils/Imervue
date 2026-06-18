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

_FORMAT_BY_EXT: dict[str, str] = {".pdf": "PDF", ".tif": "TIFF", ".tiff": "TIFF"}
_PAGE_NUMBER_WIDTH = 3
# Formats that cannot carry alpha / palette — flatten to RGB before saving.
_RGB_ONLY = frozenset({"PDF"})


def multipage_format(ext: str) -> str | None:
    """Return the Pillow save format for a multi-page extension, or None."""
    return _FORMAT_BY_EXT.get(ext.lower())


def split_page_name(source: str, index: int, ext: str) -> str:
    """Deterministic output filename for one split page (zero-padded index)."""
    suffix = ext if ext.startswith(".") else f".{ext}"
    return f"{Path(source).stem}_page{index:0{_PAGE_NUMBER_WIDTH}d}{suffix.lower()}"


def _prepare(img: Image.Image, fmt: str) -> Image.Image:
    if fmt in _RGB_ONLY and img.mode not in ("RGB", "L"):
        return img.convert("RGB")
    if img.mode == "P":
        return img.convert("RGB")
    return img


def combine_to_multipage(paths: list[str], destination: str) -> dict:
    """Combine *paths* into one multi-page file at *destination* (.pdf/.tif)."""
    fmt = multipage_format(Path(destination).suffix)
    if fmt is None:
        raise ValueError(f"destination must be .pdf/.tif/.tiff, got {destination!r}")
    if not paths:
        raise ValueError("no input images to combine")
    pages: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as img:
            img.load()
            pages.append(_prepare(img.copy(), fmt))
    pages[0].save(str(destination), format=fmt, save_all=True,
                  append_images=pages[1:])
    return {"destination": str(destination), "format": fmt, "pages": len(paths)}


def split_multipage(source: str, out_dir: str, ext: str = ".png") -> list[Path]:
    """Split a raster multi-page file (TIFF/GIF/APNG) into one image per page."""
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    mode = "RGBA" if ext.lower() == ".png" else "RGB"
    saved: list[Path] = []
    with Image.open(source) as img:
        frames = getattr(img, "n_frames", 1)
        for index in range(frames):
            img.seek(index)
            out_path = out_root / split_page_name(source, index, ext)
            img.convert(mode).save(str(out_path))
            saved.append(out_path)
    return saved
