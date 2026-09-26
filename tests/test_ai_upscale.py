"""
Tests for AI upscale dialog — model registry, tile helper, inference pipeline.

Tests that exercise actual ONNX inference are skipped if onnxruntime is not
installed. Registry and tile-math tests have no heavy dependencies.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from Imervue.gui.ai_upscale_dialog import UPSCALE_MODELS, _TILE_SIZE, _TILE_PAD


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

class TestModelRegistry:
    def test_all_models_have_required_fields(self):
        required = {"repo", "file", "scale", "desc_key", "desc_default"}
        for key, info in UPSCALE_MODELS.items():
            missing = required - set(info.keys())
            assert not missing, f"Model '{key}' missing fields: {missing}"

    def test_scale_values(self):
        for key, info in UPSCALE_MODELS.items():
            assert info["scale"] in (2, 4), (
                f"Model '{key}' has unexpected scale {info['scale']}"
            )

    def test_files_have_onnx_extension(self):
        for key, info in UPSCALE_MODELS.items():
            assert info["file"].endswith(".onnx"), (
                f"Model '{key}' file doesn't end with .onnx: {info['file']}"
            )

    def test_expected_models_present(self):
        assert "realesrgan-x4plus" in UPSCALE_MODELS
        assert "realesrgan-x4plus-anime" in UPSCALE_MODELS
        assert "realesrgan-x2plus" in UPSCALE_MODELS

    def test_every_model_pins_a_commit(self):
        # bandit B615: an unpinned download follows whatever "main" becomes.
        import re
        for key, info in UPSCALE_MODELS.items():
            assert re.fullmatch(r"[0-9a-f]{40}", info.get("revision", "")), key

    def test_download_passes_the_pinned_revision(self, monkeypatch):
        import sys
        import types

        from Imervue.gui import ai_upscale_dialog

        calls: list[dict] = []
        fake = types.SimpleNamespace(hf_hub_download=lambda **kw: calls.append(kw) or "x.onnx")
        monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
        for key, info in UPSCALE_MODELS.items():
            assert ai_upscale_dialog._download_model(key) == "x.onnx"
            assert calls[-1] == {"repo_id": info["repo"], "filename": info["file"],
                                 "revision": info["revision"]}

    def test_repos_are_valid_huggingface_ids(self):
        for key, info in UPSCALE_MODELS.items():
            repo = info["repo"]
            # HuggingFace repo IDs have the format "owner/name"
            parts = repo.split("/")
            assert len(parts) == 2, f"Model '{key}' has invalid repo: {repo}"
            assert all(len(p) > 0 for p in parts)


# ---------------------------------------------------------------------------
# Tile math
# ---------------------------------------------------------------------------

class TestTileMath:
    def test_constants(self):
        assert _TILE_SIZE > 0
        assert _TILE_PAD >= 0
        assert _TILE_SIZE > _TILE_PAD * 2

    def test_tile_covers_small_image(self):
        """An image smaller than TILE_SIZE should need only 1 tile."""
        h, w = 100, 100
        tiles_x = max(1, (w + _TILE_SIZE - 1) // _TILE_SIZE)
        tiles_y = max(1, (h + _TILE_SIZE - 1) // _TILE_SIZE)
        assert tiles_x == 1
        assert tiles_y == 1

    def test_tile_count_large_image(self):
        """A 2048x2048 image should need multiple tiles."""
        h, w = 2048, 2048
        tiles_x = max(1, (w + _TILE_SIZE - 1) // _TILE_SIZE)
        tiles_y = max(1, (h + _TILE_SIZE - 1) // _TILE_SIZE)
        assert tiles_x == 4
        assert tiles_y == 4


# ---------------------------------------------------------------------------
# Tile inference (only if onnxruntime is available)
# ---------------------------------------------------------------------------

class TestUpscaleTile:
    @pytest.fixture
    def has_onnxruntime(self):
        pytest.importorskip("onnxruntime")

    def test_tile_function_signature(self):
        """_upscale_tile should be importable and callable."""
        from Imervue.gui.ai_upscale_dialog import _upscale_tile
        assert callable(_upscale_tile)

    def test_upscale_image_function_exists(self):
        from Imervue.gui.ai_upscale_dialog import _upscale_image
        assert callable(_upscale_image)


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------

class TestScanFolder:
    @pytest.fixture
    def image_folder(self, tmp_path):
        """Create a folder with several image files and a non-image file."""
        from PIL import Image
        for name in ("a.png", "b.jpg", "c.bmp"):
            Image.new("RGB", (4, 4), "white").save(str(tmp_path / name))
        (tmp_path / "readme.txt").write_text("not an image")
        sub = tmp_path / "sub"
        sub.mkdir()
        Image.new("RGB", (4, 4), "red").save(str(sub / "d.png"))
        return tmp_path

    def test_scan_flat(self, image_folder):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        paths = _scan_folder(str(image_folder), recursive=False)
        names = [os.path.basename(p) for p in paths]
        assert "a.png" in names
        assert "b.jpg" in names
        assert "c.bmp" in names
        assert "readme.txt" not in names
        assert "d.png" not in names  # in subfolder

    def test_scan_recursive(self, image_folder):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        paths = _scan_folder(str(image_folder), recursive=True)
        names = [os.path.basename(p) for p in paths]
        assert "d.png" in names
        assert len(names) == 4  # a.png, b.jpg, c.bmp, d.png

    def test_scan_empty(self, tmp_path):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        assert _scan_folder(str(tmp_path)) == []

    def test_scan_nonexistent(self, tmp_path):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        assert _scan_folder(str(tmp_path / "nope")) == []


# ---------------------------------------------------------------------------
# Dialog folder mode
# ---------------------------------------------------------------------------

class TestDialogFolderMode:
    @pytest.fixture
    def image_folder(self, tmp_path):
        from PIL import Image
        for name in ("x.png", "y.jpg"):
            Image.new("RGB", (4, 4), "white").save(str(tmp_path / name))
        return tmp_path

    @pytest.fixture
    def stub_gui(self, qapp):
        from unittest.mock import MagicMock
        from PySide6.QtWidgets import QMainWindow
        gui = MagicMock()
        mw = QMainWindow()
        gui.main_window = mw
        yield gui
        mw.close()

    def test_folder_mode_shows_source_row(self, stub_gui):
        from Imervue.gui.ai_upscale_dialog import AIUpscaleDialog
        dlg = AIUpscaleDialog(stub_gui, paths=None, folder=None)
        # isHidden checks the widget's own hidden flag, not parent visibility
        assert not dlg._src_row_widget.isHidden()
        dlg.close()

    def test_preset_paths_hides_source_row(self, stub_gui, image_folder):
        from Imervue.gui.ai_upscale_dialog import AIUpscaleDialog
        dlg = AIUpscaleDialog(stub_gui, paths=[str(image_folder / "x.png")])
        assert dlg._src_row_widget.isHidden()
        dlg.close()

    def test_folder_prefill_scans(self, stub_gui, image_folder):
        from Imervue.gui.ai_upscale_dialog import AIUpscaleDialog
        dlg = AIUpscaleDialog(stub_gui, folder=str(image_folder))
        assert len(dlg._paths) == 2
        dlg.close()


# ---------------------------------------------------------------------------
# Traditional resampling methods
# ---------------------------------------------------------------------------

class TestTraditionalMethods:
    def test_registry_has_expected_methods(self):
        from Imervue.gui.ai_upscale_dialog import TRADITIONAL_METHODS
        assert "trad:lanczos" in TRADITIONAL_METHODS
        assert "trad:bicubic" in TRADITIONAL_METHODS
        assert "trad:nearest" in TRADITIONAL_METHODS

    def test_all_methods_have_desc(self):
        from Imervue.gui.ai_upscale_dialog import TRADITIONAL_METHODS
        for _key, info in TRADITIONAL_METHODS.items():
            assert "desc_key" in info
            assert "desc_default" in info

    def test_resampling_map_matches_registry(self):
        from Imervue.gui.ai_upscale_dialog import (
            TRADITIONAL_METHODS, _TRAD_RESAMPLING,
        )
        assert set(_TRAD_RESAMPLING.keys()) == set(TRADITIONAL_METHODS.keys())

    def test_tagged_photo_is_upscaled_upright(self, tmp_path):
        """The output carries no EXIF, so the stored sideways pixels stayed sideways."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        exif = Image.Exif()
        exif[0x0112] = 6
        src = tmp_path / "p.jpg"
        Image.new("RGB", (10, 8)).save(src, exif=exif)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _UpscaleWorker([str(src)], str(out_dir), "trad:nearest", False, scale_override=2).run()
        (result,) = out_dir.iterdir()
        with Image.open(result) as out:
            assert out.size == (16, 20)

    def test_overwrite_skips_an_animated_file(self, tmp_path):
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        path = tmp_path / "anim.webp"
        frames = [Image.new("RGB", (8, 4), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
        frames[0].save(path, save_all=True, append_images=frames[1:])
        results = []
        worker = _UpscaleWorker([str(path)], "", "trad:nearest", True, scale_override=2)
        worker.result_ready.connect(lambda ok, bad: results.append((ok, bad)))
        worker.run()
        assert results == [(0, 1)]
        with Image.open(path) as img:
            assert img.n_frames == 3 and img.size == (8, 4)

    @staticmethod
    def _photo_exif():
        from PIL import Image
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
        return exif

    def test_overwrite_keeps_the_exif_and_replaces_in_one_step(self, tmp_path):
        """The overwrite re-encoded at quality 75 and dropped the camera and capture date."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        path = tmp_path / "p.jpg"
        Image.new("RGB", (10, 8), (30, 90, 160)).save(path, quality=95, exif=self._photo_exif())
        _UpscaleWorker([str(path)], "", "trad:nearest", True, scale_override=2).run()
        with Image.open(path) as img:
            assert img.size == (20, 16)
            assert img.getexif()[0x010F] == "Canon"
            assert img.getexif().get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
        assert [f.name for f in tmp_path.iterdir()] == ["p.jpg"]

    def test_new_file_keeps_the_source_exif(self, tmp_path):
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        src = tmp_path / "p.png"
        Image.new("RGB", (10, 8)).save(src, exif=self._photo_exif())
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _UpscaleWorker([str(src)], str(out_dir), "trad:nearest", False, scale_override=2).run()
        with Image.open(out_dir / "p_x2.png") as out:
            assert out.getexif().get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"

    def test_raw_source_is_developed_full_size_and_written_as_png(self, tmp_path, monkeypatch):
        """A .cr2 source produced 'shot_x2.cr2' holding PNG bytes, from the small preview."""
        import numpy as np
        from PIL import Image
        from Imervue.gpu_image_view.images import image_loader
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        monkeypatch.setattr(image_loader, "_load_raw",
                            lambda _p, thumbnail: np.full((12, 18, 3), 70, dtype=np.uint8))
        raw = tmp_path / "shot.cr2"
        Image.new("RGB", (6, 4)).save(raw, format="TIFF")   # Pillow sees only a preview
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _UpscaleWorker([str(raw)], str(out_dir), "trad:nearest", False, scale_override=2).run()
        assert [f.name for f in out_dir.iterdir()] == ["shot_x2.png"]
        with Image.open(out_dir / "shot_x2.png") as out:
            assert out.format == "PNG"
            assert out.size == (36, 24)                    # 2x the developed RAW, not the preview

    def test_transparency_survives_and_opaque_alpha_is_dropped(self, tmp_path):
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        clear = tmp_path / "clear.png"
        Image.new("RGBA", (4, 4), (255, 0, 0, 0)).save(clear)
        solid = tmp_path / "solid.png"
        Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(solid)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _UpscaleWorker([str(clear), str(solid)], str(out_dir), "trad:nearest", False,
                       scale_override=2).run()
        with Image.open(out_dir / "clear_x2.png") as out:
            assert out.mode == "RGBA" and out.getpixel((0, 0))[3] == 0
        with Image.open(out_dir / "solid_x2.png") as out:
            assert out.mode == "RGB"

    def test_lanczos_upscale(self, tmp_path):
        """Lanczos resize should produce exact expected dimensions."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        src = tmp_path / "small.png"
        Image.new("RGB", (10, 8), "blue").save(str(src))

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        worker = _UpscaleWorker(
            [str(src)], str(out_dir), "trad:lanczos", False,
            scale_override=3)
        worker.run()

        results = list(out_dir.glob("*.png"))
        assert len(results) == 1
        out_img = Image.open(str(results[0]))
        assert out_img.size == (30, 24)

    def test_nearest_upscale_preserves_pixels(self, tmp_path):
        """Nearest-neighbor on a solid-color image should be lossless."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker
        src = tmp_path / "pixel.png"
        img = Image.new("RGB", (2, 2), (42, 99, 200))
        img.save(str(src))

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        worker = _UpscaleWorker(
            [str(src)], str(out_dir), "trad:nearest", False,
            scale_override=4)
        worker.run()

        results = list(out_dir.glob("*.png"))
        out_img = Image.open(str(results[0]))
        assert out_img.size == (8, 8)
        # Every pixel should be exactly the same color
        arr = np.asarray(out_img)
        assert np.all(arr == np.array([42, 99, 200], dtype=arr.dtype))

    def test_interruption_breaks_before_processing(self, tmp_path, qapp):
        """When the thread is interrupted (closeEvent requests it), the loop
        stops at its next per-image check without upscaling more files."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        src = tmp_path / "src"
        src.mkdir()
        for name in ("a.png", "b.png"):
            Image.new("RGB", (8, 8), "blue").save(str(src / name))
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        class _Interrupted(_UpscaleWorker):
            def isInterruptionRequested(self):   # noqa: N802 - Qt override
                return True

        worker = _Interrupted(
            [str(src / "a.png"), str(src / "b.png")], str(out_dir),
            "trad:lanczos", False, scale_override=2)
        progress, results = [], []
        worker.progress.connect(lambda *a: progress.append(a))
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert progress == []                      # broke before the first image
        assert results == [(0, 0)]                 # reported so the UI resets
        assert list(out_dir.glob("*.png")) == []   # nothing upscaled



# ---------------------------------------------------------------------------
# Worker run paths (the per-image loop both methods share)
# ---------------------------------------------------------------------------


def _worker_pictures(tmp_path):
    from PIL import Image
    src = tmp_path / "src"
    src.mkdir()
    Image.new("RGB", (8, 6), (200, 40, 40)).save(src / "red.png")
    rgba = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
    rgba.putpixel((0, 0), (10, 20, 30, 0))
    rgba.save(src / "clear.png")
    (src / "broken.png").write_bytes(b"not a picture")
    out = tmp_path / "out"
    out.mkdir()
    return [str(src / "red.png"), str(src / "clear.png"), str(src / "broken.png")], out


def _run(worker):
    progress, results = [], []
    worker.progress.connect(lambda i, total, text: progress.append((i, total, text)))
    worker.result_ready.connect(lambda ok, bad: results.append((ok, bad)))
    worker.run()
    worker.deleteLater()
    return progress, results


def test_the_traditional_run_resizes_each_picture(qapp, tmp_path):
    from PIL import Image
    from Imervue.gui.ai_upscale_dialog import _UpscaleWorker
    paths, out = _worker_pictures(tmp_path)
    progress, results = _run(_UpscaleWorker(paths, str(out), "trad:nearest", False, 3))
    assert results == [(2, 1)]
    assert progress == [(0, 3, "red.png"), (1, 3, "clear.png"), (2, 3, "broken.png")]
    with Image.open(out / "red_x3.png") as done:
        assert done.size == (24, 18)
    with Image.open(out / "clear_x3.png") as done:
        assert done.size == (12, 12)


def test_the_ai_run_upscales_through_the_session_and_keeps_alpha(qapp, tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from PIL import Image
    from Imervue.gui import ai_upscale_dialog as mod

    sessions = []

    class _Session:
        def __init__(self, model_path, providers):
            sessions.append((model_path, providers))

    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(
        get_available_providers=lambda: ["DmlExecutionProvider", "CPUExecutionProvider"],
        InferenceSession=_Session))
    monkeypatch.setattr(mod, "_download_model", lambda key: f"C:/models/{key}.onnx")
    monkeypatch.setattr(mod, "_upscale_image", lambda session, arr, scale, progress_cb=None:
                        np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1))
    paths, out = _worker_pictures(tmp_path)
    progress, results = _run(mod._UpscaleWorker(paths, str(out), "realesrgan-x2plus", False))
    assert results == [(2, 1)]
    assert sessions == [("C:/models/realesrgan-x2plus.onnx",
                         ["DmlExecutionProvider", "CPUExecutionProvider"])]
    assert progress == [(0, 3, "Downloading model..."), (0, 3, "Loading model..."),
                        (0, 3, "red.png"), (1, 3, "clear.png"), (2, 3, "broken.png")]
    with Image.open(out / "red_x2.png") as done:
        assert done.size == (16, 12)
        assert done.mode == "RGB"
    with Image.open(out / "clear_x2.png") as done:
        assert done.size == (8, 8)
        assert done.mode == "RGBA"
        assert done.getpixel((0, 0))[3] < 255
