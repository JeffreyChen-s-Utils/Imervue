"""Tests for the Twitch chat hook.

Three layers:

* **Pure helpers** (``parse_chat_message``, ``match_keyword``,
  ``coerce_triggers``) are stateless string operations — easy to
  test without any socket.
* **``process_line`` round-trip** exercises the IRC dispatch logic
  without spinning up the worker thread, by calling the public
  ``process_line`` hook directly.
* **``start`` failure paths** verify the error-surface contract
  (no endpoint → False, socket open raises → False).
"""
from __future__ import annotations

import socket

from Imervue.desktop_pet.twitch_chat_hook import (
    TwitchChatClient,
    coerce_triggers,
    match_keyword,
    parse_chat_message,
)


# ---------------------------------------------------------------
# parse_chat_message
# ---------------------------------------------------------------


def test_parse_chat_message_happy_path():
    """Canonical IRC PRIVMSG → fully populated dict."""
    line = (
        ":alice!alice@alice.tmi.twitch.tv PRIVMSG #channelname :hello world"
    )
    msg = parse_chat_message(line)
    assert msg == {
        "user": "alice", "channel": "channelname", "text": "hello world",
    }


def test_parse_chat_message_returns_none_for_non_privmsg():
    """Anything else (PING, JOIN, NOTICE, etc.) → None so the
    dispatcher knows to skip it."""
    assert parse_chat_message("PING :tmi.twitch.tv") is None
    assert parse_chat_message(":alice JOIN #foo") is None
    assert parse_chat_message("") is None


def test_parse_chat_message_returns_none_for_malformed():
    """Garbage in → None out, not an exception."""
    assert parse_chat_message("PRIVMSG #foo :hi") is None   # no prefix
    assert parse_chat_message(":alice PRIVMSG nochannel hi") is None
    assert parse_chat_message(":!@ PRIVMSG #foo :hi") is None   # empty user


def test_parse_chat_message_handles_text_with_colons():
    """The text segment can contain colons (URLs, emoticons). The
    parser must split only on the *first* ' :' separator."""
    line = ":bob!bob@host PRIVMSG #foo :go to https://example.com :)"
    msg = parse_chat_message(line)
    assert msg is not None
    assert msg["text"] == "go to https://example.com :)"


# ---------------------------------------------------------------
# match_keyword
# ---------------------------------------------------------------


def test_match_keyword_substring_case_insensitive():
    """Substring match — matches anywhere in the text, not just on
    whole words. Catches "hello" in "say hello" and "HELLO" alike."""
    assert match_keyword("say hello there", {"hello": "Wave"}) == "Wave"
    assert match_keyword("HELLO!", {"hello": "Wave"}) == "Wave"


def test_match_keyword_first_dict_match_wins():
    """Iteration order matches insertion — gives the user
    predictable control over overlapping keywords."""
    triggers = {"raid": "Excited", "ai": "Boring"}
    # "raid" matches first → Excited, even though "ai" is a substring.
    assert match_keyword("incoming raid!", triggers) == "Excited"


def test_match_keyword_empty_inputs_return_none():
    assert match_keyword("", {"hi": "Wave"}) is None
    assert match_keyword("anything", {}) is None
    # Empty-keyword entries are silently skipped (they'd match
    # every message otherwise — defensive against settings typos).
    assert match_keyword("hi", {"": "Wave", "bye": "Bow"}) is None


def test_match_keyword_no_match_returns_none():
    assert match_keyword("totally unrelated", {"hi": "Wave"}) is None


# ---------------------------------------------------------------
# coerce_triggers
# ---------------------------------------------------------------


def test_coerce_triggers_drops_garbage():
    """Non-dict / non-string values must drop, never surface as
    runtime errors during message dispatch."""
    raw = {
        "hi": "Wave",
        "": "Empty",          # empty key
        "bye": "",            # empty value
        "thanks": 42,         # non-string value
        123: "Strange",       # non-string key
    }
    assert coerce_triggers(raw) == {"hi": "Wave"}


