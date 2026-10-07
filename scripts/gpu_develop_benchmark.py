"""Measure the optional GPU backend in fresh processes; never change preview defaults."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / "plugins"):
    sys.path.insert(0, str(directory))

from Imervue.image.recipe import Recipe  # noqa: E402
from scripts.performance_support import gradient, measure, write_json  # noqa: E402

CASES = ("preview", "24mp", "60mp")


def recipes() -> dict[str, Recipe]:
    """The existing reduced-preview recipe plus explicit post-GPU color stages."""
    basic = Recipe(exposure=.25, temperature=.1, shadows=.1, vibrance=.1)
    advanced = Recipe.from_dict(basic.to_dict())
    advanced.contrast, advanced.saturation = .3, .2
    advanced.tone_curve_rgb = [(0, 0), (.5, .55), (1, 1)]
    advanced.extra = {
        "split_toning": {"shadow_hue": 210, "shadow_sat": .1,
                         "highlight_hue": 45, "highlight_sat": .1},
        "levels": {"enabled": True, "black": 10, "white": 240, "gamma": 1.1},
        "channel_mixer": {"enabled": True, "red": [.9, .05, .05],
                          "green": [.05, .9, .05], "blue": [.05, .05, .9]},
    }
    return {"basic": basic, "advanced": advanced}


def pixel_difference(expected: np.ndarray, actual: np.ndarray) -> dict:
    """Exact RGB byte differences, bounded temporaries; not a perceptual color score."""
    if expected.shape != actual.shape or expected.dtype != np.uint8 or actual.dtype != np.uint8:
        raise ValueError("equally shaped uint8 images required")
    if expected.ndim != 3 or expected.shape[2] != 4 or not expected.size:
        raise ValueError("nonempty HxWx4 RGBA images required")
    changed = total = maximum = 0
    alpha_equal = True
    for start in range(0, expected.shape[0], 64):
        left, right = expected[start:start + 64], actual[start:start + 64]
        difference = np.abs(left[..., :3].astype(np.int16) - right[..., :3].astype(np.int16))
        maximum = max(maximum, int(difference.max()))
        changed += int(np.count_nonzero(difference))
        total += int(difference.sum(dtype=np.int64))
        alpha_equal = alpha_equal and np.array_equal(left[..., 3], right[..., 3])
    count = expected.shape[0] * expected.shape[1] * 3
    return {"max_rgb_byte_error": maximum, "changed_rgb_channels": changed,
            "changed_rgb_fraction": changed / count, "mean_rgb_byte_error": total / count,
            "alpha_equal": bool(alpha_equal), "byte_exact": not changed and bool(alpha_equal)}


def _input(fixture: Path, case: str) -> np.ndarray:
    if case == "preview":
        return gradient(800, 800)
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    path = fixture / f"{case}.jpg"
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if (manifest.get("fixture_version") != 1
            or actual_hash != manifest["image_sha256"][path.name]):
        raise ValueError("owned baseline fixture and unchanged image hash required")
    from Imervue.gpu_image_view.images.image_loader import decode_image_file
    return decode_image_file(str(path))


def _color_cases(renderer) -> dict:
    from Imervue.image.color_profile import to_srgb
    from gpu_develop.params import requires_cpu_reference
    from tests._icc_profiles import DISPLAY_P3
    array = np.random.default_rng(77).integers(0, 256, (128, 256, 4), dtype=np.uint8)
    source = Image.fromarray(array)
    source.info["icc_profile"] = DISPLAY_P3
    normalized = np.array(to_srgb(source))
    cases = {"identity": Recipe(), "table_exposure": Recipe(exposure=.4), **recipes()}
    cases["threshold_after_mixed"] = Recipe(
        shadows=.4, vibrance=.6, saturation=.2,
        extra={"threshold": {"enabled": True, "level": 128}},
    )
    return {name: {**pixel_difference(recipe.apply(normalized),
                                    renderer.render(normalized, recipe)),
                   "render_mode": ("identity" if recipe.is_identity() else "cpu_reference"
                                   if requires_cpu_reference(recipe) else "gpu")}
            for name, recipe in cases.items()}


def _measure_pair(array, recipe, renderer, repeats) -> dict:
    expected = recipe.apply(array)
    outputs = []

    def cpu():
        outputs[:] = [recipe.apply(array)]

    def gpu():
        outputs[:] = [renderer.render(array, recipe)]

    cpu_metrics = measure(cpu, repeats=repeats)
    outputs.clear()
    cold_gpu = measure(gpu, repeats=1)
    warm_gpu = measure(gpu, repeats=repeats)
    difference = pixel_difference(expected, outputs[-1])
    return {"cpu": cpu_metrics, "first_gpu_render": cold_gpu, "warm_gpu": warm_gpu,
            "difference": difference,
            "median_speedup": cpu_metrics["median_ms"] / warm_gpu["median_ms"]}


def run_case(fixture: Path, case: str, repeats: int) -> dict:
    from gpu_develop.renderer import GpuDevelopRenderer
    array = _input(fixture, case)
    original_hash = hashlib.sha256(array).hexdigest()
    owners = []
    opened = measure(lambda: owners.append(GpuDevelopRenderer()), repeats=1)
    renderer = owners[0]
    try:
        color = _color_cases(renderer)
        results = {name: _measure_pair(array, recipe, renderer, repeats)
                   for name, recipe in recipes().items()}
        if hashlib.sha256(array).hexdigest() != original_hash:
            raise RuntimeError("renderer modified its input")
        return {"adapter": renderer.label, "shape": list(array.shape), "open_device": opened,
                "color_cases": color, "recipes": results,
                "boundary": ("owned uint8 sRGB RGBA; full host upload/readback and CPU remainder; "
                             "no GUI, decoder timing, QImage/display or event-loop latency; "
                             "RSS includes retained CPU reference; dedicated VRAM not measured")}
    finally:
        renderer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", choices=CASES, nargs="+")
    parser.add_argument("--child", choices=CASES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.child:
        write_json(args.output, run_case(args.fixtures, args.child, args.repeats))
        return
    from scripts.performance_benchmark import environment
    report = {"environment": environment(), "wgpu_version": importlib.metadata.version("wgpu"),
              "cases": {}, "failures": {}}
    files = ["Imervue/image/recipe.py", "Imervue/image/develop_preview.py",
             "Imervue/image/develop_backends.py", "scripts/gpu_develop_benchmark.py"]
    files += [str(path.relative_to(ROOT)).replace("\\", "/")
              for path in (ROOT / "plugins/gpu_develop").glob("*.py")]
    report["source_sha256_lf"] = {
        name: hashlib.sha256((ROOT / name).read_text(encoding="utf-8").encode()).hexdigest()
        for name in files}
    for case in args.only or CASES:
        result = args.output.with_name(args.output.stem + "." + case + ".json")
        try:
            subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__)),
                            "--fixtures", str(args.fixtures), "--output", str(result),
                            "--repeats", str(args.repeats), "--child", case],
                           check=True, timeout=900)
            report["cases"][case] = json.loads(result.read_text(encoding="utf-8"))
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            report["failures"][case] = str(exc)
        write_json(args.output, report)
    if report["failures"]:
        raise SystemExit("GPU assessment failed; see report")


if __name__ == "__main__":
    main()
