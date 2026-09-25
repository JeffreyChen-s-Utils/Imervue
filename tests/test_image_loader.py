"""Tests for image_loader: load_image_file and _scan_images."""
import os
import numpy as np
import pytest
from PIL import Image

pytest.importorskip("imageio")
pytest.importorskip("rawpy")

from Imervue.gpu_image_view.images.image_loader import load_image_file, _scan_images


class TestLoadImageFile:
    def test_load_png_returns_rgba(self, sample_png):
        result = load_image_file(sample_png)
        assert result.ndim == 3
        assert result.shape[2] == 4
        assert result.dtype == np.uint8

    def test_load_jpeg_returns_rgba(self, sample_jpeg):
        result = load_image_file(sample_jpeg)
        assert result.ndim == 3
        assert result.shape[2] == 4

    def test_load_grayscale_returns_rgba(self, sample_grayscale_png):
        result = load_image_file(sample_grayscale_png)
        assert result.ndim == 3
        assert result.shape[2] == 4

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises((FileNotFoundError, OSError)):
            load_image_file(str(tmp_path / "nonexistent.png"))


class TestScanImages:
    def test_scan_finds_supported_files(self, image_folder):
        results = _scan_images(image_folder)
        basenames = [os.path.basename(p) for p in results]
        assert "alpha.png" in basenames
        assert "beta.jpg" in basenames
        assert "gamma.png" in basenames
        assert "delta.bmp" in basenames

    def test_scan_sorted_alphabetically(self, image_folder):
        results = _scan_images(image_folder)
        basenames = [os.path.basename(p).lower() for p in results]
        assert basenames == sorted(basenames)

    def test_scan_ignores_non_image(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "real.png").write_bytes(
            Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8)).tobytes()
        )
        # Create a real png
        img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8))
        img.save(str(tmp_path / "real.png"))
        results = _scan_images(str(tmp_path))
        assert len(results) == 1
        assert results[0].endswith("real.png")

    def test_scan_empty_dir(self, tmp_path):
        results = _scan_images(str(tmp_path))
        assert results == []

    def test_scan_nonexistent_dir(self):
        results = _scan_images("/nonexistent/path/xyz")
        assert results == []


class TestOpenFolder:
    def test_empty_folder_resets_to_clean_grid(self, tmp_path):
        # Navigating "back" to an image-less folder must rebuild the wall empty
        # rather than leave the previous folder's stale thumbnails behind.
        from pathlib import Path
        from types import SimpleNamespace

        from Imervue.gpu_image_view.images.image_loader import _open_folder

        empty = tmp_path / "empty"
        empty.mkdir()
        loaded = []
        view = SimpleNamespace(
            _unfiltered_images=["stale.png"],
            _stack_members={"k": 1},
            load_tile_grid_async=lambda paths: loaded.append(list(paths)),
            main_window=object(),  # no plugin_manager
        )
        # The duck-typed fake deliberately stands in for a real GPUImageView;
        # S5655's argument-type check is a false positive for test doubles.
        _open_folder(view, Path(str(empty)))  # NOSONAR
        assert loaded == [[]]
        assert view._unfiltered_images == []


def _write_sample_video(path, frame_count=5):
    iio = pytest.importorskip("imageio").v2
    pytest.importorskip("imageio_ffmpeg")
    frames = [
        np.full((16, 16, 3), 40 + idx * 30, dtype=np.uint8)
        for idx in range(frame_count)
    ]
    try:
        iio.mimwrite(str(path), frames, format="ffmpeg", fps=5)
    except (OSError, RuntimeError, ValueError) as exc:  # ffmpeg binary issues
        pytest.skip(f"ffmpeg writer unavailable: {exc}")


class TestVideoInGrid:
    def test_video_ext_supported(self):
        from Imervue.image.formats import VIEWER_EXTENSIONS
        assert ".mp4" in VIEWER_EXTENSIONS

    def test_scan_finds_video(self, tmp_path):
        _write_sample_video(tmp_path / "clip.mp4")
        results = _scan_images(str(tmp_path))
        assert any(p.endswith("clip.mp4") for p in results)

    def test_load_video_returns_rgba_poster(self, tmp_path):
        video = tmp_path / "clip.mp4"
        _write_sample_video(video)
        result = load_image_file(str(video))
        assert result.ndim == 3
        assert result.shape[2] == 4
        assert result.dtype == np.uint8


