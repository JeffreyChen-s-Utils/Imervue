"""Validate the puppet manifest and construct its document records."""
from __future__ import annotations

from Imervue.puppet.document import (
    SCHEMA_VERSION,
    PuppetDocument,
)
from Imervue.puppet.format_values import PuppetFormatError, _parse_size, _require_list
from Imervue.puppet.manifest_collections import _OPTIONAL_COLLECTIONS, _REQUIRED_COLLECTIONS
from Imervue.puppet.rig_codec import (
    _parse_pose_group,
)


def _new_document(manifest: dict) -> PuppetDocument:
    _check_version(manifest)
    doc = PuppetDocument(
        size=_parse_size(manifest.get("size")),
        **{key: [decode(item) for item in _require_list(manifest, key)]
           for key, decode, _ in _REQUIRED_COLLECTIONS},
    )
    pose = manifest.get("pose")
    if pose is not None:
        doc.pose_groups = [_parse_pose_group(g) for g in pose.get("groups", [])]

    return doc


def _populate_metadata(doc: PuppetDocument, manifest: dict) -> None:
    for key, decode, _ in _OPTIONAL_COLLECTIONS:
        setattr(doc, key, [decode(item) for item in manifest.get(key) or []])
    display = manifest.get("display_names") or {}
    if isinstance(display, dict):
        doc.display_names = {str(k): str(v) for k, v in display.items()}


def _check_version(manifest: dict) -> None:
    version = manifest.get("version")
    if version == SCHEMA_VERSION and not isinstance(version, bool):   # JSON true == 1 in Python
        return
    if isinstance(version, int) and not isinstance(version, bool) and version > SCHEMA_VERSION:
        raise PuppetFormatError(
            f"this file uses .puppet format v{version}, newer than the v{SCHEMA_VERSION} "
            "this Imervue reads; update Imervue to open it")
    raise PuppetFormatError(
        f"unsupported puppet schema version {version!r}; expected {SCHEMA_VERSION}"
    )
