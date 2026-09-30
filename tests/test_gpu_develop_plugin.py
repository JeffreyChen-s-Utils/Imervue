"""The GPU Develop plugin: registering the backend per window, the menu entry and its status box."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMenu

from Imervue.image import develop_backends

from gpu_develop import gpu_develop_plugin as plugin_mod
from gpu_develop.gpu_develop_plugin import BACKEND_KEY, GpuDevelopPlugin, status_text
from gpu_develop.translations import TRANSLATIONS


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(develop_backends, "_providers", {})
    monkeypatch.setattr(plugin_mod, "_live", set())
    monkeypatch.setattr(plugin_mod.language_wrapper, "language_word_dict", {})


def _plugin():
    return GpuDevelopPlugin(SimpleNamespace(viewer=None))


def _registered():
    return BACKEND_KEY in develop_backends._providers  # noqa: SLF001


def test_loading_registers_the_gpu_backend():
    _plugin().on_plugin_loaded()
    assert develop_backends._providers[BACKEND_KEY] is plugin_mod.PROVIDER  # noqa: SLF001


def test_the_backend_stays_while_another_window_still_has_the_plugin():
    first, second = _plugin(), _plugin()
    first.on_plugin_loaded()
    second.on_plugin_loaded()
    first.on_plugin_unloaded()
    assert _registered()
    second.on_plugin_unloaded()
    assert not _registered()


def test_unloading_twice_is_harmless():
    plugin = _plugin()
    plugin.on_plugin_loaded()
    plugin.on_plugin_unloaded()
    plugin.on_plugin_unloaded()
    assert not _registered()


def test_the_provider_probes_and_opens_the_wgpu_renderer():
    from gpu_develop.renderer import GpuDevelopRenderer, probe
    assert plugin_mod.PROVIDER.probe is probe
    assert plugin_mod.PROVIDER.open is GpuDevelopRenderer


def test_status_names_the_gpu():
    assert "RTX 5060 (Vulkan)" in status_text("RTX 5060 (Vulkan)")
    assert "Render on" in status_text("RTX 5060 (Vulkan)")


def test_status_without_a_discrete_gpu_says_the_cpu_renders():
    text = status_text(None)
    assert "Integrated GPUs are not used" in text and "CPU" in text


def test_status_uses_the_current_language(monkeypatch):
    monkeypatch.setattr(plugin_mod.language_wrapper, "language_word_dict",
                        TRANSLATIONS["Traditional_Chinese"])
    assert "RTX" in status_text("RTX")
    assert "獨立顯示卡" in status_text(None)


def test_every_language_has_every_string():
    keys = set(TRANSLATIONS["English"])
    assert set(TRANSLATIONS) == {"English", "Traditional_Chinese", "Chinese", "Japanese", "Korean"}
    for language, strings in TRANSLATIONS.items():
        assert set(strings) == keys, language
        assert "{gpu}" in strings["gpu_develop_found"], language


def test_get_translations_hands_over_the_table():
    assert _plugin().get_translations() is TRANSLATIONS


def test_the_plugins_menu_gets_the_status_entry(qapp):
    menu = QMenu()
    try:
        _plugin().on_build_menu_bar(menu)
        assert [a.text() for a in menu.actions()] == ["GPU Develop…"]
    finally:
        menu.deleteLater()


def test_the_entry_installs_wgpu_first_when_it_is_missing(monkeypatch):
    plugin = _plugin()
    calls = []
    monkeypatch.setattr(plugin_mod, "wgpu_installed", lambda: False)
    monkeypatch.setattr(plugin_mod, "ensure_dependencies",
                        lambda parent, packages, on_ready: calls.append((parent, packages, on_ready)))
    plugin._show_status()  # noqa: SLF001
    ((parent, packages, on_ready),) = calls
    assert parent is plugin.main_window
    assert packages == [("wgpu", "wgpu")]
    assert on_ready == plugin._report  # noqa: SLF001


def test_the_entry_reports_the_gpu_when_wgpu_is_there(monkeypatch):
    shown = []
    monkeypatch.setattr(plugin_mod, "wgpu_installed", lambda: True)
    monkeypatch.setattr(plugin_mod, "probe", lambda: "RTX 5060 (Vulkan)")
    monkeypatch.setattr(plugin_mod.QMessageBox, "information",
                        lambda parent, title, text: shown.append((title, text)))
    _plugin()._show_status()  # noqa: SLF001
    ((title, text),) = shown
    assert title == "GPU Develop"
    assert "RTX 5060 (Vulkan)" in text


def test_wgpu_installed_is_false_for_a_broken_spec(monkeypatch):
    def broken(_name):
        raise ValueError("wgpu.__spec__ is None")
    monkeypatch.setattr(plugin_mod.importlib.util, "find_spec", broken)
    assert plugin_mod.wgpu_installed() is False


def test_wgpu_installed_follows_find_spec(monkeypatch):
    monkeypatch.setattr(plugin_mod.importlib.util, "find_spec", lambda _name: None)
    assert plugin_mod.wgpu_installed() is False
    monkeypatch.setattr(plugin_mod.importlib.util, "find_spec", lambda _name: object())
    assert plugin_mod.wgpu_installed() is True


def test_the_package_exposes_the_plugin_class():
    import gpu_develop
    assert gpu_develop.plugin_class is GpuDevelopPlugin
