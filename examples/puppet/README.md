# Puppet examples

Drop-in `.puppet` file you can import into the **Puppet** tab of
Imervue (contributed by the `plugins/puppet/` plugin — enable it from
the plugin manager if the tab isn't already showing).

| File | Subject | Drawables | Deformers | Parameters | Motions |
|---|---|---|---|---|---|
| `puppet_procedural.puppet` | procedurally-drawn chibi rig | 6 | 6 (joint rotations) | 6 | 5 (idle / wave / curtsy / cheer / step_right) |
| `puppet_complete.puppet` | feature-complete chibi rig — every shipped feature in one rig | 14 | 3 (FK chain) | 27 (Cubism standard) | 3 (Idle group ×2 + TapHead) |

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

## `puppet_complete.puppet`

A feature-complete rig that wires every shipping feature into one
document — meant as the reference example when documenting the
plugin or onboarding new contributors.

What it demonstrates:

* **14 drawables** — head, body, two arms, two legs, left/right eye
  open + close, mouth open + close, two hair strands.
* **Cubism-standard parameter catalogue** seeded by
  `puppet.standard_params` so every standard input driver (webcam,
  blink, lip-sync, cursor look-at, viseme) works without per-rig
  configuration.
* **Bone hierarchy** — `root → torso → head_rot`; the runtime's
  topological sort applies the parent rotation before the child so a
  torso lean carries head + arms with it (FK).
* **1D parameter keyforms** for head Z-tilt and body lean.
* **2D parameter blend** keyed on `ParamAngleX × ParamAngleY`.
* **Opacity keys** — eye open/close cross-fade keyed on
  `ParamEyeLOpen` / `ParamEyeROpen`, mouth open/close keyed on
  `ParamMouthOpenY`.
* **Multiply-color tint** — `ParamCheek` shifts the head's skin tone
  toward rosy (blush effect).
* **Two expressions** — `smile`, `surprised` (mixed `additive` /
  `overwrite` blend modes).
* **Three motions** — `idle_breath` and `idle_look` in the `Idle`
  group (so the idle motion cycler picks between them), plus
  `tap_head` in the `TapHead` group (HitArea triggers it). Each
  motion carries 0.5 s fade-in / fade-out.
* **Physics rig** — `ParamAngleX → ParamHairFront` via a four-particle
  Verlet chain.
* **Two hit areas** — `head` (fires the `TapHead` motion group),
  `body` (toggles the `surprised` expression).
* **Part tree** — `face` / `hair` / `body_group` with cascading
  visibility + opacity.
* **Display names** for the most-used parameters so the dock shows
  "Head Yaw" instead of `ParamAngleX`.

Build + try it:

```bash
py examples/puppet/puppet_complete_example.py     # → puppet_complete.puppet
```

Then drag the file into the Puppet tab and:

* Toggle **Auto idle** + **Idle motions**          → breath + alternating idle clips
* Toggle **Auto-blink**                            → eye-open/close cross-fade
* Toggle **Drag-track head**                       → cursor look-at via `ParamAngleX/Y`
* Click the head                                   → triggers a random `TapHead` motion
* Click the body                                   → toggles the `surprised` expression
* Toggle **Mic lip-sync**                          → viseme drives mouth open + form
* Toggle **Webcam tracking**                       → face landmarks drive head + eyes + mouth
* Toggle **Virtual camera**                        → stream the puppet into OBS / Zoom

The script runs the validator before saving and refuses to write
the file on any `error`-severity finding, so the output is always
schema-clean.

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
