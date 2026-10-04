import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.core.exceptions.domain_exceptions import (
    FileEmptyError,
    FileSizeExceededError,
    UnsupportedImageFormatError,
)

Image.init()  # Fill pillow's internal format registry


@dataclass(frozen=True)
class ImageInfo:
    data: bytes
    width: int
    height: int
    size_bytes: int
    format: str
    mime_type: str
    extension: str


def validate_image(data: bytes) -> ImageInfo:
    if len(data) == 0:
        raise FileEmptyError()

    if len(data) > settings.max_user_avatar_bytes:
        raise FileSizeExceededError()

    try:
        with Image.open(io.BytesIO(data), formats=get_allowed_image_formats()) as img:
            if getattr(img, "is_animated", False):
                raise UnsupportedImageFormatError()

            width = img.width
            height = img.height

            if width * height > settings.max_user_avatar_pixels:
                raise FileSizeExceededError()

            img.load()

            image_format = img.format
            mime_type = get_mime_type(img.format)
            size_bytes = len(data)
            extension = f".{img.format.lower()}"

            return ImageInfo(
                data=data,
                width=width,
                height=height,
                size_bytes=size_bytes,
                format=image_format,
                mime_type=mime_type,
                extension=extension,
            )
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise UnsupportedImageFormatError() from exc


def get_allowed_image_formats() -> list[str]:
    return [
        image_format
        for image_format, mime_type in Image.MIME.items()
        if mime_type in settings.accepted_image_formats
    ]


def get_mime_type(image_format: str) -> str:
    for fmt, mime_type in Image.MIME.items():
        if fmt == image_format:
            return mime_type
    raise UnsupportedImageFormatError()
