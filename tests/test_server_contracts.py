"""Contract tests for the MCP JSON-RPC server (``Imervue.mcp_server.server``).

The exact JSON every method answers with — ids, error codes and messages,
result shapes — and the set of registered method names are what an MCP client
relies on, so they are pinned here as request -> response tables, together
with the dispatch order of ``handle_message``, the ``tools/call`` envelope, the
progress injection, the stdio loop and the resource watcher.
"""
from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from Imervue.mcp_server import server as server_module
from Imervue.mcp_server.completion import complete
from Imervue.mcp_server.notifications import Notifier
from Imervue.mcp_server.prompts import list_prompts
from Imervue.mcp_server.resources import list_resource_templates
from Imervue.mcp_server.server import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    MCPServer,
    run,
)

_NOT_OBJECT = "params must be an object"
_DATA = {"a": 1, "b": "é"}
_OUTPUT_SCHEMA = {"type": "object"}
_ANNOTATIONS = {"readOnlyHint": True}
_ECHO_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}}
_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _echo(text: str) -> str:
    return text


def _data() -> dict:
    return dict(_DATA)


def _listy() -> list:
    return [1, 2]


def _boom() -> None:
    raise RuntimeError("kaput")


def _with_progress(progress) -> bool:
    progress.report(1, 2)
    return progress.active


def _make_server() -> MCPServer:
    srv = MCPServer()
    srv.register("echo", "Echo text.", _ECHO_SCHEMA, _echo)
    srv.register(
        "data", "Return a dict.", _EMPTY_SCHEMA, _data,
        output_schema=_OUTPUT_SCHEMA, annotations=_ANNOTATIONS,
    )
    srv.register("listy", "Return a list.", _EMPTY_SCHEMA, _listy)
    srv.register("boom", "Always fails.", _EMPTY_SCHEMA, _boom)
    srv.register("prog", "Reports progress.", _EMPTY_SCHEMA, _with_progress)
    return srv


@pytest.fixture
def srv() -> MCPServer:
    return _make_server()


def _ok(msg_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _text(text: str, *, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _call(srv: MCPServer, method: str, params=None, msg_id=1):
    message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        message["params"] = params
    return srv.handle_message(message)


# ---------------------------------------------------------------------------
# Registered method names
# ---------------------------------------------------------------------------


def test_method_table_names_and_order():
    assert list(server_module._METHOD_HANDLERS) == [
        "initialize", "tools/list", "tools/call", "prompts/list", "prompts/get",
        "resources/list", "resources/templates/list", "resources/read", "ping",
        "completion/complete", "resources/subscribe", "resources/unsubscribe",
        "logging/setLevel",
    ]


def test_method_table_values_are_server_methods():
    for method, handler in server_module._METHOD_HANDLERS.items():
        assert callable(handler), method
        assert getattr(MCPServer, handler.__name__) is handler, method


# ---------------------------------------------------------------------------
# handle_message envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("message", "expected"), [
    ("oops", _err(None, -32600, "request must be a JSON object")),
    ([1, 2], _err(None, -32600, "request must be a JSON object")),
    ({"id": 7}, _err(7, -32600, "missing 'method'")),
    ({"id": "s", "method": 5}, _err("s", -32600, "missing 'method'")),
    ({"id": 3, "method": "notifications/initialized"}, None),
    ({"method": "notifications/cancelled", "params": [1]}, None),
    ({"id": 4, "method": "x/y"}, _err(4, -32601, "unknown method 'x/y'")),
    ({"method": "ping"}, _ok(None, {})),
    ({"id": "abc", "method": "ping", "params": None}, _ok("abc", {})),
    ({"id": 0, "method": "ping", "params": []}, _ok(0, {})),
])
def test_handle_message_envelope(srv, message, expected):
    assert srv.handle_message(message) == expected


def test_handler_crash_becomes_internal_error(srv, monkeypatch):
    def broken():
        raise RuntimeError("bad")

    monkeypatch.setattr("Imervue.mcp_server.prompts.list_prompts", broken)
    assert _call(srv, "prompts/list", msg_id=9) == _err(9, -32603, "internal error: bad")


# ---------------------------------------------------------------------------
# Per-method request -> response table
# ---------------------------------------------------------------------------