class TestHeifInGrid:
    def test_heif_exts_supported(self):
        from Imervue.image.formats import VIEWER_EXTENSIONS
        assert ".heic" in VIEWER_EXTENSIONS
        assert ".avif" in VIEWER_EXTENSIONS

    def test_scan_finds_heic(self, tmp_path):
        pillow_heif = pytest.importorskip("pillow_heif")
        pillow_heif.register_heif_opener()
        img = Image.fromarray(np.full((16, 16, 3), 70, dtype=np.uint8))
        img.save(str(tmp_path / "photo.heic"))
        results = _scan_images(str(tmp_path))
        assert any(p.endswith("photo.heic") for p in results)


class TestJxlInGrid:
    def test_jxl_ext_supported(self):
        from Imervue.image.formats import VIEWER_EXTENSIONS
        assert ".jxl" in VIEWER_EXTENSIONS

    def test_load_jxl_returns_rgba(self, tmp_path):
        pytest.importorskip("pillow_jxl")
        import pillow_jxl  # noqa: F401  (registers the codec)
        out = tmp_path / "shot.jxl"
        Image.fromarray(np.full((16, 16, 3), 60, dtype=np.uint8)).save(str(out), "JXL")
        result = load_image_file(str(out))
        assert result.ndim == 3
        assert result.shape[2] == 4


