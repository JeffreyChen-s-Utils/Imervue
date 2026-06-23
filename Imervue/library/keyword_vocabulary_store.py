"""Settings-backed storage for the controlled keyword vocabulary.

The vocabulary itself is the tab-indented structured-keyword text parsed by
:mod:`keyword_vocabulary`; this thin layer persists that text in the user
settings and exposes loading + a one-call "expand these keywords through the
stored vocabulary" used by the keyword editor. Settings access is lazy so
importing this module never drags in the settings singleton.
"""
from __future__ import annotations

from collections.abc import Iterable

from Imervue.library.keyword_vocabulary import (
    VocabNode,
    expand_keywords,
    parse_structured_keywords,
)

_VOCAB_KEY = "keyword_vocabulary"


def get_vocabulary_text() -> str:
    """Return the stored vocabulary text (empty string when unset / invalid)."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    text = user_setting_dict.get(_VOCAB_KEY, "")
    return text if isinstance(text, str) else ""


def set_vocabulary_text(text: str) -> None:
    """Store the vocabulary text in the user settings dict."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict[_VOCAB_KEY] = str(text)


def load_vocabulary() -> list[VocabNode]:
    """Parse the stored vocabulary text into a :class:`VocabNode` forest."""
    return parse_structured_keywords(get_vocabulary_text())


def expand_with_stored_vocabulary(keywords: Iterable[str]) -> list[str]:
    """Expand *keywords* through the stored vocabulary (leaf -> ancestors +
    synonyms). With no vocabulary configured the keywords are returned as-is
    (de-duplicated, order-stable)."""
    return expand_keywords(keywords, load_vocabulary())