_INITIALIZE_RESULT = {
    "protocolVersion": "2025-03-26",
    "capabilities": {
        "tools": {"listChanged": False},
        "prompts": {"listChanged": False},
        "resources": {"subscribe": True, "listChanged": True},
        "completions": {},
        "logging": {},
    },
    "serverInfo": {"name": "imervue", "version": "1.0.0"},
}

_TOOLS_LIST_RESULT = {"tools": [
    {"name": "echo", "description": "Echo text.", "inputSchema": _ECHO_SCHEMA},
    {
        "name": "data", "description": "Return a dict.", "inputSchema": _EMPTY_SCHEMA,
        "outputSchema": _OUTPUT_SCHEMA, "annotations": _ANNOTATIONS,
    },
    {"name": "listy", "description": "Return a list.", "inputSchema": _EMPTY_SCHEMA},
    {"name": "boom", "description": "Always fails.", "inputSchema": _EMPTY_SCHEMA},
    {"name": "prog", "description": "Reports progress.", "inputSchema": _EMPTY_SCHEMA},
]}

_SUBSCRIPTION_URI_ERROR = "params.uri must be a non-empty string"

_TABLE = [
    ("initialize", None, _ok(1, _INITIALIZE_RESULT)),
    ("initialize", [1], _ok(1, _INITIALIZE_RESULT)),
    ("ping", {"x": 1}, _ok(1, {})),
    ("tools/list", None, _ok(1, _TOOLS_LIST_RESULT)),
    ("tools/call", {"name": "echo", "arguments": {"text": "hi"}}, _ok(1, _text("hi"))),
    ("tools/call", {"name": "data"}, _ok(1, {
        **_text(json.dumps(_DATA, ensure_ascii=False, indent=2)),
        "structuredContent": _DATA,
    })),
    ("tools/call", {"name": "listy", "arguments": None},
     _ok(1, _text(json.dumps([1, 2], indent=2)))),
    ("tools/call", {"name": "boom", "arguments": {}},
     _ok(1, _text("Error: kaput", is_error=True))),
    ("tools/call", {"name": "prog"}, _ok(1, _text("false"))),
    ("tools/call", [1], _err(1, -32602, _NOT_OBJECT)),
    ("tools/call", {}, _err(1, -32602, "params.name must be a string")),
    ("tools/call", {"name": 3}, _err(1, -32602, "params.name must be a string")),
    ("tools/call", {"name": "nope"}, _err(1, -32602, "unknown tool 'nope'")),
    ("tools/call", {"name": "echo", "arguments": [1]},
     _err(1, -32602, "params.arguments must be an object")),
    ("prompts/list", None, _ok(1, {"prompts": list_prompts()})),
    ("prompts/get", [1], _err(1, -32602, _NOT_OBJECT)),
    ("prompts/get", {}, _err(1, -32602, "params.name must be a string")),
    ("prompts/get", {"name": "nope"}, _err(1, -32602, "unknown prompt 'nope'")),
    ("resources/list", None, _ok(1, {"resources": []})),
    ("resources/templates/list", None, _ok(1, list_resource_templates())),
    ("resources/read", [1], _err(1, -32602, _NOT_OBJECT)),
    ("resources/read", {"uri": "x"}, _err(1, -32602, "unsupported resource URI: 'x'")),
    ("resources/read", {}, _err(1, -32602, "unsupported resource URI: None")),
    ("resources/subscribe", [1], _err(1, -32602, _NOT_OBJECT)),
    ("resources/subscribe", {}, _err(1, -32602, _SUBSCRIPTION_URI_ERROR)),
    ("resources/subscribe", {"uri": ""}, _err(1, -32602, _SUBSCRIPTION_URI_ERROR)),
    ("resources/subscribe", {"uri": 5}, _err(1, -32602, _SUBSCRIPTION_URI_ERROR)),
    ("resources/subscribe", {"uri": "imervue://image/a"}, _ok(1, {})),
    ("resources/unsubscribe", [1], _err(1, -32602, _NOT_OBJECT)),
    ("resources/unsubscribe", {}, _err(1, -32602, _SUBSCRIPTION_URI_ERROR)),
    ("resources/unsubscribe", {"uri": "imervue://image/a"}, _ok(1, {})),
    ("completion/complete", [1], _err(1, -32602, _NOT_OBJECT)),
    ("completion/complete", None, _ok(1, complete(None, {}))),
    ("completion/complete", {
        "ref": {"type": "ref/prompt", "name": "suggest_edits"},
        "argument": {"name": "style", "value": "p"},
    }, _ok(1, {"completion": {
        "values": ["portrait", "product"], "total": 2, "hasMore": False,
    }})),
    ("logging/setLevel", [1], _err(1, -32602, "invalid log level: None")),
    ("logging/setLevel", {}, _err(1, -32602, "invalid log level: None")),
    ("logging/setLevel", {"level": "loud"}, _err(1, -32602, "invalid log level: 'loud'")),
    ("logging/setLevel", {"level": "debug"}, _ok(1, {})),
]


