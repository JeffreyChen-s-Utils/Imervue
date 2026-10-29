"""Encode the puppet manifest with stable field order and omission rules."""
from __future__ import annotations

from Imervue.puppet.archive_members import _PHYSICS_JSON
from Imervue.puppet.document import (
    SCHEMA_VERSION,
    PuppetDocument,
)
from Imervue.puppet.format_schema import (
    SCHEMA_FIELD,
    SCHEMA_URLS,
)
from Imervue.puppet.format_values import _dumps
from Imervue.puppet.manifest_collections import _OPTIONAL_COLLECTIONS, _REQUIRED_COLLECTIONS
from Imervue.puppet.rig_codec import (
    _pose_to_json,
)


def _puppet_json_bytes(doc: PuppetDocument) -> bytes:
    payload = {
        SCHEMA_FIELD: SCHEMA_URLS["puppet"],
        "version": SCHEMA_VERSION,
        "size": [int(doc.size[0]), int(doc.size[1])],
        **{key: [encode(item) for item in getattr(doc, key)]
           for key, _, encode in _REQUIRED_COLLECTIONS},
    }
    if doc.pose_groups:
        payload["pose"] = {"groups": [_pose_to_json(g) for g in doc.pose_groups]}
    if doc.motions:
        payload["motions"] = [m.name for m in doc.motions]
    if doc.expressions:
        payload["expressions"] = [e.name for e in doc.expressions]
    if doc.physics_rigs:
        payload["physics"] = _PHYSICS_JSON
    payload.update({key: [encode(item) for item in getattr(doc, key)]
                    for key, _, encode in _OPTIONAL_COLLECTIONS if getattr(doc, key)})
    if doc.display_names:
        payload["display_names"] = dict(doc.display_names)
    return _dumps(payload)
