"""Supply-chain safety tests for the safety_review plugin.

CLAUDE.md (Network & Supply-Chain Safety) requires every ``hf_hub_download``
call to pin an explicit, non-empty ``revision`` so a compromised upstream
cannot silently swap the downloaded weights (bandit B615). These tests pin
that contract for both the in-process loader (``safety_review``) and the
out-of-process subprocess runner (``_runner``).
"""

from __future__ import annotations

import sys
import types

from safety_review import _runner, safety_review

# Both modules must agree on the same EraX repo / model / revision so there is
# a single source of truth and no duplicated literal drift.
_EXPECTED_REPO = "erax-ai/EraX-Anti-NSFW-V1.1"
_EXPECTED_MODEL = "erax-anti-nsfw-yolo11m-v1.1.pt"


def _install_fakes(monkeypatch):
    """Replace huggingface_hub + ultralytics with capturing fakes.

    Returns the dict that the fake ``hf_hub_download`` records its kwargs into.
    """
    captured: dict = {}

    def fake_hf_hub_download(**kwargs):
        captured.update(kwargs)
        return "fake-model.pt"

    fake_hf = types.ModuleType("huggingface_hub")
    fake_hf.hf_hub_download = fake_hf_hub_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)

    class _FakeYOLO:
        def __init__(self, path):
            self.path = path

    fake_ultra = types.ModuleType("ultralytics")
    fake_ultra.YOLO = _FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultra)

    return captured


def _assert_pinned(captured):
    """Assert the download was pinned to a non-empty explicit revision."""
    assert captured["repo_id"] == _EXPECTED_REPO
    assert captured["filename"] == _EXPECTED_MODEL
    revision = captured.get("revision")
    assert revision is not None
    assert isinstance(revision, str)
    assert revision.strip() != ""


def test_constants_match_across_modules():
    """Both modules share the same repo/model/revision triple (no drift)."""
    assert safety_review._ERAX_REPO == _runner._ERAX_REPO == _EXPECTED_REPO
    assert safety_review._ERAX_MODEL == _runner._ERAX_MODEL == _EXPECTED_MODEL
    assert safety_review._ERAX_REVISION == _runner._ERAX_REVISION
    assert safety_review._ERAX_REVISION.strip() != ""


def test_runner_load_anime_model_pins_revision(monkeypatch):
    captured = _install_fakes(monkeypatch)
    _runner._load_anime_model()
    _assert_pinned(captured)
    assert captured["revision"] == _runner._ERAX_REVISION


def test_safety_review_get_anime_model_pins_revision(monkeypatch):
    captured = _install_fakes(monkeypatch)
    # Reset the module-level cache so the download path actually runs.
    monkeypatch.setattr(safety_review, "_cached_anime_model", None)
    safety_review._get_anime_model()
    _assert_pinned(captured)
    assert captured["revision"] == safety_review._ERAX_REVISION


def test_revision_is_a_full_commit_sha():
    """A 40-char hex SHA is the stable anchor (the repo ships no tags)."""
    revision = safety_review._ERAX_REVISION
    assert len(revision) == 40
    assert all(ch in "0123456789abcdef" for ch in revision.lower())
