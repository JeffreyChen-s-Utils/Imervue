"""
Standalone rembg runner — executed as a subprocess by the AI Background
Remover plugin when running inside a PyInstaller frozen environment.

Usage:
    python _rembg_runner.py <site_packages> single <input> <output> <model> <alpha_matting> <models_dir>
    python _rembg_runner.py <site_packages> batch  <input_list_file> <output_dir> <model> <alpha_matting> <models_dir>

Communication is via stdout lines:
    PROGRESS:<message>
    BATCH_PROGRESS:<current>:<total>:<name>
    OK:<result>
    BATCH_OK:<success>:<failed>
    ERROR:<message>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _run_single(input_path: str, output_path: str, model_name: str,
                alpha_matting: bool, models_dir: str) -> None:
    os.environ["U2NET_HOME"] = models_dir
    Path(models_dir).mkdir(parents=True, exist_ok=True)

    print("PROGRESS:Loading rembg...", flush=True)
    from rembg import remove, new_session
    from PIL import Image

    print(f"PROGRESS:Loading model: {model_name}...", flush=True)
    session = new_session(model_name)

    print("PROGRESS:Processing image...", flush=True)
    input_img = Image.open(input_path)

    output_img = remove(
        input_img,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10,
    )

    print("PROGRESS:Saving result...", flush=True)
    output_img.save(output_path)
    print(f"OK:{output_path}", flush=True)


def _run_batch(input_list_file: str, output_dir: str, model_name: str,
               alpha_matting: bool, models_dir: str) -> None:
    os.environ["U2NET_HOME"] = models_dir
    Path(models_dir).mkdir(parents=True, exist_ok=True)

    with open(input_list_file, "r", encoding="utf-8") as f:
        paths = json.load(f)

    from rembg import remove, new_session
    from PIL import Image

    session = new_session(model_name)
    success = 0
    failed = 0
    total = len(paths)

    for i, src in enumerate(paths):
        try:
            print(f"BATCH_PROGRESS:{i}:{total}:{Path(src).name}", flush=True)
            input_img = Image.open(src)
            output_img = remove(
                input_img,
                session=session,
                alpha_matting=alpha_matting,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10,
            )
            out_name = Path(src).stem + "_nobg.png"
            out_path = Path(output_dir) / out_name
            counter = 1
            while out_path.exists():
                out_name = f"{Path(src).stem}_nobg_{counter}.png"
                out_path = Path(output_dir) / out_name
                counter += 1
            output_img.save(str(out_path))
            success += 1
        except Exception as exc:
            print(f"BATCH_PROGRESS:{i}:{total}:Error: {Path(src).name}: {exc}", flush=True)
            failed += 1

    print(f"BATCH_OK:{success}:{failed}", flush=True)


if __name__ == "__main__":
    try:
        # First arg: site-packages path to prepend to sys.path
        site_packages = sys.argv[1]
        if site_packages and os.path.isdir(site_packages):
            sys.path.insert(0, site_packages)

        mode = sys.argv[2]
        if mode == "single":
            _run_single(
                input_path=sys.argv[3],
                output_path=sys.argv[4],
                model_name=sys.argv[5],
                alpha_matting=sys.argv[6].lower() == "true",
                models_dir=sys.argv[7],
            )
        elif mode == "batch":
            _run_batch(
                input_list_file=sys.argv[3],
                output_dir=sys.argv[4],
                model_name=sys.argv[5],
                alpha_matting=sys.argv[6].lower() == "true",
                models_dir=sys.argv[7],
            )
        else:
            print(f"ERROR:Unknown mode: {mode}", flush=True)
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR:{exc}", flush=True)
        sys.exit(1)
