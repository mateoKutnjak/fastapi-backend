"""Image validation boundaries, using tiny generated images."""

from io import BytesIO

import pytest
from PIL import Image

from app.config import settings
from app.core.exceptions.domain_exceptions import (
    FileEmptyError,
    FileSizeExceededError,
    UnsupportedImageFormatError,
)
from app.core.images import validate_image


def image_bytes(fmt="PNG", size=(10, 10), animated=False):
    output = BytesIO()
    image = Image.new("RGB", size, "red")
    if animated:
        image.save(
            output,
            format=fmt,
            save_all=True,
            append_images=[Image.new("RGB", size, "blue")],
            duration=100,
        )
    else:
        image.save(output, format=fmt)
    return output.getvalue()


@pytest.fixture(autouse=True)
def image_limits(monkeypatch):
    monkeypatch.setattr(
        settings, "accepted_image_formats", {"image/jpeg", "image/png", "image/webp"}
    )
    monkeypatch.setattr(settings, "max_user_avatar_bytes", 100_000)
    monkeypatch.setattr(settings, "max_user_avatar_pixels", 100)


@pytest.mark.parametrize(
    "fmt,mime,extension",
    [
        ("JPEG", "image/jpeg", ".jpeg"),
        ("PNG", "image/png", ".png"),
        ("WEBP", "image/webp", ".webp"),
    ],
)
def test_valid_image_metadata(fmt, mime, extension):
    data = image_bytes(fmt)
    info = validate_image(data)
    assert (info.format, info.mime_type, info.extension) == (fmt, mime, extension)
    assert (info.width, info.height, info.size_bytes, info.data) == (
        10,
        10,
        len(data),
        data,
    )


@pytest.mark.parametrize("delta,accepted", [(-1, False), (0, True), (1, True)])
def test_byte_limit_boundary(monkeypatch, delta, accepted):
    data = image_bytes()
    monkeypatch.setattr(settings, "max_user_avatar_bytes", len(data) + delta)
    if accepted:
        validate_image(data)
    else:
        with pytest.raises(FileSizeExceededError):
            validate_image(data)


@pytest.mark.parametrize("limit", [99, 100, 101])
def test_pixel_limit_boundary(monkeypatch, limit):
    monkeypatch.setattr(settings, "max_user_avatar_pixels", limit)
    if limit < 10 * 10:
        with pytest.raises(FileSizeExceededError):
            validate_image(image_bytes())
    else:
        validate_image(image_bytes())


def test_empty():
    with pytest.raises(FileEmptyError):
        validate_image(b"")


@pytest.mark.parametrize(
    "data", [b"hello", b"<svg></svg>", b"%PDF-1.7", b"\x89PNG\r\n\x1a\n"]
)
def test_non_images(data):
    with pytest.raises(UnsupportedImageFormatError):
        validate_image(data)


def test_truncated_png():
    with pytest.raises(UnsupportedImageFormatError):
        validate_image(image_bytes()[:45])


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_disallowed_real_format(fmt):
    with pytest.raises(UnsupportedImageFormatError):
        validate_image(image_bytes(fmt))


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_animated_images_rejected(fmt):
    with pytest.raises(UnsupportedImageFormatError):
        validate_image(image_bytes(fmt, animated=True))


def test_allowlist_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "accepted_image_formats", {"image/jpeg"})
    with pytest.raises(UnsupportedImageFormatError):
        validate_image(image_bytes("PNG"))
    assert validate_image(image_bytes("JPEG")).mime_type == "image/jpeg"
