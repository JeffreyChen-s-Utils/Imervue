"""Validate translation dictionaries before they reach :class:`LanguageWrapper`.

``language_wrapper.merge_translations`` silently skips unknown languages and
never overwrites existing keys, and ``register_language`` trusts the caller to
supply a dict with the same keys as English — so a plugin with a typo, a
missing language, or a mismatched ``{placeholder}`` fails quietly. These pure
helpers let a plugin (or a test) check a dict first:

* :func:`validate_translation` — one language dict against a reference
  (the ``register_language`` contract: same keys, no empty values, matching
  placeholders).
* :func:`validate_merge_payload` — a ``{lang: {key: text}}`` payload for
  ``merge_translations`` (every language defines the same new keys with
  matching placeholders, and the language is actually registered).

Pure dict / string work — no Qt, no singletons.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
_MAX_LISTED = 10


def extract_placeholders(text: str) -> set[str]:
    """Return the ``{name}`` placeholders in *text* (empty set for non-str)."""
    if not isinstance(text, str):
        return set()
    return set(_PLACEHOLDER_RE.findall(text))


def compare_keys(
    reference: Mapping[str, str], candidate: Mapping[str, str],
) -> tuple[set[str], set[str]]:
    """Return ``(missing, extra)``: reference keys absent from *candidate*, and
    candidate keys not in *reference*."""
    ref_keys = set(reference)
    cand_keys = set(candidate)
    return ref_keys - cand_keys, cand_keys - ref_keys


def find_empty_values(candidate: Mapping[str, str]) -> list[str]:
    """Return keys whose value is ``None``, not a string, or blank/whitespace."""
    return [
        key
        for key, value in candidate.items()
        if not isinstance(value, str) or not value.strip()
    ]


def find_placeholder_mismatches(
    reference: Mapping[str, str], candidate: Mapping[str, str],
) -> list[tuple[str, set[str], set[str]]]:
    """Return ``(key, reference_placeholders, candidate_placeholders)`` for keys
    present in both whose ``{placeholder}`` sets differ."""
    out: list[tuple[str, set[str], set[str]]] = []
    for key, ref_text in reference.items():
        if key not in candidate:
            continue
        ref_ph = extract_placeholders(ref_text)
        cand_ph = extract_placeholders(candidate[key])
        if ref_ph != cand_ph:
            out.append((key, ref_ph, cand_ph))
    return out


def validate_translation(
    reference: Mapping[str, str],
    candidate: Mapping[str, str],
    *,
    require_all_keys: bool = True,
) -> list[str]:
    """Return a list of problems with *candidate* relative to *reference*.

    With ``require_all_keys`` (the ``register_language`` contract) a candidate
    missing reference keys is an error; set it false to allow a partial dict.
    Empty values, extra keys, and placeholder mismatches are always reported.
    """
    errors: list[str] = []
    missing, extra = compare_keys(reference, candidate)
    if require_all_keys and missing:
        errors.append(f"missing {len(missing)} key(s): {_sample(missing)}")
    if extra:
        errors.append(f"{len(extra)} unknown key(s) not in reference: {_sample(extra)}")
    empties = find_empty_values(candidate)
    if empties:
        errors.append(f"{len(empties)} empty value(s): {_sample(empties)}")
    errors.extend(
        f"placeholder mismatch for {key!r}: reference {sorted(ref)} vs {sorted(cand)}"
        for key, ref, cand in find_placeholder_mismatches(reference, candidate)
    )
    return errors


def validate_merge_payload(
    translations: Mapping[str, Mapping[str, str]],
    *,
    known_languages: set[str] | None = None,
) -> list[str]:
    """Return problems with a ``merge_translations`` payload.

    Every language in the payload should define the same set of new keys (the
    union across languages) with matching placeholders and no empty values. When
    *known_languages* is given, a language not in it is flagged because
    ``merge_translations`` would silently skip it.
    """
    errors: list[str] = []
    if known_languages is not None:
        errors.extend(
            f"language {lang!r} is not registered; merge_translations will skip it"
            for lang in translations
            if lang not in known_languages
        )
    all_keys: set[str] = set().union(*(set(d) for d in translations.values())) \
        if translations else set()
    for lang, lang_dict in translations.items():
        missing = all_keys - set(lang_dict)
        if missing:
            errors.append(
                f"{lang}: missing {len(missing)} key(s) other languages define: "
                f"{_sample(missing)}",
            )
        empties = find_empty_values(lang_dict)
        if empties:
            errors.append(f"{lang}: {len(empties)} empty value(s): {_sample(empties)}")
    errors.extend(_payload_placeholder_errors(translations, all_keys))
    return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload_placeholder_errors(
    translations: Mapping[str, Mapping[str, str]], all_keys: set[str],
) -> list[str]:
    errors: list[str] = []
    for key in sorted(all_keys):
        seen: dict[str, frozenset[str]] = {}
        for lang, lang_dict in translations.items():
            if key in lang_dict:
                seen[lang] = frozenset(extract_placeholders(lang_dict[key]))
        if len({*seen.values()}) > 1:
            detail = ", ".join(f"{lang}={sorted(ph)}" for lang, ph in seen.items())
            errors.append(f"placeholder mismatch for {key!r} across languages: {detail}")
    return errors


def _sample(items: set[str]) -> str:
    ordered = sorted(items)
    shown = ordered[:_MAX_LISTED]
    suffix = f" …(+{len(ordered) - _MAX_LISTED} more)" if len(ordered) > _MAX_LISTED else ""
    return ", ".join(repr(item) for item in shown) + suffix
