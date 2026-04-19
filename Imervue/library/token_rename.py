"""
Token-based batch renamer.

Template syntax::

    {name}            original stem
    {ext}             extension including dot
    {counter}         1-based sequence
    {counter:04}      zero-padded counter (any width)
    {date}            yyyy-mm-dd of file mtime
    {date:yyyymmdd}   custom date formatting — strftime tokens allowed
    {width}           pixel width
    {height}          pixel height
    {wxh}             width×height
    {size_kb}         file size in KiB (integer)
    {camera}          EXIF make+model, best-effort
    {year} {month} {day} {hour} {minute}  — mtime components

Unknown tokens are preserved verbatim so the user can see the mistake.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

_TOKEN_RE = re.compile(r"\{([a-zA-Z_]+)(?::([^{}]+))?\}")


@dataclass
class RenamePlan:
    src: str
    dst: str
    conflict: bool = False


def preview(
    paths: list[str],
    template: str,
    *,
    start: int = 1,
) -> list[RenamePlan]:
    """Generate the full rename preview without touching the filesystem."""
    plans: list[RenamePlan] = []
    dest_names: set[str] = set()
    for i, src in enumerate(paths):
        metadata = _gather_metadata(src, start + i)
        new_name = _apply_template(template, metadata)
        parent = str(Path(src).parent)
        dst = str(Path(parent) / new_name)
        conflict = new_name in dest_names or (dst != src and os.path.exists(dst))
        dest_names.add(new_name)
        plans.append(RenamePlan(src=src, dst=dst, conflict=conflict))
    return plans


def apply_plan(plans: list[RenamePlan]) -> tuple[int, int]:
    """Rename everything in the plan. Returns (successes, failures)."""
    ok = failed = 0
    for plan in plans:
        if plan.conflict or plan.src == plan.dst:
            failed += 1
            continue
        try:
            os.rename(plan.src, plan.dst)
            ok += 1
        except OSError:
            failed += 1
    return ok, failed


def _apply_template(template: str, metadata: dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        fmt = match.group(2)
        return _resolve_token(key, fmt, metadata)
    return _TOKEN_RE.sub(replace, template)


def _resolve_token(key: str, fmt: str | None, metadata: dict[str, str]) -> str:
    if key == "counter":
        width = 0
        if fmt and fmt.isdigit():
            width = int(fmt)
        return f"{int(metadata['counter']):0{width}d}"
    if key == "date":
        ts = float(metadata["mtime"])
        dt = datetime.fromtimestamp(ts)
        if fmt:
            return dt.strftime(_translate_date_format(fmt))
        return dt.strftime("%Y-%m-%d")
    value = metadata.get(key)
    if value is None:
        return f"{{{key}{':' + fmt if fmt else ''}}}"
    return str(value)


_DATE_MAP = {
    "yyyy": "%Y", "yy": "%y", "mm": "%m", "dd": "%d",
    "hh": "%H", "MM": "%M", "ss": "%S",
}


def _translate_date_format(fmt: str) -> str:
    out = fmt
    for token, repl in _DATE_MAP.items():
        out = out.replace(token, repl)
    return out


def _gather_metadata(path: str, counter: int) -> dict[str, str]:
    p = Path(path)
    try:
        stat = p.stat()
        mtime = stat.st_mtime
        size = stat.st_size
    except OSError:
        mtime = 0.0
        size = 0

    width = height = 0
    camera = ""
    try:
        with Image.open(path) as im:
            width, height = im.size
            exif = im.getexif()
            if exif:
                make = (exif.get(271) or "").strip()  # Make
                model = (exif.get(272) or "").strip()  # Model
                camera = (f"{make} {model}").strip() or ""
    except Exception:  # noqa: BLE001, S110 - EXIF is optional; rename uses mtime fallback
        pass

    dt = datetime.fromtimestamp(mtime) if mtime else datetime.fromtimestamp(0)
    return {
        "name": p.stem,
        "ext": p.suffix,
        "counter": str(counter),
        "mtime": str(mtime),
        "width": str(width),
        "height": str(height),
        "wxh": f"{width}x{height}",
        "size_kb": str(int(size / 1024)),
        "camera": camera,
        "year": f"{dt.year:04d}",
        "month": f"{dt.month:02d}",
        "day": f"{dt.day:02d}",
        "hour": f"{dt.hour:02d}",
        "minute": f"{dt.minute:02d}",
    }
