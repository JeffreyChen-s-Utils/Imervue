# Puppet examples

Drop-in `.puppet` file you can import into the **Puppet** tab of
Imervue. The Puppet tab is built-in (see `Imervue/puppet/`) — no
plugin enable step needed.

| File | Subject | Drawables | Parameters | Motions |
|---|---|---|---|---|
| `march_7th.puppet` | March 7th (Honkai: Star Rail) Live2D rig | 307 | 203 | 9 (Idle ×7, TapHead ×1, plus author-recorded loops) |
| `ailian.puppet` | Ailian (艾莲) — community-published free Live2D rig | 480 | 207 | 6 (`/idle`, `/idle2` + 4 synthesised) plus 6 expressions |

## `march_7th.puppet`

A real Live2D model converted in-tree from the Cubism SDK output.
Source `.moc3` / textures stay on the author's machine — the binary
`.puppet` ships a snapshot of the rig with vertex morphs sampled
linearly off each parameter, so the file is self-contained and runs
on the default `requirements.txt` without the Cubism Native SDK.

**Highlights:**

* **307 drawables** with Cubism's atlas UVs preserved, masks and
  render order honoured. Front-only fragments are surfaced via the
  IsVisible bit; back-of-head / back-of-body slices stay hidden.
* **203 Cubism-standard parameters** — every standard input driver
  (webcam, blink, lip-sync, cursor look-at) drives the rig without
  per-rig configuration.
* **Vertex morphs only** — Cubism's keyform pipeline is reduced to a
  linear blend between the parameter default and ±extreme so the
  built-in runtime can play it back without licensed SDK code.
* **Nine motions:**
  * Author-converted Cubism loops — `zhaiyan`, `zhaoxiang` (both in
    the `Idle` group).
  * Reference idle / interaction loops merged in from the old
    procedural + complete examples — `idle_breath`, `idle_look`
    (Idle), `tap_head` (TapHead group, hit-area triggered).
  * Procedurally-keyed gesture loops remapped onto Cubism standard
    parameters — `idle`, `wave`, `curtsy`, `cheer`. Arm-only
    keyframes drop because the converted rig has no arm-slider
    equivalent, but every motion that touches the head or body
    survives.

## `ailian.puppet`

A second real Live2D rig converted with the same Cubism Native →
`.puppet` pipeline, used to validate the importer against a denser
mesh and a wider parameter set than March 7th. The source 4096²
textures are downsampled to 2048² before packing so the example
ships at a similar footprint to `march_7th.puppet`; the rig still
covers the full 5000×8000 author canvas, all 207 Cubism-standard
parameters, and ships with six expressions (`black`, `red`,
`shock`, `shou`, `shuiyin`, `tang`) the rig author included.

**Highlights:**

* **480 drawables** with original atlas UVs preserved — denser than
  March 7th, useful for stress-testing the renderer's draw-order
  + masking paths.
* **207 Cubism-standard parameters** drive face / body / hair /
  cloth from the same standard inputs (webcam, blink, lip-sync,
  cursor look-at) as the other examples.
* **Six motions** — two are the author's own (`/idle`, `/idle2`,
  converted from the bundled `idle.motion3.json` / `idle2.motion3.json`).
  Four are synthesised by the converter to fill out the Idle group
  when the source `.motion3.json` set is sparse: `synth_head_sway`,
  `synth_blink`, `synth_body_lean`, `synth_breath`. The synthesised
  takes use parameter-default extrema so they read as natural idle
  motion without per-rig tuning.
* **Six expressions** baked directly from the `.exp3.json` files
  the author distributed (eye-shadow swap, blush, shock, etc.).

### Try it

Launch Imervue, switch to the **Puppet** tab, click **Open Puppet…**,
pick `examples/puppet/march_7th.puppet` (or `ailian.puppet`). Click
any motion in the bottom Motions dock to play it.

Toggle the toolbar features to drive the rig live:

* **Auto idle** + **Idle motions** — breath + cycling Idle clips.
* **Auto-blink** — eye-open/close cross-fade.
* **Drag-track head** — cursor look-at via `ParamAngleX/Y`.
* **Mic lip-sync** — viseme drives mouth open + form.
* **Webcam tracking** — face landmarks drive head + eyes + mouth.
* **Virtual camera** / **NDI output** — stream the puppet into
  OBS / Zoom. See [`puppet_guide.md`](../../puppet_guide.md) at the
  repo root for the full end-to-end walkthrough covering both live
  streaming (Virtual Camera + NDI + chroma-key recipe) and
  animation production (motion record / timeline edit / MP4 export).

### Authoring your own from scratch

1. **Drawable** — start from any PNG via **Import PNG…** (the
   auto-mesh step replaces the manual vertex / index arrays).
2. **Deformer** — `Add Rotation Deformer` for head turns, `Add Warp
   Deformer` for cheek squashes / clothing folds.
3. **Parameter** — `Add Parameter` for each rig axis you want to
   drive (`ParamAngleX/Y/Z`, `ParamEyeLOpen`, `ParamMouthOpenY`, …).
4. **Keys** — drag the slider to an extreme, edit the deformer's
   form, press **Set key** in the parameter dock to snapshot the form
   at that slider value. Repeat at neutral and the opposite extreme.
5. **Motion** — toggle **Record motion**, drag sliders / use webcam
   tracking / let physics run, toggle off — the take is baked into a
   linear-segment Motion.
6. **Save** — **Save As…** writes the whole rig to a `.puppet` zip
   you can share.

See `Imervue/puppet/FORMAT.md` for the full file-format reference.
