# Observed plugin availability and failure recovery

Manage Plugins combines window-scoped load outcomes with shared resource states. Loaded only means
the plugin initialized; optional imports, weights and devices are checked when selected. Status
rows retain original error reasons, selected tool model/backend/mode text, CLIP cache paths,
backend CPU fallback and downloading/installed outcomes. No speculative heavyweight import at startup.

| Capability family | Dependencies / model acquisition | Available fallback and failure boundary |
|---|---|---|
| GPU Develop | Optional wgpu, discrete GPU only, no weights | Recipe CPU reference; provider probe/open/per-image runtime failure reported |
| ONNX denoise, deblur, colorize, style, relight, object remove, outpaint | Optional onnxruntime; user models discovered in writable models directory | Existing deterministic/heuristic modes where offered; selected missing/invalid model fails that image, shared tools retain option/error |
| Background remover, object splitter, portrait | Optional rembg/onnxruntime; rembg may acquire selected weights on first session | Existing dialog reports model/session error; frozen subprocess isolation remains, no promise of precise download percentage from third-party backend |
| Safety review / segmentation / training | Optional detector/training packages, pinned Hugging Face weights or user model, optional precise segmentation weights | Existing backend-specific dialogs/subprocess error reporting and coarse fallback unchanged |
| NPR filters, smart resize, video | Optional OpenCV/backend packages for selected feature | Shared dependency gate and existing feature-level failure, no startup import |
| Cloud share / pet integrations | Selected optional client/service packages and account settings | Existing service errors remain feature-level; host load status does not promise network credentials |
| Icon converter / language plugins | Core Pillow / dictionaries, no downloaded weights | Host import/initialization errors shown per window |
| Built-in CLIP semantic tools | Optional ONNX/Hub; pinned revision model files | Shared model download/cache availability and failures, CUDA/CPU preference unchanged |

Shared ToolDialogMixin publishes running/available/failed/cancelled with captured dropdown choices;
failed-only job retries carry those choices. Custom third-party dialogs retain their own detailed
progress; their optional states are not inferred from the word Loaded. Manage Plugins exposes
backend/device and shared dependency reasons and preserves all existing feature progress UI.

One installer per plugin destination/interpreter is allowed in this process. Unique directory
stages preserve the current installation on download/cancel/compatibility failure; a backup allows
rollback when commit fails. Models/assets are copied into the stage before commit. A cleanup failure
can leave a backup and is logged. Reservations do not coordinate independent processes.
After normal or background-job retry download, installed means files committed, not activated:
Reload Plugins in each window or restart. No automatic reload can interrupt another window's tool.
Fresh imports discard only plugin modules/bytecode. API-3 GPU provider generations are independently
leased; loading/reloading/closing one window does not unregister another generation.
Dependency cancellation retains running QThreads off the UI thread and terminates active pip
children there; uninterruptible package imports/downloads are retained until actual exit.
Installing into an interpreter is not globally transactional and cancellation may leave packages
already successfully installed. Import failure or callback failure keeps the dialog retryable.

GPU Develop has no model weights and keeps wgpu optional in its flat plugin. CPU is now
the default of new Batch Export dialogs, matching Modify’s canonical 8-bit sRGB preview.
GPU color mixing is an approximation: enabled threshold/posterize force the entire recipe
through the CPU reference because a 1-byte intermediate error can become a 255-byte edge
difference. GPU open/per-image runtime errors retain CPU fallback; integrated/software devices
remain excluded. See performance/gpu-develop-20261007.md for actual hardware and limits.
