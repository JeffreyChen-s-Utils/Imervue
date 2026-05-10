# Puppet examples

Drop-in `.puppet` files you can import into the **Puppet** tab of
Imervue (the third top-level tab, slotted right after Paint).

| File | Subject | Drawables | Deformers | Parameters | Motions |
|---|---|---|---|---|---|
| `demo_face.puppet` | procedural smiley face | 1 | 1 (rotation) | 1 | 1 (idle sine) |
| `demo_amiya.puppet` | Amiya from Arknights | 1 | 4 (region warps) | 4 | 3 (idle / wave / greet) |
| `demo_tpose.puppet` | procedural T-pose figure (recommended) | 6 | 6 (joint rotations) | 6 | 5 (idle / wave / jumping_jacks / bow / stretch) |

## `demo_face.puppet`

A fully-rigged single-drawable demo:

* 512 × 512 procedurally-painted face PNG (one drawable, ID `face`)
* Auto-generated triangle mesh (~70 vertices)
* One **rotation** deformer pinned at the canvas centre
* One **`ParamAngleX`** parameter ranging -1 .. +1 with three keys at
  -1 / 0 / +1 rotating the head ±0.6 rad
* One looping **`idle`** motion that swings `ParamAngleX` through a
  sine wave every 4 seconds (32 linear segments)

### Try it

1. Launch Imervue and switch to the **Puppet** tab.
2. Click **Open Puppet…** in the toolbar and pick `demo_face.puppet`.
3. The face appears centred on the canvas.
4. Drag the `ParamAngleX` slider in the right-hand **Parameters** dock —
   the head turns left and right.
5. In the bottom **Motions** dock, click `idle` to start playing.
   Press **Stop** to silence it.

Press **Auto-blink** in the toolbar to make the demo (more accurately,
the rig you build that follows the same parameter conventions) blink.
**Drag-track head** lets the cursor steer `ParamAngleX` / `ParamAngleY`.

### Build a fresh copy

If the binary file gets corrupted or you want to tweak the procedural
face, rebuild from source:

```bash
py examples/puppet/build_demo_puppet.py
```

The script regenerates `demo_face.puppet` end-to-end with no external
assets — the face PNG is rendered with Pillow's `ImageDraw` and the
rest of the rig is wired with the same `puppet.operations` API the
in-app authoring toolbar uses.

## `demo_amiya.puppet` — multi-region rig with three motions

A richer demo built on a real character illustration to show what a
multi-deformer rig looks like end-to-end:

* **Drawable:** Amiya (Arknights) full body, auto-meshed at cell-size
  24 → ~500 vertices, ~900 triangles
* **Four region-bound warp deformers** so each parameter only affects
  its slice of the canvas:
    * `head_warp` — top 30 % of the canvas
    * `body_warp` — middle 28 – 62 % band
    * `arm_left_warp` — left half of that band
    * `arm_right_warp` — right half of that band
* **Four parameters** with key forms shifting the relevant warp lattice:
    * `ParamHeadX` ∈ [-1, 1] — head turn left / right
    * `ParamBodySway` ∈ [-1, 1] — body lean
    * `ParamArmLeftUp` ∈ [0, 1] — left arm raise
    * `ParamArmRightUp` ∈ [0, 1] — right arm raise
* **Three looping motions:**
    * `idle` (4 s) — body sways while the head counter-bobs
    * `wave` (2 s) — right arm waves up + down twice; head bobs along
    * `greet` (3 s) — both arms raise then drop, body bows slightly

### Try it

```bash
# Open Puppet tab → Open Puppet… → demo_amiya.puppet
# In the Parameters dock on the right: drag any of the 4 sliders.
# In the Motions dock at the bottom: click `wave` to start playing it.
```

Toggle **Drag-track head** in the toolbar to drive `ParamHeadX` /
`ParamBodySway` from the cursor (cursor offset → both
``ParamAngleX/Y`` and these per-region warps if you remap them).

### Build a fresh copy

```bash
py examples/puppet/build_amiya_puppet.py
```

The script reads `assets/amiya_source.jpg` (the cached source image),
down-scales to 600 px on the long edge to keep the `.puppet` zip
under ~300 KB, runs `puppet_from_png` → `add_warp_deformer` × 4
→ key form shifts → `_idle / _wave / _greet` motion factories →
`save_puppet`. All in pure Python with no Qt or GL.

### Source-image attribution

