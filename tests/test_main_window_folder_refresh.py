"""Regression tests for external folder/image removal during browsing."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.Imervue_main_window import ImervueMainWindow
from Imervue.image.browser_state import ImageFilterSpec, ImageMetadataIndex


class _FakeViewerModel:
    def __init__(self, images=None):
        self.images = list(images or [])

    def set_images(self, paths):  # noqa: N802 - mirrors production model API
        self.images = list(paths)


class _FakeViewer:
    def __init__(self, images=None):
        self.model = _FakeViewerModel(images)
        self.current_index = 0
        self.tile_grid_mode = False
        self.deep_zoom = object()
        self._deep_zoom_loading = None
        self._unfiltered_images = list(images or [])
        self.loaded_grids = []
        self.loaded_deep_zoom = []
        self.update_calls = 0
        self.clear_deep_zoom_calls = 0
        self.settle_refit_calls = 0

    def load_tile_grid_async(self, image_paths):
        self.loaded_grids.append(list(image_paths))
        self.model.set_images(list(image_paths))
        self.tile_grid_mode = True
        self.deep_zoom = None

    def clear_tile_grid(self):
        self.tile_grid_mode = False

    def _clear_deep_zoom(self):
        self.clear_deep_zoom_calls += 1
        self.deep_zoom = None
        self._deep_zoom_loading = None

    def load_deep_zoom_image(self, path):
        self.loaded_deep_zoom.append(path)
        self.deep_zoom = object()
        self._deep_zoom_loading = None

    def _schedule_settle_refit(self):
        self.settle_refit_calls += 1

    def update(self):
        self.update_calls += 1


class _FakeModel:
    def __init__(self):
        self.root_paths = []

    def setRootPath(self, path):  # noqa: N802 - Qt API  # NOSONAR
        self.root_paths.append(path)

    def index(self, path):
        return path


class _FakeTree:
    def __init__(self):
        self.roots = []

    def setRootIndex(self, index):  # noqa: N802 - Qt API  # NOSONAR
        self.roots.append(index)


class _FakeStack:
    def __init__(self):
        self.indices = []

    def setCurrentIndex(self, index):  # noqa: N802 - Qt API  # NOSONAR
        self.indices.append(index)


class _FakeToast:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


class _FakeTreeWatchdog:
    def __init__(self):
        self.paths = []

    def watch(self, path):
        self.paths.append(path)


class _StubMainWindow:
    _apply_refreshed_image_list = ImervueMainWindow._apply_refreshed_image_list
    _handle_active_folder_missing = ImervueMainWindow._handle_active_folder_missing
    _clear_view_folder_watch = ImervueMainWindow._clear_view_folder_watch
    _filter_image_paths = staticmethod(ImervueMainWindow._filter_image_paths)
    _nearest_existing_parent = staticmethod(ImervueMainWindow._nearest_existing_parent)

    def __init__(self, images=None):
        self.viewer = _FakeViewer(images)
        self._browse_mode = "grid"
        self.refresh_list_calls = 0
        self._view_stack = _FakeStack()
        self.model = _FakeModel()
        self.tree = _FakeTree()
        self.breadcrumb = SimpleNamespace(paths=[], set_path=lambda p: self.breadcrumb.paths.append(p))
        self.filename_label = SimpleNamespace(text="", setText=lambda t: setattr(self.filename_label, "text", t))
        self.toast = _FakeToast()
        self._tree_watchdog = _FakeTreeWatchdog()
        self.watched = []
        self._image_metadata_index = ImageMetadataIndex()

    def refresh_list_view(self):
        self.refresh_list_calls += 1

    def watch_folder(self, folder):
        self.watched.append(folder)

    def _refresh_tag_filter_options(self):
        """No-op: the stub has no tag-filter combo to repopulate."""

    def _current_filter_spec(self):
        return ImageFilterSpec()


def test_refresh_deep_zoom_keeps_current_image_when_still_present():
    win = _StubMainWindow(["/p/a.png", "/p/b.png"])
    win.viewer.current_index = 1
    win._apply_refreshed_image_list(["/p/b.png", "/p/c.png"])
    assert win.viewer.model.images == ["/p/b.png", "/p/c.png"]
    assert win.viewer.current_index == 0
    assert win.viewer.loaded_deep_zoom == []
    assert win.viewer.update_calls == 1


def test_refresh_deep_zoom_loads_neighbor_when_current_image_removed():
    win = _StubMainWindow(["/p/a.png", "/p/b.png", "/p/c.png"])
    win.viewer.current_index = 1
    win._apply_refreshed_image_list(["/p/a.png", "/p/c.png"])
    assert win.viewer.current_index == 1
    assert win.viewer.loaded_deep_zoom == ["/p/c.png"]
    assert win.viewer.clear_deep_zoom_calls == 1


def test_refresh_keeps_in_flight_load_when_image_still_present():
    # The click's deep-zoom load hasn't finished (deep_zoom is None) when a
    # folder refresh lands. The image is still in the list, so the in-flight
    # load must be preserved (no clear / reload) and the completion handler
    # left to display it — otherwise the click never enters deep zoom.
    win = _StubMainWindow(["/p/a.png", "/p/b.png"])
    win.viewer.deep_zoom = None
    win.viewer._deep_zoom_loading = "/p/b.png"
    win.viewer.current_index = 1
    win._apply_refreshed_image_list(["/p/b.png", "/p/c.png"])
    assert win.viewer.current_index == 0
    assert win.viewer.loaded_deep_zoom == []
    assert win.viewer.clear_deep_zoom_calls == 0
    assert win.viewer.settle_refit_calls == 1


def test_refresh_reenters_deep_zoom_when_in_flight_image_removed():
    # Same in-flight state, but the image being loaded has left the folder.
    # Recognising the in-flight load (not just a finished deep_zoom) means the
    # viewer re-enters deep zoom on a neighbour instead of stranding a stuck
    # "Loading…" view that the completion guard would silently discard.
    win = _StubMainWindow(["/p/a.png", "/p/b.png", "/p/c.png"])
    win.viewer.deep_zoom = None
    win.viewer._deep_zoom_loading = "/p/b.png"
    win.viewer.current_index = 1
    win._apply_refreshed_image_list(["/p/a.png", "/p/c.png"])
    assert win.viewer.loaded_deep_zoom == ["/p/c.png"]
    assert win.viewer.clear_deep_zoom_calls == 1


def test_refresh_refits_kept_deep_zoom_for_filmstrip_band():
    # A single-image folder gains a second image while the user is zoomed in on
    # the first (fit view). The filmstrip now appears and steals bottom space,
    # so the kept image must be re-fit — the "wrong size / strip not shown"
    # report. The settle re-fit is scheduled; it self-cancels if the user had
    # taken zoom control.
    win = _StubMainWindow(["/p/a.png"])
    win.viewer.current_index = 0
    win._apply_refreshed_image_list(["/p/a.png", "/p/b.png"])
    assert win.viewer.current_index == 0
    assert win.viewer.loaded_deep_zoom == []
    assert win.viewer.settle_refit_calls == 1


def test_refresh_does_not_refit_when_not_in_deep_zoom():
    # In list/grid browsing (no deep-zoom image, nothing loading) the kept-image
    # path must not schedule a deep-zoom re-fit.
    win = _StubMainWindow(["/p/a.png", "/p/b.png"])
    win.viewer.deep_zoom = None
    win.viewer._deep_zoom_loading = None
    win.viewer.current_index = 0
    win._apply_refreshed_image_list(["/p/a.png", "/p/c.png"])
    assert win.viewer.settle_refit_calls == 0


def test_refresh_empty_folder_clears_viewer():
    win = _StubMainWindow(["/p/a.png"])
    win._apply_refreshed_image_list([])
    assert win.viewer.loaded_grids == [[]]
    assert win.viewer.model.images == []
    assert win.viewer._unfiltered_images == []


def test_missing_active_folder_clears_viewer_and_roots_tree_to_parent(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    removed = parent / "removed"
    win = _StubMainWindow([str(removed / "a.png")])
    win._handle_active_folder_missing(str(removed))
    assert win.viewer.loaded_grids == [[]]
    assert win.viewer.model.images == []
    assert win.model.root_paths[-1] == str(parent)
    assert win.tree.roots[-1] == str(parent)
    assert win._tree_watchdog.paths[-1] == str(parent)
    assert win.toast.warnings


def test_image_filter_matches_filename():
    paths = ["/p/sunset.png", "/p/portrait.png"]
    assert ImervueMainWindow._filter_image_paths(paths, "sun") == ["/p/sunset.png"]


def test_image_filter_matches_rating():
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    old = user_setting_dict.get("image_ratings")
    try:
        user_setting_dict["image_ratings"] = {"/p/a.png": 4, "/p/b.png": 2}
        paths = ["/p/a.png", "/p/b.png"]
        assert ImervueMainWindow._filter_image_paths(paths, "rating:>=3") == ["/p/a.png"]
    finally:
        if old is None:
            user_setting_dict.pop("image_ratings", None)
        else:
            user_setting_dict["image_ratings"] = old
