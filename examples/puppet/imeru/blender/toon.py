"""Scene, light and cel-shaded materials for the Blender model of Imeru.

Shading is the cel look of 3D anime games: a white Diffuse BSDF goes through Shader to RGB,
so its grey value is the light falling on the surface (the sun's strength is pi, so a surface
square to the sun reads 1.0), and fixed thresholds split it into a lit, a shade and an
optional deep tone. Colours can blend from top to bottom of the canvas (hair turning cyan at
the tips), a rim light picks out the silhouette, and hair gets a zigzag "angel ring" band.
Lines are inverted hulls: a Solidify shell with flipped normals and back faces culled.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from common import H, PX, W, hexrgb, px

#: Render at this multiple of the canvas size; the build downsamples for clean edges.
SCALE = 2
#: Where the key light travels: from the viewer's upper left, slightly from the front.
LIGHT_DIRECTION = Vector((0.34, 0.86, -0.38))


def setup_scene(samples: int = 48) -> bpy.types.Scene:
    """An empty scene: EEVEE, transparent film, orthographic front camera, one sun."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = W * SCALE, H * SCALE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.filter_size = 1.2
    scene.eevee.taa_render_samples = samples
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    scene.world = world
    cam_data = bpy.data.cameras.new("camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = H / PX
    cam_data.sensor_fit = "VERTICAL"
    cam_data.clip_start, cam_data.clip_end = 0.1, 100.0
    camera = bpy.data.objects.new("camera", cam_data)
    camera.location = px(W / 2, H / 2, 20000)
    camera.rotation_euler = (math.radians(90), 0, 0)
    scene.collection.objects.link(camera)
    scene.camera = camera
    sun_data = bpy.data.lights.new("key", "SUN")
    sun_data.energy = math.pi
    sun_data.angle = math.radians(0.6)
    sun = bpy.data.objects.new("key", sun_data)
    sun.rotation_euler = LIGHT_DIRECTION.normalized().to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)
    return scene


class _Graph:
    """Small helper for building a material node tree by hand."""

    def __init__(self, material: bpy.types.Material):
        material.use_nodes = True
        self.tree = material.node_tree
        self.tree.nodes.clear()

    def node(self, kind: str, **inputs):
        node = self.tree.nodes.new(kind)
        for key, value in inputs.items():
            node.inputs[key].default_value = value
        return node

    def link(self, out, socket) -> None:
        self.tree.links.new(out, socket)

    def colour(self, value):
        """A colour socket: *value* is a socket already, or a ``#RRGGBB`` string."""
        if isinstance(value, str):
            return self._const(value)
        return value

    def _const(self, hex_colour: str):
        node = self.tree.nodes.new("ShaderNodeRGB")
        node.outputs[0].default_value = hexrgb(hex_colour)
        return node.outputs[0]

    def mix(self, factor, a, b, blend: str = "MIX"):
        node = self.tree.nodes.new("ShaderNodeMix")
        node.data_type = "RGBA"
        node.blend_type = blend
        if isinstance(factor, float | int):
            node.inputs[0].default_value = float(factor)
        else:
            self.link(factor, node.inputs[0])
        self.link(self.colour(a), node.inputs[6])
        self.link(self.colour(b), node.inputs[7])
        return node.outputs[2]

    def math(self, op: str, a, b=0.0, c=0.0):
        node = self.tree.nodes.new("ShaderNodeMath")
        node.operation = op
        for socket, value in zip(node.inputs, (a, b, c), strict=False):
            if isinstance(value, float | int):
                socket.default_value = float(value)
            else:
                self.link(value, socket)
        return node.outputs[0]

    def light(self, bsdf: str = "ShaderNodeBsdfDiffuse", **inputs):
        """The grey value of a white BSDF under the scene lights (shadows included)."""
        shader = self.node(bsdf, **inputs)
        to_rgb = self.node("ShaderNodeShaderToRGB")
        self.link(shader.outputs[0], to_rgb.inputs[0])
        grey = self.node("ShaderNodeRGBToBW")
        self.link(to_rgb.outputs[0], grey.inputs[0])
        return grey.outputs[0]

    def world_y(self):
        """The canvas y (pixels, down) of the shaded point."""
        geometry = self.node("ShaderNodeNewGeometry")
        split = self.node("ShaderNodeSeparateXYZ")
        self.link(geometry.outputs["Position"], split.inputs[0])
        return self.math("MULTIPLY_ADD", split.outputs["Z"], -PX, H / 2), split

    def emit(self, colour) -> None:
        out = self.node("ShaderNodeOutputMaterial")
        emission = self.node("ShaderNodeEmission")
        self.link(self.colour(colour), emission.inputs["Color"])
        self.link(emission.outputs[0], out.inputs["Surface"])


