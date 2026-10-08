"""Canonical preview/export color, byte metrics and discontinuous GPU-stage boundaries."""
from __future__ import annotations

from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageCms
from _icc_profiles import DISPLAY_P3, grey_profile

from Imervue.gpu_image_view.images.image_loader import decode_image_file
from Imervue.image import develop_backends
from Imervue.image.color_profile import to_srgb
from Imervue.image.develop_preview import PreviewCache, PreviewRequest, render_preview
from Imervue.image.export_metadata import export_save_options, srgb_profile
from Imervue.image.recipe import Recipe
from Imervue.image.save_formats import save_image
from gpu_develop.renderer import GpuDevelopRenderer
from scripts.gpu_develop_benchmark import pixel_difference, recipes


def _pixels():
    return np.random.default_rng(77).integers(0, 256, (32, 48, 4), dtype=np.uint8)


@pytest.mark.parametrize("profile", ["srgb", "p3", "grey18"])
@pytest.mark.parametrize("policy", ["all", "no_location", "none"])
@pytest.mark.parametrize("recipe_name", ["basic", "advanced", "threshold"])
def test_normalized_color_full_preview_and_lossless_export_agree(
        tmp_path, profile, policy, recipe_name):
    pixels = _pixels()
    source = Image.fromarray(pixels[..., 0] if profile == "grey18" else pixels)
    icc = {"srgb": srgb_profile(), "p3": DISPLAY_P3, "grey18": grey_profile(1.8)}[profile]
    source.info["icc_profile"] = icc
    path = tmp_path / "source.png"
    exif = Image.Exif()
    exif[0x0112] = 6
    source.save(path, icc_profile=icc, exif=exif)
    original = path.read_bytes()
    decoded = decode_image_file(str(path))
    expected_base = np.array(to_srgb(source).transpose(Image.Transpose.ROTATE_270).convert("RGBA"))
    np.testing.assert_array_equal(decoded, expected_base)
    recipe = (Recipe(shadows=.4, vibrance=.6, extra={"threshold": {"enabled": True, "level": 128}})
              if recipe_name == "threshold" else recipes()[recipe_name])
    request = PreviewRequest(1, str(path), Image.fromarray(decoded), recipe, Event())
    preview = render_preview(request, PreviewCache(), full=True)
    exported = develop_backends.render(decoded, recipe)
    np.testing.assert_array_equal(np.array(preview.image), exported)
    np.testing.assert_array_equal(exported[..., 3], decoded[..., 3])
    output = tmp_path / "export.png"
    save_image(Image.fromarray(exported), output, "PNG", extra=export_save_options(path, policy))
    np.testing.assert_array_equal(decode_image_file(str(output)), exported)
    with Image.open(output) as saved:
        assert 0x0112 not in saved.getexif()
        profile_bytes = saved.info.get("icc_profile")
        if policy == "none":
            assert profile_bytes is None
        else:
            import io
            output_profile = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
            assert "srgb" in ImageCms.getProfileDescription(output_profile).lower()
            if profile != "srgb":
                assert profile_bytes != icc
    assert path.read_bytes() == original
    np.testing.assert_array_equal(decoded, expected_base)


@pytest.mark.parametrize("kind", ["threshold", "posterize"])
def test_discontinuous_stages_use_reference_without_gpu_or_wgpu(kind, monkeypatch):
    renderer = object.__new__(GpuDevelopRenderer)
    renderer.label = "Offline GPU"
    monkeypatch.setattr(renderer, "_run", lambda *_: pytest.fail("quantized recipe used the GPU"))
    recipe = Recipe(shadows=.4, vibrance=.6, saturation=.2,
                    extra={kind: {"enabled": True, "level": 128, "levels": 4}})
    source = _pixels()
    before = source.copy()
    np.testing.assert_array_equal(renderer.render(source, recipe), recipe.apply(source))
    np.testing.assert_array_equal(source, before)


def test_byte_difference_counts_rgb_without_hiding_alpha_errors():
    expected = np.zeros((2, 2, 4), dtype=np.uint8)
    actual = expected.copy()
    actual[0, 0, 0] = 255
    actual[1, 1, 3] = 1
    report = pixel_difference(expected, actual)
    assert report["max_rgb_byte_error"] == 255
    assert report["changed_rgb_channels"] == 1
    assert report["changed_rgb_fraction"] == 1 / 12
    assert report["mean_rgb_byte_error"] == 255 / 12
    assert not report["byte_exact"] and not report["alpha_equal"]


@pytest.mark.parametrize("actual", [np.zeros((1, 1, 3), dtype=np.uint8),
                                   np.zeros((1, 1, 4), dtype=np.float32)])
def test_byte_difference_refuses_invalid_comparison(actual):
    with pytest.raises(ValueError):
        pixel_difference(np.zeros((1, 1, 4), dtype=np.uint8), actual)



@pytest.mark.parametrize("error", ["device lost", "GPU memory exhausted", "driver failure"])
def test_backend_failure_keeps_canonical_color_and_source(error, caplog):
    source = _pixels()
    before = source.copy()
    recipe = recipes()["advanced"]

    def fail(_array, _recipe):
        raise RuntimeError(error)

    renderer = SimpleNamespace(label="Unavailable GPU", render=fail)
    output = develop_backends.render(source, recipe, renderer)
    np.testing.assert_array_equal(output, recipe.apply(before))
    np.testing.assert_array_equal(source, before)
    assert error in caplog.text and "rendering it on the CPU" in caplog.text


@pytest.mark.parametrize("kind", ["threshold", "posterize"])
@pytest.mark.parametrize("setting", [None, [], {}, {"enabled": False}])
def test_disabled_or_invalid_quantizer_does_not_force_reference(kind, setting):
    from gpu_develop.params import requires_cpu_reference
    assert not requires_cpu_reference(Recipe(exposure=.1, extra={kind: setting}))



def test_geometry_lut_and_real_local_mask_keep_full_preview_export_parity(tmp_path):
    path = tmp_path / "invert.cube"
    rows = ["LUT_3D_SIZE 2"]
    for blue in (0, 1):
        for green in (0, 1):
            for red in (0, 1):
                rows.append(f"{1 - red} {1 - green} {1 - blue}")
    path.write_text("\n".join(rows), encoding="utf-8")
    source = _pixels()
    before = source.copy()
    recipe = Recipe(rotate_steps=1, flip_h=True, crop=(4, 3, 20, 15), exposure=.2,
                    lut_path=str(path), extra={"masks": [{"type": "radial", "params": {
                        "cx": 8, "cy": 6, "rx": 7, "ry": 5}, "adj": {"exposure": .4}}]})
    request = PreviewRequest(1, "source.png", Image.fromarray(source), recipe, Event())
    result = render_preview(request, PreviewCache(), full=True)
    np.testing.assert_array_equal(np.array(result.image), develop_backends.render(source, recipe))
    assert result.image.size == (20, 15) and result.full_quality
    np.testing.assert_array_equal(source, before)
