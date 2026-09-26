# `.puppet` File Format — v1

A `.puppet` file is a **zip archive** holding the data needed to render
and animate a 2D rigged character. The whole format is JSON + PNG so it
diffs humanly through git, has no proprietary binary, and is fully
documented here.

## Zip layout

```
my_character.puppet
├── puppet.json              # required — manifest, drawables, deformers, parameters
├── textures/
│   ├── face.png             # referenced by drawables[].texture
│   └── body.png
├── motions/                 # optional — referenced by puppet.json motions[]
│   ├── idle.json
│   └── wave.json
├── expressions/             # optional — referenced by puppet.json expressions[]
│   └── smile.json
└── physics.json             # optional — physics rig if puppet.json physics is set
```

Filenames inside the zip are case-sensitive. Every file under
`textures/` is loaded as a texture, and each `drawables[].texture`
names one of them; a drawable whose texture is missing is not drawn
(**Tools > Validate** reports it). Loaders reject an archive whose
entries add up to more than 2 GiB uncompressed.

## Version policy

`puppet.json["version"]` is an integer monotonically incremented when
the schema gains a breaking change. v1 is frozen by this document.

* Loaders **must** reject unknown future versions cleanly.
* Future versions append fields; existing fields keep their meaning so
  v1 readers can be forward-compatible by ignoring unknown keys.
* Writers always emit the highest version they understand.

## Top-level `puppet.json`