@pytest.mark.parametrize(("method", "params", "expected"), _TABLE)
def test_request_response_table(srv, method, params, expected):
    assert _call(srv, method, params) == expected


def test_table_covers_every_registered_method():
    assert {row[0] for row in _TABLE} == set(server_module._METHOD_HANDLERS)


def test_constants_match_the_initialize_reply():
    assert (PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION) == (
        "2025-03-26", "imervue", "1.0.0")


# ---------------------------------------------------------------------------
# State-changing methods and server-side helpers
# ---------------------------------------------------------------------------


def test_set_level_updates_the_floor_only_when_valid(srv):
    _call(srv, "logging/setLevel", {"level": "loud"})
    assert srv.log_level == "info"
    _call(srv, "logging/setLevel", {"level": "error"})
    assert srv.log_level == "error"


def test_subscribe_then_unsubscribe_tracks_the_uri(srv):
    uri = "imervue://image/a"
    _call(srv, "resources/subscribe", {"uri": uri})
    assert srv.subscriptions.is_subscribed(uri)
    _call(srv, "resources/unsubscribe", {"uri": uri})
    assert not srv.subscriptions.is_subscribed(uri)


def test_tools_call_argument_error_is_a_tool_error(srv):
    reply = _call(srv, "tools/call", {"name": "echo", "arguments": {"wrong": 1}})
    assert reply["id"] == 1
    result = reply["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("Error: argument error: ")
    assert set(result) == {"content", "isError"}


def test_progress_reporter_is_bound_to_token_and_notifier(srv):
    stream = io.StringIO()
    srv.notifier = Notifier(stream)
    reply = _call(srv, "tools/call", {"name": "prog", "_meta": {"progressToken": "t1"}})
    assert reply == _ok(1, _text("true"))
    pushed = json.loads(stream.getvalue())
    assert pushed["method"] == "notifications/progress"
    assert pushed["params"]["progressToken"] == "t1"


def test_progress_is_not_injected_into_other_tools(srv):
    srv.notifier = Notifier(io.StringIO())
    reply = _call(srv, "tools/call", {
        "name": "echo", "arguments": {"text": "x"}, "_meta": {"progressToken": 1}})
    assert reply == _ok(1, _text("x"))


def test_register_rejects_a_duplicate_name(srv):
    with pytest.raises(ValueError, match="tool 'echo' already registered"):
        srv.register("echo", "again", _EMPTY_SCHEMA, _echo)


def test_register_records_progress_acceptance(srv):
    assert srv.tools["prog"].accepts_progress is True
    assert srv.tools["echo"].accepts_progress is False


def test_emit_log_respects_the_floor(srv):
    stream = io.StringIO()
    srv.notifier = Notifier(stream)
    srv.emit_log("debug", "hidden")
    assert stream.getvalue() == ""
    srv.emit_log("error", {"k": 1}, "db")
    assert json.loads(stream.getvalue()) == {
        "jsonrpc": "2.0", "method": "notifications/message",
        "params": {"level": "error", "data": {"k": 1}, "logger": "db"},
    }


def test_emit_log_without_notifier_is_silent(srv):
    srv.emit_log("emergency", "x")


def test_resources_list_reads_the_configured_root(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "a.png")
    srv = MCPServer(resource_root=str(tmp_path))
    resources = _call(srv, "resources/list")["result"]["resources"]
    assert [entry["name"] for entry in resources] == ["a.png"]
    assert _call(srv, "resources/list", {"cursor": "!!!"}) == _err(
        1, -32602, "invalid cursor")


def test_resources_read_missing_file_is_not_found(tmp_path):
    from Imervue.mcp_server.resources import image_uri
    missing = tmp_path / "gone.png"
    reply = _call(MCPServer(), "resources/read", {"uri": image_uri(str(missing))})
    assert reply == _err(1, -32002, f"resource not found: {missing}")


# ---------------------------------------------------------------------------
# stdio loop
# ---------------------------------------------------------------------------


def _run_lines(lines: list[str]) -> list[dict]:
    stdout = io.StringIO()
    run(stdin=io.StringIO("".join(lines)), stdout=stdout)
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


def test_run_answers_in_order_and_skips_notifications(monkeypatch):
    monkeypatch.delenv("IMERVUE_MCP_ROOT", raising=False)
    replies = _run_lines([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n",
        "   \n",
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "nope"}) + "\n",
        "[]\n",
    ])
    assert replies == [
        _ok(1, {}),
        _err(2, -32601, "unknown method 'nope'"),
        _err(None, -32600, "request must be a JSON object"),
    ]


