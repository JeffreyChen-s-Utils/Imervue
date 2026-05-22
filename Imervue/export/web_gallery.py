"""
Standalone static-HTML gallery generator.

Produces a self-contained folder with ``index.html``, a ``thumbs/`` directory
of JPEG thumbnails, and either copies or references the originals. The output
has no external JS / CSS dependencies — it is a single HTML file with inline
styling and a tiny inline lightbox script so users can host it anywhere.
"""
from __future__ import annotations

import html
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

logger = logging.getLogger("Imervue.export.web_gallery")


@dataclass(frozen=True)
class WebGalleryOptions:
    thumb_max_side: int = 400
    copy_originals: bool = True
    title: str = "Imervue Gallery"
    thumbnail_quality: int = 85
    review_mode: bool = False
    """When True, each tile carries a comment textarea persisted in
    the browser's ``localStorage`` (keyed by image filename) plus a
    page-level Export Comments button that downloads every comment
    as a JSON file. Reviewers run the gallery locally or behind any
    static-file host; no server / database / build step required."""


def review_comments_key(gallery_title: str) -> str:
    """The ``localStorage`` namespace under which a single gallery's
    comments are stored. Stable across reloads of the same generated
    page; distinct per title so two galleries on the same origin
    don't collide. Pure helper so callers / tests can synthesise the
    same key without parsing the generated HTML."""
    safe = "".join(c if c.isalnum() else "_" for c in (gallery_title or "gallery"))
    return f"imervue_review_{safe}"


