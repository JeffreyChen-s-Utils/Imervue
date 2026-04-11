"""
Standalone object splitter runner — executed as a subprocess in frozen env.

Usage:
    python _runner.py <site_packages> <input> <output_dir> <model> <min_area> <padding> <models_dir>

Communication via stdout:
    STEP:<current>:<total>:<message>
    OK:<count>
    ERROR:<message>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _run(input_path: str, output_dir: str, model_name: str,
         min_area: int, padding: int, models_dir: str) -> None:
    os.environ["U2NET_HOME"] = models_dir
    Path(models_dir).mkdir(parents=True, exist_ok=True)

    # Phase 1: load rembg
    print("STEP:0:4:Loading rembg...", flush=True)
    from rembg import remove, new_session
    from PIL import Image
    import numpy as np

    # Phase 2: load model
    print(f"STEP:1:4:Loading model: {model_name}...", flush=True)
    session = new_session(model_name)

    # Phase 3: remove background
    print("STEP:2:4:Removing background...", flush=True)
    input_img = Image.open(input_path).convert("RGBA")
    output_img = remove(input_img, session=session)

    # Phase 4: find objects
    print("STEP:3:4:Finding objects...", flush=True)
    alpha = np.array(output_img)[:, :, 3]
    labels, num = _connected_components(alpha > 128)

    # Count valid objects first
    valid = []
    for label_id in range(1, num + 1):
        mask = labels == label_id
        if int(mask.sum()) >= min_area:
            valid.append(label_id)

    total_objects = len(valid)
    print(f"STEP:4:4:Found {total_objects} object(s) (filtered from {num} regions)", flush=True)

    if total_objects == 0:
        print("OK:0", flush=True)
        return

    # Phase 5+: save each object
    stem = Path(input_path).stem
    arr = np.array(output_img)
    h, w = alpha.shape

    for i, label_id in enumerate(valid):
        mask = labels == label_id

        ys, xs = np.where(mask)
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        x0, x1 = int(xs.min()), int(xs.max()) + 1

        y0 = max(0, y0 - padding)
        x0 = max(0, x0 - padding)
        y1 = min(h, y1 + padding)
        x1 = min(w, x1 + padding)

        cropped = arr[y0:y1, x0:x1].copy()
        crop_mask = mask[y0:y1, x0:x1]
        cropped[~crop_mask, 3] = 0

        obj_img = Image.fromarray(cropped, "RGBA")

        obj_num = i + 1
        out_name = f"{stem}_obj{obj_num}.png"
        out_path = Path(output_dir) / out_name
        counter = 1
        while out_path.exists():
            out_name = f"{stem}_obj{obj_num}_{counter}.png"
            out_path = Path(output_dir) / out_name
            counter += 1

        obj_img.save(str(out_path))
        print(f"STEP:{i + 1}:{total_objects}:Saved: {out_name}", flush=True)

    print(f"OK:{total_objects}", flush=True)


def _connected_components(binary: "np.ndarray"):
    """Simple BFS-based connected component labeling (no scipy needed)."""
    import numpy as np
    from collections import deque

    h, w = binary.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current_label = 0

    for y in range(h):
        for x in range(w):
            if binary[y, x] and labels[y, x] == 0:
                current_label += 1
                queue = deque()
                queue.append((y, x))
                labels[y, x] = current_label
                while queue:
                    cy, cx = queue.popleft()
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = current_label
                            queue.append((ny, nx))

    return labels, current_label


if __name__ == "__main__":
    try:
        site_packages = sys.argv[1]
        if site_packages and os.path.isdir(site_packages):
            sys.path.insert(0, site_packages)

        _run(
            input_path=sys.argv[2],
            output_dir=sys.argv[3],
            model_name=sys.argv[4],
            min_area=int(sys.argv[5]),
            padding=int(sys.argv[6]),
            models_dir=sys.argv[7],
        )
    except Exception as exc:
        print(f"ERROR:{exc}", flush=True)
        sys.exit(1)
