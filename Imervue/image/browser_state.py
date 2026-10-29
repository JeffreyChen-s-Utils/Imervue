"""Shared image-browser state helpers.

Small, UI-agnostic utilities for folder filtering, missing-file repair,
metadata indexing, and incremental cache migration.  Keeping this logic out
of the widgets makes folder refreshes testable and keeps large-directory
paths from drifting between grid/list/deep-zoom modes.

This module is the public import location; the helpers live in the
``browser_state_*`` siblings by responsibility (index, filter, query
predicates, missing-file repair, rename migration).
"""
from __future__ import annotations

from Imervue.image.browser_state_filter import (
    ImageFilterSpec,
    filter_paths,
    match_filter,
    refilter_keeping_current,
)
from Imervue.image.browser_state_index import ImageMeta, ImageMetadataIndex
from Imervue.image.browser_state_renames import (
    detect_renamed_paths,
    migrate_view_path_state,
)
from Imervue.image.browser_state_repair import (
    auto_match_same_name,
    is_missing_file_error,
    is_transient_load_error,
    missing_paths,
    relocate_root,
    remove_missing,
)

__all__ = [
    "ImageFilterSpec",
    "ImageMeta",
    "ImageMetadataIndex",
    "auto_match_same_name",
    "detect_renamed_paths",
    "filter_paths",
    "is_missing_file_error",
    "is_transient_load_error",
    "match_filter",
    "migrate_view_path_state",
    "missing_paths",
    "refilter_keeping_current",
    "relocate_root",
    "remove_missing",
]
