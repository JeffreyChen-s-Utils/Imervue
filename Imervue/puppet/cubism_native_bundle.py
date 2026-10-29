"""Cubism bundle assembly for the native Cubism conversion.

Gathers motions, expressions, physics, display names and hit areas from
the ``.model3.json`` file references and folds them into the document
through :func:`puppet.cubism_import.apply_bundle`. Missing or broken
sidecar files are logged and skipped. Split out of
:mod:`puppet.cubism_native_convert`, which re-exports every name.
"""
from __future__ import annotations

import logging
from pathlib import Path

from Imervue.puppet.cubism_import import (
    CubismBundle,
    apply_bundle,
    load_cdi3,
    load_exp3,
    load_physics3,
)
from Imervue.puppet.cubism_native_motions import (
    _collect_manifest_motions,
    _collect_orphan_motions,
)
from Imervue.puppet.document import PuppetDocument

# Same logger as the converter, so its records keep their source name.
logger = logging.getLogger("Imervue.plugin.puppet.cubism_native_convert")


def _load_expression_entry(
    bundle: CubismBundle, entry: object, base_dir: Path,
) -> None:
    """Resolve and load one entry from the manifest's ``Expressions``
    list. Tries both ``base_dir / file_ref`` and the conventional
    ``base_dir / "exp" / file_ref`` location; logs and skips when
    neither exists. Caught exceptions cover the heterogeneous failure
    surface of :func:`load_exp3` against real-world Cubism rigs."""
    if not isinstance(entry, dict):
        return
    file_ref = entry.get("File")
    if not file_ref:
        return
    name = entry.get("Name") or Path(file_ref).stem
    for path in (base_dir / file_ref, base_dir / "exp" / file_ref):
        if not path.is_file():
            continue
        try:
            bundle.expressions.append(load_exp3(path, name=str(name)))
        except Exception as exc:   # noqa: BLE001 - load_exp3 backends vary
            logger.info("expression %s failed: %s", path, exc)
        return
    logger.info("expression %s missing — skipping", file_ref)


def _collect_expressions(
    bundle: CubismBundle, file_refs: dict, base_dir: Path,
) -> None:
    """Broken paths in real-world bundles are common; also check
    under ``base_dir / "exp"``."""
    for entry in file_refs.get("Expressions") or []:
        _load_expression_entry(bundle, entry, base_dir)


def _collect_single_sidecar(
    file_refs: dict, base_dir: Path, key: str, loader, sink, label: str,
) -> None:
    """Apply the same pattern as physics / display info: look up a
    single string filename, verify it exists, hand the path to the
    loader, swallow any backend error as info-log."""
    ref = file_refs.get(key)
    if not isinstance(ref, str) or not ref:
        return
    path = base_dir / ref
    if not path.is_file():
        return
    try:
        sink(loader(path))
    except Exception as exc:   # noqa: BLE001 - third-party loaders vary
        logger.info("%s %s failed: %s", label, path, exc)


def _collect_hit_areas(bundle: CubismBundle, manifest: dict) -> None:
    from Imervue.puppet.document import HitArea
    for entry in manifest.get("HitAreas") or []:
        if not isinstance(entry, dict):
            continue
        drawable_id = entry.get("Id")
        if not isinstance(drawable_id, str) or not drawable_id:
            continue
        name = entry.get("Name") or drawable_id
        bundle.hit_areas.append(
            HitArea(id=str(name), drawables=[str(drawable_id)]),
        )


def _attach_cubism_bundle(
    document: PuppetDocument, manifest: dict, base_dir: Path,
) -> None:
    """Pull motions / expressions / physics / cdi out of the Cubism
    file references and fold them into the document via the existing
    :mod:`puppet.cubism_import` machinery. Missing files are logged +
    skipped rather than fatal — some bundles ship broken paths for
    expression files."""
    from Imervue.puppet.cubism_import import CubismBundle

    file_refs = manifest.get("FileReferences") or {}
    bundle = CubismBundle()

    referenced_paths = _collect_manifest_motions(bundle, file_refs, base_dir)
    _collect_orphan_motions(bundle, base_dir, referenced_paths)
    _collect_expressions(bundle, file_refs, base_dir)
    _collect_single_sidecar(
        file_refs, base_dir, "Physics",
        load_physics3, bundle.physics_rigs.extend, "physics",
    )
    _collect_single_sidecar(
        file_refs, base_dir, "DisplayInfo",
        load_cdi3, bundle.display_names.update, "cdi",
    )
    _collect_hit_areas(bundle, manifest)
    apply_bundle(document, bundle)
