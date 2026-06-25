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

from collections.abc import Callable
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
# extract_gps
# ---------------------------------------------------------------------------


def extract_gps(path: str) -> dict[str, Any]:
    """Read GPS latitude/longitude from an image's EXIF (offline).

    Returns ``has_gps`` plus signed decimal ``latitude`` / ``longitude``
    (positive = N/E), or nulls when the image carries no GPS record. Chain it
    into ``reverse_geocode`` to turn the coordinates into a place name.
    """
    from Imervue.image.gps import extract_gps as _extract
    img_path = _validated_file(path)
    coords = _extract(img_path)
    if coords is None:
        return {
            "path": str(img_path), "has_gps": False,
            "latitude": None, "longitude": None,
        }
    lat, lon = coords
    return {
        "path": str(img_path), "has_gps": True,
        "latitude": lat, "longitude": lon,
    }


# ---------------------------------------------------------------------------
# dominant_colors
# ---------------------------------------------------------------------------


def _color_entry(entry: Any) -> dict[str, Any]:
    r, g, b = entry.color
    return {
        "rgb": [r, g, b],
        "hex": f"#{r:02x}{g:02x}{b:02x}",
        "pixel_count": entry.pixel_count,
    }


def dominant_colors(path: str, n_colors: int = 8) -> dict[str, Any]:
    """Return the image's dominant colour palette (median-cut), dominant first.

    Each entry carries its ``rgb`` triplet, a ``hex`` string and the
    ``pixel_count`` of its bucket. ``n_colors`` is clamped to the palette
    extractor's supported range.
    """
    from Imervue.paint.palette_extract import (
        PALETTE_MAX,
        PALETTE_MIN,
        extract_palette,
    )
    img_path = _validated_file(path)
    count = max(PALETTE_MIN, min(PALETTE_MAX, int(n_colors)))
    palette = extract_palette(_load_rgba_array(img_path), n_colors=count)
    colors = [_color_entry(entry) for entry in palette]
    return {"path": str(img_path), "color_count": len(colors), "colors": colors}


# ---------------------------------------------------------------------------
# error_level_analysis
# ---------------------------------------------------------------------------


def error_level_analysis(
    path: str, quality: int = 90, scale: int = 15,
) -> dict[str, Any]:
    """Return a JPEG-recompression Error-Level-Analysis map as a PNG data URI.

    Regions edited after the last save compress differently and light up
    against the background — a quick tamper / authenticity check. ``quality``
    (1-100) and ``scale`` (amplification) are clamped by the analyser.
    """
    import base64
    import io

    from PIL import Image

    from Imervue.image.ela import error_level_analysis as _ela
    img_path = _validated_file(path)
    ela_rgba = _ela(_load_rgba_array(img_path), int(quality), int(scale))
    height, width = int(ela_rgba.shape[0]), int(ela_rgba.shape[1])
    buffer = io.BytesIO()
    Image.fromarray(ela_rgba, mode="RGBA").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {
        "path": str(img_path),
        "width": width,
        "height": height,
        "data_uri": f"data:image/png;base64,{encoded}",
    }


# ---------------------------------------------------------------------------
# search_images
# ---------------------------------------------------------------------------

# Query fields whose data lives in the running app (user settings / library
# database), so they cannot be evaluated by the standalone MCP server.
_STATEFUL_QUERY_FIELDS = (
    "min_rating", "max_rating", "favorites_only", "color_labels",
    "tags_any", "tags_all", "tags_exclude", "cull",
)


