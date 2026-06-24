"""macOS ``.app`` bundle helpers — Info.plist document-type associations.

The macOS PyInstaller spec (``Imervue_mac.spec``) declares which image types the
``.app`` opens, so Finder offers "Open With Imervue". The mapping is derived
from the shared :data:`Imervue.system.file_association.ASSOC_EXTENSIONS`, so the
three platforms stay in sync.

Pure data helpers — unit-tested without building a bundle.
"""
from __future__ import annotations

BUNDLE_IDENTIFIER = "com.imervue.viewer"

# Extension → Uniform Type Identifier for the formats Imervue opens.
_RAW_UTI = "public.camera-raw-image"
_UTI_BY_EXT: dict[str, str] = {
    ".png": "public.png",
    ".jpg": "public.jpeg",
    ".jpeg": "public.jpeg",
    ".bmp": "com.microsoft.bmp",
    ".tif": "public.tiff",
    ".tiff": "public.tiff",
    ".webp": "org.webmproject.webp",
    ".gif": "com.compuserve.gif",
    ".heic": "public.heic",
    ".heif": "public.heif",
    ".avif": "public.avif",
    ".cr2": _RAW_UTI,
    ".nef": _RAW_UTI,
    ".arw": _RAW_UTI,
    ".dng": _RAW_UTI,
    ".raf": _RAW_UTI,
    ".orf": _RAW_UTI,
}


def content_types_for(extensions: list[str]) -> list[str]:
    """De-duplicated UTIs for *extensions*, preserving order."""
    out: list[str] = []
    for ext in extensions:
        uti = _UTI_BY_EXT.get(ext.lower())
        if uti and uti not in out:
            out.append(uti)
    return out


def image_document_types(extensions: list[str]) -> list[dict]:
    """``CFBundleDocumentTypes`` declaring Imervue as a viewer for the images."""
    types = content_types_for(extensions)
    if not types:
        return []
    return [{
        "CFBundleTypeName": "Image",
        "CFBundleTypeRole": "Viewer",
        "LSItemContentTypes": types,
    }]


def info_plist(extensions: list[str], version: str = "1.0.0") -> dict:
    """Build the ``.app`` Info.plist dict: version + document associations."""
    return {
        "CFBundleShortVersionString": version,
        "CFBundleIdentifier": BUNDLE_IDENTIFIER,
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": image_document_types(extensions),
    }
