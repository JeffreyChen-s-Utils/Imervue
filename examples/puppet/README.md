# Puppet examples

Drop-in `.puppet` file you can open in the **Puppet** tab of Imervue
(**File > Examples > Imeru**, or **Open Puppet…**) or put on your desktop
from the **Desktop Pet** tab (**Load bundled Imeru**). The Puppet tab is
built in (see `Imervue/puppet/`); there is nothing to enable.

| File | Subject | Drawables | Parameters | Motions | Expressions |
|---|---|---|---|---|---|
| `imeru.puppet` | Imeru, Imervue's original mascot | 40 | 31 | 8 | 7 |

## `imeru.puppet`

Imeru is drawn and rigged entirely by the code in [`imeru/`](imeru/):
no third-party artwork, model or SDK is involved, so the file can be
shared and modified like the rest of Imervue. Rebuild it with

```
py -3 examples/puppet/imeru/build.py
```

which draws every layer (about 25 seconds), rigs it, adds the motions
and expressions, writes `imeru.puppet` and checks it against the
`.puppet` format (`Imervue/puppet/FORMAT.md`).

**What the rig shows off:**

* **Live2D-style head turns** — `ParamAngleX/Y` move every head layer by
  its depth: the eyes and nose shift most, the face outline stays put,
  the fringe moves in front and the back hair the other way, so the face
  reads as round. `ParamAngleZ` rolls the head around the neck.
* **Eyes** — the white of each eye closes onto the lower lid
  (`ParamEyeLOpen` / `ParamEyeROpen`) and the iris and highlights are
  clipped to it with `clip_mask`; `ParamEyeLSmile` / `ParamEyeRSmile`
  cross-fade to happy ^^ eyes; `ParamEyeBallX/Y` move the irises.
* **Mouth** — the inside of the mouth opens from a closed shape
  (`ParamMouthOpenY`, which also drops the jaw) and `ParamMouthForm`
  turns the corners up or down, so lip-sync and expressions work.
* **Two-joint arms** — `ParamArmRA/RB` and `ParamArmLA/LB` raise each
  upper arm at the shoulder and bend the forearm at the elbow. The
  format passes no transform from one deformer to another, so the
  forearm and hand sit in both rotation deformers and the forearm's
  runs first: bend at the elbow, then turn with the upper arm. Raised,
  the relaxed hand cross-fades to an open palm for waving.
* **Hair physics** — three physics chains swing the fringe, the side
  locks and the back hair (`ParamHairFront/Side/Back`) as the head and
  body move.
* **Every Cubism-standard parameter** — webcam tracking, auto-blink,
  lip-sync and cursor look-at drive her without per-rig setup.
* **Motions** — `idle_breath` and `idle_look` (Idle), `tap_head`
  (TapHead, plays when you click her head), `shy` (TapBody, plays when
  you click her body), and `greet`, `wave`, `surprised`, `sleepy`
  (Gesture).
* **Expressions** — `smile`, `happy`, `surprised`, `sad`, `angry`,
  `blush`, `sleepy`.

The Desktop Pet's matching voice is
[`../desktop_pet/imeru.petscript.json`](../desktop_pet/imeru.petscript.json):
greetings, a line for each time of day, replies to clicks on her `Head`
and `Body`, lines for her motions and a stretch reminder.

### Try it

Launch Imervue, switch to the **Puppet** tab and pick **File > Examples >
Imeru**. Click any motion in the bottom Motions dock to play it, or click
her head or body.

Toggle the toolbar features to drive the rig live:

* **Auto idle** + **Idle motions** — breath + cycling Idle clips.
* **Auto-blink** — eye-open/close.
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

Or build one in code the way `imeru/` does: draw layers, mesh them with
`Imervue.puppet.auto_mesh.triangulate_alpha_grid`, add vertex morphs,
deformers, motions and expressions to a `PuppetDocument`, and save it
with `Imervue.puppet.document_io.save_puppet`.

See `Imervue/puppet/FORMAT.md` for the full file-format reference.