```json
{
  "version": 1,
  "size": [2048, 2048],
  "drawables": [ … ],
  "deformers": [ … ],
  "parameters": [ … ],
  "motions": ["idle", "wave"],
  "expressions": ["smile"],
  "pose": {"groups": [ … ]},
  "physics": "physics.json",
  "hit_areas": [ … ],
  "parameter_blends": [ … ],
  "parts": [ … ],
  "display_names": {"ParamAngleX": "Head X"}
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `version` | int | yes | Schema version (must be `1` for this spec) |
| `size` | `[w, h]` ints | yes | Canvas dimensions in pixels |
| `drawables` | array | yes | Pieces of art (see *Drawable* below); may be empty |
| `deformers` | array | yes | Mesh deformation rigs (may be empty) |
| `parameters` | array | yes | Animation parameters (may be empty) |
| `motions` | array of strings | no | Names; each maps to `motions/<name>.json`, which must exist |
| `expressions` | array of strings | no | Names; each maps to `expressions/<name>.json`, which must exist |
| `pose` | object | no | Visibility groups (see *Pose* below) |
| `physics` | string | no | Path inside zip, which must exist; writers use `"physics.json"` |
| `hit_areas` | array | no | Clickable regions (see *Hit area* below) |
| `parameter_blends` | array | no | Keyforms over several parameters at once (see *Parameter blend* below) |
| `parts` | array | no | Visibility / opacity tree over drawables (see *Part* below) |
| `display_names` | object | no | Parameter or part id → friendly label. A Cubism `.cdi3.json` import fills it; it is stored and written back, and the Puppet tab's docks show the raw ids |

## Drawable

```json
{
  "id": "face",
  "texture": "textures/face.png",
  "vertices": [[x0, y0], [x1, y1], …],
  "indices": [0, 1, 2, …],
  "uvs": [[u0, v0], [u1, v1], …],
  "draw_order": 10,
  "blend_mode": "normal",
  "clip_mask": null,
  "visible": true,
  "opacity": 1.0
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the puppet |
| `texture` | string | yes | Path inside the zip (`textures/foo.png`) |
| `vertices` | array of `[x, y]` floats | yes | Mesh vertex positions in canvas-space pixels at the *neutral* pose |
| `indices` | array of ints | yes | Triangle indices, length divisible by 3, each within `[0, len(vertices))` |
| `uvs` | array of `[u, v]` floats | yes | UV coords in `[0, 1]`; same length as `vertices` |
| `draw_order` | int | yes | Lower draws first; ties broken by array order |
| `blend_mode` | enum | no | `"normal"` (default), `"additive"`, `"multiply"` |
| `clip_mask` | string\|null | no | If set, draw this drawable only where the named mask drawable's triangles cover (see *Clip masks* below) |
| `visible` | bool | no | Default `true`; pose-group members ignore it (see *Pose*) |
| `opacity` | float | no | `[0, 1]`, default `1.0` |
| `bone_weights` | object | no | Per-vertex skeletal weights (see *Bone weights* below) |
| `opacity_keys` | array | no | Parameter-driven alpha curves (see *Opacity keys* below) |
| `multiply_color` | `[r, g, b]` floats | no | Static tint multiplied into the texture colour, default `[1, 1, 1]` |
| `multiply_color_keys` | array | no | Parameter-driven tint curves (see *Multiply-colour keys* below) |
| `vertex_morphs` | array | no | Parameter-driven per-vertex offsets (see *Vertex morphs* below) |

### Clip masks

The mask is the named drawable's mesh as it is deformed this frame:
every pixel its triangles cover passes, whatever its texture's alpha
there. The mask drawable's own visibility and opacity don't matter —
an invisible drawable still clips — and the mask still draws normally
in its own turn when it is visible. An id that names no drawable, or
the drawable itself, leaves the drawable unclipped.

### Opacity keys

Optional. Drives the drawable's alpha from one or more parameters —
this is how Live2D-style cross-fades between pose variants are wired.
At render time the static `opacity` is multiplied by each curve sampled
at its parameter value and by the opacity of every Part above the
drawable. A result of `0` makes the drawable fully transparent; it is
still submitted to the renderer.

```json
"opacity_keys": [
  {
    "parameter": "arm_swing_left",
    "stops": [
      {"value": -1.57, "alpha": 1.0},
      {"value":  0.00, "alpha": 0.0}
    ]
  }
]
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `parameter` | string | yes | Parameter id sampled at runtime |
| `stops` | array | yes | At least two `{"value", "alpha"}` pairs |
| `stops[].value` | float | yes | Parameter value at this stop |
| `stops[].alpha` | float | yes | Alpha multiplier (`[0, 1]` recommended) |

Stops are linearly interpolated between adjacent points; values below
the lowest / above the highest stop clamp to the edge alpha. Multiple
entries combine multiplicatively, letting two parameters (e.g.
`swing × expression`) gate the same drawable independently.

### Multiply-colour keys

Optional. The same curve shape as *Opacity keys*, with an RGB colour
per stop instead of an alpha:

```json
"multiply_color_keys": [
  {
    "parameter": "ParamCheek",
    "stops": [
      {"value": 0.0, "color": [1.0, 1.0, 1.0]},
      {"value": 1.0, "color": [1.0, 0.6, 0.6]}
    ]
  }
]
```

Each stop needs `value` and `color` (`[r, g, b]`), and an entry needs
at least two stops. Colours are interpolated channel by channel and
clamp at the edge stops; every curve multiplies into `multiply_color`,
and negative channels clamp to `0`.

### Vertex morphs

Optional. Per-vertex offsets driven by one parameter each — the
Cubism converter stores a parameter's deformation this way:

```json
"vertex_morphs": [
  {
    "parameter": "ParamAngleX",
    "delta_at_min": [[dx0, dy0], [dx1, dy1], …],
    "delta_at_max": [[dx0, dy0], [dx1, dy1], …]
  }
]
```

`parameter` is required; `delta_at_min` / `delta_at_max` (either may be
left out) are offsets from the `vertices`, one per vertex, reached at
the parameter's `min` and `max`.
At the parameter's `default` a morph adds nothing; between the default
and an extreme it adds that side's deltas scaled linearly, and past the
extreme it holds them. Morphs run before any deformer. A morph whose
parameter doesn't exist is skipped.

### Bone weights

Optional. Maps a bone id — the `bone_id` in a `bone_rotation`
deformer's form — to one weight per vertex:

```json
"bone_weights": {
  "upper_arm_l": [1.0, 1.0, 0.6, 0.0],
  "forearm_l":   [0.0, 0.0, 0.4, 1.0]
}
```

Each list must be as long as `vertices`. Per vertex, the runtime
normalises the weights of the bones acting on the drawable so they sum
to `1`; a vertex whose weights are all `0` stays where it is.

## Deformer

```json
{
  "id": "head_rotation",
  "type": "rotation",
  "parent": null,
  "drawables": ["face"],
  "form": { "anchor": [1024, 600], "angle": 0.0 }
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the puppet |
| `type` | enum | yes | `"rotation"`, `"warp"` or `"bone_rotation"` |
| `parent` | string\|null | no | Parent deformer id; `null` (default) = root |
| `drawables` | array of strings | yes | Drawable ids this deformer affects |
| `form` | object | yes | Type-specific data — see below |

A deformer moves only the drawables in its own `drawables` list.
`parent` sets the order and nothing else: deformers run parents first
(otherwise in array order), but a parent's transform is not passed
down — a child's `anchor` stays where it was authored. Per drawable,
the pipeline is: vertex morphs, then every `bone_rotation` deformer
together in one skinning pass, then the `rotation` and `warp`
deformers in that order.

### `rotation` form

```json
{ "anchor": [cx, cy], "angle": 0.0 }
```

Rotates the controlled drawables around `anchor` by `angle` radians.

### `warp` form

```json
{
  "rows": 5,
  "cols": 5,
  "grid": [[[x, y], …], …],
  "bounds": [x_min, y_min, x_max, y_max]
}
```

`grid` is a `rows × cols` 2-D array of control points in canvas-space
pixels at the neutral pose (a flat row-major list of `rows × cols`
points also works). `bounds` is the rectangle in canvas-space that the
grid covers; vertices inside it are bilinearly interpolated from the
four surrounding grid points, and vertices outside the bounds are
unaffected by the warp. `rows` and `cols` must each be at least 2,
otherwise the warp does nothing.

### `bone_rotation` form

```json
{ "bone_id": "upper_arm_l", "anchor": [cx, cy], "angle": 0.0 }
```

One bone for linear blend skinning. Every `bone_rotation` deformer
that lists a drawable rotates that drawable's vertices around its
`anchor` by `angle` radians, and each vertex blends the results by its
`bone_weights` entry for `bone_id`. A drawable without weights for the
bone is not moved by it.

## Parameter

```json
{
  "id": "ParamAngleX",
  "min": -30.0,
  "max": 30.0,
  "default": 0.0,
  "keys": [
    {"value": -30.0, "forms": {"head_rotation": {"angle": -0.5}}},
    {"value":   0.0, "forms": {"head_rotation": {"angle":  0.0}}},
    {"value":  30.0, "forms": {"head_rotation": {"angle":  0.5}}}
  ]
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the puppet |
| `min` | float | yes | Lower bound |
| `max` | float | yes | Upper bound |
| `default` | float | yes | Value at neutral pose |
| `keys` | array | no | Key forms; default empty (parameter has no effect yet) |

A key's `forms` maps deformer id → partial form snapshot at that
parameter value. The runtime samples the parameter, finds the two
adjacent keys, and linearly interpolates between their forms (per-field:
numbers and equal-length number lists blend, a field only one of the
keys has is used as-is, and any other field comes from the lower key).
Below the lowest / above the highest key the edge key's
forms apply. The result is laid over the deformer's own `form`, so
fields a key leaves out keep their authored value. When two parameters
set the same field of the same deformer, the later parameter in the
`parameters` array wins.

## Parameter blend

```json
{
  "id": "head_xy",
  "parameters": ["ParamAngleX", "ParamAngleY"],
  "keys": [
    {"coords": [-1.0, -1.0], "forms": {"head_warp": {"grid": [ … ]}}},
    {"coords": [ 1.0, -1.0], "forms": {"head_warp": {"grid": [ … ]}}},
    {"coords": [-1.0,  1.0], "forms": {"head_warp": {"grid": [ … ]}}},
    {"coords": [ 1.0,  1.0], "forms": {"head_warp": {"grid": [ … ]}}}
  ]
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within the puppet |
| `parameters` | array of strings | yes | At least one parameter id — one axis each |
| `keys` | array | yes | Keys on the grid |
| `keys[].coords` | array of floats | yes | One value per entry in `parameters` |
| `keys[].forms` | object | no | Deformer id → partial form, as in a parameter key |

The runtime finds, on each axis, the two key coordinates around the
parameter's current value (clamping at the ends), then blends the keys
at the corners of that cell linearly along each axis. A corner without
a key is left out of the blend. Blends are applied after the
single-parameter keys, so a blend overrides them on the same deformer
fields.

## Part

```json
{
  "id": "hair",
  "drawables": ["bang_l", "bang_r"],
  "children": ["hair_back"],
  "visible": true,
  "opacity": 1.0
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique among parts |
| `drawables` | array of strings | no | Drawable ids directly under this part |
| `children` | array of strings | no | Ids of child parts |
| `visible` | bool | no | Default `true` |
| `opacity` | float | no | Default `1.0` |

Parts form a tree whose roots are the parts no other part lists as a
child. A drawable is shown only when every part above it is visible,
and its opacity is multiplied by every such part's opacity. Drawables
under no part are unaffected.

## Hit area

```json
{"id": "head", "drawables": ["face", "hair_front"], "motion": "TapHead", "expression": "surprised"}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique among hit areas |
| `drawables` | array of strings | yes | Drawables whose bounds form the region |
| `motion` | string | no | Motion group to play a random member of, or a motion name |
| `expression` | string | no | Expression to toggle |

The region is the axis-aligned bounding box of the listed drawables at
their current, deformed positions. A click inside it runs the actions:
when any motion's `group` equals `motion`, a random motion of that
group plays; otherwise the motion named `motion` is selected in the
Motions dock without playing. `expression` switches that expression on
or off. Where regions overlap, the one holding the drawable with the
highest `draw_order` wins.

## Motion (`motions/<name>.json`)

```json
{
  "version": 1,
  "duration": 2.0,
  "loop": false,
  "tracks": [
    {
      "param_id": "ParamAngleX",
      "segments": [
        {"type": "linear", "p0": [0.0, 0.0], "p1": [1.0, 30.0]},
        {"type": "cubic-bezier",
         "p0": [1.0, 30.0],
         "c0": [1.3, 30.0], "c1": [1.7, -30.0],
         "p1": [2.0, -30.0]},
        {"type": "stepped",  "p0": [t, v], "p1": [t', v]},
        {"type": "inverse-stepped", "p0": [t, v], "p1": [t', v]}
      ]
    }
  ]
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `version` | int | no | Writers emit `1`; the loader doesn't check it |
| `duration` | float | yes | Total length in seconds |
| `loop` | bool | no | Default `false`; stored and written back — playback in the Puppet tab follows the Motions dock's **Loop** checkbox instead |
| `tracks` | array | yes | One per animated parameter |
| `tracks[].param_id` | string | yes | Parameter the track drives |
| `tracks[].segments` | array | yes | Curve segments (see below) |
| `fade_in_duration` | float | no | Seconds to ease from the previous motion's values when this motion replaces it; `0` (default) uses the player's default (0.5 s in the Puppet tab) |
| `fade_out_duration` | float | no | Seconds to ease this motion's parameters back to their defaults on **Stop**; `0` (default) uses the player's default |
| `sound_path` | string | no | Absolute path to a WAV that plays once when playback starts; the file stays outside the zip |
| `group` | string | no | Motion group (`Idle`, `TapHead`, …) used by *Idle motions* and hit areas |

Each segment has a `type` (`linear`, `stepped`, `inverse-stepped`,
`cubic-bezier`) and `p0` / `p1` `[time, value]` points; `cubic-bezier`
also takes control points `c0` / `c1` and falls back to linear without
them. `stepped` holds `p0`'s value across the segment, `inverse-stepped`
jumps to `p1`'s. Writers keep segments contiguous — `p0[0]` of segment
N+1 equals `p1[0]` of segment N; the loader doesn't check this. Before
the first segment a track holds its first value, and after the last it
holds its last.

## Expression (`expressions/<name>.json`)

```json
{
  "version": 1,
  "params": [
    {"id": "ParamMouthSmile", "value": 1.0, "mode": "overwrite"},
    {"id": "ParamBrowAngle",  "value": 0.3, "mode": "additive"},
    {"id": "ParamCheekBlush", "value": 0.5, "mode": "multiply"}
  ]
}
```

`mode` is one of `additive` (the default), `multiply`, `overwrite`;
each param needs `id` and `value`, and `params` defaults to empty.
Active expressions overlay the slider / motion values in the order they
were switched on, each applied to the previous one's result.

## Pose

```json
{
  "groups": [
    {"id": "weapons", "drawables": ["sword", "bow", "fist"]}
  ]
}
```

Each group lists drawable ids that are mutually exclusive — the runtime
shows exactly one at a time: the group's first member, unless another
member has been made active. The members' own `visible` flags are
ignored. Both `id` and `drawables` are required.

## Physics (`physics.json`)

```json
{
  "version": 1,
  "rigs": [
    {
      "id": "front_hair",
      "input_param": "ParamBodyAngleX",
      "output_param": "ParamHairFront",
      "chain": [
        {"mass": 1.0, "damping": 0.7, "spring": 12.0},
        {"mass": 0.8, "damping": 0.7, "spring": 12.0}
      ],
      "gravity": [0.0, -9.8]
    }
  ]
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique among rigs |
| `input_param` | string | yes | Parameter that moves the anchor |
| `output_param` | string | yes | Parameter the tip drives |
| `chain` | array | yes | Particles, anchor first |
| `chain[].mass` | float | no | Default `1.0`; stored and written back, not used by the integrator |
| `chain[].damping` | float | no | Default `0.7`; fraction of velocity lost per step, clamped to `[0, 0.999]` |
| `chain[].spring` | float | no | Default `12.0`; each step moves the particle `spring × dt` of the way (at most all of it) toward its rest offset from the particle before it |
| `gravity` | `[x, y]` floats | no | Default `[0.0, -9.8]`; acceleration on every particle but the anchor, in a frame where the chain hangs toward −y |

Each rig is a verlet-integrated particle chain. The first particle is
the anchor: it is pinned, and `input_param`'s value × 30 px sets its
sideways position (its own `damping` / `spring` go unused). Each
following particle rests 30 px below the one before it. The tip's
sideways offset ÷ 30 px, clamped to `[-1, 1]`, is written to
`output_param` — not clamped to that parameter's own `[min, max]` — and
overrides any slider, motion or expression value there. At rest the
output equals the input (clamped). The Puppet canvas steps every chain
about 60 times a second while it is shown and the rig has chains.

## Reserved future-use keys

Loaders ignore keys not in this spec but **writers must not emit
unknown keys** for a v1 file. Any future field will arrive in v2 with a
stated migration path.
