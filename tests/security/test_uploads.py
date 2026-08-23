"""Upload validation controls C-27, C-28, C-29 against threat T-03.

Every test here is written so that it FAILS if the corresponding control is removed --
that is the standard this project holds security controls to.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from PIL.ExifTags import GPS
from PIL.ExifTags import Base as ExifBase
from PIL.TiffImagePlugin import IFDRational as R

from adai.security.uploads import UploadRejectedError, sniff_content_type, validate_and_sanitise

LIMITS = {
    "max_bytes": 15 * 1024 * 1024,
    "max_pixels": 40_000_000,
    "max_dimension": 12_000,
    "allowed_types": ("image/jpeg", "image/png", "image/webp"),
}


def _sanitise(data: bytes, **overrides: object):
    return validate_and_sanitise(data, **{**LIMITS, **overrides})  # type: ignore[arg-type]


def test_clean_jpeg_is_accepted(jpeg_bytes: bytes) -> None:
    result = _sanitise(jpeg_bytes)
    assert result.content_type == "image/jpeg"
    assert result.width == 64 and result.height == 48
    assert len(result.sha256) == 64


def test_png_is_reencoded_to_jpeg(png_bytes: bytes) -> None:
    assert _sanitise(png_bytes).content_type == "image/jpeg"


# --- C-27: content-based allowlist, SVG rejected -----------------------------------


def test_svg_is_rejected() -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(UploadRejectedError) as exc:
        _sanitise(svg)
    assert exc.value.code == "forbidden_format"


def test_html_masquerading_as_image_is_rejected() -> None:
    with pytest.raises(UploadRejectedError):
        _sanitise(b"<html><body>not an image</body></html>")


def test_extension_is_irrelevant_only_magic_bytes_count() -> None:
    assert sniff_content_type(b"\xff\xd8\xff\xe0junk") == "image/jpeg"
    assert sniff_content_type(b"GIF89a") is None


def test_gif_is_not_in_the_allowlist() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "GIF")
    with pytest.raises(UploadRejectedError):
        _sanitise(buf.getvalue())


def test_polyglot_payload_does_not_survive_reencode(jpeg_bytes: bytes) -> None:
    """A JPEG+HTML polyglot may decode as an image; the payload must not persist."""
    polyglot = jpeg_bytes + b"<html><script>alert('xss')</script></html>"
    result = _sanitise(polyglot)
    assert b"<script" not in result.data
    assert b"<html" not in result.data


# --- C-28: decompression bomb and dimension limits ---------------------------------


def test_decompression_bomb_is_rejected() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (6000, 6000)).save(buf, "PNG", optimize=True)
    with pytest.raises(UploadRejectedError) as exc:
        _sanitise(buf.getvalue(), max_pixels=1_000_000)
    assert exc.value.code in {"decompression_bomb", "too_many_pixels"}


def test_oversized_dimensions_are_rejected() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (3000, 100)).save(buf, "PNG")
    with pytest.raises(UploadRejectedError) as exc:
        _sanitise(buf.getvalue(), max_dimension=1000)
    assert exc.value.code == "dimensions_too_large"


def test_oversized_byte_length_is_rejected(jpeg_bytes: bytes) -> None:
    with pytest.raises(UploadRejectedError) as exc:
        _sanitise(jpeg_bytes, max_bytes=10)
    assert exc.value.code == "too_large"


# --- C-29: EXIF and GPS stripping ---------------------------------------------------


def _jpeg_with_gps() -> bytes:
    image = Image.new("RGB", (40, 40), (9, 9, 9))
    exif = image.getexif()
    exif[ExifBase.ImageDescription.value] = "sensitive description"
    exif[ExifBase.Make.value] = "TestPhone"
    gps = exif.get_ifd(0x8825)
    gps[GPS.GPSLatitudeRef.value] = "N"
    gps[GPS.GPSLatitude.value] = (R(9, 1), R(1, 1), R(0, 1))
    gps[GPS.GPSLongitudeRef.value] = "E"
    gps[GPS.GPSLongitude.value] = (R(38, 1), R(45, 1), R(0, 1))
    buf = io.BytesIO()
    image.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_fixture_actually_contains_gps() -> None:
    """Guard the guard: if this fails, the stripping test below proves nothing."""
    exif = Image.open(io.BytesIO(_jpeg_with_gps())).getexif()
    assert dict(exif.get_ifd(0x8825))


def test_all_exif_and_gps_are_destroyed() -> None:
    result = _sanitise(_jpeg_with_gps())
    exif = Image.open(io.BytesIO(result.data)).getexif()
    assert not dict(exif)
    assert not dict(exif.get_ifd(0x8825))


# --- malformed input ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "code"),
    [(b"", "empty"), (b"\x00\x01\x02not an image", "unknown_format")],
)
def test_malformed_inputs_rejected(data: bytes, code: str) -> None:
    with pytest.raises(UploadRejectedError) as exc:
        _sanitise(data)
    assert exc.value.code == code


def test_truncated_jpeg_is_rejected(jpeg_bytes: bytes) -> None:
    with pytest.raises(UploadRejectedError) as exc:
        _sanitise(jpeg_bytes[: len(jpeg_bytes) // 3])
    assert exc.value.code == "undecodable"


def test_blob_keys_are_unpredictable(jpeg_bytes: bytes) -> None:
    """C-30: storage keys must not be guessable or derived from the filename."""
    keys = {_sanitise(jpeg_bytes).blob_key for _ in range(20)}
    assert len(keys) == 20
    assert all(len(k) >= 32 for k in keys)
