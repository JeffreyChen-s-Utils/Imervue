"""Tool handlers exposed by the Imervue MCP server.

Each function is a self-contained piece of Imervue's pure-logic
surface — image metadata, XMP tags, format conversion, puppet rig
inspection — that's useful to an AI client. Qt-free so the server
can run as a subprocess.

The handlers live in their own module so:

* Tests can import them directly and assert on return values
  without serialising through JSON-RPC.
* :func:`register_default_tools` is the one place an upstream
  packager updates when adding or removing a tool from the default
  set.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Imervue.mcp_server.server import MCPServer

# Image extensions the listing helper considers (lower-case, with dot).
_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
    ".gif", ".heic", ".heif", ".dng", ".cr2", ".cr3", ".nef",
    ".arw", ".raf", ".orf", ".rw2", ".pef", ".srw",
})

_CONVERTIBLE_FORMATS: frozenset[str] = frozenset({
    "png", "jpeg", "jpg", "webp", "tiff", "tif", "bmp",
})
# Optional-backend output formats, routed through save_formats (HEIF / JXL).
_EXTRA_FORMAT_NAMES: dict[str, str] = {"heic": "HEIC", "avif": "AVIF", "jxl": "JXL"}
_SHARPNESS_MAX_SIDE = 512
_RGB_MAX = 255
_DEFAULT_WATERMARK_COLOR = (_RGB_MAX, _RGB_MAX, _RGB_MAX)
_DEFAULT_FRAME_TEXT_COLOR = (40, 40, 40)
_WATERMARK_CORNERS = frozenset({
    "top-left", "top-right", "bottom-left", "bottom-right", "center",
})
# Destination formats that can't carry alpha — flatten to RGB before saving.
_NO_ALPHA_FORMATS = frozenset({"jpg", "jpeg", "bmp"})


# ---------------------------------------------------------------------------
# list_images
# ---------------------------------------------------------------------------


def list_images(folder: str, *, recursive: bool = False) -> dict[str, Any]:
    """Return image files under ``folder`` with their basic stats.

    Set ``recursive`` to walk subdirectories. Non-image files and
    hidden files (leading dot) are skipped. Each entry has ``path``,
    ``size_bytes`` and ``mtime`` so an AI client can quickly find the
    latest / largest images without a separate fs call.
    """
    base = _validated_dir(folder)
    iterator = base.rglob("*") if recursive else base.iterdir()
    entries: list[dict[str, Any]] = []
    for path in iterator:
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append({
            "path": str(path),
            "size_bytes": int(stat.st_size),
            "mtime": stat.st_mtime,
        })
    entries.sort(key=lambda e: e["path"])
    return {"folder": str(base), "count": len(entries), "images": entries}


# ---------------------------------------------------------------------------
# read_image_metadata
# ---------------------------------------------------------------------------


def read_image_metadata(path: str) -> dict[str, Any]:
    """Return dimensions, format, EXIF tags, and XMP sidecar fields for
    an image. Missing data is reported as the appropriate empty value
    rather than raising — a JPEG with no EXIF still returns its
    dimensions.
    """
    image_path = _validated_file(path)
    out: dict[str, Any] = {"path": str(image_path)}
    _populate_basic_image_info(image_path, out)
    _populate_exif(image_path, out)
    _populate_xmp(image_path, out)
    return out


def _populate_basic_image_info(image_path: Path, out: dict[str, Any]) -> None:
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            out["width"] = int(img.width)
            out["height"] = int(img.height)
            out["format"] = img.format or ""
            out["mode"] = img.mode
    except Exception as exc:   # noqa: BLE001 - Pillow raises a zoo of exception types
        out["error"] = f"image probe failed: {exc}"


def _populate_exif(image_path: Path, out: dict[str, Any]) -> None:
    try:
        from Imervue.image.info import get_exif_data
        exif = get_exif_data(image_path) or {}
    except Exception:   # noqa: BLE001 - same as Pillow path
        exif = {}
    # EXIF values include byte strings / IFDRational; coerce to JSON-friendly types.
    out["exif"] = {str(k): _json_safe(v) for k, v in exif.items()}


def _populate_xmp(image_path: Path, out: dict[str, Any]) -> None:
    try:
        from Imervue.image import xmp_sidecar
        xmp = xmp_sidecar.load(image_path)
        out["xmp"] = {
            "rating": int(xmp.rating),
            "title": xmp.title,
            "description": xmp.description,
            "keywords": list(xmp.keywords),
            "color_label": xmp.color_label,
        }
    except Exception:   # noqa: BLE001 - missing sidecar is normal
        out["xmp"] = None


# ---------------------------------------------------------------------------
# read_xmp_tags
# ---------------------------------------------------------------------------


def read_xmp_tags(path: str) -> dict[str, Any]:
    """Return only the XMP sidecar fields for ``path`` — handy when
    the caller wants tags / rating without paying the EXIF parse."""
    image_path = _validated_file(path)
    from Imervue.image import xmp_sidecar
    xmp = xmp_sidecar.load(image_path)
    return {
        "path": str(image_path),
        "rating": int(xmp.rating),
        "title": xmp.title,
        "description": xmp.description,
        "keywords": list(xmp.keywords),
        "color_label": xmp.color_label,
        "is_empty": xmp.is_empty(),
    }


# ---------------------------------------------------------------------------
# convert_format
# ---------------------------------------------------------------------------


def convert_format(
    source: str,
    destination: str,
    *,
    quality: int = 90,
) -> dict[str, Any]:
    """Convert ``source`` into ``destination``. The destination format
    is inferred from the destination suffix. ``quality`` applies to
    JPEG / WebP.

    Returns the destination path plus size in bytes so the caller can
    confirm the write landed."""
    src = _validated_file(source)
    dst = Path(destination)
    if not dst.parent.exists():
        raise ValueError(f"destination parent {dst.parent} does not exist")
    fmt = dst.suffix.lower().lstrip(".")
    if fmt in _EXTRA_FORMAT_NAMES:
        return _convert_via_save_formats(src, dst, fmt, quality)
    if fmt not in _CONVERTIBLE_FORMATS:
        raise ValueError(
            f"unsupported destination format {fmt!r}; "
            f"expected one of {sorted(_CONVERTIBLE_FORMATS | set(_EXTRA_FORMAT_NAMES))}",
        )
    from PIL import Image
    with Image.open(src) as opened:
        save_kwargs: dict[str, Any] = {}
        normalised = "jpeg" if fmt in {"jpg", "jpeg"} else fmt
        if normalised in {"jpeg", "webp"}:
            save_kwargs["quality"] = max(1, min(100, int(quality)))
        # JPEG can't carry alpha — convert to RGB so a PNG-with-alpha
        # source doesn't fail mid-save. Keep the converted handle as a
        # separate name so we don't clobber the ``with`` binding.
        to_save = opened.convert("RGB") if (
            normalised == "jpeg" and opened.mode in {"RGBA", "LA"}
        ) else opened
        to_save.save(dst, format=normalised.upper(), **save_kwargs)
    return {
        "source": str(src),
        "destination": str(dst),
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# puppet_from_png
# ---------------------------------------------------------------------------


def puppet_from_png(
    source: str,
    destination: str,
    *,
    cell_size: int = 64,
) -> dict[str, Any]:
    """Run the built-in puppet PNG → ``.puppet`` import on ``source``
    and save the resulting document to ``destination``.

    Wraps :func:`Imervue.puppet.auto_mesh.puppet_from_png` +
    :func:`Imervue.puppet.document_io.save_puppet`."""
    src = _validated_file(source)
    dst = Path(destination)
    if not dst.parent.exists():
        raise ValueError(f"destination parent {dst.parent} does not exist")
    from Imervue.puppet.auto_mesh import puppet_from_png as build_puppet
    from Imervue.puppet.document_io import save_puppet
    doc = build_puppet(src, cell_size=int(cell_size))
    save_puppet(doc, dst)
    drawable = doc.drawables[0]
    return {
        "destination": str(dst),
        "canvas_size": list(doc.size),
        "vertex_count": len(drawable.vertices),
        "triangle_count": len(drawable.indices) // 3,
        "parameter_count": len(doc.parameters),
    }


# ---------------------------------------------------------------------------
# puppet_inspect
# ---------------------------------------------------------------------------


def puppet_inspect(path: str) -> dict[str, Any]:
    """Open a ``.puppet`` archive and return its top-level inventory:
    parameters, deformers, motions, expressions, hit areas, parts."""
    src = _validated_file(path)
    from Imervue.puppet.document_io import load_puppet
    doc = load_puppet(src)
    return {
        "path": str(src),
        "size": list(doc.size),
        "drawables": [d.id for d in doc.drawables],
        "deformers": [{"id": d.id, "type": d.type} for d in doc.deformers],
        "parameters": [
            {"id": p.id, "min": p.min, "max": p.max, "default": p.default,
             "key_count": len(p.keys)}
            for p in doc.parameters
        ],
        "motions": [
            {"name": m.name, "duration": m.duration, "loop": m.loop, "group": m.group}
            for m in doc.motions
        ],
        "expressions": [e.name for e in doc.expressions],
        "hit_areas": [h.id for h in doc.hit_areas],
        "parts": [p.id for p in doc.parts],
        "parameter_blends": [b.id for b in doc.parameter_blends],
        "physics_rigs": [r.id for r in doc.physics_rigs],
    }


def _convert_via_save_formats(src: Path, dst: Path, fmt: str, quality: int) -> dict[str, Any]:
    """Convert through save_formats for the optional HEIC/AVIF/JXL backends."""
    from PIL import Image
    from Imervue.image.save_formats import save_image
    with Image.open(src) as opened:
        save_image(opened, str(dst), _EXTRA_FORMAT_NAMES[fmt], max(1, min(100, int(quality))))
    return {
        "source": str(src),
        "destination": str(dst),
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# reverse_geocode
# ---------------------------------------------------------------------------


def reverse_geocode(latitude: float, longitude: float) -> dict[str, Any]:
    """Resolve GPS coordinates to the nearest major city, offline.

    Returns the ``"City, Country"`` place name and ``[city, country]`` keywords.
    """
    from Imervue.image.reverse_geocode import place_keywords
    from Imervue.image.reverse_geocode import reverse_geocode as _resolve
    lat, lon = float(latitude), float(longitude)
    return {
        "latitude": lat,
        "longitude": lon,
        "place": _resolve(lat, lon),
        "keywords": place_keywords(lat, lon),
    }


# ---------------------------------------------------------------------------
# extract_video_frame
# ---------------------------------------------------------------------------


def extract_video_frame(
    source: str, destination: str, *, frame_index: int = 0,
) -> dict[str, Any]:
    """Decode one frame of a video and save it as an image.

    ``destination``'s suffix picks the still format. Needs the imageio ffmpeg
    backend; its absence surfaces as an error rather than a crash.
    """
    src = _validated_file(source)
    dst = Path(destination)
    if not dst.parent.exists():
        raise ValueError(f"destination parent {dst.parent} does not exist")
    from PIL import Image
    from Imervue.image.video_frames import FrameReader
    with FrameReader(str(src)) as reader:
        arr = reader.frame(int(frame_index))
    with Image.fromarray(arr, mode="RGB") as img:
        img.save(dst)
    return {
        "source": str(src),
        "destination": str(dst),
        "frame_index": int(frame_index),
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# sharpness_score
# ---------------------------------------------------------------------------


def sharpness_score(path: str) -> dict[str, Any]:
    """Score an image's sharpness (Laplacian variance); flag likely-blurry."""
    import numpy as np
    from PIL import Image
    from Imervue.image.sharpness import DEFAULT_BLUR_THRESHOLD
    from Imervue.image.sharpness import sharpness_score as _score
    img_path = _validated_file(path)
    with Image.open(img_path) as opened:
        gray = opened.convert("L")
        gray.thumbnail((_SHARPNESS_MAX_SIDE, _SHARPNESS_MAX_SIDE))
        arr = np.asarray(gray, dtype=np.float64)
    score = _score(arr)
    return {
        "path": str(img_path),
        "score": score,
        "blurry": score < DEFAULT_BLUR_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# image_statistics
# ---------------------------------------------------------------------------


def _load_rgba_array(image_path: Path):
    import numpy as np
    from PIL import Image
    with Image.open(image_path) as opened:
        return np.array(opened.convert("RGBA"))


def image_statistics(path: str) -> dict[str, Any]:
    """Return per-channel (r/g/b/luma) mean, min, max, std and median."""
    img_path = _validated_file(path)
    from Imervue.image.statistics import image_statistics as _stats
    stats = _stats(_load_rgba_array(img_path))
    rounded = {
        channel: {metric: round(value, 3) for metric, value in metrics.items()}
        for channel, metrics in stats.items()
    }
    return {"path": str(img_path), "statistics": rounded}


# ---------------------------------------------------------------------------
# quality_metrics
# ---------------------------------------------------------------------------


def quality_metrics(path: str) -> dict[str, Any]:
    """Return no-reference quality metrics: colourfulness, entropy, RMS
    contrast, edge density and a noise-sigma estimate."""
    img_path = _validated_file(path)
    from Imervue.image.quality_metrics import quality_metrics as _metrics
    metrics = {k: round(v, 3) for k, v in _metrics(_load_rgba_array(img_path)).items()}
    return {"path": str(img_path), "metrics": metrics}


# ---------------------------------------------------------------------------
# read_histogram
# ---------------------------------------------------------------------------


def read_histogram(path: str) -> dict[str, Any]:
    """Return the 256-bin per-channel histogram and exposure-clipping fractions."""
    img_path = _validated_file(path)
    from Imervue.image.histogram import compute_clipping, compute_histogram
    arr = _load_rgba_array(img_path)
    hist = compute_histogram(arr)
    clip = compute_clipping(arr)
    return {
        "path": str(img_path),
        "histogram": {
            "r": hist.r.tolist(), "g": hist.g.tolist(),
            "b": hist.b.tolist(), "luma": hist.luma.tolist(),
        },
        "clipping": {
            "over_fraction": round(clip.over_fraction, 4),
            "under_fraction": round(clip.under_fraction, 4),
        },
    }


# ---------------------------------------------------------------------------
# ocr_text
# ---------------------------------------------------------------------------


def ocr_text(path: str, min_confidence: float = 0.0) -> dict[str, Any]:
    """Extract text from an image via Tesseract. Degrades gracefully: when the
    optional backend is missing it returns ``available=False`` rather than
    raising, so an agent can fall back."""
    img_path = _validated_file(path)
    from Imervue.image.ocr import extract_text, ocr_available
    if not ocr_available():
        return {"path": str(img_path), "available": False, "text": ""}
    return {
        "path": str(img_path),
        "available": True,
        "text": extract_text(str(img_path), float(min_confidence)),
    }


# ---------------------------------------------------------------------------
# image_thumbnail
# ---------------------------------------------------------------------------

_THUMB_MAX = 512


def image_thumbnail(path: str, max_size: int = 256) -> dict[str, Any]:
    """Return a downscaled PNG preview as a base64 data URI (bounded size)."""
    import base64
    import io
    from PIL import Image
    img_path = _validated_file(path)
    box = max(16, min(_THUMB_MAX, int(max_size)))
    with Image.open(img_path) as opened:
        thumb = opened.convert("RGBA")
        thumb.thumbnail((box, box), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        thumb.save(buffer, format="PNG")
        width, height = thumb.size
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {
        "path": str(img_path),
        "width": width,
        "height": height,
        "data_uri": f"data:image/png;base64,{encoded}",
    }


# ---------------------------------------------------------------------------
# find_similar
# ---------------------------------------------------------------------------


def find_similar(
    folder: str,
    *,
    threshold: int = 5,
    recursive: bool = False,
    progress: Any = None,
) -> dict[str, Any]:
    """Group near-duplicate images in *folder* by perceptual (dHash) similarity.

    ``threshold`` is the maximum Hamming distance (0 = identical hash, higher =
    more tolerant). Returns the groups (each a list of paths) of size > 1.
    ``progress`` is an optional reporter injected by the server; each hashed
    image advances it.
    """
    base = _validated_dir(folder)
    iterator = base.rglob("*") if recursive else base.iterdir()
    paths = [
        str(p) for p in iterator
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    ]
    from Imervue.image.perceptual_hash import find_similar as _find
    on_progress = None
    if progress is not None:
        def report_progress(done: int, total: int) -> None:
            progress.report(done, total=total, message=f"hashed {done}/{total}")
        on_progress = report_progress
    groups = _find(sorted(paths), int(threshold), on_progress=on_progress)
    return {
        "folder": str(base),
        "threshold": int(threshold),
        "group_count": len(groups),
        "groups": groups,
    }


# ---------------------------------------------------------------------------
# collection_stats
# ---------------------------------------------------------------------------


def collection_stats(folder: str, *, recursive: bool = False) -> dict[str, Any]:
    """Summarise a folder's ratings, favourites, colour labels and cull states.

    Returns total / rated / unrated counts, a 0-5 star distribution and
    average, favourite count, a colour-label tally and a pick/reject/unflagged
    cull tally. Reads ratings and labels from the user's settings and cull
    states from the library index.
    """
    base = _validated_dir(folder)
    iterator = base.rglob("*") if recursive else base.iterdir()
    paths = sorted(
        str(p) for p in iterator
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    from Imervue.library.collection_stats import summarize
    return {"folder": str(base), **summarize(paths)}


# ---------------------------------------------------------------------------
# apply_watermark
# ---------------------------------------------------------------------------


def _validated_rgb_triplet(
    color: Any, default: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Coerce a JSON ``[r, g, b]`` array into a clamped uint8 RGB tuple."""
    if color is None:
        return default
    if (not isinstance(color, (list, tuple)) or len(color) != 3
            or not all(isinstance(c, int) for c in color)):
        raise ValueError("color must be a list of three integers 0-255")
    return tuple(max(0, min(_RGB_MAX, int(c))) for c in color)


def _save_image_to(dst: Path, img: Any) -> None:
    """Save a PIL image to ``dst``, flattening alpha for formats lacking it."""
    fmt = dst.suffix.lower().lstrip(".")
    to_save = img.convert("RGB") if fmt in _NO_ALPHA_FORMATS else img
    to_save.save(dst)


def apply_watermark(
    source: str,
    destination: str,
    text: str,
    *,
    corner: str = "bottom-right",
    opacity: float = 0.6,
    font_fraction: float = 0.035,
    color: list[int] | None = None,
    shadow: bool = True,
) -> dict[str, Any]:
    """Render a text watermark onto ``source`` and save it to ``destination``.

    The destination format is taken from its suffix; formats that can't carry
    alpha (JPEG / BMP) are flattened to RGB first. Returns the destination
    path, its size in bytes and the corner used.
    """
    src = _validated_file(source)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if corner not in _WATERMARK_CORNERS:
        raise ValueError(
            f"corner must be one of {sorted(_WATERMARK_CORNERS)}, got {corner!r}",
        )
    dst = _validated_destination(destination)
    rgb = _validated_rgb_triplet(color, _DEFAULT_WATERMARK_COLOR)
    from PIL import Image
    from Imervue.image.watermark import WatermarkOptions
    from Imervue.image.watermark import apply_watermark as _apply
    opts = WatermarkOptions(
        text=text, corner=corner, opacity=float(opacity),
        font_fraction=float(font_fraction), color=rgb, shadow=bool(shadow),
    )
    with Image.open(src) as opened:
        _save_image_to(dst, _apply(opened, opts))
    return {
        "source": str(src),
        "destination": str(dst),
        "size_bytes": int(dst.stat().st_size),
        "corner": corner,
    }


# ---------------------------------------------------------------------------
# apply_frame
# ---------------------------------------------------------------------------


def apply_frame(
    source: str,
    destination: str,
    *,
    border: int = 40,
    color: list[int] | None = None,
    bottom_extra: int = 0,
    caption: str = "",
    text_color: list[int] | None = None,
) -> dict[str, Any]:
    """Wrap an image in a matte border (+ optional caption) and save it.

    ``border`` is the matte width in pixels, ``bottom_extra`` adds a thicker
    Polaroid-style bottom band, and ``caption`` is burned into that band.
    The destination format follows its suffix. Returns the destination path,
    its size in bytes and the framed dimensions.
    """
    src = _validated_file(source)
    dst = _validated_destination(destination)
    frame_rgb = _validated_rgb_triplet(color, _DEFAULT_WATERMARK_COLOR)
    text_rgb = _validated_rgb_triplet(text_color, _DEFAULT_FRAME_TEXT_COLOR)
    from PIL import Image
    from Imervue.image.photo_frame import FrameOptions, add_frame
    opts = FrameOptions(
        border=max(0, int(border)), color=frame_rgb,
        bottom_extra=max(0, int(bottom_extra)),
        caption=str(caption), text_color=text_rgb,
    )
    framed = add_frame(_load_rgba_array(src), opts)
    with Image.fromarray(framed, "RGBA") as out:
        _save_image_to(dst, out)
    height, width = framed.shape[:2]
    return {
        "source": str(src),
        "destination": str(dst),
        "size_bytes": int(dst.stat().st_size),
        "width": int(width),
        "height": int(height),
    }


def _validated_destination(destination: str) -> Path:
    """Return the destination Path, requiring its parent directory to exist."""
    dst = Path(destination)
    if not dst.parent.exists():
        raise ValueError(f"destination parent {dst.parent} does not exist")
    return dst


# ---------------------------------------------------------------------------
# build_collage
# ---------------------------------------------------------------------------

_COLLAGE_MAX_IMAGES = 200


def build_collage(
    sources: list[str],
    destination: str,
    *,
    columns: int = 3,
    cell_width: int = 400,
    cell_height: int = 400,
    gap: int = 12,
    margin: int = 20,
    background: list[int] | None = None,
    progress: Any = None,
) -> dict[str, Any]:
    """Composite several images into a grid montage and save it.

    Each source is letterboxed and centred in an equal ``cell_width`` x
    ``cell_height`` cell; ``gap`` separates cells and ``margin`` frames the
    grid. The destination format follows its suffix. Returns the destination
    path, image count, column count, output dimensions and size in bytes.

    ``progress`` is an optional reporter injected by the server when the
    caller passes a progressToken; each loaded source advances it.
    """
    if not isinstance(sources, (list, tuple)) or not sources:
        raise ValueError("sources must be a non-empty list of image paths")
    if len(sources) > _COLLAGE_MAX_IMAGES:
        raise ValueError(f"collage supports at most {_COLLAGE_MAX_IMAGES} images")
    dst = _validated_destination(destination)
    rgb = _validated_rgb_triplet(background, _DEFAULT_WATERMARK_COLOR)
    total = len(sources)
    arrays = []
    for index, src in enumerate(sources, start=1):
        arrays.append(_load_rgba_array(_validated_file(src)))
        if progress is not None:
            progress.report(index, total=total, message=f"loaded {index}/{total}")
    cols = max(1, int(columns))
    from PIL import Image
    from Imervue.image.collage import build_collage as _build
    collage = _build(
        arrays, cols,
        cell=(max(1, int(cell_width)), max(1, int(cell_height))),
        gap=max(0, int(gap)), margin=max(0, int(margin)), background=rgb,
    )
    with Image.fromarray(collage, "RGBA") as out:
        _save_image_to(dst, out)
    height, width = collage.shape[:2]
    return {
        "destination": str(dst),
        "image_count": len(arrays),
        "columns": cols,
        "width": int(width),
        "height": int(height),
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# crop_image
# ---------------------------------------------------------------------------


def crop_image(
    source: str,
    destination: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Crop a rectangular region out of an image and save it.

    ``x`` / ``y`` are the top-left corner and ``width`` / ``height`` the box
    size, all in source pixels. The box must lie fully inside the image. The
    destination format follows its suffix. Returns the destination path, the
    cropped dimensions and the size in bytes.
    """
    src = _validated_file(source)
    dst = _validated_destination(destination)
    left, top = int(x), int(y)
    box_w, box_h = int(width), int(height)
    if box_w <= 0 or box_h <= 0:
        raise ValueError("width and height must be positive")
    if left < 0 or top < 0:
        raise ValueError("x and y must be non-negative")
    from PIL import Image
    with Image.open(src) as opened:
        img_w, img_h = opened.size
        if left + box_w > img_w or top + box_h > img_h:
            raise ValueError(
                f"crop box ({left},{top},{box_w}x{box_h}) exceeds "
                f"image {img_w}x{img_h}",
            )
        _save_image_to(dst, opened.crop((left, top, left + box_w, top + box_h)))
    return {
        "source": str(src),
        "destination": str(dst),
        "width": box_w,
        "height": box_h,
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# resize_image
# ---------------------------------------------------------------------------


def _resize_dims(
    src_w: int, src_h: int, width: int | None, height: int | None,
) -> tuple[int, int]:
    """Resolve a resize target, preserving aspect when one edge is omitted."""
    if width is not None and height is not None:
        return (width, height)
    if width is not None:
        return (width, max(1, round(src_h * (width / src_w))))
    return (max(1, round(src_w * (height / src_h))), height)


def resize_image(
    source: str,
    destination: str,
    *,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Resize an image and save it.

    Pass both ``width`` and ``height`` for an exact resize, or just one to
    scale the other proportionally. The destination format follows its
    suffix. Returns the destination path, the new dimensions and size in bytes.
    """
    src = _validated_file(source)
    dst = _validated_destination(destination)
    target_w = None if width is None else int(width)
    target_h = None if height is None else int(height)
    if target_w is None and target_h is None:
        raise ValueError("at least one of width or height is required")
    if (target_w is not None and target_w <= 0) or (
        target_h is not None and target_h <= 0
    ):
        raise ValueError("width and height must be positive")
    from PIL import Image
    with Image.open(src) as opened:
        src_w, src_h = opened.size
        target = _resize_dims(src_w, src_h, target_w, target_h)
        _save_image_to(dst, opened.resize(target, Image.Resampling.LANCZOS))
    return {
        "source": str(src),
        "destination": str(dst),
        "width": target[0],
        "height": target[1],
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# rotate_image
# ---------------------------------------------------------------------------

# Operation name -> PIL transpose attribute. Rotations are clockwise; PIL's
# ROTATE_n constants are counter-clockwise, hence the 90/270 swap.
_ROTATE_OPERATIONS: dict[str, str] = {
    "rotate_90": "ROTATE_270",
    "rotate_180": "ROTATE_180",
    "rotate_270": "ROTATE_90",
    "flip_horizontal": "FLIP_LEFT_RIGHT",
    "flip_vertical": "FLIP_TOP_BOTTOM",
}


def rotate_image(source: str, destination: str, operation: str) -> dict[str, Any]:
    """Rotate (clockwise) or flip an image by a fixed operation and save it.

    ``operation`` is one of ``rotate_90`` / ``rotate_180`` / ``rotate_270`` /
    ``flip_horizontal`` / ``flip_vertical``. These are lossless orientation
    changes. The destination format follows its suffix. Returns the
    destination path, the operation, the resulting dimensions and size.
    """
    src = _validated_file(source)
    dst = _validated_destination(destination)
    transpose_name = _ROTATE_OPERATIONS.get(operation)
    if transpose_name is None:
        raise ValueError(
            f"operation must be one of {sorted(_ROTATE_OPERATIONS)}, "
            f"got {operation!r}",
        )
    from PIL import Image
    with Image.open(src) as opened:
        result = opened.transpose(getattr(Image.Transpose, transpose_name))
        width, height = result.size
        _save_image_to(dst, result)
    return {
        "source": str(src),
        "destination": str(dst),
        "operation": operation,
        "width": int(width),
        "height": int(height),
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_images",
        "description": (
            "List image files in a folder. Returns each entry's path, "
            "size in bytes, and mtime. Pass recursive=true to walk subfolders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Directory to list."},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder"],
        },
        "handler": list_images,
    },
    {
        "name": "read_image_metadata",
        "description": (
            "Read dimensions, format, EXIF, and XMP sidecar fields for one image."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the image."},
            },
            "required": ["path"],
        },
        "handler": read_image_metadata,
    },
    {
        "name": "read_xmp_tags",
        "description": "Return only the XMP sidecar tags / rating / label for an image.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": read_xmp_tags,
    },
    {
        "name": "convert_format",
        "description": (
            "Convert one image to another format. Destination format is taken from "
            "the destination suffix (png / jpg / jpeg / webp / tiff / bmp, plus "
            "heic / avif / jxl when their optional backends are installed)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "quality": {"type": "integer", "minimum": 1, "maximum": 100, "default": 90},
            },
            "required": ["source", "destination"],
        },
        "handler": convert_format,
    },
    {
        "name": "puppet_from_png",
        "description": (
            "Build a .puppet rig from a PNG using the built-in puppet auto-mesh. "
            "Seeds the Cubism-standard parameter catalogue so the rig is "
            "immediately drivable by the puppet input drivers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "cell_size": {"type": "integer", "minimum": 4, "maximum": 1024, "default": 64},
            },
            "required": ["source", "destination"],
        },
        "handler": puppet_from_png,
    },
    {
        "name": "puppet_inspect",
        "description": (
            "Open a .puppet archive and return a structured inventory: "
            "drawables, deformers, parameters, motions, expressions, hit areas, "
            "parts, parameter blends and physics rigs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": puppet_inspect,
    },
    {
        "name": "reverse_geocode",
        "description": (
            "Resolve GPS latitude/longitude to the nearest major city (offline). "
            "Returns a 'City, Country' place name and [city, country] keywords."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
        "handler": reverse_geocode,
    },
    {
        "name": "extract_video_frame",
        "description": (
            "Decode one frame of a video file and save it as an image. The "
            "destination suffix picks the still format. frame_index defaults to 0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "frame_index": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["source", "destination"],
        },
        "handler": extract_video_frame,
    },
    {
        "name": "sharpness_score",
        "description": (
            "Score an image's sharpness via Laplacian variance and flag whether "
            "it is likely blurry. Higher score means sharper."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": sharpness_score,
    },
    {
        "name": "image_statistics",
        "description": (
            "Return per-channel (r/g/b/luma) mean, min, max, std and median for "
            "one image — a quantitative read-out for inspection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": image_statistics,
    },
    {
        "name": "quality_metrics",
        "description": (
            "Return no-reference quality metrics for one image: colourfulness, "
            "tonal entropy, RMS contrast, edge density and a noise-sigma estimate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": quality_metrics,
    },
    {
        "name": "read_histogram",
        "description": (
            "Return the 256-bin per-channel (r/g/b/luma) histogram and the "
            "over/under exposure-clipping fractions for one image."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": read_histogram,
    },
    {
        "name": "ocr_text",
        "description": (
            "Extract text from an image via Tesseract OCR. Returns available=false "
            "(not an error) when the optional backend is missing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "min_confidence": {"type": "number", "default": 0.0},
            },
            "required": ["path"],
        },
        "handler": ocr_text,
    },
    {
        "name": "image_thumbnail",
        "description": (
            "Return a downscaled PNG preview of an image as a base64 data URI. "
            "max_size bounds the long edge (default 256, capped at 512)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_size": {"type": "integer", "minimum": 16, "maximum": 512, "default": 256},
            },
            "required": ["path"],
        },
        "handler": image_thumbnail,
    },
    {
        "name": "find_similar",
        "description": (
            "Group near-duplicate images in a folder by perceptual (dHash) "
            "similarity. threshold is the max Hamming distance (default 5); set "
            "recursive=true to walk subfolders. Returns groups of size > 1."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "threshold": {"type": "integer", "minimum": 0, "maximum": 32, "default": 5},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder"],
        },
        "handler": find_similar,
    },
    {
        "name": "collection_stats",
        "description": (
            "Summarise a folder's images: total / rated / unrated counts, a 0-5 "
            "star distribution and average, favourite count, a colour-label "
            "tally and a pick/reject/unflagged cull tally. Set recursive=true to "
            "walk subfolders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder"],
        },
        "handler": collection_stats,
    },
    {
        "name": "apply_watermark",
        "description": (
            "Render a text watermark onto an image and save it to a destination "
            "path. corner is one of top-left / top-right / bottom-left / "
            "bottom-right / center; opacity and font_fraction are 0..1 fractions; "
            "color is an [r, g, b] triplet. The destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "text": {"type": "string", "description": "Watermark text (non-empty)."},
                "corner": {
                    "type": "string",
                    "enum": ["top-left", "top-right", "bottom-left",
                             "bottom-right", "center"],
                    "default": "bottom-right",
                },
                "opacity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.6},
                "font_fraction": {
                    "type": "number", "minimum": 0.005, "maximum": 0.2, "default": 0.035,
                },
                "color": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [255, 255, 255],
                },
                "shadow": {"type": "boolean", "default": True},
            },
            "required": ["source", "destination", "text"],
        },
        "handler": apply_watermark,
    },
    {
        "name": "apply_frame",
        "description": (
            "Wrap an image in a coloured matte border and save it to a "
            "destination path. border is the matte width in pixels; bottom_extra "
            "adds a thicker Polaroid-style bottom band; caption is burned into "
            "that band. color and text_color are [r, g, b] triplets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "border": {"type": "integer", "minimum": 0, "default": 40},
                "color": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [255, 255, 255],
                },
                "bottom_extra": {"type": "integer", "minimum": 0, "default": 0},
                "caption": {"type": "string", "default": ""},
                "text_color": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [40, 40, 40],
                },
            },
            "required": ["source", "destination"],
        },
        "handler": apply_frame,
    },
    {
        "name": "build_collage",
        "description": (
            "Composite several images into a grid montage and save it. Each "
            "source is letterboxed into an equal cell_width x cell_height cell; "
            "columns sets the grid width, gap separates cells and margin frames "
            "the grid. background is an [r, g, b] triplet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array", "items": {"type": "string"}, "minItems": 1,
                },
                "destination": {"type": "string"},
                "columns": {"type": "integer", "minimum": 1, "default": 3},
                "cell_width": {"type": "integer", "minimum": 1, "default": 400},
                "cell_height": {"type": "integer", "minimum": 1, "default": 400},
                "gap": {"type": "integer", "minimum": 0, "default": 12},
                "margin": {"type": "integer", "minimum": 0, "default": 20},
                "background": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 3, "maxItems": 3, "default": [255, 255, 255],
                },
            },
            "required": ["sources", "destination"],
        },
        "handler": build_collage,
    },
    {
        "name": "crop_image",
        "description": (
            "Crop a rectangular region out of an image and save it. x / y are "
            "the top-left corner and width / height the box size, all in source "
            "pixels; the box must lie fully inside the image. The destination "
            "format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "x": {"type": "integer", "minimum": 0},
                "y": {"type": "integer", "minimum": 0},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
            "required": ["source", "destination", "x", "y", "width", "height"],
        },
        "handler": crop_image,
    },
    {
        "name": "resize_image",
        "description": (
            "Resize an image and save it. Pass both width and height for an "
            "exact resize, or just one to scale the other proportionally. The "
            "destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
            "required": ["source", "destination"],
        },
        "handler": resize_image,
    },
    {
        "name": "rotate_image",
        "description": (
            "Rotate (clockwise) or flip an image by a fixed, lossless operation "
            "and save it. operation is one of rotate_90 / rotate_180 / "
            "rotate_270 / flip_horizontal / flip_vertical. The destination "
            "format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": ["rotate_90", "rotate_180", "rotate_270",
                             "flip_horizontal", "flip_vertical"],
                },
            },
            "required": ["source", "destination", "operation"],
        },
        "handler": rotate_image,
    },
]


def register_default_tools(server: MCPServer) -> None:
    """Register every tool in :data:`_TOOL_DEFINITIONS` onto ``server``.

    Called once from :func:`Imervue.mcp_server.server.run` and from
    tests that want the default tool set. Tests that want to register
    a custom subset should drop straight into ``server.register``
    instead of using this helper. Output schemas and annotations are
    pulled from :data:`Imervue.mcp_server.tool_schemas.TOOL_METADATA`."""
    from Imervue.mcp_server.tool_schemas import TOOL_METADATA
    for entry in _TOOL_DEFINITIONS:
        meta = TOOL_METADATA.get(entry["name"], {})
        server.register(
            name=entry["name"],
            description=entry["description"],
            input_schema=entry["input_schema"],
            handler=entry["handler"],
            output_schema=meta.get("output_schema"),
            annotations=meta.get("annotations"),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validated_dir(path: str) -> Path:
    if not isinstance(path, str) or not path:
        raise ValueError("folder must be a non-empty string")
    candidate = Path(path).expanduser()
    if not candidate.is_dir():
        raise ValueError(f"folder {candidate} does not exist")
    return candidate


def _validated_file(path: str) -> Path:
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise ValueError(f"file {candidate} does not exist")
    return candidate


def _json_safe(value: Any) -> Any:
    """Coerce EXIF / Pillow values into JSON-serialisable forms.

    Bytes become hex (so the client can still see the data without
    binary-in-JSON issues); IFDRational becomes a float; tuples become
    lists; everything else falls back to ``str(value)``."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    # PIL's IFDRational / Fraction exposes numerator / denominator.
    num = getattr(value, "numerator", None)
    den = getattr(value, "denominator", None)
    if num is not None and den:
        return float(num) / float(den)
    return str(value)


