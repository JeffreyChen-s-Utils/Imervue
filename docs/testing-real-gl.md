# Workspace lifecycle and actual OpenGL regressions

The `real-gl` job in `.github/workflows/test.yml` uses Ubuntu 24.04, Python 3.12,
Xvfb and Mesa software rendering. It runs actual OpenGL contexts, shaders,
framebuffers, pixel reads and texture deletion; it measures correctness rather
than hardware GPU throughput. Windows fast/gui/integration jobs retain the
existing offscreen crash guard. The independent job sets `CI=false` and the
`xcb` platform only within its own environment.

The job explicitly installs the XCB runtime extensions and uses `ldd` on the
Qt XCB/GLX plugins before constructing QApplication. Missing shared libraries
fail this preflight; uncaptured test output retains Qt platform diagnostics.
The library categories follow [Qt's Linux platform requirements](https://doc.qt.io/qt-6/linux-requirements.html).

The selected ten cases cover full-budget thumbnail scrolling in both directions,
100k zoom/hit geometry, actual texture-handle release, two real viewer windows,
Paint edits across Viewer/Modify/Paint, independent document history and masks,
background multidocument saves and recovery, cancelling a dirty-tab close,
closing during a write, damaged image handoff, disk-full and permission errors.
Failure injection uses real workers/native snapshots and preserves the previous
valid snapshot and live dirty document.

`scripts/verify_gl_report.py` requires at least ten executed successful cases,
no skipped/failed/error cases, and a recorded actual GL renderer. The job keeps
its JUnit report in `real-gl-linux-python312` for seven days and gates dev
publication. Missing GL support is a failure, not a successful skip. Mesa CI
does not substitute for testing a vendor driver's behavior on a local desktop.

Run the same selection locally with a real desktop GL context:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_tile_textures_gl.py tests/test_workspace_lifecycle_gl.py tests/test_paint_auto_save.py::test_background_dirty_tab_and_multiple_document_recovery tests/test_main_window_layout.py::test_returning_to_paint_keeps_edited_layers_dirty_state_and_undo -v -o junit_family=xunit1 --junitxml=real-gl.xml -p no:unraisableexception
.venv\Scripts\python.exe -X utf8 scripts/verify_gl_report.py real-gl.xml
```

Use a normal desktop platform and unset a pre-existing `CI=true` for this local
selection. A Linux host can run it under `xvfb-run` as in the workflow. Keep the
headless skip marker on GL test modules; it protects the regular Windows jobs.

The regular suite additionally executes
`tests/test_autosave_crash_integration.py` in fresh offscreen child processes.
Two background document saves finish, then a third process exits with code 23
between the native bundle write and metadata commit. A fresh process recovers
both prior coherent versions into independent dirty tabs, ignores the orphan
bundle and does not restore them twice. Only the supplied test scratch directory
and isolated settings/plugin profile are touched.

## Confirmed remote execution

On 2026-10-07, commit `1431a2e7a56c48fe370332c1a3cccd960a8a0b58` passed all required CI jobs, including [actual Linux OpenGL](https://github.com/JeffreyChen-s-Utils/Imervue/actions/runs/37616163546/job/112774884736). The downloaded JUnit artifact passed `verify_gl_report.py`: ten executed cases, zero skipped/failed/errored, with `llvmpipe (LLVM 20.1.2, 256 bits)` recorded by the actual test contexts. Remote test execution took 4.99s. XCB and GLX wheel dependency preflight reported no missing libraries. This confirms the added platform runtime configuration; it does not establish which individual missing component caused the earlier abort.
