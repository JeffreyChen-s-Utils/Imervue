"""What Pillow raises when a file cannot be opened or decoded as an image."""
from __future__ import annotations

from PIL import Image

#: ``OSError`` covers a missing or unreadable file, ``UnidentifiedImageError``
#: and truncated or corrupt data; ``ValueError`` a bad mode or argument; and
#: ``DecompressionBombError``, which is not an ``OSError``, an image over
#: Pillow's pixel limit. Fuzzing PNG, JPEG, GIF, TIFF, WebP, BMP and ICO files
#: (random byte flips and truncation, open + thumbnail + convert) raised nothing
#: outside this tuple.
IMAGE_READ_ERRORS: tuple[type[Exception], ...] = (
    OSError, ValueError, Image.DecompressionBombError,
)
