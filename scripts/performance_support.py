"""Deterministic fixtures, measurements and isolated profiles for developer benchmarks."""
from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import math
import os
import platform
import statistics
import threading
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

FIXTURE_VERSION = 1
MIB = 1024 * 1024


def summarize(samples: list[float]) -> dict:
    """Nearest-rank p95; retain raw samples so small runs cannot imply precision."""
    if not samples or any(not math.isfinite(x) or x < 0 for x in samples):
        raise ValueError("measurements must be finite, non-negative and non-empty")
    ordered = sorted(samples)
    return {"samples_ms": samples, "median_ms": statistics.median(samples),
            "p95_ms": ordered[math.ceil(len(ordered) * .95) - 1],
            "min_ms": ordered[0], "max_ms": ordered[-1]}


def working_set() -> tuple[int, int]:
    """Current and lifetime peak resident bytes; use native counters on Windows."""
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD),
                       *[(name, ctypes.c_size_t) for name in
                         ("peak", "current", "pool_peak", "pool", "nonpool_peak",
                          "nonpool", "pagefile", "pagefile_peak")]]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters),
                                          counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.current), int(counters.peak)
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak *= 1 if platform.system() == "Darwin" else 1024
    stat = Path("/proc/self/statm")
    current = (int(stat.read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
               if stat.exists() else peak)
    return current, peak


def measure(operation: Callable, *, repeats: int = 3) -> dict:
    """Sample operation RSS independently of lifetime high-water marks."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    before, _ = working_set()
    rss = [before]
    stop = threading.Event()

    def sample():
        while not stop.wait(.005):
            rss.append(working_set()[0])

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    durations = []
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            operation()
            durations.append((time.perf_counter() - start) * 1000)
            rss.append(working_set()[0])
    finally:
        stop.set()
        sampler.join()
    _, lifetime_peak = working_set()
    return {**summarize(durations), "rss_before_bytes": before, "rss_peak_bytes": max(rss),
            "rss_growth_bytes": max(rss) - before, "process_peak_bytes": lifetime_peak}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def gradient(width: int, height: int, seed: int = 0):
    """Bounded-temporary RGBA gradient, also used for compressible Paint layers."""
    import numpy as np
    image = np.empty((height, width, 4), dtype=np.uint8)
    x = np.arange(width, dtype=np.uint16)[None, :]
    y = np.arange(height, dtype=np.uint16)[:, None]
    image[..., 0] = (x + seed * 19) % 256
    image[..., 1] = (y + seed * 31) % 256
    image[..., 2] = (x // 4 + y // 4 + seed * 17) % 256
    image[..., 3] = 255
    return image


def _link(seed: Path, target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    # Copies keep the tool portable to filesystems without hard links.
    try:
        os.link(seed, target)
    except OSError:
        target.write_bytes(seed.read_bytes())


def prepare_fixtures(root: Path, *, quick: bool = False) -> dict:
    """Refuse existing unowned directories; never remove another directory's files."""
    from PIL import Image
    manifest_path = root / "manifest.json"
    expected = {"fixture_version": FIXTURE_VERSION, "quick": quick}
    if root.exists():
        if not manifest_path.exists():
            raise ValueError("fixture directory exists without an ownership manifest")
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(previous.get(key) != value for key, value in expected.items()):
            raise ValueError("fixture version or scenario differs; choose a new directory")
        for field, directory in (("seed_sha256", root / "seeds"), ("image_sha256", root)):
            for name, digest in previous.get(field, {}).items():
                if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                    raise ValueError(f"fixture content changed: {name}")
    else:
        root.mkdir(parents=True)
        write_json(manifest_path, expected)
    seed_dir = root / "seeds"
    seed_dir.mkdir(exist_ok=True)
    seeds = []
    for i in range(32):
        seed = seed_dir / f"{i:02d}.jpg"
        if not seed.exists():
            Image.fromarray(gradient(32, 24, i)).convert("RGB").save(seed, quality=90)
        seeds.append(seed)
    counts = [100, 1000] if quick else [10_000, 100_000]
    for count in counts:
        for i in range(count):
            _link(seeds[i % len(seeds)], root / f"library-{count}" / f"{i % 32:02d}"
                  / f"image-{i:06d}.jpg")
    dimensions = [[600, 400], [1000, 600]] if quick else [[6000, 4000], [10_000, 6000]]
    for label, (width, height) in zip(("24mp", "60mp"), dimensions, strict=True):
        target = root / f"{label}.jpg"
        if not target.exists():
            Image.fromarray(gradient(width, height)).convert("RGB").save(target, quality=90)
    png = seed_dir / "cache.png"
    if not png.exists():
        Image.new("RGBA", (32, 24), (17, 31, 47, 255)).save(png)
    for i in range(counts[-1]):
        _link(png, root / "large-cache" / f"{i:032x}.png")
    manifest = {**expected, "libraries": counts, "dimensions": dimensions,
                "paint_dimensions": [384, 216] if quick else [3840, 2160], "paint_layers": 6,
                "seed_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in seeds},
                "image_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (root / "24mp.jpg", root / "60mp.jpg")},
                "library_pixels": ("32 repeated 32x24 JPEG seeds with unique names; "
                                   "hard links where supported"),
                "cache_pixels": ("repeated 32x24 PNG; measures entry/stat overhead, "
                                 "not full-size thumbnails")}
    write_json(manifest_path, manifest)
    return manifest


@contextlib.contextmanager
def isolated_profile(root: Path):
    """Redirect every benchmark child before any application module imports."""
    root.mkdir(parents=True, exist_ok=False)
    home = root / "home"
    home.mkdir()
    with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}), \
            patch("pathlib.Path.home", return_value=home):
        from Imervue.system import app_paths
        with patch.object(app_paths, "user_settings_path", return_value=root / "settings.json"), \
                patch.object(app_paths, "plugins_dir", return_value=root / "empty-plugins"):
            yield
