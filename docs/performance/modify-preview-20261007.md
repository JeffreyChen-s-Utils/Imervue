# Modify preview: 2026-10-07

Raw report: [modify-preview-20261007.json](modify-preview-20261007.json).
Same hardware and fixture manifest as [the fixed baseline](baseline-20261007.md).
The report identifies base commit `3cc582cf`, the changed production-source hashes and exact
benchmark hashes; these changes are committed with this report. Source hashes normalize CRLF/LF.

| Metric | 24MP median / p95 ms | 60MP median / p95 ms |
| --- | ---: | ---: |
| UI slider request | 0.21 / 0.34 | 0.27 / 0.32 |
| First accepted preview at ≤640k pixels | 101.37 / 103.40 | 119.14 / 119.35 |
| Full CPU recipe + QImage preparation on worker | 3,719.15 / 3,726.22 | 10,240.16 / 10,395.01 |
| Request to installed full result, including idle debounce | 3,916.32 / 3,926.66 | 10,437.16 / 10,598.37 |
| 10ms UI heartbeat service gap | 9.82 / 12.09 | 9.83 / 11.43 |

The former synchronous Modify refresh blocked the UI for a median 4,985/12,463ms at 24MP/60MP.
Now request callbacks return immediately, approximate pixels arrive first, and full rendering runs
on a worker. The preview uses nearest sampling to avoid Pillow's full-source RGBA premultiplication
allocation; final pixels still run the canonical CPU stages at original resolution.
Controls remain usable during color changes; geometry-changing requests temporarily prevent drawing
until the new coordinate space is installed. Requests are coalesced and obsolete results cannot land
after another edit, image switch or destructive bake.

Sampled operation RSS peaks were 1,898/4,331.5MiB, including source/canvas and full-render temporaries.
This does not make full-resolution CPU processing cheap. Maximum heartbeat gaps were 57.41/165.45ms,
although p95 was ≤12.09ms: GIL acquisition and large temporary allocations can still delay occasional
Python UI callbacks. Saving or starting a destructive effect before full quality is ready explicitly
finishes canonical rendering; that operation can wait. Reduced display pixels are never saved.

The ≤25ms request and ≤300ms first-preview targets pass in this run, as does the full-result
20% regression bound. This is one independent desktop-session run with three requests
(exposure .25/.26/.27 and the same advanced settings), not proof of a small CPU speed gain.
The end-to-end metric includes a 200ms idle debounce, unlike the old direct synchronous refresh;
the new full-compute metric isolates the corresponding recipe/QImage work. Both are retained.
Source/dependency/power/load boundaries from the baseline still apply.

Pure tests compare canonical pixels against `Recipe.apply` through rotations, flips, crop,
tone/color and alpha. Qt tests check thread affinity, latest-only coalescing, path changes,
single failure reporting, fallback, owner destruction, full geometry, saves from reduced previews
and a noninterruptible obsolete backend result after a destructive edit.
