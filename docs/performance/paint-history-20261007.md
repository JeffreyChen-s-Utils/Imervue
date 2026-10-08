# Paint history: shared tiles and byte budget

Measured on the fixed fixture and hardware from [baseline-20261007.md](baseline-20261007.md).
[Raw report](paint-history-20261007.json) contains three samples, RSS and measured source hashes.

| Metric | Baseline median / p95 (ms) | Shared history median / p95 (ms) |
| --- | ---: | ---: |
| undo_seed | 20.94 / 20.94 | 70.90 / 70.90 |
| stroke_commit | 24.37 / 25.97 | 0.84 / 0.93 |
| undo | 68.29 / 72.63 | 70.09 / 73.92 |
| redo | 66.36 / 66.82 | 69.50 / 70.32 |
| autosave_compress_write | 1335.33 / 1359.26 | 1315.41 / 1383.97 |
| autosave_recover | 216.84 / 216.84 | 236.78 / 236.78 |

After three 32x32 edits: **9,350,748 retained bytes** (8.92 MiB).
Six live RGBA layers: 199,065,600 bytes. Four unshared raster snapshots alone would use 796,262,400 bytes.

The 512 MiB limit includes the committed baseline, both history branches, unique pixel
payloads, Python containers and the weak interning index. The empty disabled history reports zero;
fixed object scaffolding is not pixel history. Capacity eviction rebuilds the weak index
so spare dictionary capacity and abandoned branch keys do not accumulate.

Repeated gradient tiles strongly favor interning. This fixture establishes timing and
bounded storage on the synthetic workload, not compression ratios for real photographs.
A separate seeded six-layer 1024x1024 random-pixel test meets the >=60% reduction target
against four full snapshots without repetitive tiles. Production brush/eraser dispatchers
supply complete damage hints, including release-tail pixels; the benchmark uses the same
32x32 edit and explicit hint. Unknown edits scan every array and retain full correctness.

Stroke commit p95: 0.93ms (target <=30ms). Undo/Redo p95 stay within 20% of baseline.
Initial capture is slower because it builds the shared tile inventory; it runs when history
is seeded. Existing default level limit remains 50, with older steps pruned at the byte limit.
An individual state exceeding the limit clears history, logs the reason and keeps live edits.

Complete metadata/geometry restoration uses reversible structural states with shared pixels;
deleted layers and changed geometry can materialize independent full arrays. Surviving
writable arrays receive changed tiles. A public committed snapshot materializer also returns
independent full arrays and excludes Qt callbacks/composite caches.

This is one independent desktop run with three samples per metric. Power/thermal state,
background tasks and the OS filesystem cache are not controlled. The autosave pipeline is
unchanged here; its background scheduling remains the next autosave stage.
