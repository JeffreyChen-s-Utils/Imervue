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
3. **File > Examples > March 7Th** (or the toolbar's **Examples ▾**
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

The Puppet toolbar exposes five live-input toggles. Combine them
as needed — they don't interfere as long as they drive different
parameters.

| Toggle | Drives | Optional dep |
|---|---|---|
| **Drag-track head** | `ParamAngleX/Y`, `ParamEyeBallX/Y` follow your mouse cursor | none |
| **Auto-blink** | `ParamEyeLOpen/ROpen` blink every ~4.5 s | none |
| **Mic lip-sync** | `ParamMouthOpenY` from your microphone RMS | `sounddevice` |
| **Webcam tracking** | head yaw/pitch/roll + eye / mouth open from face landmarks | `opencv-python` + `mediapipe` |
| **Auto idle** | Breath cycle + gentle drift on head / body | none |
| **Idle motions** | Cycles randomly through the Idle group of motions | none |

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

### 1.2 Outputs (how OBS sees the rig)

Two paths are supported. Pick **A** if you're new, **B** if you
want pixel-perfect alpha compositing.

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

When a motion finishes (or you stop one mid-play), the rig stays
frozen at the last sampled pose. Click **Reset to rest** on the
toolbar (or **Edit > Reset to rest**) to snap everything back:

- Motion player snap-stops (no fade-out)
- All live-input toggles un-check
- Active expressions drop
- Pose groups return to first-member default
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
   (webcam / drag / blink / lip-sync / idle).
3. **Output > Record motion** — toolbar button toggles on.
4. Perform — move your face / talk into the mic / drag the
   cursor — for however long you want.
5. Toggle **Record motion** off. A dialog asks for the motion
   name and optional group label (e.g. *"wave"*, *"Idle"*).
6. The new motion appears in the **Motions** dock. Click it to
   play it back, or save the rig (**File > Save As…**) to
   persist it into the `.puppet` file.

Motion recording captures at 30 Hz. Flat tracks (parameters that
didn't actually change during the take) are dropped automatically,
keeping the resulting motion file small. Each remaining track
gets one linear segment per parameter value change.

### 2.2 Editing a recorded motion

The **Motion Timeline** dialog lets you tweak a recorded motion
post-hoc.

1. In the Motions dock, right-click a motion → **Edit timeline…**
   (or double-click).
2. The dialog shows one curve per parameter track. The y-axis is
   the parameter value range, the x-axis is time.
3. Click a point to select it. Drag to move. Right-click for
   *delete* / *insert key* / *change segment type*.
4. Supported segment types: `linear`, `stepped`,
   `inverse-stepped`, `cubic-bezier` (drag the control points to
   shape the curve).
5. Use the timeline's transport bar (play / loop / scrub) to
   preview without leaving the dialog.

Tip: for natural facial motion, prefer cubic-bezier on
`ParamEyeLOpen/ROpen` (blink) and `ParamMouthOpenY` (speaking).
Linear is fine for everything else.

### 2.3 Authoring a motion by hand (no live take)

If you have a specific keyframe sequence in mind:

1. **Edit > Add Parameter** if you need a parameter that isn't
   already in the rig.
2. In the **Parameters** dock, drag the slider to the value for
   time t=0 → press **Set Key**. Imervue stamps the current
   parameter snapshot at t=0.
3. Repeat at t=1.0, t=2.0, etc.
4. The recipe runs through the Motion Timeline dialog —
   right-click → **New motion** to start from scratch with the
   keys you've authored.

For step-by-step poses across multiple parameters, the
parameter-blends feature lets you tie one input to N-dimensional
keyframes (e.g. `ParamAngleX × ParamAngleY` controlling head
direction over a 2D grid).

### 2.4 Exporting

| Action | Output |
|---|---|
| **Output > Capture frame…** | Single PNG of the current frame via `glReadPixels`. Used for thumbnails / static portraits. |
| **Output > Record…** | Frame loop into GIF / WebM / MP4 via `imageio`. The toolbar button is a toggle: start → perform → stop → write. Default 30 fps; codec picks from the file extension. |
| **Output > Export all motions…** | Renders every motion in the rig to a separate file (e.g. `<motion-name>.mp4`). Useful for batch-producing reaction clips, idle loops, etc. |

Recording uses the same **character-only off-screen render** as
the streaming outputs, so you don't have to crop the chrome out
of the file. GIF / WebM / MP4 sizes default to the document's
aspect ratio capped at 1080 longest side. PNG single-frame keeps
the document's native size.

### 2.5 Sound for recorded motions

A motion can carry a `sound_path` — an absolute path to a WAV
file. When the motion plays, the WAV plays in sync via
`QSoundEffect`. Set this manually in the Motion Timeline dialog
or by editing `motions/<name>.json` inside the `.puppet` zip;
there's no GUI for it in v1.

If `PySide6.QtMultimedia` isn't installed the audio degrades
silently and the motion's visual track still plays.

---

## Importing rigs

### From a PNG

**File > Import PNG…** runs `auto_mesh` on the image:

- Triangulates respecting the alpha channel — no white fringe at
  edges
- Seeds the Cubism-standard parameter catalogue
  (`ParamAngleX/Y/Z`, `ParamEyeLOpen/ROpen`, `ParamMouthOpenY`,
  `ParamBreath`, …)
- Produces a single-drawable rig you can then split / deform

Good for: quick prototyping, single-character art with no layer
separation.

### From a PSD

**File > Import PSD…** parses each PSD layer into its own
drawable. Layer names that match Live2D conventions (`Head`,
`Body`, `HairFront`, etc.) auto-bind to standard deformers.

Good for: artist-supplied multi-layer character files.

### From a Cubism `.moc3`

**File > Import Cubism…** runs the sample-and-reconstruct
converter:

1. Loads `.moc3` via the Cubism Native SDK (user-supplied — drop
   the SDK under `<cwd>/sdk/` or point `CUBISM_CORE_DLL` env var
   at the DLL).
2. Sweeps every Cubism parameter through its min / max values
   and records the deformed vertex positions per drawable.
3. Captures parameter-driven *visibility* transitions too — so
   gesture toggles like "peace sign" / "face cover" / "cry" /
   etc. survive the conversion.
4. Folds the existing motion / expression / physics / hit-area
   sidecars from the `.model3.json` bundle into the puppet.

Output: a self-contained `.puppet` zip you can ship without
redistributing the Cubism SDK (the SDK is never bundled — that's
required by Live2D's Free Material License).

---

## Advanced rig features

### Parameters

Every animated value is a *parameter* with a min, max, and
default. Parameters keep `keys` (single-value snapshots) that the
runtime samples linearly. See `Imervue/puppet/standard_params.py`
for the Cubism-standard ids the input drivers expect.

### Deformers

- **Rotation** — anchor + angle. Children inherit the parent's
  rotation, so a body lean carries head + arms with it.
- **Warp** — `rows × cols` bezier lattice. Used for cheek
  squashes, clothing folds, hair physics.
- **Vertex morphs** — Cubism-style per-drawable delta arrays
  blended linearly between the parameter's default and its
  extremes. The `.moc3` converter produces these.

### Pose groups

Mutually-exclusive drawable visibility. Only one member of a
group is shown at a time; selecting another hides the rest.
Used for weapon swaps, mouth-shape variants, costume changes.

### Physics

Verlet pendulum chains for hair / cloth / ribbons. An *input
parameter* (e.g. `ParamAngleX`) moves the chain's anchor; gravity
+ damping + per-particle springs pull the chain back toward
rest; the tip's lateral displacement maps back to an *output
parameter* (e.g. `ParamHairFront`).

Edit physics chains via the Bone Tree dock.

### Expressions

Stacks of parameter overrides applied on top of slider / motion
values. Modes: `additive` (final = base + value), `multiply`
(final = base × value), `overwrite` (final = value).

Used for momentary moods: *smile*, *surprised*, *angry*. The
March 7th rig ships with 8 expressions (`捂脸` / `比耶` /
`照相` / `脸红` / `黑脸` / `哭` / `流汗` / `星星`).

### Hit areas

Named regions of the rig that fire a signal when the user clicks
inside them. Bind to a motion group (`TapHead → tap_head`
plays a random motion from the `TapHead` group) or to an
expression toggle (click body → toggle `surprised`).

The March 7th rig has two hit areas — `head` triggers the
`tap_head` motion, `body` toggles the `surprised` expression.

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

The toolbar / status bar reports which features are unavailable
when you toggle them. There's also a one-shot **File > Install
dependencies…** action that batch-installs every optional Python
package; the Cubism SDK and NDI runtime have to be installed by
hand because of licensing.

---

## Keyboard shortcuts

These are Puppet-tab-local. The full shortcut reference is in
`README.md`.

| Shortcut | Action |
|---|---|
| **Mouse drag** on canvas | Pan (when drag-track is off) |
| **Mouse wheel** | Zoom (cursor-anchored) |
| **Right-click** on canvas | Clear bone-selection overlay |
| **E** | Toggle Edit Mesh mode (then drag vertices to author the mesh) |
| **B** | Toggle Auto-blink |
| **W** | Toggle Webcam tracking |
| **M** | Toggle Mic lip-sync |
| **D** | Toggle Drag-track |
| **I** | Toggle Auto-idle |
| **Space** | Play / pause the selected motion |
| **Esc** | Stop the current motion (with fade-out) |
| **Ctrl+R** | Reset to rest |

(Note: some of these shortcuts are subject to change — the
toolbar buttons are the authoritative interface.)

---

## Troubleshooting

### "Webcam tracking starts and nothing happens"

The preview window pops up showing the camera feed; if there's
no face visible, no parameters get driven. Status line shows
*"No face in frame"*. Move into frame or improve lighting.

If the preview is black: the camera is busy (another app has
it) or the OS denied camera access. macOS asks for camera
permission on first use — check System Settings → Privacy &
Security → Camera.

### "Auto-blink only fires once"

Fixed in a recent commit — blink uses a forced-write path that
bypasses the canvas's no-change-skip optimisation. Update to
latest if you're seeing this.

### "OBS shows magenta background"

By design — see Path A in the streaming section above. Add an
OBS Color Key filter on the *Video Capture Device* source with
`Custom Color = #FF00FF`.

### "ndi-python install fails with `cmake` not found"

`ndi-python` builds from source. Install CMake, the Visual
Studio C++ Build Tools, and the NDI SDK — see Path B prereqs.
If you don't need NDI specifically, use Path A (Virtual Camera).

### "Virtual camera stream looks stretched"

Fixed in a recent commit — the output now renders at the
document's aspect ratio with character-only content. Update to
latest if you're seeing the old widget-aspect stretch.

### "Motion plays but rig stays at last pose afterwards"

Click **Reset to rest** on the toolbar. Motions don't auto-rewind
on stop — they hold the last sampled value. Reset gives you a
clean baseline.

### Cubism converter shows the camera as a "phantom hand"

The peace-sign / camera / face-cover gestures on March 7th-style
rigs are driven by Cubism dynamic-visibility flags. Recent
commits taught the converter to capture those transitions as
`opacity_keys` curves. If you converted a `.moc3` on an older
build, re-convert via **File > Import Cubism…** and the rebuilt
`.puppet` will have correct gesture toggles.

---

## File format reference

The `.puppet` file format is a zip container with JSON manifests
and PNG textures. Full spec at
[`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md).

Bundled demo rig: [`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet).
