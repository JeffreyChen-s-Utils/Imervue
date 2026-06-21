"""Tests for the reusable chat-command router."""
from __future__ import annotations

from Imervue.desktop_pet.command_parser import (
    CommandRule,
    match_command,
    rule_from_spec,
    rules_from_dict,
)


# ---------------------------------------------------------------------------
# match_command — per kind
# ---------------------------------------------------------------------------


def test_exact_match_is_case_insensitive_and_whole():
    rules = [CommandRule("!wave", "Wave", "exact")]
    assert match_command("!WAVE", rules) == "Wave"
    assert match_command("!wave please", rules) is None


def test_prefix_match():
    rules = [CommandRule("!thank", "Bow", "prefix")]
    assert match_command("!thanks a lot", rules) == "Bow"
    assert match_command("please !thank", rules) is None


def test_substring_match():
    rules = [CommandRule("dance", "Dance", "substring")]
    assert match_command("can you DANCE now", rules) == "Dance"


def test_regex_match():
    rules = [CommandRule(r"(dance|move)", "Dance", "regex")]
    assert match_command("please move", rules) == "Dance"
    assert match_command("sit", rules) is None


def test_invalid_regex_never_matches_but_others_still_work():
    rules = [
        CommandRule("(", "Broken", "regex"),
        CommandRule("hi", "Hi", "substring"),
    ]
    assert match_command("say hi", rules) == "Hi"


def test_empty_text_returns_none():
    assert match_command("", [CommandRule("x", "X")]) is None


# ---------------------------------------------------------------------------
# precedence
# ---------------------------------------------------------------------------


def test_first_matching_rule_wins():
    rules = [
        CommandRule("raid", "Raid", "substring"),
        CommandRule("ai", "AI", "substring"),
    ]
    assert match_command("raidaboo", rules) == "Raid"


# ---------------------------------------------------------------------------
# rule_from_spec
# ---------------------------------------------------------------------------


def test_rule_from_spec_infers_kind():
    assert rule_from_spec("/da.+/", "D").kind == "regex"
    assert rule_from_spec("/da.+/", "D").pattern == "da.+"
    assert rule_from_spec("=!wave", "W") == CommandRule("!wave", "W", "exact")
    assert rule_from_spec("!thank*", "B") == CommandRule("!thank", "B", "prefix")
    assert rule_from_spec("dance", "D") == CommandRule("dance", "D", "substring")


def test_rules_from_dict_preserves_order_and_filters_bad():
    rules = rules_from_dict({"!hi": "Wave", "  ": "Skip", "/bye/": "Leave"})
    assert [r.result for r in rules] == ["Wave", "Leave"]
    assert rules[1].kind == "regex"


def test_rules_from_dict_routes_end_to_end():
    rules = rules_from_dict({"=!wave": "Wave", "!thank*": "Bow", "/lol|haha/": "Laugh"})
    assert match_command("!wave", rules) == "Wave"
    assert match_command("!thanks", rules) == "Bow"
    assert match_command("that's so haha", rules) == "Laugh"
    assert match_command("nothing", rules) is None
