# Puppet examples

Drop-in `.puppet` files you can import into the **Puppet** tab of
Imervue (the third top-level tab, slotted right after Paint).

| File | Subject | Drawables | Deformers | Parameters | Motions |
|---|---|---|---|---|---|
| `demo_face.puppet` | procedural smiley face | 1 | 1 (rotation) | 1 | 1 (idle sine) |
| `demo_tpose.puppet` | procedural T-pose figure | 6 | 6 (joint rotations) | 6 | 5 (idle / wave / jumping_jacks / bow / stretch) |
| `demo_anime_girl.puppet` | procedural anime-style girl ★ recommended | 6 | 6 (joint rotations) | 6 | 5 (idle / wave / curtsy / cheer / step_right) |

All three demos are painted procedurally with PIL — no external
illustrations, no licence concerns, fully reproducible from the
`build_*` scripts in this directory.

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

```bash
py examples/puppet/build_demo_puppet.py
```

The script regenerates `demo_face.puppet` end-to-end with no external
assets — the face PNG is rendered with Pillow's `ImageDraw` and the
rest of the rig is wired with the same `puppet.operations` API the
in-app authoring toolbar uses.

## `demo_tpose.puppet` — six-drawable rig with five motions

A T-pose figure with each body part on its own drawable, each joint
with its own rotation deformer, parameters swinging up to ±80 ° at
the shoulders. T-pose puts the limbs out along the X axis so each
rotation deformer rotates exactly its body part — clean separation,
dramatic visible motion.

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
# in the transport bar to silence it.
```

In the **Parameters** dock you'll see all six sliders; drag them
individually to verify each joint rotates exactly its body part.

### Build a fresh copy

```bash
py examples/puppet/build_tpose_puppet.py
py examples/puppet/preview_tpose.py    # → tpose_previews/*.png
```

A pure-Pillow software rasteriser samples every motion at three phases
and dumps PNGs into `tpose_previews/` so you can confirm the poses
look right before opening the GL canvas.

## `demo_anime_girl.puppet` — natural-pose anime girl ★ recommended

The friendliest demo to look at and the most complete to play with.
A procedurally-painted anime-style schoolgirl: round face, large
sky-blue eyes with iris highlights, pink twin-tail hair, sailor-style
top with a navy collar and red ribbon, pleated skirt, knee socks +
Mary Jane shoes. Standing relaxed with arms slightly out from the
torso so each shoulder rotation has room to swing without colliding
with the body.

**Why pick this over `demo_tpose`?** Same six-drawable / six-rotation
rig, but the pose looks like a character instead of a stick figure,
the joint angles are tuned for a natural standing pose (smaller body
lean, larger arm swing), and the motion set leans toward
character-y gestures (wave, curtsy, cheer) rather than calisthenics.

**Rig:**

* **6 drawables** painted with PIL — head (face + hair + bangs +
  twin tails), torso (uniform top + collar + ribbon + pleated skirt
  + belt), left/right arm (sleeve + skin-tone forearm + hand), left/
  right leg (skin thigh + sock band + Mary Jane shoe)
* **6 rotation deformers** anchored at the joints
* **6 parameters** in [-1, 1], extreme = ±75 ° for arms, ±35 ° for
  head, ±28 ° for legs, ±20 ° for body
* **5 motions** that each feature a different body region:
    * `idle` — gentle body sway + counter head turn (4 s, loop)
    * `wave` — right arm up, hand wobbling side to side (2 s, loop)
    * `curtsy` — body bows forward + head dips (2.4 s, loop)
    * `cheer` — both arms swing up to the sides like jumping jacks (2 s, loop)
    * `step_right` — right leg lifts out to the side and returns (1.6 s, loop)

### Try it

```bash
# Open Puppet tab → Open Puppet… → demo_anime_girl.puppet
# Click any of the five motions in the bottom Motions dock — they all
# play instantly on single-click. Drag the sliders in the Parameters
# dock to drive each joint manually.
```

### Build a fresh copy

```bash
py examples/puppet/build_anime_girl_puppet.py    # → demo_anime_girl.puppet
py examples/puppet/preview_anime_girl.py         # → anime_girl_previews/*.png
```

The whole figure is painted with Pillow's `ImageDraw` — no external
assets, no licence concerns, fully reproducible. Tweak the canvas
constants at the top of `build_anime_girl_puppet.py` (palette,
joint pivots, body-part rectangles, swing extremes) to retheme the
demo without touching the rig wiring.

## Authoring your own from scratch

The demos are the smallest non-trivial puppets you can build. The same
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
