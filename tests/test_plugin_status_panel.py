"""Actual Qt management rows and independent per-window reload/import outcomes."""
from types import SimpleNamespace

from PySide6.QtWidgets import QMainWindow

from Imervue.plugin import plugin_manager as mod
from Imervue.plugin.status import status_registry
from Imervue.menu.plugin_menu import _PluginManageDialog


def write_plugin(path, version, *, broken=False):
    path.mkdir(exist_ok=True)
    source = "raise RuntimeError('broken dependency')" if broken else (
        "from Imervue.plugin.plugin_base import ImervuePlugin\n"
        "class Plugin(ImervuePlugin):\n"
        "    plugin_name = 'Test Plugin'\n"
        f"    plugin_version = '{version}'\n"
        "plugin_class = Plugin\n")
    (path / "__init__.py").write_text(source, encoding="utf-8")


def test_failed_import_recovery_fresh_code_and_other_window(qapp, tmp_path, monkeypatch):
    windows = [QMainWindow(), QMainWindow()]
    managers = [mod.PluginManager(SimpleNamespace(viewer=None)) for _window in windows]
    plugin = tmp_path / "unique_status_plugin"
    write_plugin(plugin, "1", broken=True)
    try:
        for manager in managers:
            manager.discover_and_load([tmp_path])
            assert not manager.plugins
            rows = status_registry.snapshot(manager.status_scope)
            assert any(row.status == "failed" and "broken dependency" in row.reason for row in rows)
        write_plugin(plugin, "version-two")
        managers[0].refresh_imports()
        managers[0].unload_all()
        managers[0].discover_and_load([tmp_path])
        assert managers[0].plugins[0].plugin_version == "version-two"
        assert not managers[1].plugins
        windows[0].plugin_manager = managers[0]
        dialog = _PluginManageDialog(windows[0])
        status_registry.publish("test-download", "Test Download", "downloading", "Model.onnx")
        dialog._refresh_status()
        rows = [dialog._status_tree.topLevelItem(i)
                for i in range(dialog._status_tree.topLevelItemCount())]
        assert any(row.text(0) == "Test Download" and row.text(2) == "Model.onnx" for row in rows)
        assert dialog._tree.topLevelItemCount() == 1
        dialog.deleteLater()
        write_plugin(plugin, "version-three")
        managers[0].refresh_imports()
        managers[0].unload_all()
        managers[0].discover_and_load([tmp_path])
        assert managers[0].plugins[0].plugin_version == "version-three"
    finally:
        for manager, window in zip(managers, windows, strict=True):
            manager.unload_all()
            window.deleteLater()


def test_backend_failure_explains_actual_cpu_fallback(monkeypatch):
    from Imervue.image import develop_backends as backends
    monkeypatch.setattr(backends, "_providers", {})
    def fail():
        raise RuntimeError("driver unavailable")
    backends.register(backends.BackendProvider("test-device", fail, fail))
    assert backends.available() == [] and backends.open_renderer("test-device") is None
    row = next(row for row in status_registry.snapshot() if row.key == "backend:test-device")
    assert row.status == "failed" and "CPU fallback" in row.reason
    assert "driver unavailable" in row.reason
