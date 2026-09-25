"""Code that decodes an image catches every error a decode can raise.

``except (OSError, ValueError)`` around ``Image.open`` looks complete but is
not: a picture over Pillow's pixel limit raises ``DecompressionBombError``,
which is no ``OSError``, and a WebP with a broken EXIF chunk raises
``SyntaxError`` from ``getexif``. Either one then escaped - ending a whole
batch, a recipe render or a Qt slot. ``image/read_errors.IMAGE_READ_ERRORS``
names them all; a ``try`` whose body decodes an image catches that tuple, a
tuple naming ``DecompressionBombError`` (plugins that avoid the import), or
something broader.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DECODERS = ("Image.open", "decode_image", "decode_image_file", "load_rgba", "open_export_source",
             "recipe_base_image", "upright_image", "load_image_file", "_load_shown")
_ENOUGH = ("IMAGE_READ_ERRORS", "DecompressionBombError", "Exception")


def _catches_every_read_error(block: ast.Try) -> bool:
    for handler in block.handlers:
        if handler.type is None or any(name in ast.unparse(handler.type) for name in _ENOUGH):
            return True
    return False


def _narrow_decode_tries() -> list[str]:
    found = []
    for folder in ("Imervue", "plugins"):
        for path in sorted((_ROOT / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for block in (n for n in ast.walk(tree) if isinstance(n, ast.Try) and n.handlers):
                body = ast.unparse(ast.Module(body=block.body, type_ignores=[]))
                if any(f"{name}(" in body for name in _DECODERS) and not _catches_every_read_error(block):
                    found.append(f"{path.relative_to(_ROOT).as_posix()}:{block.lineno}")
    return found


def test_every_decode_catches_every_read_error():
    assert _narrow_decode_tries() == []
