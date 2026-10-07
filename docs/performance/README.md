# Developer performance measurements

Run from a checkout with the project's development dependencies. This tool is not a shipped CLI command.
Keep the same hardware, power mode, display driver, fixture manifest and sample count when comparing revisions.
Stop this project's tests and other foreground work during measurement; record external desktop load separately.

```powershell
.venv\Scripts\python.exe -X utf8 scripts/performance_benchmark.py `
  --fixtures .git/performance-baseline-v1 `
  --output docs/performance/baseline-20261007.json --repeats 3
```

`--quick` creates 100/1,000-entry libraries, 0.24/0.6MP images and a 384×216 document for smoke tests only.
Use a separate fixture directory for that mode. `--only` selects scenarios from the help output.
Each scenario runs in a fresh child with a new profile; settings, library DB, recipes, plugins,
autosaves and thumbnail cache are isolated before application imports. Existing directories without
an ownership manifest are refused. Changed seed/large-image hashes are refused; files are never
recursively deleted. Interrupted preparation can resume in its manifest-owned directory.
Hard links are used where supported and copied files otherwise (including NTFS's per-file link limit).
Results are atomically replaced after every scenario; failed scenarios stay visible and give a failing exit code.

| Scenario | Actual application path measured | Boundary |
| --- | --- | --- |
| Startup | QApplication, imports and hidden ImervueMainWindow construction; additional warm windows | Empty isolated profile, optional plugins disabled; excludes first widget paint and OS process launch |
| 10k / 100k library | LibraryScanner, SQLite cold/incremental scan, 100-result search, in-progress cancellation | Unique paths to 32 repeated 32×24 JPEG seeds; pHash disabled; cancellation starts at the first emitted chunk progress |
| 24MP / 60MP | Viewer decode; full GL upload, shader draw and finish; DevelopPanel creation and advanced recipe refresh | 6,000×4,000 / 10,000×6,000 JPEG gradients; hidden canvas; no HUD, window compositor or physical screen latency |
| 4K Paint | Six 3,840×2,160 RGBA layers; Undo baseline, three 32×32 strokes, Undo/Redo, autosave and recovery | Deterministic gradients compress more easily than photographic noise; three commits, not a 50-snapshot stress run |
| Disk cache | ThumbnailDiskCache constructors with empty and 100k-entry cache | Repeated small PNG payloads isolate directory/stat overhead; this is not a 100k full-size thumbnail storage benchmark |
| 10k / 100k GL wall | TileGridRenderer in a real 1,920×1,080 FBO; first upload plus 30 steady frames | Bounded visible/buffer thumbnails; real GPU/shaders/glFinish, pixel readback checked; excludes QOpenGLWidget/HUD |

“Cold” means a fresh child/profile/index or first use of a component. **The OS page cache is not flushed.**
Decode precedes image-frame measurement, so that frame explicitly has a warm file cache.
Startup's import/constructor total includes QApplication initialization; constructor-only timing excludes imports.
Warm startup constructs additional live windows, so its RSS includes those windows. All scenario names,
boundaries and input hashes accompany the raw data instead of implying one end-to-end launch measurement.

Timing uses `perf_counter`; the report retains raw milliseconds and nearest-rank p95 (three samples make
p95 the maximum). RSS is sampled every 5ms; sub-5ms transients can be missed. Windows additionally reports
the process-lifetime peak working set using native counters. Absolute RSS, growth and lifetime peak are
separate values: lifetime peak may include setup or earlier operations. Linux uses `/proc` plus `resource`;
macOS uses its resident high-water mark when a current-RSS counter is unavailable.

The baseline report includes revision, tool hashes, fixture hashes, interpreter/dependency versions and
actual GL renderer. Windows also records CPU, installed RAM and available GPUs. A laptop's power/thermal
state and unrelated background processes are not controlled by this tool. Run at least three independent
reports before declaring a small speedup; no hardware-specific timing assertion runs in ordinary CI.
RAW camera files, model inference, SSD cold-cache behavior, photographic entropy and a physical UI session
need separate supplied workloads; the synthetic fixture does not establish their performance.

After the background-preview change, Modify measurements separately retain UI request time,
accepted reduced-preview latency, full recipe/QImage compute time and request-to-installed-full
latency (including idle debounce). A 10ms Qt heartbeat records service gaps, including maximum stalls.
Small smoke images may already be full quality and have no reduced metric. The reports include
changed production-source hashes when measuring a working tree before its commit; source hashes
normalize checkout line endings. [Modify results](modify-preview-20261007.md) document the boundaries.

Paint now also records retained history bytes after the same three 32x32 edits. The
benchmark supplies the complete damage rectangle, as the production brush/eraser
dispatcher does; unknown edits retain full-array comparison. Repeated synthetic gradient
tiles favor interning, so a separate non-repeating six-layer pixel test guards the storage
reduction without that advantage. [Paint history results](paint-history-20261007.md)
include this workload boundary.

[Thumbnail wall results](wall-viewport-20261007.md) compare the same 10k/100k actual GL
frames with shared row/column candidates, retaining two independent runs and the earlier
overloaded-host anomaly. Decode admission and cancellation are guarded by separate real
pool tests; the frame workload continues to exclude disk decode and widget/HUD drawing.

[Prefetch RAM results](ram-budget-20261007.md) use a supplied real camera RAW and
a synthetic 60MP panorama. `scripts/performance_ram.py` measures two real decoder
threads in a fresh isolated profile, retaining native RSS, actual arrays, quota
reservations and decoded/refused counts. RAM admission is separate from VRAM;
skipping speculation is reported separately from completing the same workload.

## Acceptance policy

The fixed baseline and stage-specific targets are recorded in [baseline-20261007.md](baseline-20261007.md).
Acceptance requires correctness and memory bounds first, then a repeat run on the same fixtures.
Ratios compare the same metric and sample count; no substitution of decoder timing for display timing.
An optimization must retain color/alpha/geometry checks, recovery fidelity, cancellation lifetime safety,
and results under cache pressure. A target is a requirement, not a claim that it has already been reached.

`tests/test_performance_benchmark.py` covers ownership/digest rejection, deterministic pixels,
sample validation, native RSS, sampler cleanup, atomic reports, partial-failure continuation,
real child indexing/history/cache and actual GL source-pixel rendering. Real GL cases use the existing
headless skip policy; unavailable GL is a benchmark failure, not a fabricated successful result.
