"""Read a .puppet file with nothing but the Python standard library.

A reference for other programs that want to open the format (specification:
``Imervue/puppet/FORMAT.md``; JSON Schemas: ``docs/schemas/``). It checks the
media type and the format version, then returns the manifest, every texture's
bytes and the motion, expression and physics JSON the manifest points at.

    python read_puppet.py examples/puppet/imeru.puppet
"""
from __future__ import annotations

import json
import sys
import zipfile

MEDIA_TYPE = "application/vnd.imervue.puppet+zip"
SUPPORTED_VERSION = 1


def read_puppet(path: str) -> dict:
    """The parts of a v1 ``.puppet`` file; ``ValueError`` for another kind of file or version."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        # Files written before the entry existed have no "mimetype"; that is fine.
        if "mimetype" in names and archive.read("mimetype").decode("ascii").strip() != MEDIA_TYPE:
            raise ValueError(f"{path} is a zip archive but not a .puppet")
        manifest = json.loads(archive.read("puppet.json"))
        version = manifest.get("version")
        if isinstance(version, bool) or version != SUPPORTED_VERSION:
            raise ValueError(f"{path} uses .puppet format version {version!r}; this reads v1")

        def companion(entry: str) -> dict:
            return json.loads(archive.read(entry))

        return {
            "manifest": manifest,
            "textures": {name: archive.read(name) for name in sorted(names)
                         if name.startswith("textures/") and not name.endswith("/")},
            "motions": {m: companion(f"motions/{m}.json") for m in manifest.get("motions", [])},
            "expressions": {e: companion(f"expressions/{e}.json")
                            for e in manifest.get("expressions", [])},
            "physics": companion(manifest["physics"]) if manifest.get("physics") else None,
        }


def summary(puppet: dict) -> str:
    """One line about the character: canvas size and how much it holds."""
    manifest = puppet["manifest"]
    width, height = manifest["size"]
    return (f"{width}x{height} px, {len(manifest['drawables'])} drawables, "
            f"{len(manifest['parameters'])} parameters, {len(puppet['motions'])} motions, "
            f"{len(puppet['textures'])} textures")


if __name__ == "__main__":
    sys.stdout.write(summary(read_puppet(sys.argv[1])) + "\n")