def _make_thumbnail(src: str, dest: Path, max_side: int, quality: int) -> bool:
    """Write a JPEG thumbnail of ``src`` to ``dest``. Returns success flag."""
    img = QImage(src)
    if img.isNull():
        return False
    if max(img.width(), img.height()) > max_side:
        img = img.scaled(
            max_side, max_side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    return img.save(str(dest), "JPEG", quality)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>{title}</title>
<style>
body {{ font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 16px; }}
h1 {{ font-size: 1.4rem; margin: 0 0 16px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
.tile {{ background: #222; border-radius: 4px; overflow: hidden; }}
.tile img {{ width: 100%; height: 200px; object-fit: cover; display: block; cursor: pointer; }}
.caption {{ padding: 6px 8px; font-size: 0.8rem; color: #bbb; word-break: break-all; }}
.review {{ padding: 4px 8px 8px; }}
.review textarea {{ width: 100%; min-height: 50px; box-sizing: border-box; padding: 4px;
    background: #1a1a1a; color: #ddd; border: 1px solid #333; border-radius: 3px;
    font-family: inherit; font-size: 0.8rem; resize: vertical; }}
#review-bar {{ margin-bottom: 12px; display: flex; gap: 8px; align-items: center; }}
#review-bar button {{ padding: 6px 12px; background: #2a4; color: #fff; border: 0;
    border-radius: 3px; cursor: pointer; font-size: 0.85rem; }}
#review-bar button:hover {{ background: #3b5; }}
#review-bar .count {{ color: #888; font-size: 0.85rem; }}
#lightbox {{ position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: none;
    align-items: center; justify-content: center; z-index: 10; }}
#lightbox img {{ max-width: 96vw; max-height: 96vh; box-shadow: 0 0 40px #000; }}
#lightbox.open {{ display: flex; }}
</style>
</head>
<body>
<h1>{title}</h1>
{review_bar}
<div class=\"grid\">
{tiles}
</div>
<div id=\"lightbox\" onclick=\"this.classList.remove('open')\">
    <img id=\"lightbox-img\" alt=\"\">
</div>
<script>
document.querySelectorAll('.tile img').forEach(function(img) {{
    img.addEventListener('click', function() {{
        var box = document.getElementById('lightbox-img');
        box.src = img.parentElement.getAttribute('data-full');
        document.getElementById('lightbox').classList.add('open');
    }});
}});
{review_script}
</script>
</body>
</html>
"""

_REVIEW_BAR_HTML = """<div id=\"review-bar\">
<button id=\"export-comments\">Export comments (JSON)</button>
<span class=\"count\" id=\"comment-count\">0 comments</span>
</div>"""

_REVIEW_SCRIPT_TEMPLATE = """
var REVIEW_KEY = {key_json};
function loadComments() {{
    try {{ return JSON.parse(localStorage.getItem(REVIEW_KEY) || '{{}}') || {{}}; }}
    catch (_e) {{ return {{}}; }}
}}
function saveComments(data) {{
    localStorage.setItem(REVIEW_KEY, JSON.stringify(data));
    var count = Object.values(data).filter(function(v) {{ return v && v.length; }}).length;
    var el = document.getElementById('comment-count');
    if (el) el.textContent = count + ' comment' + (count === 1 ? '' : 's');
}}
(function() {{
    var data = loadComments();
    document.querySelectorAll('.review textarea').forEach(function(ta) {{
        var key = ta.getAttribute('data-key');
        if (data[key]) ta.value = data[key];
        ta.addEventListener('input', function() {{
            var d = loadComments();
            if (ta.value) d[key] = ta.value; else delete d[key];
            saveComments(d);
        }});
    }});
    saveComments(data);
    var exportBtn = document.getElementById('export-comments');
    if (exportBtn) {{
        exportBtn.addEventListener('click', function() {{
            var blob = new Blob(
                [JSON.stringify(loadComments(), null, 2)],
                {{type: 'application/json'}}
            );
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = REVIEW_KEY + '.json';
            a.click();
            URL.revokeObjectURL(url);
        }});
    }}
}})();
"""


def _build_tile_html(
    thumb_rel: str,
    full_rel: str,
    caption: str,
    *,
    review_key: str | None = None,
) -> str:
    """Render one tile. When ``review_key`` is set, append a
    per-image comment textarea keyed by that string — the review
    script wires its value to localStorage on input."""
    parts = [
        f'<div class="tile" data-full="{html.escape(full_rel, quote=True)}">',
        f'<img src="{html.escape(thumb_rel, quote=True)}" '
        f'alt="{html.escape(caption)}">',
        f'<div class="caption">{html.escape(caption)}</div>',
    ]
    if review_key is not None:
        parts.append(
            f'<div class="review"><textarea '
            f'data-key="{html.escape(review_key, quote=True)}" '
            f'placeholder="Add a comment…"></textarea></div>',
        )
    parts.append('</div>')
    return "".join(parts)


def _build_review_script(comments_key: str) -> str:
    """Build the per-page review JavaScript. Pure helper — the
    generator inlines this into the HTML template and tests can
    inspect the rendered key without parsing markup."""
    import json as _json
    return _REVIEW_SCRIPT_TEMPLATE.format(key_json=_json.dumps(comments_key))


def _place_original(src: Path, output_dir: Path, copy: bool) -> str:
    """Return the href to use for the full-size image (relative if possible)."""
    if copy:
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        dest = images_dir / src.name
        # Suffix disambiguation when multiple sources share a filename.
        counter = 1
        while dest.exists():
            dest = images_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1
        shutil.copy2(src, dest)
        return f"images/{dest.name}"
    # Reference original absolute path — only useful for local viewing.
    return src.as_uri()


def generate_web_gallery(
    images: list[str],
    output_dir: str | Path,
    opts: WebGalleryOptions | None = None,
) -> Path:
    """Render ``images`` into a self-contained gallery at ``output_dir``."""
    if not images:
        raise ValueError("generate_web_gallery requires at least one image")
    options = opts or WebGalleryOptions()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir = out_dir / "thumbs"
    thumbs_dir.mkdir(exist_ok=True)

    tiles_html: list[str] = []
    for idx, path_str in enumerate(images):
        src = Path(path_str)
        if not src.is_file():
            logger.warning("Skipping missing image: %s", src)
            continue
        thumb_name = f"thumb_{idx:05d}_{src.stem}.jpg"
        thumb_path = thumbs_dir / thumb_name
        if not _make_thumbnail(
            str(src), thumb_path, options.thumb_max_side, options.thumbnail_quality,
        ):
            logger.warning("Thumbnail failed: %s", src)
            continue
        full_href = _place_original(src, out_dir, options.copy_originals)
        tiles_html.append(_build_tile_html(
            thumb_rel=f"thumbs/{thumb_name}",
            full_rel=full_href,
            caption=src.name,
            review_key=src.name if options.review_mode else None,
        ))

    review_bar = _REVIEW_BAR_HTML if options.review_mode else ""
    review_script = (
        _build_review_script(review_comments_key(options.title))
        if options.review_mode
        else ""
    )
    index_html = _HTML_TEMPLATE.format(
        title=html.escape(options.title),
        review_bar=review_bar,
        tiles="\n".join(tiles_html),
        review_script=review_script,
    )
    index_path = out_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    logger.info("Web gallery written: %s", index_path)
    return index_path
