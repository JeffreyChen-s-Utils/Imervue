"""MCP resources — expose images as readable resources.

Resource URIs use a custom ``imervue://image/<url-encoded-path>`` scheme so a
read resolves a file path directly (no server-side root needed for reads).
``resources/list`` enumerates an optional configured root folder with cursor
pagination; ``resources/templates/list`` publishes URI templates that scale to
huge libraries. All reads reuse the pure tool functions.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

_SCHEME = "imervue://image/"
_METADATA_SUFFIX = "/metadata"
_PAGE_SIZE = 100


class ResourceError(Exception):
    """A resource access failure carrying a JSON-RPC error code."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def image_uri(path: str) -> str:
    """Build the canonical (thumbnail) resource URI for an image *path*."""
    return f"{_SCHEME}{quote(str(path), safe='')}"


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(str(offset).encode()).decode("ascii")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.b64decode(cursor).decode("ascii")))
    except (ValueError, TypeError, base64.binascii.Error) as exc:
        raise ResourceError(-32602, "invalid cursor") from exc


def list_resources(root: str | None, cursor: str | None = None) -> dict[str, Any]:
    """List image resources under *root* (paginated). Empty when no root is set."""
    base = Path(root) if root else None
    if base is None or not base.is_dir():
        return {"resources": []}
    from Imervue.mcp_server.tools import _IMAGE_EXTENSIONS
    paths = sorted(
        str(p) for p in base.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    offset = _decode_cursor(cursor)
    page = paths[offset:offset + _PAGE_SIZE]
    result: dict[str, Any] = {
        "resources": [
            {
                "uri": image_uri(p),
                "name": Path(p).name,
                "mimeType": "image/png",
                "description": "Image thumbnail (read for a preview).",
            }
            for p in page
        ],
    }
    if offset + _PAGE_SIZE < len(paths):
        result["nextCursor"] = _encode_cursor(offset + _PAGE_SIZE)
    return result


def list_resource_templates() -> dict[str, Any]:
    """Publish the parameterised resource-URI templates."""
    return {
        "resourceTemplates": [
            {
                "uriTemplate": f"{_SCHEME}{{path}}",
                "name": "Image thumbnail",
                "description": "Base64 PNG preview of an image.",
                "mimeType": "image/png",
            },
            {
                "uriTemplate": f"{_SCHEME}{{path}}{_METADATA_SUFFIX}",
                "name": "Image metadata",
                "description": "Dimensions / EXIF / XMP for an image, as JSON.",
                "mimeType": "application/json",
            },
        ],
    }


def _validated_image(path: str) -> Path:
    candidate = Path(path)
    if ".." in candidate.parts:
        raise ResourceError(-32602, "resource path must not contain '..' segments")
    if not candidate.is_file():
        raise ResourceError(-32002, f"resource not found: {path}")
    return candidate


def read_resource(uri: str) -> dict[str, Any]:
    """Resolve a resource *uri* to its contents (thumbnail blob or metadata JSON)."""
    if not isinstance(uri, str) or not uri.startswith(_SCHEME):
        raise ResourceError(-32602, f"unsupported resource URI: {uri!r}")
    rest = uri[len(_SCHEME):]
    if rest.endswith(_METADATA_SUFFIX):
        return _metadata_contents(uri, unquote(rest[: -len(_METADATA_SUFFIX)]))
    return _thumbnail_contents(uri, unquote(rest))


def _metadata_contents(uri: str, path: str) -> dict[str, Any]:
    from Imervue.mcp_server.tools import read_image_metadata
    image_path = _validated_image(path)
    meta = read_image_metadata(str(image_path))
    return {"contents": [{
        "uri": uri, "mimeType": "application/json",
        "text": json.dumps(meta, ensure_ascii=False, default=str),
    }]}


def _thumbnail_contents(uri: str, path: str) -> dict[str, Any]:
    from Imervue.mcp_server.tools import image_thumbnail
    image_path = _validated_image(path)
    thumb = image_thumbnail(str(image_path))
    base64_png = thumb["data_uri"].split(",", 1)[1]
    return {"contents": [{"uri": uri, "mimeType": "image/png", "blob": base64_png}]}
