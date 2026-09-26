"""The translated READMEs and Sphinx pages keep the English structure.

Wording can't be checked mechanically, but structure can: every translation has
the same headings at the same levels, and each section the same number of table
rows, bullets and literal blocks as English. A section, a table row or a bullet
added in English only - or left out of one language - fails here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_README_LANGS = ("de", "es", "fr", "ja", "ko", "pt-BR", "ru", "zh-CN", "zh-TW")
_DOCS_LANGS = ("de", "es", "fr", "ja", "ko", "pt-BR", "ru", "zh-cn", "zh-tw")
_RST_UNDERLINE = re.compile(r"([=\-^~\"*#])\1{2,}")
_MD_HEADING = re.compile(r"(#{1,6}) ")
_MD_BULLET = re.compile(r"\s*[-*] ")
_MD_RULE = re.compile(r"\|\s*:?-")
_RST_ROW = re.compile(r"\s*\* - ")
_RST_BULLET = re.compile(r"\s*[-*] (?!-)")


def _read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def markdown_shape(lines: list[str]) -> list[tuple[int, int, int]]:
    """``(heading level, bullets, table rows)`` per section; fenced code is skipped."""
    shape = [[0, 0, 0]]
    in_code = False
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        heading = _MD_HEADING.match(line)
        if heading:
            shape.append([len(heading.group(1)), 0, 0])
        elif _MD_BULLET.match(line):
            shape[-1][1] += 1
        elif line.startswith("|") and not _MD_RULE.match(line):
            shape[-1][2] += 1
    return [tuple(section) for section in shape]


def _is_underline(line: str) -> bool:
    return bool(_RST_UNDERLINE.fullmatch(line.strip()))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _body_counts(body: list[str]) -> tuple[int, int, int]:
    """List-table rows, bullets and literal blocks (``::``) in one section's lines."""
    rows = bullets = literals = 0
    table_indent = None   # the indent of the list-table directive we are inside
    for line in body:
        stripped = line.strip()
        if table_indent is not None and stripped and _indent(line) <= table_indent:
            table_indent = None
        if stripped.startswith(".. list-table::"):
            table_indent = _indent(line)
            continue
        if table_indent is not None:
            rows += bool(_RST_ROW.match(line))
            continue
        if stripped.startswith(".. "):
            continue   # another directive: its "::" is not a literal block
        bullets += bool(_RST_BULLET.match(line))
        literals += line.rstrip().endswith("::")
    return rows, bullets, literals


def rst_shape(lines: list[str]) -> list[tuple[str, int, int, int]]:
    """``(underline char, list-table rows, bullets, literal blocks)`` per section."""
    starts = [i for i in range(1, len(lines))
              if _is_underline(lines[i]) and lines[i - 1].strip() and not _is_underline(lines[i - 1])]
    shape = []
    for n, start in enumerate(starts):
        end = starts[n + 1] - 1 if n + 1 < len(starts) else len(lines)
        shape.append((lines[start].strip()[0], *_body_counts(lines[start + 1:end])))
    return shape


def test_markdown_shape_counts_headings_bullets_and_rows():
    lines = ["intro", "## A", "- one", "* two", "| k | v |", "|---|---|", "| x | y |",
             "```", "- not counted", "```", "### B", "text"]
    assert markdown_shape(lines) == [(0, 0, 0), (2, 2, 2), (3, 0, 0)]


def test_rst_shape_counts_rows_bullets_and_literals():
    lines = ["Title", "=====", "", ".. list-table::", "", "   * - a", "     - b", "",
             "- bullet", "", "Sub", "^^^", "", "Example::", "", "   code"]
    assert rst_shape(lines) == [("=", 1, 1, 0), ("^", 0, 0, 1)]


@pytest.mark.parametrize("lang", _README_LANGS)
def test_translated_readme_has_the_english_structure(lang):
    english = markdown_shape(_read(_ROOT / "README.md"))
    translated = markdown_shape(_read(_ROOT / "README" / f"README_{lang}.md"))
    assert [s[0] for s in translated] == [s[0] for s in english], "headings differ"
    differing = [n for n, (a, b) in enumerate(zip(english, translated, strict=True)) if a != b]
    assert differing == [], f"sections {differing} differ in bullets or table rows"


@pytest.mark.parametrize("lang", ("zh-CN", "zh-TW"))
def test_translated_puppet_guide_has_the_english_structure(lang):
    english = markdown_shape(_read(_ROOT / "puppet_guide.md"))
    translated = markdown_shape(_read(_ROOT / f"puppet_guide.{lang}.md"))
    assert [s[0] for s in translated] == [s[0] for s in english], "headings differ"
    differing = [n for n, (a, b) in enumerate(zip(english, translated, strict=True)) if a != b]
    assert differing == [], f"sections {differing} differ in bullets or table rows"


@pytest.mark.parametrize("lang", _DOCS_LANGS)
def test_translated_docs_have_the_english_structure(lang):
    english = rst_shape(_read(_ROOT / "docs" / "en" / "index.rst"))
    translated = rst_shape(_read(_ROOT / "docs" / lang / "index.rst"))
    assert [s[0] for s in translated] == [s[0] for s in english], "headings differ"
    differing = [n for n, (a, b) in enumerate(zip(english, translated, strict=True)) if a != b]
    assert differing == [], f"sections {differing} differ in table rows, bullets or literal blocks"
