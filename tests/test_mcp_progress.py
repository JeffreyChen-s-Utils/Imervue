"""Tests for MCP progress notifications on tool calls.

Covers the ProgressReporter sender and progressToken extraction in isolation,
then the end-to-end wiring: a build_collage call carrying a _meta.progressToken
pushes notifications/progress through the server's notifier, while tools
without a progress parameter (or calls without a token) stay silent.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.mcp_server.progress import ProgressReporter, progress_token
from Imervue.mcp_server.server import MCPServer
from Imervue.mcp_server.tools import register_default_tools


class _RecordingNotifier:
    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []

    def notify(self, method, params=None):
        self.calls.append((method, params))


def _save_png(path):
    Image.fromarray(np.full((10, 10, 3), 120, dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def _server_with_notifier():
    server = MCPServer()
    register_default_tools(server)
    notifier = _RecordingNotifier()
    server.notifier = notifier
    return server, notifier


def _call(server, name, arguments, *, progress_id=None):
    params = {"name": name, "arguments": arguments}
    if progress_id is not None:
        params["_meta"] = {"progressToken": progress_id}
    return server.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params,
    })


def _progress_params(notifier):
    return [p for m, p in notifier.calls if m == "notifications/progress"]


# ---------------------------------------------------------------------------
# ProgressReporter
# ---------------------------------------------------------------------------


def test_reporter_inactive_without_token():
    notifier = _RecordingNotifier()
    reporter = ProgressReporter(notifier, None)
    assert reporter.active is False
    reporter.report(1, total=3)
    assert notifier.calls == []


def test_reporter_inactive_without_notifier_does_not_crash():
    reporter = ProgressReporter(None, "tok")
    assert reporter.active is False
    reporter.report(1)  # must be a safe no-op


def test_reporter_sends_full_params():
    notifier = _RecordingNotifier()
    ProgressReporter(notifier, 5).report(2, total=10, message="halfway")
    method, params = notifier.calls[0]
    assert method == "notifications/progress"
    assert params == {
        "progressToken": 5, "progress": 2.0, "total": 10.0, "message": "halfway",
    }


def test_reporter_omits_optional_fields():
    notifier = _RecordingNotifier()
    ProgressReporter(notifier, "t").report(1)
    _, params = notifier.calls[0]
    assert params == {"progressToken": "t", "progress": 1.0}


def test_reporter_drops_non_increasing_values():
    notifier = _RecordingNotifier()
    reporter = ProgressReporter(notifier, "t")
    reporter.report(1)
    reporter.report(1)      # equal -> dropped
    reporter.report(0.5)    # lower -> dropped
    reporter.report(2)
    assert [p["progress"] for _, p in notifier.calls] == [1.0, 2.0]


# ---------------------------------------------------------------------------
# progress_token extraction
# ---------------------------------------------------------------------------


def test_progress_token_accepts_string_and_int():
    assert progress_token({"_meta": {"progressToken": "abc"}}) == "abc"
    assert progress_token({"_meta": {"progressToken": 42}}) == 42


def test_progress_token_rejects_bool_and_float():
    assert progress_token({"_meta": {"progressToken": True}}) is None
    assert progress_token({"_meta": {"progressToken": 1.5}}) is None


def test_progress_token_missing_or_malformed_meta():
    assert progress_token({}) is None
    assert progress_token({"_meta": "not-a-dict"}) is None
    assert progress_token({"_meta": {}}) is None


# ---------------------------------------------------------------------------
# Registration detection
# ---------------------------------------------------------------------------


def test_accepts_progress_flag_set_per_handler():
    server, _ = _server_with_notifier()
    assert server.tools["build_collage"].accepts_progress is True
    assert server.tools["crop_image"].accepts_progress is False


# ---------------------------------------------------------------------------
# End-to-end through the server
# ---------------------------------------------------------------------------


def test_build_collage_emits_progress_with_token(tmp_path):
    server, notifier = _server_with_notifier()
    sources = [_save_png(tmp_path / f"i{n}.png") for n in range(3)]
    response = _call(
        server, "build_collage",
        {"sources": sources, "destination": str(tmp_path / "c.png"), "columns": 2},
        progress_id="tok-1",
    )
    assert response["result"]["isError"] is False
    updates = _progress_params(notifier)
    assert len(updates) == 3
    assert all(u["progressToken"] == "tok-1" for u in updates)
    assert [u["progress"] for u in updates] == [1.0, 2.0, 3.0]
    assert updates[-1]["total"] == 3.0


def test_build_collage_without_token_is_silent(tmp_path):
    server, notifier = _server_with_notifier()
    sources = [_save_png(tmp_path / f"i{n}.png") for n in range(2)]
    response = _call(
        server, "build_collage",
        {"sources": sources, "destination": str(tmp_path / "c.png")},
    )
    assert response["result"]["isError"] is False
    assert _progress_params(notifier) == []


def test_non_progress_tool_with_token_is_silent(tmp_path):
    server, notifier = _server_with_notifier()
    src = _save_png(tmp_path / "s.png")
    response = _call(
        server, "crop_image",
        {"source": src, "destination": str(tmp_path / "o.png"),
         "x": 0, "y": 0, "width": 5, "height": 5},
        progress_id=7,
    )
    assert response["result"]["isError"] is False
    assert _progress_params(notifier) == []
