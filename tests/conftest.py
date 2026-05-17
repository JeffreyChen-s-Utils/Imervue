"""
Pytest configuration and shared fixtures for Imervue tests.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

_rng = np.random.default_rng(seed=0xC0FFEE)


# ---------------------------------------------------------------------------
# Plugin-import bootstrap
# ---------------------------------------------------------------------------
# Plugin packages live under ``<repo>/plugins/<name>/`` and are NOT on the
# default sys.path — at runtime the plugin manager prepends each plugin's
# directory so ``__init__.py`` can do ``from <plugin>.<module> import …``.
# Tests that exercise plugin-internal modules (e.g. ``portrait_blur`` lives
# inside the portrait_mode plugin) need the same path injection. Doing it
# once here at session-collect time keeps individual test modules clean.

def _bootstrap_plugin_imports() -> None:
    """Mirror what ``plugin_manager`` does at runtime — put ``plugins/`` on
    sys.path so each plugin directory is importable as a package."""
    plugin_root = Path(__file__).resolve().parent.parent / "plugins"
    if not plugin_root.is_dir():
        return
    plugin_root_str = str(plugin_root)
    if plugin_root_str not in sys.path:
        sys.path.insert(0, plugin_root_str)


_bootstrap_plugin_imports()


# ---------------------------------------------------------------------------
# Stale tmp_path cleanup
# ---------------------------------------------------------------------------
# Pytest's tmp_path stores per-session dirs under
# ``%TMP%/pytest-of-<user>/pytest-<N>/`` and *intends* to retain only the
# last three. On Windows the cleanup silently skips entries it can't
# delete (open file handles, denied permissions, antivirus scan locks),
# so the directory drifts upward over time and the user ends up with
# dozens of dead session dirs.
#
# This hook walks ``pytest-of-<user>/`` once at session start, sorts by
# numeric suffix, and removes everything older than the most-recent
# three. Each removal is best-effort — the same lock conditions that
# bit pytest's own retention can bite us, but at least we keep trying.

def _prune_old_pytest_basetemps(retain: int = 3) -> None:
    import re
    import shutil
    import tempfile

    base = Path(tempfile.gettempdir())
    if not base.is_dir():
        return
    candidates: list[Path] = []
    for parent in base.iterdir():
        if not parent.name.startswith("pytest-of-"):
            continue
        candidates.extend(
            child for child in parent.iterdir()
            if child.is_dir() and re.match(r"pytest-\d+$", child.name)
        )
    if not candidates:
        return

    def _suffix(p: Path) -> int:
        try:
            return int(p.name.rsplit("-", 1)[1])
        except (ValueError, IndexError):
            return -1

    candidates.sort(key=_suffix)
    for old in candidates[:-retain]:
        shutil.rmtree(old, ignore_errors=True)


_prune_old_pytest_basetemps()


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


# =====================================================================
# Headless-CI guard for QOpenGLWidget-constructing tests
# =====================================================================

HEADLESS_CI: bool = (
    os.environ.get("CI") == "true"
    or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
)
"""True when the test session is running on a headless CI runner
(GitHub Actions Windows) where ``QOpenGLWidget`` construction
segfaults once the offscreen-GL pool gets exhausted. Same class
of bug already handled in ``test_paint_workspace`` and
``test_puppet_auto_mesh``. Tests that construct a real
``PuppetCanvas`` / ``PuppetWorkspace`` / ``PaintWorkspace`` use
this flag to skip on CI; local runs still cover them."""

skip_on_headless_ci = pytest.mark.skipif(
    HEADLESS_CI,
    reason=(
        "QOpenGLWidget construction segfaults on the headless CI "
        "runner once the offscreen-GL pool gets exhausted. The "
        "underlying logic is exercised by pure-Python sibling "
        "tests where possible."
    ),
)
"""Pre-built ``pytest.mark.skipif`` that test modules can apply
to individual tests or as a module-level ``pytestmark`` when the
whole file constructs GL widgets."""


# =====================================================================


@pytest.fixture(autouse=True, scope="session")
def _suppress_automatic_gc():
    """Stop Python's generational GC from firing inside test code.

    Crashes seen in CI:

        Garbage-collecting
        File "Imervue/paint/tool_bar.py", line 125 in _add_tool_action
        tests/test_paint_autosave_status.py::…

    Python's GC fires when allocation counters cross
    ``gc.get_threshold()`` — by default ``(700, 10, 10)``. Inside a
    test that constructs a ``PaintWorkspace`` (dozens of toolbar
    actions, dock widgets, sliders) the gen-0 threshold trips
    mid-construction. If a *prior* test leaked an orphan QObject
    wrapper (parented to ``None``, held by a closure / signal
    capture, never ``deleteLater()``'d), GC walks into the wrapper
    while its C++ partner is already gone → ``access violation``.
    The traceback then blames the unrelated test currently running.

    Drain-only (``sendPostedEvents`` of ``DeferredDelete``) handled
    the leaks that *did* call ``deleteLater()``. This raises the
    threshold so automatic GC effectively doesn't fire during the
    session; refcounting still cleans up almost everything, and
    pytest's per-test teardown runs the explicit Qt drain.

    A targeted ``gc.collect()`` would be cheaper conceptually but
    was rejected twice: full collect added ~350 ms / test (suite
    went from 3 min → 42 min); ``gc.collect(0)`` disturbed the
    Windows clipboard state on six tests.

    The original thresholds are restored on session teardown so
    Python's exit cleanup runs normally.
    """
    import gc
    original = gc.get_threshold()
    # 700_000 is comfortably above what any single test allocates,
    # so automatic GC effectively never fires in test code. We
    # leave gen-1 / gen-2 thresholds alone since they only matter
    # if gen-0 fires.
    gc.set_threshold(700_000, original[1], original[2])
    yield
    gc.set_threshold(*original)


@pytest.fixture(autouse=True)
def _drain_qt_deferred_delete():
    """Drain queued ``DeferredDelete`` events between tests.

    ``QObject.deleteLater()`` marks an object for deletion at the
    next event-loop spin. Many Qt-using tests in this suite call
    ``deleteLater()`` in fixture teardown without spinning the
    loop afterwards — those C++ objects then linger past the
    test, and when the next test's fixture setup triggers Python
    GC the stale Python wrappers ask the now-half-dead C++ side
    a question and segfault inside the GC pass. The traceback
    shows up as "Garbage-collecting" / "Windows fatal exception:
    access violation" with no obvious test responsible.

    This autouse fixture drains all queued ``DeferredDelete``
    events after every test, so the C++ side is fully freed
    before the next test starts. Cheap (a no-op in tests that
    didn't touch Qt) and prevents the cross-test contamination
    centrally rather than requiring each Qt fixture to remember
    to call ``sendPostedEvents`` itself.

    A ``gc.collect()`` after the drain was tried and rejected:
    full collection added ~350 ms per test (suite went from 3 min
    to 42 min), and ``gc.collect(0)`` happened to disturb the
    Windows clipboard state on a handful of tests. The drain
    alone — without forcing Python GC — has handled every
    reported crash so far.
    """
    yield
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
    except ImportError:
        return
    if QCoreApplication.instance() is None:
        return
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)




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
    return _rng.integers(0, 256, (80, 100, 3), dtype=np.uint8)


@pytest.fixture
def sample_rgba_array():
    """Create a simple 100x80 RGBA numpy array."""
    return _rng.integers(0, 256, (80, 100, 4), dtype=np.uint8)


@pytest.fixture
def sample_grayscale_array():
    """Create a simple 100x80 grayscale numpy array."""
    return _rng.integers(0, 256, (80, 100), dtype=np.uint8)


@pytest.fixture
def sample_png(tmp_path):
    """Create a temporary PNG image file."""
    path = tmp_path / "test_image.png"
    img = Image.fromarray(_rng.integers(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_jpeg(tmp_path):
    """Create a temporary JPEG image file."""
    path = tmp_path / "test_image.jpg"
    img = Image.fromarray(_rng.integers(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_grayscale_png(tmp_path):
    """Create a temporary grayscale PNG image file."""
    path = tmp_path / "gray_image.png"
    arr = _rng.integers(0, 256, (64, 64), dtype=np.uint8)
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


def _format_for_name(name: str) -> str:
    if name.endswith(".png"):
        return "PNG"
    if name.endswith(".jpg"):
        return "JPEG"
    return "BMP"


@pytest.fixture
def image_folder(tmp_path):
    """Create a temporary folder with several test images."""
    names = ["alpha.png", "beta.jpg", "gamma.png", "delta.bmp"]
    for name in names:
        p = tmp_path / name
        arr = _rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        fmt = _format_for_name(name)
        if fmt == "JPEG":
            img = img.convert("RGB")
        img.save(str(p), format=fmt)
    return str(tmp_path)
