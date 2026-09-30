"""The wgpu develop renderer: slicing, dispatch shape, errors, and GPU output against ``Recipe.apply``.

The equivalence tests need ``wgpu`` and a graphics adapter. The product uses
only a discrete GPU; these tests take the discrete one when there is one and
otherwise any adapter wgpu offers (a software one on a CI runner), since what
they check is the shader's arithmetic, not the adapter policy.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import develop_backends
from Imervue.image.recipe import Recipe

from gpu_develop import renderer as renderer_mod
from gpu_develop.adapter_policy import choose_adapter
from gpu_develop.develop_shader import WORKGROUP_SIZE
from gpu_develop.renderer import GpuDevelopRenderer, dispatch_shape, slices

_SINGLE_STAGE = {
    "white balance": Recipe(temperature=0.3, tint=-0.2),
    "exposure": Recipe(exposure=0.7),
    "highlights and shadows": Recipe(highlights=-0.5, shadows=0.4),
    "whites and blacks": Recipe(whites=0.3, blacks=-0.4),
    "brightness": Recipe(brightness=0.25),
    "contrast": Recipe(contrast=0.4),
    "less contrast": Recipe(contrast=-0.6),
    "vibrance": Recipe(vibrance=0.6),
    "less vibrance": Recipe(vibrance=-0.5),
    "saturation": Recipe(saturation=-0.3),
    "tone curve": Recipe(tone_curve_rgb=[(0, 0), (0.25, 0.2), (0.75, 0.85), (1, 1)],
                         tone_curve_g=[(0, 0.05), (1, 0.95)]),
}
_EVERYTHING = Recipe(
    rotate_steps=1, flip_h=True, temperature=0.2, tint=0.1, exposure=0.3, highlights=-0.3,
    shadows=0.3, whites=0.2, blacks=-0.1, brightness=0.1, contrast=0.3, vibrance=0.4,
    saturation=0.2, tone_curve_rgb=[(0, 0), (0.5, 0.55), (1, 1)],
    extra={"levels": {"enabled": True, "black": 10, "white": 240, "gamma": 1.1}},
)


# ---- pure helpers ----------------------------------------------------------------

@pytest.mark.parametrize(("groups", "shape"), [
    (0, (1, 1)), (1, (1, 1)), (65535, (65535, 1)), (65536, (65535, 2)), (200000, (65535, 4)),
])
def test_dispatch_shape_stays_within_the_per_dimension_limit(groups, shape):
    assert dispatch_shape(groups) == shape
    assert shape[0] * shape[1] >= groups


def test_slices_cover_the_pixels_in_whole_workgroups():
    ranges = slices(1000, 300)
    assert ranges == [(0, 256), (256, 512), (512, 768), (768, 1000)]


def test_one_slice_when_everything_fits():
    assert slices(1000, 1 << 20) == [(0, 1000)]


def test_a_slice_is_never_smaller_than_a_workgroup():
    assert slices(600, 10) == [(0, WORKGROUP_SIZE), (WORKGROUP_SIZE, 2 * WORKGROUP_SIZE),
                               (2 * WORKGROUP_SIZE, 600)]


def test_probe_is_none_without_wgpu(monkeypatch):
    def missing():
        raise ImportError("No module named 'wgpu'")
    monkeypatch.setattr(renderer_mod, "_discrete_adapter", missing)
    assert renderer_mod.probe() is None


def test_probe_is_none_without_a_discrete_gpu(monkeypatch):
    monkeypatch.setattr(renderer_mod, "_discrete_adapter", lambda: None)
    assert renderer_mod.probe() is None


def test_no_discrete_gpu_refuses_to_open(monkeypatch):
    pytest.importorskip("wgpu")
    monkeypatch.setattr(renderer_mod, "_discrete_adapter", lambda: None)
    with pytest.raises(RuntimeError, match="integrated GPUs are not used"):
        GpuDevelopRenderer()


# ---- on a real adapter ------------------------------------------------------------

def _test_adapter():
    wgpu = pytest.importorskip("wgpu")
    adapters = [a for a in wgpu.gpu.enumerate_adapters_sync()
                if a.info["adapter_type"] != "Unknown"]      # not OpenGL
    if not adapters:
        pytest.skip("wgpu found no graphics adapter")
    index = choose_adapter([dict(a.info) for a in adapters])
    return adapters[0 if index is None else index]


@pytest.fixture(scope="module")
def gpu():
    renderer = GpuDevelopRenderer(_test_adapter())
    yield renderer
    renderer.close()


@pytest.fixture(scope="module")
def photo():
    rng = np.random.default_rng(7)
    image = rng.integers(0, 256, size=(240, 320, 4), dtype=np.uint8)
    image[..., 3] = rng.integers(0, 256, size=(240, 320), dtype=np.uint8)
    return image


def _compare(gpu, image, recipe):
    expected = recipe.apply(image)
    got = gpu.render(image, recipe)
    assert got.shape == expected.shape and got.dtype == np.uint8
    np.testing.assert_array_equal(got[..., 3], expected[..., 3])
    return np.abs(got.astype(int) - expected.astype(int))


@pytest.mark.parametrize("name", list(_SINGLE_STAGE))
def test_each_stage_matches_the_cpu_within_one_level(gpu, photo, name):
    diff = _compare(gpu, photo, _SINGLE_STAGE[name])
    assert diff.max() <= 1
    assert np.count_nonzero(diff) <= diff.size // 200      # at most 0.5 % of the values


def test_every_stage_together_stays_close_to_the_cpu(gpu, photo):
    diff = _compare(gpu, photo, _EVERYTHING)
    assert diff.max() <= 6      # one level off in vibrance, stretched by contrast, levels and curve
    assert np.count_nonzero(diff) <= diff.size // 20


def test_geometry_and_the_stages_after_the_gpu_run_on_the_cpu(gpu, photo):
    recipe = Recipe(rotate_steps=1, crop=(10, 20, 100, 50),
                    extra={"levels": {"enabled": True, "black": 20, "white": 200, "gamma": 1.0}})
    diff = _compare(gpu, photo, recipe)
    assert diff.shape == (50, 100, 4)
    assert not diff.any()


def test_an_identity_recipe_returns_the_image(gpu, photo):
    assert gpu.render(photo, Recipe()) is photo


def test_a_non_rgba_image_is_refused(gpu):
    with pytest.raises(ValueError, match="HxWx4"):
        gpu.render(np.zeros((4, 4, 3), dtype=np.uint8), Recipe(exposure=0.2))


def test_contrast_across_slices_uses_the_whole_images_mean(gpu, photo, monkeypatch):
    whole = gpu.render(photo, Recipe(brightness=0.1, contrast=0.5, vibrance=0.3))
    monkeypatch.setattr(gpu, "_slice_pixels", 5000)
    sliced = gpu.render(photo, Recipe(brightness=0.1, contrast=0.5, vibrance=0.3))
    np.testing.assert_array_equal(sliced, whole)


def test_a_one_pixel_image(gpu):
    pixel = np.array([[[10, 200, 90, 128]]], dtype=np.uint8)
    diff = _compare(gpu, pixel, Recipe(exposure=0.4, contrast=0.3, saturation=0.5))
    assert diff.max() <= 1


def test_a_gpu_error_becomes_a_runtime_error_and_the_image_renders_on_the_cpu(gpu, photo, monkeypatch):
    import wgpu

    def lost(*_args):
        raise wgpu.GPUInternalError("device lost")
    monkeypatch.setattr(gpu, "_run", lost)
    with pytest.raises(RuntimeError, match="device lost"):
        gpu.render(photo, Recipe(exposure=0.3))
    recipe = Recipe(exposure=0.3)
    np.testing.assert_array_equal(develop_backends.render(photo, recipe, gpu), recipe.apply(photo))


def test_a_device_that_fails_to_open_raises_runtime_error(monkeypatch):
    wgpu = pytest.importorskip("wgpu")
    adapter = _test_adapter()

    def refuse(self, _adapter):
        raise wgpu.GPUValidationError("limits")
    monkeypatch.setattr(GpuDevelopRenderer, "_open", refuse)
    with pytest.raises(RuntimeError, match="could not be opened"):
        GpuDevelopRenderer(adapter)


def test_a_changed_pipeline_is_never_rendered_on_the_gpu(monkeypatch, caplog):
    monkeypatch.setattr(renderer_mod, "stages_supported", lambda: False)
    monkeypatch.setattr(renderer_mod, "_discrete_adapter", lambda: pytest.fail("probed the GPU"))
    assert renderer_mod.probe() is None
    assert "update the plugin" in caplog.text
    with pytest.raises(RuntimeError, match="update the plugin"):
        GpuDevelopRenderer()
