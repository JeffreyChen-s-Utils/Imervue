"""Read typed JSON and texture members from a puppet ZIP archive."""
from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from typing import TypeVar

from Imervue.puppet.document import (
    Expression,
    Motion,
    PhysicsRig,
)
from Imervue.puppet.format_values import PuppetFormatError
from Imervue.puppet.physics_codec import _parse_physics_rig

_PUPPET_JSON = "puppet.json"


_PHYSICS_JSON = "physics.json"


_TEXTURES_DIR = "textures/"


_MOTIONS_DIR = "motions/"


_EXPRESSIONS_DIR = "expressions/"


_NamedEntry = TypeVar("_NamedEntry", Motion, Expression)


def _load_textures(zf: zipfile.ZipFile) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for name in zf.namelist():
        if name.startswith(_TEXTURES_DIR) and not name.endswith("/"):
            with zf.open(name) as fp:
                out[name] = fp.read()
    return out


def _load_named_entries(
    zf: zipfile.ZipFile, names: list[str], directory: str, label: str,
    parse: Callable[[str, dict], _NamedEntry],
) -> list[_NamedEntry]:
    out: list[_NamedEntry] = []
    members = set(zf.namelist())
    for name in names:
        path = f"{directory}{name}.json"
        if path not in members:
            raise PuppetFormatError(f"{label} {name!r} listed but {path} missing")
        raw = _read_json(zf, path)
        out.append(parse(name, raw))
    return out


def _load_physics(zf: zipfile.ZipFile, path: str) -> list[PhysicsRig]:
    if path not in zf.namelist():
        raise PuppetFormatError(f"physics path {path!r} missing in archive")
    raw = _read_json(zf, path)
    return [_parse_physics_rig(r) for r in raw.get("rigs", [])]


def _read_json(zf: zipfile.ZipFile, path: str) -> dict:
    with zf.open(path) as fp:
        try:
            return json.loads(fp.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PuppetFormatError(f"{path}: malformed JSON ({exc})") from exc
