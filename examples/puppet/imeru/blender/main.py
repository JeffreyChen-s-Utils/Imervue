"""Blender entry point: build Imeru in 3D and render each puppet layer to its own PNG.

Run by ``render3d.py`` as ``blender -b --factory-startup --python main.py -- OUT [LAYER ...]``.
Every builder puts its objects in one collection per puppet layer; each layer is rendered
alone (so the parts hidden behind other layers are painted too). Two extra passes render a
layer with other layers casting shadows but invisible to the camera — ``face_shadowed`` and
``body_shadowed`` — from which the build cuts the bang and neck shadow layers.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bpy  # noqa: E402

import arms  # noqa: E402
import body  # noqa: E402
import head  # noqa: E402
from geo import link  # noqa: E402
from toon import setup_scene  # noqa: E402

#: Shadow passes: (output name, layer rendered, layers casting shadows on it unseen).
SHADOW_PASSES = (
    ("face_shadowed", "face", ("bangs", "side_lock_l", "side_lock_r", "hairpin", "ahoge")),
    ("body_shadowed", "body", ("face",)),
)


def build() -> dict[str, bpy.types.Collection]:
    """Every part of the model, one collection per puppet layer."""
    collections: dict[str, bpy.types.Collection] = {}

    def collection_for(layer: str, obj: bpy.types.Object) -> None:
        if layer not in collections:
            collection = bpy.data.collections.new(layer)
            bpy.context.scene.collection.children.link(collection)
            collections[layer] = collection
        link(obj, collections[layer])

    for builder in (*head.BUILDERS, *body.BUILDERS, *arms.BUILDERS):
        builder(collection_for)
    return collections


def _show(collections: dict, visible: str, casters: tuple[str, ...] = ()) -> None:
    for name, collection in collections.items():
        for obj in collection.all_objects:
            shown = name == visible
            cast = name in casters
            obj.hide_render = not (shown or cast)
            obj.visible_camera = shown
            obj.visible_shadow = shown or cast


def render(collections: dict, out: Path, layer: str, visible: str,
           casters: tuple[str, ...] = ()) -> None:
    """Render *visible* (with *casters* only throwing shadows) to ``out/layer.png``."""
    _show(collections, visible, casters)
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.compression = 15
    scene.render.filepath = str(out / f"{layer}.png")
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    print(f"rendered {layer} in {time.perf_counter() - started:.1f}s", flush=True)


def main(argv: list[str]) -> None:
    out = Path(argv[0])
    wanted = set(argv[1:])
    out.mkdir(parents=True, exist_ok=True)
    setup_scene()
    collections = build()
    for layer in sorted(collections):
        if not wanted or layer in wanted:
            render(collections, out, layer, layer)
    for name, layer, casters in SHADOW_PASSES:
        if layer in collections and (not wanted or name in wanted):
            render(collections, out, name, layer, tuple(c for c in casters if c in collections))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