def search_images(
    folder: str, query: str, *, recursive: bool = False,
) -> dict[str, Any]:
    """Search a folder with the smart-album query DSL and return matching paths.

    Parses *query* (e.g. ``ext:png name:sunset width:>1920 aspect:>1.5``) into
    smart-album rules and filters the folder's images. Path, name, size,
    dimension and EXIF (camera / lens / place) filters work fully; rating /
    favourite / colour-label / tag / cull filters depend on the running app's
    settings and library database, so a query using those fields is rejected.
    """
    from Imervue.library.search_query import parse_query
    from Imervue.library.smart_album import apply_to_paths
    base = _validated_dir(folder)
    rules = parse_query(query)
    unsupported = sorted(field for field in _STATEFUL_QUERY_FIELDS if rules.get(field))
    if unsupported:
        raise ValueError(
            "query uses fields unavailable in the standalone server: "
            + ", ".join(unsupported),
        )
    iterator = base.rglob("*") if recursive else base.iterdir()
    paths = sorted(
        str(p) for p in iterator
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    matches = apply_to_paths(paths, rules)
    return {
        "folder": str(base), "query": query,
        "count": len(matches), "matches": matches,
    }


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
# solarize_image
# ---------------------------------------------------------------------------


def _apply_effect_and_save(
    source: str, destination: str, transform: Callable[[Any], Any],
) -> dict[str, Any]:
    """Load *source* as RGBA, run *transform*, save to *destination*, report stats.

    The shared body of every "apply one effect and save a copy" tool: returns the
    source and destination paths, the result dimensions and the file size.
    """
    from PIL import Image

    src = _validated_file(source)
    dst = _validated_destination(destination)
    result = transform(_load_rgba_array(src))
    height, width = int(result.shape[0]), int(result.shape[1])
    _save_image_to(dst, Image.fromarray(result, mode="RGBA"))
    return {
        "source": str(src),
        "destination": str(dst),
        "width": width,
        "height": height,
        "size_bytes": int(dst.stat().st_size),
    }


def solarize_image(
    source: str,
    destination: str,
    *,
    threshold: float = 0.5,
    mix: float = 1.0,
) -> dict[str, Any]:
    """Apply a solarize tone reversal to ``source`` and save it to ``destination``.

    Tones at or above ``threshold`` (0-1) are inverted; ``mix`` (0-1) blends the
    result toward the original.
    """
    from Imervue.image.solarize import apply_solarize
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_solarize(arr, float(threshold), float(mix)),
    )


# ---------------------------------------------------------------------------
# glow_image
# ---------------------------------------------------------------------------


