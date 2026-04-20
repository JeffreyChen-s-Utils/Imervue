"""Tests for the .cube LUT reader/applier."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import lut as lut_mod


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _identity_3d_cube(size: int = 3) -> str:
    """Return a .cube file body that is an identity 3D LUT of the given size."""
    lines = [f"LUT_3D_SIZE {size}"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                lines.append(
                    f"{r / (size - 1):.6f} {g / (size - 1):.6f} {b / (size - 1):.6f}"
                )
    return "\n".join(lines)


def _invert_3d_cube(size: int = 3) -> str:
    lines = [f"LUT_3D_SIZE {size}"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                lines.append(
                    f"{1 - r / (size - 1):.6f} {1 - g / (size - 1):.6f} {1 - b / (size - 1):.6f}"
                )
    return "\n".join(lines)


@pytest.fixture(autouse=True)
def _clear_cache():
    lut_mod.clear_cache()
    yield
    lut_mod.clear_cache()


class TestParse:
    def test_parses_identity_3d(self, tmp_path):
        path = _write(tmp_path, "identity.cube", _identity_3d_cube(3))
        lut = lut_mod.parse_cube(path)
        assert lut.is_3d
        assert lut.size == 3
        assert lut.table.shape == (3, 3, 3, 3)

    def test_parses_1d_lut(self, tmp_path):
        body = "LUT_1D_SIZE 4\n0.0 0.0 0.0\n0.33 0.33 0.33\n0.66 0.66 0.66\n1.0 1.0 1.0\n"
        path = _write(tmp_path, "mono.cube", body)
        lut = lut_mod.parse_cube(path)
        assert not lut.is_3d
        assert lut.size == 4

    def test_ignores_title_and_comments(self, tmp_path):
        body = (
            '# leading comment\nTITLE "my test"\n'
            + _identity_3d_cube(3)
            + "\n# trailing comment\n"
        )
        path = _write(tmp_path, "cmt.cube", body)
        lut = lut_mod.parse_cube(path)
        assert lut.size == 3

    def test_missing_size_header_raises(self, tmp_path):
        path = _write(tmp_path, "bad.cube", "0.0 0.0 0.0\n")
        with pytest.raises(ValueError):
            lut_mod.parse_cube(path)

    def test_wrong_row_count_raises(self, tmp_path):
        body = "LUT_3D_SIZE 3\n0 0 0\n1 1 1\n"
        path = _write(tmp_path, "short.cube", body)
        with pytest.raises(ValueError):
            lut_mod.parse_cube(path)

    def test_rejects_oversized_lut(self, tmp_path):
        body = "LUT_3D_SIZE 128\n"
        path = _write(tmp_path, "huge.cube", body)
        with pytest.raises(ValueError):
            lut_mod.parse_cube(path)


class TestApply:
    def test_identity_lut_leaves_pixels_unchanged(self, tmp_path):
        path = _write(tmp_path, "id.cube", _identity_3d_cube(5))
        rng = np.random.default_rng(0)
        arr = rng.integers(0, 256, (4, 6, 4), dtype=np.uint8)
        out = lut_mod.apply_cube_lut(arr, path, intensity=1.0)
        np.testing.assert_array_equal(out[..., 3], arr[..., 3])
        # Identity LUT should be within 1 step of the input (rounding).
        diff = np.abs(out[..., :3].astype(int) - arr[..., :3].astype(int))
        assert diff.max() <= 1

    def test_invert_lut_inverts_rgb(self, tmp_path):
        path = _write(tmp_path, "inv.cube", _invert_3d_cube(5))
        arr = np.full((2, 2, 4), 64, dtype=np.uint8)
        out = lut_mod.apply_cube_lut(arr, path, intensity=1.0)
        assert abs(int(out[0, 0, 0]) - (255 - 64)) <= 2

    def test_intensity_zero_is_passthrough(self, tmp_path):
        path = _write(tmp_path, "inv.cube", _invert_3d_cube(5))
        arr = np.full((2, 2, 4), 64, dtype=np.uint8)
        out = lut_mod.apply_cube_lut(arr, path, intensity=0.0)
        assert out is arr or np.array_equal(out, arr)

    def test_intensity_half_blends(self, tmp_path):
        path = _write(tmp_path, "inv.cube", _invert_3d_cube(5))
        arr = np.full((2, 2, 4), 64, dtype=np.uint8)
        out = lut_mod.apply_cube_lut(arr, path, intensity=0.5)
        expected = (64 + (255 - 64)) // 2
        assert abs(int(out[0, 0, 0]) - expected) <= 2

    def test_rejects_non_rgba(self, tmp_path):
        path = _write(tmp_path, "id.cube", _identity_3d_cube(3))
        arr = np.zeros((2, 2, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            lut_mod.apply_cube_lut(arr, path)

    def test_alpha_preserved(self, tmp_path):
        path = _write(tmp_path, "inv.cube", _invert_3d_cube(3))
        arr = np.full((2, 2, 4), 200, dtype=np.uint8)
        arr[..., 3] = 128
        out = lut_mod.apply_cube_lut(arr, path)
        assert (out[..., 3] == 128).all()