def test_coerce_triggers_non_dict_input():
    """Settings file might contain anything; non-dict → empty
    out so the rest of the loader doesn't error."""
    assert coerce_triggers(None) == {}
    assert coerce_triggers([]) == {}
    assert coerce_triggers("hi=Wave") == {}


# ---------------------------------------------------------------
# Client lifecycle / process_line
# ---------------------------------------------------------------


def test_client_start_without_endpoint_returns_false(qapp):
    """Channel + oauth are required — calling start without them
    must surface as False, not silently open a half-configured
    socket."""
    client = TwitchChatClient()
    assert client.start() is False
    assert client.is_running() is False


def test_client_start_with_only_channel_returns_false(qapp):
    client = TwitchChatClient()
    client.set_endpoint(channel="foo", oauth="")
    assert client.start() is False


def test_client_start_handles_connect_error(qapp, monkeypatch):
    """A socket-level failure (network down, DNS, refused) must
    surface as ``False`` and leave ``is_running`` False — same
    contract as the OBS hook."""
    def _raise(*_args, **_kwargs):
        raise OSError("connect failed")

    monkeypatch.setattr(socket, "create_connection", _raise)
    client = TwitchChatClient()
    client.set_endpoint(channel="foo", oauth="oauth:abc")   # noqa: S106  # test fixture
    assert client.start() is False
    assert client.is_running() is False


def test_process_line_fires_keyword(qapp):
    """The dispatch hook must marshal a recognised keyword through
    to ``keyword_matched``."""
    client = TwitchChatClient()
    received: list[str] = []
    client.keyword_matched.connect(received.append)
    client.set_triggers({"hello": "Wave"})
    client.process_line(":alice!alice@host PRIVMSG #chan :hello world")
    assert received == ["Wave"]


def test_process_line_skips_non_privmsg(qapp):
    """PING / JOIN lines must not fire keywords. PING in particular
    must round-trip silently (production code sends PONG)."""
    client = TwitchChatClient()
    received: list[str] = []
    client.keyword_matched.connect(received.append)
    client.set_triggers({"hello": "Wave"})
    client.process_line("PING :tmi.twitch.tv")
    client.process_line(":alice JOIN #chan")
    assert received == []


def test_process_line_no_trigger_match(qapp):
    """Recognised PRIVMSG but no keyword match → no signal."""
    client = TwitchChatClient()
    received: list[str] = []
    client.keyword_matched.connect(received.append)
    client.set_triggers({"hello": "Wave"})
    client.process_line(":alice!alice@host PRIVMSG #chan :totally unrelated")
    assert received == []


def test_set_endpoint_lowers_and_strips_hash(qapp):
    """Users sometimes paste ``#channel`` from chat URLs — strip the
    hash so the JOIN command (which adds its own) doesn't double
    it up."""
    client = TwitchChatClient()
    client.set_endpoint(channel="#FooBar", oauth="oauth:abc")   # noqa: S106  # test fixture
    assert client._channel == "foobar"   # noqa: SLF001


def test_set_triggers_coerces(qapp):
    """The setter must filter garbage so the live dispatch never
    sees bad entries."""
    client = TwitchChatClient()
    client.set_triggers({"hi": "Wave", "": "Empty", "bye": 0})
    assert client.triggers() == {"hi": "Wave"}


def test_stop_when_not_running_is_safe(qapp):
    """Calling stop on a never-started client must not raise."""
    client = TwitchChatClient()
    client.stop()
    assert client.is_running() is False


def test_shutdown_alias_stops(qapp, monkeypatch):
    """shutdown == stop; same lifecycle method other drivers expose."""
    def _raise(*_a, **_kw):
        raise OSError("simulated")
    monkeypatch.setattr(socket, "create_connection", _raise)
    client = TwitchChatClient()
    client.set_endpoint(channel="foo", oauth="oauth:abc")   # noqa: S106  # test fixture
    client.start()   # will fail; just exercising the shutdown alias
    client.shutdown()
    assert client.is_running() is False
