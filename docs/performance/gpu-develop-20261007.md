# GPU Develop: measured speed and canonical color decision

Keep Modify previews on the canonical CPU renderer. New Batch Export dialogs default to CPU;
GPU remains an explicit optional accelerator. Enabled threshold or posterize now render the whole
recipe on CPU. The real GPU can be much faster, but mixed color stages are not byte-identical and
a downstream discontinuity amplified a 1-level difference into a 255-level output difference.

Hardware: NVIDIA GeForce RTX 5060 Laptop GPU (Vulkan), AMD Ryzen 5 240 / Radeon 760M,
Windows 11 build 26300, Python 3.14.4, wgpu 0.32.0. Actual adapter selection used the existing
discrete-only policy. Three samples per timing, fresh child per size; nearest-rank p95 is the
maximum. OS caches, external desktop load and laptop power/thermal state are not controlled.

| Final render workload | CPU p95 | GPU p95 | Median speed ratio | Max RGB byte difference |
| --- | ---: | ---: | ---: | ---: |
| preview / basic | 110.01 ms | 4.26 ms | 31.95× | 1 |
| preview / advanced | 285.58 ms | 113.22 ms | 2.44× | 3 |
| 24mp / basic | 5692.42 ms | 158.54 ms | 39.74× | 1 |
| 24mp / advanced | 11870.72 ms | 4897.07 ms | 2.39× | 3 |
| 60mp / basic | 19814.21 ms | 418.72 ms | 52.47× | 1 |
| 60mp / advanced | 26822.28 ms | 10340.32 ms | 2.42× | 3 |

Basic is the existing preview color recipe (exposure .25, temperature .1, shadows .1, vibrance .1).
Advanced adds contrast, saturation, a tone curve, split toning, levels and channel mixer. Geometry,
ICC decoding, LUT, masks and later stages stay in the CPU/core pipeline. GPU timing includes plan
creation, host copies, full buffer upload/readback and CPU remainder; it is not just shader time.
The 640k sample is a fixed 800×800 gradient; full inputs are the same hashed baseline-v1 JPEGs.
CPU and GPU RSS include a retained CPU reference. Dedicated VRAM is not measured. No memory
reduction, physical-display latency, Qt event-loop service time or sustained FPS claim is made.

GPU device/pipeline opening alone took 1.27–1.44 seconds in these children. Small color cases
warm the shader before the first timed image; first_gpu_render measures that image’s buffer/setup
cost, not first-ever driver launch. Before/after CPU timings vary substantially although the
CPU Recipe source hash is unchanged, so no small relative performance change is attributed to
the guard. The large CPU/GPU difference is a workload observation, not a universal guarantee.

| Display P3 converted once to sRGB, seeded random RGBA | Before max RGB error | Final max RGB error | Final path |
| --- | ---: | ---: | --- |
| identity | 0 | 0 | identity |
| table_exposure | 0 | 0 | gpu |
| basic | 1 | 1 | gpu |
| advanced | 3 | 3 | gpu |
| threshold_after_mixed | 255 | 0 | cpu_reference |

On this 128×256 color fixture, basic mixed operations differed in 3 RGB channels by 1 level;
advanced differed in 862 channels (0.877%) by up to 3 levels. Threshold previously changed two
pixels completely (6 RGB channels, max 255). Its final exact output comes from the full CPU
reference, not newly exact GPU arithmetic. Alpha is unchanged in every measured case.
Posterize has the same discontinuous-boundary risk and uses the same conservative guard.
Other recipes remain GPU approximations; downstream LUTs, extreme levels or other nonlinear
operations can amplify differences. Choose CPU when canonical pixel values matter. The existing
single-stage/mixed GPU test tolerances are fixture checks, not bounds on every possible recipe.

## Canonical color and fallback validation

Normal CI tests require no GPU or wgpu for the new guards. They verify explicit GPU selection and
CPU default, plus sRGB / Display P3 / Gray Gamma 1.8 sources × all/no_location/none metadata ×
basic/advanced/threshold recipes. EXIF orientation is applied once; full CPU preview equals
CPU export; lossless PNG re-decode is identical and preserves alpha. Original input files and
arrays stay unchanged. Output ICC is sRGB, never the original wider-gamut/gray profile; none
exports remain untagged sRGB numbers. A real local radial mask, LUT, crop/rotation/flip case
also compares full preview/export. Reduced previews remain approximations and are never saved.
Injected device-loss, memory and driver errors return canonical CPU pixels without modifying
the source. Existing hardware shader, slicing and discrete-adapter policy tests also ran locally
with no GPU-test skips; missing packages/devices and provider open failures retain CPU fallback.

The edit pipeline is uint8 sRGB, not linear-light/HDR or a wide-gamut document model. ICC
normalization and RAW decoding remain core responsibilities. GPU Develop carries no model
weights; wgpu stays optional and plugin-local. AI colorization, denoise, outpainting and CLIP
keep their separate dependency/model probes and worker lifecycle. No weights are moved into
core or downloaded by this assessment. GPU-to-Qt preview integration is intentionally not
adopted: canonical full-preview fidelity is required and the existing CPU coalescing/cancellation
scheduler remains the chosen preview path. This is the completed implementation decision.

## Reproduce

```powershell
.venv\Scripts\python.exe -X utf8 scripts/gpu_develop_benchmark.py --fixtures .git/performance-baseline-v1 --output gpu.json --repeats 3
```

Raw before/after reports and their per-size child reports accompany this file. Production
source hashes use LF normalization. The final report also records the benchmark AST hash;
lint-only line wrapping after measurement preserves that AST. No hardware-specific timing
assertion is added to ordinary CI.