`assets/amiya_source.jpg` was cached from
[Danbooru post #11344502](https://danbooru.donmai.us/posts/11344502)
(rating: g, no `do_not_post` flag at fetch time). Artist:
`mowang_xiao_lajiao`. See `assets/CREDITS.md` for full provenance.

If you'd rather build the demo against your own art, replace
`assets/amiya_source.jpg` with any full-body PNG / JPG and rerun the
builder — the warp bounds are computed from the loaded image's
dimensions so the rig adapts to whatever proportions you give it.

## `demo_tpose.puppet` — six-drawable rig with five motions ★ recommended

The clearest motion demo. A procedurally-painted T-pose figure with
each body part on its own drawable, each joint with its own rotation
deformer, each parameter swinging up to ±80 ° — every motion looks
*dramatically* different from neutral.

**Why T-pose + multi-drawable:**

* Standing-pose illustrations make the limbs hang against the torso;
  rectangular warp bounds can't isolate "the arm" without also catching
  torso pixels, so motions look like muddy blobs.
* T-pose puts the limbs out along the X axis, completely separate from
  the torso. Each body part on its own PNG with the joint pivot at a
  known canvas position lets one rotation deformer rotate exactly its
  body part — clean separation, dramatic visible motion.

**Rig:**

* **6 drawables** painted with PIL: head, torso, left arm, right arm,
  left leg, right leg
* **6 rotation deformers**, each anchored at the joint:
  `head_rot` (neck), `body_rot` (waist; rotates the whole upper half),
  `arm_left_rot` / `arm_right_rot` (shoulders), `leg_left_rot` /
  `leg_right_rot` (hips)
* **6 parameters** in [-1, 1], extreme = ±80 ° for arms, ±35 ° for
  legs, ±40 ° for head, ±25 ° for body
* **5 motions** that each move different limbs:
    * `idle` — body sway + counter head bob (4 s, loop)
    * `wave` — right arm raised and shaking back-and-forth (2 s, loop)
    * `jumping_jacks` — both arms up + both legs spread, in sync (1.6 s, loop)
    * `bow` — head + body lean forward then back (2.4 s, loop)
    * `stretch` — both arms reach upward (3 s, loop)

### Try it

```bash
# Open Puppet tab → Open Puppet… → demo_tpose.puppet
# In the Motions dock at the bottom, click any of the five motions —
# it binds to the player and starts playing immediately. Press Stop
# in the transport bar to silence it. Each motion plainly moves a
# different combination of body parts — none of them look the same.
```

In the **Parameters** dock you'll see all six sliders; drag them
individually to verify each joint rotates exactly its body part.

### Build a fresh copy

```bash
py examples/puppet/build_tpose_puppet.py
```

The whole figure is painted procedurally — no external assets needed,
no copyright concerns. To customise: tweak the canvas constants
(`HEAD_RADIUS`, `TORSO_TOP_LEFT`, etc.) or the rotation extremes
(`HEAD_YAW_MAX`, `ARM_SWING_MAX`, …) at the top of the script.

### Verify renders without launching Imervue

```bash
py examples/puppet/preview_tpose.py
# wrote tpose_previews/neutral.png + p25/p50/p75 of every motion
```

A pure-Pillow software rasteriser samples every motion at three
phases and dumps PNGs into `tpose_previews/` so you can confirm the
poses look right before opening the GL canvas.

## Authoring your own from scratch

The demo is the smallest non-trivial puppet you can build. The same
shape extends to richer rigs:

1. **Drawable** — start from any PNG via **Import PNG…** (the auto-mesh
   step replaces the manual vertex / index arrays in the demo).
2. **Deformer** — `Add Rotation Deformer` for head turns, `Add Warp
   Deformer` for cheek squashes / clothing folds.
3. **Parameter** — `Add Parameter` for each rig axis you want to drive
   (`ParamAngleX/Y/Z`, `ParamEyeLOpen`, `ParamMouthOpenY`, …).
4. **Keys** — drag the slider to an extreme, edit the deformer's form
   (rotation angle / warp grid points), press **Set key** in the
   parameter dock to snapshot the form at that slider value. Repeat at
   neutral and the opposite extreme to define the rig curve.
5. **Motion** — toggle **Record motion**, drag sliders / use webcam
   tracking / let physics run, toggle off — the take is baked into a
   linear-segment Motion and added to the document.
6. **Save** — **Save As…** writes the whole rig to a `.puppet` zip you
   can share.

See `plugins/puppet/FORMAT.md` for the full file-format reference.
