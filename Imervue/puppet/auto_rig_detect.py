"""Layer-name detectors for the auto-rigger.

Pure-Python predicates that map a drawable id onto the rig role its
naming convention implies (eye side / state, mouth viseme, head, hair).
:mod:`Imervue.puppet.auto_rig` re-exports the public ones.
"""
from __future__ import annotations

import re


def _normalise(drawable_id: str) -> str:
    """Lower-case + collapse dashes/spaces into underscores so the
    pattern matchers can use one canonical form. Splits camelCase
    boundaries so Cubism-style ``EyeLOpen`` resolves the same as the
    snake-cased ``eye_l_open`` used in most PSDs."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", drawable_id)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    return re.sub(r"[\s\-]+", "_", s.lower())


def detect_eye(drawable_id: str) -> tuple[str, str] | None:
    """Return ``(side, state)`` where side is ``'l'`` or ``'r'`` and
    state is ``'open'`` or ``'close'``. ``None`` when the id isn't an
    eye layer."""
    norm = _normalise(drawable_id)
    if "eye" not in norm:
        return None
    side = _detect_side(norm)
    state = _detect_eye_state(norm)
    if side and state:
        return side, state
    return None


def _detect_side(norm: str) -> str | None:
    """Pull a left/right side out of a normalised id. Matches
    ``_l_``, ``_l$``, ``left``, and short prefix forms like ``l_eye``."""
    if re.search(r"(?:^|_)(l|left)(?:_|$)", norm):
        return "l"
    if re.search(r"(?:^|_)(r|right)(?:_|$)", norm):
        return "r"
    return None


def _detect_eye_state(norm: str) -> str | None:
    if any(t in norm for t in ("open", "opened")):
        return "open"
    if any(t in norm for t in ("close", "closed", "shut")):
        return "close"
    return None


def detect_mouth_variant(drawable_id: str) -> str | None:
    """Return ``'open'`` / ``'close'`` / ``'a'`` / ``'i'`` / ``'u'`` /
    ``'e'`` / ``'o'`` or ``None``. Recognises common variants like
    ``mouth_a`` / ``mouth_open_a`` / ``mouth_aa`` and matches Cubism's
    convention of vowel-tagged mouth shapes."""
    norm = _normalise(drawable_id)
    if "mouth" not in norm and "lip" not in norm:
        return None
    if any(t in norm for t in ("close", "closed", "shut")):
        return "close"
    for vowel in ("a", "i", "u", "e", "o"):
        if re.search(rf"(?:^|_)(?:mouth_)?{vowel}{vowel}?(?:_|$)", norm):
            return vowel
    if "open" in norm:
        return "open"
    return None


def detect_head(drawable_id: str) -> bool:
    norm = _normalise(drawable_id)
    if "forehead" in norm:
        return False
    return any(t in norm for t in ("head", "face"))


def detect_hair(drawable_id: str) -> bool:
    norm = _normalise(drawable_id)
    return any(t in norm for t in ("hair", "bang", "fringe"))
