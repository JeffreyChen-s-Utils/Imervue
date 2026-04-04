"""
Pytest configuration and shared fixtures for Imervue tests.
"""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


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
    return np.random.randint(0, 256, (80, 100, 3), dtype=np.uint8)


@pytest.fixture
def sample_rgba_array():
    """Create a simple 100x80 RGBA numpy array."""
    return np.random.randint(0, 256, (80, 100, 4), dtype=np.uint8)


@pytest.fixture
def sample_grayscale_array():
    """Create a simple 100x80 grayscale numpy array."""
    return np.random.randint(0, 256, (80, 100), dtype=np.uint8)


@pytest.fixture
def sample_png(tmp_path):
    """Create a temporary PNG image file."""
    path = tmp_path / "test_image.png"
    img = Image.fromarray(np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_jpeg(tmp_path):
    """Create a temporary JPEG image file."""
    path = tmp_path / "test_image.jpg"
    img = Image.fromarray(np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8))
    img.save(str(path))
    return str(path)


@pytest.fixture
def sample_grayscale_png(tmp_path):
    """Create a temporary grayscale PNG image file."""
    path = tmp_path / "gray_image.png"
    arr = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
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


@pytest.fixture
def image_folder(tmp_path):
    """Create a temporary folder with several test images."""
    names = ["alpha.png", "beta.jpg", "gamma.png", "delta.bmp"]
    for name in names:
        p = tmp_path / name
        arr = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        fmt = "PNG" if name.endswith(".png") else ("JPEG" if name.endswith(".jpg") else "BMP")
        if fmt == "JPEG":
            img = img.convert("RGB")
        img.save(str(p), format=fmt)
    return str(tmp_path)
