# Puppet Guide — Live Streaming & Animation Production

A walkthrough for getting from "I want to do VTuber-style streaming
or make a short animation" to "I'm live on OBS / I have an MP4
file on disk" using Imervue's **Puppet** tab.

Two paths are documented:

1. **Live streaming** — drive a puppet rig with mouse / mic /
   webcam, send the result into OBS for streaming or recording.
2. **Animation production** — record a take, edit the motion
   timeline, export to GIF / MP4 / WebM.

The two share the same rig and the same parameter system; the
only difference is whether your output is a live virtual camera
feed or a file on disk.

---

## Contents

- [Quick start](#quick-start)
- [Part 1 — Live streaming to OBS](#part-1--live-streaming-to-obs)
- [Part 2 — Making animations](#part-2--making-animations)
- [Importing rigs](#importing-rigs)
- [Advanced rig features](#advanced-rig-features)
- [Optional dependencies](#optional-dependencies)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Troubleshooting](#troubleshooting)

---

## Quick start

1. Launch Imervue (`python -m Imervue` if running from source).
2. Click the **Puppet** tab at the top of the window.
3. **File > Examples > March 7th** (or the toolbar's **Examples ▾**
   dropdown). The bundled 307-drawable Cubism rig opens centred.
4. In the bottom **Motions** dock, click any of the 18 motions.
   The rig animates immediately.
5. Press **Reset to rest** on the toolbar to snap the rig back to
   its neutral pose.

That's the baseline. The rest of this guide explains how to take
this idle rig and either go live or bake out a video.

---

## Part 1 — Live streaming to OBS

The goal: a webcam-style window in OBS showing your puppet
animated by your face / mic / mouse, ready to put in a stream.

### 1.1 Inputs (what drives the rig)

The Puppet toolbar exposes six live-input toggles (the **Live**
menu carries the same six). Combine them as needed — they don't
interfere as long as they drive different parameters.

| Toggle | Drives | Optional dep |
|---|---|---|
| **Drag-track head** | `ParamAngleX/Y`, `ParamEyeBallX/Y` follow the mouse cursor as it moves over the canvas | none |
| **Auto-blink** | `ParamEyeLOpen/ROpen` blink every ~4.5 s | none |
| **Mic lip-sync** | `ParamMouthOpenY` from microphone loudness, `ParamMouthForm` from its vowel colour | `sounddevice` |
| **Webcam tracking** | head yaw/pitch/roll, eye open, gaze and mouth open from face landmarks | `opencv-python` + `mediapipe` |
| **Auto idle** | Breath cycle + gentle drift on head / body | none |
| **Idle motions** | Plays a random motion from the `Idle` group every 8 s | none |

For a typical face-tracking VTuber setup, enable **Webcam
tracking** + **Auto-blink** + **Mic lip-sync**. When you toggle
*Webcam tracking* on, a preview window pops up showing the camera
feed with detected landmarks overlaid — useful for verifying the
tracker actually sees your face.

> **First-run note** — webcam tracking needs `mediapipe`'s
> face-landmark model. Imervue downloads it (~3.7 MB from Google
> Cloud Storage) to `<app_dir>/models/face_landmarker.task` the
> first time you enable the toggle. Subsequent launches use the
> cached copy.

**Output > VTS API** adds one more input: it opens a minimal VTube
Studio Public API server on `ws://127.0.0.1:8001` (this machine
only), so a face tracker that speaks that protocol can list the
rig's parameters and inject values into them. The server issues
and accepts tokens automatically.

### 1.2 Outputs (how OBS sees the rig)

Three paths work. Pick **A** if you're new, **B** if you want
pixel-perfect alpha compositing; **C** needs no setup at all.

#### Path A — Virtual Camera

The puppet canvas appears as a webcam in OBS's *Video Capture
Device* source list.

```bash
pip install pyvirtualcam
```

Plus the platform virtual-camera driver:

- **Windows**: OBS Studio 26+ ships the *OBS Virtual Camera*
  driver. After installing OBS, open it once and click **Start
  Virtual Camera** in the bottom-right panel — that registers
  the driver so `pyvirtualcam` can find it.
- **macOS**: OBS for Mac ships an OBS Virtual Camera system
  extension. First run will prompt to enable it under
  System Settings → Privacy & Security.
- **Linux**: `sudo apt install v4l2loopback-dkms` then
  `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"`.

Wiring:

1. In the Puppet tab, open your rig, then toggle **Output >
   Virtual camera**. The status bar tells you the exact device
   name (typically *OBS Virtual Camera*).
2. In OBS: **Sources > + > Video Capture Device** → pick the
   device named in step 1.

**Why is the background magenta?**

Virtual cameras transport RGB only — DirectShow / AVFoundation /
v4l2loopback all share that limitation. OBS treats the input as
opaque RGB, so whatever colour Imervue puts behind the character
is what OBS displays. Magenta `#FF00FF` is the industry-standard
chroma-key colour because it almost never appears in skin /
hair / eye palettes.

**Removing it in OBS:**

1. Right-click the *Video Capture Device* source → **Filters**
2. **Effect Filters → + → Color Key**
3. Configure:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF`
   - **Similarity**: start at `80`, raise to `200–300` if any
     magenta edges leak through
   - **Smoothness**: `30–50` so the cut isn't pixel-sharp
4. Close — the filter sticks to the source, so re-enabling the
   virtual camera later automatically picks it up.

#### Path B — NDI (pro grade, true alpha)

NDI carries RGBA over the LAN at sub-50 ms latency. No chroma
key needed — the alpha channel survives the wire intact.

```bash
pip install ndi-python
```

Plus:

1. Download **NDI Tools** from <https://ndi.video/tools/> — the
   installer includes the runtime DLL that `ndi-python` links
   against.
2. Install the **obs-ndi** plugin into OBS:
   <https://github.com/obs-ndi/obs-ndi/releases>

Wiring:

1. In the Puppet tab, toggle **Output > NDI output**. Status bar
   shows the source name (default *Imervue Puppet*).
2. In OBS: **Sources > + > NDI Source** → pick the source name
   from step 1.

The puppet composites directly onto your OBS scene with no
chroma-key filter. The render uses a fully-transparent
background outside the character.

**`ndi-python` build prerequisites (Windows)**

`ndi-python` ships only a source distribution; pip builds it
from C++ at install time. On Windows you need:

- **Visual Studio Build Tools 2022** with *Desktop development
  with C++* workload
- **CMake** (with *Add to system PATH* checked)
- **NDI SDK** (separate from NDI Tools — get it from
  <https://ndi.video/for-developers/ndi-sdk/>) installed at the
  default `C:\Program Files\NDI\NDI 6 SDK\`
- Environment variable `NDI_SDK_DIR` pointing at the SDK install

If that's more setup than you want, stay on Path A.

#### Path C — Window Capture (zero install)

OBS **Sources > + > Window Capture** can grab the Imervue window
directly. No virtual-camera driver, no SDK. Trade-offs:

- Captures the whole Imervue window, chrome included — you have
  to add an OBS *Crop/Pad* filter to chop down to just the
  puppet area.
- Whatever's in the puppet workspace's checker backdrop gets
  streamed too.
- Bound to whatever size the Imervue window is.

Only use this for quick demos. For anything you'd actually
stream, use A or B.

### 1.3 The character-only render path

Both Virtual Camera and NDI render the puppet to an off-screen
framebuffer **without the checker backdrop or any editor
chrome**. The toolbar / docks / status bar inside Imervue are
purely for your editing convenience; only the actual character
drawables hit the stream. The output's longest side is capped
at 1080 px (so a 3503×7777 Cubism canvas doesn't break the
DirectShow driver).

### 1.4 Reset between takes

A motion with **Loop** off stops on its last frame, **Pause** holds
the current pose, and live inputs leave their parameters wherever
they last put them. Click **Reset to rest** on the toolbar (or
**Edit > Reset to rest**) to snap everything back:

- Motion player snap-stops (no fade-out)
- All live-input toggles un-check, and **Record motion** stops (the take is kept)
- Active expressions drop
- Pose groups return to first-member default
- Physics chains snap back to rest
- Parameter values reset to authored defaults

Status bar confirms: *"Rig reset to neutral pose."*

---

## Part 2 — Making animations

The goal: end up with a `.mp4` / `.webm` / `.gif` / `.png` file
on disk.

### 2.1 Recording a motion from a live take

This is the easiest path: drive the rig with your face / mic /
mouse, record the parameter values as they fly, and Imervue
bakes the take into a `Motion` you can later play / loop / save.

1. Open your rig.
2. Enable whichever live inputs you want driving the rig
   (webcam / drag / blink / lip-sync / idle), or plan to move the
   sliders in the **Parameters** dock yourself.
3. **Output > Record motion**. A dialog asks for the motion name
   (default `user_motion`); recording starts when you confirm.
4. Perform — move your face / talk into the mic / move the
   cursor — for however long you want.
5. Choose **Output > Record motion** again to stop.
6. The new motion appears in the **Motions** dock (a take with
   an existing motion's name replaces it). Adding it reloads the
   rig, which resets parameters, expressions and physics to their
   defaults. Click the motion to play it back, or save the rig
   (**File > Save As…**) to persist it into the `.puppet` file.

Motion recording captures at 30 Hz. Flat tracks (parameters that
didn't actually change during the take) are dropped automatically.
Each remaining track gets one linear segment between every pair of
consecutive samples. The recorder reads the parameters' own values
(sliders, motions, live inputs), so expression overlays and physics
outputs are not part of the take. A recorded motion has no group.

### 2.2 Editing a recorded motion

The **Motion Timeline** dialog lets you tweak a motion's keys
post-hoc.

1. Click the motion in the **Motions** dock so the player holds
   it, then choose **Edit > Edit motion…**.
2. Pick a parameter from the **Track** list. The graph shows that
   track's keys: time runs left to right over the motion's
   duration, and the value axis always spans −1 to 1.
3. Drag a yellow point to move a key in time and value. On
   `cubic-bezier` segments, drag the purple handles to shape the
   curve. Each segment is drawn as a straight line between its
   keys.
4. The dialog doesn't add or delete keys or change a segment's
   type; the four types (`linear`, `stepped`, `inverse-stepped`,
   `cubic-bezier`) come from the motion file.
5. Every drag updates the motion in memory and re-poses the
   canvas at the player's current time. **File > Save As…**
   writes the change into the `.puppet` file.

### 2.3 Authoring a motion by hand (no live take)

The Puppet tab has no keyframe editor for new motions. To build
one without a live performance:

1. Turn on **Output > Record motion** and move the sliders in the
   **Parameters** dock — slider changes are recorded like any
   live input.
2. Stop the take and adjust its keys in **Edit > Edit motion…**
   (see 2.2).
3. For exact keyframes, write `motions/<name>.json` inside the
   `.puppet` zip by hand and list the name under `motions` in
   `puppet.json` (see [`FORMAT.md`](Imervue/puppet/FORMAT.md)).

The **Set key** button next to each slider is a rigging tool, not
a motion keyframe: it stores every deformer's current form as a
key on that parameter at the slider's value. **Edit > Add
Parameter** adds a new `ParamN` slider (−1 to 1) to key.

Parameter blends — deformer forms keyed on a grid over two or
more parameters, e.g. `ParamAngleX × ParamAngleY` steering the
head across a 2D grid — are read from `parameter_blends` in
`puppet.json`; the Puppet tab has no editor for them.

### 2.4 Exporting

| Action | Output |
|---|---|
| **Output > Capture frame…** | Single PNG of the current frame on a transparent background. Used for thumbnails / static portraits. |
| **Output > Record…** | Pick a GIF / WebM / MP4 file, then frames are written at 30 fps via `imageio` until you toggle it off; the codec follows the file extension. The toolbar button is the same toggle. |
| **Output > Export all motions…** | Pick a folder and a container (`.mp4`, `.gif` or `.webm`); every motion plays from its start and is recorded for its duration into `<motion-name>.<ext>`. Useful for batch-producing reaction clips, idle loops, etc. |

Recording uses the same **character-only off-screen render** as
the streaming outputs, so you don't have to crop the chrome out
of the file. GIF / WebM / MP4 frames fit the document's aspect
ratio into 1080 px on the long side, on a white background (these
files carry no alpha), with each side rounded to a multiple of 16.
The PNG capture keeps the document's size, up to 4096 px on the
long side.

### 2.5 Sound for recorded motions

A motion can carry a `sound_path` — an absolute path to a WAV
file. When playback of the motion starts, the WAV plays once via
`QSoundEffect`; **Pause** and **Stop** silence it. Merging a
Cubism `.model3.json` onto an open rig (see *Importing rigs*)
fills it from the motion entry's `Sound` field; for any other
motion, edit `motions/<name>.json` inside the `.puppet` zip —
the Puppet tab has no field for it. The WAV itself stays outside
the `.puppet` file, and a missing file is skipped.

If `PySide6.QtMultimedia` isn't installed the audio degrades
silently and the motion's visual track still plays.

---

## Importing rigs

### From a PNG

**File > Import PNG…** asks for a mesh cell size (64 px by
default; smaller means a denser mesh), then runs `auto_mesh` on
the image:

- Covers the image with a grid of square cells and drops every
  cell that is fully transparent
- Seeds the Cubism-standard parameter catalogue
  (`ParamAngleX/Y/Z`, `ParamEyeLOpen/ROpen`, `ParamMouthOpenY`,
  `ParamBreath`, …)
- Produces a single-drawable rig with no deformers yet — add them
  from the **Edit** menu

Good for: quick prototyping, single-character art with no layer
separation.

### From a PSD

**File > Import PSD…** turns each visible, non-empty layer into
its own drawable — a quad cropped to the layer's opaque area,
stacked in layer order — and each layer group into a Part. It then
seeds the standard parameter catalogue and auto-rigs by layer name:

- Eye layers named with a side and a state (`eye_l_open`,
  `EyeRClose`, …) fade on `ParamEyeLOpen` / `ParamEyeROpen`, so
  Auto-blink swaps them
- Mouth layers (`mouth_open`, `mouth_close`, `mouth_a` …
  `mouth_o`) fade on `ParamMouthOpenY` and `ParamMouthForm`, so
  Mic lip-sync swaps them
- `head` / `face` layers share one rotation deformer keyed on
  `ParamAngleZ` (±15°)
- `hair` / `bang` / `fringe` layers share a warp deformer plus a
  physics chain from `ParamAngleX` to `ParamHairFront`; the warp
  has no keys on `ParamHairFront` yet

Other layers (body, arms, clothing) get no deformers.

Good for: artist-supplied multi-layer character files.

### From a Cubism `.moc3`

**File > Import Cubism…** first shows a note on the import modes
(tick *Don't show this again* to skip it). It accepts both raw
`.moc3` files and the matching `.model3.json` manifest —
whichever the user picks, when the workspace has no rig open yet
the importer runs the sample-and-reconstruct conversion
end-to-end:

1. Loads `.moc3` via the Cubism Native SDK (user-supplied — drop
   the SDK under `<cwd>/sdk/` or point `CUBISM_CORE_DLL` env var
   at the DLL). Picking the raw `.moc3` works as long as the
   matching `.model3.json` sits next to it; the workspace looks
   the manifest up automatically.
2. Sweeps every Cubism parameter through its min / max values
   and records the deformed vertex positions per drawable.
3. Captures parameter-driven *visibility* transitions too — so
   gesture toggles like "peace sign" / "face cover" / "cry" /
   etc. survive the conversion.
4. Folds the existing motion / expression / physics / hit-area /
   display-name sidecars from the `.model3.json` bundle into the
   puppet. Motions in the bundle's `motions/` folder that the
   manifest doesn't list join the `Idle` group.

The converted rig opens in the canvas; **File > Save As…** writes
it as a self-contained `.puppet` zip you can ship without
redistributing the Cubism SDK (the SDK is never bundled — that's
required by Live2D's Free Material License).

> **Merging onto an existing rig.** When a `.puppet` is already
> loaded, picking a `.model3.json` instead layers its JSON-only
> metadata onto the active document: the motions, expressions,
> physics, hit areas and pose groups whose name or id isn't there
> yet, plus display names — useful for retargeting a
> Cubism motion library onto a hand-authored PSD rig. The raw
> `.moc3` path always builds a fresh document; if you want to
> add motions to an existing rig, pick the `.model3.json` or one
> of the per-asset `.motion3.json` / `.exp3.json` /
> `.physics3.json` / `.pose3.json` / `.cdi3.json` files instead.

---

## Advanced rig features

### Parameters

Every animated value is a *parameter* with a min, max, and
default. Each of a parameter's `keys` stores deformer forms at one
parameter value; the runtime interpolates linearly between the two
keys around the current value and holds the end keys beyond them.
See `Imervue/puppet/standard_params.py` for the Cubism-standard
ids the input drivers expect.

### Deformers

- **Rotation** — anchor + angle, applied to the drawables in the
  deformer's own `drawables` list. `parent` only sets the order:
  parents run before their children, but a parent's rotation moves
  just the drawables it lists, and a child's anchor doesn't follow
  it. To carry the head and arms with a body lean, list them in
  the body deformer too.
- **Warp** — `rows × cols` bilinear lattice over a `bounds`
  rectangle; vertices inside follow the grid, vertices outside
  stay put. Used for cheek squashes, clothing folds, hair swing.
- **Bone rotation** — `bone_rotation` deformers (bone id, anchor,
  angle) skin the drawables that carry `bone_weights`: each vertex
  blends the bones' rotations by its weights. Bones don't inherit
  each other's rotation either.
- **Vertex morphs** — Cubism-style per-drawable delta arrays
  blended linearly between the parameter's default and its
  extremes. The `.moc3` converter produces these.

### Pose groups

Mutually-exclusive drawable visibility. Only one member of a
group is shown at a time: pick it in the **Pose** dock, which
lists each group's members, and the others are hidden.
Used for weapon swaps, mouth-shape variants, costume changes.
The group's first member is the one shown by default; the
members' own `visible` flags don't apply.

### Physics

Verlet pendulum chains for hair / cloth / ribbons. An *input
parameter* (e.g. `ParamAngleX`) moves the chain's anchor
sideways; gravity + damping + per-particle springs pull the chain
back toward rest; the tip's sideways displacement maps back to an
*output parameter* (e.g. `ParamHairFront`), clamped to −1…1. At
rest the output equals the input, so the chain reads as a swing
that lags and overshoots whenever the input changes.

While the Puppet tab is shown and the rig has chains, the canvas
steps them about 60 times a second on a clock of its own, so they
keep swinging after the input stops. A chain's output overrides
any slider, motion or expression value on that parameter.
**Reset to rest** snaps every chain back to rest.

Chains come from a Cubism import (`.physics3.json`), from the PSD
auto-rig's hair rule, or from `physics.json` inside the `.puppet`
file; the Puppet tab has no physics editor.

### Expressions

Stacks of parameter overrides applied on top of slider / motion
values. Modes: `additive` (final = base + value), `multiply`
(final = base × value), `overwrite` (final = value). Toggle them
from the **Expressions** dock; active expressions apply in the
order they were switched on.

Used for momentary moods: *smile*, *surprised*, *angry*. The
March 7th rig ships with 8 expressions (`捂脸` / `比耶` /
`照相` / `脸红` / `黑脸` / `哭` / `流汗` / `星星`).

### Hit areas

Named click regions. A hit area's region is the bounding box of
its drawables at their current, deformed positions; left-clicking
inside one (with **Edit mesh** off) runs its actions. Its `motion`
names a motion group — a random motion of that group plays
(`TapHead` picks one of the `TapHead` motions); when no motion
carries that group, the motion of that name is selected in the
**Motions** dock, stopped, for **Play** to start. Its `expression`
toggles that expression (click body → toggle `surprised`). Where
boxes overlap, the area with the frontmost drawable wins.

The bundled March 7th rig defines no hit areas, so clicking it
does nothing. A rig converted with **File > Import Cubism…** brings
the model's `HitAreas` along as regions without actions; give
them a `motion` or `expression` in the `hit_areas` list of
`puppet.json` to make them respond. The Puppet tab has no
hit-area editor.

---

## Optional dependencies

The Puppet tab's core (rendering, parameter system, motion
playback, PNG / PSD / Cubism import) runs on the default
`requirements.txt` set. Heavier dependencies are loaded behind
`try / except` so the rest of the tab keeps working when they're
missing.

| Feature | Optional dep | Install |
|---|---|---|
| Webcam face tracking | `opencv-python` + `mediapipe` | `pip install opencv-python mediapipe` |
| Microphone lip-sync | `sounddevice` | `pip install sounddevice` |
| Virtual camera output | `pyvirtualcam` + platform driver | `pip install pyvirtualcam`, see Path A above |
| NDI output | `ndi-python` + NDI runtime + NDI SDK (build-time) | see Path B above |
| Cubism `.moc3` import | user-supplied Cubism Native SDK DLL | <https://www.live2d.com/sdk/about/> |
| Motion sound playback | `PySide6.QtMultimedia` | Usually ships with PySide6 — install via your platform's QtMultimedia package if missing |

Toggling a feature whose Python package is missing opens the
package installer for it and switches the feature on once the
install finishes. When the package is there but the device or
runtime fails (no microphone, no virtual-camera driver, no NDI
runtime), the toggle switches back off and the status bar says
why. There's also a one-shot **File > Install dependencies…**
action that batch-installs every optional Python package; the
Cubism SDK and NDI runtime have to be installed by hand because
of licensing.

---

## Keyboard shortcuts

The Puppet tab has no keyboard shortcuts of its own — every
command is on its menus and toolbar. The canvas takes these
mouse inputs:

| Input | Action |
|---|---|
| **Middle-button drag** | Pan |
| **Mouse wheel** | Zoom (cursor-anchored); **Tools > Fit to Window** re-fits |
| **Left-click** | Run the hit area under the cursor; with **Edit mesh** on, grab a vertex within 8 px of the cursor (frontmost drawable first) and drag it instead |
| **Right-click** | Clear bone-selection overlay |

---

## Troubleshooting

### "Webcam tracking starts and nothing happens"

The preview window pops up showing the camera feed; if there's
no face visible, no parameters get driven. The preview's status
line shows *"No face in frame"*. Move into frame or improve
lighting.

If the preview is black: the camera is busy (another app has
it) or the OS denied camera access. macOS asks for camera
permission on first use — check System Settings → Privacy &
Security → Camera.

### "OBS shows magenta background"

By design — see Path A in the streaming section above. Add an
OBS Color Key filter on the *Video Capture Device* source with
`Custom Color = #FF00FF`.

### "ndi-python install fails with `cmake` not found"

`ndi-python` builds from source. Install CMake, the Visual
Studio C++ Build Tools, and the NDI SDK — see Path B prereqs.
If you don't need NDI specifically, use Path A (Virtual Camera).

### "Motion plays but rig stays at last pose afterwards"

With **Loop** off in the Motions dock, a motion that reaches its
end holds its last frame, and **Pause** holds the current pose.
**Stop** eases the motion's parameters back to their defaults over
the motion's fade-out (0.5 s unless the motion sets its own).
**Reset to rest** on the toolbar puts every parameter,
expression, pose group and physics chain back in one step.

### Cubism converter shows the camera as a "phantom hand"

The peace-sign / camera / face-cover gestures on March 7th-style
rigs are driven by Cubism dynamic-visibility flags. The converter
records those transitions as `opacity_keys` curves, so each prop
only appears while its parameter is up. If a converted `.puppet`
shows the props all the time, its drawables lack those curves —
re-convert via **File > Import Cubism…** and save the result.

---

## File format reference

The `.puppet` file format is a zip container with JSON manifests
and PNG textures. Full spec at
[`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md).

Bundled demo rigs: [`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet)
and [`examples/puppet/vivian.puppet`](examples/puppet/vivian.puppet)
(see [`examples/puppet/README.md`](examples/puppet/README.md)).
