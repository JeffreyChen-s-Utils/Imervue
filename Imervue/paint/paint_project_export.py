"""Multi-page export — turn a :class:`PaintProject` into a deliverable.

Two formats:

* **CBZ** — a ZIP archive of one PNG per page in zero-padded numeric
  order. The format every comic reader (cbzreader / Manga browser /
  Tachiyomi) reads natively.
* **PDF** — one page per project page, sized to match the page's
  pixel dimensions. We use :mod:`Pillow`'s built-in PDF writer so the
  module has no extra runtime dependencies.

Both writers walk the project's pages in order and call
``document.composite()`` to flatten the stack down to a single RGBA
buffer per page. Hidden layers are honoured (already filtered out by
``composite_stack``); transparent backgrounds are flattened against
the page-template fill colour for the PDF path because PDFs don't
preserve canvas-level transparency well.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np

EXPORT_CBZ_EXTENSION = ".cbz"
EXPORT_PDF_EXTENSION = ".pdf"
DEFAULT_PNG_PAD_WIDTH = 3   # ``001.png`` / ``012.png`` / ``107.png``
DEFAULT_PDF_BACKGROUND = (255, 255, 255, 255)


def export_project_cbz(
    project,
    path: str | Path,
    *,
    pad_width: int = DEFAULT_PNG_PAD_WIDTH,
) -> Path:
    """Write a CBZ (zip of PNGs) for ``project`` and return the resolved path.

    Pages keep their layer transparency in the PNG output. The
    filenames are zero-padded so the natural alphabetical order
    matches the page order — every CBZ reader sorts pages by name.
    """
    from PIL import Image
    if project.page_count == 0:
        raise ValueError("project has no pages — nothing to export")
    pad = max(2, int(pad_width))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for index, page in enumerate(project.pages, start=1):
            image = _composite_or_default(page)
            buffer = io.BytesIO()
            Image.fromarray(image, mode="RGBA").save(buffer, format="PNG")
            zf.writestr(f"{index:0{pad}d}.png", buffer.getvalue())
    return target.resolve()


def export_project_pdf(
    project,
    path: str | Path,
    *,
    background: tuple[int, int, int, int] = DEFAULT_PDF_BACKGROUND,
) -> Path:
    """Write a multi-page PDF for ``project`` and return the resolved path.

    Each PDF page is sized to match the project page's pixel
    dimensions (PDF accepts pixel sizing via Pillow's PDF writer).
    Transparent layer pixels are flattened against ``background``
    so a partially-transparent canvas never produces a black PDF
    page.
    """
    from PIL import Image
    if project.page_count == 0:
        raise ValueError("project has no pages — nothing to export")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    flattened = [
        Image.fromarray(
            _flatten_against(_composite_or_default(page), background),
            mode="RGB",
        )
        for page in project.pages
    ]
    head, *rest = flattened
    head.save(
        target,
        format="PDF",
        save_all=bool(rest),
        append_images=rest,
    )
    return target.resolve()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _composite_or_default(page) -> np.ndarray:
    """Return the page's flattened RGBA image, or a blank fallback.

    ``PaintDocument.composite`` returns ``None`` for an empty
    document — happens when a page is constructed but no layer ever
    landed. The fallback is a 1×1 transparent buffer so the writer
    can still produce a valid output entry rather than crashing.
    """
    composite = page.document.composite()
    if composite is None:
        return np.zeros((1, 1, 4), dtype=np.uint8)
    return composite


def _flatten_against(
    rgba: np.ndarray,
    background: tuple[int, int, int, int],
) -> np.ndarray:
    """Composite ``rgba`` over a solid ``background`` colour, return RGB."""
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {rgba.shape} {rgba.dtype}",
        )
    bg_arr = np.empty_like(rgba)
    bg_arr[..., :] = background
    fg = rgba.astype(np.float32) / 255.0
    bg = bg_arr.astype(np.float32) / 255.0
    fg_a = fg[..., 3:4]
    out_rgb = bg[..., :3] * (1.0 - fg_a) + fg[..., :3] * fg_a
    return np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
