# Thumbnail wall: viewport candidates and bounded loading

Same fixed 1920x1080 shader/FBO/finish workload and hardware as [baseline](baseline-20261007.md).
Each scenario retains 30 unprofiled steady frames, actual pixel checks and VRAM accounting.

| Library | Baseline median / p95 (ms) | Run 1 median / p95 | Run 2 median / p95 |
| --- | ---: | ---: | ---: |
| 10,000 | 12.37 / 17.14 | 7.53 / 8.86 | 8.08 / 10.51 |
| 100,000 | 51.11 / 56.80 | 7.77 / 9.91 | 7.93 / 9.83 |

[Run 1](wall-viewport-20261007.json) measured the implemented behavior; [run 2](wall-viewport-repeat-20261007.json)
also includes the final documentation-only source change. Its recorded production hashes
match the staged source. Both runs meet <=16.7ms for 100k and <=1.2x the same-run 10k p95.
The same 35 visible cached rectangles and 12,233,410-byte texture allocation remain.

Geometry calculates intersecting rows/columns, with one row/column of buffer; exact
visibility still checks actual decoded dimensions, including SVG/full-size extents.
Pure tests reject any whole-model iteration during frame or texture-visibility computation.

Normal-size thumbnails are requested only for visible/buffer cells and explicit filmstrip
or retry requests. Worker objects are bounded by pool slots; a pan discards unstarted old
requests. Progress counts that current workload. Full-resolution mode retains bounded
background discovery because unknown image extents may cross cell boundaries. A managed
queue validates source generations, coalesces active requests and keeps one fresh decode
after a source rewrite. Escape keeps the warm cache and saved grid position.

The GL benchmark excludes QOpenGLWidget/HUD and disk decode. Separate real-pool tests
verify UI-thread completions and cancellation of blocked jobs without a UI wait. Actual GL
regressions check 100k scrolling, fractional/large zoom, hit geometry, selection state and
release within a tiny texture quota. Photographic decoding and RAM admission remain the
separate memory stage; these timings do not measure those costs.

An earlier [experimental run](wall-viewport-busy-20261007.json) had a 100k median/p95 of
692.47/1146.58ms. A contemporaneous WMI probe reported 100% CPU use. The raw result is
retained, rather than treated as comparable evidence of code cost. A diagnostic cProfile
run later recorded 5.93/45.95ms and 6.27s creating its GL context; profiling is excluded from
the fixed comparisons. Subsequent unprofiled runs passed the targets. CPU load coincided
with the anomalous run; these observations do not establish a sole cause for every stall.
Power/thermal state, competing tasks and filesystem caches remain uncontrolled.
