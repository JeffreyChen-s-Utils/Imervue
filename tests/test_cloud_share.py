"""Tests for the Cloud Share plugin (uploaders + dialog wiring)."""
from __future__ import annotations

import json
from urllib.request import Request

import pytest

from cloud_share import uploaders
from cloud_share.uploaders import (
    IMGUR_API,
    UploadError,
    basic_auth_header,
    build_imgur_request,
    build_webdav_request,
    parse_imgur_link,
    upload_imgur,
    upload_webdav,
    webdav_target_url,
)


class _FakeResp:
    def __init__(self, status=201, body=b""):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_basic_auth_header():
    assert basic_auth_header("u", "p").startswith("Basic ")


def test_webdav_target_url_joins_once():
    assert webdav_target_url("https://d/dav/", "a.png") == "https://d/dav/a.png"
    assert webdav_target_url("https://d/dav", "a.png") == "https://d/dav/a.png"


def test_parse_imgur_link():
    assert parse_imgur_link({"data": {"link": "x"}}) == "x"
    assert parse_imgur_link({"data": {}}) is None
    assert parse_imgur_link({}) is None


def test_https_guard_rejects_http():
    with pytest.raises(UploadError):
        uploaders._https_urlopen(Request("http://insecure.example.com/x"))


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------


def test_build_webdav_request(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"xy")
    req = build_webdav_request("https://d/dav", str(f), "u", "p")
    assert req.full_url == "https://d/dav/a.png"
    assert req.get_method() == "PUT"
    assert req.data == b"xy"
    assert req.get_header("Authorization").startswith("Basic ")


def test_build_imgur_request(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"xy")
    req = build_imgur_request(str(f), "CID")
    assert req.full_url == IMGUR_API
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Client-ID CID"


# ---------------------------------------------------------------------------
# uploads (network mocked)
# ---------------------------------------------------------------------------


def test_upload_webdav_success(tmp_path, monkeypatch):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    monkeypatch.setattr(uploaders, "_https_urlopen", lambda req, timeout=30: _FakeResp(201))
    assert upload_webdav("https://d/dav", str(f)) == "https://d/dav/a.png"


def test_upload_webdav_rejects_http(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    with pytest.raises(UploadError):
        upload_webdav("http://d/dav", str(f))


def test_upload_imgur_success(tmp_path, monkeypatch):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    body = json.dumps({"data": {"link": "https://i.imgur.com/x.png"}}).encode()
    monkeypatch.setattr(uploaders, "_https_urlopen", lambda req, timeout=30: _FakeResp(200, body))
    assert upload_imgur(str(f), "CID") == "https://i.imgur.com/x.png"


def test_upload_imgur_no_link_raises(tmp_path, monkeypatch):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    body = json.dumps({"data": {}}).encode()
    monkeypatch.setattr(uploaders, "_https_urlopen", lambda req, timeout=30: _FakeResp(200, body))
    with pytest.raises(UploadError):
        upload_imgur(str(f), "CID")


# ---------------------------------------------------------------------------
# Qt smoke
# ---------------------------------------------------------------------------


def test_s3_object_url_strips_query():
    assert uploaders.s3_object_url(
        "https://b.s3.amazonaws.com/k.png?X-Amz-Sig=abc",
    ) == "https://b.s3.amazonaws.com/k.png"


def test_upload_s3_presigned_success(tmp_path, monkeypatch):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    monkeypatch.setattr(uploaders, "_https_urlopen", lambda req, timeout=30: _FakeResp(200))
    assert uploaders.upload_s3_presigned(
        "https://b.s3.amazonaws.com/k.png?sig=1", str(f),
    ) == "https://b.s3.amazonaws.com/k.png"


def test_upload_s3_rejects_http(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    with pytest.raises(UploadError):
        uploaders.upload_s3_presigned("http://b.s3/k?sig=1", str(f))


def test_upload_batch_collects_results():
    def uploader(path):
        if path == "bad":
            raise UploadError("nope")
        return f"link:{path}"
    results = uploaders.upload_batch(uploader, ["a", "bad", "c"])
    assert results == [("a", "link:a"), ("bad", None), ("c", "link:c")]


def test_dialog_smoke(qapp, tmp_path):
    from cloud_share.cloud_share_plugin import CloudShareDialog

    dialog = CloudShareDialog(object(), [str(tmp_path / "a.png")])
    try:
        assert dialog._target.count() == 3
        assert dialog._is_webdav() is True
        dialog._target.setCurrentIndex(2)  # S3
        assert dialog._is_webdav() is False
    finally:
        dialog.deleteLater()
