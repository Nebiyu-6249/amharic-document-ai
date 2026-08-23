"""Upload validation and sanitisation.

Implements controls C-27 (content-based allowlist, re-encode, reject SVG), C-28
(dimension and decompression-bomb limits) and C-29 (strip all EXIF).

This is the highest-risk code in the application: it is the first thing that touches an
attacker-supplied file (threat T-03). The order of operations matters and is not
negotiable:

    1. size check      -- before anything is read into memory
    2. magic bytes     -- before the decoder is invoked
    3. bomb guard      -- before pixels are materialised
    4. decode          -- inside a guarded Pillow context
    5. re-encode       -- destroys any polyglot payload and all metadata

Re-encoding is what makes a polyglot harmless. A file that is simultaneously a valid
JPEG and a valid HTML document stops being valid HTML once it has been decoded to
pixels and written back out by our own encoder.
"""

from __future__ import annotations

import hashlib
import io
import secrets
from dataclasses import dataclass
from typing import Final

from PIL import Image, UnidentifiedImageError

#: Magic-byte signatures for the formats we accept. Extensions are never consulted.
_MAGIC: Final[tuple[tuple[bytes, str], ...]] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),  # confirmed by the WEBP tag at offset 8
)

#: Rejected outright (C-27). SVG is XML with script execution, not an image format we
#: can make safe by re-encoding.
_FORBIDDEN_MARKERS: Final[tuple[bytes, ...]] = (b"<svg", b"<?xml", b"<!DOCTYPE", b"<html")

#: Formats Pillow is permitted to decode. Anything else is refused even if Pillow
#: recognises it, so an obscure decoder CVE is not reachable from an upload.
_ALLOWED_PIL_FORMATS: Final[frozenset[str]] = frozenset({"JPEG", "PNG", "WEBP"})


class UploadRejectedError(Exception):
    """An upload failed validation. The message is safe to log, never to echo verbatim."""

    def __init__(self, reason: str, code: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


@dataclass(frozen=True)
class SanitisedImage:
    blob_key: str
    content_type: str
    data: bytes
    width: int
    height: int
    sha256: str


def sniff_content_type(head: bytes) -> str | None:
    """Identify the format from magic bytes alone."""
    for signature, media_type in _MAGIC:
        if head.startswith(signature):
            if media_type == "image/webp":
                if len(head) >= 12 and head[8:12] == b"WEBP":
                    return media_type
                continue
            return media_type
    return None


def new_blob_key() -> str:
    """A non-guessable storage key, unrelated to the uploaded filename (C-30)."""
    return secrets.token_urlsafe(32)


def validate_and_sanitise(
    raw: bytes,
    *,
    max_bytes: int,
    max_pixels: int,
    max_dimension: int,
    allowed_types: tuple[str, ...],
) -> SanitisedImage:
    """Validate, decode, strip metadata and re-encode an uploaded image.

    Returns a wholly new byte string produced by our own encoder. The original bytes
    are never persisted as-is.
    """
    if not raw:
        raise UploadRejectedError("empty upload", "empty")
    if len(raw) > max_bytes:
        raise UploadRejectedError(f"upload exceeds {max_bytes} bytes", "too_large")

    head = raw[:64]
    lowered = head.lower()
    for marker in _FORBIDDEN_MARKERS:
        if marker.lower() in lowered:
            raise UploadRejectedError("markup-based formats are not accepted", "forbidden_format")

    content_type = sniff_content_type(head)
    if content_type is None:
        raise UploadRejectedError("unrecognised image format", "unknown_format")
    if content_type not in allowed_types:
        raise UploadRejectedError(f"{content_type} is not an accepted type", "type_not_allowed")

    # Bound Pillow's own bomb detector to our configured limit. Pillow raises
    # DecompressionBombError above 2x this value and warns above 1x; we treat any
    # breach as fatal rather than as a warning.
    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format not in _ALLOWED_PIL_FORMATS:
                raise UploadRejectedError(
                    f"decoder {probe.format} not permitted", "decoder_not_allowed"
                )
            width, height = probe.size
            if width > max_dimension or height > max_dimension:
                raise UploadRejectedError(
                    f"image exceeds {max_dimension}px on a side", "dimensions_too_large"
                )
            if width * height > max_pixels:
                raise UploadRejectedError("image pixel count exceeds limit", "too_many_pixels")
            probe.load()
            # Convert away from palette/alpha modes so the re-encode is predictable.
            converted = probe.convert("RGB")
    except UploadRejectedError:
        raise
    except Image.DecompressionBombError as exc:
        raise UploadRejectedError("decompression bomb detected", "decompression_bomb") from exc
    except UnidentifiedImageError as exc:
        raise UploadRejectedError("file is not a decodable image", "undecodable") from exc
    except OSError as exc:
        # Truncated or corrupt files land here. Do not leak the decoder's message.
        raise UploadRejectedError("image could not be decoded", "undecodable") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit

    # Re-encode from pixels. This is the step that destroys polyglot payloads and, by
    # constructing a fresh image object, drops every EXIF/XMP/ICC block including GPS
    # (C-29) -- Pillow only writes metadata it is explicitly given.
    out = io.BytesIO()
    # frombytes builds a new image whose .info is empty. That matters: Pillow's JPEG
    # encoder falls back to im.info["exif"] when no exif= is passed, so saving the
    # decoded image directly could carry metadata straight back out.
    clean = Image.frombytes(converted.mode, converted.size, converted.tobytes())
    clean.save(out, format="JPEG", quality=92, optimize=True)
    data = out.getvalue()

    return SanitisedImage(
        blob_key=new_blob_key(),
        content_type="image/jpeg",
        data=data,
        width=converted.width,
        height=converted.height,
        sha256=hashlib.sha256(data).hexdigest(),
    )
