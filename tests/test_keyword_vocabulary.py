"""Tests for controlled-vocabulary keyword expansion."""
from __future__ import annotations

from Imervue.library.keyword_vocabulary import (
    VocabNode,
    expand_keywords,
    parse_structured_keywords,
    serialize_structured_keywords,
    suggest_completions,
)

_SAMPLE = "animal\n\tdog\n\t\tLabrador {lab} {lab retriever}\n\t\tPoodle\n\tcat\n"


# ---------------------------------------------------------------------------
# parse_structured_keywords
# ---------------------------------------------------------------------------


def test_parse_builds_hierarchy():
    vocab = parse_structured_keywords(_SAMPLE)
    assert len(vocab) == 1
    animal = vocab[0]
    assert animal.name == "animal"
    assert [c.name for c in animal.children] == ["dog", "cat"]
    dog = animal.children[0]
    assert [c.name for c in dog.children] == ["Labrador", "Poodle"]


def test_parse_extracts_synonyms():
    lab = parse_structured_keywords(_SAMPLE)[0].children[0].children[0]
    assert lab.name == "Labrador"
    assert lab.synonyms == ("lab", "lab retriever")


def test_parse_skips_blank_and_nameless_lines():
    assert parse_structured_keywords("\n\n  {orphan}\nreal\n") == [VocabNode("real")]


def test_parse_empty_text():
    assert parse_structured_keywords("") == []


# ---------------------------------------------------------------------------
# round-trip
# ---------------------------------------------------------------------------


def test_serialize_round_trips():
    vocab = parse_structured_keywords(_SAMPLE)
    assert parse_structured_keywords(serialize_structured_keywords(vocab)) == vocab


def test_serialize_indents_and_braces():
    text = serialize_structured_keywords([
        VocabNode("dog", (VocabNode("Labrador", (), ("lab",)),)),
    ])
    assert text == "dog\n\tLabrador {lab}"


# ---------------------------------------------------------------------------
# expand_keywords
# ---------------------------------------------------------------------------


def test_expand_leaf_to_ancestors_and_synonyms():
    vocab = parse_structured_keywords(_SAMPLE)
    assert expand_keywords(["Labrador"], vocab) == [
        "Labrador", "lab", "lab retriever", "dog", "animal"]


def test_expand_matches_a_synonym():
    vocab = parse_structured_keywords(_SAMPLE)
    # "lab" is a synonym of Labrador -> resolves to the same chain.
    assert expand_keywords(["lab"], vocab) == [
        "Labrador", "lab", "lab retriever", "dog", "animal"]


def test_expand_is_case_insensitive():
    vocab = parse_structured_keywords(_SAMPLE)
    assert expand_keywords(["POODLE"], vocab) == ["Poodle", "dog", "animal"]


def test_expand_unknown_leaf_is_kept():
    vocab = parse_structured_keywords(_SAMPLE)
    assert expand_keywords(["dragon"], vocab) == ["dragon"]


def test_expand_dedupes_shared_ancestors():
    vocab = parse_structured_keywords(_SAMPLE)
    result = expand_keywords(["Labrador", "Poodle"], vocab)
    # "dog" and "animal" appear once despite both leaves sharing them.
    assert result.count("dog") == 1
    assert result.count("animal") == 1
    assert result == ["Labrador", "lab", "lab retriever", "dog", "animal", "Poodle"]


# ---------------------------------------------------------------------------
# suggest_completions
# ---------------------------------------------------------------------------


def test_suggest_completions_matches_names_and_synonyms():
    vocab = parse_structured_keywords(_SAMPLE)
    # Case-insensitive: "Labrador" matches "la" too; sorted by code point so
    # the capitalised name precedes the lowercase synonyms.
    assert suggest_completions("la", vocab) == ["Labrador", "lab", "lab retriever"]


def test_suggest_completions_case_insensitive_sorted():
    vocab = parse_structured_keywords(_SAMPLE)
    assert suggest_completions("", vocab) == sorted(
        ["animal", "dog", "Labrador", "lab", "lab retriever", "Poodle", "cat"])


def test_suggest_completions_no_match():
    assert suggest_completions("xyz", parse_structured_keywords(_SAMPLE)) == []
