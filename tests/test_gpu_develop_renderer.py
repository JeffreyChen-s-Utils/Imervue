"""The wgpu develop renderer: slicing, dispatch shape, errors, and GPU output against ``Recipe.apply``.

The equivalence tests need ``wgpu`` and a graphics adapter. The product uses
only a discrete GPU; these tests take the discrete one when there is one and
otherwise any adapter wgpu offers (a software one on a CI runner), since what
they check is the shader's arithmetic, not the adapter policy. The GPU work
runs in a subprocess (``_gpu_render_worker.py``): creating a wgpu instance in a
pytest worker that had already run OpenGL tests crashed or hung the worker.
Everything else here runs in-process without a device.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.image import develop_backends
from Imervue.image.recipe import Recipe

from _gpu_render_worker import CASES, PIXEL_RECIPE, SINGLE_STAGES, one_pixel, photo
from gpu_develop import renderer as renderer_mod
from gpu_develop.develop_shader import WORKGROUP_SIZE
from gpu_develop.renderer import GpuDevelopRenderer, dispatch_shape, slices

_WORKER = Path(__file__).with_name("_gpu_render_worker.py")


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


def test_a_changed_pipeline_is_never_rendered_on_the_gpu(monkeypatch, caplog):
    monkeypatch.setattr(renderer_mod, "stages_supported", lambda: False)
    monkeypatch.setattr(renderer_mod, "_discrete_adapter", lambda: pytest.fail("probed the GPU"))
    assert renderer_mod.probe() is None
    assert "update the plugin" in caplog.text
    with pytest.raises(RuntimeError, match="update the plugin"):
        GpuDevelopRenderer()


def test_limit_backends_creates_the_instance_without_opengl(monkeypatch):
    pytest.importorskip("wgpu")
    from wgpu.backends.wgpu_native import extras
    calls = []
    monkeypatch.setattr(extras, "set_instance_extras", lambda **kwargs: calls.append(kwargs))
    renderer_mod.limit_backends()
    assert calls == [{"backends": renderer_mod.instance_backends()}]
    assert "GL" not in calls[0]["backends"]


def test_limit_backends_keeps_an_instance_that_already_exists(monkeypatch, caplog):
    pytest.importorskip("wgpu")
    from wgpu.backends.wgpu_native import extras

    def exists(**_kwargs):
        raise RuntimeError("Instance already exists")
    monkeypatch.setattr(extras, "set_instance_extras", exists)
    caplog.set_level("DEBUG", logger="Imervue.plugin.gpu_develop")
    renderer_mod.limit_backends()
    assert "already exists" in caplog.text


# ---- the renderer without a device ----------------------------------------------------

def test_no_discrete_gpu_refuses_to_open(monkeypatch):
    pytest.importorskip("wgpu")
    monkeypatch.setattr(renderer_mod, "_discrete_adapter", lambda: None)
    with pytest.raises(RuntimeError, match="integrated GPUs are not used"):
        GpuDevelopRenderer()


def _fake_adapter():
    return SimpleNamespace(info={"device": "Fake GPU", "backend_type": "Vulkan", "adapter_type": "DiscreteGPU"},
                           limits={"max-storage-buffer-binding-size": 1 << 27, "max-buffer-size": 1 << 28})


def test_a_device_that_fails_to_open_raises_runtime_error(monkeypatch):
    wgpu = pytest.importorskip("wgpu")

    def refuse(self, _adapter):
        raise wgpu.GPUValidationError("limits")
    monkeypatch.setattr(GpuDevelopRenderer, "_open", refuse)
    with pytest.raises(RuntimeError, match="Fake GPU .Vulkan. could not be opened"):
        GpuDevelopRenderer(_fake_adapter())


@pytest.fixture
def offline(monkeypatch):
    """A renderer whose device is never opened; ``_run`` must be patched before it is reached."""
    pytest.importorskip("wgpu")
    monkeypatch.setattr(GpuDevelopRenderer, "_open", lambda self, adapter: None)
    return GpuDevelopRenderer(_fake_adapter())


def test_an_identity_recipe_returns_the_image(offline):
    image = photo()
    assert offline.render(image, Recipe()) is image


def test_a_non_rgba_image_is_refused(offline):
    with pytest.raises(ValueError, match="HxWx4"):
        offline.render(np.zeros((4, 4, 3), dtype=np.uint8), Recipe(exposure=0.2))


def test_a_recipe_without_gpu_work_never_reaches_the_device(offline, monkeypatch):
    monkeypatch.setattr(offline, "_run", lambda *_a: pytest.fail("used the GPU"))
    recipe = CASES["geometry and levels"]
    np.testing.assert_array_equal(offline.render(photo(), recipe), recipe.apply(photo()))


def test_a_gpu_error_becomes_a_runtime_error_and_the_image_renders_on_the_cpu(offline, monkeypatch):
    import wgpu

    def lost(*_args):
        raise wgpu.GPUInternalError("device lost")
    monkeypatch.setattr(offline, "_run", lost)
    recipe = Recipe(exposure=0.3)
    with pytest.raises(RuntimeError, match="device lost"):
        offline.render(photo(), recipe)
    np.testing.assert_array_equal(develop_backends.render(photo(), recipe, offline), recipe.apply(photo()))


# ---- on a real adapter, in a subprocess ----------------------------------------------

@pytest.fixture(scope="module")
def gpu(tmp_path_factory):
    """Every case of ``_gpu_render_worker.CASES`` rendered on the GPU in a fresh process."""
    pytest.importorskip("wgpu")
    out = tmp_path_factory.mktemp("gpu") / "renders.npz"
    done = subprocess.run([sys.executable, str(_WORKER), str(out)], capture_output=True, text=True,
                          timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    with np.load(out) as archive:
        results = {name: archive[name] for name in archive.files}
    if "skip" in results:
        pytest.skip(str(results["skip"]))
    return results


def _diff(got: np.ndarray, expected: np.ndarray) -> np.ndarray:
    assert got.shape == expected.shape and got.dtype == np.uint8
    np.testing.assert_array_equal(got[..., 3], expected[..., 3])
    return np.abs(got.astype(int) - expected.astype(int))


@pytest.mark.parametrize("name", SINGLE_STAGES)
def test_each_stage_matches_the_cpu_within_one_level(gpu, name):
    diff = _diff(gpu[name], CASES[name].apply(photo()))
    assert diff.max() <= 1
    assert np.count_nonzero(diff) <= diff.size // 200      # at most 0.5 % of the values


def test_every_stage_together_stays_close_to_the_cpu(gpu):
    diff = _diff(gpu["everything"], CASES["everything"].apply(photo()))
    assert diff.max() <= 6      # one level off in vibrance, stretched by contrast, levels and curve
    assert np.count_nonzero(diff) <= diff.size // 20


def test_geometry_and_the_stages_after_the_gpu_run_on_the_cpu(gpu):
    diff = _diff(gpu["geometry and levels"], CASES["geometry and levels"].apply(photo()))
    assert diff.shape == (50, 100, 4)
    assert not diff.any()


def test_contrast_across_slices_uses_the_whole_images_mean(gpu):
    np.testing.assert_array_equal(gpu["sliced contrast"], gpu["whole contrast"])


def test_a_one_pixel_image(gpu):
    assert _diff(gpu["one pixel"], PIXEL_RECIPE.apply(one_pixel())).max() <= 1


def test_the_renderer_names_its_adapter(gpu):
    assert str(gpu["adapter"]).endswith(")")
