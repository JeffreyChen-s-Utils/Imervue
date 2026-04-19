"""
Metadata CSV / JSON export.

Given a list of image paths, build a record per image (stat + EXIF highlights
+ color label / rating / tags / note) and write it as CSV or JSON.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.ExifTags import TAGS

_EXIF_FIELDS = (
    "DateTimeOriginal", "Make", "Model", "LensModel",
    "FocalLength", "FNumber", "ExposureTime", "ISOSpeedRatings",
)


def build_records(paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for p in paths:
        records.append(_build_one(p))
    return records


def export_csv(paths: list[str], dest_path: str) -> int:
    """Write records to a CSV. Returns the number of rows written."""
    records = build_records(paths)
    if not records:
        Path(dest_path).write_text("", encoding="utf-8")
        return 0
    fieldnames = _collect_fieldnames(records)
    with open(dest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return len(records)


def export_json(paths: list[str], dest_path: str, *, indent: int = 2) -> int:
    records = build_records(paths)
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=indent, default=str)
    return len(records)


def _collect_fieldnames(records: list[dict]) -> list[str]:
    seen: list[str] = []
    present: set[str] = set()
    for rec in records:
        for key in rec:
            if key not in present:
                present.add(key)
                seen.append(key)
    return seen


def _build_one(path: str) -> dict[str, Any]:
    p = Path(path)
    rec: dict[str, Any] = {
        "path": str(p),
        "name": p.name,
        "parent": str(p.parent),
        "ext": p.suffix.lower().lstrip("."),
    }
    try:
        stat = p.stat()
        rec["size_bytes"] = stat.st_size
        rec["modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except OSError:
        pass
    _populate_image_fields(path, rec)
    _populate_user_fields(str(p), rec)
    return rec


def _populate_image_fields(path: str, rec: dict[str, Any]) -> None:
    try:
        with Image.open(path) as im:
            rec["width"], rec["height"] = im.size
            exif_raw = im.getexif()
            if exif_raw:
                for tag_id, value in exif_raw.items():
                    tag = TAGS.get(tag_id, str(tag_id))
                    if tag in _EXIF_FIELDS:
                        rec[f"exif_{tag}"] = _coerce_value(value)
    except Exception:  # noqa: BLE001, S110  # nosec B110 - export should continue past one bad file
        pass


def _populate_user_fields(path: str, rec: dict[str, Any]) -> None:
    try:
        from Imervue.user_settings.color_labels import get_color_label
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        rec["color_label"] = get_color_label(path) or ""
        ratings = user_setting_dict.get("image_ratings", {})
        rec["rating"] = int(ratings.get(path, 0))
        favs = user_setting_dict.get("image_favorites", [])
        rec["favorite"] = bool(path in favs) if isinstance(favs, (list, set, tuple)) else False
    except Exception:  # noqa: BLE001, S110  # nosec B110 - user fields optional; skip lookup errors
        pass
    try:
        from Imervue.library import image_index
        rec["note"] = image_index.get_note(path)
        tags = image_index.tags_of_image(path)
        if tags:
            rec["tags"] = ";".join(tags)
        cs = image_index.get_cull_state(path)
        if cs != image_index.CULL_UNFLAGGED:
            rec["cull"] = cs
    except Exception:  # noqa: BLE001, S110 - library index is optional; export continues without it
        pass


def _coerce_value(v: Any) -> Any:
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return repr(v)
    if isinstance(v, (tuple, list)):
        return str(v)
    return v
