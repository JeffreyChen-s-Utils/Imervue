"""The develop-backend registry: registering, probing, opening and the CPU fallback."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import develop_backends
from Imervue.image.develop_backends import CPU, BackendProvider
from Imervue.image.recipe import Recipe


@pytest.fixture(autouse=True)
def _empty_registry(monkeypatch):
    monkeypatch.setattr(develop_backends, "_providers", {})


class _Renderer:
    label = "Fake GPU"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0
        self.closed = False

    def render(self, arr, recipe):
        self.calls += 1
        if self.fail:
            raise RuntimeError("device lost")
        return np.zeros_like(arr)

    def close(self):
        self.closed = True


def _provider(key="fake", label="Fake GPU", opener=_Renderer):
    return BackendProvider(key=key, probe=lambda: label, open=opener)


def _image():
    return np.full((4, 6, 4), 100, dtype=np.uint8)


def test_nothing_is_available_until_a_backend_registers():
    assert develop_backends.available() == []


def test_a_registered_backend_is_offered_with_its_probe_label():
    develop_backends.register(_provider())
    assert develop_backends.available() == [("fake", "Fake GPU")]


def test_registering_the_same_key_replaces_the_backend():
    develop_backends.register(_provider(label="old"))
    develop_backends.register(_provider(label="new"))
    assert develop_backends.available() == [("fake", "new")]


def test_the_cpu_key_is_reserved():
    with pytest.raises(ValueError, match="built-in"):
        develop_backends.register(_provider(key=CPU))


def test_unregister_removes_the_backend_and_ignores_unknown_keys():
    develop_backends.register(_provider())
    develop_backends.unregister("fake")
    develop_backends.unregister("never-registered")
    assert develop_backends.available() == []


@pytest.mark.parametrize("label", [None, ""])
def test_a_backend_that_cannot_run_here_is_not_offered(label):
    develop_backends.register(_provider(label=label))
    assert develop_backends.available() == []


@pytest.mark.parametrize("error", [RuntimeError("driver"), OSError("dll"), ImportError("wgpu")])
def test_a_probe_that_fails_hides_only_that_backend(error, caplog):
    def broken():
        raise error
    develop_backends.register(BackendProvider(key="broken", probe=broken, open=_Renderer))
    develop_backends.register(_provider())
    assert develop_backends.available() == [("fake", "Fake GPU")]
    assert "cannot run" in caplog.text


def test_open_renderer_builds_the_backends_renderer():
    develop_backends.register(_provider())
    assert isinstance(develop_backends.open_renderer("fake"), _Renderer)


@pytest.mark.parametrize("key", [CPU, "unknown"])
def test_open_renderer_gives_none_for_the_cpu_and_unknown_keys(key):
    develop_backends.register(_provider())
    assert develop_backends.open_renderer(key) is None


@pytest.mark.parametrize("error", [RuntimeError("no device"), OSError("dll"), ImportError("wgpu")])
def test_a_backend_that_fails_to_open_leaves_the_cpu(error, caplog):
    def opener():
        raise error
    develop_backends.register(_provider(opener=opener))
    assert develop_backends.open_renderer("fake") is None
    assert "failed to open" in caplog.text


def test_render_without_a_renderer_is_recipe_apply():
    recipe = Recipe(exposure=0.5)
    np.testing.assert_array_equal(develop_backends.render(_image(), recipe), recipe.apply(_image()))


def test_render_uses_the_renderer():
    renderer = _Renderer()
    out = develop_backends.render(_image(), Recipe(exposure=0.5), renderer)
    assert renderer.calls == 1
    assert not out.any()


def test_an_identity_recipe_never_reaches_the_renderer():
    renderer = _Renderer()
    image = _image()
    assert develop_backends.render(image, Recipe(), renderer) is image
    assert renderer.calls == 0


def test_a_renderer_failure_renders_that_image_on_the_cpu(caplog):
    recipe = Recipe(exposure=0.5)
    out = develop_backends.render(_image(), recipe, _Renderer(fail=True))
    np.testing.assert_array_equal(out, recipe.apply(_image()))
    assert "Fake GPU failed" in caplog.text
