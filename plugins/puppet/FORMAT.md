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

Filenames inside the zip are case-sensitive. `textures/` is the only
required subdirectory.

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
  "physics": "physics.json"
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `version` | int | yes | Schema version (must be `1` for this spec) |
| `size` | `[w, h]` ints | yes | Canvas dimensions in pixels |
| `drawables` | array | yes | Pieces of art (see *Drawable* below) — at least one |
| `deformers` | array | yes | Mesh deformation rigs (may be empty) |
| `parameters` | array | yes | Animation parameters (may be empty) |
| `motions` | array of strings | no | Names; each maps to `motions/<name>.json` |
| `expressions` | array of strings | no | Names; each maps to `expressions/<name>.json` |
| `pose` | object | no | Visibility groups (see *Pose* below) |
| `physics` | string | no | Path inside zip; usually `"physics.json"` |

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
| `indices` | array of ints | yes | Triangle indices, length divisible by 3 |
| `uvs` | array of `[u, v]` floats | yes | UV coords in `[0, 1]`; same length as `vertices` |
| `draw_order` | int | yes | Lower draws first; ties broken by array order |
| `blend_mode` | enum | no | `"normal"` (default), `"additive"`, `"multiply"` |
| `clip_mask` | string\|null | no | If set, render this drawable only inside `<id>`'s alpha |
| `visible` | bool | no | Default `true` |
| `opacity` | float | no | `[0, 1]`, default `1.0` |
| `bone_weights` | object | no | Per-vertex skeletal weights (see *Bone weights* below) |
| `opacity_keys` | array | no | Parameter-driven alpha curves (see *Opacity keys* below) |

### Opacity keys

Optional. Drives the drawable's alpha from one or more parameters —
this is how Live2D-style cross-fades between pose variants are wired.
At render time the static `opacity` is multiplied by each curve sampled
at its parameter value; a final zero short-circuits the draw call.

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
| `type` | enum | yes | `"rotation"` or `"warp"` (v1 supports these two) |
| `parent` | string\|null | yes | Parent deformer id; null = root |
| `drawables` | array of strings | yes | Drawable ids this deformer affects |
| `form` | object | yes | Type-specific data — see below |

### `rotation` form

```json
{ "anchor": [cx, cy], "angle": 0.0 }
```

Rotates the controlled drawables around `anchor` by `angle` radians at
the neutral pose.

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
pixels at the neutral pose. `bounds` is the rectangle in canvas-space
that the grid covers; vertices outside the bounds are unaffected by the
warp.

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
| `keys` | array | yes | Key forms; may be empty (parameter has no effect yet) |

A key's `forms` maps deformer id → partial form snapshot at that
parameter value. The runtime samples the parameter, finds the two
adjacent keys, and linearly interpolates between their forms (per-field).

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

`duration` is total length in seconds. Segments must tile the timeline
without gaps; `p0[0]` of segment N+1 equals `p1[0]` of segment N.

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

`mode` is one of `additive`, `multiply`, `overwrite`. Expressions
overlay on top of motion / slider values per the priority order set by
the runtime.

## Pose

```json
{
  "groups": [
    {"id": "weapons", "drawables": ["sword", "bow", "fist"]}
  ]
}
```

Each group lists drawable ids that are mutually exclusive — the runtime
shows exactly one at a time (the last one whose `visible` was set).

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

Each rig is a verlet-integrated particle chain. `input_param` drives
the chain's anchor; `output_param` receives the tip's lateral
displacement (clamped to its `[min, max]`).

## Reserved future-use keys

Loaders ignore keys not in this spec but **writers must not emit
unknown keys** for a v1 file. Any future field will arrive in v2 with a
stated migration path.
