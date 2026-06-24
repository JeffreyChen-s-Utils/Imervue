"""Reusable chat-command router.

The Twitch hook's ``match_keyword`` only does substring matching. This module
generalises it into a first-match-wins router whose rules can match a message
by ``exact`` text, a ``prefix``, a ``substring``, or a ``regex`` — reusable for
Twitch, webhooks, or a chat-plugin. All matching is case-insensitive and pure
(no Qt, no I/O); an unparseable regex rule simply never matches.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MATCH_KINDS = ("exact", "prefix", "substring", "regex")


@dataclass
class CommandRule:
    """One routing rule: match *pattern* (by *kind*) → emit *result*."""

    pattern: str
    result: str
    kind: str = "substring"


def _rule_matches(rule: CommandRule, text: str, lowered: str) -> bool:
    pattern = rule.pattern
    if rule.kind == "exact":
        return lowered.strip() == pattern.lower()
    if rule.kind == "prefix":
        return bool(pattern) and lowered.startswith(pattern.lower())
    if rule.kind == "regex":
        try:
            return re.search(pattern, text, re.IGNORECASE) is not None
        except re.error:
            return False
    return bool(pattern) and pattern.lower() in lowered


def match_command(text: str, rules: Iterable[CommandRule]) -> str | None:
    """Route *text* through *rules*, returning the first match's result.

    Rule order is the precedence order — the first rule that matches wins.
    """
    if not text:
        return None
    lowered = text.lower()
    for rule in rules:
        if _rule_matches(rule, text, lowered):
            return rule.result
    return None


def rule_from_spec(spec: str, result: str) -> CommandRule:
    """Infer a rule from *spec* syntax.

    ``/pat/`` → regex, leading ``=`` → exact, trailing ``*`` → prefix,
    otherwise substring.
    """
    s = spec.strip()
    if len(s) >= 2 and s.startswith("/") and s.endswith("/"):
        return CommandRule(s[1:-1], result, "regex")
    if s.startswith("="):
        return CommandRule(s[1:], result, "exact")
    if s.endswith("*"):
        return CommandRule(s[:-1], result, "prefix")
    return CommandRule(s, result, "substring")


def rules_from_dict(mapping: Mapping[str, str]) -> list[CommandRule]:
    """Build rules from an ordered ``{spec: result}`` map (order = priority)."""
    out: list[CommandRule] = []
    for spec, result in mapping.items():
        if isinstance(spec, str) and spec.strip() and isinstance(result, str):
            out.append(rule_from_spec(spec, result))
    return out
