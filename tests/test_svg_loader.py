"""Tests for SVG loading support."""
import numpy as np
import pytest

pytest.importorskip("imageio")
pytest.importorskip("rawpy")


class TestSVGLoader:
    def test_svg_in_supported_exts(self):
        from Imervue.gpu_image_view.images.image_loader import _SUPPORTED_EXTS
        assert ".svg" in _SUPPORTED_EXTS

    def test_load_svg_file(self, tmp_path):
        """A minimal SVG should load as RGBA numpy array."""
        svg_path = tmp_path / "test.svg"
        svg_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
            '<rect width="64" height="64" fill="red"/>'
            '</svg>'
        )
        from Imervue.gpu_image_view.images.image_loader import load_image_file
        result = load_image_file(str(svg_path))
        assert result.ndim == 3
        assert result.shape[2] == 4
        assert result.shape[0] == 64
        assert result.shape[1] == 64
        # Red rect → R channel should be dominant
        assert result[:, :, 0].mean() > 200

    def test_scan_finds_svg(self, tmp_path):
        """_scan_images should find .svg files."""
        svg_path = tmp_path / "icon.svg"
        svg_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
        )
        from Imervue.gpu_image_view.images.image_loader import _scan_images
        result = _scan_images(str(tmp_path))
        assert any(p.endswith(".svg") for p in result)
