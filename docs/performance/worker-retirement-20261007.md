# Worker cancellation and dialog retirement — 2026-10-07

Cancel/OK/window-close now return to the UI immediately. The dialog disables
controls and shows Cancelling (or Finishing for a custom successful result)
in its title. A retained retirement thread calls cancellation hooks and joins
actual workers, then queued completion finishes the first requested result.
Workers are reparented away from a possibly destroyed dialog. Late results
cannot change an already requested rejection into acceptance.

Before this change, three real-QThread tests with a controlled 250ms
uninterruptible boundary gave UI close times of 257.29, 262.47 and 265.06ms.
The worker waited for cancellation and then spent 250ms returning from its
current operation. This is an explicit lifetime probe, not real decoder or
model throughput. Afterward, the reproducible benchmark uses the same boundary
and separately tests a `stop()` hook that itself blocks for 250ms.

| Probe | UI request median / p95 ms | Actual retirement median / p95 ms | 10ms heartbeat median / p95 ms |
|---|---:|---:|---:|
| Uninterruptible decode/inference/I/O boundary | 0.35 / 1.02 | 257.34 / 257.93 | 10.08 / 11.36 |
| Blocking cancellation hook | 0.28 / 0.40 | 267.83 / 276.77 | 15.57 / 16.52 |

Both UI request p95 values meet the 50ms threshold while the real QThread
remains alive for at least 250ms. Maximum heartbeat intervals were 22.71 and
23.81ms. The second probe's roughly 15ms timer cadence reflects observed
Windows scheduling; it does not establish a codec speedup or a hard realtime
latency guarantee. Adding a new visible label initially triggered a measured
139–207ms native layout/show delay; using the existing window title avoids that
extra resize work in the cancellation request.

[Raw report](worker-retirement-20261007.json) retains every sample, environment,
measured source/tool hashes and parent revision. The benchmark runs in a fresh
isolated profile without user plugins/settings, with actual QDialog/QThread
objects and no OpenGL widget. Reproduce:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/performance_workers.py --output worker-report.json --repeats 3
```

The cancellation hooks in bundled QThread consumers were inspected: batch
export, duplicate scan, EXIF strip, organizer, sanitize and GIF/video set abort
flags; background-removal and object-splitter subprocess workers terminate their
child. No hook accesses GUI widgets. Hooks now run off the UI thread and must
remain thread-safe. Exceptions are logged and cannot skip the lifetime join.
The shared `finalize_worker()` also retains a worker whose custom done packet
precedes actual thread/TLS exit, without cancelling a successful output.

Tests exercise real modal completion, accept/reject/close/direct done, heartbeat
while a hook blocks, multiple workers, duplicate attributes, failed hooks,
already queued accept, deleted owner, clean reopen, successful passive
retirement, TLS polling and final exit draining. Non-Qt duck-typed adapters
retain their synchronous teardown API. Final application event-loop exit
joins outstanding retirement threads for safe process shutdown; that final
exit wait is excluded from the interactive dialog-cancellation measurement.