def test_run_parse_error_reply(monkeypatch):
    monkeypatch.delenv("IMERVUE_MCP_ROOT", raising=False)
    (reply,) = _run_lines(["{ not json\n"])
    assert reply["id"] is None
    assert reply["error"]["code"] == -32700
    assert reply["error"]["message"].startswith("parse error: ")


def test_run_registers_the_default_tools(monkeypatch):
    monkeypatch.delenv("IMERVUE_MCP_ROOT", raising=False)
    (reply,) = _run_lines([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})])
    names = {tool["name"] for tool in reply["result"]["tools"]}
    assert {"list_images", "read_image_metadata"} <= names


def test_run_uses_the_resource_root_from_the_environment(tmp_path, monkeypatch):
    Image.new("RGB", (4, 4)).save(tmp_path / "b.png")
    monkeypatch.setenv("IMERVUE_MCP_ROOT", str(tmp_path))
    (reply,) = _run_lines([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "resources/list"}) + "\n"])
    assert [entry["name"] for entry in reply["result"]["resources"]] == ["b.png"]


# ---------------------------------------------------------------------------
# Resource watcher
# ---------------------------------------------------------------------------


def test_resource_watcher_none_for_missing_root(tmp_path):
    srv = MCPServer(resource_root=str(tmp_path / "absent"))
    assert server_module._start_resource_watcher(srv) is None


class _FakeObserver:
    """Stands in for watchdog's Observer so the test needs no real file-system event."""

    def __init__(self):
        self.scheduled = []
        self.daemon = False
        self.started = False

    def schedule(self, handler, path, recursive):
        self.scheduled.append((handler, path, recursive))

    def start(self):
        self.started = True


def test_resource_watcher_pushes_updated_and_list_changed(tmp_path, monkeypatch):
    import watchdog.observers
    monkeypatch.setattr(watchdog.observers, "Observer", _FakeObserver)
    srv = MCPServer(resource_root=str(tmp_path))
    stream = io.StringIO()
    srv.notifier = Notifier(stream)
    observer = server_module._start_resource_watcher(srv)
    assert isinstance(observer, _FakeObserver)
    assert observer.started and observer.daemon
    [(handler, path, recursive)] = observer.scheduled
    from Imervue.mcp_server.resources import image_uri
    srv.subscriptions.subscribe(image_uri(str(tmp_path / "new.png")))
    assert (path, recursive) == (str(tmp_path), False)
    handler.on_any_event(SimpleNamespace(is_directory=False, src_path=str(tmp_path / "new.png")))
    file_output = stream.getvalue()
    assert "notifications/resources/updated" in file_output
    assert "notifications/resources/list_changed" in file_output
    handler.on_any_event(SimpleNamespace(is_directory=True, src_path=str(tmp_path / "sub")))
    dir_output = stream.getvalue()[len(file_output):]
    assert "notifications/resources/updated" not in dir_output
    assert "notifications/resources/list_changed" in dir_output