def _tone(g: _Graph, stops: list, y_socket):
    """One tone's colour down the canvas: ``stops`` is ``[(y, colour), ...]``, top first.

    Between two stops the colour eases from one to the next; above the first and below
    the last it holds.
    """
    colour = g.colour(stops[0][1])
    for (y0, _), (y1, nxt) in zip(stops, stops[1:], strict=False):
        t = g.math("DIVIDE", g.math("SUBTRACT", y_socket, y0), max(1.0, y1 - y0))
        t = g.math("MINIMUM", g.math("MAXIMUM", t, 0.0), 1.0)
        t = g.math("MULTIPLY", t, g.math("SUBTRACT", 2.0, t))
        colour = g.mix(t, colour, nxt)
    return colour


def toon(name: str, lit: str, shade: str, *, deep: str | None = None,
         split: float = 0.42, deep_split: float = 0.12, stops: list | None = None,
         rim: str | None = None, rim_split: float = 0.74, rim_strength: float = 0.55,
         spec: str | None = None, spec_split: float = 0.55, roughness: float = 0.3,
         ring: dict | None = None) -> bpy.types.Material:
    """A cel material.

    *lit* / *shade* / *deep* are ``#RRGGBB``. *stops* overrides them down the canvas:
    ``[(y, lit, shade, deep), ...]`` from the top. *ring* adds an angel-ring band:
    ``{"y": centre, "half": px, "zig": px, "period": px, "colour": ..}``.
    """
    material = bpy.data.materials.new(name)
    g = _Graph(material)
    y_px, split_xyz = g.world_y()
    column = {"lit": 1, "shade": 2, "deep": 3}

    def tone(key: str, colour: str):
        if stops:
            return _tone(g, [(row[0], row[column[key]]) for row in stops], y_px)
        return g.colour(colour)

    light = g.light()
    lit_mask = g.math("GREATER_THAN", light, split)
    colour = tone("shade", shade)
    if deep:
        deep_mask = g.math("GREATER_THAN", light, deep_split)
        colour = g.mix(deep_mask, tone("deep", deep), colour)
    colour = g.mix(lit_mask, colour, tone("lit", lit))
    if rim:
        weight = g.node("ShaderNodeLayerWeight", Blend=0.35)
        rim_mask = g.math("GREATER_THAN", weight.outputs["Facing"], rim_split)
        rim_mask = g.math("MULTIPLY", rim_mask, g.math("GREATER_THAN", light, deep_split))
        colour = g.mix(g.math("MULTIPLY", rim_mask, rim_strength), colour, rim, "SCREEN")
    if spec:
        gloss = g.light("ShaderNodeBsdfGlossy", Roughness=roughness)
        spec_mask = g.math("GREATER_THAN", gloss, spec_split)
        colour = g.mix(spec_mask, colour, spec, "SCREEN")
    if ring:
        colour = _angel_ring(g, colour, ring, y_px, split_xyz, light)
    g.emit(colour)
    material.use_backface_culling = False
    return material


def _angel_ring(g: _Graph, colour, ring: dict, y_px, split_xyz, light):
    """A zigzag highlight band across the hair at canvas y ``ring['y']``."""
    x_px = g.math("MULTIPLY", split_xyz.outputs["X"], PX)
    wave = g.math("SINE", g.math("MULTIPLY", x_px, 2 * math.pi / ring.get("period", 26.0)))
    centre = g.math("ADD", g.math("MULTIPLY", wave, ring.get("zig", 7.0)), ring["y"])
    distance = g.math("ABSOLUTE", g.math("SUBTRACT", y_px, centre))
    band = g.math("LESS_THAN", distance, ring.get("half", 9.0))
    weight = g.node("ShaderNodeLayerWeight", Blend=0.4)
    front = g.math("LESS_THAN", weight.outputs["Facing"], ring.get("facing", 0.55))
    lit = g.math("GREATER_THAN", light, 0.2)
    mask = g.math("MULTIPLY", g.math("MULTIPLY", band, front), lit)
    return g.mix(g.math("MULTIPLY", mask, ring.get("strength", 0.85)), colour,
                 ring["colour"], "SCREEN")


def flat(name: str, colour: str) -> bpy.types.Material:
    """An unlit colour (line work, painted details)."""
    material = bpy.data.materials.new(name)
    g = _Graph(material)
    g.emit(colour)
    return material


def add_outline(obj: bpy.types.Object, colour: str, width_px: float = 2.4, *,
                even: bool = True) -> None:
    """Give *obj* an inverted-hull line of *width_px* canvas pixels.

    *even* keeps the line width even on sharp creases; plates seen edge-on (sheets) need
    it off, or near-vertical faces push the hull out into long spikes.
    """
    line = flat(f"{obj.name}_line", colour)
    line.use_backface_culling = True
    line.use_backface_culling_shadow = True
    obj.data.materials.append(line)
    hull = obj.modifiers.new("outline", "SOLIDIFY")
    hull.thickness = -width_px / PX
    hull.offset = -1.0
    hull.use_flip_normals = True
    hull.use_even_offset = even
    hull.use_quality_normals = True
    hull.use_rim = False
    hull.material_offset = len(obj.data.materials) - 1
