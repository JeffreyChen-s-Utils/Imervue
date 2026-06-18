"""Cloud / share uploaders — WebDAV (PUT) and Imgur (POST), HTTPS-only.

Uploading **publishes** the image to a third-party service, so it only ever
runs on an explicit user action with the user's own credentials. Every network
call goes through the HTTPS-only :func:`_https_urlopen` guard (the project's
network-safety rule), mirroring ``Imervue/plugin/pip_installer.py``.

The URL/auth/response helpers are pure and unit-tested; the upload functions
read the file and call the guard, which tests exercise with a fake response.
"""
from __future__ import annotations

import json
from base64 import b64encode
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

IMGUR_API = "https://api.imgur.com/3/image"
_HTTP_TIMEOUT = 30
_WEBDAV_OK = (200, 201, 204)


class UploadError(RuntimeError):
    """Raised when an upload is rejected (bad scheme) or fails."""


def _https_urlopen(req: Request, timeout: int = _HTTP_TIMEOUT):
    """urlopen that refuses any scheme other than https (bandit B310)."""
    scheme = urlparse(req.full_url).scheme
    if scheme != "https":
        raise UploadError(f"Refusing non-https URL scheme: {scheme!r}")
    return urlopen(req, timeout=timeout)  # nosec B310  # scheme validated above


def basic_auth_header(username: str, password: str) -> str:
    """Build an HTTP Basic ``Authorization`` header value."""
    token = b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def webdav_target_url(base_url: str, filename: str) -> str:
    """Join a WebDAV collection URL and a filename into a target URL."""
    return base_url.rstrip("/") + "/" + filename


def parse_imgur_link(payload: dict) -> str | None:
    """Pull the public image link out of an Imgur API response payload."""
    data = payload.get("data") if isinstance(payload, dict) else None
    return data.get("link") if isinstance(data, dict) else None


def build_webdav_request(base_url: str, file_path: str,
                         username: str = "", password: str | None = None) -> Request:
    path = Path(file_path)
    req = Request(  # noqa: S310 - scheme enforced by _https_urlopen at send time
        webdav_target_url(base_url, path.name),
        data=path.read_bytes(),
        method="PUT",
    )
    if username:
        req.add_header("Authorization", basic_auth_header(username, password or ""))
    return req


def upload_webdav(base_url: str, file_path: str,
                  username: str = "", password: str | None = None) -> str:
    """PUT *file_path* to a WebDAV collection; return its URL."""
    req = build_webdav_request(base_url, file_path, username, password)
    with _https_urlopen(req) as resp:
        status = getattr(resp, "status", None)
        if status is not None and status not in _WEBDAV_OK:
            raise UploadError(f"WebDAV upload failed: HTTP {status}")
    return req.full_url


def build_imgur_request(file_path: str, client_id: str) -> Request:
    data = b64encode(Path(file_path).read_bytes())
    req = Request(  # noqa: S310 - scheme enforced by _https_urlopen at send time
        IMGUR_API, data=data, method="POST",
    )
    req.add_header("Authorization", f"Client-ID {client_id}")
    return req


def upload_imgur(file_path: str, client_id: str) -> str:
    """POST *file_path* to Imgur (anonymous, user's Client-ID); return the link."""
    req = build_imgur_request(file_path, client_id)
    with _https_urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    link = parse_imgur_link(payload)
    if not link:
        raise UploadError("Imgur upload returned no link.")
    return link
