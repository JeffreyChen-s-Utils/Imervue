"""Read-side MCP tool handlers: listing, metadata, analysis, search, conversion.

Every handler takes plain JSON arguments and returns a JSON-serialisable
dict. Registered through :data:`Imervue.mcp_server.tool_defs_read.READ_TOOL_DEFINITIONS`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from Imervue.mcp_server.tool_support import (
    IMAGE_EXTENSIONS,
    NO_ALPHA_FORMATS,
    json_safe,
    load_rgba_array,
    open_upright,
    validated_dir,
    validated_file,
)

_CONVERTIBLE_FORMATS: frozenset[str] = frozenset({
    "png", "jpeg", "jpg", "webp", "tiff", "tif", "bmp",
})
# Optional-backend output formats, routed through save_formats (HEIF / JXL).
_EXTRA_FORMAT_NAMES: dict[str, str] = {"heic": "HEIC", "avif": "AVIF", "jxl": "JXL"}
_SHARPNESS_MAX_SIDE = 512


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
    base = validated_dir(folder)
    iterator = base.rglob("*") if recursive else base.iterdir()
    entries: list[dict[str, Any]] = []
    for path in iterator:
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
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
    image_path = validated_file(path)
    out: dict[str, Any] = {"path": str(image_path)}
    _populate_basic_image_info(image_path, out)
    _populate_exif(image_path, out)
    _populate_xmp(image_path, out)
    return out


def _populate_basic_image_info(image_path: Path, out: dict[str, Any]) -> None:
    from PIL import Image

    from Imervue.image.orientation import QUARTER_TURN_CODES, exif_orientation
    from Imervue.image.read_errors import IMAGE_READ_ERRORS
    try:
        with Image.open(image_path) as img:
            # The upright size the other tools (crop, resize, …) work in.
            width, height = img.size
            if exif_orientation(img) in QUARTER_TURN_CODES:
                width, height = height, width
            out["width"] = int(width)
            out["height"] = int(height)
            out["format"] = img.format or ""
            out["mode"] = img.mode
    except IMAGE_READ_ERRORS as exc:
        out["error"] = f"image probe failed: {exc}"


def _populate_exif(image_path: Path, out: dict[str, Any]) -> None:
    from Imervue.image.info import get_exif_data
    exif = get_exif_data(image_path) or {}   # {} for an unreadable file or EXIF block
    # EXIF values include byte strings / IFDRational; coerce to JSON-friendly types.
    out["exif"] = {str(k): json_safe(v) for k, v in exif.items()}


def _populate_xmp(image_path: Path, out: dict[str, Any]) -> None:
    from Imervue.image import xmp_sidecar
    xmp = xmp_sidecar.load(image_path)   # empty XmpData for a missing or malformed sidecar
    out["xmp"] = {
        "rating": int(xmp.rating),
        "title": xmp.title,
        "description": xmp.description,
        "keywords": list(xmp.keywords),
        "color_label": xmp.color_label,
    }


# ---------------------------------------------------------------------------
# read_xmp_tags
# ---------------------------------------------------------------------------


def read_xmp_tags(path: str) -> dict[str, Any]:
    """Return only the XMP sidecar fields for ``path`` — handy when
    the caller wants tags / rating without paying the EXIF parse."""
    image_path = validated_file(path)
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
    src = validated_file(source)
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
    with open_upright(src) as opened:
        save_kwargs: dict[str, Any] = {}
        normalised = "jpeg" if fmt in {"jpg", "jpeg"} else fmt
        if normalised in {"jpeg", "webp"}:
            save_kwargs["quality"] = max(1, min(100, int(quality)))
        # JPEG / BMP can't carry alpha, and JPEG also can't write palette
        # ("P") or 1-bit modes — a GIF or paletted PNG source would raise
        # "cannot write mode P as JPEG" mid-save. Flatten anything that
        # isn't already a directly-writable RGB/greyscale buffer, mirroring
        # _save_image_to. Keep the converted handle under a separate name so
        # we don't clobber the ``with`` binding.
        needs_flatten = fmt in NO_ALPHA_FORMATS and opened.mode not in {
            "RGB", "L",
        }
        to_save = opened.convert("RGB") if needs_flatten else opened
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
    src = validated_file(source)
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
    src = validated_file(path)
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
    from Imervue.image.save_formats import save_image
    with open_upright(src) as opened:
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
    src = validated_file(source)
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
    from Imervue.image.sharpness import DEFAULT_BLUR_THRESHOLD
    from Imervue.image.sharpness import sharpness_score as _score
    img_path = validated_file(path)
    with open_upright(img_path) as opened:
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




def image_statistics(path: str) -> dict[str, Any]:
    """Return per-channel (r/g/b/luma) mean, min, max, std and median."""
    img_path = validated_file(path)
    from Imervue.image.statistics import image_statistics as _stats
    stats = _stats(load_rgba_array(img_path))
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
    img_path = validated_file(path)
    from Imervue.image.quality_metrics import quality_metrics as _metrics
    metrics = {k: round(v, 3) for k, v in _metrics(load_rgba_array(img_path)).items()}
    return {"path": str(img_path), "metrics": metrics}


# ---------------------------------------------------------------------------
# read_histogram
# ---------------------------------------------------------------------------


def read_histogram(path: str) -> dict[str, Any]:
    """Return the 256-bin per-channel histogram and exposure-clipping fractions."""
    img_path = validated_file(path)
    from Imervue.image.histogram import compute_clipping, compute_histogram
    arr = load_rgba_array(img_path)
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
    img_path = validated_file(path)
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
    img_path = validated_file(path)
    box = max(16, min(_THUMB_MAX, int(max_size)))
    with open_upright(img_path) as opened:
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
    base = validated_dir(folder)
    iterator = base.rglob("*") if recursive else base.iterdir()
    paths = [
        str(p) for p in iterator
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
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
    base = validated_dir(folder)
    iterator = base.rglob("*") if recursive else base.iterdir()
    paths = sorted(
        str(p) for p in iterator
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
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
    img_path = validated_file(path)
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
    img_path = validated_file(path)
    count = max(PALETTE_MIN, min(PALETTE_MAX, int(n_colors)))
    palette = extract_palette(load_rgba_array(img_path), n_colors=count)
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
    img_path = validated_file(path)
    ela_rgba = _ela(load_rgba_array(img_path), int(quality), int(scale))
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
    base = validated_dir(folder)
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
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )
    matches = apply_to_paths(paths, rules)
    return {
        "folder": str(base), "query": query,
        "count": len(matches), "matches": matches,
    }
