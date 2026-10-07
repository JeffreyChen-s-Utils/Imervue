"""Reproducible developer benchmark; see docs/performance/README.md for boundaries.

Run from the repository root using the project's environment, never an installed release.
Each scenario runs in a fresh child and only touches manifest-owned fixtures or a new profile.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.performance_support import (  # noqa: E402
    gradient, isolated_profile, measure, prepare_fixtures, summarize, write_json,
)

SCENARIOS = ("startup", "library-small", "library-large", "image-24mp", "image-60mp",
             "paint", "cache", "wall-small", "wall-large")


def _application():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def startup(_fixture: Path, _profile: Path, repeats: int) -> dict:
    # Constructor readiness is separate from first GL frame below. The user's optional
    # plugin directory is intentionally not loaded into the benchmark profile.
    start = time.perf_counter()
    app = _application()
    from Imervue.Imervue_main_window import ImervueMainWindow
    windows = []

    def construct():
        window = ImervueMainWindow()
        windows.append(window)

    cold = measure(construct, repeats=1)
    cold["import_and_constructor_ms"] = (time.perf_counter() - start) * 1000
    warm = measure(construct, repeats=repeats)
    # Keep all QObject owners alive until the parent captures JSON; the child then
    # exits without invoking the application's last-window closeEvent/os._exit.
    app._benchmark_windows = windows
    return {"cold_constructor": cold, "warm_constructor": warm,
            "boundary": ("fresh profile; optional plugins disabled; "
                         "hidden window construction, no first paint")}


def library(fixture: Path, profile: Path, repeats: int, *, large: bool) -> dict:
    from Imervue.library import image_index
    from Imervue.library.scanner import LibraryScanner
    manifest = json.loads((fixture / "manifest.json").read_text())
    count = manifest["libraries"][int(large)]
    source = fixture / f"library-{count}"
    image_index.set_db_path(profile / "catalog.db")
    failures = []

    def scan():
        scanner = LibraryScanner([str(source)], with_phash=False)
        scanner.error.connect(failures.append)
        scanner.run()
        if failures:
            raise RuntimeError(failures[-1])

    try:
        cold = measure(scan, repeats=1)
        warm = measure(scan, repeats=repeats)
        indexed = image_index.count_images()
        if indexed != count:
            raise RuntimeError(f"index count {indexed}, expected {count}")
        query = image_index.ImageQuery(name_contains="image-", limit=100)
        search = measure(lambda: image_index.search_images(query), repeats=30)
        # Cancel after real work has started, on the emitting worker thread. This
        # measures return from an in-progress scan, including its pool shutdown.
        cancellations = []

        def cancel_scan():
            scanner = LibraryScanner([str(source)], with_phash=False)
            requested = []

            def cancel(*_args):
                if not requested:
                    requested.append(time.perf_counter())
                    scanner.cancel()

            scanner.progress.connect(cancel)
            scanner.run()
            if not requested:
                raise RuntimeError("scan completed before a cancellation point")
            cancellations.append((time.perf_counter() - requested[0]) * 1000)

        measure(cancel_scan, repeats=repeats)
        return {"count": indexed, "cold_index": cold, "warm_index": warm, "search": search,
                "cancel_after_progress": summarize(cancellations),
                "boundary": "metadata index (pHash disabled); cancel at first real chunk progress"}
    finally:
        image_index.close()


def image(fixture: Path, profile: Path, repeats: int, *, label: str) -> dict:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMainWindow, QSplitter
    from Imervue.gui import develop_panel
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import RecipeStore
    from Imervue.gpu_image_view.images.image_loader import decode_image_file
    app = _application()
    source = fixture / f"{label}.jpg"
    decoded = []

    def decode():
        decoded[:] = [decode_image_file(str(source))]

    cold = measure(decode, repeats=1)
    warm = measure(decode, repeats=repeats)
    shape = list(decoded[0].shape)
    decoded.clear()
    from scripts.performance_gl import first_image_frames
    display = first_image_frames(str(source), repeats)
    develop_panel.recipe_store = RecipeStore(store_path=profile / "recipes.json")
    window = QMainWindow()
    panel = develop_panel.DevelopPanel(SimpleNamespace(
        main_window=window, reload_current_image_with_recipe=lambda: None))
    splitter = QSplitter(Qt.Orientation.Horizontal)
    panel.build_left_panel(splitter)
    panel.build_right_panel(splitter)
    first = measure(lambda: panel.bind_to_path(str(source)), repeats=1)
    panel._current = Recipe(exposure=.25, temperature=.1, shadows=.1, vibrance=.1)
    preview = _measure_modify(panel, app, repeats)
    # Event-loop service gap: the synchronous refresh prevents any pending Qt
    # event from being serviced for at least its call duration.
    result = {"shape": shape, "cold_decode": cold, "warm_decode": warm, "gl_display": display,
              "first_modify_canvas": first, **preview,
              "boundary": "real DevelopPanel refresh, advanced recipe; QImage ready, hidden canvas"}
    panel._destroy_canvas()
    app.processEvents()
    return result


def _measure_modify(panel, app, repeats: int) -> dict:
    """Time requests, accepted reduced results and the final installed full image."""
    from PySide6.QtCore import QTimer
    request_times, low_times, full_times, gaps = [], [], [], []
    started = [0.0]
    last_tick = [time.perf_counter()]

    def tick():
        now = time.perf_counter()
        gaps.append((now - last_tick[0]) * 1000)
        last_tick[0] = now

    def ready(result):
        if not result.pixels.full_quality:
            low_times.append((time.perf_counter() - started[0]) * 1000)
        else:
            full_times.append(result.render_ms)

    heartbeat = QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(tick)
    heartbeat.start()
    panel._preview.result_ready.connect(ready)
    iteration = [0]

    def refresh():
        panel._current.exposure = .25 + iteration[0] * .01
        iteration[0] += 1
        started[0] = time.perf_counter()
        panel._schedule_preview()
        request_times.append((time.perf_counter() - started[0]) * 1000)
        deadline = time.perf_counter() + 90
        while panel._canvas_recipe != panel._current or not panel._preview.is_idle:
            if time.perf_counter() > deadline:
                raise TimeoutError("Modify preview did not finish")
            app.processEvents()
            time.sleep(.001)

    try:
        complete = measure(refresh, repeats=repeats)
        return {"modify_preview": complete, "modify_ui_request": summarize(request_times),
                "modify_reduced_ready": summarize(low_times) if low_times else None,
                "modify_full_compute": summarize(full_times),
                "modify_heartbeat_gap": summarize(gaps) if gaps else None,
                "preview_recipe": "exposure .25/.26/.27; temperature .1, shadows .1, vibrance .1"}
    finally:
        heartbeat.stop()
        panel._preview.result_ready.disconnect(ready)


def paint(fixture: Path, profile: Path, repeats: int) -> dict:
    from Imervue.paint.document import PaintDocument
    from Imervue.paint.undo_stack import UndoStack
    from Imervue.paint.damage import DamageRect
    from Imervue.paint.auto_save import write_snapshot, recover_snapshot
    manifest = json.loads((fixture / "manifest.json").read_text())
    width, height = manifest["paint_dimensions"]
    document = PaintDocument()
    document.load_image(gradient(width, height))
    for i in range(manifest["paint_layers"] - 1):
        layer = document.add_layer(name=f"Layer {i}")
        layer.image[:] = gradient(width, height, i + 1)
        layer.opacity = .8
    stacks = []
    seed = measure(lambda: stacks.append(UndoStack(document)), repeats=1)
    stack = stacks[0]

    def stroke():
        array = document.active_layer().image
        array[10:42, 10:42, 0] ^= 1
        stack.commit(regions=((array, DamageRect(10, 10, 32, 32)),))

    commit = measure(stroke, repeats=repeats)
    history_bytes = stack.history_bytes
    undo = measure(stack.undo, repeats=repeats)
    redo = measure(stack.redo, repeats=repeats)
    snapshots = []
    save = measure(lambda: snapshots.append(write_snapshot(
        document, directory=profile / "autosaves", document_id="benchmark")), repeats=repeats)
    recover = measure(lambda: recover_snapshot(snapshots[-1]), repeats=1)
    from scripts.performance_autosave import background_autosave
    background = background_autosave(
        _application(), document, stack, profile / "background-autosaves", repeats,
    )
    return {"shape": [height, width], "layers": document.layer_count,
            "layer_bytes": sum(layer.image.nbytes for layer in document.layers()),
            "history_bytes_after_strokes": history_bytes,
            "undo_seed": seed, "stroke_commit": commit, "undo": undo, "redo": redo,
            "autosave_compress_write": save, "autosave_recover": recover,
            "background_autosave": background,
            "bundle_bytes": snapshots[-1].bundle_path.stat().st_size,
            "boundary": ("six gradient RGBA layers; 32x32 edit; "
                         "compression easier than photographic noise")}


def _cache_measure(factory, repeats: int) -> tuple[dict, dict, int]:
    """Measure each constructor separately and join its inventory before the next sample."""
    import time
    from performance_support import summarize
    constructor_ms, instances = [], []

    def complete():
        start = time.perf_counter()
        instance = factory()
        constructor_ms.append((time.perf_counter() - start) * 1000)
        ready = getattr(instance, "wait_ready", None)
        try:
            if ready is not None and not ready(60):
                raise TimeoutError("Thumbnail inventory did not finish")
        finally:
            close = getattr(instance, "close", None)
            if close is not None:
                close()
        instances[:] = [instance]

    phase = measure(complete, repeats=repeats)
    return {**phase, **summarize(constructor_ms)}, phase, len(instances[-1]._files)


def cache(fixture: Path, profile: Path, repeats: int) -> dict:
    from unittest.mock import patch
    from Imervue.image import thumbnail_disk_cache as module
    empty = profile / "empty-cache"
    empty.mkdir()
    with patch.object(module, "_get_cache_dir", return_value=empty):
        cold, _cold_phase, _ = _cache_measure(module.ThumbnailDiskCache, 1)
        warm, _warm_phase, _ = _cache_measure(module.ThumbnailDiskCache, repeats)
    with patch.object(module, "_get_cache_dir", return_value=fixture / "large-cache"):
        full, phase, entries = _cache_measure(module.ThumbnailDiskCache, repeats)
    return {"empty_cold": cold, "empty_warm": warm, "large_cache": full,
            "inventory_completion": phase, "entries": entries,
            "boundary": "constructor latency excludes scanner join; inventories run sequentially; "
                        "phase RSS includes inventory; quota fits all tiny PNG fixtures"}


def _wall_view(context, surface, count: int):
    import numpy as np
    from Imervue.gpu_image_view import tile_textures
    from Imervue.gpu_image_view.gl_renderer import GLRenderer
    from Imervue.gpu_image_view.tile_layout import tile_grid_layout
    renderer = GLRenderer()
    renderer.init()
    renderer.set_ortho(1920, 1080)
    images = [f"image-{i}" for i in range(count)]
    _, cell, cols = tile_grid_layout(1920, 256, 1, 8, 1)
    first = (count // (2 * cols)) * cols
    array = np.full((256, 256, 4), 255, dtype=np.uint8)
    view = SimpleNamespace(
        model=SimpleNamespace(images=images),
        tile_cache={path: array.copy() for path in images[max(0, first - cols):first + cols * 7]},
        thumbnail_size=256, tile_scale=1, tile_padding=8,
        grid_offset_x=0, grid_offset_y=-(first // cols) * cell,
        width=lambda: 1920, height=lambda: 1080, devicePixelRatio=lambda: 1,
        tile_textures={}, _tile_tex_sizes={}, _vram_usage=0, _vram_limit=64 * 1024 * 1024,
        _tile_uploader=None, renderer=renderer, _tile_load_times={}, offline_paths=set(),
        tile_selection_mode=False, focused_tile_index=-1,
        _drag_selecting=False, _drag_start_pos=None, _drag_end_pos=None)

    @contextlib.contextmanager
    def current():
        if not context.makeCurrent(surface):
            raise RuntimeError("lost OpenGL context")
        yield

    view._current_gl_context = current
    view._ensure_tile_texture = (
        lambda path, data: tile_textures.ensure_tile_texture(view, path, data))
    view._evict_tile_textures_if_needed = lambda: tile_textures.evict_if_needed(view)
    return view


def wall(fixture: Path, _profile: Path, repeats: int, *, large: bool) -> dict:
    from OpenGL import GL
    from Imervue.gpu_image_view.tile_grid_renderer import TileGridRenderer
    from Imervue.gpu_image_view import tile_textures
    from scripts.performance_gl import framebuffer, release_renderer
    app = _application()
    count = json.loads((fixture / "manifest.json").read_text())["libraries"][int(large)]
    with framebuffer(1920, 1080) as (context, surface):
        view = _wall_view(context, surface, count)
        renderer = TileGridRenderer(view)

        def frame():
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            renderer.paint()
            GL.glFinish()

        try:
            first = measure(frame, repeats=1)
            steady = measure(frame, repeats=max(30, repeats))
            pixel = GL.glReadPixels(128, 1080 - 128, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            if list(pixel) != [255, 255, 255, 255] or GL.glGetError() != GL.GL_NO_ERROR:
                raise RuntimeError("wall did not render the expected visible pixel")
            return {"count": count, "viewport": [1920, 1080], "first_gl_frame": first,
                    "steady_gl_frame": steady, "vram_bytes": view._vram_usage,
                    "visible_rects": len(view.tile_rects), "pixel_rgba": list(pixel),
                    "renderer": GL.glGetString(GL.GL_RENDERER).decode(),
                    "version": GL.glGetString(GL.GL_VERSION).decode(),
                    "boundary": ("real shader/FBO/finish, bounded visible thumbnails; "
                                 "excludes QOpenGLWidget/HUD")}
        finally:
            tile_textures.delete_all_tile_textures(view)
            release_renderer(view.renderer)
            app.processEvents()


def dispatch(name: str, fixture: Path, profile: Path, repeats: int) -> dict:
    functions = {"startup": startup, "paint": paint, "cache": cache}
    if name in functions:
        return functions[name](fixture, profile, repeats)
    if name.startswith("library-"):
        return library(fixture, profile, repeats, large=name.endswith("large"))
    if name.startswith("wall-"):
        return wall(fixture, profile, repeats, large=name.endswith("large"))
    if name.startswith("image-"):
        return image(fixture, profile, repeats, label=name.removeprefix("image-"))
    raise ValueError(f"unknown scenario: {name}")


def environment() -> dict:
    versions = {name: importlib.metadata.version(name)
                for name in ("numpy", "Pillow", "PySide6", "PyOpenGL")}
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_hashes = {p.name: _source_digest(p)
                     for p in Path(__file__).parent.glob("performance_*.py")}
    changes = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD", "--", "Imervue"], cwd=ROOT, text=True).splitlines()
    changes += subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "Imervue"],
        cwd=ROOT, text=True).splitlines()
    changed_sources = {name: _source_digest(ROOT / name) for name in sorted(set(changes))
                       if name.endswith(".py") and (ROOT / name).is_file()}
    hardware = {}
    if os.name == "nt":
        command = ("[PSCustomObject]@{cpu=(Get-CimInstance Win32_Processor).Name; "
                   "ram_bytes=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; "
                   "gpus=@((Get-CimInstance Win32_VideoController).Name)} "
                   "| ConvertTo-Json -Compress")
        hardware = json.loads(subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", command], text=True, timeout=30))
    return {"platform": platform.platform(), "python": platform.python_version(),
            "logical_cpus": os.cpu_count(), "processor": platform.processor(),
            "hardware": hardware,
            "versions": versions, "product_revision": revision, "tool_sha256": source_hashes,
            "product_changed_sources_sha256": changed_sources,
            "source_hash_newlines": "LF",
            "cold_definition": "fresh child/profile/index; OS page cache is NOT flushed",
            "rss_definition": ("5ms sampled resident working set "
                               "plus process lifetime high-water mark")}


def _source_digest(path: Path) -> str:
    """Normalize checkout line endings so identical source has the same identity."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quick", action="store_true", help="small smoke fixtures, not a baseline")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", choices=SCENARIOS, nargs="+")
    parser.add_argument("--child", choices=SCENARIOS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    fixture = args.fixtures.resolve()
    if args.child:
        manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("fixture_version") != 1 or "image_sha256" not in manifest:
            parser.error("child requires a prepared, owned fixture directory")
        profile = fixture / "runs" / uuid.uuid4().hex
        with isolated_profile(profile):
            value = dispatch(args.child, fixture, profile, args.repeats)
            write_json(args.output, value)
        # Application QThreads can outlive Qt wrapper teardown on Windows; each
        # scenario has completed before this explicit, flushed child-only exit.
        os._exit(0)
    manifest = prepare_fixtures(fixture, quick=args.quick)
    report = {"schema_version": 1, "environment": environment(), "fixture": manifest,
              "scenarios": {}, "failures": {}}
    for name in args.only or SCENARIOS:
        print(f"Measuring {name}", flush=True)
        result = fixture / "results" / f"{uuid.uuid4().hex}.json"
        command = [sys.executable, "-X", "utf8", str(Path(__file__)), "--fixtures", str(fixture),
                   "--output", str(result), "--repeats", str(args.repeats), "--child", name]
        try:
            subprocess.run(command, cwd=ROOT, check=True, timeout=1800)
            report["scenarios"][name] = json.loads(result.read_text(encoding="utf-8"))
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            report["failures"][name] = str(exc)
        write_json(args.output, report)
    if report["failures"]:
        raise SystemExit("One or more scenarios failed; see the report")


if __name__ == "__main__":
    main()
