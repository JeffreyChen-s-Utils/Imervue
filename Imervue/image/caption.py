"""Generate alt-text / captions for an image with a local vision LLM.

Follows the desktop-pet's local-LLM approach (Ollama on localhost — no cloud,
no API key) so it stays consistent with the project's offline-by-default
design: a vision-capable model (e.g. ``llava``) describes the image. The prompt
and request-payload construction and the response parsing are pure and
unit-tested; the network call reuses the pet client's already-reviewed,
host-validated POST helper rather than opening a second raw socket.
"""
from __future__ import annotations

import base64
from pathlib import Path

DEFAULT_MODEL = "llava"
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_S = 60.0

_PROMPTS = {
    "alt_text": (
        "Describe this image in one concise sentence suitable as alt text. "
        "Reply with only the description."
    ),
    "detailed": (
        "Describe this image in detail: the main subjects, the setting, and "
        "the overall mood."
    ),
    "keywords": (
        "List 5 to 10 comma-separated keywords describing this image. "
        "Reply with only the keywords."
    ),
}
CAPTION_STYLES = tuple(_PROMPTS)


def build_caption_prompt(style: str = "alt_text") -> str:
    """Return the instruction prompt for *style* (falls back to alt-text)."""
    return _PROMPTS.get(style, _PROMPTS["alt_text"])


def build_caption_payload(model: str, image_bytes: bytes, prompt: str) -> dict:
    """Build the Ollama ``/api/generate`` payload for a vision request.

    The image is base64-encoded into the ``images`` array (what Ollama's vision
    models expect); ``stream`` is False so the reply arrives in one envelope.
    """
    return {
        "model": model,
        "prompt": prompt,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
    }


def parse_caption_response(data: object) -> str | None:
    """Pull the caption out of Ollama's ``{"response": ...}`` envelope.

    Accepts ``object`` rather than ``dict`` because the function defensively
    validates its input: a non-dict envelope (or a non-string ``response``)
    yields ``None`` instead of raising. Strips surrounding quotes/whitespace
    (vision models love to wrap the answer in quotes); an empty or missing
    response yields ``None``.
    """
    raw = data.get("response") if isinstance(data, dict) else None
    if not isinstance(raw, str):
        return None
    text = raw.strip().strip('"').strip("'").strip()
    return text or None


def generate_caption(
    image_path: str | Path,
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    style: str = "alt_text",
    timeout: float = DEFAULT_TIMEOUT_S,
) -> str:
    """Caption *image_path* via a local Ollama vision model.

    Raises ``ValueError`` if the model returns nothing, and propagates the
    network / URL errors from the underlying POST so the caller can fall back.
    """
    from Imervue.desktop_pet.llm_dialogue import _request_json
    image_bytes = Path(image_path).read_bytes()
    payload = build_caption_payload(model, image_bytes, build_caption_prompt(style))
    url = base_url.rstrip("/") + "/api/generate"
    caption = parse_caption_response(_request_json(url, payload, timeout=timeout))
    if caption is None:
        raise ValueError("vision model returned an empty caption")
    return caption
