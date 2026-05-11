# Puppet examples

Drop-in `.puppet` file you can import into the **Puppet** tab of
Imervue (now a built-in top-level tab, slotted right after Paint).

| File | Subject | Drawables | Deformers | Parameters | Motions |
|---|---|---|---|---|---|
| `demo_anime_girl.puppet` | anime-girl rig built from `puppet_char.png` | 7 | 6 (joint rotations) | 6 | 5 (idle / wave / curtsy / cheer / step_right) |

## `demo_anime_girl.puppet`

Single feature-complete demo built from the bundled
`puppet_char.png`. The figure is split into seven drawables: a
**static base layer** at draw_order 0 (the full character) plus six
body-part **slices** (head, torso, two arms, two legs) on top with
their own rotation deformers. Each slice's alpha is feathered along
its rectangle edges so the cut blends into the base; the modest
joint angles keep the un-rotated base from peeking through behind a
rotated slice.

**Pipeline (run by `build_anime_girl_puppet.py`):**

1. Chroma-key the off-white backdrop in `puppet_char.png` so the
   silhouette goes transparent.
2. Crop to the figure bbox + 60 % padding on each side so rotated
   limbs stay inside the canvas.
3. Build the base drawable from the full canvas.
4. Crop six rectangular body-part slices, multiply each by a
   soft-edge alpha mask, and stack them with their own rotation
   deformers anchored at the joints.

**Parameters & motions:**

* `ParamHeadYaw` — head tilt left/right (±7°)
* `ParamBodyLean` — torso lean (±4°)
* `ParamArm{Left,Right}Swing` — shoulder swing (±15°)
* `ParamLeg{Left,Right}Swing` — hip swing (±9°)
* Motions: `idle` (4 s body sway + head bob), `wave` (right arm up,
  hand wobbling), `curtsy` (body bow + head dip), `cheer` (both
  arms up), `step_right` (right leg sideways).

### Try it

```bash
# Launch Imervue, switch to the Puppet tab, click Open Puppet…,
# pick examples/puppet/demo_anime_girl.puppet.
# Click any of the five motions in the bottom Motions dock — each
# plays on single-click. Drag sliders in the Parameters dock to
# drive each joint manually.
```

### Build a fresh copy

```bash
py examples/puppet/build_anime_girl_puppet.py    # → demo_anime_girl.puppet
py examples/puppet/preview_anime_girl.py         # → anime_girl_previews/*.png
```

The build is fully reproducible from `puppet_char.png` plus the
script — no other assets are needed. To re-target the rig at a
different illustration, drop a new image in next to the script and
re-tune the body-part rectangles + joint pivot fractions at the top
of `build_anime_girl_puppet.py` (look for `*_FRAC` constants).

## Authoring your own from scratch

The demo is the smallest non-trivial puppet you can build. The same
shape extends to richer rigs:

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

See `Imervue/puppet/FORMAT.md` for the full file-format reference.
