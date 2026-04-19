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
.tile {{ background: #222; border-radius: 4px; overflow: hidden; cursor: pointer; }}
.tile img {{ width: 100%; height: 200px; object-fit: cover; display: block; }}
.caption {{ padding: 6px 8px; font-size: 0.8rem; color: #bbb; word-break: break-all; }}
#lightbox {{ position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: none;
    align-items: center; justify-content: center; z-index: 10; }}
#lightbox img {{ max-width: 96vw; max-height: 96vh; box-shadow: 0 0 40px #000; }}
#lightbox.open {{ display: flex; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class=\"grid\">
{tiles}
</div>
<div id=\"lightbox\" onclick=\"this.classList.remove('open')\">
    <img id=\"lightbox-img\" alt=\"\">
</div>
<script>
document.querySelectorAll('.tile').forEach(function(tile) {{
    tile.addEventListener('click', function() {{
        var img = document.getElementById('lightbox-img');
        img.src = tile.getAttribute('data-full');
        document.getElementById('lightbox').classList.add('open');
    }});
}});
</script>
</body>
</html>
"""


def _build_tile_html(thumb_rel: str, full_rel: str, caption: str) -> str:
    return (
        f'<div class="tile" data-full="{html.escape(full_rel, quote=True)}">'
        f'<img src="{html.escape(thumb_rel, quote=True)}" alt="{html.escape(caption)}">'
        f'<div class="caption">{html.escape(caption)}</div>'
        f'</div>'
    )


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
        ))

    index_html = _HTML_TEMPLATE.format(
        title=html.escape(options.title),
        tiles="\n".join(tiles_html),
    )
    index_path = out_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    logger.info("Web gallery written: %s", index_path)
    return index_path
