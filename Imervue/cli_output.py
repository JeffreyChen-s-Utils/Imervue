"""Headless output transactions, deterministic cohorts and machine-readable results."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from PIL import Image

from Imervue.image.export_metadata import export_save_options
from Imervue.image.output_policy import OutputPolicy, path_key, write_output
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.save_formats import save_image
from Imervue.system.atomic_write import write_text_atomically
from Imervue.system.job_state import JobItem


def plan_targets(targets: list[Path]) -> list[Path]:
    """Give repeated destinations distinct names in input order before threads start."""
    used: set[str] = set()
    planned = []
    for target in targets:
        candidate, number = target, 0
        while path_key(candidate) in used:
            number += 1
            candidate = target.with_name(f"{target.stem}_{number}{target.suffix}")
        used.add(path_key(candidate))
        planned.append(candidate)
    return planned


def process_output(src: Path, target: Path, operation, args, cancelled) -> JobItem:
    """Publish an image only after its complete encoder transaction and cancellation check."""
    if cancelled():
        return JobItem(str(src), "cancelled")
    if args.dry_run:
        return JobItem(str(src), "dry", str(target))
    conflict = getattr(args, "output_conflict", None) or ("replace" if args.overwrite else "skip")
    policy = OutputPolicy(conflict, allow_source=conflict == "replace")

    def write(stage: Path) -> None:
        operation(src, stage, args)
        metadata = getattr(args, "export_metadata", None)
        if metadata is not None:
            # Explicit metadata selection can re-encode lossy formats; default leaves the
            # operation's encoder and quality untouched. Strip always removes metadata.
            metadata = "none" if args.command == "strip" else metadata
            with Image.open(stage) as encoded:
                encoded.load()
                image, fmt = encoded.copy(), encoded.format
            image.info.clear()
            save_image(image, str(stage), "WebP" if fmt == "WEBP" else fmt,
                       getattr(args, "quality", None),
                       export_save_options(src, metadata))

    try:
        result = write_output(src, target, write, policy, cancelled=cancelled)
    except IMAGE_READ_ERRORS as exc:
        return JobItem(str(src), "failed", error=str(exc) or type(exc).__name__)
    return JobItem(str(src), result.status, result.path)


def result_message(item: JobItem) -> tuple[str, str]:
    """Keep the legacy CLI messages and tally names for existing callers."""
    if item.status == "failed":
        return "error", f"error: {item.source}: {item.error}"
    if item.status == "skipped":
        return "skip", f"skip (exists): {item.output}"
    if item.status == "dry":
        return "dry", f"would write {item.output}"
    if item.status == "cancelled":
        return "cancelled", f"cancelled: {item.source}"
    return "ok", f"{item.source} -> {item.output}"


def write_report(path: Path, results: list[JobItem]) -> None:
    """Atomically write all results with file links only for committed outputs."""
    rows = []
    for item in results:
        row = asdict(item)
        row["output_uri"] = (
            Path(item.output).resolve().as_uri()
            if item.status == "succeeded" and item.output else ""
        )
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomically(path, json.dumps({"items": rows}, ensure_ascii=False, indent=2))
