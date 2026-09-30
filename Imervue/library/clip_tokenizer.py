"""CLIP's byte-level BPE tokenizer in plain Python.

Turns a search phrase into the token ids the CLIP text encoder expects, from
the model's own ``vocab.json`` and ``merges.txt`` — the same steps as the
reference ``tokenizer.json``: NFC, whitespace runs collapsed, lower case; split
into contractions (``'s`` ``'t`` ``'re`` ``'ve`` ``'m`` ``'ll`` ``'d``), runs of
letters, single numerals and runs of other symbols; each piece byte-encoded,
merged by rank with ``</w>`` closing the word, and wrapped in the start and end
tokens. No third-party package is needed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

START_OF_TEXT = "<|startoftext|>"
END_OF_TEXT = "<|endoftext|>"
#: Positions the text encoder has, the start and end tokens included.
CONTEXT_LENGTH = 77
_END_OF_WORD = "</w>"
_CONTRACTION = re.compile(r"'(?:s|t|re|ve|m|ll|d)")
_WHITESPACE = re.compile(r"\s+")
_SPECIAL = (START_OF_TEXT, END_OF_TEXT)
# The start and end markers count wherever they appear, before any other step.
_SPECIAL_SPLIT = re.compile("(" + "|".join(re.escape(s) for s in _SPECIAL) + ")")


@lru_cache(maxsize=1)
def byte_to_unicode() -> dict[int, str]:
    """GPT-2's byte → printable-character table, so every byte is one BPE symbol."""
    printable = [*range(ord("!"), ord("~") + 1), *range(ord("¡"), ord("¬") + 1),
                 *range(ord("®"), ord("ÿ") + 1)]
    chars = list(printable)
    extra = 0
    for byte in range(256):
        if byte not in printable:
            printable.append(byte)
            chars.append(256 + extra)
            extra += 1
    return {byte: chr(code) for byte, code in zip(printable, chars, strict=True)}


def normalise(text: str) -> str:
    """NFC, every whitespace run as one space, trimmed, lower case."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip().lower()


def _kind(char: str) -> str:
    """``L`` for a letter, ``N`` for a numeral, ``S`` for a space, ``O`` for anything else."""
    if char.isspace():
        return "S"
    major = unicodedata.category(char)[0]
    return major if major in "LN" else "O"


def _piece_end(text: str, start: int) -> int:
    """Where the piece starting at *start* ends: a letter run, one numeral, or a symbol run."""
    kind = _kind(text[start])
    if kind == "N":
        return start + 1
    end = start + 1
    while end < len(text) and _kind(text[end]) == kind:
        end += 1
    return end


def split_pieces(text: str) -> Iterator[str]:
    """CLIP's pre-tokenizer: the pieces of normalised *text*, spaces dropped."""
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        match = _CONTRACTION.match(text, index)
        end = match.end() if match else _piece_end(text, index)
        yield text[index:end]
        index = end


def pieces(text: str) -> Iterator[str]:
    """The pieces of raw *text*: start / end markers kept whole, the rest normalised and split."""
    for segment in _SPECIAL_SPLIT.split(text):
        if segment in _SPECIAL:
            yield segment
        elif segment:
            yield from split_pieces(normalise(segment))


class ClipTokenizer:
    """Encode text for CLIP from its ``vocab.json`` (token → id) and ``merges.txt``."""

    def __init__(self, vocab: dict[str, int], merges: list[tuple[str, str]]) -> None:
        self._vocab = vocab
        self._ranks = {pair: rank for rank, pair in enumerate(merges)}
        self._bpe = lru_cache(maxsize=4096)(self._bpe_uncached)
        self.start_id = vocab[START_OF_TEXT]
        self.end_id = vocab[END_OF_TEXT]

    @classmethod
    def from_files(cls, vocab_path: str | Path, merges_path: str | Path) -> ClipTokenizer:
        """Load the tokenizer; ``merges.txt`` may open with a ``#version`` line."""
        vocab = json.loads(Path(vocab_path).read_text(encoding="utf-8"))
        merges = []
        for line in Path(merges_path).read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and not line.startswith("#version"):
                merges.append((parts[0], parts[1]))
        return cls(vocab, merges)

    def _bpe_uncached(self, piece: str) -> tuple[str, ...]:
        """Merge the byte symbols of one piece by rank, lowest first."""
        if piece in _SPECIAL:
            return (piece,)
        symbols = [byte_to_unicode()[b] for b in piece.encode("utf-8")]
        symbols[-1] += _END_OF_WORD
        while len(symbols) > 1:
            pairs = {(a, b) for a, b in zip(symbols, symbols[1:], strict=False)}
            best = min(pairs, key=lambda pair: self._ranks.get(pair, len(self._ranks)))
            if best not in self._ranks:
                break
            symbols = _merge(symbols, best)
        return tuple(symbols)

    def tokens(self, text: str) -> list[int]:
        """The ids of *text*'s tokens, without the start and end tokens."""
        ids: list[int] = []
        for piece in pieces(text):
            ids.extend(self._vocab.get(symbol, self.end_id) for symbol in self._bpe(piece))
        return ids

    def encode(self, text: str) -> list[int]:
        """Start token, *text*'s tokens cut to fit :data:`CONTEXT_LENGTH`, end token."""
        return [self.start_id, *self.tokens(text)[:CONTEXT_LENGTH - 2], self.end_id]


def _merge(symbols: list[str], pair: tuple[str, str]) -> list[str]:
    """Join every adjacent occurrence of *pair*, left to right."""
    merged: list[str] = []
    index = 0
    while index < len(symbols):
        if index + 1 < len(symbols) and (symbols[index], symbols[index + 1]) == pair:
            merged.append(symbols[index] + symbols[index + 1])
            index += 2
        else:
            merged.append(symbols[index])
            index += 1
    return merged
