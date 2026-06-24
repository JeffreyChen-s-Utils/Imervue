"""Code replacements — snippet expansion for captions and keywords.

Photo Mechanic's *Code Replacements* (a.k.a. hot codes): type a short code after
a delimiter (``\\wch``) and it expands to a longer canned phrase, which may in
turn carry ``{variable}`` placeholders filled from the photo's metadata. This
lets a photographer keep a small ``code -> phrase`` map and stamp consistent
captions across a shoot without retyping boilerplate.

Expansion runs in two stages: codes are substituted (bounded passes so a code
that references itself cannot loop forever), then ``{variable}`` tokens are
filled from the metadata. Unknown codes and unknown variables are left verbatim.

Pure string processing — no I/O, no optional deps.
"""
from __future__ import annotations

import re

_CODE_PASS_LIMIT = 10
_VARIABLE_RE = re.compile(r"\{(\w+)\}")


def expand_codes(
    text: str,
    codes: dict[str, str],
    meta: dict[str, object] | None = None,
    *,
    delimiter: str = "\\",
) -> str:
    """Expand ``{delimiter}code`` snippets and ``{variable}`` tokens in *text*.

    *codes* maps a bare code name to its replacement phrase; *meta* supplies the
    values for ``{variable}`` placeholders. Codes whose name is unknown and
    variables absent from *meta* are left exactly as written. *delimiter* is the
    single character that introduces a code (Photo Mechanic uses a backslash).
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    if not isinstance(codes, dict):
        raise TypeError(f"codes must be a dict, got {type(codes).__name__}")
    resolved = _substitute_codes(text, codes, delimiter)
    return _substitute_variables(resolved, meta or {})


def _substitute_codes(text: str, codes: dict[str, str], delimiter: str) -> str:
    if not delimiter:
        raise ValueError("delimiter must be a non-empty string")
    pattern = re.compile(re.escape(delimiter) + r"(\w+)")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return codes.get(name, match.group(0))

    result = text
    for _ in range(_CODE_PASS_LIMIT):
        expanded = pattern.sub(replace, result)
        if expanded == result:
            break
        result = expanded
    return result


def _substitute_variables(text: str, meta: dict[str, object]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(meta[key]) if key in meta else match.group(0)

    return _VARIABLE_RE.sub(replace, text)
