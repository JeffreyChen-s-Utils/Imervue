# Puppet archive refactor independent review

The review goal was to preserve the public puppet archive behavior while reducing file complexity through cohesive format boundaries.

No blocking correctness, security, or API findings were identified. This is a review of the working diff in D:/Codes/Imervue-puppet-quality, including all fourteen untracked runtime modules and tests/test_puppet_archive_contracts.py. No production or test files were edited.

The ZIP transport remains in document_io and archive_container. The write sequence remains mimetype, manifest, textures, motions, expressions, then optional physics. The mimetype member remains first and uncompressed. The aggregate declared uncompressed size check still runs before member reads, and document_io still supplies its patchable ceiling to both public load paths. No extraction or filesystem interpretation of member names was introduced.

The manifest collection table preserves required and optional collection order, field-specific list validation, duplicates, optional empty-value handling, and JSON omission rules. Drawable curves and vertex deformation remain separate domain concepts with their own validation. Motion, expression, physics, parameter, and rig codecs keep their corresponding parse and encode operations together. The manifest decode/encode/table split adds small modules, but each has an identifiable responsibility and there is no anonymous numbered or threshold-sized partition.

PuppetFormatError is one shared class, re-exported from document_io. Existing imports therefore catch errors raised by the moved codecs. Its defining __module__ changes to Imervue.puppet.format_values. This is observable introspection metadata, but no documented or repository consumer requiring the old metadata was found. The intentional public functions retain their signatures. Previously incidental imported symbols and private helpers are no longer all available through document_io; the explicit __all__ identifies the supported facade.

The changed atomic-save test remains meaningful. It patches archive_container._motion_json_bytes, which is the function used by the new writer after earlier members have been written. It still expects the injected OSError and asserts the previous destination bytes are unchanged. Its failure scenario was relocated, not weakened.

Independent validation used D:/Codes/Imervue/.venv/Scripts/python.exe with QT_QPA_PLATFORM=offscreen. The three targeted test modules test_puppet_archive_contracts.py, test_puppet_document_io.py, and test_puppet_archive_curves.py passed, 98 tests in 10.51 seconds. AST comparison found 42 of 52 original function/class definitions unchanged after relocation. The ten adjusted definitions were inspected against the baseline.

The supplied differential artifacts independently compare equal across 2,317 records, including 962 accepted archives. The script compares decompressed archive member payload bytes and exception class names/messages. It does not compare complete ZIP byte streams, duplicate member identity, ZipInfo metadata, exception defining modules, or all in-memory value types. The format tests and manual review supply additional evidence for order, compression, tuple conversion, and error re-export identity. The corpus modifies one JSON location at a time and is not exhaustive.

The parent-reported Radon proxy result of all fifteen runtime files at or below twenty was not independently reproduced here. Radon is absent from the required Python environment. No packages were installed. The hosted Codacy result was not checked. Full-suite, lint, security scanning, packaging, and documentation gates remain the owning worker's responsibility. This review does not certify those gates.
