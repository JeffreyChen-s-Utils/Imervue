"""Controlled-vocabulary keyword expansion (Photo-Mechanic-style).

A controlled vocabulary is a hierarchy of keywords with synonyms: applying a
leaf keyword should also apply its ancestors and its synonyms, so "Labrador"
expands to ``["Labrador", "lab", "dog", "animal"]``. This lifts the flat,
manual keywording the editor does today into a DAM-grade tool that improves
search recall through the existing ``tags_all`` / ``tags_any`` rules.

The text format is tab-indented (one tab per level); a node's synonyms follow
its name in braces::

    animal
    \tdog
    \t\tLabrador {lab} {lab retriever}

Pure dict/list/string work — no Qt, no I/O.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

_SYNONYM_RE = re.compile(r"\{([^}]*)\}")
_INDENT = "\t"


@dataclass(frozen=True)
class VocabNode:
    """One keyword in the vocabulary: a name, ordered children and synonyms."""

    name: str
    children: tuple[VocabNode, ...] = ()
    synonyms: tuple[str, ...] = ()


@dataclass
class _Builder:
    name: str
    synonyms: list[str]
    children: list[_Builder] = field(default_factory=list)

    def freeze(self) -> VocabNode:
        return VocabNode(
            name=self.name,
            children=tuple(child.freeze() for child in self.children),
            synonyms=tuple(self.synonyms),
        )


def _parse_line(stripped: str) -> tuple[str, list[str]]:
    synonyms = [s.strip() for s in _SYNONYM_RE.findall(stripped) if s.strip()]
    name = _SYNONYM_RE.sub("", stripped).strip()
    return name, synonyms


def parse_structured_keywords(text: str) -> list[VocabNode]:
    """Parse tab-indented vocabulary *text* into a forest of :class:`VocabNode`.

    One tab per level; ``{synonym}`` tokens follow the name. Blank lines and
    lines whose name is empty are skipped.
    """
    roots: list[_Builder] = []
    stack: list[tuple[int, _Builder]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        depth = len(raw) - len(raw.lstrip(_INDENT))
        name, synonyms = _parse_line(raw.strip())
        if not name:
            continue
        node = _Builder(name=name, synonyms=synonyms)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)
        stack.append((depth, node))
    return [builder.freeze() for builder in roots]


def serialize_structured_keywords(vocab: Iterable[VocabNode]) -> str:
    """Serialise a vocabulary forest back to tab-indented text (round-trips)."""
    lines: list[str] = []

    def emit(node: VocabNode, depth: int) -> None:
        synonyms = "".join(f" {{{syn}}}" for syn in node.synonyms)
        lines.append(f"{_INDENT * depth}{node.name}{synonyms}")
        for child in node.children:
            emit(child, depth + 1)

    for root in vocab:
        emit(root, 0)
    return "\n".join(lines)


def _iter_paths(
    nodes: Iterable[VocabNode], prefix: tuple[VocabNode, ...] = (),
) -> Iterator[tuple[VocabNode, ...]]:
    for node in nodes:
        path = (*prefix, node)
        yield path
        yield from _iter_paths(node.children, path)


def _matches(node: VocabNode, needle: str) -> bool:
    folded = needle.casefold()
    return node.name.casefold() == folded or any(
        syn.casefold() == folded for syn in node.synonyms
    )


def _find_path(
    vocab: Iterable[VocabNode], leaf: str,
) -> tuple[VocabNode, ...] | None:
    return next(
        (path for path in _iter_paths(vocab) if _matches(path[-1], leaf)),
        None,
    )


def expand_keywords(leaves: Iterable[str], vocab: Iterable[VocabNode]) -> list[str]:
    """Expand each leaf to itself, its synonyms and its ancestors' names.

    Matching is case-insensitive against names and synonyms; the first match in
    a depth-first walk wins. An unknown leaf is kept as given. The result is
    order-stable and de-duplicated (case-insensitively).
    """
    vocab = list(vocab)
    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            out.append(value)

    for leaf in leaves:
        path = _find_path(vocab, leaf)
        if path is None:
            add(leaf)
            continue
        node = path[-1]
        add(node.name)
        for syn in node.synonyms:
            add(syn)
        for ancestor in reversed(path[:-1]):
            add(ancestor.name)
    return out


def suggest_completions(prefix: str, vocab: Iterable[VocabNode]) -> list[str]:
    """Return vocabulary names and synonyms starting with *prefix* (sorted)."""
    folded = prefix.casefold()
    found: set[str] = set()
    for path in _iter_paths(vocab):
        node = path[-1]
        for term in (node.name, *node.synonyms):
            if term.casefold().startswith(folded):
                found.add(term)
    return sorted(found)
