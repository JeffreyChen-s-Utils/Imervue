"""Tests for the plain-Python CLIP BPE tokenizer.

The vocabulary and merges below are the subset of CLIP ViT-B/32's own files that
these phrases use, in their original rank order, and the expected ids are what
the reference ``tokenizers`` implementation returns for them — so the tokenizer
is checked against the real model without downloading it.
"""
from __future__ import annotations

import json

import pytest

from Imervue.library.clip_tokenizer import (
    CONTEXT_LENGTH,
    END_OF_TEXT,
    START_OF_TEXT,
    ClipTokenizer,
    byte_to_unicode,
    normalise,
    pieces,
    split_pieces,
)

_VOCAB = {'!!</w>': 748,
 "'s</w>": 568,
 "'t</w>": 713,
 '0</w>': 271,
 '2</w>': 273,
 '4</w>': 275,
 '<|endoftext|>': 49407,
 '<|startoftext|>': 49406,
 '_</w>': 318,
 'a</w>': 320,
 'at</w>': 536,
 'cafÃ©</w>': 15304,
 'cat</w>': 2368,
 'cr': 1075,
 'don</w>': 847,
 'golden</w>': 3878,
 'in</w>': 530,
 'it</w>': 585,
 'me</w>': 614,
 'neon</w>': 13919,
 'night</w>': 930,
 'of</w>': 539,
 'photo</w>': 1125,
 'retriever</w>': 28394,
 'score</w>': 4431,
 'snow</w>': 2583,
 'stop</w>': 1691,
 'street</w>': 2012,
 'under</w>': 1798,
 'x</w>': 343,
 '¬': 105,
 '¯': 107,
 'Â²</w>': 41175,
 'Ã¨': 12138,
 'ãĤ¿': 34941,
 'ãĥ': 2429,
 'ãĥ¼</w>': 30391,
 'äº': 21078,
 'æĿ±': 48338}

_MERGES = ['r e',
 's t',
 'o r',
 'o n</w>',
 'e r</w>',
 'i n</w>',
 't o</w>',
 'a t</w>',
 'o f</w>',
 'r i',
 'n e',
 'd e',
 'o l',
 "' s</w>",
 'u n',
 'n o',
 'g h',
 'i t</w>',
 'h o',
 'm e</w>',
 'gh t</w>',
 's c',
 'v er</w>',
 'no w</w>',
 'n i',
 'a f',
 "' t</w>",
 '! !</w>',
 'd er</w>',
 'p ho',
 'd on</w>',
 'e t</w>',
 't ri',
 'st o',
 'ni ght</w>',
 'c r',
 'st re',
 'pho to</w>',
 'de n</w>',
 'e ver</w>',
 'or e</w>',
 'g ol',
 'sto p</w>',
 'un der</w>',
 'stre et</w>',
 'c at</w>',
 'ã ĥ',
 's now</w>',
 'c af',
 'gol den</w>',
 'ã Ĥ',
 'Ã ©</w>',
 'sc ore</w>',
 'Ã ¨',
 'ne on</w>',
 'caf Ã©</w>',
 're tri',
 'ä º',
 'æ Ŀ',
 'retri ever</w>',
 'ãĥ ¼</w>',
 'ãĤ ¿',
 'Â ²</w>',
 'æĿ ±']

_EXPECTED = {'a photo of a cat': [49406, 320, 1125, 539, 320, 2368, 49407],
 'Golden Retriever in SNOW': [49406, 3878, 28394, 530, 2583, 49407],
 'neon street at night!!': [49406, 13919, 2012, 536, 930, 748, 49407],
 "don't STOP": [49406, 847, 713, 1691, 49407],
 'café  crème': [49406, 15304, 1075, 12138, 614, 49407],
 '東京タワー': [49406, 48338, 21078, 105, 34941, 2429, 107, 30391, 49407],
 'x²': [49406, 343, 41175, 49407],
 "it's 2024": [49406, 585, 568, 273, 271, 273, 275, 49407],
 'under_score': [49406, 1798, 318, 4431, 49407]}


