# Background Paint autosave — 2026-10-07

Periodic autosave now enqueues the immutable last committed edit and performs
snapshot reconstruction, compression and writing on a background worker.
Each workspace allows one writer and keeps only the latest pending version of
each document. Explicit `take_autosave_snapshot_now()` retains its synchronous
path-returning contract. A document that cannot retain history first takes an
independent UI-thread copy; that fallback can stall and is outside the O(1)
enqueue measurements below.

The fixed #62 fixture remains six 3840×2160 RGBA gradient layers (199,065,600
live pixel bytes), on the same Ryzen 5 240/32 GB Windows host. Three samples
per independent child/profile retain the same edit/history/recovery workload.
The benchmark now also drives the actual QObject/mixin/QThreadPool autosave
path while a 10ms UI heartbeat runs; it does not create a GL Paint widget.
Source/tool hashes and raw timings/RSS are retained in
[first report](autosave-background-20261007.json) and
[intermediate repeat](autosave-background-repeat-20261007.json) and
[final-source report](autosave-background-final-20261007.json).

| Metric | First run median / p95 ms | Intermediate median / p95 ms | Final source median / p95 ms |
|---|---:|---:|---:|
| UI enqueue | 0.15 / 0.66 | 0.14 / 0.56 | 0.13 / 0.85 |
| Worker snapshot materialization | 67.05 / 71.21 | 74.76 / 77.51 | 79.61 / 80.16 |
| Worker compression + write | 1371.26 / 1479.30 | 1260.18 / 1268.48 | 1561.78 / 1562.26 |
| Request to recorded success | 1455.52 / 1562.87 | 1348.04 / 1357.31 | 1659.47 / 1660.06 |
| 10ms UI heartbeat interval | 9.98 / 11.34 | 10.04 / 11.53 | 10.05 / 11.38 |

All enqueue p95 values satisfy the 25ms requirement. Worker compression/write
p95 stays within 1.2× the original 1359.26ms baseline. Heartbeat maximum gaps
are 17.65/17.26/19.99ms. Sampled background-phase RSS peaks are
481.04/480.54/480.89 MiB;
the detached materialized document adds approximately 200 MiB while writing.
No claim is made that compression itself became faster.

The first run also measured larger synchronous-write/history timings, despite
unchanged history operations. Its results remain visible: synchronous write
p95 1763.71ms, Undo/Redo p95 116.05/112.69ms. The repeat gives synchronous write
p95 1308.24ms and Undo/Redo p95 62.55/64.64ms, within the existing acceptance
targets. Host load, OS cache, power and thermal state are uncontrolled; this
variation cannot be attributed to source changes alone. The final source run
gives synchronous write p95 1585.48ms and Undo/Redo p95 77.25/78.90ms, also
within the original 20% regression limits. It includes the late document
replacement/deleted-canvas result checks; hashes match the measured sources.

Committed snapshots own immutable pixel tiles and copied structural metadata;
workers never walk live canvas pixels. A later stroke, layer/mask change,
Undo or document replacement cannot mix two versions inside one bundle.
Repeat requests coalesce; returning to the version already being written
removes an obsolete pending version. Empty documents do not record success.
Write/materialization failures report their error and retain readable older
snapshots. Tests cover full layers, masks, selections, named selections,
groups, reference indices and manga panel metadata through native recovery.

Application-owned signal senders and jobs outlive closed owners until terminal
delivery. Closing/replacing a document cancels its pending write; a writer
already compressing finishes safely and deletes cancelled late output.
Cancellation arriving between completion and UI delivery schedules deletion
on another worker. GUI success records ownership immediately in the queued
completion slot, so an intervening close cannot leave an unowned result.

Reproduce from the checkout:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/performance_benchmark.py --fixtures .git/performance-baseline-v1 --output autosave-report.json --repeats 3 --only paint
```

The normal benchmark fixture ownership/digest checks and isolated profiles
still apply. Photographic-noise compression, history-disabled UI-copy latency
and physical canvas rendering need separate workloads; these figures do not
establish their performance.
