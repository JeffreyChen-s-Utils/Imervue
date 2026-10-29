"""Additive catalog tables, indexes and schema version."""
from __future__ import annotations

import sqlite3


_SCHEMA_VERSION = 2


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS images (
    path TEXT PRIMARY KEY,
    parent TEXT,
    name TEXT,
    ext TEXT,
    size INTEGER,
    mtime REAL,
    width INTEGER,
    height INTEGER,
    phash INTEGER,
    taken_at REAL,
    indexed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_images_parent ON images(parent);
CREATE INDEX IF NOT EXISTS idx_images_ext ON images(ext);
CREATE INDEX IF NOT EXISTS idx_images_taken_at ON images(taken_at);
-- Complete the default ordering: equal/unknown capture times must not force
-- a temporary sort of the entire catalog before a small LIMIT can return.
CREATE INDEX IF NOT EXISTS idx_images_sort ON images(taken_at DESC, mtime DESC);
-- Composite indexes for the facet queries in ``search_paths``: the
-- common shape is "filter by parent / ext + sort by taken_at desc".
-- Without the composites SQLite filters via the single-column index
-- then sorts a full result set into a temp table. With the composite,
-- the index iterator itself is already in taken_at order.
CREATE INDEX IF NOT EXISTS idx_images_parent_taken_at
    ON images(parent, taken_at);
CREATE INDEX IF NOT EXISTS idx_images_ext_taken_at
    ON images(ext, taken_at);
-- ``WHERE phash IS NOT NULL`` is the entry point for similarity /
-- dedupe scans. A partial index keeps the structure tiny (only rows
-- with a computed phash) and turns the scan into a direct lookup.
CREATE INDEX IF NOT EXISTS idx_images_phash_notnull
    ON images(phash) WHERE phash IS NOT NULL;

CREATE TABLE IF NOT EXISTS notes (
    path TEXT PRIMARY KEY,
    note TEXT,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS tag_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    name TEXT NOT NULL,
    UNIQUE(parent_id, name)
);

CREATE TABLE IF NOT EXISTS image_tags (
    path TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (path, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id);

CREATE TABLE IF NOT EXISTS culling (
    path TEXT PRIMARY KEY,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS smart_albums (
    name TEXT PRIMARY KEY,
    rules_json TEXT NOT NULL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS library_roots (
    path TEXT PRIMARY KEY,
    added_at REAL
);
"""


def _set_schema_version(c: sqlite3.Connection, version: int) -> None:
    c.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(version),),
    )
