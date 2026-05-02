"""Save / load multi-page :class:`PaintProject` bundles.

The project file format is a ZIP archive with a fixed layout:

* ``manifest.json``  — top-level project metadata (format version,
  project name, author, active-page index, ordered list of page
  names).
* ``page_<i>.imervue`` — one full document_io NPZ per page, stored
  as raw bytes inside the archive.

ZIP rather than the NPZ format the single-document save uses
because each page already IS an NPZ; nesting NPZ-in-NPZ via
np.savez doesn't compose. ZIP gives us a single user-facing file
that bundles N self-describing pages with no per-page parsing
beyond the existing document_io machinery.

``load_project`` always passes ``allow_pickle=False`` through to
the inner page loaders — a malicious file cannot execute pickled
code via either the ZIP or the NPZ layer.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from Imervue.paint.document_io import (
    load_document_from_buffer,
    save_document_to_buffer,
)
from Imervue.paint.paint_project import PaintProject, ProjectPage

PROJECT_FORMAT_VERSION = 1
PROJECT_FILE_EXTENSION = ".imervue-proj"
_MANIFEST_NAME = "manifest.json"


def save_project(project: PaintProject, path: str | Path) -> None:
    """Write ``project`` to a ``.imervue-proj`` ZIP bundle."""
    if not project.pages:
        raise ValueError("cannot save an empty PaintProject — no pages")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format_version": PROJECT_FORMAT_VERSION,
        "name": project.name,
        "author": project.author,
        "active_page_index": int(project.active_page_index),
        "pages": [{"name": page.name} for page in project.pages],
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_MANIFEST_NAME, json.dumps(manifest))
        for i, page in enumerate(project.pages):
            blob = save_document_to_buffer(page.document)
            zf.writestr(f"page_{i}.imervue", blob)


def load_project(path: str | Path) -> PaintProject:
    """Load a ``.imervue-proj`` bundle and rebuild a :class:`PaintProject`."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"project file {target!s} does not exist")
    with zipfile.ZipFile(target, "r") as zf:
        try:
            manifest_blob = zf.read(_MANIFEST_NAME)
        except KeyError as exc:
            raise ValueError(
                f"project file {target!s} missing {_MANIFEST_NAME!r}",
            ) from exc
        manifest = _parse_manifest(manifest_blob)
        pages_meta = manifest["pages"]
        pages: list[ProjectPage] = []
        for i, page_meta in enumerate(pages_meta):
            try:
                blob = zf.read(f"page_{i}.imervue")
            except KeyError as exc:
                raise ValueError(
                    f"project file is missing page_{i}.imervue",
                ) from exc
            doc = load_document_from_buffer(blob)
            page_name = str(page_meta.get("name", f"Page {i + 1}"))
            pages.append(ProjectPage(document=doc, name=page_name))
    project = PaintProject(
        name=str(manifest.get("name", "Untitled Project")),
        author=str(manifest.get("author", "")),
        pages=pages,
        active_page_index=int(manifest.get("active_page_index", 0)),
    )
    return project


def _parse_manifest(blob: bytes) -> dict:
    """Validate the project manifest payload."""
    try:
        manifest = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"corrupt project manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(
            f"manifest must be a dict, got {type(manifest).__name__}",
        )
    if manifest.get("format_version") != PROJECT_FORMAT_VERSION:
        raise ValueError(
            f"unsupported project format version "
            f"{manifest.get('format_version')!r}; "
            f"this build understands {PROJECT_FORMAT_VERSION}",
        )
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("project manifest has no pages")
    return manifest