@pytest.fixture
def tokenizer(tmp_path):
    vocab = tmp_path / "vocab.json"
    merges = tmp_path / "merges.txt"
    vocab.write_text(json.dumps(_VOCAB), encoding="utf-8")
    merges.write_text("#version: 0.2\n" + "\n".join(_MERGES) + "\n", encoding="utf-8")
    return ClipTokenizer.from_files(vocab, merges)


@pytest.mark.parametrize(("text", "ids"), list(_EXPECTED.items()))
def test_encode_matches_the_reference_tokenizer(tokenizer, text, ids):
    assert tokenizer.encode(text) == ids


def test_the_version_line_is_not_a_merge(tokenizer):
    assert ("#version:", "0.2") not in tokenizer._ranks  # noqa: SLF001
    assert len(tokenizer._ranks) == len(_MERGES)  # noqa: SLF001


def test_encode_wraps_in_start_and_end(tokenizer):
    ids = tokenizer.encode("")
    assert ids == [tokenizer.start_id, tokenizer.end_id] == [49406, 49407]


def test_encode_cuts_a_long_text_to_the_context_length(tokenizer):
    ids = tokenizer.encode("a " * 200)
    assert len(ids) == CONTEXT_LENGTH
    assert ids[0] == tokenizer.start_id and ids[-1] == tokenizer.end_id
    assert tokenizer.tokens("a " * 200) == [320] * 200


def test_a_symbol_missing_from_the_vocabulary_becomes_the_end_token(tokenizer):
    # No merge joins them, so each of "z", "z", "z</w>" is looked up alone.
    assert tokenizer.tokens("zzz") == [tokenizer.end_id] * 3


def test_markers_count_wherever_they_appear(tokenizer):
    assert tokenizer.tokens(f"cat{END_OF_TEXT}a") == [2368, 49407, 320]


def test_byte_table_covers_every_byte_with_distinct_printable_symbols():
    table = byte_to_unicode()
    assert sorted(table) == list(range(256))
    assert len(set(table.values())) == 256
    assert table[ord("a")] == "a"
    assert all(not ch.isspace() for ch in table.values())


@pytest.mark.parametrize(("text", "normalised"), [
    ("  Golden\tRetriever\n", "golden retriever"),
    ("e\u0301cole", "\u00e9cole"),                 # NFC composes the accent
    ("A\u3000B", "a b"),                          # ideographic space is whitespace
])
def test_normalise(text, normalised):
    assert normalise(text) == normalised


@pytest.mark.parametrize(("text", "expected"), [
    ("don't stop", ["don", "'t", "stop"]),
    ("it's 2024", ["it", "'s", "2", "0", "2", "4"]),
    ("night!!", ["night", "!!"]),
    ("under_score", ["under", "_", "score"]),
    ("x\u00b2", ["x", "\u00b2"]),                  # superscript two is a numeral
    ("\u6771\u4eac\u30bf", ["\u6771\u4eac\u30bf"]),     # CJK are letters
    ("!'s", ["!'", "s"]),                         # a symbol run swallows the apostrophe
    ("'ll'd", ["'ll", "'d"]),
])
def test_split_pieces(text, expected):
    assert list(split_pieces(text)) == expected


def test_pieces_keep_the_markers_whole_and_normalise_the_rest():
    assert list(pieces(f"#{START_OF_TEXT}Cat {END_OF_TEXT}")) == [
        "#", START_OF_TEXT, "cat", END_OF_TEXT]


def test_bpe_merges_by_rank_not_by_position(tmp_path):
    vocab = {"a": 0, "b": 1, "c</w>": 2, "ab": 3, "bc</w>": 4, "abc</w>": 5, "a</w>": 6,
             START_OF_TEXT: 7, END_OF_TEXT: 8}
    (tmp_path / "v.json").write_text(json.dumps(vocab), encoding="utf-8")
    # "b c</w>" outranks "a b": the right pair merges first, then nothing joins "a".
    (tmp_path / "m.txt").write_text("b c</w>\na b\n", encoding="utf-8")
    tok = ClipTokenizer.from_files(tmp_path / "v.json", tmp_path / "m.txt")
    assert tok.tokens("abc") == [0, 4]
