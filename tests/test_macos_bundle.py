"""Tests for macOS bundle Info.plist document-type helpers."""
from __future__ import annotations

from Imervue.system.file_association import ASSOC_EXTENSIONS
from Imervue.system.macos_bundle import (
    BUNDLE_IDENTIFIER,
    content_types_for,
    image_document_types,
    info_plist,
)


def test_content_types_dedupes_jpeg():
    assert content_types_for([".jpg", ".jpeg", ".png"]) == ["public.jpeg", "public.png"]


def test_content_types_ignores_unknown():
    assert content_types_for([".xyz"]) == []


def test_raw_formats_map_to_camera_raw():
    assert content_types_for([".cr2", ".nef"]) == ["public.camera-raw-image"]


def test_image_document_types_structure():
    docs = image_document_types([".png"])
    assert len(docs) == 1
    assert docs[0]["CFBundleTypeRole"] == "Viewer"
    assert docs[0]["LSItemContentTypes"] == ["public.png"]


def test_image_document_types_empty_for_no_known_exts():
    assert image_document_types([".xyz"]) == []


def test_info_plist_for_real_extensions():
    plist = info_plist(ASSOC_EXTENSIONS, version="1.2.3")
    assert plist["CFBundleShortVersionString"] == "1.2.3"
    assert plist["CFBundleIdentifier"] == BUNDLE_IDENTIFIER
    assert plist["NSHighResolutionCapable"] is True
    # Every supported extension that has a UTI is declared.
    declared = plist["CFBundleDocumentTypes"][0]["LSItemContentTypes"]
    assert "public.png" in declared
    assert "public.jpeg" in declared
    assert "public.camera-raw-image" in declared