def glow_image(
    source: str,
    destination: str,
    *,
    amount: float = 0.5,
    radius: int = 15,
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Apply a diffuse-glow / Orton bloom to ``source`` and save to ``destination``.

    ``amount`` (0-1) is the glow opacity, ``radius`` the blur radius and
    ``threshold`` (0-1) the brightness above which regions bloom (0 = whole frame).
    """
    from Imervue.image.glow import apply_glow
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_glow(arr, float(amount), int(radius), float(threshold)),
    )


# ---------------------------------------------------------------------------
# tonal / colour effects
# ---------------------------------------------------------------------------


def velvia_image(
    source: str, destination: str, *,
    strength: float = 1.0, luminance_protection: float = 0.5,
) -> dict[str, Any]:
    """Apply a Velvia luminance-weighted saturation boost and save the result."""
    from Imervue.image.velvia import apply_velvia
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_velvia(arr, float(strength), float(luminance_protection)),
    )


def emboss_image(
    source: str, destination: str, *,
    azimuth_deg: float = 135.0, elevation_deg: float = 45.0,
    depth: float = 1.0, grayscale: bool = True,
) -> dict[str, Any]:
    """Apply a directional-light emboss relief and save the result."""
    from Imervue.image.emboss import apply_emboss
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_emboss(
            arr, float(azimuth_deg), float(elevation_deg), float(depth), bool(grayscale),
        ),
    )


def film_negative_image(
    source: str, destination: str, *, gamma: float = 1.0,
) -> dict[str, Any]:
    """Invert a scanned colour negative (auto film base) and save the positive."""
    from Imervue.image.film_negative import apply_film_negative
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_film_negative(arr, None, float(gamma)),
    )


def defringe_image(
    source: str, destination: str, *,
    amount: float = 1.0, edge_threshold: float = 0.1, hue: str = "purple",
) -> dict[str, Any]:
    """Desaturate purple/green chromatic-aberration edge fringes and save the result."""
    from Imervue.image.defringe import apply_defringe
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_defringe(arr, float(amount), float(edge_threshold), str(hue)),
    )


def graduated_density_image(
    source: str, destination: str, *,
    angle_deg: float = 0.0, density_stops: float = 1.0,
    hardness: float = 0.5, offset: float = 0.0,
) -> dict[str, Any]:
    """Apply a linear graduated neutral-density gradient and save the result."""
    from Imervue.image.graduated_density import apply_graduated_density
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_graduated_density(
            arr, float(angle_deg), float(density_stops), float(hardness), float(offset),
        ),
    )


def filmic_tonemap_image(
    source: str, destination: str, *,
    exposure: float = 0.0, white_point: float = 4.0,
    contrast: float = 1.0, saturation: float = 1.0, mode: str = "reinhard",
) -> dict[str, Any]:
    """Apply a filmic (Reinhard/Hable) tone-map highlight rolloff and save the result."""
    from Imervue.image.filmic_tonemap import apply_filmic_tonemap
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_filmic_tonemap(
            arr, float(exposure), float(white_point),
            float(contrast), float(saturation), str(mode),
        ),
    )


_TONE_EQ_DEFAULT = (0.0, 0.0, 0.0, 0.0, 0.0)
_DETAIL_EQ_DEFAULT = (1.0, 1.0, 1.0, 1.0)


def tone_equalizer_image(
    source: str, destination: str, *,
    zone_gains: list[float] | None = None, smoothing: int = 12,
) -> dict[str, Any]:
    """Apply per-luminance-zone exposure (shadows to highlights) and save the result."""
    from Imervue.image.tone_equalizer import apply_tone_equalizer
    gains = tuple(float(g) for g in (zone_gains if zone_gains is not None else _TONE_EQ_DEFAULT))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_tone_equalizer(arr, gains, int(smoothing)),
    )


def detail_equalizer_image(
    source: str, destination: str, *, band_gains: list[float] | None = None,
) -> dict[str, Any]:
    """Re-weight contrast per detail band (finest to coarsest, 1.0 neutral) and save."""
    from Imervue.image.detail_equalizer import apply_detail_equalizer
    gains = tuple(float(g) for g in (band_gains if band_gains is not None else _DETAIL_EQ_DEFAULT))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_detail_equalizer(arr, gains),
    )


# ---------------------------------------------------------------------------
# stylize / artistic effects
# ---------------------------------------------------------------------------


def colormap_image(
    source: str, destination: str, *, name: str = "viridis",
) -> dict[str, Any]:
    """Re-colour ``source`` luminance through a named colour map and save the result."""
    from Imervue.image.colormap import apply_colormap
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_colormap(arr, str(name)),
    )


def false_color_image(source: str, destination: str) -> dict[str, Any]:
    """Map ``source`` luminance to a false-colour exposure scale and save the result."""
    from Imervue.image.false_color import false_color
    return _apply_effect_and_save(source, destination, false_color)


def dither_image(
    source: str, destination: str, *, levels: int = 2,
) -> dict[str, Any]:
    """Ordered-dither ``source`` to ``levels`` tones per channel and save the result."""
    from Imervue.image.dither import ordered_dither
    return _apply_effect_and_save(
        source, destination,
        lambda arr: ordered_dither(arr, int(levels)),
    )


def split_toning_image(
    source: str, destination: str, *,
    shadow_hue: float = 210.0, shadow_saturation: float = 0.0,
    highlight_hue: float = 45.0, highlight_saturation: float = 0.0,
    balance: float = 0.0,
) -> dict[str, Any]:
    """Tint shadows and highlights with separate hues weighted by luminance, then save."""
    from Imervue.image.split_toning import apply_split_toning
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_split_toning(
            arr, float(shadow_hue), float(shadow_saturation),
            float(highlight_hue), float(highlight_saturation), float(balance),
        ),
    )


def pixel_sort_image(
    source: str, destination: str, *,
    lower: int = 60, upper: int = 200, vertical: bool = False,
) -> dict[str, Any]:
    """Sort pixels within brightness bands (``lower``-``upper``) and save the result."""
    from Imervue.image.pixel_sort import pixel_sort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: pixel_sort(arr, int(lower), int(upper), vertical=bool(vertical)),
    )


# ---------------------------------------------------------------------------
# geometric / detail effects
# ---------------------------------------------------------------------------


def polar_image(
    source: str, destination: str, *,
    to_polar: bool = True, invert: bool = False,
) -> dict[str, Any]:
    """Warp ``source`` between rectangular and polar coordinates and save the result."""
    from Imervue.image.polar import polar_distort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: polar_distort(arr, bool(to_polar), bool(invert)),
    )


def kaleidoscope_image(
    source: str, destination: str, *,
    segments: int = 6, angle_deg: float = 0.0,
) -> dict[str, Any]:
    """Mirror ``source`` into ``segments`` kaleidoscope wedges and save the result."""
    import math

    from Imervue.image.kaleidoscope import kaleidoscope
    angle_offset = math.radians(float(angle_deg))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: kaleidoscope(arr, int(segments), None, angle_offset),
    )


def frosted_glass_image(
    source: str, destination: str, *, radius: int = 4, seed: int = 0,
) -> dict[str, Any]:
    """Scatter each pixel to a random neighbour within ``radius`` and save the result."""
    from Imervue.image.frosted_glass import frosted_glass
    return _apply_effect_and_save(
        source, destination,
        lambda arr: frosted_glass(arr, int(radius), int(seed)),
    )


def clahe_image(
    source: str, destination: str, *,
    clip_limit: float = 2.0, tiles: int = 8,
) -> dict[str, Any]:
    """Apply contrast-limited adaptive histogram equalization and save the result."""
    from Imervue.image.clahe import apply_clahe
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_clahe(arr, float(clip_limit), int(tiles)),
    )


def local_contrast_image(
    source: str, destination: str, *,
    clarity: float = 0.0, texture: float = 0.0,
) -> dict[str, Any]:
    """Add midtone clarity and fine-detail texture local contrast, then save."""
    from Imervue.image.local_contrast import apply_clarity, apply_texture
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_texture(apply_clarity(arr, float(clarity)), float(texture)),
    )


# ---------------------------------------------------------------------------
# tone-grading / lens effects
# ---------------------------------------------------------------------------


def posterize_image(
    source: str, destination: str, *, levels: int = 4,
) -> dict[str, Any]:
    """Quantize each channel to ``levels`` discrete steps and save the result."""
    from Imervue.image.posterize import PosterizeOptions, apply_posterize
    options = PosterizeOptions(enabled=True, levels=int(levels))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_posterize(arr, options),
    )


def gradient_map_image(
    source: str, destination: str, *,
    intensity: float = 1.0, perceptual: bool = False,
) -> dict[str, Any]:
    """Map luminance through a black-to-white gradient and save the blended result."""
    from Imervue.image.gradient_map import GradientMapOptions, apply_gradient_map
    options = GradientMapOptions(
        enabled=True, intensity=float(intensity), perceptual=bool(perceptual),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_gradient_map(arr, options),
    )


def film_grain_image(
    source: str, destination: str, *,
    intensity: float = 0.25, size: int = 1,
    monochrome: bool = True, seed: int = 0,
) -> dict[str, Any]:
    """Add tunable Gaussian film grain to the image and save the result."""
    from Imervue.image.film_grain import FilmGrainOptions, apply_film_grain
    options = FilmGrainOptions(
        enabled=True, intensity=float(intensity), size=int(size),
        monochrome=bool(monochrome), seed=int(seed),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_film_grain(arr, options),
    )


def dehaze_image(
    source: str, destination: str, *, strength: float = 0.5,
) -> dict[str, Any]:
    """Remove atmospheric haze (dark-channel prior) by ``strength`` and save."""
    from Imervue.image.dehaze import dehaze
    return _apply_effect_and_save(
        source, destination,
        lambda arr: dehaze(arr, float(strength)),
    )


def distort_image(
    source: str, destination: str, *,
    mode: str = "swirl", strength: float = 0.5,
) -> dict[str, Any]:
    """Warp the image with a swirl, pinch or ripple distortion and save the result."""
    from Imervue.image.distort import distort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: distort(arr, str(mode), float(strength)),
    )


# ---------------------------------------------------------------------------
# colour-grading / curve effects
# ---------------------------------------------------------------------------


def levels_image(
    source: str, destination: str, *,
    black: int = 0, white: int = 255, gamma: float = 1.0,
) -> dict[str, Any]:
    """Remap tones with input black/white points and a gamma, then save."""
    from Imervue.image.levels import LevelsOptions, apply_levels
    options = LevelsOptions(
        enabled=True, black=int(black), white=int(white), gamma=float(gamma),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_levels(arr, options),
    )


def auto_color_balance_image(
    source: str, destination: str, *,
    method: str = "percentile_stretch", intensity: float = 1.0,
    percentile: float = 1.0, retinex_radius: int = 24,
) -> dict[str, Any]:
    """Auto white-balance / colour-cast correction by the chosen method, then save."""
    from Imervue.image.auto_color_balance import AutoBalanceOptions, auto_balance
    options = AutoBalanceOptions(
        method=str(method), intensity=float(intensity),
        percentile=float(percentile), retinex_radius=int(retinex_radius),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: auto_balance(arr, options),
    )


def channel_mixer_image(
    source: str, destination: str, *,
    red: list[float] | None = None, green: list[float] | None = None,
    blue: list[float] | None = None, offsets: list[float] | None = None,
    monochrome: bool = False,
) -> dict[str, Any]:
    """Remix output channels from a 3x3 weight matrix plus offsets, then save."""
    from Imervue.image.channel_mixer import ChannelMixerOptions, apply_channel_mixer
    options = ChannelMixerOptions(
        enabled=True,
        red=[float(v) for v in (red if red is not None else [1.0, 0.0, 0.0])],
        green=[float(v) for v in (green if green is not None else [0.0, 1.0, 0.0])],
        blue=[float(v) for v in (blue if blue is not None else [0.0, 0.0, 1.0])],
        offsets=[float(v) for v in (offsets if offsets is not None else [0.0, 0.0, 0.0])],
        monochrome=bool(monochrome),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_channel_mixer(arr, options),
    )


_CURVE_PRESETS = ("s_curve", "lift_shadows", "compress_highlights")


def _curve_points(preset: str, strength: float):
    """Return the master-curve points for a named preset."""
    from Imervue.image import curves
    builders = {
        "s_curve": curves.s_curve_preset,
        "lift_shadows": curves.lift_shadows_preset,
        "compress_highlights": curves.compress_highlights_preset,
    }
    builder = builders.get(preset)
    if builder is None:
        raise ValueError(
            f"unknown curve preset {preset!r}; expected one of {_CURVE_PRESETS}",
        )
    return builder(strength)


def curve_image(
    source: str, destination: str, *,
    preset: str = "s_curve", strength: float = 0.15,
) -> dict[str, Any]:
    """Apply a tone-curve preset (S-curve, lift shadows, compress highlights), then save."""
    from Imervue.image.curves import CurveOptions, apply_curves
    options = CurveOptions(
        enabled=True, per_channel={"rgb": _curve_points(str(preset), float(strength))},
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_curves(arr, options),
    )


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
        "name": "extract_gps",
        "description": (
            "Read GPS latitude/longitude from an image's EXIF. Returns has_gps "
            "and signed decimal coordinates (null when absent); chain into "
            "reverse_geocode for a place name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": extract_gps,
    },
    {
        "name": "dominant_colors",
        "description": (
            "Extract the dominant colour palette (median-cut), dominant first. "
            "Each colour carries rgb, hex and pixel_count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "n_colors": {
                    "type": "integer", "minimum": 1, "maximum": 64, "default": 8,
                },
            },
            "required": ["path"],
        },
        "handler": dominant_colors,
    },
    {
        "name": "error_level_analysis",
        "description": (
            "Return a JPEG-recompression Error-Level-Analysis map as a PNG data "
            "URI — regions edited after the last save light up against the rest."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "quality": {
                    "type": "integer", "minimum": 1, "maximum": 100, "default": 90,
                },
                "scale": {
                    "type": "integer", "minimum": 1, "maximum": 100, "default": 15,
                },
            },
            "required": ["path"],
        },
        "handler": error_level_analysis,
    },
    {
        "name": "search_images",
        "description": (
            "Search a folder with the smart-album query DSL (e.g. "
            "'ext:png name:sunset width:>1920 aspect:>1.5 size:>2mb camera:canon'). "
            "Returns matching paths. Path/name/size/dimension/EXIF filters work; "
            "rating/favourite/colour/tag/cull fields are rejected as they need "
            "the running app's database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Directory to search."},
                "query": {"type": "string", "description": "Smart-album query DSL."},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["folder", "query"],
        },
        "handler": search_images,
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
    {
        "name": "solarize_image",
        "description": (
            "Apply a solarize tone reversal and save the result. Tones at or "
            "above threshold (0-1) are inverted; mix (0-1) blends back toward "
            "the original. The destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "threshold": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
                "mix": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": solarize_image,
    },
    {
        "name": "glow_image",
        "description": (
            "Apply a diffuse-glow / Orton soft-focus bloom and save the result. "
            "amount (0-1) is the glow opacity, radius the blur size, threshold "
            "(0-1) the brightness above which regions bloom (0 = whole frame). "
            "The destination format follows its suffix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "amount": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
                "radius": {
                    "type": "integer", "minimum": 1, "maximum": 200, "default": 15,
                },
                "threshold": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": glow_image,
    },
    {
        "name": "velvia_image",
        "description": (
            "Apply a Velvia luminance-weighted saturation boost: intensifies "
            "muted colours while sparing already-saturated ones and the shadows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "strength": {
                    "type": "number", "minimum": -1, "maximum": 4, "default": 1.0,
                },
                "luminance_protection": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": velvia_image,
    },
    {
        "name": "emboss_image",
        "description": (
            "Apply a directional-light emboss relief, shading the luminance as a "
            "height field lit from a chosen azimuth and elevation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "azimuth_deg": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 135.0,
                },
                "elevation_deg": {
                    "type": "number", "minimum": 0, "maximum": 90, "default": 45.0,
                },
                "depth": {
                    "type": "number", "minimum": 0, "maximum": 10, "default": 1.0,
                },
                "grayscale": {"type": "boolean", "default": True},
            },
            "required": ["source", "destination"],
        },
        "handler": emboss_image,
    },
    {
        "name": "film_negative_image",
        "description": (
            "Invert a scanned colour negative to a positive, dividing out the "
            "auto-estimated orange film base, with an optional output gamma."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "gamma": {
                    "type": "number", "minimum": 0.1, "maximum": 6, "default": 1.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": film_negative_image,
    },
    {
        "name": "defringe_image",
        "description": (
            "Desaturate purple/green chromatic-aberration fringes on high-contrast "
            "edges, leaving flat colour untouched."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "amount": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
                "edge_threshold": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.1,
                },
                "hue": {
                    "type": "string", "enum": ["purple", "green", "all"],
                    "default": "purple",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": defringe_image,
    },
    {
        "name": "graduated_density_image",
        "description": (
            "Apply a linear graduated neutral-density gradient: darken one side of "
            "the frame along an angled line, by a number of exposure stops."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "angle_deg": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 0.0,
                },
                "density_stops": {
                    "type": "number", "minimum": -8, "maximum": 8, "default": 1.0,
                },
                "hardness": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
                "offset": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": graduated_density_image,
    },
    {
        "name": "filmic_tonemap_image",
        "description": (
            "Apply a filmic Reinhard or Hable tone-map: compress highlights into a "
            "soft rolloff with pivoted contrast and a saturation restore."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "exposure": {
                    "type": "number", "minimum": -6, "maximum": 6, "default": 0.0,
                },
                "white_point": {
                    "type": "number", "minimum": 0.1, "maximum": 64, "default": 4.0,
                },
                "contrast": {
                    "type": "number", "minimum": 0.1, "maximum": 4, "default": 1.0,
                },
                "saturation": {
                    "type": "number", "minimum": 0, "maximum": 4, "default": 1.0,
                },
                "mode": {
                    "type": "string", "enum": ["reinhard", "hable"],
                    "default": "reinhard",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": filmic_tonemap_image,
    },
    {
        "name": "tone_equalizer_image",
        "description": (
            "Apply a tone equalizer: independent exposure per luminance zone "
            "(shadows to highlights, in stops) over a smoothed mask."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "zone_gains": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -4, "maximum": 4},
                    "minItems": 2,
                    "description": "Stop adjustments, shadows to highlights.",
                },
                "smoothing": {
                    "type": "integer", "minimum": 0, "maximum": 50, "default": 12,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": tone_equalizer_image,
    },
    {
        "name": "detail_equalizer_image",
        "description": (
            "Apply a detail equalizer: re-weight contrast per frequency band "
            "(finest to coarsest); a gain of 1.0 is neutral."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "band_gains": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -8, "maximum": 8},
                    "minItems": 1,
                    "description": "Per-band gain, finest to coarsest (1.0 neutral).",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": detail_equalizer_image,
    },
    {
        "name": "colormap_image",
        "description": (
            "Re-colour the image by mapping its luminance through a perceptual "
            "colour map (viridis, magma or jet)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "name": {
                    "type": "string",
                    "enum": ["viridis", "magma", "jet"],
                    "default": "viridis",
                },
            },
            "required": ["source", "destination"],
        },
        "handler": colormap_image,
    },
    {
        "name": "false_color_image",
        "description": (
            "Map luminance to a false-colour exposure scale (blacks through "
            "whites), the way a video monitor flags clipping."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["source", "destination"],
        },
        "handler": false_color_image,
    },
    {
        "name": "dither_image",
        "description": (
            "Ordered (Bayer) dither the image to a small number of tones per "
            "channel, trading colour depth for a retro halftone look."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "levels": {
                    "type": "integer", "minimum": 2, "maximum": 8, "default": 2,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": dither_image,
    },
    {
        "name": "split_toning_image",
        "description": (
            "Tint shadows and highlights with separate hues, weighted by "
            "luminance, with a balance control for the split point."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "shadow_hue": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 210.0,
                },
                "shadow_saturation": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.0,
                },
                "highlight_hue": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 45.0,
                },
                "highlight_saturation": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.0,
                },
                "balance": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": split_toning_image,
    },
    {
        "name": "pixel_sort_image",
        "description": (
            "Pixel-sort the image: reorder pixels by brightness within contiguous "
            "bands bounded by lower/upper thresholds, for a glitch-art smear."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "lower": {
                    "type": "integer", "minimum": 0, "maximum": 255, "default": 60,
                },
                "upper": {
                    "type": "integer", "minimum": 0, "maximum": 255, "default": 200,
                },
                "vertical": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": pixel_sort_image,
    },
    {
        "name": "polar_image",
        "description": (
            "Warp the image between rectangular and polar coordinates: wrap it "
            "into a disc (tiny-planet) or unroll a disc back into a strip."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "to_polar": {"type": "boolean", "default": True},
                "invert": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": polar_image,
    },
    {
        "name": "kaleidoscope_image",
        "description": (
            "Mirror the image into a number of kaleidoscope wedges around the "
            "centre, with an optional rotation of the wedge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "segments": {
                    "type": "integer", "minimum": 2, "maximum": 64, "default": 6,
                },
                "angle_deg": {
                    "type": "number", "minimum": 0, "maximum": 360, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": kaleidoscope_image,
    },
    {
        "name": "frosted_glass_image",
        "description": (
            "Frosted-glass scatter: replace each pixel with a random neighbour "
            "within a radius, for a textured diffusion. The seed is reproducible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "radius": {
                    "type": "integer", "minimum": 0, "maximum": 64, "default": 4,
                },
                "seed": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["source", "destination"],
        },
        "handler": frosted_glass_image,
    },
    {
        "name": "clahe_image",
        "description": (
            "Contrast-limited adaptive histogram equalization: boost local "
            "contrast per tile on the luminance, with a clip limit to cap noise."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "clip_limit": {
                    "type": "number", "minimum": 1, "maximum": 8, "default": 2.0,
                },
                "tiles": {
                    "type": "integer", "minimum": 1, "maximum": 16, "default": 8,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": clahe_image,
    },
    {
        "name": "local_contrast_image",
        "description": (
            "Local contrast: midtone-weighted clarity at a large radius plus "
            "fine-detail texture at a small radius (each -1 to 1, 0 neutral)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "clarity": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
                "texture": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": local_contrast_image,
    },
    {
        "name": "posterize_image",
        "description": (
            "Posterize: quantize each channel to a small number of discrete "
            "levels for a flat, banded poster look."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "levels": {
                    "type": "integer", "minimum": 2, "maximum": 64, "default": 4,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": posterize_image,
    },
    {
        "name": "gradient_map_image",
        "description": (
            "Gradient map: remap luminance through a black-to-white gradient "
            "and blend it over the original by an intensity factor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "intensity": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
                "perceptual": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": gradient_map_image,
    },
    {
        "name": "film_grain_image",
        "description": (
            "Add Gaussian film grain: tunable intensity and clump size, "
            "monochrome or per-channel, with a reproducible seed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "intensity": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.25,
                },
                "size": {
                    "type": "integer", "minimum": 1, "maximum": 8, "default": 1,
                },
                "monochrome": {"type": "boolean", "default": True},
                "seed": {"type": "integer", "minimum": 0, "default": 0},
            },
            "required": ["source", "destination"],
        },
        "handler": film_grain_image,
    },
    {
        "name": "dehaze_image",
        "description": (
            "Dehaze: estimate atmospheric light with a dark-channel prior and "
            "recover contrast and colour through the haze, by a strength factor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "strength": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": dehaze_image,
    },
    {
        "name": "distort_image",
        "description": (
            "Geometric distortion: swirl around the centre, pinch/bulge, or a "
            "sinusoidal ripple. Strength runs -1 to 1 (sign flips the direction)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["swirl", "pinch", "ripple"],
                    "default": "swirl",
                },
                "strength": {
                    "type": "number", "minimum": -1, "maximum": 1, "default": 0.5,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": distort_image,
    },
    {
        "name": "levels_image",
        "description": (
            "Levels: set input black and white points and a midtone gamma to "
            "remap the tonal range. gamma 1.0 is neutral."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "black": {
                    "type": "integer", "minimum": 0, "maximum": 254, "default": 0,
                },
                "white": {
                    "type": "integer", "minimum": 1, "maximum": 255, "default": 255,
                },
                "gamma": {
                    "type": "number", "minimum": 0.1, "maximum": 9.99, "default": 1.0,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": levels_image,
    },
    {
        "name": "auto_color_balance_image",
        "description": (
            "Automatic white-balance / colour-cast correction by gray-world, "
            "white-patch, percentile-stretch or simplified-retinex, blended by "
            "intensity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": [
                        "gray_world", "white_patch",
                        "percentile_stretch", "simplified_retinex",
                    ],
                    "default": "percentile_stretch",
                },
                "intensity": {
                    "type": "number", "minimum": 0, "maximum": 1, "default": 1.0,
                },
                "percentile": {
                    "type": "number", "minimum": 0, "maximum": 10, "default": 1.0,
                },
                "retinex_radius": {
                    "type": "integer", "minimum": 4, "maximum": 64, "default": 24,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": auto_color_balance_image,
    },
    {
        "name": "channel_mixer_image",
        "description": (
            "Channel mixer: build each output channel as a weighted sum of the "
            "input R/G/B plus an offset. Set monochrome to fold all rows into a "
            "tunable black-and-white conversion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "red": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -2, "maximum": 2},
                    "minItems": 3, "maxItems": 3,
                    "description": "Output-red weights [from_r, from_g, from_b].",
                },
                "green": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -2, "maximum": 2},
                    "minItems": 3, "maxItems": 3,
                    "description": "Output-green weights [from_r, from_g, from_b].",
                },
                "blue": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -2, "maximum": 2},
                    "minItems": 3, "maxItems": 3,
                    "description": "Output-blue weights [from_r, from_g, from_b].",
                },
                "offsets": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -1, "maximum": 1},
                    "minItems": 3, "maxItems": 3,
                    "description": "Per-channel constant offset [r, g, b].",
                },
                "monochrome": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        },
        "handler": channel_mixer_image,
    },
    {
        "name": "curve_image",
        "description": (
            "Apply a master tone-curve preset: an S-curve for contrast, lift "
            "shadows for a flat look, or compress highlights to recover detail. "
            "strength scales the preset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "preset": {
                    "type": "string",
                    "enum": ["s_curve", "lift_shadows", "compress_highlights"],
                    "default": "s_curve",
                },
                "strength": {
                    "type": "number", "minimum": 0, "maximum": 0.5, "default": 0.15,
                },
            },
            "required": ["source", "destination"],
        },
        "handler": curve_image,
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


