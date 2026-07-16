"""Importing the AI background-remover plugin must not reconfigure root logging.

``logging.basicConfig`` at import time hijacked all propagated logging into a
truncated CWD file and could raise -- aborting the plugin load -- when the CWD was
read-only (a frozen install under Program Files). It was removed in favour of the
module's named logger.
"""
from __future__ import annotations

import logging


def test_import_adds_no_root_file_handler():
    import ai_background_remover.ai_background_remover  # noqa: F401
    offenders = [
        h for h in logging.getLogger().handlers
        if isinstance(h, logging.FileHandler)
        and str(getattr(h, "baseFilename", "")).endswith("ai_bg_remover.log")
    ]
    assert offenders == []
