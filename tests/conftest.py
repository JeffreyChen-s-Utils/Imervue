"""
Pytest configuration and shared fixtures for Imervue tests.
"""

import numpy as np
import pytest
from PIL import Image


# ===========================
# User-settings isolation (autouse)
# ===========================
# ``user_settings_path()`` resolves via ``app_dir()`` which is derived from
# ``__file__``, not cwd — so ``monkeypatch.chdir`` does NOT protect it.
# Worse, several user-settings helpers (``add_recent_*``, ``add_bookmark``,
# ``ClipboardMonitor.set_enabled`` …) call ``schedule_save()`` which starts
# a background ``threading.Timer`` that flushes the dict a few seconds
# later. Without this fixture:
#
#   1. Tests write to the real ``<repo>/user_setting.json``.
#   2. Debounced timers started inside tests survive past the test method
#      and can fire during a LATER unrelated test, clobbering the real
#      file with a stale state (often all-empty lists because the last
#      mutator was a teardown that reset them).
#
# This fixture redirects the settings path to a per-test tmp file,
# snapshots the in-memory dict, and cancels any pending debounced save at
# teardown so no timer from this test can write to anything after the
# fixture tears down.

@pytest.fixture(autouse=True)
def _isolate_user_settings(tmp_path, monkeypatch):
    try:
        from Imervue.user_settings import user_setting_dict as mod
    except ImportError:
        # Module not importable in this test environment — nothing to do.
        yield
        return

    original = {
        k: (list(v) if isinstance(v, list) else v)
        for k, v in mod.user_setting_dict.items()
    }
    monkeypatch.setattr(
        mod, "_user_settings_path",
        lambda: tmp_path / "user_setting.json",
    )
    try:
        yield
    finally:
        mod.cancel_pending_save()
        mod.user_setting_dict.clear()
        mod.user_setting_dict.update(original)


# ===========================
# Qt fixture (session-scoped — only one QApplication can exist per process)
# ===========================

@pytest.fixture(scope="session")
def qapp():
    """Provide a single QApplication for tests that need Qt.

    Tests that don't import PySide6 are unaffected — the fixture is
    only instantiated when explicitly requested.
    """
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    # Don't quit the app here — quitting it makes subsequent tests in the
    # same session unable to recreate it on some platforms. Letting Python
    # exit clean it up is fine for the test runner.


# ===========================
# Test image fixtures
# ===========================

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def sample_rgb_array():
    """Create a simple 100x80 RGB numpy array."""
    return np.random.randint(0, 256, (80, 100, 3), dtype=np.uint8)


@pytest.fixture
def sample_rgba_array():
    """Create a simple 100x80 RGBA numpy array."""
    return np.random.randint(0, 256, (80, 100, 4), dtype=np.uint8)


@pytest.fixture
def sample_grayscale_array():
    """Create a simple 100x80 grayscale numpy array."""
    return np.random.randint(0, 256, (80, 100), dtype=np.uint8)


@pytest.fixture
def sample_png(tmp_path):
    """Create a temporary PNG image file."""
    path = tmp_path / "test_image.png"
    img = Image.fromarray(np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_jpeg(tmp_path):
    """Create a temporary JPEG image file."""
    path = tmp_path / "test_image.jpg"
    img = Image.fromarray(np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_grayscale_png(tmp_path):
    """Create a temporary grayscale PNG image file."""
    path = tmp_path / "gray_image.png"
    arr = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    img = Image.fromarray(arr, mode="L")
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_gif(tmp_path):
    """Create a temporary animated GIF file with 3 frames."""
    path = tmp_path / "anim.gif"
    frames = []
    for i in range(3):
        arr = np.full((32, 32, 3), i * 80, dtype=np.uint8)
        frames.append(Image.fromarray(arr))
    frames[0].save(
        str(path), save_all=True, append_images=frames[1:],
        duration=100, loop=0,
    )
    return str(path)


@pytest.fixture
def image_folder(tmp_path):
    """Create a temporary folder with several test images."""
    names = ["alpha.png", "beta.jpg", "gamma.png", "delta.bmp"]
    for name in names:
        p = tmp_path / name
        arr = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        fmt = "PNG" if name.endswith(".png") else ("JPEG" if name.endswith(".jpg") else "BMP")
        if fmt == "JPEG":
            img = img.convert("RGB")
        img.save(str(p), format=fmt)
    return str(tmp_path)
