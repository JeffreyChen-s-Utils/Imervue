# Puppet examples

Drop-in `.puppet` file you can import into the **Puppet** tab of
Imervue (contributed by the `plugins/puppet/` plugin — enable it from
the plugin manager if the tab isn't already showing).

| File | Subject | Drawables | Deformers | Parameters | Motions |
|---|---|---|---|---|---|
| `puppet_procedural.puppet` | procedurally-drawn chibi rig | 6 | 6 (joint rotations) | 6 | 5 (idle / wave / curtsy / cheer / step_right) |

## `puppet_procedural.puppet`

A fully procedural demo: every body part is drawn directly with PIL
primitives onto its own transparent canvas, then triangulated into a
mesh. No source image, no chroma-key, no segmentation — each drawable
starts life with a clean anti-aliased silhouette, so rotations can
never expose the white edges, ghost overlaps, or "cut" artefacts that
come from slicing a single hand-drawn image into parts.

The rig has six drawables: torso, two legs, two arms, head. Each
rotates around its joint anchor independently (head at the neck,
arms at the shoulders, legs at the hips), and a parent `body_rot`
leans the whole figure for the `curtsy` motion.

**Pipeline (run by `puppet_procedural_example.py`):**

1. Pick canvas size + figure-frac anchors for the head, neck,
   shoulders, hips, and feet.
2. Render each body part onto a transparent canvas with `PIL.ImageDraw`
   at 4× supersample, downscaled with LANCZOS for anti-aliasing.
3. Wrap each layer in a `Drawable` via `triangulate_alpha_grid`, wire
   one rotation deformer per joint, and bind the five motions.
4. Save as `puppet_procedural.puppet` next to the script.

**Parameters & motions:**

* `ParamHeadYaw` — head tilt left/right (±12°)
* `ParamBodyLean` — torso lean (±6°)
* `ParamArm{Left,Right}Swing` — shoulder swing (±80°)
* `ParamLeg{Left,Right}Swing` — hip swing (±14°)
* Motions: `idle` (4 s body sway + arm swing), `wave` (right arm up,
  hand wobbling), `curtsy` (body bow + head dip), `cheer` (both
  arms up), `step_right` (right leg sideways).

### Try it

```bash
# Launch Imervue, switch to the Puppet tab, click Open Puppet…,
# pick examples/puppet/puppet_procedural.puppet.
# Click any of the five motions in the bottom Motions dock — each
# plays on single-click. Drag sliders in the Parameters dock to
# drive each joint manually.
```

### Build a fresh copy

```bash
py examples/puppet/puppet_procedural_example.py    # → puppet_procedural.puppet
py examples/puppet/puppet_procedural_preview.py    # → puppet_procedural_previews/*.png
```

To retarget the rig — different palette, proportions, or new body
parts — edit the constants at the top of `puppet_procedural_example.py`
(`*_RGB` for colours, `HEAD_RADIUS` / `LIMB_THICKNESS` / `SHOULDER_*`
etc. for geometry) and add or remove `_Part` entries in `_build_doc`.

## Authoring your own from scratch

The procedural demo is one path; the more typical path is to start
from your own illustration:

1. **Drawable** — start from any PNG via **Import PNG…** (the
   auto-mesh step replaces the manual vertex / index arrays).
2. **Deformer** — `Add Rotation Deformer` for head turns, `Add Warp
   Deformer` for cheek squashes / clothing folds.
3. **Parameter** — `Add Parameter` for each rig axis you want to
   drive (`ParamAngleX/Y/Z`, `ParamEyeLOpen`, `ParamMouthOpenY`, …).
4. **Keys** — drag the slider to an extreme, edit the deformer's
   form (rotation angle / warp grid points), press **Set key** in
   the parameter dock to snapshot the form at that slider value.
   Repeat at neutral and the opposite extreme to define the rig
   curve.
5. **Motion** — toggle **Record motion**, drag sliders / use webcam
   tracking / let physics run, toggle off — the take is baked into
   a linear-segment Motion and added to the document.
6. **Save** — **Save As…** writes the whole rig to a `.puppet` zip
   you can share.

See `plugins/puppet/FORMAT.md` for the full file-format reference.
