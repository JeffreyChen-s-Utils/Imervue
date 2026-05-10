# Puppet examples

Drop-in `.puppet` files you can import into the **Puppet** tab of
Imervue (the third top-level tab, slotted right after Paint).

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
5. In the bottom **Motions** dock, double-click `idle` and press **Play**
   to see the head swing on its own.

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
