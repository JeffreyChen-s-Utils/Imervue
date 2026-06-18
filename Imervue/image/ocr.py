"""Optical character recognition via the optional Tesseract backend.

Extract selectable text from screenshots, scans and receipts. The Tesseract
``image_to_data`` TSV output is parsed into structured words (text, confidence,
bounding box) by pure functions that are fully unit-testable without Tesseract
installed. The actual OCR run needs ``pytesseract`` plus the Tesseract binary;
when either is absent the feature degrades gracefully (``ocr_available`` →
False, ``extract_*`` raises :class:`OcrUnavailableError`).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


class OcrUnavailableError(RuntimeError):
    """Raised when an OCR run is requested but Tesseract is not available."""


@dataclass(frozen=True)
class OcrWord:
    """One recognised word with its confidence and bounding box."""

    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block: int
    paragraph: int
    line: int


def parse_tsv(tsv: str, min_confidence: float = 0.0) -> list[OcrWord]:
    """Parse Tesseract ``image_to_data`` TSV into words above *min_confidence*.

    Robust to column order (keyed off the header row). Rows with empty text or
    a confidence of ``-1`` (non-word layout rows) are dropped.
    """
    rows = tsv.splitlines()
    if not rows:
        return []
    index = {name: i for i, name in enumerate(rows[0].split("\t"))}
    if "text" not in index or "conf" not in index:
        return []
    words: list[OcrWord] = []
    for row in rows[1:]:
        word = _row_to_word(row.split("\t"), index, min_confidence)
        if word is not None:
            words.append(word)
    return words


def _row_to_word(cols: list[str], index: dict[str, int],
                 min_confidence: float) -> OcrWord | None:
    if len(cols) <= index["text"]:
        return None
    text = cols[index["text"]].strip()
    if not text:
        return None
    try:
        confidence = float(cols[index["conf"]])
    except (ValueError, IndexError):
        return None
    if confidence < min_confidence:
        return None
    return OcrWord(
        text=text,
        confidence=confidence,
        left=_int_at(cols, index, "left"),
        top=_int_at(cols, index, "top"),
        width=_int_at(cols, index, "width"),
        height=_int_at(cols, index, "height"),
        block=_int_at(cols, index, "block_num"),
        paragraph=_int_at(cols, index, "par_num"),
        line=_int_at(cols, index, "line_num"),
    )


def _int_at(cols: list[str], index: dict[str, int], name: str) -> int:
    try:
        return int(cols[index[name]])
    except (KeyError, ValueError, IndexError):
        return 0


def words_to_text(words: list[OcrWord]) -> str:
    """Join words back into text, one line per Tesseract (block, par, line)."""
    grouped: dict[tuple[int, int, int], list[str]] = {}
    order: list[tuple[int, int, int]] = []
    for word in words:
        key = (word.block, word.paragraph, word.line)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(word.text)
    return "\n".join(" ".join(grouped[key]) for key in order)


@lru_cache(maxsize=1)
def ocr_available() -> bool:
    """Return True when pytesseract and a working Tesseract binary are present."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001 - any failure means OCR is unavailable
        return False
    return True


def extract_words(image, min_confidence: float = 0.0) -> list[OcrWord]:
    """Run Tesseract on *image* (path or PIL image) and return parsed words."""
    if not ocr_available():
        raise OcrUnavailableError("Tesseract OCR is not installed.")
    import pytesseract
    from PIL import Image
    opened = image if isinstance(image, Image.Image) else Image.open(image)
    tsv = pytesseract.image_to_data(opened)
    return parse_tsv(tsv, min_confidence)


def extract_text(image, min_confidence: float = 0.0) -> str:
    """Run OCR and return the recognised text as newline-separated lines."""
    return words_to_text(extract_words(image, min_confidence))
