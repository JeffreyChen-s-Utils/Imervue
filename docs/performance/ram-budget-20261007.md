# Viewer prefetch RAM admission — 2026-10-07

Neighbor prefetch now accounts actual pyramid array bytes together with in-flight
decoder reservations, independently of texture VRAM. The process shares 20% of
physical RAM, clamped to 256 MiB–8 GiB, fairly across viewer windows. Optional
psutil absence/probe failure uses a shared 2 GiB fallback. Speculation is skipped
when admission fails; opening that image still uses ordinary foreground loading.

This quota covers speculative neighbor pyramids and their worker/result tickets.
It is not an allocator or a ceiling on process RSS, the foreground image,
thumbnail-wall caches, Paint/Modify buffers or third-party decoder scratch.
Existing reservations survive cancellation; a reduced quota drains caches on
the next scheduling pass and prevents further admission until space is available.

The [raw report](ram-budget-20261007.json) retains every sample, native Windows
WorkingSet/lifetime peak, decoded/refused counts, actual array bytes, peak
accounted bytes, fixture digests and normalized measured source/tool hashes.
The host is the same Ryzen 5 240 machine with 31.31 GiB usable RAM; GL is not used.

| Fresh process, three samples | Median / p95 ms | Sampled RSS peak MiB | Decoded per run |
|---|---:|---:|---:|
| Nikon RAW only | 1549.81 / 1726.98 | 274.65 | 1 |
| 60MP panorama only | 2142.26 / 2258.98 | 705.54 | 1 |
| RAW + panorama, no admission | 2352.37 / 2438.91 | 785.87 | 2 |
| RAW + panorama, 2 GiB admission | 1853.03 / 2132.07 | 704.16 | 1 |
| RAW + panorama, 3 GiB admission | 2538.54 / 2630.16 | 802.38 | 2 |

RAW is a supplied 4940×3292 camera file from the pinned
[rawpy test fixture](https://github.com/letmaik/rawpy/blob/a39c2e7a44911889c3360891012f862f904ba551/test/iss042e297200.NEF).
The local file is not redistributed. Panorama is a deterministic 30000×2000 RGB
gradient JPEG (quality 90), generated with the existing benchmark helper; it
does not establish photographic-entropy performance. RAW header admission uses
libraw sensor dimensions, not the embedded preview or compressed file size.

Reservations are 780,599,040 bytes for RAW and 1,440,000,000 for the panorama.
Actual retained pyramids are 86,392,368 and 315,000,000 bytes. All three 2 GiB
runs peak at 1,440,000,000 accounted bytes and skip one decode; all three 3 GiB
runs peak at 2,220,599,040 and decode both. A refused job does not wait in a
decoder thread. The two-GiB duration cannot be presented as a speedup for the
same work. The three-GiB result stays within 20% of the matching unbounded p95;
three desktop samples do not justify a smaller timing claim.

Header probing and the estimates (24 bytes/pixel for rasters, 48 for RAW,
160 for nonidentity recipes, 512 MiB for unknown dimensions) run on workers.
These conservative estimates are admission policy, not guarantees about every
codec's scratch allocations. Result delivery retains an actual-byte ticket and
atomically exchanges it for cache accounting. Stale generations/identities,
errors, aborts and owner destruction release the appropriate tickets without
forgetting running decoders. Cache admission rejects a single oversized result
before evicting useful smaller entries.

To reproduce, provide the pinned RAW as `raw.NEF`, and generate `panorama.jpg`
with `Image.fromarray(gradient(30000, 2000)).convert('RGB').save(..., quality=90)`
from `scripts/performance_support.py`. Run each case in a fresh process:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/performance_ram.py raw.NEF --output raw.json
.venv\Scripts\python.exe -X utf8 scripts/performance_ram.py panorama.jpg --output panorama.json
.venv\Scripts\python.exe -X utf8 scripts/performance_ram.py raw.NEF panorama.jpg --output unbounded.json
.venv\Scripts\python.exe -X utf8 scripts/performance_ram.py raw.NEF panorama.jpg --limit-mib 2048 --output bounded-2gib.json
.venv\Scripts\python.exe -X utf8 scripts/performance_ram.py raw.NEF panorama.jpg --limit-mib 3072 --output bounded-3gib.json
```

The tool owns a fresh temporary profile and retains decoded results during each
sample. It never downloads or modifies input images. It uses two real worker
bodies with a direct collector to measure decoding and memory; independent
QObject/QThreadPool tests cover queued UI delivery, blocked cancellation,
source replacement, foreground promotion, errors and window destruction.
Unrelated host activity/power/thermal state remain uncontrolled. An earlier
experiment while full-suite tests ran had larger timings; the final report was
measured after that workload ended and is used for this comparison.
