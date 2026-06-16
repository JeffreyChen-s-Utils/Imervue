"""Tests for image captioning (prompt/payload/parse are pure; the network call
is exercised with a stubbed POST helper). No Qt needed."""
from __future__ import annotations

import base64

import pytest

from Imervue.image.caption import (
    CAPTION_STYLES,
    build_caption_payload,
    build_caption_prompt,
    generate_caption,
    parse_caption_response,
)


class TestBuildCaptionPrompt:
    @pytest.mark.parametrize("style", CAPTION_STYLES)
    def test_known_styles_are_non_empty(self, style):
        assert build_caption_prompt(style).strip()

    def test_alt_text_mentions_description(self):
        assert "alt text" in build_caption_prompt("alt_text").lower()

    def test_unknown_style_falls_back_to_alt_text(self):
        assert build_caption_prompt("bogus") == build_caption_prompt("alt_text")


class TestBuildCaptionPayload:
    def test_structure_and_base64_round_trip(self):
        image_bytes = b"\x89PNG\r\nfake-bytes"
        payload = build_caption_payload("llava", image_bytes, "describe it")
        assert payload["model"] == "llava"
        assert payload["prompt"] == "describe it"
        assert payload["stream"] is False
        assert base64.b64decode(payload["images"][0]) == image_bytes


class TestParseCaptionResponse:
    def test_extracts_and_strips_quotes(self):
        assert parse_caption_response({"response": '  "a red car"  '}) == "a red car"

    def test_empty_response_is_none(self):
        assert parse_caption_response({"response": "   "}) is None

    def test_missing_or_non_string_is_none(self):
        assert parse_caption_response({}) is None
        assert parse_caption_response({"response": 5}) is None
        assert parse_caption_response("not a dict") is None


class TestGenerateCaption:
    def test_posts_vision_payload_and_returns_caption(self, tmp_path, monkeypatch):
        from Imervue.desktop_pet import llm_dialogue

        image = tmp_path / "photo.png"
        image.write_bytes(b"\x89PNG\r\nbody")
        captured = {}

        def _fake_post(url, payload, timeout):
            captured["url"] = url
            captured["payload"] = payload
            return {"response": '"a small dog"'}

        monkeypatch.setattr(llm_dialogue, "_request_json", _fake_post)
        out = generate_caption(image, model="llava", base_url="http://localhost:11434")

        assert out == "a small dog"
        assert captured["url"].endswith("/api/generate")
        assert captured["payload"]["images"]  # base64 image attached
        assert captured["payload"]["stream"] is False

    def test_empty_caption_raises(self, tmp_path, monkeypatch):
        from Imervue.desktop_pet import llm_dialogue

        image = tmp_path / "photo.png"
        image.write_bytes(b"data")
        monkeypatch.setattr(
            llm_dialogue, "_request_json", lambda *a, **k: {"response": "  "})
        with pytest.raises(ValueError, match="empty caption"):
            generate_caption(image)
