"""Batch destination planning, transactional work and result publication."""
from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from threading import Event, Lock
from Imervue.cli_output import plan_targets, process_output, result_message, write_report
from Imervue.cli_paths import _checked_path, _validated_out_dir, output_path
from Imervue.cli_workers import _resolve_workers, _run_outputs
from Imervue.image.output_policy import path_key
from Imervue.system.job_state import JobItem


def _process_one(src: Path, out_dir, operation, suffix: str, ext_fn, args) -> tuple[str, str]:
    """Process one file; return ``(status, message)`` — pure of shared state."""
    target = output_path(src, str(out_dir) if out_dir else None, suffix, ext_fn(args))
    return result_message(process_output(src, target, operation, args, lambda: False))


def _write(args, paths: Sequence[Path], operation, suffix: str, ext_fn) -> int:
    try:
        out_dir = _validated_out_dir(args.out)
        targets = plan_targets([output_path(src, out_dir, suffix, ext_fn(args)) for src in paths])
        report = _checked_path(args.result_report) if getattr(args, "result_report", None) else None
        if report and path_key(report) in {path_key(p) for p in [*paths, *targets]}:
            raise ValueError("Result report must differ from every source and output")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    cancelled, lock, completed = Event(), Lock(), {}

    def work(pair):
        src, target = pair
        result = process_output(src, target, operation, args, cancelled.is_set)
        with lock:
            completed[str(src)] = result
        return result

    interrupted = _run_outputs(list(zip(paths, targets, strict=True)), work,
                               _resolve_workers(getattr(args, "jobs", 1), len(paths)), cancelled)
    results = [completed.get(str(src), JobItem(str(src), "cancelled")) for src in paths]
    tally = {"ok": 0, "skip": 0, "error": 0, "dry": 0, "cancelled": 0}
    for item in results:
        status, message = result_message(item)
        tally[status] += 1
        print(message, file=sys.stderr if status == "error" else sys.stdout)
    print(f"{tally['ok'] + tally['dry']} processed, {tally['skip']} skipped, "
          f"{tally['error']} errors", file=sys.stderr)
    if report:
        try:
            if path_key(report) in {path_key(r.output) for r in results if r.output}:
                raise OSError("Result report conflicts with an actual output")
            write_report(report, results)
        except OSError as exc:
            print(f"error: result report: {exc}", file=sys.stderr)
            return 1
    if interrupted:
        return 130
    return 1 if tally["error"] else 0
