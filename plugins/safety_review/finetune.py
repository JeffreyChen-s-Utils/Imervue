"""Fine-tune the NSFW YOLO detector on a labelled dataset.

Closes the loop with the manual editor: label images there ("Add to dataset"),
then run this on the resulting folder to fine-tune a model, and point the
plugin at the output ``.pt`` via *Detection Model & Classes*.

Usage:

    py plugins/safety_review/finetune.py <dataset_dir> [options]

    --base erax|<path.pt>   starting weights (default: erax medium)
    --epochs N              training epochs (default: 100)
    --imgsz N              image size (default: 640)
    --device cpu|0|0,1     training device (default: ultralytics auto)
    --out PATH             where to copy the best weights (default:
                           <dataset_dir>/finetuned.pt)

Needs ``ultralytics`` (and a GPU for any real run). The config building is
pure and unit-tested; the training itself is not (it needs weights + hardware).
"""
from __future__ import annotations

import argparse
import os
import shutil

# Duplicated (like _runner.py) so this stays runnable as a standalone script
# without the plugin package on sys.path.
_ERAX_REPO = "erax-ai/EraX-Anti-NSFW-V1.1"
_ERAX_MODEL = "erax-anti-nsfw-yolo11m-v1.1.pt"
_ERAX_REVISION = "90878ab981060833413ae1a24df72f5e1fff66bc"

DEFAULT_EPOCHS = 100
DEFAULT_IMGSZ = 640


def data_yaml_path(dataset_dir: str) -> str:
    """Path to the dataset's ``data.yaml``; raises if the dataset is missing it."""
    path = os.path.join(dataset_dir, "data.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"No data.yaml in {dataset_dir!r} — build a dataset with the "
            f"manual editor's 'Add to dataset' first.")
    return path


def train_config(dataset_dir: str, epochs: int = DEFAULT_EPOCHS,
                 imgsz: int = DEFAULT_IMGSZ, device=None) -> dict:
    """ultralytics ``model.train(**kwargs)`` arguments for this run."""
    config = {
        "data": data_yaml_path(dataset_dir),
        "epochs": int(epochs),
        "imgsz": int(imgsz),
        "project": os.path.join(dataset_dir, "runs"),
        "name": "finetune",
        "exist_ok": True,
    }
    if device is not None:
        config["device"] = device
    return config


def resolve_base_weights(base: str) -> str:
    """``"erax"`` → download the EraX medium weights; otherwise a ``.pt`` path."""
    if base == "erax":
        from huggingface_hub import hf_hub_download
        return hf_hub_download(repo_id=_ERAX_REPO, filename=_ERAX_MODEL,
                               revision=_ERAX_REVISION)
    return base


def default_output(dataset_dir: str) -> str:
    return os.path.join(dataset_dir, "finetuned.pt")


def run(dataset_dir: str, base: str = "erax", epochs: int = DEFAULT_EPOCHS,
        imgsz: int = DEFAULT_IMGSZ, device=None, out: str | None = None) -> str:
    """Fine-tune and copy the best weights to *out*; returns the output path."""
    from ultralytics import YOLO
    model = YOLO(resolve_base_weights(base))
    results = model.train(**train_config(dataset_dir, epochs, imgsz, device))
    best = os.path.join(str(getattr(results, "save_dir", "")), "weights", "best.pt")
    out = out or default_output(dataset_dir)
    if os.path.isfile(best):
        shutil.copy2(best, out)
    return out


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Fine-tune the NSFW detector.")
    parser.add_argument("dataset_dir", help="dataset folder containing data.yaml")
    parser.add_argument("--base", default="erax")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    parser.add_argument("--device", default=None)
    parser.add_argument("--out", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)
    out = run(args.dataset_dir, base=args.base, epochs=args.epochs,
              imgsz=args.imgsz, device=args.device, out=args.out)
    print(f"Fine-tuned weights written to: {out}")  # noqa: T201 — CLI output


if __name__ == "__main__":
    main()
