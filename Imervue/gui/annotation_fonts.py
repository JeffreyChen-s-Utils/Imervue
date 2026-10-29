"""
Font lookup for baked text annotations.

Resolves a Qt font family name to a TrueType file (the Windows font registry
first, then a per-platform list of common system fonts, then PIL's built-in
bitmap font) and caches the loaded font per ``(family, size)``.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from PIL import ImageFont


_FONT_CACHE: dict[tuple[str, int], ImageFont.ImageFont] = {}


def _system_font_candidates() -> list[str]:
    if sys.platform == "win32":
        return [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
        ]
    if sys.platform == "darwin":
        return [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    # Linux
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    ]


def _resolve_font_path(family: str) -> str | None:
    """Try to find a .ttf/.ttc file for a given font family name on Windows."""
    if not family or sys.platform != "win32":
        return None
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        )
    except OSError:
        return None
    try:
        return _scan_font_registry(winreg, key, family.lower())
    finally:
        with contextlib.suppress(OSError):
            winreg.CloseKey(key)


def _scan_font_registry(winreg, key, family_lower: str) -> str | None:
    i = 0
    while True:
        try:
            name, value, _ = winreg.EnumValue(key, i)
        except OSError:
            return None
        i += 1
        if family_lower not in name.lower():
            continue
        resolved = _resolve_font_value(value)
        if resolved:
            return resolved


def _resolve_font_value(value: str) -> str | None:
    p = Path(value)
    if not p.is_absolute():
        p = Path(r"C:\Windows\Fonts") / p
    return str(p) if p.exists() else None


def _get_font(size: int, family: str = "") -> ImageFont.ImageFont:
    cache_key = (family, size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]
    font: ImageFont.ImageFont | None = None
    # Try the requested family first
    if family:
        resolved = _resolve_font_path(family)
        if resolved:
            with contextlib.suppress(OSError):
                font = ImageFont.truetype(resolved, size)
    # Fallback to system defaults
    if font is None:
        for cand in _system_font_candidates():
            try:
                font = ImageFont.truetype(cand, size)
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = font
    return font