def test_opening_the_viewer_does_not_import_raw_decoders():
    # rawpy and imageio cost ~90 ms of startup and only RAW files need them,
    # so the loaders import them where a RAW file is decoded. Checked in a
    # fresh interpreter, since this test session has imported everything.
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    code = ("import sys; import Imervue.Imervue_main_window; "
            "print(sorted(m for m in ('rawpy', 'imageio') if m in sys.modules))")
    result = subprocess.run(  # noqa: S603 - fixed argv: this interpreter
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=repo,
        timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def _portrait_jpeg(path):
    """40x20 stored pixels, left half red, tagged 'rotate 90 CW to view' (6)."""
    arr = np.zeros((20, 40, 3), dtype=np.uint8)
    arr[:, :20] = (255, 0, 0)
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.fromarray(arr).save(path, exif=exif, quality=100)
    return str(path)


class TestExifOrientation:
    """Phones and cameras tag portrait shots instead of turning the pixels."""

    @pytest.mark.parametrize("thumbnail", [False, True])
    def test_tagged_photo_loads_upright(self, tmp_path, thumbnail):
        img = load_image_file(_portrait_jpeg(tmp_path / "p.jpg"), thumbnail=thumbnail)
        assert img.shape[:2] == (40, 20)
        assert img[5, 10, 0] > 200 and img[35, 10, 0] < 60   # red half is on top

    def test_new_recipe_applies_to_the_upright_image(self, tmp_path):
        from Imervue.image.recipe import Recipe
        img = load_image_file(_portrait_jpeg(tmp_path / "p.jpg"), recipe=Recipe(crop=(0, 0, 20, 10)))
        assert img.shape[:2] == (10, 20)

    def test_legacy_geometry_recipe_keeps_the_stored_orientation(self, tmp_path):
        """A crop saved before images loaded upright was drawn on the sideways pixels."""
        from Imervue.image.recipe import Recipe
        legacy = Recipe.from_dict({"crop": [0, 0, 30, 20]})
        img = load_image_file(_portrait_jpeg(tmp_path / "p.jpg"), recipe=legacy)
        assert img.shape[:2] == (20, 30)

    def test_legacy_tone_only_recipe_still_loads_upright(self, tmp_path):
        from Imervue.image.recipe import Recipe
        legacy = Recipe.from_dict({"brightness": 0.2})
        img = load_image_file(_portrait_jpeg(tmp_path / "p.jpg"), recipe=legacy)
        assert img.shape[:2] == (40, 20)


class TestDecodeImageFile:
    """The editors' base: the viewer's decode without recipe or view-time simulation."""

    def test_raw_is_developed_through_libraw(self, tmp_path, monkeypatch):
        """Pillow opens a CR2 as TIFF and returns its small embedded preview."""
        from Imervue.gpu_image_view.images import image_loader
        developed = np.zeros((30, 45, 3), dtype=np.uint8)
        monkeypatch.setattr(image_loader, "_load_raw", lambda _p, thumbnail: developed)
        out = image_loader.decode_image_file(str(tmp_path / "shot.CR2"))
        assert out.shape == (30, 45, 4)

    @pytest.mark.parametrize("name", ["IMG_1.CR3", "P1.RW2", "DSCN1.nrw", "nx.SRW", "IMGP1.pef"])
    def test_every_libraw_format_is_developed(self, tmp_path, monkeypatch, name):
        """Only six RAW formats reached libraw; a CR3 or RW2 went to Pillow and failed."""
        from Imervue.gpu_image_view.images import image_loader
        developed = np.zeros((30, 45, 3), dtype=np.uint8)
        monkeypatch.setattr(image_loader, "_load_raw", lambda _p, thumbnail: developed)
        assert image_loader.decode_image_file(str(tmp_path / name)).shape == (30, 45, 4)

    @pytest.mark.parametrize("thumbnail", [False, True])
    def test_unreadable_raw_is_an_oserror(self, tmp_path, thumbnail):
        """libraw's LibRawError slipped past every ``IMAGE_READ_ERRORS`` handler."""
        from Imervue.gpu_image_view.images.image_loader import decode_image_file
        from Imervue.image.read_errors import IMAGE_READ_ERRORS
        path = tmp_path / "broken.cr2"
        path.write_bytes(b"not a raw file" * 20)
        with pytest.raises(OSError, match="libraw can't decode") as caught:
            decode_image_file(str(path), thumbnail=thumbnail)
        assert isinstance(caught.value, IMAGE_READ_ERRORS)
        import rawpy
        assert isinstance(caught.value.__cause__, rawpy.LibRawError)

    def test_view_time_simulation_is_not_baked_in(self, tmp_path, monkeypatch):
        from Imervue.gpu_image_view import cvd_view_mode
        from Imervue.gpu_image_view.images.image_loader import decode_image_file
        monkeypatch.setattr(cvd_view_mode, "apply_if_active", lambda _a: 1 / 0)
        path = tmp_path / "a.png"
        Image.new("RGB", (5, 3), (10, 20, 30)).save(path)
        out = decode_image_file(str(path))
        assert out.shape == (3, 5, 4) and tuple(out[0, 0]) == (10, 20, 30, 255)

    @pytest.mark.parametrize(("orient", "shape"), [(True, (40, 20)), (False, (20, 40))])
    def test_orientation_can_be_skipped_for_a_legacy_recipe(self, tmp_path, orient, shape):
        from Imervue.gpu_image_view.images.image_loader import decode_image_file
        exif = Image.Exif()
        exif[0x0112] = 6
        path = tmp_path / "p.jpg"
        Image.new("RGB", (40, 20)).save(path, exif=exif)
        assert decode_image_file(str(path), orient=orient).shape[:2] == shape


def test_scanning_a_folder_by_name_puts_page2_before_page10(tmp_path):
    """Next / previous went page1, page10, page11, page2 while the file tree showed page1, page2."""
    from Imervue.gpu_image_view.images.image_loader import _scan_images
    for name in ("page10.png", "page2.png", "page1.png"):
        (tmp_path / name).write_bytes(b"x")
    names = [os.path.basename(p) for p in _scan_images(str(tmp_path))]
    assert names == ["page1.png", "page2.png", "page10.png"]
    backwards = [os.path.basename(p) for p in _scan_images(str(tmp_path), ascending=False)]
    assert backwards == ["page10.png", "page2.png", "page1.png"]


def test_scanning_by_modified_time_or_size_uses_the_listing(tmp_path, monkeypatch):
    """The per-path stat is gone: the order comes from what scandir already returned."""
    from Imervue.gpu_image_view.images import image_loader
    for name, size, stamp in (("a.png", 30, 300), ("b.png", 10, 100), ("c.png", 20, 200)):
        path = tmp_path / name
        path.write_bytes(b"x" * size)
        os.utime(path, (stamp, stamp))

    def no_stat(*_args, **_kwargs):
        raise AssertionError("a stat per path")

    monkeypatch.setattr(os.path, "getmtime", no_stat)
    monkeypatch.setattr(os.path, "getsize", no_stat)
    by_date = [os.path.basename(p) for p in image_loader._scan_images(str(tmp_path), sort_by="modified")]
    by_size = [os.path.basename(p) for p in image_loader._scan_images(str(tmp_path), sort_by="size",
                                                                      ascending=False)]
    assert by_date == ["b.png", "c.png", "a.png"]
    assert by_size == ["a.png", "c.png", "b.png"]
    by_created = image_loader._scan_images(str(tmp_path), sort_by="created")
    assert sorted(by_created) == sorted(str(p) for p in tmp_path.iterdir())


def test_a_folder_sorted_by_name_is_scanned_not_read_from_the_cache(tmp_path, monkeypatch):
    """Checking every cached path cost 9x a fresh scan (5000 files: 349 ms against 38 ms)."""
    from Imervue.gpu_image_view.images import image_loader
    from Imervue.image import folder_index
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    (tmp_path / "a.png").write_bytes(b"x")
    monkeypatch.setitem(user_setting_dict, "sort_by", "name")
    monkeypatch.setattr(folder_index, "load", lambda *_a, **_k: pytest.fail("cache read"))
    monkeypatch.setattr(folder_index, "save", lambda *_a, **_k: pytest.fail("cache written"))
    assert image_loader._scan_images_for_user(str(tmp_path)) == [str(tmp_path / "a.png")]


def test_a_folder_sorted_by_resolution_still_uses_the_cache(tmp_path, monkeypatch):
    from Imervue.gpu_image_view.images import image_loader
    from Imervue.image import folder_index
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    monkeypatch.setitem(user_setting_dict, "sort_by", "resolution")
    monkeypatch.setattr(folder_index, "load", lambda *_a, **_k: ["cached.png"])
    assert image_loader._scan_images_for_user(str(tmp_path)) == ["cached.png"]


@pytest.mark.parametrize("thumbnail", [False, True])
def test_a_raster_decode_takes_the_giant_slot_for_its_pixel_count(tmp_path, monkeypatch, thumbnail):
    """Several workers decoding panoramas at once could add their gigabytes up."""
    from contextlib import contextmanager

    from Imervue.gpu_image_view.images import image_loader
    asked = []

    @contextmanager
    def slot(pixels):
        asked.append(pixels)
        yield

    monkeypatch.setattr(image_loader, "decode_slot", slot)
    path = tmp_path / "a.png"
    Image.new("RGB", (30, 20)).save(path)
    image_loader.decode_image_file(str(path), thumbnail=thumbnail)
    assert asked == [600]


def test_the_wall_leaves_out_hidden_files_and_mac_companions(tmp_path):
    """A card from a Mac showed a broken ._ thumbnail beside every photo."""
    from Imervue.gpu_image_view.images.image_loader import _scan_images
    for name in ("a.png", "._a.png", ".b.png"):
        (tmp_path / name).write_bytes(b"x")
    assert [os.path.basename(p) for p in _scan_images(str(tmp_path))] == ["a.png"]


def test_the_progressive_scan_leaves_out_hidden_files(qapp, tmp_path):
    from Imervue.gpu_image_view.images.image_loader import FolderScanWorker
    for name in ("a.png", "._a.png"):
        (tmp_path / name).write_bytes(b"x")
    finished = []
    worker = FolderScanWorker(str(tmp_path))
    worker.signals.finished.connect(lambda _folder, images: finished.append(images))
    worker.run()
    assert [[os.path.basename(p) for p in images] for images in finished] == [["a.png"]]


def test_a_hidden_picture_opened_on_purpose_joins_its_folders_list(tmp_path):
    from types import SimpleNamespace

    from Imervue.gpu_image_view.images import image_loader
    for name in ("a.png", ".b.png", "c.png"):
        (tmp_path / name).write_bytes(b"x")
    loaded = []
    model = SimpleNamespace(images=[])
    model.set_images = lambda images: setattr(model, "images", list(images))
    viewer = SimpleNamespace(model=model, current_index=-1, tile_grid_mode=True,
                             load_deep_zoom_image=loaded.append, main_window=SimpleNamespace())
    image_loader._open_file(viewer, tmp_path / ".b.png")
    assert [os.path.basename(p) for p in model.images] == [".b.png", "a.png", "c.png"]
    assert viewer.current_index == 0
    assert loaded == [str(tmp_path / ".b.png")]
