"""Assemble puppet archive members and enforce the archive size boundary."""
from __future__ import annotations

import zipfile

from Imervue.puppet.archive_members import (
    _EXPRESSIONS_DIR,
    _MOTIONS_DIR,
    _PHYSICS_JSON,
    _PUPPET_JSON,
    _load_named_entries,
    _load_physics,
    _load_textures,
    _read_json,
)
from Imervue.puppet.document import (
    PuppetDocument,
)
from Imervue.puppet.expression_codec import _expression_json_bytes, _parse_expression
from Imervue.puppet.format_schema import (
    MEDIA_TYPE,
    MIMETYPE_ENTRY,
)
from Imervue.puppet.format_values import PuppetFormatError
from Imervue.puppet.manifest_decode import _new_document, _populate_metadata
from Imervue.puppet.manifest_encode import _puppet_json_bytes
from Imervue.puppet.motion_codec import _motion_json_bytes, _parse_motion
from Imervue.puppet.physics_codec import _physics_json_bytes


def _write_entries(zf: zipfile.ZipFile, doc: PuppetDocument) -> None:
    """Write every entry of *doc* into the open archive *zf*.

    The first entry is ``mimetype``, stored uncompressed, so a tool can tell a
    ``.puppet`` from any other zip by its first bytes (as EPUB and ODF do).
    """
    zf.writestr(zipfile.ZipInfo(MIMETYPE_ENTRY), MEDIA_TYPE, compress_type=zipfile.ZIP_STORED)
    zf.writestr(_PUPPET_JSON, _puppet_json_bytes(doc))
    for tex_path, tex_bytes in doc.textures.items():
        zf.writestr(tex_path, tex_bytes)
    for motion in doc.motions:
        zf.writestr(f"{_MOTIONS_DIR}{motion.name}.json", _motion_json_bytes(motion))
    for expr in doc.expressions:
        zf.writestr(f"{_EXPRESSIONS_DIR}{expr.name}.json", _expression_json_bytes(expr))
    if doc.physics_rigs:
        zf.writestr(_PHYSICS_JSON, _physics_json_bytes(doc.physics_rigs))


def _load_from_zip(zf: zipfile.ZipFile, *, max_uncompressed: int) -> PuppetDocument:
    total = sum(info.file_size for info in zf.infolist())
    if total > max_uncompressed:
        raise PuppetFormatError(
            f"archive expands to {total:,} bytes, over the {max_uncompressed:,} limit")
    if _PUPPET_JSON not in zf.namelist():
        raise PuppetFormatError(f"missing {_PUPPET_JSON}")
    manifest = _read_json(zf, _PUPPET_JSON)

    doc = _new_document(manifest)

    doc.textures = _load_textures(zf)
    doc.motions = _load_named_entries(
        zf, manifest.get("motions") or [], _MOTIONS_DIR, "motion", _parse_motion,
    )
    doc.expressions = _load_named_entries(
        zf, manifest.get("expressions") or [], _EXPRESSIONS_DIR, "expression", _parse_expression,
    )
    if manifest.get("physics"):
        doc.physics_rigs = _load_physics(zf, manifest["physics"])
    _populate_metadata(doc, manifest)
    return doc
