"""Shared conflict reservations and cancellable atomic output commits for every entry point."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

CONFLICTS = ("rename", "skip", "replace")
_lock = RLock()
_active: set[str] = set()


@dataclass(frozen=True)
class OutputPolicy:
    """Explicit caller defaults share one conflict engine; source replacement needs consent."""

    conflict: str = "rename"
    allow_source: bool = False

    def __post_init__(self):
        if self.conflict not in CONFLICTS:
            raise ValueError(f"invalid conflict policy: {self.conflict}")


@dataclass(frozen=True)
class OutputResult:
    """A completed commit, an intentional skip, or cancelled work with no committed output."""

    status: str
    path: str = ""


_DEFAULT_POLICY = OutputPolicy()


def path_key(path: str | Path) -> str:
    """Resolve aliases and Windows case before comparing sources or active reservations."""
    return os.path.normcase(os.path.realpath(path))


def free_output_path(target: str | Path) -> Path:
    """Choose a free numbered sibling against disk and current process reservations."""
    target = Path(target)
    with _lock:
        candidate, counter = target, 1
        while candidate.exists() or path_key(candidate) in _active:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            counter += 1
        return candidate


def _reserve(source: str | Path, target: Path, policy: OutputPolicy) -> tuple[Path, str] | None:
    with _lock:
        if policy.conflict == "rename":
            target = free_output_path(target)
        key = path_key(target)
        if policy.conflict == "skip" and (target.exists() or key in _active):
            return None
        if key == path_key(source) and not policy.allow_source:
            raise ValueError("Replacing the source requires explicit overwrite consent")
        if key in _active:
            raise FileExistsError(f"Output is currently being written: {target}")
        _active.add(key)
        return target, key


def write_output(
    source: str | Path, target: str | Path, write: Callable[[Path], None],
    policy: OutputPolicy = _DEFAULT_POLICY, *, cancelled: Callable[[], bool] | None = None,
) -> OutputResult:
    """Write a unique same-format sibling and commit once; cancellation keeps existing files whole.

    Reservations coordinate writers inside this process, including separate windows. Other
    processes are outside the reservation contract. Completed writes remain valid when later
    cancellation occurs. Errors propagate after releasing the reservation and temporary file.
    """
    if cancelled is not None and cancelled():
        return OutputResult("cancelled")
    reservation = _reserve(source, Path(target), policy)
    if reservation is None:
        return OutputResult("skipped", str(target))
    selected, reservation_key = reservation
    temporary = None
    try:
        selected.parent.mkdir(parents=True, exist_ok=True)
        # Keep the real suffix: older operations infer their encoder from the path.
        with tempfile.NamedTemporaryFile(prefix=".imervue-output-", suffix=selected.suffix,
                                         dir=selected.parent, delete=False) as stream:
            temporary = Path(stream.name)
        if cancelled is not None and cancelled():
            return OutputResult("cancelled")
        write(temporary)
        if cancelled is not None and cancelled():
            return OutputResult("cancelled")
        if temporary.stat().st_size == 0:
            raise ValueError("Output writer produced an empty file")
        if policy.conflict != "replace" and selected.exists():
            raise FileExistsError(f"Output appeared during writing: {selected}")
        os.replace(temporary, selected)
        return OutputResult("succeeded", str(selected))
    finally:
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        finally:
            with _lock:
                _active.discard(reservation_key)
